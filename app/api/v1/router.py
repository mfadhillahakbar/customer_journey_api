from fastapi import APIRouter
from app.api.v1.endpoints import button_clicks, filters, health

api_v1_router = APIRouter()

# Mount analytics routes under /api/v1
api_v1_router.include_router(button_clicks.router)
api_v1_router.include_router(filters.router)
api_v1_router.include_router(health.router)
