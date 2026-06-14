"""Configurable deterministic patterns for document classification."""

from __future__ import annotations

import re

from app.models.enums import DocumentType


CLASSIFICATION_PATTERNS: tuple[tuple[DocumentType, str, float], ...] = (
    (DocumentType.NOTIFICATION, r"\bNotification\s+No\.?\s+", 0.95),
    (DocumentType.CIRCULAR, r"\bCircular\s+No\.?\s+", 0.95),
    (DocumentType.ORDER, r"\bOrder\s+No\.?\s+", 0.95),
    (DocumentType.GAZETTE, r"\bGazette\b", 0.80),
    (DocumentType.POLICY, r"\bPolicy\b", 0.80),
    (DocumentType.ADVISORY, r"\bAdvisory\b", 0.80),
)


def compile_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


def build_compiled_patterns(
    patterns: tuple[tuple[DocumentType, str, float], ...] = CLASSIFICATION_PATTERNS,
) -> list[tuple[DocumentType, re.Pattern[str], float]]:
    return [
        (doc_type, compile_pattern(pattern), confidence)
        for doc_type, pattern, confidence in patterns
    ]
