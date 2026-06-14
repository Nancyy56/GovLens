"""Unit tests for deterministic document classification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.classification.classifier import RuleBasedDocumentClassifier
from app.models.enums import DocumentType
from app.schemas.processing import DocumentMetadata, PageContent, RawDocument


def make_raw_document(text: str) -> RawDocument:
    return RawDocument(
        document_id=uuid.uuid4(),
        source_type="pdf",
        source_path="/tmp/source.pdf",
        pages=[PageContent(page_number=1, text=text)],
        ingested_at=datetime.now(UTC),
    )


def test_classify_notification() -> None:
    raw = make_raw_document("Ministry of Finance\nNotification No. 17/2024\n21 January 2024")
    result = RuleBasedDocumentClassifier().classify(raw)

    assert result.document_type == DocumentType.NOTIFICATION
    assert result.confidence_score == 0.95


def test_classify_circular() -> None:
    raw = make_raw_document("Department of Revenue\nCircular No. 04/2025-GST\n21 Jan 2024")
    result = RuleBasedDocumentClassifier().classify(raw)

    assert result.document_type == DocumentType.CIRCULAR
    assert result.confidence_score == 0.95


def test_classify_order() -> None:
    raw = make_raw_document("CBIC\nOrder No. XYZ/12/2024\n21-01-2024")
    result = RuleBasedDocumentClassifier().classify(raw)

    assert result.document_type == DocumentType.ORDER
    assert result.confidence_score == 0.95


def test_classify_gazette() -> None:
    raw = make_raw_document("Government Gazette Extraordinary\nPublished on 15 March 2024")
    result = RuleBasedDocumentClassifier().classify(raw)

    assert result.document_type == DocumentType.GAZETTE
    assert result.confidence_score == 0.80


def test_classify_policy() -> None:
    raw = make_raw_document("National Education Policy 2020\nMinistry of Education")
    result = RuleBasedDocumentClassifier().classify(raw)

    assert result.document_type == DocumentType.POLICY
    assert result.confidence_score == 0.80


def test_classify_advisory() -> None:
    raw = make_raw_document("Travel Advisory for monsoon season\nMinistry of External Affairs")
    result = RuleBasedDocumentClassifier().classify(raw)

    assert result.document_type == DocumentType.ADVISORY
    assert result.confidence_score == 0.80


def test_classify_unknown() -> None:
    raw = make_raw_document("Some random text with no classification signal whatsoever.")
    result = RuleBasedDocumentClassifier().classify(raw)

    assert result.document_type == DocumentType.UNKNOWN
    assert result.confidence_score == 0.20


def test_metadata_type_override_used() -> None:
    raw = make_raw_document("Random text without explicit type signal.")
    metadata = DocumentMetadata(
        title="Test",
        document_type=DocumentType.CIRCULAR,
        confidence_score=0.0,
    )
    result = RuleBasedDocumentClassifier().classify(raw, metadata=metadata)

    assert result.document_type == DocumentType.CIRCULAR
    assert result.confidence_score == 0.95


def test_metadata_unknown_type_falls_back_to_rules() -> None:
    raw = make_raw_document("Random text without any signal.")
    metadata = DocumentMetadata(
        title="Test",
        document_type=DocumentType.UNKNOWN,
        confidence_score=0.0,
    )
    result = RuleBasedDocumentClassifier().classify(raw, metadata=metadata)

    assert result.document_type == DocumentType.UNKNOWN
    assert result.confidence_score == 0.20


def test_metadata_none_uses_rules() -> None:
    raw = make_raw_document("Notification No. 99/2024")
    result = RuleBasedDocumentClassifier().classify(raw, metadata=None)

    assert result.document_type == DocumentType.NOTIFICATION
    assert result.confidence_score == 0.95
