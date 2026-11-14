"""Unit tests for PDF extraction (digital and scanned)."""

from __future__ import annotations

import hashlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from app.ingestion.exceptions import DocumentLoadError
from app.ingestion.pdf_loader import AutoPDFLoader, OCRDocumentLoader, PyMuPDFDocumentLoader, get_document_loader
from app.schemas.processing import RawDocument


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


class FakeImage:
    def __init__(self, text: str) -> None:
        self.text = text


def install_fake_ocr(monkeypatch: pytest.MonkeyPatch, page_texts: list[str]) -> list[str]:
    """Install fake pdf2image/pytesseract modules; returns a list recording converted paths."""

    converted: list[str] = []

    def convert_from_path(path: str) -> list[FakeImage]:
        converted.append(path)
        return [FakeImage(text) for text in page_texts]

    monkeypatch.setitem(sys.modules, "pdf2image", SimpleNamespace(convert_from_path=convert_from_path))
    monkeypatch.setitem(sys.modules, "pytesseract", SimpleNamespace(image_to_string=lambda image: image.text))
    return converted


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


# ---- OCR loader tests ----


def test_ocr_loader_returns_one_page_per_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    install_fake_ocr(monkeypatch, ["scanned one", "scanned two"])

    result = OCRDocumentLoader().load(str(pdf_path))

    assert [page.page_number for page in result.pages] == [1, 2]
    assert result.raw_text == "scanned one\nscanned two"


def test_ocr_loader_wraps_ocr_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")

    def broken(path: str) -> list[FakeImage]:
        raise RuntimeError("poppler missing")

    monkeypatch.setitem(sys.modules, "pdf2image", SimpleNamespace(convert_from_path=broken))
    monkeypatch.setitem(sys.modules, "pytesseract", SimpleNamespace(image_to_string=lambda image: ""))

    with pytest.raises(DocumentLoadError):
        OCRDocumentLoader().load(str(pdf_path))


# ---- Content hash ----


def test_loader_sets_content_hash_of_file_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "notice.pdf"
    pdf_path.write_bytes(b"%PDF-1.7 unique bytes")
    install_fake_fitz(monkeypatch, FakeDocument(["text"]))

    result = PyMuPDFDocumentLoader().load(str(pdf_path))

    assert result.content_hash == hashlib.sha256(b"%PDF-1.7 unique bytes").hexdigest()


# ---- AutoPDFLoader ----


def test_auto_loader_reads_digital_pdf_once_without_ocr(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "digital.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    install_fake_fitz(monkeypatch, FakeDocument(["a" * 100, "b" * 100]))
    converted = install_fake_ocr(monkeypatch, ["should not be used"])
    calls: list[str] = []
    original_load = PyMuPDFDocumentLoader.load

    def counting_load(self, path: str) -> RawDocument:
        calls.append(path)
        return original_load(self, path)

    monkeypatch.setattr(PyMuPDFDocumentLoader, "load", counting_load)

    result = AutoPDFLoader().load(str(pdf_path))

    assert calls == [str(pdf_path)]
    assert converted == []
    assert result.pages[0].text == "a" * 100


def test_auto_loader_falls_back_to_ocr_for_scans(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    install_fake_fitz(monkeypatch, FakeDocument(["", "", "short"]))
    converted = install_fake_ocr(monkeypatch, ["ocr page one", "ocr page two", "ocr page three"])

    result = AutoPDFLoader().load(str(pdf_path))

    assert converted == [str(pdf_path)]
    assert result.pages[0].text == "ocr page one"


def test_factory_returns_pymupdf_for_digital_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "digital.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    install_fake_fitz(monkeypatch, FakeDocument(["a" * 100, "b" * 100, "c" * 100]))

    loader = get_document_loader(str(pdf_path))

    assert isinstance(loader, PyMuPDFDocumentLoader)


def test_factory_returns_ocr_for_empty_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")
    install_fake_fitz(monkeypatch, FakeDocument(["", "", ""]))

    loader = get_document_loader(str(pdf_path))

    assert isinstance(loader, OCRDocumentLoader)


def test_factory_raises_on_pymupdf_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"%PDF-1.7")

    def bad_load(self, _: str) -> RawDocument:
        raise RuntimeError("fitz failed")

    monkeypatch.setattr(PyMuPDFDocumentLoader, "load", bad_load)

    with pytest.raises(RuntimeError, match="fitz failed"):
        get_document_loader(str(pdf_path))
