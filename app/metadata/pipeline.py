"""Metadata extraction pipeline orchestration."""

from __future__ import annotations

from collections.abc import Sequence

from app.metadata.interfaces import MetadataExtractionStrategy, MetadataValidator
from app.metadata.validators import CriticalFieldMetadataValidator
from app.schemas.processing import DocumentMetadata, MetadataExtractionResult, RawDocument


class MetadataExtractionPipeline:
    """Coordinate metadata extraction strategy execution and validation.

    The pipeline is intentionally narrow: it accepts a `RawDocument`, invokes
    configured extraction strategies, validates the resulting metadata, and
    returns a result envelope. It does not implement extraction, regex rules,
    LLM calls, OCR, classification, retrieval, embeddings, or storage.

    Multiple strategies may be supplied to support future chains such as
    RuleBasedExtractor followed by LLMExtractor. The first strategy that returns
    metadata ends the chain; strategies that raise `NotImplementedError` are
    recorded as warnings so placeholders can exist before implementation.
    """

    def __init__(
        self,
        strategies: MetadataExtractionStrategy | Sequence[MetadataExtractionStrategy],
        validator: MetadataValidator | None = None,
    ) -> None:
        if isinstance(strategies, Sequence):
            self.strategies = list(strategies)
        else:
            self.strategies = [strategies]

        self.validator = validator or CriticalFieldMetadataValidator()

    def run(self, raw_document: RawDocument) -> MetadataExtractionResult:
        """Run extraction strategy orchestration and validate the result."""

        warnings: list[str] = []
        errors: list[str] = []
        metadata: DocumentMetadata | None = None

        for strategy in self.strategies:
            try:
                metadata = strategy.extract(raw_document)
                break
            except NotImplementedError as exc:
                warnings.append(str(exc))
            except Exception as exc:
                errors.append(str(exc))

        if metadata is None:
            if not errors:
                errors.append("No metadata extraction strategy produced metadata.")
            return MetadataExtractionResult(metadata=None, warnings=warnings, errors=errors)

        validation = self.validator.validate(metadata)
        warnings.extend(validation.warnings)

        return MetadataExtractionResult(
            metadata=metadata,
            warnings=warnings,
            errors=errors,
        )
