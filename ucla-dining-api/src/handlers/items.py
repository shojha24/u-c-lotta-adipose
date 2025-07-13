from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from src.services.s3_service import s3_service
from src.utils.response import create_response
import logging

logger = logging.getLogger(__name__)

async def get_item(item_id: str) -> Dict[str, Any]:
    """Get specific item details"""
    try:
        data, last_modified = await s3_service.get_data()
        
        item = data.get('items', {}).get(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        result = {
            'id': item_id,
            **item,
            'lastUpdated': last_modified.isoformat() if last_modified else None
        }
        
        return create_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def search_items(q: Optional[str] = None, dietary: Optional[str] = None, 
                      allergen: Optional[str] = None) -> Dict[str, Any]:
    """Search items by query, dietary restrictions, or allergens"""
    try:
        data, last_modified = await s3_service.get_data()
        
        items = data.get('items', {})
        results = []
        
        for item_id, item_data in items.items():
            # Text search
            if q and q.lower() not in item_data.get('name', '').lower():
                continue
            
            # Dietary filter
            if dietary:
                labels = item_data.get('labels', [])
                if dietary.lower() not in [label.lower() for label in labels]:
                    continue
            
            # Allergen filter
            if allergen:
                labels = item_data.get('labels', [])
                if allergen.lower() in [label.lower() for label in labels]:
                    continue  # Skip items that contain the allergen
            
            results.append({
                'id': item_id,
                'name': item_data.get('name'),
                'labels': item_data.get('labels', []),
                'calories': item_data.get('calories')
            })
        
        return create_response({
            'items': results,
            'count': len(results),
            'lastUpdated': last_modified.isoformat() if last_modified else None
        })
        
    except Exception as e:
        logger.error(f"Error in search_items: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
