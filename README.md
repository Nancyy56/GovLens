# GovLens

**Government Document Retrieval-Augmented Generation (RAG) System**

GovLens is a modular RAG system for querying and comparing government documents. The implementation extracts text from PDFs, chunks text by page, generates embeddings, stores vectors in Qdrant, retrieves relevant chunks, builds citations, checks supersession relationships, and generates answers through Ollama.

---

## Overview

### Problem Statement

Government organizations publish notifications, circulars, orders, gazettes, policies, and advisories. GovLens is structured to help users ask natural-language questions over those documents and inspect source-backed answers.

### Why RAG

The implementation uses retrieval before generation. Query text is embedded, relevant chunks are retrieved from Qdrant, and the generation prompt is built from those chunks plus citations and supersession warnings.

### Why Semantic Search

The vector store uses dense embeddings from `BAAI/bge-small-en-v1.5` through `sentence-transformers`. Retrieval is currently dense-vector similarity search only.

### Why Citations Matter

The citation builder creates deterministic citations from retrieved chunks using document type, document number, issue date when available, and page number.

---

## Features

### Ingestion Pipeline

- **PDF Loading**: Digital PDFs via PyMuPDF; scanned PDFs via OCR fallback using `pdf2image` and `pytesseract`
- **Text Extraction**: Preserves one-based page numbers for citation mapping
- **Metadata Extraction**: Rule-based extraction of document numbers, dates, departments, subjects, and referenced documents
- **Document Classification**: Rule-based document type detection for notification, circular, order, gazette, policy, advisory, or unknown
- **Chunking**: Page-preserving token-aware splitting with default 500-1000 word-estimated chunks
- **Embedding Generation**: HuggingFace `BAAI/bge-small-en-v1.5` model through `sentence-transformers`

### Retrieval Layer

- **Top-K Similarity Search**: Configurable retrieval with API default `top_k=10`
- **Vector Database**: Qdrant with cosine distance
- **Document Number Filtering**: Optional query-time filtering by `document_numbers`
- **Payload Metadata**: Retrieved chunks carry document identifiers, page number, chunk text, issue date, title, file name, department, and subject when stored in Qdrant payload

### Comparison Preparation

- **Multi-Source Grouping**: Groups retrieved chunks by source document
- **Page-Level Aggregation**: Combines chunks per page for each source
- **Scope Note**: The current comparison engine prepares source context; it does not perform a separate diff or contradiction analysis

### Generation Layer

- **Prompt Construction**: Structured prompt with grounding rules and source context
- **Local LLM Inference**: Ollama integration using `qwen3:8b`
- **Markdown Output**: The API returns `answer_markdown`
- **Temperature Control**: Ollama request sets `temperature=0` and `stream=false`

### Supersession Analysis

- **Document Lineage**: Traverses `SUPERSEDES` relationships stored in PostgreSQL
- **Warnings**: Returns supersession warnings when the checked document is superseded
- **Scope Note**: Query service checks the first retrieved chunk's document id, not every retrieved document

### Citation System

- **Deterministic Citations**: Page-level citations generated from retrieved chunk metadata
- **Document Type Labels**: Formats labels such as `Notification No. X` or `Circular No. X`
- **Date Inclusion**: Adds issue date in ISO format when available

---

## Architecture Overview

```text
PDF / OCR text
      |
      v
Rule-based metadata extraction
      |
      v
Rule-based classification
      |
      v
Page-preserving chunking
      |
      v
HuggingFace embeddings
      |
      v
Qdrant vector store
      |
      v
Query embedding + top-k retrieval
      |
      v
Comparison preparation + citations + supersession check
      |
      v
PromptBuilder
      |
      v
Ollama qwen3:8b
      |
      v
Markdown answer + citations
```

PostgreSQL stores document metadata, chunk text, and supersession relationships. Qdrant stores dense embeddings and retrieval payload metadata.

---

## End-to-End Query Flow

1. `POST /api/v1/query` receives a query, optional `top_k`, and optional `document_numbers`.
2. `QueryService` embeds the query with `HuggingFaceEmbeddingProvider`.
3. `QdrantDocumentRetriever` searches Qdrant and converts payloads into `RetrievedChunk` objects.
4. `ComparisonEngine` groups chunks by source document and page.
5. `CitationBuilder` builds deterministic citations from retrieved chunks.
6. `DatabaseSupersessionEngine` checks the first retrieved document's supersession chain.
7. `PromptBuilder` creates a grounded prompt from query, source chunks, citations, and warnings.
8. `OllamaClient` calls `/api/generate` with `qwen3:8b`, `stream=false`, and `temperature=0`.
9. `QueryResult` returns `answer_markdown`, `citations`, and `supersession_warnings`.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | Python 3.12, FastAPI 0.104.1 | REST API framework |
| **ORM** | SQLAlchemy `>=2.0.35` | Database abstraction |
| **Migrations** | Alembic 1.13.1 | Schema versioning |
| **Vector Database Client** | `qdrant-client` 1.18.0 | Qdrant similarity search |
| **Embeddings** | `sentence-transformers`, `BAAI/bge-small-en-v1.5` | Dense vector generation |
| **LLM Backend** | Ollama, `qwen3:8b` | Local text generation |
| **Database** | PostgreSQL 16 | Document metadata, chunk text, supersession graph |
| **PDF Processing** | PyMuPDF, `pdf2image`, `pytesseract` | Digital extraction and OCR fallback |
| **Containerization** | Docker, Docker Compose | Local service orchestration |

---

## Project Structure

```text
app/
├── api/                  # FastAPI routes and schemas
├── chunking/             # Page-preserving chunking
├── citations/            # Deterministic citation generation
├── classification/       # Rule-based document classification
├── comparison/           # Source grouping for comparison input
├── core/                 # Settings and constants
├── db/                   # SQLAlchemy session management
├── generation/           # Prompt builder, Ollama client, answer generator
├── ingestion/            # PDF and OCR document loaders
├── metadata/             # Rule-based metadata extraction
├── models/               # PostgreSQL ORM models and enums
├── repositories/         # CRUD repositories
├── retrieval/            # Qdrant-backed retrieval
├── schemas/              # Processing and document schemas
├── services/             # Ingestion and query orchestration
├── supersession/         # PostgreSQL-backed supersession analysis
└── vectorstore/          # Embedding providers and Qdrant store
```

---

## API Documentation

### Health Check

`GET /api/v1/health`

Returns application health status.

**Response:**

```json
{
  "status": "ok"
}
```

---

### Document Ingestion

`POST /api/v1/ingest`

Ingests a PDF document into the system.

**Request Body:**

```json
{
  "file_path": "/path/to/document.pdf"
}
```

**Response fields:**

- `document_id`
- `document_number`
- `document_type`
- `chunk_count`

---

### Document Query

`POST /api/v1/query`

Queries ingested documents and receives a citation-backed answer.

**Request Body:**

```json
{
  "query": "What are the key changes in GST notification 17/2024?",
  "top_k": 10,
  "document_numbers": ["17/2024"]
}
```

**Response fields:**

- `query`
- `answer_markdown`
- `citations`
- `supersession_warnings`

---

## Setup

### Prerequisites

- Docker and Docker Compose
- Python 3.12 for local development
- Ollama with the `qwen3:8b` model available before query generation
- System packages for OCR if scanned PDFs are used: Tesseract and Poppler utilities

### Docker Compose

```bash
# Create or verify environment configuration
cp .env.example .env

# Start PostgreSQL, Qdrant, Ollama, and the FastAPI app
docker compose up --build -d
```

The app service runs Alembic migrations and starts Uvicorn.

### Ollama Setup

```bash
docker compose exec ollama ollama pull qwen3:8b
docker compose exec ollama ollama list
```

### Qdrant Setup

```bash
curl http://localhost:6333/health
```

### PostgreSQL Setup

```bash
docker compose exec postgres psql -U govlens_user -d govlens -c "SELECT 1;"
```

### Health Checks

```bash
curl http://localhost:8000/api/v1/health
docker compose ps
```

---

## Example Usage

### Ingest a Document

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/app/sample_notification.pdf"}'
```

### Query Documents

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Summarize the key provisions",
    "top_k": 10,
    "document_numbers": []
  }'
```

### Filter by Document Number

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What does section 3 say?",
    "document_numbers": ["17/2024"]
  }'
```

---

## Design Decisions

- **FastAPI** is used for the REST API, dependency injection, request validation, and OpenAPI documentation.
- **PostgreSQL** stores relational document metadata, persisted chunk text, and the supersession relationship graph.
- **Qdrant** stores dense vectors and payload metadata so retrieval can return scored chunks with citation-relevant fields.
- **HuggingFace embeddings** are loaded locally through `sentence-transformers`; the configured model is `BAAI/bge-small-en-v1.5`.
- **Ollama** is used for local generation through a simple HTTP client to `/api/generate`.
- **Local inference** keeps the generation backend independent from hosted LLM APIs, but model availability depends on local setup.
- **Dependency injection** is used through service dependency providers and protocol-style interfaces so components can be tested or swapped.
- **Separate retrieval and generation layers** keep embedding, vector search, prompt construction, citation generation, and LLM calls in distinct modules.
- **Rule-based metadata extraction, classification, and chunking** make the pipeline deterministic and easy to inspect, with the tradeoff of pattern brittleness.
- **Page-preserving chunking** supports page-level citations, while overlap sentences can duplicate small amounts of context across chunks.

---

## Engineering Tradeoffs

- **Local LLMs**
  - Advantages: no hosted API dependency, useful for private or offline-oriented workflows after models are available.
  - Disadvantages: slower responses, hardware dependency, model download requirements, and response time varies by machine.

- **Dense-only retrieval**
  - Advantages: simple architecture and direct semantic matching.
  - Disadvantages: no hybrid BM25/sparse retrieval, no reranking, and lexical edge cases can be missed.

- **Qdrant**
  - Advantages: dedicated vector search with payload filtering and cosine distance.
  - Disadvantages: adds another service to operate alongside PostgreSQL and Ollama.

- **PostgreSQL for metadata and chunk text**
  - Advantages: durable relational records, migrations, indexes, and relationship tracking.
  - Disadvantages: embeddings remain outside PostgreSQL, so consistency between Qdrant and PostgreSQL is an operational concern.

- **Rule-based metadata and classification**
  - Advantages: deterministic, auditable, and no labeled training data required.
  - Disadvantages: brittle outside document formats covered by the regex patterns.

- **Non-streaming Ollama responses**
  - Advantages: simple API contract and one response body.
  - Disadvantages: users wait for the full generation before seeing output.

- **Single Qdrant collection**
  - Advantages: simple initial setup.
  - Disadvantages: no tenant, corpus, model-version, or document-version isolation in the current implementation.

---

## Known Limitations

See [docs/known_limitations.md](docs/known_limitations.md) for the detailed list. Key current limitations include CPU-only inference latency, large prompt processing time, Ollama response time depending on hardware, retrieval quality depending on chunking, no hybrid retrieval, no reranking, no streaming responses, no authentication, no rate limiting, and no automated RAG evaluation framework.

---

## Assignment Coverage

See [docs/assignment_mapping.md](docs/assignment_mapping.md) for detailed requirement traceability.

| Requirement | Status | Implementation |
| ----------- | -------- | -------------- |
| PDF Ingestion | Implemented | `app/ingestion` |
| OCR Fallback | Implemented | `app/ingestion/pdf_loader.py` |
| Text Extraction with Page Numbers | Implemented | `app/ingestion/pdf_loader.py`, `app/schemas/processing.py` |
| Metadata Extraction | Implemented | `app/metadata` |
| Document Classification | Implemented | `app/classification` |
| Chunking | Implemented | `app/chunking` |
| Embeddings | Implemented | `app/vectorstore/embedder.py` |
| Qdrant Storage | Implemented | `app/vectorstore/qdrant_store.py` |
| PostgreSQL Metadata | Implemented | `app/models/documents.py`, `alembic/versions/20260612_0001_create_document_domain_tables.py` |
| Retrieval | Implemented | `app/retrieval` |
| Document Number Filtering | Implemented | `app/retrieval/retriever.py` |
| Comparison Preparation | Partial | `app/comparison` |
| Citations | Implemented | `app/citations` |
| Supersession Analysis | Partial | `app/supersession` |
| Generation | Implemented | `app/generation` |
| REST API | Implemented | `app/api` |
| Docker Compose | Implemented | `docker-compose.yml`, `Dockerfile` |

---

## Future Improvements

- [ ] Hybrid retrieval combining dense and sparse signals
- [ ] Reranking with cross-encoders or another reranker
- [ ] Streaming response support
- [ ] Authentication and authorization
- [ ] Rate limiting middleware
- [ ] Evaluation metrics for retrieval and generation quality
- [ ] Web UI for document upload and querying
- [ ] Async processing queue for large documents
- [ ] Automatic relationship extraction from metadata
- [ ] Supersession checks across all retrieved documents
- [ ] Test updates for current Qdrant client APIs and loader implementation

---

## Remaining Gaps

- No authentication, authorization, or API key enforcement
- No rate limiting
- No streaming responses
- No automated RAG evaluation framework
- No hybrid retrieval or reranking
- Comparison currently prepares source context but does not perform explicit diff analysis
- Supersession analysis currently checks only the first retrieved document id in query flow
- Some tests reference loader classes or Qdrant client methods that do not match the current implementation
