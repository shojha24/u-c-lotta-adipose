from typing import Dict, Any
from fastapi import HTTPException
from src.services.s3_service import s3_service
from src.utils.response import create_response
import logging

logger = logging.getLogger(__name__)

async def get_trucks() -> Dict[str, Any]:
    """Get food truck information"""
    try:
        data, last_modified = await s3_service.get_data()
        
        trucks = data.get('trucks', {})
        
        return create_response({
            'trucks': trucks,
            'lastUpdated': last_modified.isoformat() if last_modified else None
        })
        
    except Exception as e:
        logger.error(f"Error in get_trucks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
