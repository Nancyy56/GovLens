"""FastAPI dependency providers for application services.

Heavy, thread-safe components (embedding model, reranker, Qdrant client,
Ollama client) are created once per process and shared. Anything holding a
database session is created per request.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.classification.classifier import RuleBasedDocumentClassifier
from app.chunking.chunker import RuleBasedDocumentChunker
from app.chunking.tokens import HuggingFaceTokenizer
from app.citations.builder import CitationBuilder
from app.comparison.engine import ComparisonEngine
from app.core.config import settings
from app.db.database import SessionLocal, get_session
from app.generation.generator import LLMAnswerGenerator
from app.generation.ollama_client import OllamaClient
from app.ingestion.pdf_loader import AutoPDFLoader
from app.metadata.extractors import FallbackMetadataExtractor, LLMMetadataExtractor, RuleBasedMetadataExtractor
from app.repositories.documents import DocumentChunkRepository, DocumentRepository
from app.retrieval.hybrid import HybridDocumentRetriever
from app.retrieval.keyword import PostgresKeywordSearcher
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.retriever import QdrantDocumentRetriever
from app.services.comparison import ComparisonService
from app.services.documents import DocumentService
from app.services.ingestion import DocumentIngestionService
from app.services.jobs import IngestionJobRunner
from app.services.query import QueryService
from app.supersession.engine import DatabaseSupersessionEngine
from app.supersession.linker import DocumentRelationshipLinker
from app.vectorstore.embedder import HuggingFaceEmbeddingProvider
from app.vectorstore.qdrant_store import QdrantVectorStore


def get_loader() -> AutoPDFLoader:
    return AutoPDFLoader()


def get_metadata_extractor() -> FallbackMetadataExtractor:
    fallback = LLMMetadataExtractor(get_llm_client()) if settings.metadata_llm_fallback else None
    return FallbackMetadataExtractor(RuleBasedMetadataExtractor(), fallback)


def get_classifier() -> RuleBasedDocumentClassifier:
    return RuleBasedDocumentClassifier()


@lru_cache(maxsize=1)
def get_text_tokenizer() -> HuggingFaceTokenizer:
    return HuggingFaceTokenizer(settings.embedding_model)


def get_chunker() -> RuleBasedDocumentChunker:
    return RuleBasedDocumentChunker(token_counter=get_text_tokenizer().count)


@lru_cache(maxsize=1)
def get_embedding_provider() -> HuggingFaceEmbeddingProvider:
    return HuggingFaceEmbeddingProvider(model_name=settings.embedding_model)


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key,
    )


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoderReranker | None:
    if not settings.reranker_enabled:
        return None
    return CrossEncoderReranker(model_name=settings.reranker_model, tokenizer=get_text_tokenizer())


@lru_cache(maxsize=1)
def get_llm_client() -> OllamaClient:
    return OllamaClient(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.ollama_timeout_seconds,
        num_predict=settings.ollama_num_predict,
        keep_alive=_keep_alive(settings.ollama_keep_alive),
    )


def _keep_alive(value: str) -> str | int:
    # Ollama treats the number 0 (not the string "0") as "unload now".
    return int(value) if value.strip().lstrip("-").isdigit() else value


def build_ingestion_service(session: Session) -> DocumentIngestionService:
    return DocumentIngestionService(
        loader=get_loader(),
        metadata_extractor=get_metadata_extractor(),
        classifier=get_classifier(),
        chunker=get_chunker(),
        embedding_provider=get_embedding_provider(),
        vector_store=get_vector_store(),
        document_repository=DocumentRepository(session),
        document_chunk_repository=DocumentChunkRepository(session),
        relationship_linker=DocumentRelationshipLinker(session),
        tokenizer=get_text_tokenizer(),
    )


def build_query_service(session: Session) -> QueryService:
    dense = QdrantDocumentRetriever(
        embedding_provider=get_embedding_provider(),
        vector_store=get_vector_store(),
    )
    retriever = HybridDocumentRetriever(
        dense_retriever=dense,
        keyword_searcher=PostgresKeywordSearcher(session) if settings.hybrid_search_enabled else None,
        reranker=get_reranker(),
        candidate_multiplier=settings.retrieval_candidate_multiplier,
        min_rerank_score=settings.reranker_min_score,
    )
    return QueryService(
        retriever=retriever,
        comparison_engine=ComparisonEngine(),
        citation_builder=CitationBuilder(),
        supersession_engine=DatabaseSupersessionEngine(session),
        llm_client=LLMAnswerGenerator(llm_client=get_llm_client()),
    )


@lru_cache(maxsize=1)
def get_job_runner() -> IngestionJobRunner:
    return IngestionJobRunner(
        session_factory=SessionLocal,
        service_factory=build_ingestion_service,
        upload_dir=settings.upload_dir,
        max_workers=settings.ingest_workers,
    )


def get_ingestion_service(session: Session = Depends(get_session)) -> DocumentIngestionService:
    return build_ingestion_service(session)


def get_query_service(session: Session = Depends(get_session)) -> QueryService:
    return build_query_service(session)


def get_document_service(session: Session = Depends(get_session)) -> DocumentService:
    return DocumentService(
        session=session,
        vector_store=get_vector_store(),
        embedding_provider=get_embedding_provider(),
        tokenizer=get_text_tokenizer(),
    )


def get_comparison_service(session: Session = Depends(get_session)) -> ComparisonService:
    return ComparisonService(
        session=session,
        document_service=DocumentService(session=session, vector_store=get_vector_store()),
        llm_client=get_llm_client(),
    )
