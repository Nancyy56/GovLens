# GovLens: A Retrieval-Augmented Generation System for Trustworthy Question Answering over Government Documents

**Project report**

| | |
|---|---|
| **Project title** | GovLens: cited, verified question answering and comparison over government documents |
| **Submitted by** | *(your name, roll number)* |
| **Team members** | *(names and roll numbers, if a group project)* |
| **Guide / supervisor** | *(name)* |
| **Department / programme** | *(for example, B.Tech Computer Science and Engineering)* |
| **Institution** | *(college and university)* |
| **Academic year** | *(for example, 2026-27)* |
| **Source code** | https://github.com/Nancyy56/GovLens |

> **How to use this file.** Everything below describes the project as it exists in the repository at the time of writing. Fill in the bracketed items on this page, then adapt headings and numbering to your institution's report template. Every number in this report (file counts, test counts, endpoint counts, timings) was measured from the actual project; section 13 explains how to reproduce them. Section 17 lists references in a neutral format that you should reformat to your required citation style.

---

## Table of contents

1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [Background and related concepts](#3-background-and-related-concepts)
4. [Requirements analysis](#4-requirements-analysis)
5. [System architecture](#5-system-architecture)
6. [Detailed design of the back end](#6-detailed-design-of-the-back-end)
7. [Database design](#7-database-design)
8. [API design](#8-api-design)
9. [Front-end design](#9-front-end-design)
10. [Security design](#10-security-design)
11. [Deployment and operations](#11-deployment-and-operations)
12. [Testing](#12-testing)
13. [Evaluation and results](#13-evaluation-and-results)
14. [Development history and problems solved](#14-development-history-and-problems-solved)
15. [Limitations and future work](#15-limitations-and-future-work)
16. [Conclusion](#16-conclusion)
17. [References](#17-references)
18. [Appendices](#18-appendices)

---

## 1. Abstract

Government departments publish large numbers of circulars, notifications, orders, gazettes and policy documents. They are long, written in dense legal language, frequently replace or amend one another, and are usually distributed as PDF files, some of them scanned images. A citizen, accountant, lawyer or official who needs a specific answer (for example, "What is the current GST rate on packaged food, and has it changed?") must find the right documents, read them, and work out which one is currently in force.

GovLens is a web application that automates this work. A user uploads PDF documents, or imports them from official government websites by link. The system reads each document (using optical character recognition for scanned pages), extracts its number, date, department and type, splits it into page-aware passages, and builds both a semantic (vector) index and a keyword (full-text) index. It also reads the text for references to other documents and automatically builds a **supersession graph**: which document replaces, amends or merely mentions which.

When the user asks a question, GovLens retrieves the best passages with **hybrid search** (dense vectors plus full-text search, fused by reciprocal rank fusion and re-scored by a cross-encoder), and asks a **locally hosted language model** to write an answer using only those passages. The answer streams to the screen word by word, every claim carries a clickable citation to the exact document and page, and a **sentence-level verifier** then checks that the numbers and key words in each sentence actually appear in the cited pages. If a cited document has been superseded, the interface warns the user and names the newer document. If the library does not contain the answer, the system says so instead of guessing.

Around this core the project provides a complete product: a React single-page interface with a document library, original-PDF viewer, lineage graph, sentence-level document comparison with export, plain-language document briefs, saved documents with notes, a timeline, query history with feedback, usage analytics, an audit log, role-based access control, and a directory of about 120 official sources (112 for India) to help users find the PDFs. For production use the project adds HTTPS reverse proxying, account lockout, a password policy, security headers, data-retention jobs, scheduled backups, a safe URL importer protected against server-side request forgery, continuous-integration configuration, and a hardened container build.

The back end is written in Python (FastAPI, SQLAlchemy, PostgreSQL, Qdrant, Ollama), the front end in TypeScript (React, Vite, Tailwind CSS). The repository contains about 9,300 lines of Python application code, 4,200 lines of tests (274 automated tests, all passing), and about 2,600 lines of front-end code. On the development laptop, enabling GPU inference reduced the time to answer a question from about 125 seconds to about 8 seconds.

**Keywords:** retrieval-augmented generation, government documents, hybrid search, reciprocal rank fusion, cross-encoder re-ranking, hallucination mitigation, citation verification, document supersession, optical character recognition, FastAPI, React.

---

## 2. Introduction

### 2.1 Background

Public administration produces legal and regulatory text continuously. In India alone, the Gazette of India, the Central Board of Indirect Taxes and Customs (CBIC), the Reserve Bank of India, SEBI, the Ministry of Corporate Affairs and dozens of ministries and state governments publish notifications and circulars every week. Three properties make this material hard to use:

1. **Volume and format.** Documents are long, formal, and mostly delivered as PDF. Some are scanned images with no selectable text.
2. **Layered change.** A notification may be "issued in supersession of" an earlier one, a circular may "amend" a notification, and an order may "rescind" several older circulars. The rule that applies today is often the result of a chain of documents, and an older document can look authoritative while being obsolete.
3. **Stakes.** A wrong rate, a missed deadline, or reliance on a withdrawn rule has financial and legal consequences.

### 2.2 Problem statement

Design and build a system that lets a person ask natural-language questions about a collection of government PDF documents and receive answers that are (a) **grounded** only in those documents, (b) **cited** to the exact document and page, (c) **checked** against the cited text, (d) **aware of supersession**, and (e) honest about what the documents do not say. The system must run on modest hardware without sending documents to third-party services, and must be suitable for real deployment (authentication, auditing, backups, secure operation).

### 2.3 Why existing approaches fall short

| Approach | Weakness for this problem |
|---|---|
| Keyword search in a PDF reader | Finds words, not meaning; cannot answer a question; ignores which document is current |
| General-purpose chatbots | May invent facts ("hallucinate"), cannot cite the user's documents, send data to an outside service |
| Plain RAG demos (embed, retrieve, generate) | Usually no OCR, no verification of the answer, no awareness of supersession, no access control or auditing |
| Manual research | Slow, error-prone, hard to repeat |

### 2.4 Objectives

1. Ingest digital and scanned PDFs, preserving page numbers for citation.
2. Extract structured metadata (number, date, department, subject, type) automatically.
3. Detect and store relationships between documents (supersedes, amends, references), including references to documents not yet uploaded.
4. Retrieve relevant passages with hybrid search and re-ranking.
5. Generate cited answers with a locally hosted language model, streamed to the user.
6. Verify each answer sentence against its cited sources and warn about superseded documents.
7. Compare two versions of a document sentence by sentence.
8. Provide a modern, accessible web interface, with role-based access control.
9. Make the system deployable and operable: containers, HTTPS, backups, monitoring hooks, automated tests, continuous integration.
10. Help users **find** official documents, by providing a curated directory of sources and a safe import-from-link feature.

### 2.5 Scope

**In scope:** English-language PDF documents; local, single-organisation deployment; text-based question answering, comparison and summarisation.

**Out of scope (see section 15):** multilingual question answering (for example Hindi), per-document permissions, multi-machine scaling, automatic crawling of government websites, and legal advice. GovLens helps people find and read documents; it is not a substitute for checking the official source.

### 2.6 Summary of contributions

- An end-to-end RAG pipeline specialised for government documents, including OCR, rule-based metadata extraction and a relationship (supersession) graph.
- A hybrid retrieval stack: dense vectors + PostgreSQL full-text + reciprocal rank fusion + cross-encoder re-ranking + a relevance threshold that enables honest "I don't know" answers.
- A transparent, explainable **answer verifier** that checks numbers and key words sentence by sentence against cited pages.
- A complete product layer: React interface, authentication and roles, history and feedback, analytics, audit log, saved documents, PDF viewer, comparison, briefs.
- A **safe URL importer** (domain allow-list, private-network blocking, redirect re-validation, size and type enforcement).
- Production engineering: container images, HTTPS, hardened configuration, backups, retention, CI/CD, and measured performance work (CPU to GPU inference).

---

## 3. Background and related concepts

This section explains the ideas the project builds on, so that the design chapters can be read without outside knowledge.

### 3.1 Large language models and hallucination

A large language model (LLM) generates text by predicting the next token. Models are fluent but can state false things with confidence ("hallucination"). For legal text this is unacceptable, so the model must be **constrained** by supplying the source passages and instructing it to answer only from them.

### 3.2 Retrieval-Augmented Generation (RAG)

RAG (Lewis et al., 2020) separates *knowledge* from the *model*: relevant passages are retrieved from a document store at question time and placed in the prompt. Advantages: the knowledge can be updated by adding documents (no retraining), answers can cite sources, and private documents never need to be sent for model training. The quality of a RAG system depends mostly on retrieval quality and on how strictly the generation step is constrained and checked.

### 3.3 Embeddings and vector search

An **embedding model** converts text into a vector so that texts with similar meaning have nearby vectors. GovLens uses `BAAI/bge-small-en-v1.5`, a compact sentence-embedding model (384 dimensions) from the BGE family. Vectors are stored in **Qdrant**, a vector database, which finds the nearest vectors to the question vector using cosine similarity. This **dense retrieval** finds passages that mean the same thing even if they use different words (Karpukhin et al., 2020).

### 3.4 Keyword (lexical) search

Dense retrieval can miss exact identifiers such as "Notification No. 12/2023". Lexical search matches words and is strong for numbers and names. GovLens uses PostgreSQL full-text search (`tsvector`, `ts_rank_cd`, a GIN index) and boosts passages that contain the exact document number mentioned in the question. Classic lexical ranking functions such as BM25 are described by Robertson and Zaragoza (2009).

### 3.5 Hybrid search and reciprocal rank fusion

Dense and lexical results have incompatible score scales, so they cannot simply be added. **Reciprocal Rank Fusion (RRF)** (Cormack et al., 2009) combines *ranks* instead: each result receives `1 / (k + rank)` from each list (GovLens uses `k = 60`), and the sums are sorted. RRF needs no tuning and is robust, which is why it is a common default.

### 3.6 Cross-encoder re-ranking

A **bi-encoder** (the embedding model) encodes the question and each passage separately, which is fast but approximate. A **cross-encoder** reads the question and a passage *together* and outputs a relevance score, which is slower but more accurate (Nogueira and Cho, 2019). GovLens re-scores the fused candidates with `cross-encoder/ms-marco-MiniLM-L-6-v2` and drops passages below a threshold, so questions the documents cannot answer retrieve nothing and the system abstains.

### 3.7 Optical character recognition

Scanned PDFs contain images of pages. **OCR** converts those images to text. GovLens uses Tesseract (Smith, 2007) through `pytesseract`, with `pdf2image` (Poppler) to render pages. OCR is used automatically only when too few pages contain real text.

### 3.8 Supersession and legal lineage

In legal publishing, a newer document may *supersede* (replace) an older one. GovLens models this as a directed graph whose nodes are documents and whose edges are `SUPERSEDES`, `AMENDS` or `REFERENCES`. A document is marked `SUPERSEDED` when some other document supersedes it. When a retrieved source is superseded, the answer shows a warning with the chain to the latest document.

### 3.9 Server-sent events

A normal HTTP response arrives all at once. **Server-sent events (SSE)** let a server push a stream of small messages over one HTTP response. GovLens uses SSE to stream the answer token by token, so the user sees the first words in seconds rather than waiting for the whole answer.

### 3.10 Password hashing and brute-force defence

Passwords must never be stored directly. GovLens uses **scrypt** (Percival, 2009), a memory-hard key-derivation function, with a per-password random salt. To slow guessing it combines a per-IP rate limit on the sign-in endpoint with a per-account lockout.

### 3.11 Server-side request forgery (SSRF)

If a server downloads a URL supplied by a user, an attacker may point it at internal addresses (for example a cloud metadata service) to read private data. This class of attack is SSRF. GovLens's importer defends against it in depth (section 6.10), following the guidance of the OWASP SSRF prevention cheat sheet.

---

## 4. Requirements analysis

### 4.1 Actors

| Actor | Description | Role in the system |
|---|---|---|
| **Viewer** | A reader who asks questions, searches and browses | `VIEWER` |
| **Editor** | Maintains the library: uploads, imports, deletes, edits relationships | `EDITOR` (includes viewer rights) |
| **Administrator** | Manages users, sees analytics, audit log and metrics, runs maintenance | `ADMIN` (includes editor rights) |
| **Service client** | A script using an API key | API key with a role |
| **Operator** | Deploys and maintains the system | Uses Docker, `make`, environment files |

### 4.2 Functional requirements

| ID | Requirement | Implemented in |
|---|---|---|
| F1 | Upload PDF files (single or multiple), with progress | `POST /ingest/upload`, Documents page |
| F2 | Import a PDF from an approved government website by link | `POST /ingest/url`, import dialog |
| F3 | Extract text from digital and scanned PDFs, keeping page numbers | `app/ingestion/pdf_loader.py` |
| F4 | Extract document number, issue date, department, subject, type | `app/metadata`, `app/classification` |
| F5 | Detect supersedes / amends / references relationships, including pending references | `app/supersession/linker.py` |
| F6 | Refuse duplicate documents | SHA-256 hash, HTTP 409 |
| F7 | Hybrid retrieval with re-ranking and a relevance threshold | `app/retrieval` |
| F8 | Answer questions with citations, streamed | `POST /query/stream` |
| F9 | Verify each answer sentence against its cited sources | `app/generation/verification.py` |
| F10 | Warn when a cited document is superseded | `app/services/query.py`, Ask page |
| F11 | Abstain when the documents do not contain the answer | prompt rule + relevance threshold |
| F12 | Compare two documents sentence by sentence, with optional AI summary | `POST /compare`, Compare page |
| F13 | Passage search without AI | `POST /query/search`, Search page |
| F14 | Plain-language brief of a document | `POST /documents/{id}/brief` |
| F15 | View original PDF and extracted page text | `GET /documents/{id}/file`, `/pages/{n}` |
| F16 | Document library: list, filter, search, delete, re-ingest, manual links | `/documents` |
| F17 | Saved documents with private notes | `/bookmarks` |
| F18 | Per-user history; rate answers helpful or not helpful | `/history` |
| F19 | Usage analytics for administrators | `/analytics` |
| F20 | Audit log of sensitive actions | `/audit` |
| F21 | Users and roles; sign-in, sign-out, password change; unlock locked accounts | `/auth`, `/users` |
| F22 | Timeline view of documents | Timeline page |
| F23 | Directory of official government sources, with search tips | Find documents page |
| F24 | Export answers and comparisons as Markdown; print comparisons | front end |
| F25 | Background ingestion with retries and status | `app/services/jobs.py` |

### 4.3 Non-functional requirements

| Category | Requirement | How it is met |
|---|---|---|
| **Privacy** | Documents and questions stay on the operator's machine | Local embedding model, local Ollama LLM, local databases |
| **Accuracy** | Reduce hallucination; make remaining risk visible | Constrained prompt, threshold abstention, sentence verifier, citations |
| **Security** | Authenticated access, least privilege, resistance to common attacks | Roles, scrypt, lockout, rate limits, CSP, SSRF protection, audit log |
| **Performance** | Interactive answers on modest hardware | Streaming, GPU option, model warm-up, caching of briefs |
| **Reliability** | Survive crashes and partial failures | Compensating deletes, reconciliation, job retries, health checks |
| **Operability** | Easy to deploy, observe and back up | Docker Compose, Makefile, metrics, structured logs, daily backups |
| **Maintainability** | Understandable, testable code | Layered design, interfaces and dependency injection, 274 tests, type-checked front end |
| **Usability** | Clear, accessible interface | Responsive layout, dark mode, keyboard shortcuts, ARIA labels, empty-state guidance |
| **Portability** | Run on Linux, macOS, Windows through Docker | Container images, optional GPU override |

### 4.4 Use cases (summary)

1. **Ask a question.** A viewer asks "What was the GST rate on packaged food in 2023 and what is it now?". The system retrieves from both notifications, warns that 12/2023 is superseded by 25/2024, and answers with citations that open the source page.
2. **Add a document.** An editor pastes a link from `cbic.gov.in`. The importer validates and downloads the PDF; a background job ingests it; the document appears in the library with extracted metadata and relationships.
3. **Compare versions.** A viewer opens notification 25/2024 and chooses "Compare with 12/2023". The system shows added, removed and changed sentences with page numbers and an AI summary limited to those changes.
4. **Audit and administer.** An administrator reviews the audit log, unlocks a user locked out by failed sign-ins, and reads the analytics page to find questions that were answered without sources.

---

## 5. System architecture

### 5.1 Logical architecture

```text
                          +-------------------------------+
                          |  Browser (React single-page   |
                          |  app: Ask, Search, Documents, |
                          |  Compare, Admin, ...)         |
                          +---------------+---------------+
                                          | HTTPS (REST + Server-Sent Events)
                                          v
                +-------------------------+--------------------------+
                |  Caddy reverse proxy (production): TLS, headers    |
                +-------------------------+--------------------------+
                                          |
                                          v
        +---------------------------------+------------------------------------+
        |                    FastAPI application (Gunicorn + Uvicorn workers)     |
        |                                                                        |
        |  API layer: routes, schemas, auth/roles, rate limits, error handlers   |
        |  Service layer: ingestion, query, comparison, brief, history, audit,   |
        |                 bookmarks, URL import, jobs, retention                 |
        |  Domain modules: loaders, metadata, classification, chunking,          |
        |                  retrieval, citations, supersession, generation,       |
        |                  verification, comparison                              |
        |  Background: ingestion workers, retention loop, model warm-up          |
        +-----+---------------------+--------------------+----------------+-----+
              |                     |                    |                |
              v                     v                    v                v
      +-------+------+     +--------+-------+    +-------+------+   +-----+--------+
      | PostgreSQL   |     |   Qdrant       |    |   Ollama     |   | Local files  |
      | metadata,    |     | vector index   |    | LLM (qwen3   |   | uploaded     |
      | chunks, FTS, |     | (cosine)       |    | 4B instruct) |   | PDFs         |
      | users, logs  |     |                |    |  CPU or GPU  |   |              |
      +--------------+     +----------------+    +--------------+   +--------------+
```

### 5.2 Why these components

| Choice | Reason |
|---|---|
| **FastAPI** | Type-driven request validation (Pydantic), automatic OpenAPI documentation, first-class streaming responses, dependency injection |
| **PostgreSQL** | Reliable relational store for metadata, relationships, users and logs; built-in full-text search with GIN indexes; transactions |
| **Qdrant** | Purpose-built vector database with filtering and cosine search; simple to run in Docker |
| **Two stores** | Vectors and relational data have different access patterns. Relational data is the *source of truth*; vectors are a *derived index* that can be rebuilt from stored chunk text (the system includes a reconciliation job that does exactly this) |
| **Ollama** | Runs open-weight LLMs locally behind a simple HTTP API; supports CPU and GPU; keeps documents private |
| **`qwen3:4b-instruct`** | A small instruction-tuned model that fits in 16 GB RAM and a 4 GB GPU; adequate for grounded answering because the prompt supplies the facts |
| **`bge-small-en-v1.5`** | Small (384-dim) and fast on CPU, with good English retrieval quality |
| **React + TypeScript + Vite** | Mature ecosystem, type safety across the API boundary, fast builds |
| **Tailwind CSS** | Utility-first styling with design tokens, easy light and dark themes |
| **TanStack Query** | Caching, request de-duplication and background refetching for server state |
| **Docker Compose** | One-command reproducible environment for several services |
| **Caddy** | Automatic HTTPS certificates with a tiny configuration |

### 5.3 Technology stack and versions

**Back end** (from `requirements.txt`): Python 3.12; FastAPI 0.104.1; Uvicorn 0.24.0 with Gunicorn 23.0.0; Pydantic 2.5.0 and pydantic-settings 2.1.0; SQLAlchemy >= 2.0.35; Alembic 1.13.1; psycopg2-binary 2.9.9; qdrant-client 1.18.0; httpx 0.25.2; python-multipart 0.0.6; PyMuPDF 1.24.14; sentence-transformers >= 5.0.0; PyTorch >= 2.7.0; pdf2image; pytesseract; pytest 7.4.3.

**Front end** (from `frontend/package.json`): React 18.3; React Router 6.28; TanStack Query 5.62; react-markdown 9 with remark-gfm 4; lucide-react (icons); clsx; Vite 5.4; Tailwind CSS 4.3; TypeScript 5.6.

**Infrastructure:** PostgreSQL 16; Qdrant (v1.12.4 in production compose); Ollama (0.5.4 in production compose); Caddy 2.8; Docker and Docker Compose.

### 5.4 Layered code organisation

The back end follows a layered structure (about 103 Python files, 9,287 lines):

| Layer | Directory | Responsibility |
|---|---|---|
| API | `app/api` | HTTP routes, request/response schemas, authentication and roles, rate limiting, health |
| Services | `app/services` | Use-case orchestration: ingestion, query, comparison, brief, history, audit, bookmarks, URL import, jobs, retention, auth, documents |
| Domain | `app/ingestion`, `app/metadata`, `app/classification`, `app/chunking`, `app/retrieval`, `app/citations`, `app/supersession`, `app/generation`, `app/comparison`, `app/vectorstore` | The algorithms; each behind an interface so it can be replaced or faked in tests |
| Persistence | `app/models`, `app/repositories`, `app/db`, `alembic` | SQLAlchemy models, repositories, session management, migrations |
| Cross-cutting | `app/core` | Configuration, logging, metrics, text utilities, constants |
| Entry point | `app/main.py` | Application factory, middleware, startup tasks, static front end |

**Design principles used:** dependency injection through interfaces (Python `Protocol` classes) so that services are tested with fakes; heavy objects (models, clients) are process-wide singletons while database sessions are per request; configuration only through environment variables; failure of an optional feature (logging, auditing, reranking) must never break the main action.

### 5.5 Request lifecycle

1. The browser sends a request with `Authorization: Bearer <token>`.
2. A middleware assigns a request id, measures latency for Prometheus metrics, and adds security headers to the response.
3. The security dependency resolves the caller to a *principal* (user or API key), applies the **per-identity rate limit**, and enforces the **required role**.
4. The route validates the body with Pydantic and calls a service.
5. Domain exceptions (not found, duplicate, ambiguous, path not allowed, LLM unavailable) are mapped to precise HTTP statuses by global exception handlers; unexpected errors return a generic message plus a request id that matches the server log, so internals are never leaked.

---

## 6. Detailed design of the back end

### 6.1 Document ingestion pipeline

```text
Upload / import / path
  -> AutoPDFLoader (PyMuPDF; OCR when < 50% of pages contain text)
  -> SHA-256 hash  -> duplicate? -> HTTP 409 with the existing document id
  -> RuleBasedMetadataExtractor (number, date, department, subject, mentions)
  -> RuleBasedDocumentClassifier
  -> insert documents row
  -> RuleBasedDocumentChunker (page-preserving chunks) -> insert document_chunks
  -> DocumentRelationshipLinker (references -> relationships, statuses)
  -> embedding windows -> HuggingFaceEmbeddingProvider -> Qdrant upsert
  -> commit
  on any failure: roll back the database and delete the document's vectors
```

**Loading and OCR (`app/ingestion/pdf_loader.py`).** PyMuPDF extracts text page by page, with one-based page numbers (matching how citations are written). A page counts as "textful" if it has at least 50 characters. If fewer than half of the pages are textful, the file is treated as scanned and re-read with `pdf2image` (Poppler renders each page) and Tesseract. The reading is done once, and OCR is only paid for when needed.

**Duplicate detection.** The SHA-256 hash of the file is stored with a uniqueness constraint. Re-uploading the same file returns HTTP 409 with the id of the existing document, instead of silently creating a copy.

**Metadata extraction (`app/metadata`).** A deterministic, regular-expression extractor (`patterns.py`) finds:
- the **document number** after "Notification No.", "Circular No.", "Order No." or "F. No." (for example `12/2023`, `04/2025-GST`);
- the **issue date** in four formats (`1 April 2023`, `1 Apr 2023`, `01-04-2023`, `2023-04-01`);
- the **subject** line (`Subject: ...`);
- the **department** (`Ministry of ...`, `Department of ...`, `Central Board of ...`);
- **mentions of other documents**, including the long form ("Notification of the Government of India, No. 12/2023") and lists ("Notifications Nos. 1/2020, 2/2020 and 3/2020").

Because regular expressions miss unusual formats, an optional **LLM fallback** asks the model only for fields that the patterns missed, and a field is **kept only if its value can be verified in the document text** (for example, a returned document number must literally appear in the text). This keeps the benefit of the model without trusting it.

**Classification (`app/classification`).** Ordered patterns assign `NOTIFICATION`, `CIRCULAR`, `ORDER` (confidence 0.95, because the document names itself), then weaker patterns `GAZETTE`, `REPORT`, `POLICY`, `ADVISORY` (0.80), otherwise `UNKNOWN`. A weak word counts only if it appears in the document heading (first 1,200 characters) or is used repeatedly, to avoid classifying a circular as a "policy" because of a passing mention.

**Chunking (`app/chunking/chunker.py`).** Chunks are 500 to 1,000 tokens, measured with the embedding model's own tokenizer, with one-sentence overlap, and **never cross a page boundary**. Page preservation is what makes exact page citations possible. Because the embedding model and the re-ranker read at most 512 tokens, a longer chunk is split into **400-token windows with 50-token overlap** for embedding and scoring (`app/chunking/tokens.py`, `app/vectorstore/windows.py`), so no part of a chunk is invisible to search.

**Embedding and storage.** `BAAI/bge-small-en-v1.5` (loaded once per process, thread-safe) produces 384-dimension vectors, stored in the Qdrant collection `government_documents` with a payload containing the document id, number, type, page and chunk index.

**Transactional safety.** Two stores cannot share one transaction, so the service uses a **compensating action**: if anything fails after vectors were written, the database transaction is rolled back and the vectors for that document are deleted. A **reconciliation** routine (run at startup in the background and available to administrators) removes vectors whose document no longer exists and **rebuilds vectors for documents that have chunks but no vectors**, from the stored chunk text.

### 6.2 Relationship and supersession graph

Documents refer to each other in standard phrases. `DocumentRelationshipLinker` (`app/supersession/linker.py`) and the extractor classify each mention using the **clause around it**:

| Phrase pattern | Relationship |
|---|---|
| "in supersession of X", "X is hereby rescinded / withdrawn / superseded" | `SUPERSEDES` |
| "amends X", "amendment to X" | `AMENDS` |
| any other mention of "Notification No. X" | `REFERENCES` |

Lists are handled ("Circulars Nos. 1/2019 and 2/2019 are hereby withdrawn"), and clause boundaries prevent "in supersession of A, and under B" from marking B as superseded.

Every mention is stored in `document_references`, resolved or **pending**. When a referenced document is uploaded **later**, the linker resolves the pending mention and creates the edge, so upload order does not matter. Document numbers are normalised (case and spaces ignored) before matching. When a `SUPERSEDES` edge exists, the older document's status becomes `SUPERSEDED`; deleting the newer document makes the older one `ACTIVE` again. Editors can add manual links (marked `MANUAL`), which survive re-ingestion.

`DatabaseSupersessionEngine` (`app/supersession/engine.py`) follows `SUPERSEDES` edges to the **latest document in the chain**, with cycle protection (visited-set), and returns the chain. At question time this is evaluated for **each distinct retrieved document**, not only the first.

**Worked example from the project's sample set.** Notification 25/2024 says "In supersession of the Notification No. 12/2023", so a `SUPERSEDES` edge 25/2024 to 12/2023 is created and 12/2023 becomes `SUPERSEDED`. Circular 4/2024 "amends the Notification No. 25/2024" (an `AMENDS` edge). Order 7/2024 references Circular 4/2024 and withdraws Circulars 1/2019 and 2/2019 and rescinds Order 3/2018, which are not uploaded, so they remain **pending** references until those documents arrive.

### 6.3 Retrieval

`HybridDocumentRetriever` (`app/retrieval/hybrid.py`):

1. **Dense search.** Embed the question with the same model; ask Qdrant for `top_k x 3` candidates (the *candidate multiplier*).
2. **Keyword search.** PostgreSQL full-text search over the stored `tsvector` column (GIN index), ranked with `ts_rank_cd`, plus a **boost for chunks containing a document number that appears in the question** (so "Notification 12/2023" finds that document even when the semantic embedding is vague).
3. **Fusion.** Reciprocal Rank Fusion with `k = 60`.
4. **Re-ranking.** A cross-encoder (`ms-marco-MiniLM-L-6-v2`) re-scores the merged candidates; scores are normalised to 0 to 1.
5. **Threshold.** Chunks scoring below `RERANKER_MIN_SCORE` (default 0.01) are dropped. If nothing remains, the system answers "The provided documents do not contain information about this." and **does not call the language model at all**, which both saves time and prevents invented answers.
6. **Filtering.** The user can restrict a question to chosen document numbers.

If the re-ranker model cannot be loaded, reranking is disabled gracefully and retrieval still works (reported as an informational check on the readiness endpoint).

### 6.4 Answer generation

`QueryService` orchestrates retrieval, grouping (`ComparisonEngine` groups chunks by document and page, most relevant first), citation building (`CitationBuilder`), supersession checks, prompt building and generation.

**Prompt (`app/generation/prompt_builder.py`).** The prompt starts "You are a retrieval-grounded document assistant" and lists strict numbered rules: use only the provided sources; tag each claim with the source tag `[S1]`, `[S2]`...; if the answer is not explicitly in the sources, reply exactly with the no-answer sentence; no commentary about the sources or rules; and, when any retrieved document is superseded, mention which newer document replaces it. Each source is printed with its tag, document number, page and text.

**Citations.** `[S#]` tags in the answer are matched to the retrieved sources. Only the sources the answer actually used are listed; if the model cited nothing valid, all retrieved sources are listed and the result is flagged `citations_inferred`. The model produces the *tags*; the citation *details* (document, page, quoted text) are built by deterministic code, so the model cannot invent a page number.

**Local LLM client (`app/generation/ollama_client.py`).** Calls Ollama's `/api/generate` with temperature 0 (deterministic) and `think: false`, a bounded `num_predict` (512 tokens), one retry if the model process dies, metrics for latency and outcomes, a `generate_stream` method for streaming, and `warm_up()` to load the model into memory at start-up (skipped when `OLLAMA_KEEP_ALIVE=0`).

**Streaming protocol.** `POST /query/stream` returns `text/event-stream` with events `retrieval` (counts and supersession warnings), many `token` events, a `done` event with the full result, then a `saved` event with the history id, and an `error` event if generation fails part way. Retrieval and the supersession check run before streaming starts, so database reads finish while the request session is open.

### 6.5 Answer verification (hallucination mitigation)

After generation, `verify_answer` (`app/generation/verification.py`) checks **every sentence** of the answer against the pages it cites. The method is deliberately simple and explainable rather than another model:

1. **Numbers.** Every number in the sentence (rates, amounts, dates, document numbers) must appear in the cited pages. Wrong numbers are the costliest error in legal text.
2. **Word overlap.** At least **50%** of the sentence's *content words* (stop-words removed, light stemming) must appear in the cited pages.
3. **Uncited sentences** are reported as `UNCITED`.

Each sentence gets a status (`SUPPORTED`, `UNSUPPORTED`, `UNCITED`) and a reason. The report (`checked`, `supported`, `unsupported`, `uncited`, `all_supported`) is returned with the answer and shown in the interface as "All statements trace back to the sources" or "N statement(s) need a closer look". **What it means:** a failure reliably flags statements a human should verify; a pass shows the evidence is present but does *not* prove the conclusion is correct. This limitation is stated openly in the documentation and in the interface.

### 6.6 Document comparison

`DocumentDiffer` (`app/comparison/differ.py`) compares two documents **sentence by sentence**:

1. Both documents are rebuilt from stored chunks as page-tagged sentences (an abbreviation-aware splitter avoids splitting at "No." or "Rs.").
2. A normalised key per sentence is compared with Python's `difflib.SequenceMatcher` (`autojunk=False`).
3. Replaced blocks are paired by similarity; a pair above **0.4** similarity is reported as `MODIFIED` (with the similarity), otherwise as one `REMOVED` plus one `ADDED`.
4. The result has counts (added, removed, modified, unchanged) and the page of each side.

The optional **AI summary** receives *only the detected changes* (not the whole documents) and must cite their pages, so it cannot describe differences the deterministic diff did not find. The stored relationship (for example "target SUPERSEDES base") is returned too. The interface can export the comparison as Markdown or print it.

*Example:* comparing 12/2023 with 25/2024 reports 1 added, 0 removed, 6 modified and 3 unchanged sentences (measured on the sample documents).

### 6.7 Plain-language document brief

`BriefService` (`app/services/brief.py`) writes a short brief of one document with sections *In one sentence*, *Who is affected*, *What changes or must be done*, *Deadlines and dates*, *Penalties or consequences*. The model sees only the first 7,000 characters (page-tagged) so it fits the context window; the prompt forbids outside knowledge and requires "Not stated" for missing facts. The response states whether the brief covers all pages or only the first N. Briefs are **cached** per document version (keyed by id and `updated_at`, LRU of 128). Measured: about 18 seconds the first time, 0.1 seconds from cache.

### 6.8 Background ingestion jobs

Uploading with `background=true` returns immediately with a job id. `IngestionJobRunner` (`app/services/jobs.py`) runs worker threads that **claim the oldest `PENDING` job with a conditional `UPDATE`** (so several workers or processes never take the same job), run ingestion, and record the result. Jobs interrupted by a crash are re-queued at startup, **up to 3 attempts**, then marked failed with the error. A job whose file is gone fails immediately. The interface polls job status and refreshes the library when jobs finish.

### 6.9 Query history, feedback and analytics

Every answered question is stored in `query_logs` with the **full result** (so a past answer can be reopened exactly), counts of supported and unsupported statements, latency, and the user's feedback (helpful, not helpful, optional note). `HistoryService` provides per-user history (private: filtered by username), search, deletion, and feedback. `analytics()` (administrators only) computes totals, unique users, share of answers that had sources, average and 95th-percentile latency, satisfaction, share of verified statements, questions per day, most cited documents, and a **"worth a look" list** (answers that were rated not helpful, had no sources, or had unsupported statements), which usually reveals a missing document. Recording a history row **never raises**: logging must not break answering.

### 6.10 Safe import from a URL (SSRF defence)

`app/services/url_import.py` downloads a PDF from a link, with these layered controls:

| Control | Detail |
|---|---|
| Scheme and credentials | Only `http` and `https`; no `user:pass@` in URLs |
| Ports | Only 80 and 443 |
| **Domain allow-list** | The host must equal or be a subdomain of an approved domain (`IMPORT_ALLOWED_DOMAINS`, defaults include `gov.in`, `nic.in`, `rbi.org.in`, `sansad.in`, `gov.uk`, `europa.eu`, `federalregister.gov`, `govinfo.gov`, ...). A suffix trick such as `evilgov.in` does not match. `*` allows any public host |
| **Private-network blocking** | The host is resolved and **every** address must be globally routable. Loopback, private, link-local (including the 169.254.169.254 cloud-metadata address) and reserved ranges are refused. Literal IP addresses are checked directly |
| **Connected-peer check** | After connecting, the address actually connected to is checked again (defends against DNS changing between check and use) |
| **Redirects** | Followed manually, at most 5, and **each hop is validated again**; a redirect to a non-approved or private address is refused |
| Size and type | Body capped at `MAX_UPLOAD_MB` (50), checked while streaming; the first bytes must be `%PDF-` (a web page saved as `.pdf` is rejected) |
| Slow generators | Some sites answer HTTP 202 while building a PDF; the importer waits and retries (up to 4 times, 3 seconds apart) |
| Cleanup | A rejected download leaves no file behind |

The route maps failures to exact statuses (403 not allowed, 415 not a PDF, 413 too large, 502 download failed). 24 automated tests cover this module, including private-IP, redirect, size and loop cases. Live checks confirmed `127.0.0.1`, `169.254.169.254`, `localhost`, `example.com` and `file://` are all refused, and a real PDF from `govinfo.gov` was downloaded, indexed (171 passages) and classified.

### 6.11 Bookmarks, original PDF and audit log

- **Bookmarks** (`app/services/bookmarks.py`): a user saves a document and keeps a private note (up to 4,000 characters), unique per user and document, removed automatically if the document is deleted.
- **Original PDF** (`GET /documents/{id}/file`): serves the stored file inline with `nosniff`, but **only if the resolved path lies inside an allowed folder** (upload directory or the ingest allow-list), so a tampered path cannot expose arbitrary files; verified by tests that try paths outside, missing paths and `..` traversal.
- **Audit log** (`app/services/audit.py`): an append-only table recording who did what and when: `auth.login`, `auth.login_failed`, `auth.locked`, `auth.password_changed`, `document.upload`, `document.import_url`, `document.delete`, `document.reingest`, `index.reconcile`, `user.create`, `user.update`, `user.delete`. Administrators can filter and search it. Writing an audit entry never raises.

### 6.12 Maintenance: reconciliation, retention, warm-up

- **Reconciliation:** described in 6.1; runs at start-up and on demand.
- **Retention** (`app/services/retention.py`): a daily background job deletes stored questions older than `QUERY_LOG_RETENTION_DAYS` (default 90) and audit entries older than `AUDIT_LOG_RETENTION_DAYS` (default 365); 0 keeps everything.
- **Model warm-up:** at start-up a background thread loads the language model so the first user does not wait for a multi-minute cold load (measured 160 to 225 seconds on the development laptop).

---

## 7. Database design

### 7.1 Overview

PostgreSQL holds 11 application tables plus Alembic's `alembic_version`. Primary keys are UUIDs. Schema changes are versioned with **6 Alembic migrations**, so any environment can be created or upgraded with `alembic upgrade head`.

### 7.2 Entity relationships

```text
users 1---* auth_tokens                      documents 1---* document_chunks
users 1---* query_logs   (user_id, SET NULL) documents 1---* document_references
users 1---* ingestion_jobs (submitted_by)    documents *---* documents  (document_relationships)
documents 1---* bookmarks (CASCADE)          rate_limit_windows (independent)
audit_logs (independent, append-only)
```

### 7.3 Tables

**`documents`**: one row per document.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| title | varchar | Extracted subject, or file name |
| document_number | varchar | For example `12/2023`; indexed, normalised for matching |
| document_type | varchar | `NOTIFICATION`, `CIRCULAR`, `ORDER`, `GAZETTE`, `POLICY`, `ADVISORY`, `REPORT`, `UNKNOWN` |
| issue_date, effective_date | date | Nullable |
| department, subject | varchar | |
| source_url | text | Local path of the stored PDF |
| file_name | varchar | Original file name |
| file_hash | varchar | SHA-256, **unique** (duplicate detection) |
| status | varchar | `ACTIVE`, `SUPERSEDED`, `ARCHIVED` |
| created_at, updated_at | timestamptz | |

**`document_chunks`**: passages of text.

| Column | Type | Notes |
|---|---|---|
| id, document_id | uuid | FK to documents (cascade) |
| chunk_index, page_number | integer | Page is one-based |
| chunk_text | text | |
| token_count | integer | |
| search_vector | tsvector | **Generated column**, `to_tsvector('english', chunk_text)`, with a **GIN index** |

**`document_relationships`**: directed edges (`source_document_id`, `target_document_id`, `relationship_type` in `SUPERSEDES`, `AMENDS`, `REFERENCES`, `origin` in `AUTO`, `MANUAL`).

**`document_references`**: every mention found in a document's text (`referenced_number`, raw form, type, relationship type, `resolved_document_id` nullable). Unresolved rows are the **pending references**.

**`ingestion_jobs`**: `status` (`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`), `file_path`, `original_filename`, `document_id`, `error`, `attempts`, `submitted_by`, timestamps.

**`users`**: `username` (unique, case-insensitive), `password_hash` (scrypt), `role` (`VIEWER`, `EDITOR`, `ADMIN`), `is_active`, `created_at`, `last_login_at`, `failed_attempts`, `locked_until`.

**`auth_tokens`**: `user_id`, `token_hash` (**SHA-256 of the token; the token itself is never stored**), `created_at`, `expires_at`.

**`rate_limit_windows`**: (`identity`, `window_start`, `count`), shared by all workers.

**`query_logs`**: `user_id`, `username`, `question`, `answer_markdown`, `result` (JSON of the full answer), `source_count`, `supported_count`, `unsupported_count`, `latency_ms`, `feedback` (1, -1, null), `feedback_note`, `created_at`.

**`bookmarks`**: `username`, `document_id`, `note`, timestamps; unique on (`username`, `document_id`).

**`audit_logs`**: `created_at`, `username`, `action`, `target`, `detail`, `ip`; indexed on time and action.

### 7.4 Vector store

Qdrant collection `government_documents`, cosine distance, 384-dimension vectors; payload carries `document_id`, `document_number`, `document_type`, `page_number`, `chunk_index`, text and metadata. Vectors can always be rebuilt from `document_chunks`.

### 7.5 Migrations

| Revision | Purpose |
|---|---|
| `20260612_0001` | Initial document domain tables |
| `20261106_0002` | References, ingestion jobs, nullable issue date, full-text index |
| `20261106_0003` | Users, sessions, rate limits, job attempts, relationship origin, stored `search_vector` |
| `20261115_0004` | `query_logs` (history, feedback, analytics) |
| `20261115_0005` | `bookmarks`, `audit_logs` |
| `20261115_0006` | Account lockout columns on `users` |

---

## 8. API design

### 8.1 Conventions

- Base path `/api/v1`; JSON requests and responses; UUID identifiers.
- Authentication with `Authorization: Bearer <session token or API key>`.
- Errors: `{"detail": "..."}` with a precise status (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 502, 503). Duplicate and ambiguous document errors include the offending ids. Unexpected errors add a `request_id` that matches the server log.
- Every response carries `X-Request-ID`. Rate-limit rejections return 429 with `Retry-After`.
- Interactive documentation is generated automatically at `/docs` (Swagger UI) and `/openapi.json`.

### 8.2 Endpoint reference (42 endpoints)

Role column: **P** public, **V** viewer, **E** editor, **A** admin.

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/health` | P | Liveness |
| GET | `/health/ready` | P | Readiness: database, Qdrant, Ollama (model present), reranker (informational) |
| POST | `/auth/login` | P | Exchange username and password for a session token (per-IP rate limited, account lockout) |
| POST | `/auth/logout` | V | Invalidate the session token |
| GET | `/auth/me` | V | Current user |
| POST | `/auth/password` | V | Change own password (signs out all sessions) |
| POST | `/ingest` | E | Ingest a PDF already on the server (path must be inside an allowed folder) |
| POST | `/ingest/upload` | E | Upload a PDF; `?background=true` queues a job |
| POST | `/ingest/url` | E | Import a PDF from an approved website; queues a job |
| GET | `/ingest/url/allowed-domains` | V | Domains the importer accepts |
| POST | `/ingest/jobs` | E | Queue a server-side file |
| GET | `/ingest/jobs` | V | List jobs (filter by status) |
| GET | `/ingest/jobs/{id}` | V | One job |
| POST | `/query` | V | Answer a question (complete response) |
| POST | `/query/stream` | V | Answer as server-sent events |
| POST | `/query/search` | V | Ranked passages without AI |
| POST | `/compare` | V | Compare two documents (id or number) with optional AI summary |
| GET | `/documents` | V | List with pagination, type, status, and text search |
| GET | `/documents/{id}` | V | Detail with page count, lineage (incoming and outgoing edges), pending references |
| GET | `/documents/{id}/pages/{n}` | V | Stored text of one page |
| GET | `/documents/{id}/file` | V | Original PDF, inline |
| POST | `/documents/{id}/brief` | V | Plain-language brief (cached; `?refresh=true`) |
| DELETE | `/documents/{id}` | E | Delete document, chunks, vectors, links |
| POST | `/documents/{id}/reingest` | E | Re-run ingestion from the stored file |
| POST | `/documents/{id}/relationships` | E | Add a manual relationship |
| DELETE | `/documents/relationships/{id}` | E | Remove a relationship |
| POST | `/documents/reconcile` | A | Rebuild missing vectors, remove orphans |
| GET | `/history` | V | Own questions (search, pagination) |
| GET | `/history/{id}` | V | One saved answer |
| DELETE | `/history/{id}`, `/history` | V | Delete one entry, or clear all |
| POST | `/history/{id}/feedback` | V | Rate an answer |
| GET | `/bookmarks` | V | Saved documents |
| PUT | `/bookmarks/{document_id}` | V | Save or update a note |
| DELETE | `/bookmarks/{document_id}` | V | Remove |
| GET | `/analytics` | A | Usage analytics (7 to 180 days) |
| GET | `/audit` | A | Audit log with filters |
| GET | `/users` | A | List users |
| POST | `/users` | A | Create a user |
| PATCH | `/users/{id}` | A | Change role, active flag, password, or unlock |
| DELETE | `/users/{id}` | A | Delete a user |
| GET | `/metrics` | A | Prometheus metrics |

### 8.3 Streaming answer example

```text
event: retrieval
data: {"retrieved_chunks": 2, "documents": 2, "supersession_warnings": [{"document_number": "12/2023", "is_superseded": true, ...}]}

event: token
data: {"text": "The"}

event: token
data: {"text": " GST"}

... more tokens ...

event: done
data: {"query": "...", "answer_markdown": "...", "sources": [...], "verification": {...}}

event: saved
data: {"id": "a0aac7f7-..."}
```

### 8.4 Role enforcement

Each router declares its minimum role through dependencies (`require_viewer`, `require_editor`, `require_admin`). Roles are cumulative (`VIEWER` < `EDITOR` < `ADMIN`). With authentication disabled (development only) every request is treated as an administrator, and the production configuration guard refuses to start in that mode.

---

## 9. Front-end design

### 9.1 Overview

The front end is a single-page application in `frontend/` (about 2,600 lines of TypeScript and TSX in 31 files). In production, FastAPI serves the compiled files from `frontend/dist` and falls back to `index.html` for client-side routes; unknown `/api/` paths still return 404 JSON. The original single-page interface remains available at `/legacy`.

### 9.2 Architecture

| Concern | Approach |
|---|---|
| Routing | React Router; heavier pages are **lazy-loaded** into separate JavaScript chunks (code splitting) |
| Server state | TanStack Query: caching, de-duplication, polling for background jobs, invalidation after mutations |
| Authentication | `AuthProvider` context; token in browser storage; a global 401 handler returns the user to sign-in; `can(role)` hides what a role cannot do |
| API client | One typed module (`lib/api.ts`); types mirror the server's response models (`lib/types.ts`) |
| Streaming | `fetch` with a stream reader that parses server-sent events (so the bearer token can be sent, which the browser's `EventSource` cannot do) |
| Styling | Tailwind CSS with design tokens as CSS variables; light and dark themes; respects `prefers-reduced-motion` |
| Markdown | `react-markdown` (no raw HTML is rendered, which removes a class of injection risks) |
| Charts | Hand-written SVG (area chart, bars, lineage graph) with no charting dependency |

### 9.3 Pages and components

| Page | What it provides |
|---|---|
| **Sign in** | Branded form with feature highlights; clear error messages |
| **Overview** | Statistics (documents, passages, superseded, queued jobs), recent documents, system health, documents by type, recent ingestion, "taking effect soon" and "recently superseded" cards, and a getting-started guide when the library is empty |
| **Ask** | Chat-style, streaming answers; clickable `[S1]` citations opening a source panel with the exact passage and page; supersession warnings; verification report; sources list; copy, export, regenerate; thumbs up or down; history sidebar; options to set passages read and restrict to chosen documents; deep links (`/ask?q=...&doc=...`); a notice when a web-search query (`site:`, `filetype:`) is typed; a hint to find and import documents when no sources are found |
| **Search** | Hybrid passage search without AI, term highlighting, relevance bars, "Ask AI about this" |
| **Documents** | Search, type and status filters, pagination, drag-and-drop multi-file upload, import from link, live job progress, failed-job messages |
| **Document view** | Metadata; **lineage graph** (SVG); **plain-language brief**; **page text** and **original PDF** tabs; save with private note; compare shortcuts; re-ingest and delete (editors) |
| **Compare** | Two selectors, optional focus topic, counts, side-by-side changes with filters, AI summary, **Markdown export and print/PDF** |
| **Timeline** | Documents grouped by issue month, with status and effective date; filters |
| **Saved** | Bookmarked documents with notes |
| **Find documents** | About 120 official sources, region and category filters, search, step-by-step guide, ready-made web-search queries with an "Open in Google" button, import-by-link |
| **Analytics** (admin) | KPI tiles, questions per day, most cited documents, "worth a look" list |
| **Admin** | Users and roles, locked-account unlock, audit log, ingestion jobs, reconcile, change password |
| **Command palette** (Ctrl or Cmd + K) | Jump to any page, find documents, start a question |
| **Shortcuts help** (`?`) | List of keyboard shortcuts |

### 9.4 Usability and accessibility

Responsive layout from phone to desktop; dark and light themes with system preference; keyboard navigation and shortcuts; visible focus rings; labels and ARIA attributes (`role="alert"`, `aria-live` toasts, `aria-pressed` toggles, `aria-label` on icon buttons); loading skeletons and empty states with next steps; reduced-motion support; error messages written for users.

### 9.5 Performance

Code splitting (the Ask page is about 19 kB, the main bundle about 75 kB gzipped), cached server state, debounced searches, lazy-loaded PDF blobs, and cached briefs.

---

## 10. Security design

### 10.1 Threat model and controls

| # | Threat | Control |
|---|---|---|
| 1 | Unauthorised access | Mandatory authentication; hashed session tokens (SHA-256) with 12-hour expiry; cumulative roles checked on every route |
| 2 | Password theft from the database | scrypt hashing with per-password salt; constant-time comparison; dummy hash for unknown users (equal response time) |
| 3 | Credential guessing | Per-IP sign-in rate limit (10 per minute); per-account **lockout** (5 failures, 15 minutes) that returns the same generic error; admin unlock; 10-character minimum, common-password and username checks |
| 4 | Abuse and denial of service | Per-identity sliding-window rate limit shared across workers through PostgreSQL; upload size limit (50 MB); request body limit in the proxy; bounded LLM output |
| 5 | SSRF through URL import | Section 6.10 |
| 6 | Reading arbitrary server files | Path-based ingestion restricted to allowed folders; PDF serving checks the resolved path is inside allowed folders |
| 7 | Cross-site scripting | Markdown rendered without raw HTML; strict **Content-Security-Policy** (`script-src 'self'`); no inline scripts in the built page |
| 8 | Clickjacking and sniffing | `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff` |
| 9 | Cached sensitive data | `Cache-Control: no-store` on API responses |
| 10 | Transport security | HTTPS through Caddy; HSTS header in production |
| 11 | Leaking internals | Generic 500 messages with a request id; debug mode never enabled in the framework; secrets only from environment |
| 12 | Insecure defaults in production | **Startup guard** refuses to start in production if authentication is off, debug is on, passwords or keys are defaults or weak, CORS is `*`, rate limiting is off, or the admin password violates the policy |
| 13 | Unnoticed misuse | Append-only **audit log** of sensitive actions |
| 14 | Data exposure over time | Retention jobs delete old questions and audit entries |
| 15 | Container compromise | Read-only root file system, all Linux capabilities dropped, `no-new-privileges`, non-root user, internal-only database network |
| 16 | Vulnerable dependencies | Dependabot update PRs; pinned versions; CI |

### 10.2 Residual risks (stated honestly)

The session token is kept in the browser's storage, which a cross-site-scripting flaw could read; the strict CSP and absence of raw HTML mitigate but do not eliminate this (HTTP-only cookies would be stronger). There are no per-document permissions and no multi-factor authentication. Verification flags unsupported statements but cannot prove correctness.

---

## 11. Deployment and operations

### 11.1 Environments

| Environment | Files | Purpose |
|---|---|---|
| **Development** | `docker-compose.yml` | Postgres 16, Qdrant, Ollama, and the app with the source folder mounted and `--reload` |
| **GPU (optional)** | `docker-compose.gpu.yml` | Gives the Ollama container the NVIDIA GPU by passing device files and host driver libraries (works without the NVIDIA container toolkit); also enables flash attention and a quantised KV cache and a 30-minute model keep-alive |
| **Production** | `docker-compose.prod.yml`, `Caddyfile`, `.env.production` | Caddy (HTTPS), hardened app, internal-only databases, daily backup service |

### 11.3 Container image

A multi-stage `Dockerfile`: (1) Node 22 builds the React app with `npm ci` and `npm run build`; (2) a Python 3.12 builder installs dependencies, with **CPU-only PyTorch** installed first (build argument `TORCH_INDEX` selects a CUDA build); (3) a slim runtime image with Tesseract and Poppler, a non-root user, a health check and Gunicorn with Uvicorn workers (`--max-requests` recycling, graceful timeout). **Measured image size: 2.45 GB for production versus 9.92 GB for the earlier CUDA build.**

### 11.4 Production stack

- **Caddy** terminates TLS (automatic certificates), adds security headers, limits request bodies to 60 MB, and does not buffer streaming responses.
- **App**: read-only root file system, `cap_drop: ALL`, `no-new-privileges`, memory limit 4 GB; writable only through the data volume and `/tmp`; migrations run once before workers start.
- **PostgreSQL, Qdrant, Ollama** are on an internal network with no published ports.
- **Backup service**: a daily `pg_dump` compressed and verified (`gzip -t`) into a `backups` volume, keeping the newest `BACKUP_KEEP` (14) files.
- Required secrets use Compose `:?` checks, so a missing value stops the start-up with a clear message.

### 11.5 Configuration

Every setting is an environment variable (loaded by `pydantic-settings`); `.env.production.example` documents them. Key settings are listed in Appendix B.

### 11.6 Continuous integration and automation

- **GitHub Actions** (`.github/workflows/ci.yml`): backend tests (with CPU PyTorch), Ruff lint for serious errors, front-end type-check and build, and a Docker build.
- **Dependabot** (`.github/dependabot.yml`): weekly updates for Python and npm, monthly for Docker and Actions.
- **Makefile**: `make dev`, `test`, `lint`, `frontend-build`, `prod-up`, `prod-down`, `prod-logs`, `backup`, `eval`.

### 11.7 Observability

Structured JSON logs in production with request ids; Prometheus metrics at `/api/v1/metrics` (HTTP requests and latency per route, LLM requests and latency, query outcomes, ingestion queue depth, worker status); liveness and readiness endpoints for orchestrators; an in-app system health card.

---

## 12. Testing

### 12.1 Automated back-end tests

**274 tests in 25 files (about 4,200 lines), all passing.** They use SQLite and fakes for speed, so they run in about 20 seconds without any external service.

| Area | Test files (tests) |
|---|---|
| Generation, prompts, streaming | `test_generation` (22), `test_verification` (13) |
| HTTP behaviour: auth, errors, uploads, SSE, rate limits, config guard | `test_api` (20), `test_auth` (14) |
| Services | `test_services` (15), `test_document_management` (11) |
| Retrieval and search | `test_hybrid_retrieval` (15), `test_retrieval` (6), `test_vectorstore` (13) |
| Extraction and classification | `test_rule_based_metadata_extractor` (11), `test_document_classifier` (14), `test_metadata_framework` (5), `test_pdf_loader` (12) |
| Chunking | `test_document_chunker` (10) |
| Relationships and supersession | `test_relationship_detection` (13), `test_linker` (6), `test_supersession` (6) |
| Comparison | `test_differ` (6), `test_comparison` (5) |
| Citations | `test_citations` (8) |
| **URL import / SSRF** | `test_url_import` (13 test functions, 24 cases with parameters) |
| **Hardening** | `test_hardening` (10): lockout, unlock, weak passwords, headers, retention, production guard |
| History, briefs, bookmarks, audit, PDF serving | `test_history` (4), `test_brief` (3), `test_bookmarks_audit` (5) |

Notable properties tested: duplicate detection; compensating deletes on failure; job claiming and retries; every role boundary over HTTP; rate limiting across instances and at minute boundaries; SSE event sequence; the answer verifier on correct, wrong-number and uncited sentences; path-traversal attempts; lockout, expiry and unlock; retention deleting only old rows; the production configuration guard (including a regression test for a bug found during live testing).

### 12.2 Front-end checks

`tsc` type-checking in strict mode (no unused locals or parameters) and a production build run in CI. There is no automated browser (end-to-end) test suite yet (see section 15).

### 12.3 Live end-to-end checks performed

These were run against the real running system (not mocks):

- Ingestion of the four sample PDFs; automatic detection that 25/2024 supersedes 12/2023 and 12/2023 became `SUPERSEDED`.
- Streaming answers with supersession warning; feedback; history; analytics.
- Comparison of 12/2023 and 25/2024 (1 added, 0 removed, 6 modified, 3 unchanged).
- Import from URL: refusal of unsafe links, successful import of a real PDF from `govinfo.gov`.
- Original PDF served inline with correct headers; bookmark note; audit entries.
- **Full production stack** (separate project): HTTPS through Caddy with HSTS, startup refusal on weak configuration, lockout after repeated failures, unlock by an administrator, weak password rejection, audit trail, and a working backup file.

---

## 13. Evaluation and results

### 13.1 Method

The repository includes an evaluation harness (`eval/run_eval.py`, dataset `eval/dataset.json`) that calls the running API and measures:

| Metric | Meaning |
|---|---|
| **hit@k** | An expected source (and page, where specified) appears in the top-k retrieved chunks |
| **MRR** | Mean of 1 / rank of the first correct chunk |
| **Answer contains** | Every required string appears in the generated answer |
| **Abstention** | Questions marked unanswerable receive the "do not contain" reply and no citations; answerable ones do not |
| **Citation precision** | Share of cited sources that are an expected source |
| **Supersession** | A warning is returned when one is expected |
| **Verified** | Share of answers where every statement was found in its cited pages |
| **Links** | Expected supersedes / amends / references links and pending references exist |
| **Threshold margin** | Lowest score of a correct chunk versus highest score for unanswerable questions (shows how safe the relevance threshold is) |

The dataset has **22 questions** over two groups of documents: a real 38-page **scanned** report (`AnnualAuditReview_IAW.pdf`, which requires OCR) and the four generated sample notifications, circulars and orders (`eval/make_sample_pdfs.py`), plus relationship expectations.

### 13.2 Measured results

The evaluation was run on 15 November 2026 against the running system (the 38-page scanned audit report plus the four sample documents), on the development laptop with the GPU enabled, using the default settings (`top_k = 10`, hybrid search and re-ranking on). The detailed per-question output is saved by the harness in `eval/results/`.

**Summary of the 22 questions** (18 answerable, 4 deliberately unanswerable):

| Metric | Result | Meaning |
|---|---|---|
| Retrieval hit rate (hit@k) | **1.000** (18 of 18) | The expected source and page was among the retrieved chunks for every answerable question |
| Mean reciprocal rank (MRR) | **0.972** | The correct chunk was ranked first for 17 of 18 questions and second for one (`gst-current-rate`) |
| Answer contains required facts | **1.000** | Every answer included all required strings (for example the rate, the date, the financial year) |
| Abstention accuracy | **1.000** (4 of 4) | All four unanswerable questions (income tax, unrelated topic, customs, traffic) received the "documents do not contain this" reply with no citations, and no answerable question was wrongly refused |
| Citation precision | **0.972** | Almost all cited sources were an expected source; one answer (`old-penalty-superseded`) also cited an additional source (precision 0.5 for that question) |
| Supersession warning returned | **1.000** | Whenever a superseded document was relevant, the warning was shown |
| Answers fully verified | **0.833** (15 of 18) | Every sentence of 15 answers was confirmed in its cited pages; 3 answers (`audit-constraints`, `old-penalty-superseded`, `circular-amends`) had at least one sentence the verifier could not confirm and flagged for human checking |
| Relationship links detected | **1.000** | All 3 expected links (25/2024 supersedes 12/2023; 4/2024 amends 25/2024; 7/2024 references 4/2024) and all 3 pending references (1/2019, 2/2019, 3/2018) were found |
| Lowest score of a correct chunk | 0.976 | |
| Highest score for an unanswerable question | 0.0 | The wide gap (0.976 versus 0.0) shows the relevance threshold of 0.01 is very safe on this set |
| Mean retrieval time (search only) | 2.96 seconds | |
| Mean time to a complete answer | 20.0 seconds | |

**Reading the results honestly.**

- The three answers that were not fully verified are exactly the case the verifier is designed for: it flagged them for a human to check rather than letting them pass silently. Verification flags statements; it does not prove a statement wrong.
- The mean answer time here (about 20 seconds) is higher than the "about 8 seconds" quoted in section 13.3 because the evaluation uses ten retrieved passages per question, and the scanned report produces long passages. Short questions on small documents are answered in about 8 seconds.
- The evaluation set is modest (22 questions over five documents). It shows that the design works and catches regressions; it is not a large statistical benchmark. The sample documents were written for the evaluation, so results on real, messier documents may be lower.

### 13.3 Performance measurements (development laptop)

Hardware: 12 logical CPUs, 15 GB RAM, NVIDIA GeForce GTX 1650 with 4 GB of memory.

| Measurement | Before (CPU only) | After (GPU enabled) |
|---|---|---|
| Prompt processing speed | 10 tokens/second | 137 to 141 tokens/second (about 13 times faster) |
| Time to answer one question | about 125 seconds | about 8 seconds (first word after about 5 seconds) |
| Generation speed | 4.5 tokens/second | about 22 tokens/second |
| Cold model load (first question after restart) | included in the above | 160 to 225 seconds; removed from the user's path by start-up warm-up |
| Plain-language brief | not measured | about 18 seconds, then 0.1 seconds from cache |
| Production image size | 9.92 GB (CUDA PyTorch) | 2.45 GB (CPU PyTorch) |

**Cause and fix:** Docker could not use the GPU because `nvidia-container-toolkit` was not installed and `sudo` was not available. The fix passes the NVIDIA device files and host driver libraries directly to the Ollama container, which enabled CUDA. Because 3.6 GB of video memory cannot hold the whole model plus its context, about half the layers run on the CPU, which explains why answers take about 8 rather than about 2 seconds.

### 13.4 Discussion

- Retrieval quality is strongest for questions that name a document or use distinctive terms (lexical component plus number boost) and for paraphrased questions (dense component); the cross-encoder removes unrelated passages so that unanswerable questions abstain.
- Answer quality is bounded by the small local model: it occasionally cites the wrong tag or adds commentary. The verifier catches unsupported numbers and statements, but cannot detect a wrong inference built from correct words.
- Scanned documents depend on OCR quality (Tesseract can misread digits in tables); this limits answers about such pages even when retrieval is right.

---

## 14. Development history and problems solved

### 14.1 Phases

| Phase | Content |
|---|---|
| **1. Initial implementation** | Modular RAG pipeline: PDF and OCR ingestion, rule-based metadata and classification, page-preserving chunking, HuggingFace embeddings, Qdrant and PostgreSQL storage, dense retrieval, citations, supersession engine, Ollama generation, FastAPI routes, Docker Compose, tests |
| **2. Hardening and quality** (merged from a contributor's fork) | Authentication and roles, rate limiting, hybrid retrieval and re-ranking, background jobs, streaming, answer verification, document management and reconciliation, comparison, metrics, backups, evaluation harness, extended tests |
| **3. Product and production** | React front end; history, feedback, analytics; import from URL; briefs; bookmarks; original-PDF viewer; audit log; timeline; official source directory; account lockout and password policy; security headers; retention; production Docker/Caddy stack; CI; GPU acceleration |

The Git history records these as separate commits (`Initial GovLens implementation`, `Expand GovLens security and document workflows`, then three commits for the React front end, production deployment and backend features).

### 14.2 Problems encountered and how they were solved

This list is useful evidence of engineering judgement.

| # | Problem | Cause | Solution |
|---|---|---|---|
| 1 | Answers took about two minutes | Ollama ran on the CPU inside Docker (10 tokens/second prompt processing); GPU not visible to Docker | Passed NVIDIA devices and driver libraries to the container; added flash attention and quantised KV cache; measured 13 times faster |
| 2 | First question after a restart took 4 minutes | Cold model load | Background warm-up at start-up; 30-minute keep-alive |
| 3 | Test environment installation failed with "Disk quota exceeded" | `/tmp` is RAM-backed and default PyTorch pulls several GB of CUDA libraries | Installed CPU-only PyTorch; later applied the same in the production Dockerfile (image 9.9 GB to 2.45 GB) |
| 4 | Dependencies would not build | System Python 3.14 is newer than the pinned packages support | Used Python 3.12, the version used by the project's Dockerfile |
| 5 | Port conflicts (Postgres 5432, proxy 8080) | Other services on the host | Made ports configurable; local `.env` selects free ports |
| 6 | A production admin password containing "admin" was rejected by the new password policy, but the app still started "healthy" with no way to sign in | Bootstrap errors were only logged | Production start-up now validates the admin password and refuses to start; clear error log; regression test (found by a live test of the production stack) |
| 7 | Streaming test failed after adding history logging | A test's minimal event was not a full result | Made history recording fail-safe so it can never break an answer |
| 8 | A government site returned HTTP 202 for a PDF | The site builds PDFs on demand | Importer waits and retries; documented that very long Acts may still time out |
| 9 | Users typed `site:sebi.gov.in ... filetype:pdf` into GovLens and got "no information" | Those operators are for Google, and the page did not make that clear | Reworded the tip, added "Open in Google", a notice when such queries are typed, and a "find and import the PDF" hint on empty answers |
| 10 | A strict CSP might block the browser's PDF viewer | `object-src 'none'` blocks plug-in rendering in Chrome | Allowed `blob:` in `object-src`; verified the built page has no inline scripts |
| 11 | Safety tooling blocked a command containing backup-script text | Text resembling a deletion command | Re-did the edit with file-editing tools instead |
| 12 | Some Indian government sites time out or block scripts | Network and bot protection | Verified all directory links, kept unverifiable major sites with a "may be slow" mark, and added a disclaimer |

---

## 15. Limitations and future work

### 15.1 Limitations

**Answer quality**
- The default model (`qwen3:4b-instruct`) is small. It can cite the wrong tag or add commentary; verification flags many but not all such cases.
- Verification is an evidence check, not a proof of correctness (it can pass a sentence that reuses source words but draws a wrong conclusion, and can flag a heavily paraphrased correct sentence).
- English only. Hindi and other languages are not supported by the models used.
- The relevance threshold (0.01) is tuned on the evaluation set and may need adjusting for other collections.

**Extraction**
- Metadata and relationships are pattern-based. Unusual phrasings (for example "shall cease to have effect") are classified as plain references; variant number forms ("No. 01/2017") may not match. Manual links are provided as a remedy.
- OCR can misread digits and tables.

**Security and operations**
- No per-document permissions, no multi-factor authentication, no single sign-on.
- Session tokens live in browser storage (see 10.2).
- One machine only: no autoscaling or high availability.
- Backups are written to a local volume; there is no automatic off-site copy and no automated restore test.
- Metrics are exposed but no dashboards or alerts are bundled.

**Testing**
- Unit and API tests use SQLite and fakes; PostgreSQL-specific behaviour (full-text search, migrations) is covered by live runs against the Docker stack rather than by `pytest`.
- No automated browser tests.
- The URL importer is fast for static files but waits on sites that generate PDFs on demand.

**Process**
- Several older documents in `docs/` (technical report, project review, runtime validation report) describe the first version and are out of date; this report supersedes them.

### 15.2 Future work

1. **Browser end-to-end tests** (Playwright) for upload, ask, compare and admin flows.
2. **Metrics dashboards and alerts** (Prometheus and Grafana).
3. **Cookie-based sessions** with HTTP-only, same-site cookies, and optional multi-factor authentication or OIDC single sign-on.
4. **Per-document or per-collection permissions.**
5. **Multilingual support** (for example Hindi) with a multilingual embedding and language model.
6. **A stronger or hosted model** behind the existing generator interface, and a larger evaluation set.
7. **Scheduled crawling** of selected government sources, with change detection and notifications when a watched rule changes.
8. **Learned verification** (entailment model) in addition to the current explainable checker.
9. **Off-site backups and a tested restore drill**; multi-node deployment.
10. **Obligation and deadline extraction** into a calendar of compliance dates.

---

## 16. Conclusion

GovLens shows that a locally hosted RAG system can be made *trustworthy enough to be useful* for government documents by combining several complementary safeguards instead of relying on the language model alone: page-preserving chunking and deterministic citations make every claim traceable; hybrid retrieval with a cross-encoder and a relevance threshold lets the system say "the documents do not contain this"; a relationship graph detects that a cited rule has been superseded; and a sentence-level verifier exposes statements that the sources do not support.

The project goes beyond a prototype. It provides a complete user interface, role-based access control, audit logging, safe document import, scheduled backups, hardened containers and HTTPS, automated tests (274 passing) and continuous integration, and it documents its limitations honestly. Measured performance work (moving inference to the GPU) turned a two-minute wait into an eight-second answer on modest hardware.

The main lessons were that retrieval quality and strict, checkable constraints matter more than model size for grounded answering; that production readiness is mostly about failure handling, safe defaults and observability rather than features (a live test of the production stack found a real start-up bug that unit tests had missed); and that user-interface details such as clear empty states, honest warnings and one-click paths from "not found" to "find and import the document" decide whether a technically correct system is actually usable.

---

## 17. References

The following are standard works for the techniques used. Please reformat to your required citation style (IEEE, APA, and so on) and verify details before submission.

1. P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," *Advances in Neural Information Processing Systems (NeurIPS)*, 2020.
2. V. Karpukhin et al., "Dense Passage Retrieval for Open-Domain Question Answering," *Proceedings of EMNLP*, 2020.
3. G. V. Cormack, C. L. A. Clarke, and S. Buettcher, "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods," *Proceedings of ACM SIGIR*, 2009.
4. S. Robertson and H. Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond," *Foundations and Trends in Information Retrieval*, 2009.
5. R. Nogueira and K. Cho, "Passage Re-ranking with BERT," arXiv:1901.04085, 2019.
6. N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," *Proceedings of EMNLP-IJCNLP*, 2019.
7. S. Xiao et al., "C-Pack: Packaged Resources To Advance General Chinese Embedding" (BGE embedding models), arXiv:2309.07597, 2023.
8. R. Smith, "An Overview of the Tesseract OCR Engine," *Proceedings of ICDAR*, 2007.
9. C. Percival, "Stronger Key Derivation via Sequential Memory-Hard Functions," *BSDCan*, 2009.
10. OWASP Foundation, "Server-Side Request Forgery Prevention Cheat Sheet."
11. OWASP Foundation, "Content Security Policy Cheat Sheet."
12. Software documentation: FastAPI, SQLAlchemy, Alembic, Pydantic, PostgreSQL, Qdrant, Ollama, PyMuPDF, sentence-transformers, React, Vite, Tailwind CSS, TanStack Query, Docker, Caddy (official project websites).

---

## 18. Appendices

### Appendix A. Repository structure

```text
GovLens/
|-- app/                      FastAPI application (103 Python files, 9,287 lines)
|   |-- api/                  routes, schemas, security, health, dependencies
|   |   `-- routes/           analytics, audit, auth, bookmarks, compare, documents,
|   |                         history, ingestion, query, users
|   |-- services/             audit, auth, bookmarks, brief, comparison, dependencies,
|   |                         documents, exceptions, history, ingestion, jobs, paths,
|   |                         query, retention, schemas, url_import
|   |-- ingestion/            PDF loaders (PyMuPDF, OCR) and contracts
|   |-- metadata/             extractors, patterns, normalisation, validators, pipeline
|   |-- classification/       rule-based classifier
|   |-- chunking/             chunker, tokenizer windows
|   |-- retrieval/            dense retriever, keyword search, hybrid, reranker
|   |-- vectorstore/          embedder, Qdrant store, windows
|   |-- citations/            citation builder
|   |-- supersession/         engine and relationship linker
|   |-- generation/           prompt builder, Ollama client, generator, verification
|   |-- comparison/           differ and engine
|   |-- models/, repositories/, schemas/, db/   persistence
|   |-- core/                 config, logging, metrics, text, constants
|   |-- static/               original plain-HTML interface (served at /legacy)
|   `-- main.py               application factory, middleware, start-up tasks
|-- frontend/                 React application (31 files, about 2,600 lines)
|   `-- src/                  pages/, components/, lib/ (api, auth, types, export, resources, theme)
|-- alembic/versions/         6 database migrations
|-- tests/                    25 test files, 274 tests
|-- eval/                     evaluation dataset, harness, sample-PDF generator
|-- scripts/                  backup.sh, restore.sh
|-- docs/                     architecture, limitations, assignment mapping, this report
|-- Dockerfile                multi-stage production image
|-- docker-compose.yml        development stack
|-- docker-compose.gpu.yml    optional GPU override for Ollama
|-- docker-compose.prod.yml   production stack (Caddy, backups, hardening)
|-- Caddyfile                 reverse proxy and headers
|-- Makefile                  developer and operator shortcuts
|-- .github/                  CI workflow, Dependabot
|-- .env.example, .env.production.example
`-- README.md
```

### Appendix B. Configuration reference

All settings are environment variables (case-insensitive). Defaults are from `app/core/config.py`.

| Setting | Default | Meaning |
|---|---|---|
| `POSTGRES_HOST`, `PORT`, `DB`, `USER`, `PASSWORD` | localhost, 5432, govlens, govlens_user, changeme | Database connection (password must be changed in production) |
| `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` | localhost, 6333, none, government_documents | Vector store |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | http://ollama:11434, qwen3:4b-instruct | Language model server and model |
| `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_NUM_PREDICT`, `OLLAMA_KEEP_ALIVE` | 900, 512, 0 | Time limit, answer length, how long the model stays loaded (0 unloads after each answer) |
| `EMBEDDING_MODEL` | BAAI/bge-small-en-v1.5 | Embedding model |
| `HYBRID_SEARCH_ENABLED`, `RETRIEVAL_CANDIDATE_MULTIPLIER` | true, 3 | Hybrid search and candidate pool size |
| `RERANKER_ENABLED`, `RERANKER_MODEL`, `RERANKER_MIN_SCORE` | true, cross-encoder/ms-marco-MiniLM-L-6-v2, 0.01 | Re-ranking and relevance cut-off |
| `METADATA_LLM_FALLBACK` | true | Let the model fill fields the patterns missed (verified against the text) |
| `UPLOAD_DIR`, `MAX_UPLOAD_MB`, `INGEST_ALLOWED_DIRS`, `INGEST_WORKERS` | data/uploads, 50, /app,data/uploads, 1 | Uploads and background workers |
| `IMPORT_ALLOWED_DOMAINS`, `IMPORT_TIMEOUT_SECONDS` | government domains list, 30 | URL import allow-list and timeout |
| `AUTH_ENABLED` | true | Require sign-in (false only for local experiments) |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | admin, generated | First administrator; a password is generated into `data/initial_admin_password.txt` if empty |
| `TOKEN_TTL_HOURS` | 12 | Session lifetime |
| `API_KEYS` | empty | Service keys `key` or `key:ROLE`, comma-separated |
| `RATE_LIMIT_PER_MINUTE`, `LOGIN_RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_BACKEND` | 60, 10, database | Request limits per identity and sign-in attempts per IP |
| `LOGIN_MAX_FAILURES`, `LOGIN_LOCKOUT_MINUTES` | 5, 15 | Account lockout |
| `QUERY_LOG_RETENTION_DAYS`, `AUDIT_LOG_RETENTION_DAYS` | 90, 365 | Data retention (0 keeps everything) |
| `CORS_ORIGINS` | empty | Allowed cross-origin sites (empty disables) |
| `ENV`, `DEBUG`, `LOG_LEVEL`, `LOG_FORMAT` | development, false, INFO, text | Mode and logging (`json` in production) |

### Appendix C. How to run

**Development (Docker):**

```bash
git clone https://github.com/Nancyy56/GovLens.git && cd GovLens
cp .env.example .env
docker compose up -d --build
docker compose exec ollama ollama pull qwen3:4b-instruct   # about 2.5 GB
# open http://localhost:8000
# first sign-in: username admin, password in data/initial_admin_password.txt
```

**Optional GPU (NVIDIA):** add `COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml` to `.env` (adjust the driver library versions in `docker-compose.gpu.yml` to match `nvidia-smi`).

**Front-end development:**

```bash
cd frontend && npm install
npm run dev        # http://localhost:5173, proxies /api to localhost:8000
npm run build      # output in frontend/dist
```

**Tests:**

```bash
docker compose exec app python -m pytest -q      # 274 tests
cd frontend && npx tsc -b --noEmit               # type-check
python3 eval/make_sample_pdfs.py                 # sample documents
python3 eval/run_eval.py                         # quality evaluation
```

**Production:**

```bash
cp .env.production.example .env.production      # fill in every value
make prod-up                                     # Caddy HTTPS, hardened app, backups
```

### Appendix D. Sample questions and expected behaviour

Using the four sample documents (Notification 12/2023, Notification 25/2024, Circular 4/2024, Order 7/2024):

| Question | Expected behaviour |
|---|---|
| What is the GST rate on packaged food items? | 12 percent, citing 25/2024 (the current document), with a superseded warning about 12/2023 |
| What was the GST rate on packaged food in 2023, and what is it now? | 5 percent (12/2023) and 12 percent (25/2024), stating that 12/2023 is superseded |
| What is the late filing penalty? | Rs 100 per day in 12/2023, replaced by 18 percent annual interest in 25/2024 |
| What is the current due date for monthly returns? | The 25th of the following month (Circular 4/2024), which amends 25/2024 |
| Which documents were withdrawn or rescinded? | Circulars 1/2019 and 2/2019 withdrawn; Order 3/2018 rescinded (Order 7/2024) |
| What is the GST rate on electronics? | "The provided documents do not contain information about this." (abstention) |

### Appendix E. Glossary

| Term | Meaning |
|---|---|
| **RAG** | Retrieval-Augmented Generation: retrieve passages, then generate an answer from them |
| **Embedding** | A vector representing the meaning of a text |
| **Dense retrieval** | Search by vector similarity |
| **Lexical / full-text search** | Search by words |
| **RRF** | Reciprocal Rank Fusion: combine ranked lists by rank |
| **Cross-encoder** | A model that scores a question and passage together |
| **Chunk** | A passage of a document stored and searched as a unit |
| **OCR** | Optical character recognition: text from images |
| **Supersession** | A newer document replacing an older one |
| **Hallucination** | A fluent but false statement by a language model |
| **SSE** | Server-sent events: a server pushing a stream of messages |
| **SSRF** | Server-side request forgery |
| **CSP** | Content-Security-Policy, a browser security header |
| **HSTS** | HTTP Strict Transport Security |
| **Gazette** | The official publication in which governments publish laws and notices |
| **Notification / Circular / Order** | Common kinds of government documents |

### Appendix F. Official source directory (summary)

The **Find documents** page lists about 120 sources, verified as reachable when listed, with what to find and how to search: **112 for India** (central law and gazette, tax and finance, regulators such as RBI, SEBI, IRDAI, TRAI, over 40 ministries and departments, courts and tribunals, commissions and public bodies, audit and statistics bodies, and 17 state governments) and **6 international** (US Federal Register, GovInfo, Regulations.gov; UK Legislation and GOV.UK; EUR-Lex). The list is in `frontend/src/lib/resources.ts`.

### Appendix G. Project statistics

| Item | Value |
|---|---|
| Python application code | 103 files, 9,287 lines |
| Automated tests | 25 files, 4,202 lines, **274 tests** |
| Database migrations | 6 (505 lines) |
| Front end | 31 files, 2,622 lines (TypeScript and TSX) |
| Scripts and evaluation | 370 lines |
| API endpoints | 42 |
| Database tables | 11 application tables |
| Source directory entries | about 120 (112 India) |
| Git commits | 6 |
| Production image size | 2.45 GB |
| Typical answer time (GPU, laptop) | about 8 seconds |

---

*End of report.*
