"""Persist document-to-document links detected during ingestion."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.metadata.normalization import normalize_document_number
from app.models.documents import Document, DocumentReference, DocumentRelationship
from app.models.enums import DocumentStatus, DocumentType, RelationshipType
from app.schemas.processing import DocumentMention

logger = logging.getLogger(__name__)


class CreatedLink(BaseModel):
    """A relationship edge created while linking a document."""

    source_document_id: uuid.UUID
    source_document_number: str
    target_document_id: uuid.UUID
    target_document_number: str
    relationship_type: RelationshipType


class LinkReport(BaseModel):
    """Outcome of linking one document into the relationship graph."""

    created: list[CreatedLink] = []
    # Mentions whose target document has not been ingested yet.
    pending_references: list[str] = []


def normalized_number_column():
    """SQL expression matching ``normalize_document_number`` closely enough for lookups."""

    return func.lower(func.replace(Document.document_number, " ", ""))


class DocumentRelationshipLinker:
    """Turn detected mentions into ``DocumentRelationship`` edges.

    Mentions are stored as ``DocumentReference`` rows first so a reference to
    a document that has not been ingested yet is resolved automatically when
    that document arrives. A ``SUPERSEDES`` edge marks its target SUPERSEDED.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def link_new_document(self, document: Document, mentions: Sequence[DocumentMention]) -> LinkReport:
        report = LinkReport()
        self._record_outgoing(document, mentions, report)
        self._resolve_incoming(document, report)
        self.session.flush()
        return report

    def resolve_incoming(self, document: Document) -> LinkReport:
        """Resolve pending references to this document (e.g. after a re-ingest)."""

        report = LinkReport()
        self._resolve_incoming(document, report)
        self.session.flush()
        return report

    def recompute_status(self, document_id: uuid.UUID) -> None:
        """Set a document ACTIVE or SUPERSEDED based on its incoming SUPERSEDES edges."""

        document = self.session.get(Document, document_id)
        if document is None or document.status == DocumentStatus.ARCHIVED:
            return
        superseded = self.session.execute(
            select(DocumentRelationship.id)
            .where(
                DocumentRelationship.target_document_id == document_id,
                DocumentRelationship.relationship_type == RelationshipType.SUPERSEDES,
            )
            .limit(1)
        ).first() is not None
        document.status = DocumentStatus.SUPERSEDED if superseded else DocumentStatus.ACTIVE

    def _record_outgoing(self, document: Document, mentions: Sequence[DocumentMention], report: LinkReport) -> None:
        for mention in mentions:
            normalized = normalize_document_number(mention.document_number)
            if not normalized:
                continue
            target = self._find_document(normalized, mention.document_type, exclude_id=document.id)
            reference = DocumentReference(
                source_document_id=document.id,
                referenced_number=normalized,
                referenced_number_raw=mention.document_number[:128],
                referenced_type=mention.document_type,
                relationship_type=mention.relationship_type,
                resolved_document_id=target.id if target else None,
            )
            self.session.add(reference)
            if target is None:
                report.pending_references.append(mention.document_number)
                continue
            self._add_edge(document, target, mention.relationship_type, report)

    def _resolve_incoming(self, document: Document, report: LinkReport) -> None:
        """Resolve references other documents made to this one before it existed."""

        if not document.document_number:
            return
        normalized = normalize_document_number(document.document_number)
        pending = self.session.scalars(
            select(DocumentReference).where(
                DocumentReference.referenced_number == normalized,
                DocumentReference.resolved_document_id.is_(None),
                DocumentReference.source_document_id != document.id,
            )
        ).all()
        for reference in pending:
            if not self._type_compatible(reference.referenced_type, document.document_type):
                continue
            source = self.session.get(Document, reference.source_document_id)
            if source is None:
                continue
            reference.resolved_document_id = document.id
            self._add_edge(source, document, reference.relationship_type, report)

    def _add_edge(
        self,
        source: Document,
        target: Document,
        relationship_type: RelationshipType,
        report: LinkReport,
    ) -> None:
        exists = self.session.execute(
            select(DocumentRelationship.id).where(
                DocumentRelationship.source_document_id == source.id,
                DocumentRelationship.target_document_id == target.id,
                DocumentRelationship.relationship_type == relationship_type,
            )
        ).first()
        if exists:
            return
        self.session.add(
            DocumentRelationship(
                source_document_id=source.id,
                target_document_id=target.id,
                relationship_type=relationship_type,
            )
        )
        # Flush so the duplicate check above sees this edge on later iterations.
        self.session.flush()
        if relationship_type == RelationshipType.SUPERSEDES and target.status != DocumentStatus.ARCHIVED:
            target.status = DocumentStatus.SUPERSEDED
        report.created.append(
            CreatedLink(
                source_document_id=source.id,
                source_document_number=source.document_number,
                target_document_id=target.id,
                target_document_number=target.document_number,
                relationship_type=relationship_type,
            )
        )
        logger.info(
            "Linked %s %s %s",
            source.document_number or source.id,
            relationship_type.value,
            target.document_number or target.id,
        )

    def _find_document(
        self,
        normalized_number: str,
        document_type: DocumentType | None,
        exclude_id: uuid.UUID,
    ) -> Document | None:
        candidates = self.session.scalars(
            select(Document).where(
                normalized_number_column() == normalized_number,
                Document.id != exclude_id,
            )
        ).all()
        compatible = [c for c in candidates if self._type_compatible(document_type, c.document_type)]
        if not compatible:
            return None
        # Prefer an exact type match, then the most recently issued document.
        compatible.sort(
            key=lambda c: (
                c.document_type == document_type,
                c.issue_date.toordinal() if c.issue_date else 0,
            ),
            reverse=True,
        )
        return compatible[0]

    @staticmethod
    def _type_compatible(referenced_type: DocumentType | None, actual_type: DocumentType | None) -> bool:
        if referenced_type is None or actual_type in (None, DocumentType.UNKNOWN):
            return True
        return referenced_type == actual_type
