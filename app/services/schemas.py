"""Pydantic schemas for application service results."""

from __future__ import annotations

import uuid
from typing import Sequence, Union

from pydantic import BaseModel, Field

from app.models.enums import DocumentStatus
from app.supersession.schemas import SupersessionResult


class IngestionResult(BaseModel):
    """Outcome of a full document ingestion run."""

    document_id: uuid.UUID
    status: DocumentStatus
    chunk_count: int = Field(ge=0)
    embedded_count: int = Field(ge=0)


class QueryResult(BaseModel):
    """Final assembled response for a user query."""

    query: str
    answer_markdown: str
    citations: Sequence[str] = Field(default_factory=list)
    supersession_warnings: Sequence[SupersessionResult] = Field(default_factory=list)


IngestionResult.model_rebuild()
QueryResult.model_rebuild()
