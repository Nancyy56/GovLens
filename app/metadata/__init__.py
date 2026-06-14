"""
Metadata extraction architecture module.

This package exposes contracts, placeholder strategies, validation, and
pipeline orchestration for future metadata extractors. It intentionally does
not implement extraction logic.
"""

from app.metadata.extractors import LLMMetadataExtractor, RuleBasedMetadataExtractor
from app.metadata.interfaces import MetadataExtractionStrategy, MetadataValidator
from app.metadata.pipeline import MetadataExtractionPipeline
from app.metadata.validators import CriticalFieldMetadataValidator

__all__ = [
    "CriticalFieldMetadataValidator",
    "LLMMetadataExtractor",
    "MetadataExtractionPipeline",
    "MetadataExtractionStrategy",
    "MetadataValidator",
    "RuleBasedMetadataExtractor",
]
