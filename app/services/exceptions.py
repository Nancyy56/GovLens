"""Service-layer errors that the API maps to HTTP status codes."""

from __future__ import annotations

import uuid


class DuplicateDocumentError(Exception):
    """The same file (by content hash) has already been ingested."""

    def __init__(self, existing_document_id: uuid.UUID, document_number: str | None = None) -> None:
        self.existing_document_id = existing_document_id
        self.document_number = document_number
        super().__init__(f"Document already ingested as {existing_document_id}")


class DocumentNotFoundError(Exception):
    """No document matches the supplied id or number."""


class AmbiguousDocumentError(Exception):
    """A document number matches more than one stored document."""

    def __init__(self, reference: str, document_ids: list[uuid.UUID]) -> None:
        self.reference = reference
        self.document_ids = document_ids
        super().__init__(
            f"Document number {reference!r} matches {len(document_ids)} documents; use a document id instead"
        )


class PathNotAllowedError(Exception):
    """A path-based ingestion request points outside the allowed directories."""


class SourceUnavailableError(Exception):
    """The stored source file for a document no longer exists."""
