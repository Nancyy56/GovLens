"""Document ingestion orchestration service."""

from __future__ import annotations

import hashlib
import uuid
import logging
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from app.chunking.interfaces import DocumentChunker
from app.chunking.tokens import TextTokenizer
from app.core import metrics
from app.classification.interfaces import DocumentClassifier
from app.ingestion.contracts import DocumentLoader
from app.metadata.interfaces import MetadataExtractionStrategy
from app.models.enums import DocumentStatus
from app.repositories.documents import DocumentChunkRepository, DocumentRepository
from app.schemas.documents import DocumentChunkCreate, DocumentCreate
from app.schemas.processing import DocumentClassificationResult, DocumentMetadata, RawDocument
from app.services.exceptions import DuplicateDocumentError
from app.services.schemas import IngestionResult
from app.supersession.linker import DocumentRelationshipLinker, LinkReport
from app.vectorstore.interfaces import EmbeddingProvider, VectorStore
from app.vectorstore.windows import build_embedded_chunks

logger = logging.getLogger(__name__)


class DocumentIngestionService:
    """Load, analyse, chunk, embed, and store one document.

    PostgreSQL and Qdrant are written as one unit: rows are flushed, vectors
    are upserted, then the transaction commits. If anything fails after the
    vectors were written, they are deleted again so the two stores never
    disagree about which documents exist.
    """

    def __init__(
        self,
        loader: DocumentLoader,
        metadata_extractor: MetadataExtractionStrategy,
        classifier: DocumentClassifier,
        chunker: DocumentChunker,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        document_repository: DocumentRepository,
        document_chunk_repository: DocumentChunkRepository,
        relationship_linker: DocumentRelationshipLinker | None = None,
        tokenizer: TextTokenizer | None = None,
    ) -> None:
        self.loader = loader
        self.metadata_extractor = metadata_extractor
        self.classifier = classifier
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.document_repository = document_repository
        self.document_chunk_repository = document_chunk_repository
        self.relationship_linker = relationship_linker
        self.tokenizer = tokenizer

    def ingest(self, file_path: str, original_filename: str | None = None) -> IngestionResult:
        logger.info("Starting ingestion for %s", file_path)
        document = None
        file_hash: str | None = None
        vectors_written = False
        try:
            raw_document = self.loader.load(file_path)
            logger.info(
                "Loaded %s: %s pages, %s characters",
                file_path,
                raw_document.page_count,
                len(raw_document.raw_text),
            )
            file_hash = raw_document.content_hash or hashlib.sha256(raw_document.raw_text.encode()).hexdigest()
            self._reject_duplicate(file_hash)

            metadata = self.metadata_extractor.extract(raw_document)
            classification = self.classifier.classify(raw_document, metadata=metadata)
            logger.info(
                "Metadata for %s: number=%s type=%s (confidence %.2f), mentions=%s",
                file_path,
                metadata.document_number,
                classification.document_type,
                classification.confidence_score,
                len(metadata.mentions),
            )

            file_name = original_filename or Path(raw_document.source_path).name
            document = self._persist_document(raw_document, metadata, classification, file_hash, file_name)

            chunks = self.chunker.chunk(raw_document, metadata=metadata)
            self._persist_chunks(document.id, chunks)
            logger.info("Persisted %s chunks for document %s", len(chunks), document.id)

            link_report = (
                self.relationship_linker.link_new_document(document, metadata.mentions)
                if self.relationship_linker is not None
                else LinkReport()
            )

            document_type = classification.document_type or metadata.document_type
            embedded = build_embedded_chunks(
                document_id=document.id,
                document_number=metadata.document_number,
                document_type=document_type,
                chunks=chunks,
                embedding_provider=self.embedding_provider,
                tokenizer=self.tokenizer,
                title=metadata.title or file_name,
                file_name=file_name,
                department=metadata.department,
                subject=metadata.subject,
                issue_date=metadata.issue_date,
            )
            vectors_written = True
            self.vector_store.upsert(embedded)
            self._commit()
            logger.info("Completed ingestion for %s as document %s", file_path, document.id)
            metrics.ingestions.inc("ok")

            return IngestionResult(
                document_id=document.id,
                status=document.status,
                chunk_count=len(chunks),
                embedded_count=len(embedded),
                document_number=metadata.document_number,
                document_type=document_type,
                title=metadata.title or file_name,
                issue_date=metadata.issue_date,
                page_count=raw_document.page_count,
                links_created=link_report.created,
                pending_references=link_report.pending_references,
            )
        except Exception as exc:
            self._rollback()
            if vectors_written and document is not None:
                self._remove_vectors(document.id)
            if file_hash and isinstance(exc, IntegrityError) and "file_hash" in str(exc.orig):
                # A concurrent request ingested the same file first.
                existing = self.document_repository.get_by_file_hash(file_hash)
                if existing is not None:
                    raise DuplicateDocumentError(existing.id, existing.document_number) from exc
            if isinstance(exc, DuplicateDocumentError):
                metrics.ingestions.inc("duplicate")
            else:
                metrics.ingestions.inc("error")
                logger.exception("Ingestion failed for %s", file_path)
            raise

    def _reject_duplicate(self, file_hash: str) -> None:
        existing = self.document_repository.get_by_file_hash(file_hash)
        if existing is not None:
            logger.info("Skipping %s: identical file already ingested as %s", file_hash[:12], existing.id)
            raise DuplicateDocumentError(existing.id, existing.document_number)

    def _remove_vectors(self, document_id: uuid.UUID) -> None:
        try:
            self.vector_store.delete_document(document_id)
            logger.info("Removed vectors for failed ingestion of %s", document_id)
        except Exception:
            logger.exception(
                "Could not remove vectors for failed ingestion of %s; run /documents/reconcile",
                document_id,
            )

    def _persist_document(
        self,
        raw_document: RawDocument,
        metadata: DocumentMetadata,
        classification: DocumentClassificationResult,
        file_hash: str,
        file_name: str,
    ) -> "app.models.documents.Document":
        document_data = DocumentCreate(
            title=metadata.title or file_name,
            document_number=metadata.document_number or "",
            document_type=classification.document_type or metadata.document_type,
            issue_date=metadata.issue_date,
            effective_date=metadata.effective_date,
            department=metadata.department,
            subject=metadata.subject,
            source_url=raw_document.source_path,
            file_name=file_name,
            file_hash=file_hash,
            status=DocumentStatus.ACTIVE,
        )
        return self.document_repository.create(document_data)

    def _persist_chunks(
        self,
        document_id: uuid.UUID,
        chunks,
    ) -> None:
        for chunk in chunks:
            chunk_data = DocumentChunkCreate(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                chunk_text=chunk.chunk_text,
                token_count=chunk.estimated_token_count,
            )
            self.document_chunk_repository.create(chunk_data)

    def _commit(self) -> None:
        session = getattr(self.document_repository, "session", None)
        if session is not None:
            session.commit()

    def _rollback(self) -> None:
        session = getattr(self.document_repository, "session", None)
        if session is not None:
            session.rollback()
