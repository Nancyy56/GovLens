# Interviewer Guide

## 5-Minute Architecture Summary

GovLens is a modular RAG system for government documents. It ingests PDFs, extracts text with page numbers, extracts metadata, classifies document type, chunks text, embeds chunks, stores vectors in Qdrant, retrieves relevant chunks, builds citations, checks supersession relationships, and generates answers through Ollama.

The main API is a FastAPI application with two business endpoints:

- `POST /api/v1/ingest`
- `POST /api/v1/query`

PostgreSQL stores document metadata, chunk text, and document relationships. Qdrant stores dense embeddings and payload metadata needed for retrieval and citations.

## Request Lifecycle

### Ingestion Request

1. Client sends a PDF path to `POST /api/v1/ingest`.
2. `DocumentIngestionService` loads the PDF.
3. `RuleBasedMetadataExtractor` extracts metadata.
4. `RuleBasedDocumentClassifier` classifies the document.
5. PostgreSQL document and chunk rows are persisted.
6. Chunks are embedded with `BAAI/bge-small-en-v1.5`.
7. Embeddings are upserted into Qdrant with payload metadata.

### Query Request

1. Client sends query text, optional `top_k`, and optional `document_numbers` to `POST /api/v1/query`.
2. `QueryService` embeds the query.
3. `QdrantDocumentRetriever` searches Qdrant and returns ranked chunks.
4. `ComparisonEngine` groups chunks by source document and page.
5. `CitationBuilder` creates deterministic citations.
6. `DatabaseSupersessionEngine` checks the first retrieved document's supersession chain.
7. `PromptBuilder` creates a grounded prompt.
8. `OllamaClient` generates markdown with `qwen3:8b`.
9. The API returns `answer_markdown`, `citations`, and `supersession_warnings`.

## Interesting Engineering Decisions

- **Page-preserving chunking** keeps page numbers available for legal-style citations.
- **Dense retrieval plus separate citation generation** keeps retrieval and citation logic independent.
- **PostgreSQL and Qdrant separation** stores relational metadata in PostgreSQL and vectors in Qdrant.
- **Rule-based metadata and classification** make extraction auditable and deterministic, though pattern-dependent.
- **Dependency injection** separates service wiring from business logic.
- **Local Ollama generation** avoids hosted LLM API calls, but response time depends on local hardware.

## Challenges Encountered

- Citation accuracy depends on preserving page numbers through ingestion, chunking, embedding, retrieval, and generation.
- Retrieval quality depends on chunking, embedding model quality, and absence of reranking.
- Local inference can be slow on CPU-only hardware.
- Rule-based metadata extraction is brittle outside covered document formats.
- Supersession analysis requires reliable relationship data in PostgreSQL.

## Why Qdrant

Qdrant is used because the system needs vector similarity search and payload metadata. The implementation stores dense embeddings in a Qdrant collection named `government_documents` and uses cosine distance.

## Why Ollama

Ollama is used as the local generation backend. The current client calls `qwen3:8b` with `stream=false` and `temperature=0`.

## Why RAG

RAG is used because answers are grounded in retrieved document chunks and citations instead of relying only on model memory. The current prompt instructs the model to answer only from provided sources.

## Known Limitations

- No authentication or authorization
- No rate limiting
- No streaming responses
- No hybrid retrieval
- No reranking
- No automated RAG evaluation framework
- CPU-only inference can be slow
- Ollama response time depends on hardware
- Comparison currently groups sources rather than performing explicit diff analysis
- Query-time supersession checks cover only the first retrieved document id

## Potential Future Improvements

- Add authentication, authorization, and rate limiting
- Add hybrid retrieval and reranking
- Add automated retrieval and citation evaluation
- Extend supersession checks to all retrieved documents
- Add explicit comparison or diff analysis
- Add streaming responses
- Add monitoring, metrics, and tracing
- Add a web UI and async ingestion jobs
- Improve metadata extraction and relationship detection
