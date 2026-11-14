"""Configurable deterministic patterns for document classification."""

from __future__ import annotations

import re

from app.models.enums import DocumentType


CLASSIFICATION_PATTERNS: tuple[tuple[DocumentType, str, float], ...] = (
    (DocumentType.NOTIFICATION, r"\bNotification\s+No\.?\s+", 0.95),
    (DocumentType.CIRCULAR, r"\bCircular\s+No\.?\s+", 0.95),
    (DocumentType.ORDER, r"\bOrder\s+No\.?\s+", 0.95),
    (DocumentType.GAZETTE, r"\bGazette\b", 0.80),
    (DocumentType.REPORT, r"\b(?:Annual|Audit|Performance)\s+(?:Review|Report)\b|\bReport\s+on\b", 0.80),
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


# Patterns at or above this confidence name the document type explicitly
# ("Notification No. ..."); weaker ones are single words that also appear
# in passing ("in line with the Policy").
STRONG_CONFIDENCE = 0.9
# The heading of a document says what it is; mentions further down often do not.
HEADER_CHARS = 1200
# A weak word outside the heading only counts if the document keeps using it.
MIN_BODY_OCCURRENCES = 3
BODY_ONLY_CONFIDENCE = 0.5
