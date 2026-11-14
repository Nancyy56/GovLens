"""Unit tests for deterministic document chunking."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.chunking import RuleBasedDocumentChunker
from app.models.enums import DocumentType
from app.schemas.processing import DocumentMetadata, PageContent, RawDocument


def make_raw_document(pages: list[tuple[int, str]]) -> RawDocument:
    return RawDocument(
        document_id=uuid.uuid4(),
        source_type="pdf",
        source_path="/tmp/source.pdf",
        pages=[PageContent(page_number=p, text=t) for p, t in pages],
        ingested_at=datetime.now(UTC),
    )


def make_metadata(**kwargs) -> DocumentMetadata:
    defaults = dict(
        title="Test",
        document_number="TEST-01",
        document_type=DocumentType.ORDER,
        issue_date=None,
        confidence_score=0.9,
    )
    defaults.update(kwargs)
    return DocumentMetadata(**defaults)


def test_single_page_small_document() -> None:
    text = (
        "Ministry of Finance\n"
        "Order No. TEST-01\n"
        "21 January 2024\n"
        "This order directs all departments to comply."
    )
    raw = make_raw_document([(1, text)])
    chunks = RuleBasedDocumentChunker(min_tokens=500, max_tokens=1000).chunk(raw)

    assert len(chunks) == 1
    assert chunks[0].page_number == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].document_id == raw.document_id
    assert "Ministry of Finance" in chunks[0].chunk_text
    assert "Order No. TEST-01" in chunks[0].chunk_text
    assert "21 January 2024" in chunks[0].chunk_text
    assert chunks[0].estimated_token_count == len(chunks[0].chunk_text.split())


def test_multi_page_document() -> None:
    pages = [
        (1, "Page one content here. It has some sentences."),
        (2, "Page two content here. More sentences follow."),
        (3, "Page three content here. Final sentences."),
    ]
    raw = make_raw_document(pages)
    chunks = RuleBasedDocumentChunker(min_tokens=500, max_tokens=1000).chunk(raw)

    assert [c.page_number for c in chunks] == [1, 2, 3]


def test_large_page_split_into_multiple_chunks() -> None:
    sentences = [f"This is sentence number {i}. It continues the text." for i in range(200)]
    text = " ".join(sentences)
    raw = make_raw_document([(1, text)])
    chunks = RuleBasedDocumentChunker(min_tokens=200, max_tokens=400).chunk(raw)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.page_number == 1
        assert chunk.estimated_token_count <= 400


def test_page_boundary_preservation() -> None:
    raw = make_raw_document([(1, "Page 1 text."), (2, "Page 2 text.")])
    chunks = RuleBasedDocumentChunker(min_tokens=1, max_tokens=1000).chunk(raw)

    texts = [c.chunk_text for c in chunks]
    assert "Page 1 text." in texts
    assert "Page 2 text." in texts
    assert sum(1 for c in chunks if c.page_number == 1) == 1
    assert sum(1 for c in chunks if c.page_number == 2) == 1


def test_chunk_ordering() -> None:
    raw = make_raw_document([(1, "Alpha."), (2, "Beta."), (3, "Gamma.")])
    chunks = RuleBasedDocumentChunker(min_tokens=1, max_tokens=1000).chunk(raw)

    assert [c.page_number for c in chunks] == [1, 2, 3]
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == 0


def test_token_estimation() -> None:
    text = "one two three four five"
    raw = make_raw_document([(1, text)])
    chunks = RuleBasedDocumentChunker(min_tokens=1, max_tokens=100).chunk(raw)

    assert chunks[0].estimated_token_count == 5


def test_metadata_carried_forward() -> None:
    raw = make_raw_document([(1, "Order No. 42/2024\nSubject: Test\n")])
    metadata = make_metadata(
        document_type=DocumentType.ORDER,
        document_number="42/2024",
    )
    chunks = RuleBasedDocumentChunker().chunk(raw, metadata=metadata)

    assert chunks[0].document_type == DocumentType.ORDER
    assert chunks[0].document_number == "42/2024"


def test_empty_page_skipped() -> None:
    raw = make_raw_document([(1, ""), (2, "Real content here.")])
    chunks = RuleBasedDocumentChunker(min_tokens=1, max_tokens=1000).chunk(raw)

    assert len(chunks) == 1
    assert chunks[0].page_number == 2


def test_whitespace_only_page_skipped() -> None:
    raw = make_raw_document([(1, "   \n\t  "), (2, "Content.")])
    chunks = RuleBasedDocumentChunker(min_tokens=1, max_tokens=1000).chunk(raw)

    assert len(chunks) == 1
    assert chunks[0].page_number == 2


def test_line_breaks_are_preserved_in_chunk_text() -> None:
    from datetime import UTC, datetime
    import uuid

    from app.schemas.processing import PageContent, RawDocument

    raw = RawDocument(
        document_id=uuid.uuid4(),
        source_type="pdf",
        source_path="x.pdf",
        pages=[PageContent(page_number=1, text="Ministry of Finance\nNotification No. 12/2023\nThe rate is 5 percent. It applies now.")],
        ingested_at=datetime.now(UTC),
    )
    chunk = RuleBasedDocumentChunker().chunk(raw)[0]
    assert chunk.chunk_text == "Ministry of Finance\nNotification No. 12/2023\nThe rate is 5 percent. It applies now."
