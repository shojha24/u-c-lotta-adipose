from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from src.services.s3_service import s3_service
from src.utils.response import create_response
import logging
import re
import requests

logger = logging.getLogger(__name__)

NUTRITION_CALC_API = "https://dining.ucla.edu/wp-content/plugins/custom-short-code/nutrition_calc_ajax.php"

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


def _build_nutrition_payload(items_param: str) -> str:
    """
    Normalize an items query string into UCLA's nutrition_calc_ajax.php format:
      '<id>,<type>,<multiplier>;...'
    Accepts either:
      - Native format: '4318,recipe,1;2201,subrecipe,2;'
      - Shorthand format: '4318:1,2201:2' or '4318,2201'
    """
    raw = items_param.strip()
    if not raw:
        raise ValueError("items parameter cannot be empty")

    if ";" in raw or re.search(r"\b(recipe|subrecipe)\b", raw):
        parts = [p.strip() for p in raw.split(";") if p.strip()]
        normalized = []
        for part in parts:
            fields = [f.strip() for f in part.split(",")]
            if len(fields) != 3 or not fields[0].isdigit():
                raise ValueError(f"Invalid item entry: {part}")
            item_id, item_type, mult = fields
            if item_type not in ("recipe", "subrecipe"):
                raise ValueError(f"Invalid item type: {item_type}")
            float(mult)
            normalized.append(f"{item_id},{item_type},{mult};")
        return "".join(normalized)

    # Shorthand: '4318:1,2201:2' or '4318,2201'
    normalized = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            item_id, mult = [x.strip() for x in entry.split(":", 1)]
        else:
            item_id, mult = entry, "1"
        if not item_id.isdigit():
            raise ValueError(f"Invalid item ID: {item_id}")
        float(mult)
        normalized.append(f"{item_id},recipe,{mult};")

    if not normalized:
        raise ValueError("No valid items provided")
    return "".join(normalized)


async def calculate_nutrition(items_param: str) -> Dict[str, Any]:
    """Calculate combined nutrition for one or more menu items via UCLA's nutrition API."""
    try:
        payload = _build_nutrition_payload(items_param)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        response = requests.get(
            NUTRITION_CALC_API,
            params={"items": payload},
            timeout=10,
        )
        response.raise_for_status()
        nutrition = response.json()
        return create_response({
            "items": payload,
            "nutrition": nutrition,
        })
    except requests.RequestException as e:
        logger.error(f"Error calling UCLA nutrition API: {str(e)}")
        raise HTTPException(status_code=502, detail="Error fetching nutrition data from UCLA")
    except ValueError as e:
        logger.error(f"Invalid JSON from UCLA nutrition API: {str(e)}")
        raise HTTPException(status_code=502, detail="Invalid response from UCLA nutrition API")
