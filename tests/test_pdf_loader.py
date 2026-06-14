"""Unit tests for PDF extraction (digital and scanned)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from app.ingestion.exceptions import DocumentLoadError
from app.ingestion.pdf_loader import DoclingDocumentLoader, PyMuPDFDocumentLoader, get_document_loader


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def get_text(self, mode: str) -> str:
        assert mode == "text"
        return self.text


class FakeDocument:
    def __init__(self, page_texts: list[str]) -> None:
        self._pages = [FakePage(text) for text in page_texts]
        self.page_count = len(self._pages)
        self.closed = False

    def load_page(self, page_index: int) -> FakePage:
        return self._pages[page_index]

    def close(self) -> None:
        self.closed = True


def install_fake_fitz(monkeypatch: pytest.MonkeyPatch, document: FakeDocument) -> None:
    fake_fitz = SimpleNamespace(open=lambda _: document)
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)


class FakeTextItem:
    def __init__(self, text: str, page_no: int) -> None:
        self.text = text
        self.prov = [SimpleNamespace(page_no=page_no)]


class FakeDoclingDocument:
    def __init__(self, items: list[FakeTextItem]) -> None:
        self.texts = items


class FakeConverter:
    def __init__(self, document: FakeDoclingDocument) -> None:
        self._document = document

    def convert(self, source: str) -> SimpleNamespace:
        return SimpleNamespace(document=self._document)


def install_fake_docling(monkeypatch: pytest.MonkeyPatch, document: FakeDoclingDocument) -> None:
    fake_converter = FakeConverter(document)
    fake_module = SimpleNamespace(DocumentConverter=lambda *a, **k: fake_converter)
    monkeypatch.setitem(sys.modules, "docling.document_converter", fake_module)


# Existing PyMuPDF tests follow unchanged below...


def test_successful_extraction(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "notice.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    fake_document = FakeDocument(["first page", "second page"])
    install_fake_fitz(monkeypatch, fake_document)

    result = PyMuPDFDocumentLoader().load(str(pdf_path))

    assert result.source_type == "pdf"
    assert result.source_path == str(pdf_path)
    assert result.page_count == 2
    assert result.raw_text == "first page\nsecond page"
    assert [page.text for page in result.pages] == ["first page", "second page"]
    assert fake_document.closed is True


def test_empty_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    install_fake_fitz(monkeypatch, FakeDocument([]))

    result = PyMuPDFDocumentLoader().load(str(pdf_path))

    assert result.page_count == 0
    assert result.pages == []
    assert result.raw_text == ""


def test_invalid_path() -> None:
    with pytest.raises(DocumentLoadError):
        PyMuPDFDocumentLoader().load("/not/a/real/file.pdf")


def test_page_ordering(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "ordered.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    install_fake_fitz(monkeypatch, FakeDocument(["page one", "page two", "page three"]))

    result = PyMuPDFDocumentLoader().load(str(pdf_path))

    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert [page.text for page in result.pages] == ["page one", "page two", "page three"]
    assert result.raw_text == "page one\npage two\npage three"


# ---- DoclingDocumentLoader tests ----


def test_docling_loader_returns_raw_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    document = FakeDoclingDocument([
        FakeTextItem("header text", 1),
        FakeTextItem("body text", 1),
        FakeTextItem("more body", 2),
    ])
    install_fake_docling(monkeypatch, document)

    result = DoclingDocumentLoader().load(str(pdf_path))

    assert result.source_type == "pdf"
    assert result.page_count == 2
    assert result.raw_text == "header text\nbody text\nmore body"
    assert [page.page_number for page in result.pages] == [1, 2]


def test_docling_loader_preserves_page_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    document = FakeDoclingDocument([
        FakeTextItem("page three text", 3),
        FakeTextItem("page one text", 1),
        FakeTextItem("page two text", 2),
    ])
    install_fake_docling(monkeypatch, document)

    result = DoclingDocumentLoader().load(str(pdf_path))

    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert result.pages[0].text == "page one text"
    assert result.pages[2].text == "page three text"


def test_docling_loader_handles_empty_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    document = FakeDoclingDocument([
        FakeTextItem("", 1),
        FakeTextItem("   ", 2),
        FakeTextItem("real text", 2),
    ])
    install_fake_docling(monkeypatch, document)

    result = DoclingDocumentLoader().load(str(pdf_path))

    assert result.page_count == 1
    assert result.pages[0].page_number == 2
    assert result.pages[0].text == "real text"


def test_docling_loader_wraps_import_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    monkeypatch.setitem(sys.modules, "docling.document_converter", None)

    with pytest.raises(DocumentLoadError):
        DoclingDocumentLoader().load(str(pdf_path))


def test_factory_returns_pymupdf_for_digital_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "digital.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    install_fake_fitz(monkeypatch, FakeDocument(["a" * 100, "b" * 100, "c" * 100]))

    loader = get_document_loader(str(pdf_path))

    assert isinstance(loader, PyMuPDFDocumentLoader)


def test_factory_returns_docling_for_empty_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    install_fake_fitz(monkeypatch, FakeDocument(["", "", ""]))
    document = FakeDoclingDocument([
        FakeTextItem("scanned page one", 1),
        FakeTextItem("scanned page two", 2),
    ])
    install_fake_docling(monkeypatch, document)

    loader = get_document_loader(str(pdf_path))

    assert isinstance(loader, DoclingDocumentLoader)


def test_factory_raises_on_pymupdf_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")

    def bad_load(self, _: str) -> RawDocument:
        raise RuntimeError("fitz failed")

    monkeypatch.setattr(PyMuPDFDocumentLoader, "load", bad_load)

    with pytest.raises(RuntimeError, match="fitz failed"):
        get_document_loader(str(pdf_path))
