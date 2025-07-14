import re
from datetime import datetime
from typing import List

VALID_HALLS = [
    'b-cafe', 'cafe-1919', 'epic-covel', 'de-neve', 
    'epic-ackerman', 'rende', 'feast', 'b-plate', 
    'drey', 'study'
]

VALID_ACTIVITY_LOCATIONS = [
    "b-cafe", "cafe-1919", "epic-covel", "de-neve", 
    "epic-ackerman", "rende", "feast", "b-plate", 
    "drey", "study", "b-fit", "wooden"
]

VALID_MEALS = ['breakfast', 'lunch', 'dinner', 'ext_dinner']

def validate_hall_id(hall_id: str) -> bool:
    """Validate hall ID"""
    return hall_id in VALID_HALLS

def validate_activity_location(location: str) -> bool:
    """Validate activity location"""
    return location in VALID_ACTIVITY_LOCATIONS

def validate_date(date: str) -> bool:
    """Validate date format (YYYY-MM-DD)"""
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        return False
    
    try:
        datetime.strptime(date, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_meal(meal: str) -> bool:
    """Validate meal type"""
    return meal in VALID_MEALS
