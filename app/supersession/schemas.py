"""Pydantic schemas for supersession analysis results."""

from __future__ import annotations

import uuid
from typing import Sequence

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus


class DocumentReference(BaseModel):
    """Minimal identifier for a document appearing in the supersession chain."""

    document_id: uuid.UUID
    document_number: str


class SupersessionResult(BaseModel):
    """Analysis result for a single document's supersession status."""

    document_id: uuid.UUID
    document_number: str | None = None
    status: DocumentStatus | None = None
    is_superseded: bool = False
    latest_document_id: uuid.UUID
    latest_document_number: str | None = None
    superseded_by_document_id: uuid.UUID | None = None
    superseded_by_document_number: str | None = None
    supersession_chain: Sequence[DocumentReference] = Field(default_factory=list)


SupersessionResult.model_rebuild()
