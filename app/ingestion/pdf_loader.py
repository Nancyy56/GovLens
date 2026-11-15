"""Digital and scanned PDF loaders.

Digital PDFs are loaded with PyMuPDF. Scanned PDFs are loaded with Tesseract
OCR. ``AutoPDFLoader`` reads a file once with PyMuPDF and only falls back to
OCR when too few pages contain text. All loaders preserve page order and
one-based page numbers.
"""

from __future__ import annotations

import hashlib
import uuid
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ingestion.contracts import DocumentLoader
from app.ingestion.exceptions import DocumentLoadError, UnsupportedDocumentError
from app.schemas.processing import PageContent, RawDocument

logger = logging.getLogger(__name__)

DEFAULT_TEXT_THRESHOLD = 50
DEFAULT_MIN_TEXTFUL_PAGES_RATIO = 0.5


def compute_file_hash(file_path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file's bytes."""

    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_pdf_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        raise UnsupportedDocumentError(f"Unsupported document type for path: {file_path}")

    if not path.is_file():
        raise DocumentLoadError(f"PDF file does not exist: {file_path}")
    return path


def _build_raw_document(path: Path, pages: list[PageContent], source_type: str) -> RawDocument:
    return RawDocument(
        document_id=uuid.uuid4(),
        source_type=source_type,
        source_path=str(path),
        pages=pages,
        ingested_at=datetime.now(UTC),
        content_hash=compute_file_hash(path),
    )


def is_mostly_text(
    raw_document: RawDocument,
    text_threshold: int = DEFAULT_TEXT_THRESHOLD,
    min_textful_pages_ratio: float = DEFAULT_MIN_TEXTFUL_PAGES_RATIO,
) -> bool:
    """Return True when enough pages carry a usable text layer."""

    if not raw_document.pages:
        return False
    textful = sum(1 for p in raw_document.pages if len(p.text.strip()) >= text_threshold)
    return textful / len(raw_document.pages) >= min_textful_pages_ratio


class PyMuPDFDocumentLoader(DocumentLoader):
    """Load text from digitally-born PDFs using PyMuPDF.

    The loader preserves page order and one-based page numbers so downstream
    citation generation can map extracted text back to the original PDF pages.
    """

    source_type = "pdf"

    def load(self, file_path: str) -> RawDocument:
        """Extract ordered page text from a digital PDF file."""

        path = _validate_pdf_path(file_path)
        fitz = self._load_pymupdf()
        document: Any | None = None

        try:
            document = fitz.open(str(path))
            pages = [
                PageContent(page_number=page_index + 1, text=document.load_page(page_index).get_text("text") or "")
                for page_index in range(document.page_count)
            ]
        except UnsupportedDocumentError:
            raise
        except Exception as exc:
            raise DocumentLoadError(f"Failed to load digital PDF: {file_path}") from exc
        finally:
            if document is not None:
                document.close()

        return _build_raw_document(path, pages, self.source_type)

    def _load_pymupdf(self) -> Any:
        """Import PyMuPDF lazily so tests can provide a lightweight fake."""

        try:
            import fitz
        except ImportError as exc:
            raise DocumentLoadError("PyMuPDF is required for digital PDF extraction.") from exc

        return fitz


class OCRDocumentLoader(DocumentLoader):
    """Load text from scanned PDFs using Tesseract OCR."""

    source_type = "pdf"

    def load(self, file_path: str) -> RawDocument:
        path = _validate_pdf_path(file_path)

        try:
            from pdf2image import convert_from_path
            import pytesseract
        except ImportError as exc:
            raise DocumentLoadError("pdf2image and pytesseract are required for OCR.") from exc

        try:
            images = convert_from_path(str(path))
            pages = [
                PageContent(page_number=i, text=pytesseract.image_to_string(image))
                for i, image in enumerate(images, start=1)
            ]
        except Exception as exc:
            raise DocumentLoadError(f"Failed to OCR PDF: {file_path}") from exc

        return _build_raw_document(path, pages, self.source_type)


class AutoPDFLoader(DocumentLoader):
    """Read a PDF once with PyMuPDF and OCR it only when it looks scanned.

    The PyMuPDF result is returned directly for digital PDFs, so the file is
    parsed a single time on the common path.
    """

    def __init__(
        self,
        digital_loader: DocumentLoader | None = None,
        ocr_loader: DocumentLoader | None = None,
        text_threshold: int = DEFAULT_TEXT_THRESHOLD,
        min_textful_pages_ratio: float = DEFAULT_MIN_TEXTFUL_PAGES_RATIO,
    ) -> None:
        self.digital_loader = digital_loader or PyMuPDFDocumentLoader()
        self.ocr_loader = ocr_loader or OCRDocumentLoader()
        self.text_threshold = text_threshold
        self.min_textful_pages_ratio = min_textful_pages_ratio

    def load(self, file_path: str) -> RawDocument:
        digital = self.digital_loader.load(file_path)
        if is_mostly_text(digital, self.text_threshold, self.min_textful_pages_ratio):
            logger.info("Using PyMuPDF text for %s (%s pages)", file_path, digital.page_count)
            return digital

        logger.info("Falling back to OCR for %s (%s pages with little text)", file_path, digital.page_count)
        return self.ocr_loader.load(file_path)


def get_document_loader(
    file_path: str,
    text_threshold: int = DEFAULT_TEXT_THRESHOLD,
    min_textful_pages_ratio: float = DEFAULT_MIN_TEXTFUL_PAGES_RATIO,
) -> DocumentLoader:
    """Return the appropriate loader for the supplied PDF.

    Probes the file with PyMuPDF first. If enough pages contain substantive
    text, the digital loader is used. Otherwise the scanned (OCR) loader
    is returned. Prefer ``AutoPDFLoader`` in pipelines: it avoids parsing the
    file twice.
    """
    probe = PyMuPDFDocumentLoader().load(file_path)
    if is_mostly_text(probe, text_threshold, min_textful_pages_ratio):
        return PyMuPDFDocumentLoader()
    return OCRDocumentLoader()
