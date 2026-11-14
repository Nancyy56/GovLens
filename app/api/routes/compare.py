"""Document comparison route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_comparison_service
from app.api.schemas import CompareRequest
from app.services.comparison import ComparisonResult, ComparisonService

router = APIRouter(prefix="/compare", tags=["comparison"])


@router.post("", response_model=ComparisonResult)
def compare_documents(
    request: CompareRequest,
    service: ComparisonService = Depends(get_comparison_service),
):
    """Show what changed between two documents, with an optional plain-language summary."""

    try:
        return service.compare(request.base, request.target, focus=request.focus, summarize=request.summarize)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
