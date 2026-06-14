"""FastAPI dependency providers for application services."""

from __future__ import annotations

from app.services.dependencies import (
    get_classifier,
    get_embedding_provider,
    get_ingestion_service,
    get_query_service,
    get_vector_store,
)
from app.services import DocumentIngestionService, QueryService

__all__ = [
    "get_ingestion_service",
    "get_query_service",
]
