from typing import Dict, Any, Optional
from fastapi import HTTPException
from src.services.s3_service import s3_service
from src.utils.validation import validate_gym_id
from src.utils.response import create_response
import logging

logger = logging.getLogger(__name__)


async def get_all_gyms() -> Dict[str, Any]:
    """Get all UCLA recreation/gym facilities with hours and locations."""
    try:
        data, last_modified = await s3_service.get_data()
        gyms = data.get("gyms", {})

        result = [
            {"id": gym_id, **gym_data}
            for gym_id, gym_data in gyms.items()
        ]

        return create_response({
            "gyms": result,
            "lastUpdated": last_modified.isoformat() if last_modified else None,
        })
    except Exception as e:
        logger.error(f"Error in get_all_gyms: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_gym(gym_id: str) -> Dict[str, Any]:
    """Get details for a specific gym facility."""
    if not validate_gym_id(gym_id):
        raise HTTPException(status_code=400, detail="Invalid gym ID")

    try:
        data, last_modified = await s3_service.get_data()
        gym = data.get("gyms", {}).get(gym_id)
        if not gym:
            raise HTTPException(status_code=404, detail="Gym not found")

        return create_response({
            "id": gym_id,
            **gym,
            "lastUpdated": last_modified.isoformat() if last_modified else None,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_gym: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_gym_hours(gym_id: str, day: Optional[str] = None) -> Dict[str, Any]:
    """Get regular and special operating hours for a specific gym."""
    if not validate_gym_id(gym_id):
        raise HTTPException(status_code=400, detail="Invalid gym ID")

    try:
        data, last_modified = await s3_service.get_data()
        gym = data.get("gyms", {}).get(gym_id)
        if not gym:
            raise HTTPException(status_code=404, detail="Gym not found")

        hours = gym.get("hours", {})
        if day:
            day_lower = day.lower()[:3]
            if day_lower in hours:
                hours = {day_lower: hours[day_lower]}
            else:
                raise HTTPException(status_code=400, detail="Invalid day parameter")

        return create_response({
            "gymId": gym_id,
            "hoursLabel": gym.get("hours_label"),
            "hours": hours,
            "specialHours": gym.get("special_hours", {}),
            "notes": gym.get("notes", []),
            "lastUpdated": last_modified.isoformat() if last_modified else None,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_gym_hours: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
