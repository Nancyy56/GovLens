"""Metadata extraction strategies."""

from __future__ import annotations

import re
from datetime import date, datetime
from re import Pattern

from app.metadata.interfaces import MetadataExtractionStrategy
from app.metadata.patterns import (
    DATE_FORMATS,
    DATE_PATTERNS,
    DEPARTMENT_PATTERNS,
    DOCUMENT_NUMBER_PATTERNS,
    REFERENCE_PATTERNS,
    SUBJECT_PATTERNS,
)
from app.models.enums import DocumentType
from app.schemas.processing import DocumentMetadata, RawDocument


class RuleBasedMetadataExtractor(MetadataExtractionStrategy):
    """Extract metadata using deterministic, configurable text patterns.

    This strategy performs no OCR, classification, LLM calls, retrieval,
    embeddings, supersession detection, or fallback orchestration. It only
    reads text already present on `RawDocument` and maps explicit textual
    matches into `DocumentMetadata`.
    """

    def __init__(
        self,
        document_number_patterns: tuple[tuple[str, str], ...] = DOCUMENT_NUMBER_PATTERNS,
        date_patterns: tuple[str, ...] = DATE_PATTERNS,
        subject_patterns: tuple[str, ...] = SUBJECT_PATTERNS,
        department_patterns: tuple[str, ...] = DEPARTMENT_PATTERNS,
        reference_patterns: tuple[str, ...] = REFERENCE_PATTERNS,
        date_formats: tuple[str, ...] = DATE_FORMATS,
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

        return DocumentMetadata(
            document_number=document_number,
            document_type=document_type,
            issue_date=issue_date,
            department=department,
            subject=subject,
            referenced_documents=referenced_documents,
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
    """Placeholder for a future LLM-backed metadata extractor."""

    def extract(self, raw_document: RawDocument) -> DocumentMetadata:
        """Raise until LLM metadata extraction is intentionally implemented."""

        raise NotImplementedError("LLM metadata extraction is not implemented.")
