"""FastAPI dependency providers for application services."""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends

from app.classification.classifier import RuleBasedDocumentClassifier
from app.chunking.chunker import RuleBasedDocumentChunker
from app.citations.builder import CitationBuilder
from app.comparison.engine import ComparisonEngine
from app.core.config import settings
from app.db.database import get_session
from app.ingestion.pdf_loader import get_document_loader
from app.metadata.extractors import RuleBasedMetadataExtractor
from app.repositories.documents import DocumentChunkRepository, DocumentRepository
from app.retrieval.retriever import QdrantDocumentRetriever
from app.services.ingestion import DocumentIngestionService
from app.services.query import QueryService
from app.supersession.engine import DatabaseSupersessionEngine
from app.vectorstore.embedder import HashEmbeddingProvider
from app.vectorstore.qdrant_store import QdrantVectorStore
from app.generation.generator import LLMAnswerGenerator
from app.vectorstore.embedder import (
    HashEmbeddingProvider,
    HuggingFaceEmbeddingProvider,
)
from app.generation.ollama_client import OllamaClient


class _LoaderWrapper:
    def __init__(self, factory):
        self.factory = factory

    def load(self, file_path: str):
        return self.factory(file_path).load(file_path)


def get_loader():
    return _LoaderWrapper(get_document_loader)


def get_metadata_extractor():
    return RuleBasedMetadataExtractor()


def get_classifier():
    return RuleBasedDocumentClassifier()


def get_chunker():
    return RuleBasedDocumentChunker()


def get_embedding_provider():
    return HuggingFaceEmbeddingProvider(
    model_name="BAAI/bge-small-en-v1.5"
)


def get_vector_store():
    return QdrantVectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )


def get_comparison_engine():
    return ComparisonEngine()


def get_citation_builder():
    return CitationBuilder()


def get_document_repository(session) -> DocumentRepository:
    return DocumentRepository(session)


def get_document_chunk_repository(session) -> DocumentChunkRepository:
    return DocumentChunkRepository(session)


def get_supersession_engine(session) -> DatabaseSupersessionEngine:
    return DatabaseSupersessionEngine(session)


def get_ingestion_service(session=Depends(get_session)) -> DocumentIngestionService:
    return DocumentIngestionService(
        loader=get_loader(),
        metadata_extractor=get_metadata_extractor(),
        classifier=get_classifier(),
        chunker=get_chunker(),
        embedding_provider=get_embedding_provider(),
        vector_store=get_vector_store(),
        document_repository=get_document_repository(session),
        document_chunk_repository=get_document_chunk_repository(session),
    )


def get_query_service(session=Depends(get_session)) -> QueryService:
    from app.generation.interfaces import LLMClient

    
    return QueryService(
        retriever=QdrantDocumentRetriever(
            embedding_provider=get_embedding_provider(),
            vector_store=get_vector_store(),
        ),
        comparison_engine=get_comparison_engine(),
        citation_builder=get_citation_builder(),
        supersession_engine=get_supersession_engine(session),
        llm_client=LLMAnswerGenerator(
            llm_client=OllamaClient()
        ),
    )
