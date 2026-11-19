from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from fastapi.responses import JSONResponse

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


def seconds_until_end_of_day(now: Optional[datetime] = None, min_seconds: int = 60) -> int:
    """Compute seconds remaining until midnight (00:00:00) America/Los_Angeles."""
    current = now.astimezone(PACIFIC_TZ) if now else datetime.now(PACIFIC_TZ)
    next_day = current.date() + timedelta(days=1)
    midnight = datetime(next_day.year, next_day.month, next_day.day, tzinfo=PACIFIC_TZ)
    remaining = int((midnight - current).total_seconds())
    return max(remaining, min_seconds)


def create_response(
    data: Dict[str, Any],
    status_code: int = 200,
    headers: Dict[str, str] = None,
    cache_ttl: Optional[int] = None,
) -> JSONResponse:
    """Create a standardized JSON response with end-of-day TTL caching by default."""
    ttl = seconds_until_end_of_day() if cache_ttl is None else max(0, int(cache_ttl))
    cache_control = f"public, max-age={ttl}" if ttl > 0 else "no-cache"

    default_headers = {
        'Cache-Control': cache_control,
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,OPTIONS',
    }

    if headers:
        default_headers.update(headers)

    return JSONResponse(
        content=data,
        status_code=status_code,
        headers=default_headers,
    )


def create_error_response(status_code: int, message: str) -> JSONResponse:
    """Create a standardized error response"""
    return JSONResponse(
        content={
            'error': {
                'message': message,
                'statusCode': status_code,
            }
        },
        status_code=status_code,
        headers={
            'Access-Control-Allow-Origin': '*',
        },
    )
