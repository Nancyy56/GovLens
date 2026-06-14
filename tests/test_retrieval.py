"""Unit tests for the retrieval layer."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.models.enums import DocumentType
from app.retrieval import QdrantDocumentRetriever, RetrievalResult, RetrievedChunk
from app.retrieval.interfaces import DocumentRetriever
from app.vectorstore.interfaces import EmbeddingProvider, VectorStore


class FakeEmbeddingProvider:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeVectorStore:
    def __init__(self, hits):
        self._hits = hits
        self.search_calls = []

    def search(self, query_vector, limit=10, filters=None):
        self.search_calls.append(
            {"query_vector": query_vector, "limit": limit, "filters": filters}
        )
        return self._hits


def _make_hit(document_id, document_number, document_type, page_number, chunk_index, chunk_text, score):
    return {
        "id": str(document_id),
        "score": score,
        "payload": {
            "document_id": str(document_id),
            "document_number": document_number,
            "document_type": document_type.value if document_type else None,
            "page_number": page_number,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
        },
    }


class TestDocumentRetriever:
    def test_interface_contract(self) -> None:
        class FakeRetriever:
            def retrieve(self, query, top_k=10, document_numbers=None):
                return RetrievalResult(query=query, retrieved_chunks=[])

        retriever: DocumentRetriever = FakeRetriever()
        result = retriever.retrieve("test query")
        assert isinstance(result, RetrievalResult)
        assert result.query == "test query"


class TestQdrantDocumentRetriever:
    def test_retrieve_embeds_query_and_searches(self) -> None:
        hits = [
            _make_hit(uuid.UUID("11111111-1111-1111-1111-111111111111"), "N1", DocumentType.NOTIFICATION, 1, 0, "text one", 0.95),
        ]
        store = FakeVectorStore(hits)
        provider = FakeEmbeddingProvider()
        retriever = QdrantDocumentRetriever(provider, store)

        result = retriever.retrieve("government order", top_k=5)

        assert len(store.search_calls) == 1
        assert store.search_calls[0]["limit"] == 5
        assert store.search_calls[0]["filters"] is None
        assert len(result.retrieved_chunks) == 1
        assert result.retrieved_chunks[0].document_number == "N1"
        assert result.retrieved_chunks[0].score == 0.95

    def test_retrieve_sorts_by_score_descending(self) -> None:
        low = _make_hit(uuid.UUID("22222222-2222-2222-2222-222222222222"), "LOW", DocumentType.ORDER, 1, 0, "low", 0.4)
        high = _make_hit(uuid.UUID("33333333-3333-3333-3333-333333333333"), "HIGH", DocumentType.ORDER, 1, 0, "high", 0.9)
        mid = _make_hit(uuid.UUID("44444444-4444-4444-4444-444444444444"), "MID", DocumentType.ORDER, 1, 0, "mid", 0.7)
        store = FakeVectorStore([low, high, mid])
        retriever = QdrantDocumentRetriever(FakeEmbeddingProvider(), store)

        result = retriever.retrieve("query")

        scores = [chunk.score for chunk in result.retrieved_chunks]
        assert scores == sorted(scores, reverse=True)
        assert result.retrieved_chunks[0].document_number == "HIGH"

    def test_retrieve_filters_by_document_numbers(self) -> None:
        hit_a = _make_hit(uuid.UUID("55555555-5555-5555-5555-555555555555"), "A", DocumentType.CIRCULAR, 1, 0, "a", 0.9)
        hit_b = _make_hit(uuid.UUID("66666666-6666-6666-6666-666666666666"), "B", DocumentType.ORDER, 1, 0, "b", 0.8)
        store = FakeVectorStore([hit_a, hit_b])
        retriever = QdrantDocumentRetriever(FakeEmbeddingProvider(), store)

        result = retriever.retrieve("query", document_numbers=["A"])

        assert len(result.retrieved_chunks) == 1
        assert result.retrieved_chunks[0].document_number == "A"
        assert store.search_calls[0]["filters"] == {"document_number": ["A"]}

    def test_retrieve_empty_result(self) -> None:
        store = FakeVectorStore([])
        retriever = QdrantDocumentRetriever(FakeEmbeddingProvider(), store)

        result = retriever.retrieve("obscure query")

        assert result.retrieved_chunks == []
        assert result.query == "obscure query"

    def test_retrieve_converts_payload_fields(self) -> None:
        doc_id = uuid.UUID("77777777-7777-7777-7777-777777777777")
        hit = _make_hit(doc_id, "NUM", DocumentType.POLICY, 3, 2, "policy text", 0.85)
        store = FakeVectorStore([hit])
        retriever = QdrantDocumentRetriever(FakeEmbeddingProvider(), store)

        result = retriever.retrieve("policy")

        chunk = result.retrieved_chunks[0]
        assert chunk.document_id == doc_id
        assert chunk.document_number == "NUM"
        assert chunk.document_type == DocumentType.POLICY
        assert chunk.page_number == 3
        assert chunk.chunk_index == 2
        assert chunk.chunk_text == "policy text"
