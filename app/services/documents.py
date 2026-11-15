"""Document management: list, inspect, delete, link, and reconcile stores."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.chunking.tokens import TextTokenizer
from app.metadata.normalization import normalize_document_number
from app.models.documents import Document, DocumentChunk, DocumentReference, DocumentRelationship
from app.models.enums import DocumentStatus, DocumentType, RelationshipOrigin, RelationshipType
from app.schemas.documents import DocumentRead, DocumentRelationshipRead
from app.schemas.processing import PageContent
from app.services.exceptions import AmbiguousDocumentError, DocumentNotFoundError, SourceUnavailableError
from app.services.schemas import IngestionResult
from app.supersession.linker import DocumentRelationshipLinker, normalized_number_column
from app.vectorstore.interfaces import EmbeddingProvider, VectorStore
from app.vectorstore.windows import build_embedded_chunks

logger = logging.getLogger(__name__)


class DocumentSummary(DocumentRead):
    chunk_count: int = 0


class RelatedDocument(BaseModel):
    relationship_id: uuid.UUID
    relationship_type: RelationshipType
    origin: RelationshipOrigin
    document_id: uuid.UUID
    document_number: str
    document_type: DocumentType
    status: DocumentStatus


class PendingReference(BaseModel):
    referenced_number: str
    relationship_type: RelationshipType


class DocumentDetail(DocumentSummary):
    page_count: int = 0
    # Edges where this document is the source ("this supersedes X").
    outgoing: list[RelatedDocument] = Field(default_factory=list)
    # Edges where this document is the target ("X supersedes this").
    incoming: list[RelatedDocument] = Field(default_factory=list)
    pending_references: list[PendingReference] = Field(default_factory=list)


class DocumentPage(BaseModel):
    items: list[DocumentSummary]
    total: int
    limit: int
    offset: int


class ReconcileReport(BaseModel):
    # Vectors whose document no longer exists in PostgreSQL (removed).
    orphaned_vector_documents_removed: list[str] = Field(default_factory=list)
    # Documents that had chunks in PostgreSQL but no vectors in Qdrant.
    documents_missing_vectors: list[uuid.UUID] = Field(default_factory=list)
    # Of those, documents whose vectors were rebuilt from the stored chunk text.
    documents_repaired: list[uuid.UUID] = Field(default_factory=list)


class DocumentService:
    def __init__(
        self,
        session: Session,
        vector_store: VectorStore,
        linker: DocumentRelationshipLinker | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        tokenizer: TextTokenizer | None = None,
    ) -> None:
        self.session = session
        self.vector_store = vector_store
        self.linker = linker or DocumentRelationshipLinker(session)
        self.embedding_provider = embedding_provider
        self.tokenizer = tokenizer

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        document_type: DocumentType | None = None,
        status: DocumentStatus | None = None,
        search: str | None = None,
    ) -> DocumentPage:
        filters = []
        if document_type is not None:
            filters.append(Document.document_type == document_type)
        if status is not None:
            filters.append(Document.status == status)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Document.document_number.ilike(pattern),
                    Document.title.ilike(pattern),
                    Document.subject.ilike(pattern),
                    Document.department.ilike(pattern),
                )
            )

        total = self.session.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
        chunk_counts = (
            select(DocumentChunk.document_id, func.count().label("chunk_count"))
            .group_by(DocumentChunk.document_id)
            .subquery()
        )
        rows = self.session.execute(
            select(Document, func.coalesce(chunk_counts.c.chunk_count, 0))
            .outerjoin(chunk_counts, chunk_counts.c.document_id == Document.id)
            .where(*filters)
            .order_by(Document.created_at.desc(), Document.id)
            .limit(limit)
            .offset(offset)
        ).all()
        items = [self._summary(document, count) for document, count in rows]
        return DocumentPage(items=items, total=total, limit=limit, offset=offset)

    def get(self, document_id: uuid.UUID) -> DocumentDetail:
        document = self._require(document_id)
        chunk_count, page_count = self.session.execute(
            select(func.count(), func.count(func.distinct(DocumentChunk.page_number))).where(
                DocumentChunk.document_id == document_id
            )
        ).one()
        pending = self.session.scalars(
            select(DocumentReference).where(
                DocumentReference.source_document_id == document_id,
                DocumentReference.resolved_document_id.is_(None),
            )
        ).all()
        return DocumentDetail(
            **self._summary(document, chunk_count).model_dump(),
            page_count=page_count,
            outgoing=[
                self._related(rel, rel.target_document) for rel in document.outgoing_relationships
            ],
            incoming=[
                self._related(rel, rel.source_document) for rel in document.incoming_relationships
            ],
            pending_references=[
                PendingReference(referenced_number=ref.referenced_number_raw, relationship_type=ref.relationship_type)
                for ref in pending
            ],
        )

    def resolve(self, reference: str) -> Document:
        """Find a document by id or by document number."""

        try:
            return self._require(uuid.UUID(reference))
        except ValueError:
            pass
        matches = self.session.scalars(
            select(Document).where(normalized_number_column() == normalize_document_number(reference))
        ).all()
        if not matches:
            raise DocumentNotFoundError(f"No document with id or number {reference!r}")
        if len(matches) > 1:
            raise AmbiguousDocumentError(reference, [m.id for m in matches])
        return matches[0]

    def load_pages(self, document_id: uuid.UUID) -> list[PageContent]:
        """Rebuild page text from stored chunks, in reading order."""

        chunks = self.session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.page_number, DocumentChunk.chunk_index)
        ).all()
        pages: dict[int, list[str]] = {}
        for chunk in chunks:
            pages.setdefault(chunk.page_number, []).append(chunk.chunk_text)
        return [PageContent(page_number=page, text="\n".join(texts)) for page, texts in pages.items()]

    def source_file(self, document_id: uuid.UUID, allowed_dirs: list[str]) -> str | None:
        """Path of the original PDF, only if it still exists inside one of ``allowed_dirs``."""

        source = self._require(document_id).source_url
        if not source:
            return None
        resolved = Path(source).resolve()
        if not resolved.is_file():
            return None
        for allowed in allowed_dirs:
            root = Path(allowed).resolve()
            if root in resolved.parents:
                return str(resolved)
        return None

    def page_text(self, document_id: uuid.UUID, page_number: int) -> PageContent:
        self._require(document_id)
        pages = {page.page_number: page for page in self.load_pages(document_id)}
        if page_number not in pages:
            raise DocumentNotFoundError(f"Document {document_id} has no stored text for page {page_number}")
        return pages[page_number]

    def delete(self, document_id: uuid.UUID) -> list[uuid.UUID]:
        """Delete a document from both stores; returns documents whose status was restored."""

        document = self._require(document_id)
        superseded_ids = [
            rel.target_document_id
            for rel in document.outgoing_relationships
            if rel.relationship_type == RelationshipType.SUPERSEDES
        ]
        try:
            self.session.delete(document)
            self.session.flush()
            # Documents this one superseded may be the latest version again.
            for target_id in superseded_ids:
                self.linker.recompute_status(target_id)
            self.vector_store.delete_document(document_id)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        logger.info("Deleted document %s", document_id)
        return superseded_ids

    def reingest(self, document_id: uuid.UUID, ingestion_service) -> IngestionResult:
        """Re-run ingestion from the stored source file without risking the document.

        The old record stays until the new one is fully stored: its file hash
        is parked so the duplicate check lets the same file through, and is
        restored if re-ingestion fails. On success the old record is deleted,
        references to it are re-resolved to the new one, and manually added
        relationships are carried over.
        """

        old = self._require(document_id)
        source = old.source_url
        if not source or not Path(source).is_file():
            raise SourceUnavailableError("The source file for this document is no longer available")

        manual_links = [
            (rel.relationship_type, "outgoing", rel.target_document_id)
            for rel in old.outgoing_relationships
            if rel.origin == RelationshipOrigin.MANUAL
        ] + [
            (rel.relationship_type, "incoming", rel.source_document_id)
            for rel in old.incoming_relationships
            if rel.origin == RelationshipOrigin.MANUAL
        ]
        original_hash, file_name = old.file_hash, old.file_name
        old.file_hash = f"reingest-{old.id}"
        self.session.commit()

        try:
            result = ingestion_service.ingest(source, original_filename=file_name)
        except Exception:
            self.session.rollback()
            old = self.session.get(Document, document_id)
            if old is not None:
                old.file_hash = original_hash
                self.session.commit()
            raise

        self.delete(document_id)
        new = self._require(result.document_id)
        self.linker.resolve_incoming(new)
        for relationship_type, direction, other_id in manual_links:
            if self.session.get(Document, other_id) is None:
                continue
            source_id, target_id = (new.id, other_id) if direction == "outgoing" else (other_id, new.id)
            self._ensure_relationship(source_id, target_id, relationship_type, RelationshipOrigin.MANUAL)
        self.linker.recompute_status(new.id)
        self.session.commit()
        self.session.refresh(new)
        logger.info("Re-ingested %s as %s (%s manual links kept)", document_id, new.id, len(manual_links))
        return result.model_copy(update={"status": new.status})

    def _ensure_relationship(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        relationship_type: RelationshipType,
        origin: RelationshipOrigin,
    ) -> DocumentRelationship:
        existing = self.session.scalars(
            select(DocumentRelationship).where(
                DocumentRelationship.source_document_id == source_id,
                DocumentRelationship.target_document_id == target_id,
                DocumentRelationship.relationship_type == relationship_type,
            )
        ).first()
        if existing is not None:
            if origin == RelationshipOrigin.MANUAL:
                existing.origin = origin
            return existing
        relationship = DocumentRelationship(
            source_document_id=source_id,
            target_document_id=target_id,
            relationship_type=relationship_type,
            origin=origin,
        )
        self.session.add(relationship)
        self.session.flush()
        if relationship_type == RelationshipType.SUPERSEDES:
            self.linker.recompute_status(target_id)
        return relationship

    def add_relationship(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        relationship_type: RelationshipType,
    ) -> DocumentRelationshipRead:
        if source_id == target_id:
            raise ValueError("A document cannot be related to itself")
        self._require(source_id)
        self._require(target_id)
        existing = self._ensure_relationship(source_id, target_id, relationship_type, RelationshipOrigin.MANUAL)
        self.session.commit()
        self.session.refresh(existing)
        return DocumentRelationshipRead.model_validate(existing)

    def delete_relationship(self, relationship_id: uuid.UUID) -> None:
        relationship = self.session.get(DocumentRelationship, relationship_id)
        if relationship is None:
            raise DocumentNotFoundError(f"No relationship {relationship_id}")
        target_id = relationship.target_document_id
        self.session.delete(relationship)
        self.session.flush()
        self.linker.recompute_status(target_id)
        self.session.commit()

    def reconcile(self) -> ReconcileReport:
        """Repair drift between PostgreSQL and Qdrant."""

        report = ReconcileReport()
        vector_ids = self.vector_store.list_document_ids()
        db_ids = {str(i) for i in self.session.scalars(select(Document.id)).all()}

        for orphan in sorted(vector_ids - db_ids):
            self.vector_store.delete_document(orphan)
            report.orphaned_vector_documents_removed.append(orphan)

        with_chunks = self.session.scalars(select(DocumentChunk.document_id).distinct()).all()
        report.documents_missing_vectors = [i for i in with_chunks if str(i) not in vector_ids]
        if self.embedding_provider is not None:
            for document_id in report.documents_missing_vectors:
                try:
                    self._rebuild_vectors(document_id)
                    report.documents_repaired.append(document_id)
                except Exception:
                    logger.exception("Could not rebuild vectors for %s", document_id)
        logger.info(
            "Reconcile: removed %s orphaned vector sets, %s documents missing vectors, %s repaired",
            len(report.orphaned_vector_documents_removed),
            len(report.documents_missing_vectors),
            len(report.documents_repaired),
        )
        return report

    def _rebuild_vectors(self, document_id: uuid.UUID) -> None:
        """Re-embed a document's stored chunks; the source file is not needed."""

        document = self._require(document_id)
        chunks = self.session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.page_number, DocumentChunk.chunk_index)
        ).all()
        self.vector_store.upsert(
            build_embedded_chunks(
                document_id=document.id,
                document_number=document.document_number,
                document_type=document.document_type,
                chunks=chunks,
                embedding_provider=self.embedding_provider,
                tokenizer=self.tokenizer,
                title=document.title,
                file_name=document.file_name,
                department=document.department,
                subject=document.subject,
                issue_date=document.issue_date,
            )
        )

    def _require(self, document_id: uuid.UUID) -> Document:
        document = self.session.get(Document, document_id)
        if document is None:
            raise DocumentNotFoundError(f"No document {document_id}")
        return document

    @staticmethod
    def _summary(document: Document, chunk_count: int) -> DocumentSummary:
        return DocumentSummary(**DocumentRead.model_validate(document).model_dump(), chunk_count=chunk_count)

    @staticmethod
    def _related(relationship: DocumentRelationship, other: Document) -> RelatedDocument:
        return RelatedDocument(
            relationship_id=relationship.id,
            relationship_type=relationship.relationship_type,
            origin=relationship.origin,
            document_id=other.id,
            document_number=other.document_number,
            document_type=other.document_type,
            status=other.status,
        )
