"""Pydantic schemas for document domain create/read operations."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentStatus, DocumentType, RelationshipType


class DocumentCreate(BaseModel):
    """Input payload for creating a document metadata record."""

    title: str
    document_number: str
    document_type: DocumentType = DocumentType.UNKNOWN
    issue_date: date
    effective_date: date | None = None
    department: str | None = None
    subject: str | None = None
    source_url: str | None = None
    file_name: str
    file_hash: str
    status: DocumentStatus = DocumentStatus.ACTIVE


class DocumentRead(BaseModel):
    """Read model returned from ORM-backed document rows."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    document_number: str
    document_type: DocumentType
    issue_date: date
    effective_date: date | None
    department: str | None
    subject: str | None
    source_url: str | None
    file_name: str
    file_hash: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime


class DocumentChunkCreate(BaseModel):
    """Input payload for persisting extracted chunk text."""

    document_id: uuid.UUID
    chunk_index: int
    page_number: int
    chunk_text: str
    token_count: int


class DocumentChunkRead(BaseModel):
    """Read model for relational chunk text metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    page_number: int
    chunk_text: str
    token_count: int
    created_at: datetime


class DocumentRelationshipCreate(BaseModel):
    """Input payload for a directed relationship between two documents."""

    source_document_id: uuid.UUID
    target_document_id: uuid.UUID
    relationship_type: RelationshipType


class DocumentRelationshipRead(BaseModel):
    """Read model for document lineage and reference edges."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_document_id: uuid.UUID
    target_document_id: uuid.UUID
    relationship_type: RelationshipType
    created_at: datetime
