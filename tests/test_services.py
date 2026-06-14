"""Unit tests for application service layer."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services import DocumentIngestionService, QueryService
from app.services.schemas import IngestionResult, QueryResult


class FakeLoader:
    def __init__(self, raw_document: Any) -> None:
        self.raw_document = raw_document
        self.loaded_paths: list[str] = []

    def load(self, file_path: str) -> Any:
        self.loaded_paths.append(file_path)
        return self.raw_document


class FakeMetadataExtractor:
    def __init__(self, metadata: Any) -> None:
        self.metadata = metadata
        self.extract_calls: list[Any] = []

    def extract(self, raw_document: Any) -> Any:
        self.extract_calls.append(raw_document)
        return self.metadata


class FakeClassifier:
    def __init__(self, classification: Any) -> None:
        self.classification = classification
        self.classify_calls: list[Any] = []

    def classify(self, raw_document: Any, metadata: Any = None) -> Any:
        self.classify_calls.append((raw_document, metadata))
        return self.classification


class FakeChunker:
    def __init__(self, chunks: list[Any]) -> None:
        self.chunks = chunks
        self.chunk_calls: list[Any] = []

    def chunk(self, raw_document: Any, metadata: Any = None) -> list[Any]:
        self.chunk_calls.append((raw_document, metadata))
        return self.chunks


class FakeEmbeddingProvider:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.embeddings = embeddings
        self.embed_calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(texts)
        return self.embeddings


class FakeVectorStore:
    def __init__(self) -> None:
        self.upserted: list[Any] = []

    def upsert(self, chunks: list[Any]) -> None:
        self.upserted.extend(chunks)


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.created: list[Any] = []

    def create(self, document: Any) -> Any:
        self.created.append(document)
        result = MagicMock()
        result.id = "11111111-1111-1111-1111-111111111111"
        return result


class FakeDocumentChunkRepository:
    def __init__(self) -> None:
        self.created: list[Any] = []

    def create(self, chunk: Any) -> None:
        self.created.append(chunk)


class TestDocumentIngestionService:
    def test_happy_path(self) -> None:
        from app.models.enums import DocumentType, DocumentStatus
        from app.schemas.processing import DocumentClassificationResult, DocumentMetadata, PageContent, RawDocument
        from app.chunking.schemas import DocumentChunkData
        from datetime import UTC, datetime
        import uuid

        raw = RawDocument(
            document_id=uuid.uuid4(),
            source_type="pdf",
            source_path="/tmp/test.pdf",
            pages=[PageContent(page_number=1, text="Notification No. 17/2024\nSubject: Test\n")],
            ingested_at=datetime.now(UTC),
        )
        metadata = DocumentMetadata(document_number="17/2024", document_type=DocumentType.NOTIFICATION, subject="Test")
        classification = DocumentClassificationResult(document_type=DocumentType.NOTIFICATION, confidence_score=0.95)
        chunks = [
            DocumentChunkData(
                document_id=raw.document_id,
                page_number=1,
                chunk_index=0,
                chunk_text="Notification No. 17/2024",
                estimated_token_count=3,
            )
        ]
        embeddings = [[0.1] * 384]

        service = DocumentIngestionService(
            loader=FakeLoader(raw),
            metadata_extractor=FakeMetadataExtractor(metadata),
            classifier=FakeClassifier(classification),
            chunker=FakeChunker(chunks),
            embedding_provider=FakeEmbeddingProvider(embeddings),
            vector_store=FakeVectorStore(),
            document_repository=FakeDocumentRepository(),
            document_chunk_repository=FakeDocumentChunkRepository(),
        )

        result = service.ingest("/tmp/test.pdf")

        assert isinstance(result, IngestionResult)
        assert result.status == DocumentStatus.ACTIVE
        assert result.chunk_count == 1
        assert result.embedded_count == 1

    def test_propagates_loader_error(self) -> None:
        class BadLoader:
            def load(self, file_path: str) -> Any:
                raise RuntimeError("load failed")

        service = DocumentIngestionService(
            loader=BadLoader(),
            metadata_extractor=FakeMetadataExtractor(None),
            classifier=FakeClassifier(None),
            chunker=FakeChunker([]),
            embedding_provider=FakeEmbeddingProvider([]),
            vector_store=FakeVectorStore(),
            document_repository=FakeDocumentRepository(),
            document_chunk_repository=FakeDocumentChunkRepository(),
        )

        with pytest.raises(RuntimeError, match="load failed"):
            service.ingest("/tmp/test.pdf")

    def test_propagates_metadata_extractor_error(self) -> None:
        class BadExtractor:
            def extract(self, raw_document: Any) -> Any:
                raise RuntimeError("extract failed")

        from app.schemas.processing import RawDocument, PageContent
        from datetime import UTC, datetime
        import uuid

        raw = RawDocument(
            document_id=uuid.uuid4(),
            source_type="pdf",
            source_path="/tmp/test.pdf",
            pages=[PageContent(page_number=1, text="hello")],
            ingested_at=datetime.now(UTC),
        )

        service = DocumentIngestionService(
            loader=FakeLoader(raw),
            metadata_extractor=BadExtractor(),
            classifier=FakeClassifier(None),
            chunker=FakeChunker([]),
            embedding_provider=FakeEmbeddingProvider([]),
            vector_store=FakeVectorStore(),
            document_repository=FakeDocumentRepository(),
            document_chunk_repository=FakeDocumentChunkRepository(),
        )

        with pytest.raises(RuntimeError, match="extract failed"):
            service.ingest("/tmp/test.pdf")


class TestQueryService:
    def test_happy_path(self) -> None:
        retriever = MagicMock()
        retriever.retrieve.return_value = MagicMock(retrieved_chunks=[])

        comparison_engine = MagicMock()
        comparison_engine.prepare.return_value = MagicMock()

        citation_builder = MagicMock()
        citation_builder.build.return_value = MagicMock(citations=[])

        supersession_engine = MagicMock()
        supersession_engine.check_document.return_value = None

        answer_generator = MagicMock()
        answer_generator.generate.return_value = MagicMock(answer_markdown="answer", citations=[], supersession_warnings=[])

        service = QueryService(
            retriever=retriever,
            comparison_engine=comparison_engine,
            citation_builder=citation_builder,
            supersession_engine=supersession_engine,
            llm_client=answer_generator,
        )

        result = service.query("test query")

        assert isinstance(result, QueryResult)
        assert result.answer_markdown == "answer"

    def test_propagates_retriever_error(self) -> None:
        retriever = MagicMock()
        retriever.retrieve.side_effect = RuntimeError("retrieval failed")

        service = QueryService(
            retriever=retriever,
            comparison_engine=MagicMock(),
            citation_builder=MagicMock(),
            supersession_engine=MagicMock(),
            llm_client=MagicMock(),
        )

        with pytest.raises(RuntimeError, match="retrieval failed"):
            service.query("test query")
