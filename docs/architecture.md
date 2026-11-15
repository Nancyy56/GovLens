# GovLens Architecture

GovLens is a modular RAG pipeline with separate layers for ingestion, metadata and relationship extraction, chunking, embeddings, storage, hybrid retrieval, citation, supersession analysis, generation, and document comparison.

## Flows

```text
INGESTION   POST /ingest | /ingest/upload | /ingest/jobs (background)
  AutoPDFLoader (PyMuPDF; OCR if < 50% of pages have text)
  -> SHA-256 duplicate check (409 if already ingested)
  -> RuleBasedMetadataExtractor (number, date, department, subject, mentions + link type)
  -> RuleBasedDocumentClassifier
  -> documents row -> RuleBasedDocumentChunker -> document_chunks rows
  -> DocumentRelationshipLinker: document_references -> document_relationships, statuses
  -> HuggingFaceEmbeddingProvider -> QdrantVectorStore.upsert
  -> commit  (on failure: rollback + delete the document's vectors)

QUERY       POST /query | /query/stream | /query/search
  HybridDocumentRetriever
    QdrantDocumentRetriever (dense) + PostgresKeywordSearcher (full text, number boost)
    -> reciprocal_rank_fusion -> CrossEncoderReranker -> top_k
  -> ComparisonEngine (group by document/page, most relevant first)
  -> CitationBuilder + DatabaseSupersessionEngine (each distinct document)
  -> PromptBuilder ([S#] tags, rules, warnings) -> OllamaClient (qwen3:8b)
  -> LLMAnswerGenerator keeps cited sources, appends Sources list

COMPARE     POST /compare
  DocumentService.resolve (id or number) -> load_pages (from chunks)
  -> DocumentDiffer (sentence diff with page numbers) -> optional LLM summary of the diff

MANAGEMENT  /documents ...
  list / get / page text / delete (both stores, status recompute)
  reingest (old record kept until the new one is stored; manual links carried over)
  relationships (manual links marked MANUAL) / reconcile (rebuilds missing vectors)

ACCESS      /auth, /users, every protected route
  bearer session token or service API key -> Principal -> rate limit -> role check

BACKGROUND  in the API process
  ingestion workers (claim PENDING jobs from PostgreSQL, retry interrupted ones)
  startup reconciliation (PostgreSQL <-> Qdrant)
```

Answers pass through `verify_answer` (`app/generation/verification.py`) before they are returned: each sentence's numbers and key words must appear in the pages it cites.

## Component Responsibilities

| Component | Location | Notes |
| --------- | -------- | ----- |
| API | `app/api` | Routes, request schemas, API-key auth and rate limiting (`security.py`), liveness and readiness (`health.py`) |
| Wiring | `app/services/dependencies.py` | Heavy clients (models, Qdrant, Ollama) are process-wide singletons; session-bound services are per request |
| Ingestion | `app/services/ingestion.py`, `app/ingestion/pdf_loader.py` | Duplicate check, persistence, linking, embeddings, compensating vector delete |
| Background jobs | `app/services/jobs.py` | Jobs stored in `ingestion_jobs`; worker threads claim them with a conditional update; interrupted jobs retried up to 3 times |
| Auth | `app/services/auth.py`, `app/api/security.py` | scrypt passwords, hashed session tokens, roles, service keys, shared rate limits |
| Web UI | `app/static` | Plain HTML/CSS/JS served at `/` |
| Metrics | `app/core/metrics.py` | Prometheus text format at `/api/v1/metrics` |
| Verification | `app/generation/verification.py` | Sentence-level evidence check of answers |
| Metadata | `app/metadata` | Regex extraction; `_extract_mentions` classifies each mention (and lists of them) from their clause; `FallbackMetadataExtractor` asks the LLM for missing fields and keeps only verifiable values |
| Relationships | `app/supersession/linker.py` | Records mentions, resolves pending ones when a document arrives, maintains `SUPERSEDED` status |
| Supersession | `app/supersession/engine.py` | Follows `SUPERSEDES` edges to the latest document, cycle-safe |
| Chunking | `app/chunking/chunker.py`, `app/chunking/tokens.py` | Page-preserving 500-1000-token chunks (model tokenizer), one-sentence overlap; long chunks embedded/reranked as 400-token windows |
| Embeddings | `app/vectorstore/embedder.py` | `BAAI/bge-small-en-v1.5`, loaded once per process (thread-safe) |
| Vector store | `app/vectorstore/qdrant_store.py` | Collection `government_documents`, cosine; delete by document, list ids, ping |
| Keyword search | `app/retrieval/keyword.py` | PostgreSQL `to_tsvector`/`ts_rank_cd` (GIN index); SQLite fallback for tests |
| Hybrid + rerank | `app/retrieval/hybrid.py`, `app/retrieval/reranker.py` | RRF (k=60); cross-encoder with graceful disable |
| Generation | `app/generation` | Prompt with source tags, citation selection, streaming Ollama client |
| Comparison | `app/comparison/differ.py`, `app/services/comparison.py` | Abbreviation-aware sentence diff; similarity-based pairing of modified sentences |
| Documents | `app/services/documents.py` | Management operations and store reconciliation |

## Data Model (PostgreSQL)

| Table | Purpose |
|---|---|
| `documents` | One row per document; `file_hash` (SHA-256) is unique; `issue_date` nullable; `status` ACTIVE/SUPERSEDED/ARCHIVED |
| `document_chunks` | Chunk text per page; GIN full-text index `ix_document_chunks_fts` |
| `document_relationships` | Directed edges: SUPERSEDES, AMENDS, REFERENCES |
| `document_references` | Every mention found in a document's text, resolved or pending |
| `ingestion_jobs` | Background job status, attempts, submitter, document id, error |
| `users`, `auth_tokens` | Accounts (scrypt hashes, roles) and session token hashes |
| `rate_limit_windows` | Per-minute request counts shared by API workers |

Migrations: `20260612_0001` (initial), `20261106_0002` (references, jobs, nullable issue date, full-text index), `20261106_0003` (users, sessions, rate limits, job attempts, relationship origin, stored `search_vector`).
