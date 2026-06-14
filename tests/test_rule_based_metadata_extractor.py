"""Unit tests for deterministic rule-based metadata extraction."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from app.metadata.extractors import RuleBasedMetadataExtractor
from app.models.enums import DocumentType
from app.schemas.processing import PageContent, RawDocument


def make_raw_document(text: str) -> RawDocument:
    return RawDocument(
        document_id=uuid.uuid4(),
        source_type="pdf",
        source_path="/tmp/source.pdf",
        pages=[PageContent(page_number=1, text=text)],
        ingested_at=datetime.now(UTC),
    )


def test_notification_extraction() -> None:
    raw_document = make_raw_document(
        """
        Ministry of Finance
        Notification No. 17/2024
        21 January 2024
        Subject: Tax compliance procedure
        """
    )

    metadata = RuleBasedMetadataExtractor().extract(raw_document)

    assert metadata.document_type == DocumentType.NOTIFICATION
    assert metadata.document_number == "17/2024"
    assert metadata.issue_date == date(2024, 1, 21)
    assert metadata.subject == "Tax compliance procedure"
    assert metadata.department == "Ministry of Finance"


def test_circular_extraction() -> None:
    raw_document = make_raw_document(
        """
        Department of Revenue
        Circular No. 04/2025-GST
        21 Jan 2024
        SUBJECT: GST clarification
        """
    )

    metadata = RuleBasedMetadataExtractor().extract(raw_document)

    assert metadata.document_type == DocumentType.CIRCULAR
    assert metadata.document_number == "04/2025-GST"
    assert metadata.issue_date == date(2024, 1, 21)
    assert metadata.subject == "GST clarification"
    assert metadata.department == "Department of Revenue"


def test_date_extraction_for_numeric_formats() -> None:
    extractor = RuleBasedMetadataExtractor()

    dash_date = extractor.extract(make_raw_document("Order No. XYZ/12/2024\n21-01-2024"))
    iso_date = extractor.extract(make_raw_document("Order No. XYZ/12/2024\n2024-01-21"))

    assert dash_date.issue_date == date(2024, 1, 21)
    assert iso_date.issue_date == date(2024, 1, 21)


def test_subject_extraction_with_dash() -> None:
    raw_document = make_raw_document("F.No. 12/34/2024\nSubject - Annual reporting requirements")

    metadata = RuleBasedMetadataExtractor().extract(raw_document)

    assert metadata.document_number == "12/34/2024"
    assert metadata.subject == "Annual reporting requirements"


def test_department_extraction() -> None:
    raw_document = make_raw_document(
        """
        Central Board of Indirect Taxes
        Order No. CBIC/01/2024
        """
    )

    metadata = RuleBasedMetadataExtractor().extract(raw_document)

    assert metadata.department == "Central Board of Indirect Taxes"


def test_missing_field_handling() -> None:
    raw_document = make_raw_document("This page has no explicit government metadata.")

    metadata = RuleBasedMetadataExtractor().extract(raw_document)

    assert metadata.document_number is None
    assert metadata.document_type is None
    assert metadata.issue_date is None
    assert metadata.subject is None
    assert metadata.department is None
    assert metadata.referenced_documents == []


def test_multiple_reference_extraction() -> None:
    raw_document = make_raw_document(
        """
        Order No. MAIN/01/2025
        This order refers to Notification No. 17/2024 and Circular No. 04/2025-GST.
        It also refers to Order No. XYZ/12/2024 and Notification No. 17/2024.
        """
    )

    metadata = RuleBasedMetadataExtractor().extract(raw_document)

    assert metadata.referenced_documents == [
        "Notification No. 17/2024",
        "Circular No. 04/2025-GST",
        "Order No. XYZ/12/2024",
    ]
