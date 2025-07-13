from typing import Dict, Any, Optional
from fastapi import HTTPException
from src.services.s3_service import s3_service
from src.utils.validation import validate_hall_id, validate_date
from src.utils.response import create_response
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

HALL_NAME_MAP = {
    'b-cafe': 'Bruin Cafe',
    'cafe-1919': 'Cafe 1919',
    'epic-covel': 'Epicuria at Covel',
    'de-neve': 'De Neve Dining',
    'epic-ackerman': 'Epicuria at Ackerman',
    'rende': 'Rendezvous',
    'feast': 'Feast at Rieber',
    'b-plate': 'Bruin Plate',
    'drey': 'The Drey',
    'study': 'The Study at Hedrick'
}

async def get_all_halls(open_only: Optional[bool] = None) -> Dict[str, Any]:
    """Get all dining halls"""
    try:
        data, last_modified = await s3_service.get_data()
        
        halls = data.get('halls', {})
        
        result = []
        for hall_id, hall_data in halls.items():
            hall_info = {
                'id': hall_id,
                'name': HALL_NAME_MAP.get(hall_id, hall_id),
                'link': hall_data.get('link'),
                'isOpen': is_hall_currently_open(hall_data)
            }
            
            if open_only is None or (open_only and hall_info['isOpen']) or (not open_only):
                result.append(hall_info)
        
        if open_only:
            result = [hall for hall in result if hall['isOpen']]
        
        return create_response({
            'halls': result,
            'lastUpdated': last_modified.isoformat() if last_modified else None
        })
        
    except Exception as e:
        logger.error(f"Error in get_all_halls: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_hall(hall_id: str) -> Dict[str, Any]:
    """Get specific hall details"""
    if not validate_hall_id(hall_id):
        raise HTTPException(status_code=400, detail="Invalid hall ID")
    
    try:
        data, last_modified = await s3_service.get_data()
        
        hall = data.get('halls', {}).get(hall_id)
        if not hall:
            raise HTTPException(status_code=404, detail="Hall not found")
        
        result = {
            'id': hall_id,
            'name': HALL_NAME_MAP.get(hall_id, hall_id),
            'link': hall.get('link'),
            'hours': hall.get('hours', {}),
            'isOpen': is_hall_currently_open(hall),
            'lastUpdated': last_modified.isoformat() if last_modified else None
        }
        
        return create_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_hall: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_hall_hours(hall_id: str, day: Optional[str] = None) -> Dict[str, Any]:
    """Get hall hours"""
    if not validate_hall_id(hall_id):
        raise HTTPException(status_code=400, detail="Invalid hall ID")
    
    try:
        data, last_modified = await s3_service.get_data()
        
        hall = data.get('halls', {}).get(hall_id)
        if not hall:
            raise HTTPException(status_code=404, detail="Hall not found")
        
        hours = hall.get('hours', {})
        
        if day:
            day_lower = day.lower()
            if day_lower in hours:
                hours = {day_lower: hours[day_lower]}
            else:
                raise HTTPException(status_code=400, detail="Invalid day parameter")
        
        return create_response({
            'hallId': hall_id,
            'hours': hours,
            'lastUpdated': last_modified.isoformat() if last_modified else None
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_hall_hours: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_hall_menu(hall_id: str, date: Optional[str] = None, 
                       meal: Optional[str] = None) -> Dict[str, Any]:
    """Get hall menu"""
    if not validate_hall_id(hall_id):
        raise HTTPException(status_code=400, detail="Invalid hall ID")
    
    if date and not validate_date(date):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    try:
        data, last_modified = await s3_service.get_data()
        
        hall = data.get('halls', {}).get(hall_id)
        if not hall:
            raise HTTPException(status_code=404, detail="Hall not found")
        
        menu = hall.get('menu', {})
        
        if date:
            if date in menu:
                menu = {date: menu[date]}
                
                if meal and isinstance(menu[date], dict) and meal in menu[date]:
                    menu[date] = {meal: menu[date][meal]}
            else:
                raise HTTPException(status_code=404, detail="Menu not found for specified date")
        
        return create_response({
            'hallId': hall_id,
            'menu': menu,
            'lastUpdated': last_modified.isoformat() if last_modified else None
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_hall_menu: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_hall_menu_by_date(hall_id: str, date: str) -> Dict[str, Any]:
    """Get hall menu for specific date"""
    if not validate_hall_id(hall_id) or not validate_date(date):
        raise HTTPException(status_code=400, detail="Invalid hall ID or date format")
    
    try:
        data, last_modified = await s3_service.get_data()
        
        hall = data.get('halls', {}).get(hall_id)
        if not hall or date not in hall.get('menu', {}):
            raise HTTPException(status_code=404, detail="Menu not found")
        
        return create_response({
            'hallId': hall_id,
            'date': date,
            'menu': hall['menu'][date],
            'lastUpdated': last_modified.isoformat() if last_modified else None
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_hall_menu_by_date: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def is_hall_currently_open(hall: Dict[str, Any]) -> bool:
    """Check if hall is currently open"""
    try:
        now = datetime.now()
        current_day = now.strftime('%a').lower()
        current_time = now.strftime('%H:%M')
        
        day_hours = hall.get('hours', {}).get(current_day, {})
        if not day_hours:
            return False
        
        # Check each meal period
        for meal, hours in day_hours.items():
            if hours and hours != 'Closed' and is_time_in_range(current_time, hours):
                return True
        
        return False
    except Exception:
        return False

def is_time_in_range(current_time: str, time_range: str) -> bool:
    """Check if current time is within the given range"""
    try:
        if not time_range or time_range == 'Closed':
            return False
        
        # Parse time range (e.g., "7:00 a.m. - 9:00 a.m.")
        import re
        match = re.search(r'(\d{1,2}:\d{2})\s*([ap]\.?m\.?)\s*-\s*(\d{1,2}:\d{2})\s*([ap]\.?m\.?)', 
                         time_range, re.IGNORECASE)
        if not match:
            return False
        
        start_time, start_period, end_time, end_period = match.groups()
        
        start_24 = convert_to_24_hour(start_time, start_period)
        end_24 = convert_to_24_hour(end_time, end_period)
        
        return start_24 <= current_time <= end_24
    except Exception:
        return False

def convert_to_24_hour(time_str: str, period: str) -> str:
    """Convert 12-hour time to 24-hour format"""
    try:
        hours, minutes = time_str.split(':')
        hour = int(hours)
        
        if 'p' in period.lower() and hour != 12:
            hour += 12
        elif 'a' in period.lower() and hour == 12:
            hour = 0
        
        return f"{hour:02d}:{minutes}"
    except Exception:
        return "00:00"
