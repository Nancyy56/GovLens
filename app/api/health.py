"""
Health check endpoint.

Provides liveness and readiness checks for the application.
Used by orchestration platforms and monitoring systems.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
        HealthResponse: Status of the application.
        
    Example:
        GET /health
        
        Response:
        {
            "status": "healthy"
        }
    """
    return HealthResponse(status="ok")
