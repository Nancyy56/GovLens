"""Pydantic schemas for API request/response contracts."""

from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, Field

from app.services.schemas import IngestionResult, QueryResult


class IngestRequest(BaseModel):
    file_path: str = Field(..., description="Absolute or workspace-relative path to the source PDF.")


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural-language question to answer from the document corpus.")
    top_k: int = Field(default=10, ge=1, le=100, description="Maximum number of chunks to retrieve.")
    document_numbers: Sequence[str] = Field(default_factory=list, description="Optional filter to restrict retrieval to specific document numbers.")
