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

# A document number as it appears after "No." in government documents.
DOCUMENT_NUMBER_VALUE = r"[A-Za-z0-9][A-Za-z0-9./_-]*(?:-[A-Za-z0-9]+)?"

# A list item must contain a digit, so words like "and" are never taken as numbers.
_LISTED_NUMBER = r"(?=[A-Za-z./_-]*\d)" + DOCUMENT_NUMBER_VALUE

# Separator between numbers in a list: "1/2020, 2/2020 and No. 3/2020".
LIST_SEPARATOR_PATTERN = r"\s*(?:,|\band\b|&)\s*(?:Nos?\.?\s*)?"

# Mentions of other documents. Matches "Notification No. 12/2023", the long
# form "notification of the Government of India ..., No. 12/2023", and lists
# such as "Notifications Nos. 1/2020, 2/2020 and 3/2020".
MENTION_PATTERN = (
    r"\b(?P<type>Notification|Circular|Order)s?\b"
    r"(?:\s+(?:of|in|issued|dated)\b[^.;\n]{0,160}?)?"
    r"\s*,?\s*Nos?\.?\s*(?P<numbers>" + DOCUMENT_NUMBER_VALUE
    + r"(?:" + LIST_SEPARATOR_PATTERN + _LISTED_NUMBER + r")*)"
)

# Text allowed between two separate mentions that form one list,
# e.g. "Notification No. A and Circular No. B are rescinded".
MENTION_GROUP_GAP_PATTERN = r"^\s*(?:,|\band\b|&|,\s*and\b)\s*$"

# Words near a mention that reveal how the current document relates to it.
# Checked in order; the first match wins.
RELATIONSHIP_KEYWORD_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "SUPERSEDES",
        r"supersession|supersed|rescind|repeal|withdraw|stands?\s+revoked|\brevok|\bcancel",
    ),
    ("AMENDS", r"amend|modif(?:y|ies|ied|ication)|substitut"),
)

# How far (in characters) around a mention to look for relationship keywords.
RELATIONSHIP_CONTEXT_CHARS = 100

# Clause boundaries. Keywords on the far side of one belong to a different
# clause ("in supersession of A, and under B" must not mark B superseded).
# Plain commas are not boundaries because legal text often reads
# "in supersession of the Ministry of Finance, Department of Revenue, Notification No. X".
CLAUSE_BOUNDARY_PATTERN = r";|\.\s|,\s*(?:and|or|but|except|save|read\s+with|under|in\s+exercise)\b"
