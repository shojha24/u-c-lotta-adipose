from typing import Dict, Any, Optional
from fastapi import HTTPException
from src.utils.response import create_response
from src.utils.validation import validate_activity_location
from datetime import datetime
import requests
import logging
import re

logger = logging.getLogger(__name__)

ACTIVITY_MAP = {
    "b-cafe": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=867",
    "cafe-1919": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=867",
    "epic-covel": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=864",
    "de-neve": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=866",
    "epic-ackerman": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=874",
    "rende": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=870",
    "feast": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=872",
    "b-plate": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=864",
    "drey": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=869",
    "study": "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php?location_id=871",
    "b-fit": "https://goboardapi.azurewebsites.net/api/FacilityCount/GetCountsByAccount?AccountAPIKey=73829a91-48cb-4b7b-bd0b-8cf4134c04cd",
    "wooden": "https://goboardapi.azurewebsites.net/api/FacilityCount/GetCountsByAccount?AccountAPIKey=73829a91-48cb-4b7b-bd0b-8cf4134c04cd",
    "kinross": "https://goboardapi.azurewebsites.net/api/FacilityCount/GetCountsByAccount?AccountAPIKey=73829a91-48cb-4b7b-bd0b-8cf4134c04cd"
}

ID_NAME_MAP = {
    'b-fit': 'Bruin Fitness Center - FITWELL',
    'wooden': 'John Wooden Center - FITWELL',
    'kinross': 'Kinross Rec Center - FITWELL'
}

INVERTED_ID_NAME_MAP = {v: k for k, v in ID_NAME_MAP.items()}

async def get_all_activity() -> Dict[str, Any]:
    """
    Fetches the activity percentage for all locations (dining halls and gyms).
    """
    try:
        results = {}
        # Fetch and process gym data from the single API endpoint
        gym_url = ACTIVITY_MAP['b-fit']
        response = requests.get(gym_url)
        response.raise_for_status()
        data = response.json()

        for facility in data:
            # CORRECTED: Use the inverted map to find the short code from the full name
            gym_code = INVERTED_ID_NAME_MAP.get(facility['FacilityName'])
            
            if gym_code:
                if gym_code not in results:
                    results[gym_code] = {}
                
                results[gym_code][facility['LocationName']] = {
                    'lastCount': facility['LastCount'],
                    'isClosed': facility['IsClosed'],
                    'capacity': facility['TotalCapacity']
                }
        
        # Handle dining halls by iterating through all locations
        for location_id, url in ACTIVITY_MAP.items():
            # Skip gyms, as they have already been processed
            if location_id in ID_NAME_MAP:
                continue

            response = requests.get(url)
            response.raise_for_status()
            activity_match = re.search(r'(\d+%)', response.text)
            
            if activity_match:
                results[location_id] = activity_match.group(1)
            else:
                # Log a warning instead of raising an exception for one failure
                logger.warning(f"Activity data not found for {location_id}")
                results[location_id] = "Not available"

        return create_response(results)

    except requests.RequestException as e:
        logger.error(f"Error fetching activity data: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching activity data")
    

async def get_activity(location_id: str) -> Dict[str, Any]:
    """
    Fetches the activity percentage for a given dining location.
    
    Args:
        location_id (str): The ID of the dining location.
    
    Returns:
        Dict[str, Any]: A dictionary containing the activity percentage.
    
    Raises:
        HTTPException: If the location ID is not found or if there is an error fetching data.
    """
    if not validate_activity_location(location_id):
        raise HTTPException(status_code=404, detail="Invalid location ID")

    try:
        response = requests.get(ACTIVITY_MAP[location_id])
        response.raise_for_status()

        gym_name = ID_NAME_MAP.get(location_id, None)
        
        if gym_name:
            # For b-fit and wooden, the response is an xml file.
            data = response.json()

            areas = {}
    
            for facility in data:
                if facility['FacilityName'] == gym_name:
                    gym_area = facility['LocationName']
                    last_ct = facility['LastCount']
                    closed = facility['IsClosed']
                    capacity = facility['TotalCapacity']
                    areas[gym_area] = {
                        'lastCount': last_ct,
                        'isClosed': closed,
                        'capacity': capacity
                    }

            return create_response({location_id: areas})
        
        else:
            activity_match = re.search(r'(\d+%)', response.text)
            if activity_match:
                return create_response({location_id: activity_match.group(1)})
            else:
                raise HTTPException(status_code=500, detail="Activity data not found")
    
    except requests.RequestException as e:
        logger.error(f"Error fetching activity for {location_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching activity data")
