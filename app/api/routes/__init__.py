"""
API route configuration and router setup.

Aggregates all API routes and provides the main router
for the FastAPI application. Every router except health and sign-in requires
at least the VIEWER role; individual routes raise that to EDITOR or ADMIN.
"""

from fastapi import APIRouter, Depends

from app.api.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.compare import router as compare_router
from app.api.routes.documents import router as documents_router
from app.api.routes.ingestion import router as ingestion_router
from app.api.routes.query import router as query_router
from app.api.routes.users import router as users_router
from app.api.security import require_viewer

viewer = [Depends(require_viewer)]

api_router = APIRouter()

# Public: health checks (for orchestrators) and sign-in.
api_router.include_router(health_router)
api_router.include_router(auth_router)

api_router.include_router(ingestion_router, dependencies=viewer)
api_router.include_router(query_router, dependencies=viewer)
api_router.include_router(compare_router, dependencies=viewer)
api_router.include_router(documents_router, dependencies=viewer)
api_router.include_router(users_router)
