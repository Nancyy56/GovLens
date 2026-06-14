"""Pydantic schemas for retrieval results."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Sequence

from pydantic import BaseModel, Field

from app.models.enums import DocumentType


class RetrievedChunk(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    document_id: uuid.UUID
    document_number: str | None = None
    document_type: DocumentType | None = None

    title: str | None = None
    file_name: str | None = None
    department: str | None = None
    subject: str | None = None

    page_number: int = Field(ge=1)
    chunk_index: int = Field(ge=0)

    chunk_text: str

    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    issue_date: date | None = None


class RetrievalResult(BaseModel):
    """Aggregate result returned by a retrieval call."""

    query: str
    retrieved_chunks: Sequence[RetrievedChunk] = Field(default_factory=list)


RetrievedChunk.model_rebuild()
RetrievalResult.model_rebuild()
