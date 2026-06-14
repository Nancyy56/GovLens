"""Interfaces for metadata extraction framework components."""

from __future__ import annotations

from typing import Protocol

from app.schemas.processing import DocumentMetadata, MetadataValidationResult, RawDocument


class MetadataExtractionStrategy(Protocol):
    """Contract for future metadata extraction strategies.

    Implementations may eventually use deterministic rules, an LLM, a human
    review queue, or another mechanism. This interface only defines the shape
    of the plug-in point and must not contain extraction logic itself.
    """

    def extract(self, raw_document: RawDocument) -> DocumentMetadata:
        """Return extracted metadata for a raw document."""
        ...


class MetadataValidator(Protocol):
    """Contract for validating extracted metadata completeness."""

    def validate(self, metadata: DocumentMetadata) -> MetadataValidationResult:
        """Validate metadata without mutating or enriching it."""
        ...
