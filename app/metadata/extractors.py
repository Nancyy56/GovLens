"""Metadata extraction strategies."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from re import Pattern

from app.metadata.interfaces import MetadataExtractionStrategy
from app.metadata.normalization import normalize_document_number
from app.metadata.patterns import (
    DATE_FORMATS,
    DATE_PATTERNS,
    DEPARTMENT_PATTERNS,
    DOCUMENT_NUMBER_PATTERNS,
    CLAUSE_BOUNDARY_PATTERN,
    LIST_SEPARATOR_PATTERN,
    MENTION_GROUP_GAP_PATTERN,
    MENTION_PATTERN,
    REFERENCE_PATTERNS,
    RELATIONSHIP_CONTEXT_CHARS,
    RELATIONSHIP_KEYWORD_PATTERNS,
    SUBJECT_PATTERNS,
)
from app.models.enums import DocumentType, RelationshipType
from app.schemas.processing import DocumentMention, DocumentMetadata, RawDocument

logger = logging.getLogger(__name__)

# When one number is mentioned several times, keep the strongest link.
_RELATIONSHIP_STRENGTH = {
    RelationshipType.REFERENCES: 0,
    RelationshipType.AMENDS: 1,
    RelationshipType.SUPERSEDES: 2,
}


class RuleBasedMetadataExtractor(MetadataExtractionStrategy):
    """Extract metadata using deterministic, configurable text patterns.

    This strategy performs no OCR, classification, LLM calls, retrieval,
    embeddings, or fallback orchestration. It only reads text already present
    on `RawDocument` and maps explicit textual matches into `DocumentMetadata`,
    including which other documents this one supersedes, amends, or references.
    """

    def __init__(
        self,
        document_number_patterns: tuple[tuple[str, str], ...] = DOCUMENT_NUMBER_PATTERNS,
        date_patterns: tuple[str, ...] = DATE_PATTERNS,
        subject_patterns: tuple[str, ...] = SUBJECT_PATTERNS,
        department_patterns: tuple[str, ...] = DEPARTMENT_PATTERNS,
        reference_patterns: tuple[str, ...] = REFERENCE_PATTERNS,
        date_formats: tuple[str, ...] = DATE_FORMATS,
        mention_pattern: str = MENTION_PATTERN,
        relationship_keyword_patterns: tuple[tuple[str, str], ...] = RELATIONSHIP_KEYWORD_PATTERNS,
        relationship_context_chars: int = RELATIONSHIP_CONTEXT_CHARS,
        clause_boundary_pattern: str = CLAUSE_BOUNDARY_PATTERN,
    ) -> None:
        self.document_number_patterns = [
            (DocumentType[document_type_name], re.compile(pattern, re.IGNORECASE))
            for document_type_name, pattern in document_number_patterns
        ]
        self.date_patterns = self._compile_many(date_patterns)
        self.subject_patterns = self._compile_many(subject_patterns, flags=re.IGNORECASE | re.MULTILINE)
        self.department_patterns = self._compile_many(department_patterns, flags=re.IGNORECASE)
        self.reference_patterns = self._compile_many(reference_patterns, flags=re.IGNORECASE)
        self.date_formats = date_formats
        self.mention_pattern = re.compile(mention_pattern, re.IGNORECASE)
        self.relationship_keyword_patterns = [
            (RelationshipType[name], re.compile(pattern, re.IGNORECASE))
            for name, pattern in relationship_keyword_patterns
        ]
        self.relationship_context_chars = relationship_context_chars
        self.clause_boundary_pattern = re.compile(clause_boundary_pattern, re.IGNORECASE)
        self.list_separator_pattern = re.compile(LIST_SEPARATOR_PATTERN, re.IGNORECASE)
        self.mention_group_gap_pattern = re.compile(MENTION_GROUP_GAP_PATTERN, re.IGNORECASE)

    def extract(self, raw_document: RawDocument) -> DocumentMetadata:
        """Extract explicit metadata fields from raw document text."""

        text = raw_document.raw_text
        document_type, document_number = self._extract_document_number(text)
        issue_date = self._extract_issue_date(text)
        subject = self._extract_subject(text)
        department = self._extract_department(text)
        referenced_documents = self._extract_referenced_documents(
            text=text,
            document_number=document_number,
            document_type=document_type,
        )
        mentions = self._extract_mentions(text=text, document_number=document_number)

        return DocumentMetadata(
            document_number=document_number,
            document_type=document_type,
            issue_date=issue_date,
            department=department,
            subject=subject,
            referenced_documents=referenced_documents,
            mentions=mentions,
            supersedes_documents=[
                m.document_number for m in mentions if m.relationship_type == RelationshipType.SUPERSEDES
            ],
            amends_documents=[
                m.document_number for m in mentions if m.relationship_type == RelationshipType.AMENDS
            ],
            confidence_score=self._confidence_score(
                document_number=document_number,
                document_type=document_type,
                issue_date=issue_date,
                subject=subject,
                department=department,
            ),
        )

    def _extract_document_number(self, text: str) -> tuple[DocumentType | None, str | None]:
        best_document_type: DocumentType | None = None
        best_number: str | None = None
        best_start: int | None = None

        for document_type, pattern in self.document_number_patterns:
            match = pattern.search(text)
            if match is None:
                continue
            start = match.start()
            if best_start is None or start < best_start:
                best_start = start
                best_document_type = document_type
                best_number = self._clean_value(match.group("number"))

        return best_document_type, best_number

    def _extract_issue_date(self, text: str) -> date | None:
        for pattern in self.date_patterns:
            match = pattern.search(text)
            if match is None:
                continue

            parsed_date = self._parse_date(match.group("date"))
            if parsed_date is not None:
                return parsed_date

        return None

    def _extract_subject(self, text: str) -> str | None:
        for pattern in self.subject_patterns:
            match = pattern.search(text)
            if match is not None:
                subject = self._clean_value(match.group("subject"))
                if subject:
                    return subject
        return None

    def _extract_department(self, text: str) -> str | None:
        for pattern in self.department_patterns:
            match = pattern.search(text)
            if match is not None:
                department = self._clean_value(match.group("department"))
                if department:
                    return department
        return None

    def _extract_referenced_documents(
        self,
        *,
        text: str,
        document_number: str | None,
        document_type: DocumentType | None,
    ) -> list[str]:
        seen: set[str] = set()
        ordered: list[tuple[int, str]] = []

        for pattern in self.reference_patterns:
            for match in pattern.finditer(text):
                reference = self._clean_value(match.group("reference"))
                if not reference or self._is_current_document_reference(reference, document_number, document_type):
                    continue

                normalized_reference = reference.casefold()
                if normalized_reference not in seen:
                    ordered.append((match.start(), reference))
                    seen.add(normalized_reference)

        ordered.sort(key=lambda item: item[0])
        return [reference for _, reference in ordered]

    def _extract_mentions(self, *, text: str, document_number: str | None) -> list[DocumentMention]:
        """Find other documents named in the text and how this one relates to them.

        Each mention's relationship is decided from the words in the same
        clause just before and after it. The context never reaches into a
        neighbouring mention or across a clause boundary, otherwise
        "in supersession of A, and under B" would mark B as superseded too.
        Mentions written as one list ("Nos. A, B and C", or "Notification
        No. A and Circular No. B") share the list's context, so in
        "... A and B are hereby rescinded" both are superseded.
        """

        own_number = normalize_document_number(document_number) if document_number else None
        matches = list(self.mention_pattern.finditer(text))
        groups = self._group_listed_mentions(text, matches)
        best: dict[str, DocumentMention] = {}
        order: list[str] = []

        for group in groups:
            first, last = matches[group[0]], matches[group[-1]]
            previous_end = matches[group[0] - 1].end() if group[0] > 0 else 0
            next_start = matches[group[-1] + 1].start() if group[-1] + 1 < len(matches) else len(text)
            before = text[max(previous_end, first.start() - self.relationship_context_chars):first.start()]
            after = text[last.end():min(next_start, last.end() + self.relationship_context_chars)]
            boundaries = list(self.clause_boundary_pattern.finditer(before))
            if boundaries:
                before = before[boundaries[-1].end():]
            first_boundary = self.clause_boundary_pattern.search(after)
            if first_boundary:
                after = after[:first_boundary.start()]
            # The mention itself ("notification ... No. X") may contain the keyword too.
            context = f"{before} {text[first.start():last.end()]} {after}"
            relationship_type = self._classify_relationship(context)

            for index in group:
                match = matches[index]
                document_type = DocumentType[match.group("type").upper()]
                for raw_number in self.list_separator_pattern.split(match.group("numbers")):
                    number = self._clean_value(raw_number)
                    if not number:
                        continue
                    normalized = normalize_document_number(number)
                    if normalized == own_number:
                        continue
                    mention = DocumentMention(
                        document_number=number,
                        document_type=document_type,
                        relationship_type=relationship_type,
                    )
                    existing = best.get(normalized)
                    if existing is None:
                        best[normalized] = mention
                        order.append(normalized)
                    elif (
                        _RELATIONSHIP_STRENGTH[mention.relationship_type]
                        > _RELATIONSHIP_STRENGTH[existing.relationship_type]
                    ):
                        best[normalized] = mention

        return [best[key] for key in order]

    def _group_listed_mentions(self, text: str, matches: list) -> list[list[int]]:
        """Group consecutive mentions separated only by "," / "and" / "&"."""

        groups: list[list[int]] = []
        for index, match in enumerate(matches):
            if groups and self.mention_group_gap_pattern.match(text[matches[index - 1].end():match.start()]):
                groups[-1].append(index)
            else:
                groups.append([index])
        return groups

    def _classify_relationship(self, context: str) -> RelationshipType:
        for relationship_type, pattern in self.relationship_keyword_patterns:
            if pattern.search(context):
                return relationship_type
        return RelationshipType.REFERENCES

    def _parse_date(self, value: str) -> date | None:
        for date_format in self.date_formats:
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        return None

    def _confidence_score(
        self,
        *,
        document_number: str | None,
        document_type: DocumentType | None,
        issue_date: date | None,
        subject: str | None,
        department: str | None,
    ) -> float:
        extracted_fields = [
            document_number is not None,
            document_type is not None,
            issue_date is not None,
            subject is not None,
            department is not None,
        ]
        return sum(extracted_fields) / len(extracted_fields)

    def _is_current_document_reference(
        self,
        reference: str,
        document_number: str | None,
        document_type: DocumentType | None,
    ) -> bool:
        if document_number is None or document_type is None or document_type == DocumentType.UNKNOWN:
            return False

        return reference.casefold().startswith(document_type.value.casefold()) and document_number.casefold() in reference.casefold()

    def _compile_many(self, patterns: tuple[str, ...], *, flags: int = re.IGNORECASE) -> list[Pattern[str]]:
        return [re.compile(pattern, flags) for pattern in patterns]

    def _clean_value(self, value: str) -> str:
        return " ".join(value.strip(" \t\r\n.;,").split())


class LLMMetadataExtractor(MetadataExtractionStrategy):
    """Ask an LLM for metadata, keeping only values that can be verified in the text.

    The model reads the first part of the document and returns JSON. Each
    value is then checked: the document number must appear verbatim, the
    date must parse and its year must appear, the subject must be made of
    words from the document, and the type must be a known type. Anything
    that fails a check is dropped, so the model cannot invent metadata.
    """

    PROMPT = """Extract metadata from the start of this government document.
Return a JSON object with exactly these keys:
"document_number": the number after "No." identifying THIS document (not ones it mentions), or null
"document_type": one of NOTIFICATION, CIRCULAR, ORDER, GAZETTE, POLICY, ADVISORY, REPORT, or null
"issue_date": the date this document was issued as YYYY-MM-DD, or null
"subject": the subject or title in at most 25 words, copied from the text, or null
"department": the issuing ministry or department, copied from the text, or null
Use null when the text does not state the value. Do not guess.

Document start:
\"\"\"
{text}
\"\"\"
"""
    HEAD_CHARS = 2500

    def __init__(self, llm_client=None) -> None:
        self.llm_client = llm_client

    def extract(self, raw_document: RawDocument) -> DocumentMetadata:
        if self.llm_client is None:
            raise NotImplementedError("LLM metadata extraction is not configured.")
        head = raw_document.raw_text[: self.HEAD_CHARS]
        answer = self.llm_client.generate_json(self.PROMPT.format(text=head))
        return self.validate(answer, raw_document.raw_text)

    @classmethod
    def validate(cls, answer: dict, text: str) -> DocumentMetadata:
        folded = " ".join(text.split()).casefold()
        words = set(re.findall(r"[a-z0-9]+", folded))

        def as_text(key: str, max_len: int) -> str | None:
            value = answer.get(key)
            if not isinstance(value, str):
                return None
            value = " ".join(value.split()).strip(" .;,")
            return value if 0 < len(value) <= max_len else None

        def from_text(value: str | None, min_overlap: float) -> str | None:
            if value is None:
                return None
            tokens = re.findall(r"[a-z0-9]+", value.casefold())
            if not tokens:
                return None
            return value if sum(t in words for t in tokens) / len(tokens) >= min_overlap else None

        number = as_text("document_number", 128)
        if number is not None and normalize_document_number(number) not in folded.replace(" ", ""):
            number = None

        issue_date = None
        raw_date = as_text("issue_date", 10)
        if raw_date is not None:
            try:
                parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
                if 1900 <= parsed.year <= date.today().year + 1 and str(parsed.year) in folded:
                    issue_date = parsed
            except ValueError:
                pass

        document_type = None
        raw_type = as_text("document_type", 32)
        if raw_type is not None and raw_type.upper() in DocumentType.__members__ and raw_type.upper() != "UNKNOWN":
            document_type = DocumentType[raw_type.upper()]

        return DocumentMetadata(
            document_number=number,
            document_type=document_type,
            issue_date=issue_date,
            subject=from_text(as_text("subject", 300), 0.8),
            department=from_text(as_text("department", 256), 0.9),
            confidence_score=0.5,
        )


class FallbackMetadataExtractor(MetadataExtractionStrategy):
    """Run the rule-based extractor, and ask the LLM only for fields it missed.

    LLM failures never fail ingestion: the rule-based result is kept.
    """

    FILLABLE = ("document_number", "document_type", "issue_date", "subject", "department")

    def __init__(self, primary: MetadataExtractionStrategy, fallback: MetadataExtractionStrategy | None) -> None:
        self.primary = primary
        self.fallback = fallback

    def extract(self, raw_document: RawDocument) -> DocumentMetadata:
        metadata = self.primary.extract(raw_document)
        missing = [name for name in self.FILLABLE if getattr(metadata, name) in (None, "", DocumentType.UNKNOWN)]
        if not missing or self.fallback is None:
            return metadata
        try:
            suggested = self.fallback.extract(raw_document)
        except Exception as exc:
            logger.warning("LLM metadata fallback failed; keeping rule-based metadata: %s", exc)
            return metadata
        filled = {name: getattr(suggested, name) for name in missing if getattr(suggested, name) is not None}
        if filled:
            logger.info("LLM metadata fallback filled %s", ", ".join(sorted(filled)))
        return metadata.model_copy(update=filled)
