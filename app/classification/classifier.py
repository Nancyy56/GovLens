"""Deterministic document classifier implementation."""

from __future__ import annotations

from typing import List, Optional

from app.classification.rules import (
    BODY_ONLY_CONFIDENCE,
    HEADER_CHARS,
    MIN_BODY_OCCURRENCES,
    STRONG_CONFIDENCE,
    build_compiled_patterns,
)
from app.models.enums import DocumentType
from app.schemas.processing import DocumentClassificationResult, DocumentMetadata, RawDocument


class RuleBasedDocumentClassifier:
    """Classify documents using deterministic regex patterns.

    Priority:
    1. If metadata already carries a concrete document_type, reuse it.
    2. Otherwise use the first pattern (in priority order) found in the
       document heading.
    3. Otherwise use an explicit pattern ("Circular No.") anywhere, or a weak
       single-word pattern ("Policy") only if it recurs in the body.
    4. Fall back to UNKNOWN when no signal is found.
    """

    def __init__(
        self,
        patterns: Optional[List[tuple]] = None,
    ) -> None:
        if patterns is None:
            self._patterns = build_compiled_patterns()
        else:
            from app.classification.rules import compile_pattern

            self._patterns = [
                (doc_type, compile_pattern(pattern), confidence)
                for doc_type, pattern, confidence in patterns
            ]

    def classify(
        self,
        raw_document: RawDocument,
        metadata: DocumentMetadata | None = None,
    ) -> DocumentClassificationResult:
        text = raw_document.raw_text

        metadata_type = self._metadata_type(metadata)
        if metadata_type is not None:
            return DocumentClassificationResult(
                document_type=metadata_type,
                confidence_score=0.95,
            )

        header = text[:HEADER_CHARS]
        for doc_type, pattern, confidence in self._patterns:
            if pattern.search(header):
                return DocumentClassificationResult(document_type=doc_type, confidence_score=confidence)

        for doc_type, pattern, confidence in self._patterns:
            if confidence >= STRONG_CONFIDENCE and pattern.search(text):
                return DocumentClassificationResult(document_type=doc_type, confidence_score=confidence)
        for doc_type, pattern, confidence in self._patterns:
            if confidence < STRONG_CONFIDENCE and len(pattern.findall(text)) >= MIN_BODY_OCCURRENCES:
                return DocumentClassificationResult(
                    document_type=doc_type,
                    confidence_score=min(confidence, BODY_ONLY_CONFIDENCE),
                )

        return DocumentClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence_score=0.20,
        )

    @staticmethod
    def _metadata_type(metadata: DocumentMetadata | None) -> DocumentType | None:
        if metadata is None:
            return None
        doc_type = metadata.document_type
        if doc_type is None or doc_type == DocumentType.UNKNOWN:
            return None
        return doc_type
