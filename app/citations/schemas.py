"""Pydantic schemas for citation construction results."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Sequence

from pydantic import BaseModel, Field

from app.models.enums import DocumentType


class Citation(BaseModel):
    """Deterministic citation derived from a retrieved chunk."""

    model_config = {"arbitrary_types_allowed": True}

    document_id: uuid.UUID
    document_number: str | None = None
    document_type: DocumentType | None = None
    page_number: int = Field(ge=1)
    issue_date: date | None = None
    citation_text: str


class CitationBundle(BaseModel):
    """Aggregate citation set produced from a retrieval result."""

    citations: Sequence[Citation] = Field(default_factory=list)


Citation.model_rebuild()
CitationBundle.model_rebuild()
