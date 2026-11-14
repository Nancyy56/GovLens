"""Pydantic schemas for application service results."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Sequence

from pydantic import BaseModel, Field

from app.generation.verification import VerificationReport
from app.models.enums import DocumentStatus, DocumentType
from app.supersession.linker import CreatedLink
from app.supersession.schemas import SupersessionResult


class IngestionResult(BaseModel):
    """Outcome of a full document ingestion run."""

    document_id: uuid.UUID
    status: DocumentStatus
    chunk_count: int = Field(ge=0)
    embedded_count: int = Field(ge=0)
    document_number: str | None = None
    document_type: DocumentType | None = None
    title: str | None = None
    issue_date: date | None = None
    page_count: int = Field(default=0, ge=0)
    # Supersedes/amends/references edges created by this ingestion.
    links_created: list[CreatedLink] = Field(default_factory=list)
    # Document numbers mentioned in the text that are not ingested yet.
    pending_references: list[str] = Field(default_factory=list)


class SourceCitation(BaseModel):
    """A cited source with the tag ("S1") used for it inside the answer."""

    label: str
    document_id: uuid.UUID
    document_number: str | None = None
    document_type: DocumentType | None = None
    page_number: int
    issue_date: date | None = None
    citation_text: str


class QueryResult(BaseModel):
    """Final assembled response for a user query."""

    query: str
    answer_markdown: str
    citations: Sequence[str] = Field(default_factory=list)
    sources: Sequence[SourceCitation] = Field(default_factory=list)
    supersession_warnings: Sequence[SupersessionResult] = Field(default_factory=list)
    verification: VerificationReport = Field(default_factory=VerificationReport)
    # True when the answer used no [S#] tags, so all retrieved sources are listed.
    citations_inferred: bool = False


IngestionResult.model_rebuild()
QueryResult.model_rebuild()
