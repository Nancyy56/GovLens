"""Compare two stored documents and summarize what changed."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.comparison.differ import ChangeType, DocumentDiffer, TextChange
from app.generation.interfaces import LLMClient
from app.models.documents import Document, DocumentRelationship
from app.models.enums import DocumentStatus, DocumentType, RelationshipType
from app.services.documents import DocumentService

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]+")
NO_DIFFERENCES_TEXT = "No textual differences were found between the two documents."


class ComparedDocument(BaseModel):
    document_id: uuid.UUID
    document_number: str
    document_type: DocumentType
    title: str
    issue_date: date | None
    status: DocumentStatus


class ComparisonResult(BaseModel):
    base: ComparedDocument
    target: ComparedDocument
    # Stored relationship between the two, e.g. "target SUPERSEDES base".
    relationship: str | None = None
    summary_markdown: str | None = None
    total_changes: int
    added: int
    removed: int
    modified: int
    unchanged_sentences: int
    changes: list[TextChange] = Field(default_factory=list)
    changes_truncated: bool = False


class ComparisonService:
    """Diff two documents sentence by sentence, then have the LLM explain the diff.

    The diff itself is deterministic. The LLM only sees the detected changes
    (not the full documents) and must cite page numbers from them, so its
    summary cannot describe differences that the diff did not find.
    """

    def __init__(
        self,
        session: Session,
        document_service: DocumentService,
        llm_client: LLMClient | None,
        differ: DocumentDiffer | None = None,
        max_changes_in_prompt: int = 40,
        max_changes_returned: int = 200,
    ) -> None:
        self.session = session
        self.document_service = document_service
        self.llm_client = llm_client
        self.differ = differ or DocumentDiffer()
        self.max_changes_in_prompt = max_changes_in_prompt
        self.max_changes_returned = max_changes_returned

    def compare(
        self,
        base_reference: str,
        target_reference: str,
        focus: str | None = None,
        summarize: bool = True,
    ) -> ComparisonResult:
        base = self.document_service.resolve(base_reference)
        target = self.document_service.resolve(target_reference)
        if base.id == target.id:
            raise ValueError("Choose two different documents to compare")

        diff = self.differ.diff(
            self.document_service.load_pages(base.id),
            self.document_service.load_pages(target.id),
        )
        changes = self._prioritize(diff.changes, focus)
        relationship = self._relationship(base, target)

        summary = None
        if summarize and self.llm_client is not None:
            summary = (
                self.llm_client.generate(self._prompt(base, target, changes, relationship, focus))
                if changes
                else NO_DIFFERENCES_TEXT
            )

        counts = {change_type: 0 for change_type in ChangeType}
        for change in diff.changes:
            counts[change.change_type] += 1

        return ComparisonResult(
            base=self._describe(base),
            target=self._describe(target),
            relationship=relationship,
            summary_markdown=summary,
            total_changes=len(diff.changes),
            added=counts[ChangeType.ADDED],
            removed=counts[ChangeType.REMOVED],
            modified=counts[ChangeType.MODIFIED],
            unchanged_sentences=diff.unchanged_sentence_count,
            changes=changes[: self.max_changes_returned],
            changes_truncated=len(changes) > self.max_changes_returned,
        )

    @staticmethod
    def _prioritize(changes: list[TextChange], focus: str | None) -> list[TextChange]:
        """With a focus, put changes mentioning its terms first (otherwise keep document order)."""

        if not focus:
            return list(changes)
        terms = set(_TOKEN.findall(focus.lower()))

        def overlap(change: TextChange) -> int:
            text = f"{change.base_text or ''} {change.target_text or ''}".lower()
            return len(terms & set(_TOKEN.findall(text)))

        return sorted(changes, key=overlap, reverse=True)

    def _relationship(self, base: Document, target: Document) -> str | None:
        edges = self.session.scalars(
            select(DocumentRelationship).where(
                or_(
                    (DocumentRelationship.source_document_id == base.id)
                    & (DocumentRelationship.target_document_id == target.id),
                    (DocumentRelationship.source_document_id == target.id)
                    & (DocumentRelationship.target_document_id == base.id),
                )
            )
        ).all()
        if not edges:
            return None
        # Report the strongest link.
        order = [RelationshipType.SUPERSEDES, RelationshipType.AMENDS, RelationshipType.REFERENCES]
        edge = min(edges, key=lambda e: order.index(e.relationship_type))
        source = "base" if edge.source_document_id == base.id else "target"
        other = "target" if source == "base" else "base"
        return f"{source} {edge.relationship_type.value} {other}"

    def _prompt(
        self,
        base: Document,
        target: Document,
        changes: list[TextChange],
        relationship: str | None,
        focus: str | None,
    ) -> str:
        base_label = self._label(base)
        target_label = self._label(target)
        lines = [
            "You are comparing two government documents.",
            "",
            "STRICT RULES:",
            "1. Describe ONLY the differences listed under Detected Changes. Do not use outside knowledge.",
            "2. Group related changes and explain what changed in plain language (rates, dates, scope, obligations, deadlines).",
            f"3. Cite pages as [Base p.N] for {base_label} and [Target p.N] for {target_label}.",
            "4. If a change is only formatting or wording with no change in meaning, say so briefly.",
            "5. Keep it concise. Use a short bulleted list.",
            "",
            f"Base document: {base_label}",
            f"Target document: {target_label}",
        ]
        if relationship:
            lines.append(f"Stored relationship: {relationship}.")
        if focus:
            lines.append(f"Focus the summary on: {focus}")

        shown = changes[: self.max_changes_in_prompt]
        lines += ["", f"# Detected Changes ({len(shown)} of {len(changes)})"]
        for index, change in enumerate(shown, start=1):
            if change.change_type == ChangeType.MODIFIED:
                lines.append(
                    f"{index}. MODIFIED\n   Base p.{change.base_page}: {change.base_text}\n"
                    f"   Target p.{change.target_page}: {change.target_text}"
                )
            elif change.change_type == ChangeType.REMOVED:
                lines.append(f"{index}. REMOVED from base p.{change.base_page}: {change.base_text}")
            else:
                lines.append(f"{index}. ADDED in target p.{change.target_page}: {change.target_text}")
        return "\n".join(lines)

    @staticmethod
    def _label(document: Document) -> str:
        number = document.document_number or document.file_name
        dated = f", dated {document.issue_date.isoformat()}" if document.issue_date else ""
        return f"{document.document_type.value.title()} No. {number}{dated}"

    @staticmethod
    def _describe(document: Document) -> ComparedDocument:
        return ComparedDocument(
            document_id=document.id,
            document_number=document.document_number,
            document_type=document.document_type,
            title=document.title,
            issue_date=document.issue_date,
            status=document.status,
        )
