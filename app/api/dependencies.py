"""FastAPI dependency providers for application services."""

from __future__ import annotations

from app.services.dependencies import (
    get_classifier,
    get_comparison_service,
    get_document_service,
    get_embedding_provider,
    get_ingestion_service,
    get_job_runner,
    get_llm_client,
    get_query_service,
    get_vector_store,
)

__all__ = [
    "get_classifier",
    "get_comparison_service",
    "get_document_service",
    "get_embedding_provider",
    "get_ingestion_service",
    "get_job_runner",
    "get_llm_client",
    "get_query_service",
    "get_vector_store",
]
