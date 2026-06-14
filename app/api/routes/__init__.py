"""
API route configuration and router setup.

Aggregates all API routes and provides the main router
for the FastAPI application.
"""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.query import router as query_router

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(health_router)
api_router.include_router(ingestion_router)
api_router.include_router(query_router)
