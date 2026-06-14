"""Unit tests for comparison preparation engine."""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.processing import PageContent
from app.comparison.engine import ComparisonEngine
from app.comparison.schemas import ComparisonInput, SourceContext
from app.models.enums import DocumentType
from app.retrieval.schemas import RetrievedChunk


def _make_chunk(document_id, document_number, document_type, page_number, chunk_index, chunk_text):
    return RetrievedChunk(
        document_id=document_id,
        document_number=document_number,
        document_type=document_type,
        page_number=page_number,
        chunk_index=chunk_index,
        chunk_text=chunk_text,
        score=0.9,
    )


class TestComparisonEngine:
    def test_single_source(self) -> None:
        doc_id = "11111111-1111-1111-1111-111111111111"
        chunks = [
            _make_chunk(doc_id, "N1", DocumentType.NOTIFICATION, 1, 0, "alpha"),
            _make_chunk(doc_id, "N1", DocumentType.NOTIFICATION, 1, 1, "beta"),
        ]
        result = ComparisonEngine().prepare("query", chunks)
        assert len(result.sources) == 1
        assert str(result.sources[0].document_id) == doc_id
        assert result.sources[0].document_number == "N1"
        assert result.sources[0].chunks == [
            PageContent(page_number=1, text="alpha\n\nbeta")
        ]

    def test_multiple_sources(self) -> None:
        id_a = "11111111-1111-1111-1111-111111111111"
        id_b = "22222222-2222-2222-2222-222222222222"
        chunks = [
            _make_chunk(id_a, "N1", DocumentType.NOTIFICATION, 1, 0, "a1"),
            _make_chunk(id_b, "C1", DocumentType.CIRCULAR, 2, 0, "b1"),
        ]
        result = ComparisonEngine().prepare("query", chunks)
        assert len(result.sources) == 2
        assert {str(s.document_id) for s in result.sources} == {id_a, id_b}

    def test_chunk_ordering_by_page_then_index(self) -> None:
        doc_id = "11111111-1111-1111-1111-111111111111"
        chunks = [
            _make_chunk(doc_id, "N1", DocumentType.NOTIFICATION, 2, 0, "p2a"),
            _make_chunk(doc_id, "N1", DocumentType.NOTIFICATION, 1, 0, "p1a"),
        ]
        result = ComparisonEngine().prepare("query", chunks)
        source = result.sources[0]
        assert source.chunks[0].page_number == 1
        assert source.chunks[1].page_number == 2

    def test_metadata_preserved(self) -> None:
        doc_id = "11111111-1111-1111-1111-111111111111"
        chunks = [
            _make_chunk(doc_id, "N1", DocumentType.NOTIFICATION, 1, 0, "text"),
        ]
        result = ComparisonEngine().prepare("query", chunks)
        source = result.sources[0]
        assert source.document_number == "N1"
        assert source.document_type == DocumentType.NOTIFICATION

    def test_empty_input(self) -> None:
        result = ComparisonEngine().prepare("query", [])
        assert result.sources == []
        assert result.query == "query"
