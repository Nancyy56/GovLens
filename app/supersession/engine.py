"""Database-backed supersession analysis engine."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.documents import Document, DocumentRelationship
from app.models.enums import RelationshipType
from app.repositories.documents import DocumentRepository, DocumentRelationshipRepository
from app.supersession.interfaces import SupersessionEngine
from app.supersession.schemas import DocumentReference, SupersessionResult


class DatabaseSupersessionEngine(SupersessionEngine):
    """Resolve document supersession lineage using the relational graph.

    Traverses incoming SUPERSEDES edges to rebuild the full supersession
    chain for a target document. Cycles are detected and truncated by
    tracking visited node ids.
    """

    def __init__(
        self,
        session: Session,
        document_repository: DocumentRepository | None = None,
        relationship_repository: DocumentRelationshipRepository | None = None,
    ) -> None:
        self.session = session
        self.document_repository = document_repository or DocumentRepository(session)
        self.relationship_repository = relationship_repository or DocumentRelationshipRepository(
            session
        )

    def check_document(self, document_id: uuid.UUID) -> SupersessionResult:
        document = self.document_repository.get(document_id)
        if document is None:
            return SupersessionResult(
                document_id=document_id,
                status=None,
                is_superseded=False,
                latest_document_id=document_id,
                latest_document_number=None,
                superseded_by_document_id=None,
                superseded_by_document_number=None,
                supersession_chain=[],
            )

        chain = self._build_chain(document_id)
        latest = chain[-1]
        is_superseded = len(chain) > 1

        superseded_by = None
        if is_superseded and len(chain) >= 2:
            superseded_by = chain[1]

        return SupersessionResult(
            document_id=document_id,
            document_number=document.document_number,
            status=document.status,
            is_superseded=is_superseded,
            latest_document_id=latest.document_id,
            latest_document_number=latest.document_number,
            superseded_by_document_id=superseded_by.document_id if superseded_by else None,
            superseded_by_document_number=superseded_by.document_number if superseded_by else None,
            supersession_chain=chain,
        )

    def _build_chain(self, start_document_id: uuid.UUID) -> Sequence[DocumentReference]:
        visited: set[uuid.UUID] = set()
        chain: list[DocumentReference] = []

        current_id = start_document_id
        while current_id is not None:
            if current_id in visited:
                break
            visited.add(current_id)

            document = self.document_repository.get(current_id)
            if document is None:
                break

            chain.append(
                DocumentReference(
                    document_id=document.id,
                    document_number=document.document_number,
                )
            )

            current_id = self._find_superseding_document_id(current_id)

        return chain

    def _find_superseding_document_id(self, document_id: uuid.UUID) -> uuid.UUID | None:
        statement = (
            select(DocumentRelationship.source_document_id)
            .where(
                DocumentRelationship.target_document_id == document_id,
                DocumentRelationship.relationship_type == RelationshipType.SUPERSEDES,
            )
            .limit(1)
        )
        result = self.session.execute(statement).scalar_one_or_none()
        return result
