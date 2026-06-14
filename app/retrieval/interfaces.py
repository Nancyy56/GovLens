"""Protocols for document retrieval boundaries."""

from __future__ import annotations

from typing import Protocol

from app.retrieval.schemas import RetrievalResult


class DocumentRetriever(Protocol):
    """Contract for retrieving relevant chunks from the vector store."""

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        document_numbers: list[str] | None = None,
    ) -> RetrievalResult:
        """Return ranked chunks relevant to the supplied query."""
        ...
