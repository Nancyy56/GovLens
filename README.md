# GovLens

**Government Document Retrieval-Augmented Generation (RAG) System**

GovLens answers natural-language questions about government documents (notifications, circulars, orders, gazettes, policies, advisories, reports) with citations down to the page, and checks each sentence of the answer against the pages it cites. It extracts text from PDFs (with OCR for scans), detects which documents supersede or amend which, retrieves relevant passages with hybrid search and reranking, and generates answers locally through Ollama. It also compares two documents and explains what changed. A built-in web interface at `http://localhost:8000/` covers asking, browsing, comparing, uploading, and user management, with sign-in and roles.

---

## Overview

### Problem Statement

Government bodies publish large volumes of formal PDFs, and newer documents regularly replace or amend older ones. Finding a rule, proving where it came from, and knowing whether it is still in force is slow by hand. GovLens lets users ask questions and inspect source-backed answers that flag superseded documents.

### Why RAG

The language model only sees passages retrieved from the ingested documents and is instructed to answer from them alone, so answers stay grounded in the corpus rather than the model's memory. Citations are built by code from stored metadata, never by the model.

### Why Hybrid Search

Dense embeddings (`BAAI/bge-small-en-v1.5`) match meaning even when wording differs. PostgreSQL full-text search catches exact terms and document numbers such as `17/2024`, which embeddings handle poorly. The two rankings are fused, then a cross-encoder reranks the short list.

---

## Features

### Ingestion
- **PDF loading**: PyMuPDF for digital PDFs; automatic OCR fallback (`pdf2image` + Tesseract) when fewer than half the pages have text. Each file is parsed once.
- **Upload or path**: upload a PDF over HTTP, or ingest a file already on the server (restricted to `INGEST_ALLOWED_DIRS`).
- **Background jobs**: large or scanned PDFs can be queued; the API returns a job id to poll. Jobs live in PostgreSQL and are claimed by worker threads; a job interrupted by a restart is retried (up to 3 attempts).
- **Duplicate detection**: files are identified by SHA-256 of their bytes; re-ingesting the same file returns `409` with the existing document id.
- **Metadata extraction**: rule-based patterns for document number, type, issue date, department, subject; fields the patterns miss are asked of the LLM, and each LLM value is kept only if it can be verified in the text (the number appears verbatim, the date's year appears, the subject uses the document's words). A missing date is stored as empty, never guessed.
- **Classification**: the document heading decides the type; a weak word like "Policy" in the body only counts if it recurs.
- **Relationship detection**: mentions of other documents are classified from the wording of their own clause ("in supersession of", "hereby rescinded" → SUPERSEDES; "amend", "substitute" → AMENDS; otherwise REFERENCES). Lists ("Nos. 1/2020, 2/2020 and 3/2020 are rescinded", "Notification No. A and Circular No. B are withdrawn") share the relationship. Links to documents not yet ingested are kept as pending and resolved when that document arrives. A superseded document's status becomes `SUPERSEDED`.
- **Chunking**: page-preserving chunks of 500–1000 tokens (counted with the embedding model's tokenizer), one-sentence overlap, line breaks kept. Chunks longer than the models' 512-token input are embedded and reranked as overlapping windows, so no text is invisible to search.
- **Consistent storage**: PostgreSQL rows and Qdrant vectors are written as one unit; if the database commit fails, the vectors are removed again. At startup GovLens reconciles the two stores and rebuilds any missing vectors from the stored chunk text.

### Retrieval
- **Hybrid search**: Qdrant dense search plus PostgreSQL full-text search (GIN index) with an exact-document-number boost, merged with Reciprocal Rank Fusion.
- **Reranking**: cross-encoder `cross-encoder/ms-marco-MiniLM-L-6-v2` reorders the fused candidates. If the model cannot load, reranking is disabled with a logged error and retrieval continues.
- **Filtering** by document number.

### Answers
- **Grounded prompt**: strict answer-only-from-sources rules; the exact fallback reply when the sources do not contain the answer; extra rules when sources span several documents or include superseded ones.
- **Inline citations**: each source page is tagged `[S1]`, `[S2]`, … The response lists only the sources the answer actually cited, and a deterministic **Sources** list is appended to the answer.
- **Answer verification**: every sentence is checked against the pages it cites — all its numbers must appear there and at least half its key words. The response's `verification` lists supported, unsupported, and uncited sentences, and the web interface warns when anything could not be confirmed.
- **Supersession warnings** for every retrieved document, not just the top result.
- **Streaming** via server-sent events.
- **Relevance cut-off**: reranked chunks scoring below `RERANKER_MIN_SCORE` (0.01) are dropped. If nothing relevant remains, GovLens answers "The provided documents do not contain information about this." without calling the model. The prompt also restates the question after the sources so the model stays on topic.

### Comparison
- Sentence-level diff between two documents (added / removed / modified, with page numbers on both sides), aware of abbreviations like "No." and "Rs.".
- Optional plain-language summary by the model, which only sees the detected changes and must cite pages.
- Reports any stored relationship between the two documents.

### Document management
- List, search, inspect (with incoming/outgoing links and pending references), delete, and re-ingest documents.
- Add or remove relationships manually when detection misses one; manual links survive re-ingestion.
- Re-ingest safely: the old record is kept until the new one is stored.
- Reconcile PostgreSQL and Qdrant, rebuilding missing vectors without the source files.

### Web interface
- Served by GovLens itself at `/` (no build step, no external assets).
- Ask with streamed answers, clickable source tags that open the cited page, supersession banners, and verification warnings.
- Browse and search documents, see links in both directions, add/remove links, re-ingest, delete.
- Compare two documents; upload PDFs (immediately or as background jobs) and watch job progress; manage users.

### Operations and security
- **Accounts and roles**: sign in with a username and password (scrypt-hashed). Sessions are random tokens stored only as hashes, expiring after `TOKEN_TTL_HOURS`. Roles: **VIEWER** (ask, search, compare, browse), **EDITOR** (+ ingest, re-ingest, delete, edit links), **ADMIN** (+ users, metrics, reconcile). The last active admin cannot be removed; password changes and deactivation end that user's sessions.
- **First admin**: created at startup when no users exist, from `ADMIN_USERNAME`/`ADMIN_PASSWORD`, or with a generated password written to `data/initial_admin_password.txt`.
- **Service API keys** for scripts, each with a role (`API_KEYS=key:VIEWER`).
- **Rate limiting** per user or key, and per IP for sign-in attempts; counts are shared across API workers through PostgreSQL (sliding-window estimate).
- **CORS** restricted to `CORS_ORIGINS`.
- **Errors**: unexpected errors return a generic message with a request id (never a traceback); every log line carries the request id (`X-Request-ID`).
- **Readiness check** of PostgreSQL, Qdrant, and Ollama (including whether the model is pulled).
- **Metrics** in Prometheus text format at `/api/v1/metrics` (admins): requests, latency, LLM calls, ingestions, query outcomes, job queue depth.
- **Backups**: `scripts/backup.sh` and `scripts/restore.sh` (database and uploads; vectors are rebuilt on restore).
- **Logging** as text or JSON lines; no prompts or document text are logged at INFO level.
- **Evaluation harness** (`eval/`) measuring retrieval, answer correctness, abstention, citation precision, verification, supersession warnings, and the relationship graph.

---

## Architecture Overview

```text
                        INGESTION  (POST /ingest, /ingest/upload, /ingest/jobs)
PDF ─▶ AutoPDFLoader (PyMuPDF, OCR fallback) ─▶ SHA-256 duplicate check
    ─▶ RuleBasedMetadataExtractor (number, date, department, subject, mentions)
    ─▶ RuleBasedDocumentClassifier
    ─▶ PostgreSQL: documents ─▶ RuleBasedDocumentChunker ─▶ PostgreSQL: document_chunks
    ─▶ DocumentRelationshipLinker (document_references ─▶ document_relationships, status)
    ─▶ HuggingFace embeddings ─▶ Qdrant upsert ─▶ commit (or roll back and delete vectors)

                        QUERY  (POST /query, /query/stream, /query/search)
Question ─▶ HybridDocumentRetriever
              ├─ Qdrant dense search
              ├─ PostgreSQL full-text search (+ exact number boost)
              ├─ Reciprocal Rank Fusion
              └─ Cross-encoder reranker
         ─▶ ComparisonEngine (group by document and page, most relevant first)
         ─▶ CitationBuilder  +  DatabaseSupersessionEngine (every retrieved document)
         ─▶ PromptBuilder ([S1]… tags, rules, warnings) ─▶ Ollama (qwen3:4b-instruct)
         ─▶ keep cited sources only ─▶ verify each sentence ─▶ answer + Sources + warnings

                        COMPARE  (POST /compare)
Two documents ─▶ pages rebuilt from chunks ─▶ DocumentDiffer ─▶ (optional) LLM summary of the diff
```

PostgreSQL holds document metadata, chunk text (with a full-text index), relationships, pending references, and ingestion jobs. Qdrant holds embeddings plus the payload needed for citations.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | Python 3.12, FastAPI 0.104.1 | REST API, validation, OpenAPI docs |
| **ORM / migrations** | SQLAlchemy `>=2.0.35`, Alembic 1.13.1 | Database access and schema versions |
| **Relational DB** | PostgreSQL 16 | Metadata, chunks, full-text search, relationships, jobs |
| **Vector DB** | Qdrant (`qdrant-client` 1.18.0) | Dense similarity search |
| **Embeddings** | `sentence-transformers`, `BAAI/bge-small-en-v1.5` | 384-dimension vectors |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Second-stage relevance scoring |
| **LLM** | Ollama, `qwen3:4b-instruct` (default) | Local answers, summaries, metadata fallback |
| **PDF** | PyMuPDF, `pdf2image`, `pytesseract` | Digital extraction and OCR |
| **Uploads** | `python-multipart` | Multipart file uploads |
| **Containers** | Docker, Docker Compose | Local orchestration |

---

## Project Structure

```text
app/
├── api/                  # Routes, request schemas, auth and rate limiting, health checks
├── chunking/             # Page-preserving chunking
├── citations/            # Deterministic citation text
├── classification/       # Rule-based document type detection
├── comparison/           # Source grouping and sentence-level document diff
├── core/                 # Settings, constants, logging
├── db/                   # SQLAlchemy engine and sessions
├── generation/           # Prompt builder, Ollama client, citation selection, streaming
├── ingestion/            # PDF and OCR loaders
├── metadata/             # Rule-based metadata and mention extraction
├── models/               # ORM models and enums
├── repositories/         # CRUD repositories
├── retrieval/            # Dense, keyword, hybrid retrieval and reranking
├── schemas/              # Processing and document schemas
├── services/             # Ingestion, query, comparison, documents, jobs, wiring
├── supersession/         # Supersession chains and relationship linking
└── vectorstore/          # Embedding provider and Qdrant store
eval/                     # Evaluation dataset, sample PDF generator, runner
tests/                    # Unit and API tests (SQLite-backed where a database is needed)
```

---

## API

All endpoints are under `/api/v1`. Interactive docs: `http://localhost:8000/docs`. Every endpoint except the health checks and sign-in needs `Authorization: Bearer <session token>` (from `/auth/login`) or `X-API-Key: <service key>`. The minimum role is shown in brackets.

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness: `{"status": "ok"}` (public) |
| `GET /health/ready` | Checks PostgreSQL, Qdrant, Ollama; `503` if any is down (public) |
| `POST /auth/login` | `{"username", "password"}` → `access_token` (public, rate-limited per IP) |
| `POST /auth/logout`, `GET /auth/me`, `POST /auth/password` | End session, who am I, change own password [viewer] |
| `GET/POST /users`, `PATCH/DELETE /users/{id}` | Manage users and roles [admin] |
| `GET /metrics` | Prometheus metrics [admin] |
| `POST /ingest` | Ingest a server-side PDF: `{"file_path": "/app/data/x.pdf"}` [editor] |
| `POST /ingest/upload` | Upload a PDF (multipart field `file`); add `?background=true` to queue it [editor] |
| `POST /ingest/jobs` | Queue a server-side PDF; returns a job (`202`) [editor] |
| `GET /ingest/jobs`, `GET /ingest/jobs/{id}` | Job status: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, with attempts [viewer] |
| `POST /query` | Answer a question: `{"query": "...", "top_k": 10, "document_numbers": []}` [viewer] |
| `POST /query/stream` | Same, as server-sent events: `retrieval`, `token`…, `done` (or `error`) [viewer] |
| `POST /query/search` | Ranked chunks only, no LLM [viewer] |
| `POST /compare` | `{"base": "12/2023", "target": "25/2024", "focus": "rates", "summarize": true}` (ids or numbers) [viewer] |
| `GET /documents` | List with `limit`, `offset`, `document_type`, `status`, `search` [viewer] |
| `GET /documents/{id}` | Details, links in both directions, pending references [viewer] |
| `GET /documents/{id}/pages/{n}` | Stored text of one page [viewer] |
| `DELETE /documents/{id}` | Delete from both stores; documents it superseded become active again [editor] |
| `POST /documents/{id}/reingest` | Re-run ingestion from the stored file; keeps the old record if it fails [editor] |
| `POST /documents/{id}/relationships` | Add a link: `{"target_document_id": "...", "relationship_type": "SUPERSEDES"}` [editor] |
| `DELETE /documents/relationships/{id}` | Remove a link [editor] |
| `POST /documents/reconcile` | Remove orphaned vectors; rebuild missing ones [admin] |

Error codes: `503` the language model failed or is unreachable (for example, Ollama ran out of memory), `500` unexpected error (generic message plus `request_id`), `401` not signed in or invalid credentials, `403` role too low or path outside allowed directories, `404` not found, `409` duplicate file or ambiguous document number, `413` upload too large, `415` not a PDF, `422` unreadable PDF or invalid request, `429` rate limited (with `Retry-After`).

### Query response

```json
{
  "query": "What is the GST rate on packaged food items?",
  "answer_markdown": "The GST rate on packaged food items is 12 percent [S2]. The previous rate of 5 percent [S1] is superseded.\n\n**Sources**\n- [S2] Notification No. 25/2024, Dated: 2024-03-15, (Page 1)\n- [S1] Notification No. 12/2023, Dated: 2023-04-01, (Page 1)",
  "citations": ["[S2] Notification No. 25/2024\nDated: 2024-03-15\n(Page 1)", "..."],
  "sources": [{"label": "S2", "document_id": "...", "document_number": "25/2024", "page_number": 1, "...": "..."}],
  "supersession_warnings": [{"document_number": "12/2023", "is_superseded": true, "latest_document_number": "25/2024", "...": "..."}],
  "verification": {"checked": 2, "supported": 2, "unsupported": 0, "uncited": 0, "all_supported": true, "sentences": ["..."]},
  "citations_inferred": false
}
```

---

## Setup

### Prerequisites
- Docker and Docker Compose
- Network access on first run (Ollama model, embedding and reranker models from HuggingFace)

### Start

```bash
cp .env.example .env              # optionally set ADMIN_PASSWORD
docker compose up --build -d      # PostgreSQL, Qdrant, Ollama, app (runs migrations)
docker compose exec ollama ollama pull qwen3:4b-instruct
curl http://localhost:8000/api/v1/health/ready
cat data/initial_admin_password.txt   # if ADMIN_PASSWORD was not set
```

Open `http://localhost:8000/`, sign in as `admin`, change the password (top right), and add users under **Users**.

### Configuration

Key settings (see `.env.example` and `app/core/config.py`):

| Variable | Default | Meaning |
|---|---|---|
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | `admin`, generated | First admin, created when no users exist |
| `TOKEN_TTL_HOURS` | `12` | Session lifetime |
| `API_KEYS` | empty | Service keys for scripts: `key` (admin) or `key:VIEWER`, comma-separated |
| `RATE_LIMIT_PER_MINUTE`, `LOGIN_RATE_LIMIT_PER_MINUTE` | `60`, `10` | Per user/key, and sign-in attempts per IP; `0` disables |
| `RATE_LIMIT_BACKEND` | `database` | `memory` for a single process without database writes |
| `AUTH_ENABLED` | `True` | `False` treats every request as admin (local experiments only) |
| `CORS_ORIGINS` | empty | Allowed browser origins |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | `http://ollama:11434`, `qwen3:4b-instruct` | Generation backend (`qwen3:8b` is better but needs ~8 GB RAM) |
| `OLLAMA_KEEP_ALIVE` | `0` | Unload the model after each answer (~5 s slower, prevents Ollama's prompt cache from exhausting laptop RAM); e.g. `5m` with more memory |
| `METADATA_LLM_FALLBACK` | `True` | Ask the LLM for metadata the patterns missed |
| `HYBRID_SEARCH_ENABLED` | `True` | Add keyword search to dense search |
| `RERANKER_ENABLED`, `RERANKER_MODEL` | `True`, MiniLM cross-encoder | Second-stage reranking |
| `RERANKER_MIN_SCORE` | `0.01` | Reranked chunks below this are treated as irrelevant |
| `INGEST_ALLOWED_DIRS` | `/app,data/uploads` | Directories path-based ingestion may read |
| `UPLOAD_DIR`, `MAX_UPLOAD_MB` | `data/uploads`, `50` | Upload storage and size limit |
| `LOG_LEVEL`, `LOG_FORMAT` | `INFO`, `text` | `json` for structured logs |

---

## Example Usage

```bash
# Sign in (use the token on every request below)
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "..."}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
alias curl='curl -H "Authorization: Bearer $TOKEN"'

# Upload and ingest now
curl -X POST localhost:8000/api/v1/ingest/upload -F "file=@notice.pdf;type=application/pdf"

# Upload a large scan as a background job, then poll it
curl -X POST 'localhost:8000/api/v1/ingest/upload?background=true' -F "file=@scan.pdf;type=application/pdf"
curl localhost:8000/api/v1/ingest/jobs/<job-id>

# Ask a question (or stream it)
curl -X POST localhost:8000/api/v1/query -H 'Content-Type: application/json' \
  -d '{"query": "What is the GST rate on packaged food items?"}'
curl -N -X POST localhost:8000/api/v1/query/stream -H 'Content-Type: application/json' \
  -d '{"query": "What is the GST rate on packaged food items?"}'

# Compare two documents
curl -X POST localhost:8000/api/v1/compare -H 'Content-Type: application/json' \
  -d '{"base": "12/2023", "target": "25/2024", "focus": "rates and penalties"}'
```

---

## Testing and Evaluation

```bash
docker compose exec app python -m pytest -q          # unit and API tests

# Retrieval and answer quality against eval/dataset.json (22 questions, link checks)
docker compose exec app python eval/make_sample_pdfs.py
# ingest AnnualAuditReview_IAW.pdf and data/samples/*.pdf, then:
export GOVLENS_USERNAME=admin GOVLENS_PASSWORD=...
python3 eval/run_eval.py --retrieval-only           # fast
python3 eval/run_eval.py                             # includes generated answers

# Backups
scripts/backup.sh                                    # -> backups/<timestamp>/
scripts/restore.sh backups/<timestamp>               # replaces database and uploads
```

---

## Design Decisions and Trade-offs

- **Hybrid retrieval with RRF**: fusing by rank avoids calibrating cosine scores against full-text ranks. Keyword search runs in PostgreSQL, so no extra service is needed; the cost is that chunk text is indexed twice (Qdrant payload and PostgreSQL).
- **Cross-encoder reranking**: more accurate than embedding similarity, but slower, so it only scores the fused short list (`top_k × RETRIEVAL_CANDIDATE_MULTIPLIER`).
- **Citations chosen after generation**: the model cites `[S#]` tags; code maps them to stored metadata. Fabricated tags are ignored. If the model cites nothing, all retrieved sources are listed as a fallback.
- **Rule-based metadata and relationship detection**: deterministic and auditable, no training data, but brittle on formats the patterns do not cover. Manual relationship endpoints cover the gaps.
- **Compensating delete instead of distributed transactions**: Qdrant has no shared transaction with PostgreSQL, so vectors are removed if the commit fails, and `/documents/reconcile` repairs any remaining drift.
- **Database-backed job queue**: no extra broker to run; workers claim jobs with a conditional update, so several API processes can share the queue, and interrupted jobs are retried.
- **Database-backed rate limiting**: shared across workers without Redis, at the cost of one small write per request (`RATE_LIMIT_BACKEND=memory` avoids it for a single process).
- **Deterministic answer verification** instead of a second "judge" model: fast and explainable, but it checks evidence overlap, not meaning, so it flags rather than proves.
- **Verified LLM metadata**: the LLM only fills fields the patterns missed, and only values found in the text are kept.
- **Local LLM**: private and free per request. The default 4B instruct model answers in seconds to a minute on CPU; the 8B model is better but needs more memory than a busy 16 GB laptop has.
- **No separate frontend build**: the web interface is plain HTML/JS served by FastAPI, so there is nothing extra to install, at the cost of a simpler UI.

---

## Known Limitations

See [docs/known_limitations.md](docs/known_limitations.md). In short: answers are only as good as a small local model on CPU; extraction and relationship detection are pattern-based (with a verified LLM fallback for metadata); verification flags unsupported statements but cannot prove correctness; there is no HTTPS or multi-machine deployment, since GovLens targets a local machine.

## Web interface (React)

The UI lives in `frontend/` (Vite, React, TypeScript, Tailwind, TanStack Query). FastAPI serves the built app from `frontend/dist`; the original page stays available at `/legacy`.

| Page | What it does |
|---|---|
| Overview | Library stats, system health (database, Qdrant, Ollama), recent ingestion |
| Ask | Streaming answers, clickable `[S1]` citations that open the exact source page, per-sentence verification, supersession warnings, scope to chosen documents |
| Search | Instant hybrid passage search (no AI) with match highlighting and relevance bars; jump to "Ask AI" from any result |
| History and feedback | Every answer is saved per user; reopen, search or delete past questions; rate answers 👍/👎; copy or export an answer as Markdown |
| Analytics (admin) | Questions per day, answered and verified rates, satisfaction, response time, most cited documents, and a "worth a look" list of weak answers |
| Quick search (Ctrl/⌘ K) | Command palette: jump to any page, find documents, or start a question from anywhere |
| Find documents | A directory of ~120 official sources: **112 for India** (Gazette and law, tax and finance, regulators, 40+ ministries, courts, commissions, and 17 state governments) plus US, UK and EU. Filter by region and category; includes a step-by-step guide and ready-made search queries for locating PDFs |
| Import from link | Paste a PDF link from an approved government site; GovLens downloads and indexes it. Only allow-listed domains (`IMPORT_ALLOWED_DOMAINS`) are accepted, private/internal addresses are always refused, every redirect is re-checked, and size and PDF type are enforced |
| Plain-language brief | One click on any document: who is affected, what must be done, deadlines, penalties, written only from the document text and cached |
| Saved | Bookmark documents and keep private notes on why they matter |
| Original PDF viewer | View the uploaded PDF next to the extracted text on each document page (served only from the upload folders) |
| Audit log (admin) | Who signed in, uploaded, imported, deleted or changed users, with searchable history |
| Timeline | Documents by issue date with status and effective date; filter to what is still in force |
| Documents | Lineage graph, search and filter, drag-and-drop PDF upload with live job progress, lineage (supersedes / amends / references), page text viewer |
| Compare | Deterministic sentence-level diff of two versions plus an AI summary limited to changes actually found |
| Admin | Users and roles, ingestion jobs, index reconciliation, password change |

```bash
cd frontend && npm install
npm run dev        # http://localhost:5173, proxies /api to localhost:8000
npm run build      # outputs frontend/dist
```

## Production

```bash
cp .env.production.example .env.production   # fill in every value
make prod-up                                 # Caddy (HTTPS) + Gunicorn workers + internal-only databases
```

- With `ENV=production` the app **refuses to start** if `AUTH_ENABLED` is off, `DEBUG` is on, or the Postgres / Qdrant secrets are still defaults.
- The production stack publishes only ports 80/443; Postgres, Qdrant and Ollama are not reachable from outside. The app container runs with a read-only filesystem, no Linux capabilities, and migrations run once before workers start.
- **Account protection:** five wrong passwords in a row lock the account for 15 minutes (`LOGIN_MAX_FAILURES`, `LOGIN_LOCKOUT_MINUTES`); the error message never reveals whether an account exists, and an admin can unlock from the Admin page. Passwords need 10+ characters and may not be common or contain the username.
- **Browser hardening:** every response carries `nosniff`, `X-Frame-Options: DENY`, a strict Content-Security-Policy for the web app, `Cache-Control: no-store` on API responses, and HSTS in production.
- **Privacy:** stored questions are deleted after `QUERY_LOG_RETENTION_DAYS` (default 90) and audit entries after `AUDIT_LOG_RETENTION_DAYS` (default 365).
- **Backups:** the production stack runs a daily `pg_dump` into a `backups` volume (newest `BACKUP_KEEP` kept). The production image uses CPU PyTorch (about 2.5 GB instead of 9.9 GB); pass `--build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu124` for a GPU build.
- Dependabot opens weekly update PRs for Python, npm, Docker and GitHub Actions.
- `make backup` / `scripts/restore.sh` for data; CI (`.github/workflows/ci.yml`) runs backend tests, the frontend type-check and build, and a Docker build.
- `make help` lists all shortcuts.
