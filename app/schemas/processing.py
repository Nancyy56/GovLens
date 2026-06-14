"""Pydantic contracts for document processing boundaries.

These schemas describe data exchanged between future pipeline stages. They do
not perform OCR, parsing, metadata extraction, classification, retrieval, or
storage; they only define typed payload shapes for those future components.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DocumentType


class PageContent(BaseModel):
    """Text extracted from a single page of a digitally-born document.

    Page numbers are one-based to match how citations are displayed to users
    and how government PDFs are commonly referenced.
    """

    page_number: int = Field(ge=1)
    text: str


class RawDocument(BaseModel):
    """Text extraction output accepted by downstream metadata stages.

    Digital loaders populate ordered page content first. `raw_text` and
    `page_count` are then derived from those pages so full-document text never
    drifts away from page-level citation context.
    """

    document_id: uuid.UUID
    source_type: str
    source_path: str
    pages: list[PageContent]
    raw_text: str = ""
    page_count: int = Field(default=0, ge=0)
    ingested_at: datetime

    @model_validator(mode="after")
    def derive_text_from_pages(self) -> Self:
        """Keep aggregate text and page count synchronized with `pages`."""

        self.raw_text = "\n".join(page.text for page in self.pages)
        self.page_count = len(self.pages)
        return self


class DocumentMetadata(BaseModel):
    """Structured metadata inferred or collected from a government document.

    Relationship lists hold document identifiers or document numbers exactly as
    detected by a future extractor. Resolving those strings to database rows is
    a separate storage concern and is not part of this contract.
    """

    title: str | None = None
    document_number: str | None = None
    document_type: DocumentType | None = None
    issue_date: date | None = None
    effective_date: date | None = None
    department: str | None = None
    subject: str | None = None
    supersedes_documents: list[str] = Field(default_factory=list)
    amends_documents: list[str] = Field(default_factory=list)
    referenced_documents: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class MetadataValidationResult(BaseModel):
    """Validation outcome for extracted document metadata.

    Validation checks structural completeness of already-extracted metadata. It
    does not infer, repair, or extract any values.
    """

    is_valid: bool
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MetadataExtractionResult(BaseModel):
    """Result envelope returned by the metadata extraction framework.

    `metadata` is optional so orchestration can report strategy failures without
    fabricating extracted values.
    """

    metadata: DocumentMetadata | None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DocumentClassificationResult(BaseModel):
    """Classification result for a document type decision.

    Future classifiers may be rules-based, model-based, or human-assisted; this
    schema captures only the selected type and confidence score.
    """

    document_type: DocumentType
    confidence_score: float = Field(ge=0.0, le=1.0)


class DocumentProcessingResult(BaseModel):
    """Aggregate result passed from processing into storage orchestration.

    This object is a transport contract for already-produced outputs. It does
    not imply the pipeline has been implemented in this codebase.
    """

    raw_document: RawDocument
    metadata: DocumentMetadata
    classification: DocumentClassificationResult
