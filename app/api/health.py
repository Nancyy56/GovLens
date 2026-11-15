"""
Health check endpoints.

``/health`` is a cheap liveness check. ``/health/ready`` verifies that the
services GovLens depends on are reachable, for readiness probes and for
checking a deployment before a demo.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.dependencies import get_llm_client, get_reranker, get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str


class DependencyCheck(BaseModel):
    ok: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, DependencyCheck]


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness: the API process is running."""
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}})
def readiness_check():
    """Readiness: PostgreSQL, Qdrant, and Ollama (with the configured model) are reachable."""

    checks = {
        "database": _check(_ping_database),
        "qdrant": _check(lambda: get_vector_store().ping()),
        "ollama": _check(lambda: get_llm_client().ping()),
    }
    reranker = get_reranker()
    if reranker is not None and not reranker.available:
        # Informational: retrieval still works without the reranker.
        checks["reranker"] = DependencyCheck(ok=False, detail="Model failed to load; reranking disabled")

    required_ok = all(checks[name].ok for name in ("database", "qdrant", "ollama"))
    body = ReadinessResponse(status="ok" if required_ok else "degraded", checks=checks)
    return JSONResponse(status_code=200 if required_ok else 503, content=body.model_dump())


def _ping_database() -> None:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))


def _check(probe: Callable[[], None]) -> DependencyCheck:
    try:
        probe()
        return DependencyCheck(ok=True)
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        return DependencyCheck(ok=False, detail=str(exc) or exc.__class__.__name__)
