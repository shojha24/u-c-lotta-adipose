import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from src.handlers import activity, halls, trucks, items
from src.utils.response import create_error_response
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="UCLA Dining API",
    description="REST API for UCLA dining hall information",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ucla-dining-api"}

# Activity endpoints
@app.get("/activity")
async def get_activity():
    return await activity.get_all_activity()

@app.get("/activity/{location_id}")
async def get_activity(location_id: str):
    return await activity.get_activity(location_id)

# Halls endpoints
@app.get("/halls")
async def get_all_halls(open: bool = None):
    return await halls.get_all_halls(open)

@app.get("/halls/{hall_id}")
async def get_hall(hall_id: str):
    return await halls.get_hall(hall_id)

@app.get("/halls/{hall_id}/hours")
async def get_hall_hours(hall_id: str, day: str = None):
    return await halls.get_hall_hours(hall_id, day)

@app.get("/halls/{hall_id}/menu")
async def get_hall_menu(hall_id: str, date: str = None, meal: str = None):
    return await halls.get_hall_menu(hall_id, date, meal)

@app.get("/halls/{hall_id}/menu/{date}")
async def get_hall_menu_by_date(hall_id: str, date: str):
    return await halls.get_hall_menu_by_date(hall_id, date)

# Trucks endpoint
@app.get("/trucks")
async def get_trucks():
    return await trucks.get_trucks()

# Items endpoint
@app.get("/items/{item_id}")
async def get_item(item_id: str):
    return await items.get_item(item_id)

# Search endpoint
@app.get("/search")
async def search_items(q: str = None, dietary: str = None, allergen: str = None):
    return await items.search_items(q, dietary, allergen)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return create_error_response(500, "Internal server error")

# Lambda handler
handler = Mangum(app)
