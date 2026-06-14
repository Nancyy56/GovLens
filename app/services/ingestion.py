"""Document ingestion orchestration service."""

from __future__ import annotations

import uuid
import logging
from datetime import date
from typing import Sequence

from app.chunking.interfaces import DocumentChunker
from app.classification.interfaces import DocumentClassifier
from app.ingestion.contracts import DocumentLoader, MetadataExtractor
from app.metadata.interfaces import MetadataExtractionStrategy
from app.models.enums import DocumentStatus
from app.repositories.documents import DocumentChunkRepository, DocumentRepository
from app.schemas.documents import DocumentChunkCreate, DocumentCreate
from app.schemas.processing import DocumentClassificationResult, DocumentMetadata, RawDocument
from app.services.schemas import IngestionResult
from app.vectorstore.interfaces import EmbeddingProvider, VectorStore

logger = logging.getLogger(__name__)


class DocumentIngestionService:
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
    ) -> None:
        self.loader = loader
        self.metadata_extractor = metadata_extractor
        self.classifier = classifier
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.document_repository = document_repository
        self.document_chunk_repository = document_chunk_repository

    def ingest(self, file_path: str) -> IngestionResult:
        logger.info("Starting ingestion for %s", file_path)
        try:
            raw_document = self.loader.load(file_path)
            logger.info(
                "Loaded raw document %s from %s with %s pages and %s characters",
                raw_document.document_id,
                file_path,
                raw_document.page_count,
                len(raw_document.raw_text),
            )

            metadata = self.metadata_extractor.extract(raw_document)
            logger.info(
                "Extracted metadata for %s: document_number=%s document_type=%s confidence=%.2f",
                raw_document.document_id,
                metadata.document_number,
                metadata.document_type,
                metadata.confidence_score,
            )

            classification = self.classifier.classify(raw_document, metadata=metadata)
            logger.info(
                "Classified %s as %s with confidence %.2f",
                raw_document.document_id,
                classification.document_type,
                classification.confidence_score,
            )

            document = self._persist_document(raw_document, metadata, classification)
            logger.info("Persisted document row %s for raw document %s", document.id, raw_document.document_id)

            chunks = self.chunker.chunk(raw_document, metadata=metadata)
            logger.info("Generated %s chunks for document %s", len(chunks), document.id)
            self._persist_chunks(document.id, chunks)
            logger.info("Persisted %s chunk rows for document %s", len(chunks), document.id)

            chunk_texts = [chunk.chunk_text for chunk in chunks]
            embeddings = self.embedding_provider.embed(chunk_texts)
            logger.info("Generated %s embeddings for document %s", len(embeddings), document.id)

            from app.vectorstore.schemas import EmbeddedChunk

            embedded = [
                EmbeddedChunk(
                    document_id=document.id,
                    document_number=metadata.document_number,
                    document_type=classification.document_type or metadata.document_type,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.chunk_text,
                    embedding=embedding,
                    metadata={**(chunk.metadata or {}),"title": metadata.title or raw_document.source_path.split("/")[-1],"file_name": raw_document.source_path.split("/")[-1],"department": metadata.department,"subject": metadata.subject,"issue_date": (
                                                                                                                                                                                                                                                metadata.issue_date.isoformat()
                                                                                                                                                                                                                                                if metadata.issue_date
                                                                                                                                                                                                                                                else None
                                                                                                                                                                                                                                            ),
                    },
                )
                for chunk, embedding in zip(chunks, embeddings)
            ]
            self.vector_store.upsert(embedded)
            logger.info("Stored %s vectors for document %s", len(embedded), document.id)
            self._commit()
            logger.info("Completed ingestion for %s as document %s", file_path, document.id)

            return IngestionResult(
                document_id=document.id,
                status=DocumentStatus.ACTIVE,
                chunk_count=len(chunks),
                embedded_count=len(embedded),
            )
        except Exception:
            self._rollback()
            logger.exception("Ingestion failed for %s", file_path)
            raise

    def _persist_document(
        self,
        raw_document: RawDocument,
        metadata: DocumentMetadata,
        classification: DocumentClassificationResult,
    ) -> "app.models.documents.Document":
        today = date.today()
        document_data = DocumentCreate(
            title=metadata.title or raw_document.source_path.split("/")[-1],
            document_number=metadata.document_number or "",
            document_type=classification.document_type or metadata.document_type,
            issue_date=metadata.issue_date or today,
            effective_date=metadata.effective_date,
            department=metadata.department,
            subject=metadata.subject,
            source_url=raw_document.source_path,
            file_name=raw_document.source_path.split("/")[-1],
            file_hash=str(raw_document.document_id),
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
