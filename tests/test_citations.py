"""Unit tests for deterministic citation builder."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.citations import CitationBuilder
from app.citations.schemas import Citation, CitationBundle
from app.models.enums import DocumentType
from app.retrieval.schemas import RetrievedChunk


def _make_chunk(**kwargs: Any) -> RetrievedChunk:
    defaults: dict[str, Any] = dict(
        document_id="12345678-1234-1234-1234-123456789abc",
        document_number="",
        document_type=None,
        page_number=1,
        chunk_index=0,
        chunk_text="text",
        score=0.9,
        issue_date=None,
    )
    defaults.update(kwargs)
    return RetrievedChunk(**defaults)


class TestCitationBuilder:
    def test_notification_citation(self) -> None:
        chunk = _make_chunk(
            document_type=DocumentType.NOTIFICATION,
            document_number="17/2024",
            page_number=3,
            issue_date=date(2024, 1, 21),
        )
        bundle = CitationBuilder().build([chunk])
        assert bundle.citations[0].citation_text == (
            "Notification No. 17/2024\n"
            "Dated: 2024-01-21\n"
            "(Page 3)"
        )

    def test_circular_citation(self) -> None:
        chunk = _make_chunk(
            document_type=DocumentType.CIRCULAR,
            document_number="05/2025-GST",
            page_number=2,
            issue_date=None,
        )
        bundle = CitationBuilder().build([chunk])
        assert bundle.citations[0].citation_text == (
            "Circular No. 05/2025-GST\n"
            "(Page 2)"
        )

    def test_page_preserved(self) -> None:
        chunk = _make_chunk(page_number=7)
        bundle = CitationBuilder().build([chunk])
        assert "(Page 7)" in bundle.citations[0].citation_text

    def test_issue_date_included_when_present(self) -> None:
        chunk = _make_chunk(issue_date=date(2024, 1, 21))
        bundle = CitationBuilder().build([chunk])
        assert "Dated: 2024-01-21" in bundle.citations[0].citation_text

    def test_issue_date_omitted_when_none(self) -> None:
        chunk = _make_chunk(issue_date=None)
        bundle = CitationBuilder().build([chunk])
        assert "Dated:" not in bundle.citations[0].citation_text

    def test_multiple_citations(self) -> None:
        chunks = [
            _make_chunk(
                document_type=DocumentType.NOTIFICATION,
                document_number="17/2024",
                page_number=1,
            ),
            _make_chunk(
                document_type=DocumentType.CIRCULAR,
                document_number="04/2025-GST",
                page_number=2,
            ),
        ]
        bundle = CitationBuilder().build(chunks)
        assert len(bundle.citations) == 2
        assert bundle.citations[0].citation_text.startswith("Notification No. 17/2024")
        assert bundle.citations[1].citation_text.startswith("Circular No. 04/2025-GST")

    def test_missing_metadata_handled_gracefully(self) -> None:
        chunk = _make_chunk(document_type=None, document_number=None)
        bundle = CitationBuilder().build([chunk])
        citation = bundle.citations[0]
        assert citation.document_type is None
        assert citation.document_number is None
        assert citation.citation_text.startswith("Unknown Document")

    def test_empty_input(self) -> None:
        bundle = CitationBuilder().build([])
        assert bundle.citations == []
