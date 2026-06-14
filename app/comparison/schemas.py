"""Pydantic schemas for comparison preparation results."""

from __future__ import annotations

import uuid
from typing import Sequence

from pydantic import BaseModel, Field

from app.schemas.processing import PageContent
from app.models.enums import DocumentType


class SourceContext(BaseModel):
    """Chunks and minimal metadata for one source document."""

    model_config = {"arbitrary_types_allowed": True}

    document_id: uuid.UUID
    document_number: str | None = None
    document_type: DocumentType | None = None
    chunks: Sequence[PageContent]


class ComparisonInput(BaseModel):
    """Structured input prepared for future comparison/answer generation."""

    query: str
    sources: Sequence[SourceContext] = Field(default_factory=list)


SourceContext.model_rebuild()
ComparisonInput.model_rebuild()
