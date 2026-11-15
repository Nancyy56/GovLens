"""Per-user query history and answer feedback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import uuid

from app.api.security import Principal, require_viewer
from app.db.database import get_session
from app.services.history import FeedbackRequest, HistoryDetail, HistoryPage, HistoryService

router = APIRouter(prefix="/history", tags=["history"])


def _service(session: Session = Depends(get_session)) -> HistoryService:
    return HistoryService(session)


@router.get("", response_model=HistoryPage)
def list_history(
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=200),
    principal: Principal = Depends(require_viewer),
    service: HistoryService = Depends(_service),
):
    """Your own past questions, newest first."""

    return service.list(principal.username, limit=limit, offset=offset, search=search)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_history(principal: Principal = Depends(require_viewer), service: HistoryService = Depends(_service)):
    service.clear(principal.username)


@router.get("/{log_id}", response_model=HistoryDetail)
def get_history(log_id: uuid.UUID, principal: Principal = Depends(require_viewer), service: HistoryService = Depends(_service)):
    item = service.get(principal.username, log_id)
    if item is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    return item


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(log_id: uuid.UUID, principal: Principal = Depends(require_viewer), service: HistoryService = Depends(_service)):
    if not service.delete(principal.username, log_id):
        raise HTTPException(status_code=404, detail="History entry not found")


@router.post("/{log_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def give_feedback(
    log_id: uuid.UUID,
    request: FeedbackRequest,
    principal: Principal = Depends(require_viewer),
    service: HistoryService = Depends(_service),
):
    """Rate an answer: 1 helpful, -1 not helpful, 0 to clear."""

    try:
        found = service.set_feedback(principal.username, log_id, request.rating, request.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=404, detail="History entry not found")
