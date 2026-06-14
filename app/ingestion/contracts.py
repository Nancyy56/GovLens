"""Abstract interfaces for future document processing components.

The protocols in this module define architectural boundaries only. Concrete
implementations may later handle PDF loading, text extraction, metadata
extraction, or classification elsewhere, but no such logic belongs here.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.processing import (
    DocumentClassificationResult,
    DocumentMetadata,
    RawDocument,
)


class DocumentLoader(Protocol):
    """Contract for converting an external source reference into raw text.

    Future implementations should accept a source path or URI and return a
    `RawDocument` containing extracted text plus ingestion bookkeeping. This
    interface deliberately does not prescribe OCR, filesystem strategy, or
    network behavior.
    """

    def load(self, file_path: str) -> RawDocument:
        """Load an external document source into the raw-document contract."""
        ...


class MetadataExtractor(Protocol):
    """Contract for deriving structured metadata from raw document text.

    Future implementations may use manual review, deterministic rules, models,
    or external systems. This interface exposes only the typed result expected
    by downstream storage and relationship mapping code.
    """

    def extract(self, raw_document: RawDocument) -> DocumentMetadata:
        """Extract document metadata from a raw document payload."""
        ...


class DocumentClassifier(Protocol):
    """Contract for assigning a high-level government document type.

    Future classifiers should return a `DocumentClassificationResult` without
    mutating persistence state. Storage, reconciliation, and business decisions
    remain outside this boundary.
    """

    def classify(self, raw_document: RawDocument) -> DocumentClassificationResult:
        """Classify a raw document into one of the supported document types."""
        ...
