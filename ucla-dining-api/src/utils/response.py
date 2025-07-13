from typing import Dict, Any
from fastapi import Response
from fastapi.responses import JSONResponse

def create_response(data: Dict[str, Any], status_code: int = 200, 
                   headers: Dict[str, str] = None) -> JSONResponse:
    """Create a standardized JSON response"""
    default_headers = {
        'Cache-Control': 'public, max-age=3600',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,OPTIONS'
    }
    
    if headers:
        default_headers.update(headers)
    
    return JSONResponse(
        content=data,
        status_code=status_code,
        headers=default_headers
    )

def create_error_response(status_code: int, message: str) -> JSONResponse:
    """Create a standardized error response"""
    return JSONResponse(
        content={
            'error': {
                'message': message,
                'statusCode': status_code
            }
        },
        status_code=status_code,
        headers={
            'Access-Control-Allow-Origin': '*'
        }
    )
