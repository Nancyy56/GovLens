"""Pydantic schemas for API request/response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IngestionJobStatus, RelationshipType
from app.services.schemas import IngestionResult, QueryResult


class IngestRequest(BaseModel):
    file_path: str = Field(..., description="Path to a PDF inside an allowed ingestion directory (INGEST_ALLOWED_DIRS).")


class ImportUrlRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2000, description="Link to a PDF on an approved government website.")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural-language question to answer from the document corpus.")
    top_k: int = Field(default=10, ge=1, le=100, description="Maximum number of chunks to retrieve.")
    document_numbers: Sequence[str] = Field(default_factory=list, description="Optional filter to restrict retrieval to specific document numbers.")


class CompareRequest(BaseModel):
    base: str = Field(..., description="Older/base document: id or document number.")
    target: str = Field(..., description="Newer/target document: id or document number.")
    focus: str | None = Field(default=None, description="Optional topic to focus the summary on, e.g. 'tax rates'.")
    summarize: bool = Field(default=True, description="Ask the LLM for a plain-language summary of the changes.")


class RelationshipCreateRequest(BaseModel):
    target_document_id: uuid.UUID
    relationship_type: RelationshipType = Field(description="SUPERSEDES means this document replaces the target.")


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: IngestionJobStatus
    file_path: str
    original_filename: str | None
    document_id: uuid.UUID | None
    error: str | None
    attempts: int = 0
    submitted_by: uuid.UUID | None = None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


__all__ = [
    "CompareRequest",
    "ImportUrlRequest",
    "IngestRequest",
    "IngestionJobRead",
    "IngestionResult",
    "QueryRequest",
    "QueryResult",
    "RelationshipCreateRequest",
]
