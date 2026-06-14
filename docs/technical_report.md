# GovLens Technical Report

## Project Overview

GovLens is a Retrieval-Augmented Generation (RAG) system for querying and comparing government documents. The current implementation includes PDF ingestion, OCR fallback, rule-based metadata extraction, rule-based classification, page-preserving chunking, HuggingFace embeddings, Qdrant storage, dense-vector retrieval, citation generation, supersession analysis, and Ollama-based answer generation.

## Objectives

- Ingest PDF documents
- Extract text with one-based page numbers
- Extract metadata using rule-based patterns
- Classify document type using rule-based patterns
- Chunk text without crossing page boundaries
- Generate embeddings with `BAAI/bge-small-en-v1.5`
- Store vectors and metadata in Qdrant
- Store document metadata, chunk text, and relationships in PostgreSQL
- Retrieve relevant chunks using dense-vector similarity search
- Filter retrieval by document number
- Prepare multi-source context for answer generation
- Generate deterministic citations
- Check supersession relationships
- Generate answers through local Ollama inference
- Expose ingestion and query APIs through FastAPI
- Run local services through Docker Compose

## Technology Stack

### Backend

- Python 3.12
- FastAPI 0.104.1
- Pydantic 2.5.0
- SQLAlchemy `>=2.0.35`
- Alembic 1.13.1

### PDF Processing

- PyMuPDF for digital PDF extraction
- `pdf2image` and `pytesseract` for OCR fallback

### Embeddings

- `sentence-transformers`
- `BAAI/bge-small-en-v1.5`

### Vector Database

- Qdrant
- `qdrant-client` 1.18.0
- Cosine distance
- Collection name: `government_documents`

### Relational Database

- PostgreSQL 16
- SQLAlchemy ORM models
- Alembic migration

### Large Language Model

- Ollama
- Model: `qwen3:8b`
- Request options: `stream=false`, `temperature=0`, `num_predict=512`

### Containerization

- Docker
- Docker Compose

## Ingestion Pipeline

1. Load a PDF with `PyMuPDFDocumentLoader` or `OCRDocumentLoader`.
2. Build a `RawDocument` with ordered `PageContent` records.
3. Extract metadata with `RuleBasedMetadataExtractor`.
4. Classify document type with `RuleBasedDocumentClassifier`.
5. Persist a `Document` row in PostgreSQL.
6. Chunk the document with `RuleBasedDocumentChunker`.
7. Persist `DocumentChunk` rows in PostgreSQL.
8. Embed chunk text with `HuggingFaceEmbeddingProvider`.
9. Upsert `EmbeddedChunk` records into Qdrant with payload metadata.

## Retrieval Pipeline

1. Accept a query through `POST /api/v1/query`.
2. Embed the query with `HuggingFaceEmbeddingProvider`.
3. Search Qdrant with `QdrantVectorStore.search`.
4. Convert Qdrant hits into `RetrievedChunk` objects.
5. Optionally filter by `document_numbers`.
6. Sort chunks by score descending.

## Query Orchestration

1. Retrieve chunks with `QdrantDocumentRetriever`.
2. Prepare comparison input with `ComparisonEngine`.
3. Build citations with `CitationBuilder`.
4. Check supersession for the first retrieved document id with `DatabaseSupersessionEngine`.
5. Build a grounded prompt with `PromptBuilder`.
6. Generate markdown with `OllamaClient`.
7. Return `QueryResult` with `answer_markdown`, `citations`, and `supersession_warnings`.

## Assignment Coverage

### Implemented

- PDF ingestion
- OCR fallback
- Text extraction with page numbers
- Rule-based metadata extraction
- Rule-based document classification
- Page-preserving chunking
- HuggingFace embeddings
- Qdrant vector storage
- PostgreSQL metadata storage
- Dense top-k retrieval
- Document number filtering
- Citation generation
- Ollama generation
- FastAPI routes
- Docker Compose local service orchestration

### Partially Implemented

- Comparison: current implementation groups chunks by source and page but does not perform explicit difference or contradiction analysis.
- Supersession: current engine can traverse `SUPERSEDES` chains, but query flow checks only the first retrieved document id.
- Local deployment: Docker Compose includes local PostgreSQL, Qdrant, and Ollama services, but HuggingFace and Ollama models may require network access during setup.

## Current Limitations

- No authentication or authorization
- No rate limiting
- No streaming responses
- No automated RAG evaluation framework
- No hybrid retrieval
- No reranking
- Retrieval quality depends on chunking and embedding quality
- Large prompts can increase Ollama response time
- Ollama response time depends on local hardware
- Comparison is source grouping rather than explicit comparison analysis
- Supersession warnings are limited to the first retrieved document in query flow

## Conclusion

GovLens implements a modular RAG workflow with ingestion, embedding generation, vector storage, retrieval, citation generation, supersession analysis, and answer generation. The implementation is assessment-oriented and should be described with conservative language until authentication, evaluation, hybrid retrieval, reranking, streaming, and broader supersession coverage are added.
