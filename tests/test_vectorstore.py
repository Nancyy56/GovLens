"""Unit tests for embedding and vector storage layer."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.chunking.schemas import DocumentChunkData
from app.models.enums import DocumentType
from app.vectorstore import (
    EmbeddedChunk,
    HuggingFaceEmbeddingProvider,
    QdrantVectorStore,
)
from app.vectorstore.interfaces import EmbeddingProvider, VectorStore
from app.vectorstore.qdrant_store import COLLECTION_NAME


def _make_chunk(**kwargs) -> DocumentChunkData:
    defaults = dict(
        document_id=uuid.uuid4(),
        document_number="NOTIF-01",
        document_type=DocumentType.NOTIFICATION,
        page_number=1,
        chunk_index=0,
        chunk_text="Notification No. 17/2024\nSubject: Test",
        estimated_token_count=5,
        metadata={"source": "test"},
    )
    defaults.update(kwargs)
    return DocumentChunkData(**defaults)


class TestEmbeddingProvider:
    def test_interface_contract(self) -> None:
        class FakeProvider:
            def embed(self, texts):
                return [[0.0] * 3 for _ in texts]

        provider: EmbeddingProvider = FakeProvider()
        result = provider.embed(["hello world"])
        assert isinstance(result, list)
        assert all(isinstance(v, list) for v in result)

    def test_huggingface_embedder_raises_without_sentence_transformers(self) -> None:
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            provider = HuggingFaceEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", batch_size=32, device=None)
            provider._model = None
            with pytest.raises(RuntimeError, match="sentence-transformers is required"):
                provider.embed(["test"])


class TestHuggingFaceEmbeddingProvider:
    def test_embed_returns_list_of_lists(self) -> None:
        provider = HuggingFaceEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", batch_size=32, device=None)
        provider._model = MagicMock()
        provider._model.encode.return_value.tolist.return_value = [
            [0.1] * 384,
            [0.2] * 384,
        ]

        result = provider.embed(["text one", "text two"])
        assert result == [[0.1] * 384, [0.2] * 384]
        provider._model.encode.assert_called_once()

    def test_lazy_model_loading(self) -> None:
        provider = HuggingFaceEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", batch_size=16, device="cpu")
        provider._model = None

        fake_model = MagicMock()
        fake_model.encode.return_value.tolist.return_value = [[0.5] * 384]

        with patch.dict(
            "sys.modules",
            {"sentence_transformers": MagicMock(SentenceTransformer=lambda *a, **k: fake_model)},
        ):
            result = provider.embed(["only"])
            assert result == [[0.5] * 384]
            assert provider._model is fake_model


class TestEmbeddedChunk:
    def test_embedded_chunk_from_chunk_data(self) -> None:
        chunk = _make_chunk()
        embedded = EmbeddedChunk(
            document_id=chunk.document_id,
            document_number=chunk.document_number,
            document_type=chunk.document_type,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            chunk_text=chunk.chunk_text,
            embedding=[0.1] * 384,
            metadata=chunk.metadata,
        )
        assert embedded.document_id == chunk.document_id
        assert embedded.embedding == [0.1] * 384
        assert embedded.metadata == {"source": "test"}
        assert embedded.page_number == 1

    def test_embeddings_dimensions_preserved(self) -> None:
        for dim in [384, 768, 1024]:
            embedded = EmbeddedChunk(
                document_id=uuid.uuid4(),
                page_number=1,
                chunk_index=0,
                chunk_text="test",
                embedding=[0.0] * dim,
            )
            assert len(embedded.embedding) == dim


class TestQdrantVectorStore:
    def test_search_is_implemented(self) -> None:
        store = QdrantVectorStore.__new__(QdrantVectorStore)
        store.host = "localhost"
        store.port = 6333
        store.collection = COLLECTION_NAME
        store.api_key = None
        store._vector_size = 384
        store._client = MagicMock()
        store._client.get_collections.return_value.collections = [SimpleNamespace(name=COLLECTION_NAME)]
        store._client.query_points.return_value.points = [
            SimpleNamespace(id="p1", score=0.42, payload={"document_id": "d1"}),
        ]

        result = store.search([0.0] * 384, limit=5)

        assert result == [{"id": "p1", "score": 0.42, "payload": {"document_id": "d1"}}]
        assert store._client.query_points.call_args.kwargs["limit"] == 5

    def test_search_without_collection_returns_empty(self) -> None:
        store = QdrantVectorStore()
        store._client = MagicMock()
        store._client.get_collections.return_value.collections = []

        assert store.search([0.0] * 384) == []
        store._client.query_points.assert_not_called()

    def test_delete_document_filters_by_document_id(self) -> None:
        store = QdrantVectorStore()
        store._client = MagicMock()
        store._client.get_collections.return_value.collections = [SimpleNamespace(name=COLLECTION_NAME)]

        store.delete_document("abc")

        selector = store._client.delete.call_args.kwargs["points_selector"]
        condition = selector.filter.must[0]
        assert condition.key == "document_id"
        assert condition.match.value == "abc"

    def test_upsert_with_empty_chunks_is_noop(self) -> None:
        store = QdrantVectorStore.__new__(QdrantVectorStore)
        store.collection = COLLECTION_NAME
        store._vector_size = None
        store._client = MagicMock()

        store.upsert([])

        store._client.upsert.assert_not_called()

    def test_upsert_builds_correct_payload(self) -> None:
        store = QdrantVectorStore.__new__(QdrantVectorStore)
        store.host = "localhost"
        store.port = 6333
        store.collection = COLLECTION_NAME
        store.api_key = None
        store._client = MagicMock()
        store._vector_size = 384

        chunks = [
            EmbeddedChunk(
                document_id=uuid.UUID("12345678-1234-1234-1234-123456789abc"),
                document_number="NOTIF-01",
                document_type=DocumentType.NOTIFICATION,
                page_number=2,
                chunk_index=3,
                chunk_text="Sample text",
                embedding=[0.1] * 384,
                metadata={"source": "unit-test"},
            )
        ]

        store.upsert(chunks)

        store._client.upsert.assert_called_once()
        call_args = store._client.upsert.call_args
        assert call_args.kwargs["collection_name"] == COLLECTION_NAME

        points = call_args.kwargs["points"]
        assert len(points) == 1
        point = points[0]
        assert point["id"] == str(uuid.uuid5(uuid.UUID("12345678-1234-1234-1234-123456789abc"), "2:3"))
        assert point["vector"] == [0.1] * 384
        assert point["payload"]["document_id"] == "12345678-1234-1234-1234-123456789abc"
        assert point["payload"]["document_number"] == "NOTIF-01"
        assert point["payload"]["document_type"] == "NOTIFICATION"
        assert point["payload"]["page_number"] == 2
        assert point["payload"]["chunk_index"] == 3
        assert point["payload"]["chunk_text"] == "Sample text"
        assert point["payload"]["source"] == "unit-test"

    def test_upsert_infers_vector_size_and_creates_collection(self) -> None:
        store = QdrantVectorStore.__new__(QdrantVectorStore)
        store.host = "localhost"
        store.port = 6333
        store.collection = COLLECTION_NAME
        store.api_key = None
        store._vector_size = None

        fake_client = MagicMock()
        fake_client.get_collections.return_value.collections = []
        store._client = fake_client

        chunk = EmbeddedChunk(
            document_id=uuid.uuid4(),
            page_number=1,
            chunk_index=0,
            chunk_text="text",
            embedding=[0.0] * 768,
        )

        with patch.object(store, "_get_client", return_value=fake_client):
            store.upsert([chunk])

        assert store._vector_size == 768
        fake_client.create_collection.assert_called_once()
        create_call = fake_client.create_collection.call_args
        assert create_call.kwargs["collection_name"] == COLLECTION_NAME
        vector_params = create_call.kwargs["vectors_config"]
        assert vector_params.size == 768

    def test_upsert_skips_collection_creation_when_exists(self) -> None:
        store = QdrantVectorStore.__new__(QdrantVectorStore)
        store.host = "localhost"
        store.port = 6333
        store.collection = COLLECTION_NAME
        store.api_key = None
        store._vector_size = None

        fake_client = MagicMock()
        collection_mock = MagicMock()
        collection_mock.name = COLLECTION_NAME
        fake_client.get_collections.return_value.collections = [collection_mock]
        store._client = fake_client

        chunk = EmbeddedChunk(
            document_id=uuid.uuid4(),
            page_number=1,
            chunk_index=0,
            chunk_text="text",
            embedding=[0.0] * 384,
        )

        with patch.object(store, "_get_client", return_value=fake_client):
            store.upsert([chunk])

        fake_client.create_collection.assert_not_called()
