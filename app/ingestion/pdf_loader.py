"""Digital and scanned PDF loaders.

Digital PDFs are loaded with PyMuPDF. Scanned PDFs are loaded with Docling.
Both loaders preserve page order and one-based page numbers.
"""

from __future__ import annotations

import uuid
import logging
from pdf2image import convert_from_path
import pytesseract
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ingestion.contracts import DocumentLoader
from app.ingestion.exceptions import DocumentLoadError, UnsupportedDocumentError
from app.schemas.processing import PageContent, RawDocument

logger = logging.getLogger(__name__)


class PyMuPDFDocumentLoader(DocumentLoader):
    """Load text from digitally-born PDFs using PyMuPDF.

    The loader preserves page order and one-based page numbers so downstream
    citation generation can map extracted text back to the original PDF pages.
    OCR can be added later behind a separate loader without changing this
    contract.
    """

    source_type = "pdf"

    def load(self, file_path: str) -> RawDocument:
        """Extract ordered page text from a digital PDF file."""

        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            raise UnsupportedDocumentError(f"Unsupported document type for path: {file_path}")

        if not path.is_file():
            raise DocumentLoadError(f"PDF file does not exist: {file_path}")

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

        return RawDocument(
            document_id=uuid.uuid4(),
            source_type=self.source_type,
            source_path=str(path),
            pages=pages,
            ingested_at=datetime.now(UTC),
        )

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
        path = Path(file_path)

        if path.suffix.lower() != ".pdf":
            raise UnsupportedDocumentError(
                f"Unsupported document type for path: {file_path}"
            )

        if not path.is_file():
            raise DocumentLoadError(
                f"PDF file does not exist: {file_path}"
            )

        try:
            images = convert_from_path(str(path))

            pages = [
                PageContent(
                    page_number=i,
                    text=pytesseract.image_to_string(image),
                )
                for i, image in enumerate(images, start=1)
            ]

        except Exception as exc:
            raise DocumentLoadError(
                f"Failed to OCR PDF: {file_path}"
            ) from exc

        return RawDocument(
            document_id=uuid.uuid4(),
            source_type=self.source_type,
            source_path=str(path),
            pages=pages,
            ingested_at=datetime.now(UTC),
        )
    
def get_document_loader(
    file_path: str,
    text_threshold: int = 50,
    min_textful_pages_ratio: float = 0.5,
) -> DocumentLoader:
    """Return the appropriate loader for the supplied PDF.

    Probes the file with PyMuPDF first. If enough pages contain substantive
    text, the digital loader is used. Otherwise the scanned (OCR) loader
    is returned.
    """
    logger.info("Probing PDF loader for %s", file_path)
    probe = PyMuPDFDocumentLoader().load(file_path)
    raw_text_length = len(probe.raw_text)
    logger.info(
        "PyMuPDF probe extracted %s pages and %s characters from %s",
        probe.page_count,
        raw_text_length,
        file_path,
    )

    if not probe.pages:
        logger.info("Selecting OCRDocumentLoader for %s because no pages were extracted", file_path)
        return OCRDocumentLoader()
    textful = sum(1 for p in probe.pages if len(p.text.strip()) >= text_threshold)
    ratio = textful / len(probe.pages)

    if ratio >= min_textful_pages_ratio:
        logger.info(
            "Selecting PyMuPDFDocumentLoader for %s; textful_pages=%s total_pages=%s ratio=%.2f",
            file_path,
            textful,
            len(probe.pages),
            ratio,
        )
        return PyMuPDFDocumentLoader()
    logger.info(
        "Selecting OCRDocumentLoader for %s; textful_pages=%s total_pages=%s ratio=%.2f",
        file_path,
        textful,
        len(probe.pages),
        ratio,
    )
    return OCRDocumentLoader()
