"""Configurable regex patterns for deterministic metadata extraction."""

from __future__ import annotations

DOCUMENT_NUMBER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("NOTIFICATION", r"\bNotification\s+No\.?\s+(?P<number>[A-Za-z0-9][A-Za-z0-9./_-]*(?:-[A-Za-z0-9]+)?)"),
    ("CIRCULAR", r"\bCircular\s+No\.?\s+(?P<number>[A-Za-z0-9][A-Za-z0-9./_-]*(?:-[A-Za-z0-9]+)?)"),
    ("ORDER", r"\bOrder\s+No\.?\s+(?P<number>[A-Za-z0-9][A-Za-z0-9./_-]*(?:-[A-Za-z0-9]+)?)"),
    ("UNKNOWN", r"\bF\.?\s*No\.?\s+(?P<number>[A-Za-z0-9][A-Za-z0-9./_-]*(?:-[A-Za-z0-9]+)?)"),
)

DATE_PATTERNS: tuple[str, ...] = (
    r"\b(?P<date>\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
    r"\b(?P<date>\d{1,2}\s+(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{4})\b",
    r"\b(?P<date>\d{1,2}-\d{1,2}-\d{4})\b",
    r"\b(?P<date>\d{4}-\d{1,2}-\d{1,2})\b",
)

DATE_FORMATS: tuple[str, ...] = (
    "%d %B %Y",
    "%d %b %Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
)

SUBJECT_PATTERNS: tuple[str, ...] = (
    r"^\s*Subject\s*:\s*(?P<subject>.+?)\s*$",
    r"^\s*SUBJECT\s*:\s*(?P<subject>.+?)\s*$",
    r"^\s*Subject\s*-\s*(?P<subject>.+?)\s*$",
)

DEPARTMENT_PATTERNS: tuple[str, ...] = (
    r"\b(?P<department>Ministry\s+of\s+[A-Za-z][A-Za-z &,-]+)",
    r"\b(?P<department>Department\s+of\s+[A-Za-z][A-Za-z &,-]+)",
    r"\b(?P<department>Central\s+Board\s+of\s+[A-Za-z][A-Za-z &,-]+)",
)

REFERENCE_PATTERNS: tuple[str, ...] = (
    r"\b(?P<reference>Notification\s+No\.?\s+[A-Za-z0-9][A-Za-z0-9./_-]*(?:-[A-Za-z0-9]+)?)",
    r"\b(?P<reference>Circular\s+No\.?\s+[A-Za-z0-9][A-Za-z0-9./_-]*(?:-[A-Za-z0-9]+)?)",
    r"\b(?P<reference>Order\s+No\.?\s+[A-Za-z0-9][A-Za-z0-9./_-]*(?:-[A-Za-z0-9]+)?)",
)
