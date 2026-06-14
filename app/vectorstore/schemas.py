"""Pydantic schemas for embedding and vector storage results."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import DocumentType


class EmbeddedChunk(BaseModel):
    """Chunk enriched with a dense embedding and serialization metadata."""

    model_config = {"arbitrary_types_allowed": True}

    document_id: uuid.UUID
    document_number: str | None = None
    document_type: DocumentType | None = None
    page_number: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    chunk_text: str
    embedding: list[float]
    metadata: dict[str, Any] | None = None


EmbeddedChunk.model_rebuild()
