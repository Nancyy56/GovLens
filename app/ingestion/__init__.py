"""
Document ingestion module (placeholder).

This module will handle document ingestion pipelines including
parsing, preprocessing, and initial data loading.

Currently a placeholder - no ingestion logic implemented.
"""

from app.ingestion.contracts import DocumentClassifier, DocumentLoader, MetadataExtractor
from app.ingestion.exceptions import DocumentLoadError, UnsupportedDocumentError
from app.ingestion.pdf_loader import OCRDocumentLoader, PyMuPDFDocumentLoader, get_document_loader

__all__ = [
    "DocumentClassifier",
    "DocumentLoader",
    "DocumentLoadError",
    "OCRDocumentLoader",
    "get_document_loader",
    "MetadataExtractor",
    "PyMuPDFDocumentLoader",
    "UnsupportedDocumentError",
]
