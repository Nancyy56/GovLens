"""Saved documents and private notes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.security import Principal, require_viewer
from app.db.database import get_session
from app.services.bookmarks import BookmarkRead, BookmarkService

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


class BookmarkRequest(BaseModel):
    note: str | None = Field(default=None, max_length=4000, description="Omit to keep the current note.")


def _service(session: Session = Depends(get_session)) -> BookmarkService:
    return BookmarkService(session)


@router.get("", response_model=list[BookmarkRead])
def list_bookmarks(principal: Principal = Depends(require_viewer), service: BookmarkService = Depends(_service)):
    """Your saved documents, most recently touched first."""

    return service.list(principal.username)


@router.put("/{document_id}", response_model=BookmarkRead)
def save_bookmark(
    document_id: uuid.UUID,
    request: BookmarkRequest,
    principal: Principal = Depends(require_viewer),
    service: BookmarkService = Depends(_service),
):
    """Save a document, or update the note on one you already saved."""

    return service.save(principal.username, document_id, request.note)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_bookmark(document_id: uuid.UUID, principal: Principal = Depends(require_viewer), service: BookmarkService = Depends(_service)):
    if not service.remove(principal.username, document_id):
        raise HTTPException(status_code=404, detail="That document is not saved")
