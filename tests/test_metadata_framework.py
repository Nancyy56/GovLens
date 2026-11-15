"""Unit tests for metadata extraction framework orchestration."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from app.metadata.extractors import LLMMetadataExtractor, RuleBasedMetadataExtractor
from app.metadata.pipeline import MetadataExtractionPipeline
from app.metadata.validators import CriticalFieldMetadataValidator
from app.models.enums import DocumentType
from app.schemas.processing import DocumentMetadata, PageContent, RawDocument


class FakeMetadataStrategy:
    def __init__(self, metadata: DocumentMetadata) -> None:
        self.metadata = metadata

    def extract(self, raw_document: RawDocument) -> DocumentMetadata:
        return self.metadata


class FailingMetadataStrategy:
    def extract(self, raw_document: RawDocument) -> DocumentMetadata:
        raise RuntimeError("strategy failed")


def make_raw_document() -> RawDocument:
    return RawDocument(
        document_id=uuid.uuid4(),
        source_type="pdf",
        source_path="/tmp/source.pdf",
        pages=[PageContent(page_number=1, text="digital text")],
        ingested_at=datetime.now(UTC),
    )


def make_metadata() -> DocumentMetadata:
    return DocumentMetadata(
        title="Government Order",
        document_number="GO-2026-01",
        document_type=DocumentType.ORDER,
        issue_date=date(2026, 6, 12),
        confidence_score=0.95,
    )


def test_validator_accepts_complete_critical_fields() -> None:
    result = CriticalFieldMetadataValidator().validate(make_metadata())

    assert result.is_valid is True
    assert result.missing_fields == []
    assert result.warnings == []


def test_validator_reports_missing_critical_fields() -> None:
    metadata = DocumentMetadata.model_construct(
        title="Incomplete",
        document_number=" ",
        document_type=DocumentType.UNKNOWN,
        issue_date=None,
        confidence_score=0.2,
        supersedes_documents=[],
        amends_documents=[],
        referenced_documents=[],
    )

    result = CriticalFieldMetadataValidator().validate(metadata)

    assert result.is_valid is False
    assert result.missing_fields == ["document_type", "document_number", "issue_date"]
    assert result.warnings == [
        "Missing critical metadata field: document_type",
        "Missing critical metadata field: document_number",
        "Missing critical metadata field: issue_date",
    ]


def test_pipeline_returns_metadata_and_validation_warnings() -> None:
    metadata = DocumentMetadata.model_construct(
        title="Incomplete",
        document_number="",
        document_type=DocumentType.ORDER,
        issue_date=date(2026, 6, 12),
        confidence_score=0.7,
        supersedes_documents=[],
        amends_documents=[],
        referenced_documents=[],
    )
    pipeline = MetadataExtractionPipeline(FakeMetadataStrategy(metadata))

    result = pipeline.run(make_raw_document())

    assert result.metadata is metadata
    assert result.errors == []
    assert result.warnings == ["Missing critical metadata field: document_number"]


def test_pipeline_records_strategy_failures_without_extracting() -> None:
    pipeline = MetadataExtractionPipeline(FailingMetadataStrategy())

    result = pipeline.run(make_raw_document())

    assert result.metadata is None
    assert result.warnings == []
    assert result.errors == ["strategy failed"]


def test_pipeline_supports_future_strategy_chaining() -> None:
    metadata = make_metadata()
    pipeline = MetadataExtractionPipeline(
        [
            LLMMetadataExtractor(),
            FakeMetadataStrategy(metadata),
        ]
    )

    result = pipeline.run(make_raw_document())

    assert result.metadata is metadata
    assert result.errors == []
    assert result.warnings == [
        "LLM metadata extraction is not configured.",
    ]
