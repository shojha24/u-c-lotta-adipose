import boto3
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.environ.get('S3_BUCKET_NAME')
        self.data_key = os.environ.get('S3_DATA_KEY', 'dining-data.json')
        self.cache: Optional[Dict[str, Any]] = None
        self.cache_timestamp: Optional[datetime] = None

    async def get_data(self) -> tuple[Dict[str, Any], Optional[datetime]]:
        """
        Get dining data from S3 with proactive cache validation.
        Returns a tuple of (data, last_modified_timestamp).
        """
        try:
            head_response = self.s3_client.head_object(
                Bucket=self.bucket_name, Key=self.data_key
            )
            s3_last_modified = head_response['LastModified']

            # If we have a cache, check if it's stale by comparing timestamps
            if self.cache and self.cache_timestamp:
                if self.cache_timestamp.tzinfo is None:
                    self.cache_timestamp = self.cache_timestamp.replace(tzinfo=timezone.utc)
                
                if s3_last_modified <= self.cache_timestamp:
                    logger.info("Returning fresh data from in-memory cache.")
                    return self.cache, self.cache_timestamp

            # If cache is stale or doesn't exist, fetch new data
            logger.info("Cache is stale or empty. Fetching new data from S3.")
            response = self.s3_client.get_object(
                Bucket=self.bucket_name, Key=self.data_key
            )
            data = json.loads(response['Body'].read().decode('utf-8'))
            
            # Update cache and timestamp with the new data's modification date
            self.cache = data
            self.cache_timestamp = s3_last_modified
            
            return data, s3_last_modified
            
        except Exception as e:
            logger.error(f"Error fetching data from S3: {str(e)}")
            # As a fallback, return the stale cache if an S3 error occurs
            if self.cache:
                logger.warning("Falling back to stale cache due to S3 error.")
                return self.cache, self.cache_timestamp
            raise Exception("Failed to fetch dining data")

# Singleton instance
s3_service = S3Service()
