"""Qdrant-backed document retriever implementation."""

from __future__ import annotations

from app.retrieval.interfaces import DocumentRetriever
from app.retrieval.schemas import RetrievalResult, RetrievedChunk
from app.vectorstore.interfaces import EmbeddingProvider, VectorStore


class QdrantDocumentRetriever(DocumentRetriever):
    """Retrieve relevant chunks from Qdrant using dense-vector similarity.

    The retriever is intentionally thin: it embeds the query, delegates
    vector search to the configured VectorStore, and converts raw hits into
    typed RetrievedChunk objects. It does not apply supersession reasoning,
    generate answers, or format citations.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        document_numbers: list[str] | None = None,
    ) -> RetrievalResult:
        query_vector = self.embedding_provider.embed([query])[0]

        filters: dict | None = None
        if document_numbers:
            filters = {"document_number": document_numbers}

        hits = self.vector_store.search(
            query_vector=query_vector,
            limit=top_k,
            filters=filters,
        )

        # A long chunk is stored as several windows; keep each chunk once, at its best score.
        chunks: list[RetrievedChunk] = []
        seen: set[tuple[str, int, int]] = set()
        for hit in sorted(hits, key=lambda h: h.get("score", 0.0), reverse=True):
            chunk = self._hit_to_chunk(hit)
            key = (str(chunk.document_id), chunk.page_number, chunk.chunk_index)
            if key not in seen:
                seen.add(key)
                chunks.append(chunk)

        if document_numbers:
            chunks = [c for c in chunks if c.document_number in document_numbers]

        chunks.sort(key=lambda chunk: chunk.score, reverse=True)
        return RetrievalResult(query=query, retrieved_chunks=chunks)

    @staticmethod
    def _hit_to_chunk(hit: dict) -> RetrievedChunk:
        payload = hit.get("payload") or {}
        raw_issue_date = payload.get("issue_date")
        parsed_issue_date = None
        if isinstance(raw_issue_date, str):
            try:
                from datetime import date
                parsed_issue_date = date.fromisoformat(raw_issue_date)
            except ValueError:
                parsed_issue_date = None
        return RetrievedChunk(
                document_id=payload["document_id"],
                document_number=payload.get("document_number"),
                document_type=payload.get("document_type"),

                title=payload.get("title"),
                file_name=payload.get("file_name"),
                department=payload.get("department"),
                subject=payload.get("subject"),

                page_number=payload["page_number"],
                chunk_index=payload["chunk_index"],
                chunk_text=payload.get("chunk_text", ""),
                score=hit.get("score", 0.0),
                issue_date=parsed_issue_date,
        )
