"""Custom exceptions for document loading failures."""


class DocumentLoadError(Exception):
    """Raised when a supported document cannot be loaded or read."""


class UnsupportedDocumentError(DocumentLoadError):
    """Raised when a loader receives a document type it does not support."""
