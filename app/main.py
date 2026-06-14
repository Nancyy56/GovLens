"""
FastAPI application factory and configuration.

Creates and configures the FastAPI application instance with
middleware, error handlers, and route registration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.constants import API_V1_STR, PROJECT_NAME, PROJECT_DESCRIPTION
from app.api.routes import api_router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Sets up:
    - Application metadata
    - CORS middleware
    - API routes
    - Exception handlers
    
    Returns:
        FastAPI: Configured application instance.
    """
    app = FastAPI(
        title=PROJECT_NAME,
        description=PROJECT_DESCRIPTION,
        version="0.1.0",
        debug=settings.debug,
    )
    
    # Add CORS middleware to allow cross-origin requests
    # Configure for your specific needs in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes under /api/v1 prefix
    app.include_router(api_router, prefix=API_V1_STR)
    
    return app


# Create application instance
app = create_app()


@app.on_event("startup")
async def startup_event() -> None:
    """
    Perform initialization tasks on application startup.
    
    This event runs once when the application starts.
    Place database connection setup, cache initialization,
    or other startup logic here.
    """
    print(f"Starting {PROJECT_NAME} in {settings.env} mode")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """
    Perform cleanup tasks on application shutdown.
    
    This event runs when the application is shutting down.
    Close database connections, cleanup resources here.
    """
    print(f"Shutting down {PROJECT_NAME}")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
