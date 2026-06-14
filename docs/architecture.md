# GovLens Architecture

GovLens is implemented as a modular RAG pipeline with separate layers for ingestion, metadata extraction, chunking, embeddings, vector storage, retrieval, comparison preparation, citation generation, supersession analysis, and answer generation.

```text
PDF / OCR text
      |
      v
PyMuPDFDocumentLoader / OCRDocumentLoader
      |
      v
RawDocument with one-based PageContent records
      |
      v
RuleBasedMetadataExtractor
      |
      v
RuleBasedDocumentClassifier
      |
      v
RuleBasedDocumentChunker
      |
      v
HuggingFaceEmbeddingProvider
      |
      v
QdrantVectorStore
      |
      v
QdrantDocumentRetriever
      |
      v
ComparisonEngine + CitationBuilder + DatabaseSupersessionEngine
      |
      v
PromptBuilder
      |
      v
OllamaClient -> qwen3:8b
      |
      v
answer_markdown + citations + supersession_warnings
```

## Component Responsibilities

| Component | Current implementation | Notes |
| --------- | ---------------------- | ----- |
| API | `app/api` | FastAPI routes for health, ingestion, and query |
| Ingestion | `app/services/ingestion.py`, `app/ingestion/pdf_loader.py` | Loads PDFs, extracts metadata, classifies, chunks, embeds, stores vectors, and persists PostgreSQL rows |
| Metadata | `app/metadata/extractors.py` | Rule-based regex extraction |
| Classification | `app/classification/classifier.py` | Rule-based document type detection |
| Chunking | `app/chunking/chunker.py` | Page-preserving chunks with 500-1000 word-estimated defaults |
| Embeddings | `app/vectorstore/embedder.py` | `BAAI/bge-small-en-v1.5` through `sentence-transformers` |
| Vector Store | `app/vectorstore/qdrant_store.py` | Qdrant collection `government_documents`, cosine distance, payload metadata |
| Retrieval | `app/retrieval/retriever.py` | Dense-vector top-k retrieval with optional document number filtering |
| Comparison | `app/comparison/engine.py` | Groups retrieved chunks by source document and page; does not perform explicit diff analysis |
| Citations | `app/citations/builder.py` | Deterministic page-level citations |
| Supersession | `app/supersession/engine.py` | Traverses PostgreSQL `SUPERSEDES` relationships |
| Generation | `app/generation` | Prompt construction and Ollama generation |
| Database | `app/models/documents.py`, `app/db/database.py` | PostgreSQL ORM models, session management, Alembic migration |

## Verified Design Notes

- FastAPI is used for the REST API and OpenAPI schema.
- PostgreSQL stores document metadata, chunk text, and document relationships.
- Qdrant stores embeddings and retrieval payload metadata.
- HuggingFace embeddings are local when the model is available.
- Ollama generation uses `qwen3:8b` with `stream=false` and `temperature=0`.
- Retrieval is dense-only; there is no hybrid retrieval or reranking in the current implementation.
- Authentication, authorization, rate limiting, and streaming are not implemented.
