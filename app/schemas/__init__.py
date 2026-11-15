"""
Pydantic schemas for request/response validation.

Contains all request and response schemas used in API endpoints.
Schemas provide data validation and serialization for FastAPI.
"""

from app.schemas.documents import (
    DocumentChunkCreate,
    DocumentChunkRead,
    DocumentCreate,
    DocumentRead,
    DocumentRelationshipCreate,
    DocumentRelationshipRead,
)
from app.schemas.processing import (
    DocumentClassificationResult,
    DocumentMention,
    MetadataExtractionResult,
    MetadataValidationResult,
    DocumentMetadata,
    DocumentProcessingResult,
    PageContent,
    RawDocument,
)

__all__ = [
    "DocumentChunkCreate",
    "DocumentChunkRead",
    "DocumentClassificationResult",
    "DocumentCreate",
    "DocumentMention",
    "DocumentMetadata",
    "MetadataExtractionResult",
    "MetadataValidationResult",
    "DocumentProcessingResult",
    "DocumentRead",
    "DocumentRelationshipCreate",
    "DocumentRelationshipRead",
    "PageContent",
    "RawDocument",
]
