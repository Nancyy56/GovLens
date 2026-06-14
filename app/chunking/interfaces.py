"""Protocol for document chunking boundary."""

from __future__ import annotations

from typing import Protocol

from app.schemas.processing import DocumentMetadata, PageContent, RawDocument


class DocumentChunker(Protocol):
    """Contract for splitting raw documents into citation-preserving chunks.

    Implementations must not cross page boundaries and must carry page numbers
    on every chunk so downstream systems can map text back to source PDF pages.
    """

    def chunk(
        self,
        raw_document: RawDocument,
        metadata: DocumentMetadata | None = None,
    ) -> list["DocumentChunkData"]:
        """Return ordered chunks derived from the supplied document."""
        ...
