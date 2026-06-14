"""Protocol for document classification boundary."""

from __future__ import annotations

from typing import Protocol

from app.schemas.processing import DocumentClassificationResult, DocumentMetadata, RawDocument


class DocumentClassifier(Protocol):
    """Contract for assigning a high-level government document type.

    Classifiers must be deterministic and side-effect free. They return a
    DocumentClassificationResult without mutating the raw_document or
    metadata payloads.
    """

    def classify(
        self,
        raw_document: RawDocument,
        metadata: DocumentMetadata | None = None,
    ) -> DocumentClassificationResult:
        """Return a typed classification decision for the supplied document."""
        ...
