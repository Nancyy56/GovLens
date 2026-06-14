"""Metadata validation components."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.metadata.interfaces import MetadataValidator
from app.models.enums import DocumentType
from app.schemas.processing import DocumentMetadata, MetadataValidationResult


class CriticalFieldMetadataValidator(MetadataValidator):
    """Validate metadata for fields required before storage.

    The validator checks only presence of critical fields. It does not extract,
    infer, normalize, classify, or repair metadata values.
    """

    critical_fields = ("document_type", "document_number", "issue_date")

    def validate(self, metadata: DocumentMetadata) -> MetadataValidationResult:
        """Return missing critical fields and associated warnings."""

        missing_fields: list[str] = []

        if self._is_missing_document_type(getattr(metadata, "document_type", None)):
            missing_fields.append("document_type")

        if self._is_missing_string(getattr(metadata, "document_number", None)):
            missing_fields.append("document_number")

        if self._is_missing_date(getattr(metadata, "issue_date", None)):
            missing_fields.append("issue_date")

        warnings = [f"Missing critical metadata field: {field_name}" for field_name in missing_fields]
        return MetadataValidationResult(
            is_valid=not missing_fields,
            missing_fields=missing_fields,
            warnings=warnings,
        )

    def _is_missing_document_type(self, value: Any) -> bool:
        return value is None or value == DocumentType.UNKNOWN

    def _is_missing_string(self, value: Any) -> bool:
        return not isinstance(value, str) or not value.strip()

    def _is_missing_date(self, value: Any) -> bool:
        return not isinstance(value, date)
