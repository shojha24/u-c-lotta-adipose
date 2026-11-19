import boto3
import gzip
import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
STALE_RETRY_SECONDS = 300  # 5 minutes if S3 hasn't been updated yet after midnight


def _next_end_of_day_pacific(now: Optional[datetime] = None) -> datetime:
    """Return the next midnight (00:00:00) in America/Los_Angeles."""
    current = now.astimezone(PACIFIC_TZ) if now else datetime.now(PACIFIC_TZ)
    next_day = current.date() + timedelta(days=1)
    return datetime(next_day.year, next_day.month, next_day.day, tzinfo=PACIFIC_TZ)


class S3Service:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.environ.get('S3_BUCKET_NAME')
        self.data_key = os.environ.get('S3_DATA_KEY', 'dining-data.json')
        self.cache: Optional[Dict[str, Any]] = None
        self.cache_timestamp: Optional[datetime] = None
        self.cache_expires_at: Optional[datetime] = None

    def _is_cache_valid(self, now: Optional[datetime] = None) -> bool:
        """Check whether the in-memory cache is still valid (before end-of-day PT)."""
        if self.cache is None or self.cache_expires_at is None:
            return False
        current = now.astimezone(PACIFIC_TZ) if now else datetime.now(PACIFIC_TZ)
        return current < self.cache_expires_at

    def invalidate_cache(self) -> None:
        """Manually clear the in-memory cache."""
        self.cache = None
        self.cache_timestamp = None
        self.cache_expires_at = None

    async def get_data(self) -> tuple[Dict[str, Any], Optional[datetime]]:
        """
        Get dining data from S3 with end-of-day Pacific Time TTL caching.
        Avoids all S3 calls (including HeadObject) while the cached data is
        still within the current Pacific calendar day.
        Returns a tuple of (data, last_modified_timestamp).
        """
        now_pt = datetime.now(PACIFIC_TZ)

        if self._is_cache_valid(now_pt):
            logger.info("Returning data from in-memory end-of-day cache (0 S3 calls).")
            return self.cache, self.cache_timestamp

        try:
            # If we already have cached data from a previous day, check HeadObject first
            # to see if the daily scraper has uploaded a newer file yet.
            if self.cache is not None and self.cache_timestamp is not None:
                head_response = self.s3_client.head_object(
                    Bucket=self.bucket_name, Key=self.data_key
                )
                s3_last_modified = head_response['LastModified']
                cached_ts = self.cache_timestamp
                if cached_ts.tzinfo is None:
                    cached_ts = cached_ts.replace(tzinfo=timezone.utc)

                if s3_last_modified <= cached_ts:
                    # Scraper hasn't updated S3 yet today; keep serving cache and re-check soon
                    self.cache_expires_at = now_pt + timedelta(seconds=STALE_RETRY_SECONDS)
                    logger.info(
                        "S3 data unchanged since last load; extending cache briefly."
                    )
                    return self.cache, self.cache_timestamp

            # Cold start or newer object available: fetch in a single GetObject call
            logger.info("Fetching dining data from S3.")
            response = self.s3_client.get_object(
                Bucket=self.bucket_name, Key=self.data_key
            )
            raw_bytes = response['Body'].read()
            if raw_bytes[:2] == b'\x1f\x8b':
                raw_bytes = gzip.decompress(raw_bytes)
            data = json.loads(raw_bytes.decode('utf-8'))
            s3_last_modified = response.get('LastModified', datetime.now(timezone.utc))

            self.cache = data
            self.cache_timestamp = s3_last_modified
            self.cache_expires_at = _next_end_of_day_pacific(now_pt)

            logger.info(
                f"Cached dining data from S3 until {self.cache_expires_at.isoformat()}."
            )
            return data, s3_last_modified

        except Exception as e:
            logger.error(f"Error fetching data from S3: {str(e)}")
            if self.cache is not None:
                logger.warning("Falling back to stale cache due to S3 error.")
                return self.cache, self.cache_timestamp
            raise Exception("Failed to fetch dining data")


# Singleton instance
s3_service = S3Service()
