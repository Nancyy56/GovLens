"""Protocols for embedding and vector storage boundaries."""

from __future__ import annotations

from typing import Protocol, Sequence

from app.chunking.schemas import DocumentChunkData


class EmbeddingProvider(Protocol):
    """Contract for converting text into dense vector representations."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return embeddings for the supplied text sequence."""
        ...


class VectorStore(Protocol):
    """Contract for persisting embedded chunks and future retrieval."""

    def upsert(self, chunks: Sequence[DocumentChunkData]) -> None:
        """Insert or update embedded chunks in the store."""
        ...

    def search(self, query_vector: Sequence[float], limit: int = 10, filters: dict | None = None) -> list[dict]:
        """Query the vector store and return scored hits with payloads."""
        ...

    def delete_document(self, document_id) -> None:
        """Remove all vectors belonging to a document."""
        ...

    def list_document_ids(self) -> set[str]:
        """Return the distinct document ids that have stored vectors."""
        ...
