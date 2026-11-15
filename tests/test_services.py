"""Unit tests for application service layer."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.models.enums import DocumentStatus
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
        self.deleted: list[Any] = []

    def upsert(self, chunks: list[Any]) -> None:
        self.upserted.extend(chunks)

    def delete_document(self, document_id: Any) -> None:
        self.deleted.append(document_id)


class FakeDocumentRepository:
    def __init__(self, existing_by_hash: dict[str, Any] | None = None) -> None:
        self.created: list[Any] = []
        self.existing_by_hash = existing_by_hash or {}

    def create(self, document: Any) -> Any:
        self.created.append(document)
        result = MagicMock()
        result.id = "11111111-1111-1111-1111-111111111111"
        result.status = DocumentStatus.ACTIVE
        return result

    def get_by_file_hash(self, file_hash: str) -> Any:
        return self.existing_by_hash.get(file_hash)


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
        retriever.retrieve.return_value = MagicMock(retrieved_chunks=[MagicMock(document_id="doc-1")])

        comparison_engine = MagicMock()
        comparison_engine.prepare.return_value = MagicMock()

        citation_builder = MagicMock()
        citation_builder.build.return_value = MagicMock(citations=[])

        supersession_engine = MagicMock()
        supersession_engine.check_document.return_value = None

        from app.generation.schemas import GeneratedAnswer

        answer_generator = MagicMock()
        answer_generator.generate.return_value = GeneratedAnswer(query="test query", answer_markdown="answer")

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


def _ingestion_inputs():
    import uuid
    from datetime import UTC, datetime

    from app.chunking.schemas import DocumentChunkData
    from app.models.enums import DocumentType
    from app.schemas.processing import DocumentClassificationResult, DocumentMetadata, PageContent, RawDocument

    raw = RawDocument(
        document_id=uuid.uuid4(),
        source_type="pdf",
        source_path="/tmp/test.pdf",
        pages=[PageContent(page_number=1, text="Notification No. 17/2024")],
        ingested_at=datetime.now(UTC),
        content_hash="abc123",
    )
    metadata = DocumentMetadata(document_number="17/2024", document_type=DocumentType.NOTIFICATION)
    classification = DocumentClassificationResult(document_type=DocumentType.NOTIFICATION, confidence_score=0.95)
    chunks = [
        DocumentChunkData(document_id=raw.document_id, page_number=1, chunk_index=0, chunk_text="text", estimated_token_count=1)
    ]
    return raw, metadata, classification, chunks


def _ingestion_service(repository, vector_store, raw, metadata, classification, chunks):
    return DocumentIngestionService(
        loader=FakeLoader(raw),
        metadata_extractor=FakeMetadataExtractor(metadata),
        classifier=FakeClassifier(classification),
        chunker=FakeChunker(chunks),
        embedding_provider=FakeEmbeddingProvider([[0.1] * 4]),
        vector_store=vector_store,
        document_repository=repository,
        document_chunk_repository=FakeDocumentChunkRepository(),
    )


class TestIngestionImprovements:
    def test_result_reports_number_type_and_pages(self) -> None:
        raw, metadata, classification, chunks = _ingestion_inputs()
        result = _ingestion_service(FakeDocumentRepository(), FakeVectorStore(), raw, metadata, classification, chunks).ingest("/tmp/test.pdf")
        assert result.document_number == "17/2024"
        assert result.document_type == "NOTIFICATION"
        assert result.page_count == 1

    def test_duplicate_file_is_rejected_before_any_write(self) -> None:
        import uuid

        from app.services.exceptions import DuplicateDocumentError

        raw, metadata, classification, chunks = _ingestion_inputs()
        existing = MagicMock(id=uuid.uuid4(), document_number="17/2024")
        repository = FakeDocumentRepository(existing_by_hash={"abc123": existing})
        store = FakeVectorStore()

        with pytest.raises(DuplicateDocumentError) as error:
            _ingestion_service(repository, store, raw, metadata, classification, chunks).ingest("/tmp/test.pdf")

        assert error.value.existing_document_id == existing.id
        assert repository.created == [] and store.upserted == []

    def test_file_hash_is_content_hash(self) -> None:
        raw, metadata, classification, chunks = _ingestion_inputs()
        repository = FakeDocumentRepository()
        _ingestion_service(repository, FakeVectorStore(), raw, metadata, classification, chunks).ingest("/tmp/test.pdf")
        assert repository.created[0].file_hash == "abc123"

    def test_missing_issue_date_is_stored_as_none(self) -> None:
        raw, metadata, classification, chunks = _ingestion_inputs()
        repository = FakeDocumentRepository()
        _ingestion_service(repository, FakeVectorStore(), raw, metadata, classification, chunks).ingest("/tmp/test.pdf")
        assert repository.created[0].issue_date is None

    def test_vectors_removed_when_commit_fails(self) -> None:
        raw, metadata, classification, chunks = _ingestion_inputs()
        repository = FakeDocumentRepository()
        repository.session = MagicMock()
        repository.session.commit.side_effect = RuntimeError("database went away")
        store = FakeVectorStore()

        with pytest.raises(RuntimeError, match="database went away"):
            _ingestion_service(repository, store, raw, metadata, classification, chunks).ingest("/tmp/test.pdf")

        assert len(store.upserted) == 1
        assert store.deleted == ["11111111-1111-1111-1111-111111111111"]
        repository.session.rollback.assert_called_once()


def _query_service(chunks, supersession_engine=None, generator=None):
    from app.citations.builder import CitationBuilder
    from app.comparison.engine import ComparisonEngine
    from app.generation.generator import LLMAnswerGenerator

    retriever = MagicMock()
    retriever.retrieve.return_value = MagicMock(retrieved_chunks=chunks)
    if supersession_engine is None:
        supersession_engine = MagicMock()
        supersession_engine.check_document.return_value = None
    return QueryService(
        retriever=retriever,
        comparison_engine=ComparisonEngine(),
        citation_builder=CitationBuilder(),
        supersession_engine=supersession_engine,
        llm_client=generator or LLMAnswerGenerator(llm_client=MagicMock(spec=["generate"], generate=MagicMock(return_value="Answer [S1]."))),
    )


def _retrieved(document_id: str, page: int = 1, number: str = "N1"):
    from app.retrieval.schemas import RetrievedChunk

    return RetrievedChunk(document_id=document_id, document_number=number, document_type="NOTIFICATION",
                          page_number=page, chunk_index=0, chunk_text=f"text {page}", score=0.9)


class TestQueryImprovements:
    def test_no_retrieved_chunks_skips_llm(self) -> None:
        from app.generation.prompt_builder import NO_ANSWER_TEXT

        generator = MagicMock()
        result = _query_service([], generator=generator).query("q")

        assert result.answer_markdown == NO_ANSWER_TEXT
        generator.generate.assert_not_called()

    def test_supersession_checked_for_every_distinct_document(self) -> None:
        engine = MagicMock()
        engine.check_document.return_value = None
        doc_a = "11111111-1111-1111-1111-111111111111"
        doc_b = "22222222-2222-2222-2222-222222222222"

        _query_service([_retrieved(doc_a, 1), _retrieved(doc_a, 2), _retrieved(doc_b, 1, "N2")], supersession_engine=engine).query("q")

        checked = [str(call.args[0]) for call in engine.check_document.call_args_list]
        assert checked == [doc_a, doc_b]

    def test_result_contains_labeled_sources(self) -> None:
        result = _query_service([_retrieved("11111111-1111-1111-1111-111111111111")]).query("q")

        assert result.citations == ["[S1] Notification No. N1\n(Page 1)"]
        assert result.sources[0].label == "S1"
        assert result.sources[0].page_number == 1

    def test_stream_emits_retrieval_tokens_and_done(self) -> None:
        events = list(_query_service([_retrieved("11111111-1111-1111-1111-111111111111")]).stream("q"))

        assert [e["event"] for e in events] == ["retrieval", "token", "done"]
        assert events[0]["data"]["retrieved_chunks"] == 1
        assert events[-1]["data"]["sources"][0]["label"] == "S1"


def test_search_returns_chunks_without_calling_llm() -> None:
    generator = MagicMock()
    chunk = _retrieved("11111111-1111-1111-1111-111111111111")

    results = _query_service([chunk], generator=generator).search("q", top_k=3)

    assert results == [chunk]
    generator.generate.assert_not_called()
