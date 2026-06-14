"""Pydantic schemas for chunking results."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import DocumentType


class DocumentChunkData(BaseModel):
    """Structured chunk record derived from a processed government document."""

    model_config = {"arbitrary_types_allowed": True}

    document_id: uuid.UUID
    document_number: str | None = None
    document_type: DocumentType | None = None
    page_number: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    chunk_text: str
    estimated_token_count: int = Field(ge=0)
    metadata: dict[str, Any] | None = None


DocumentChunkData.model_rebuild()
