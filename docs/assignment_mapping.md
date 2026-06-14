# Assignment Mapping

This matrix maps observed assignment-style requirements to current implementation evidence. Status values are conservative:

- **IMPLEMENTED**: code path exists and is wired into the main flow.
- **PARTIAL**: code exists, but the main flow covers only part of the requirement or the feature is preparatory.
- **NOT IMPLEMENTED**: no verified implementation found in current source.

---

Requirement:
Ingest PDF documents.

Status:
IMPLEMENTED

Implementation Location:
`app/ingestion/pdf_loader.py`, `app/services/ingestion.py`

Evidence:
`PyMuPDFDocumentLoader.load`, `OCRDocumentLoader.load`, `DocumentIngestionService.ingest`

Notes:
The ingestion service loads a PDF, extracts metadata, classifies it, chunks it, embeds chunks, stores vectors in Qdrant, and persists PostgreSQL rows.

---

Requirement:
Extract text from digital PDFs.

Status:
IMPLEMENTED

Implementation Location:
`app/ingestion/pdf_loader.py`

Evidence:
`PyMuPDFDocumentLoader.load`, `PyMuPDFDocumentLoader._load_pymupdf`

Notes:
Digital PDFs are loaded with PyMuPDF and converted into ordered `PageContent` records.

---

Requirement:
Support OCR for scanned PDFs.

Status:
IMPLEMENTED

Implementation Location:
`app/ingestion/pdf_loader.py`

Evidence:
`OCRDocumentLoader.load`, `get_document_loader`

Notes:
OCR fallback uses `pdf2image.convert_from_path` and `pytesseract.image_to_string`. OCR is not verified end-to-end in this documentation pass.

---

Requirement:
Preserve page numbers for citations.

Status:
IMPLEMENTED

Implementation Location:
`app/schemas/processing.py`, `app/ingestion/pdf_loader.py`, `app/chunking/chunker.py`

Evidence:
`PageContent.page_number`, `PyMuPDFDocumentLoader.load`, `OCRDocumentLoader.load`, `RuleBasedDocumentChunker._chunk_page`

Notes:
Page numbers are one-based in schemas and carried through chunk metadata and Qdrant payload.

---

Requirement:
Extract metadata such as document number, date, department, subject, and references.

Status:
IMPLEMENTED

Implementation Location:
`app/metadata/extractors.py`, `app/metadata/patterns.py`

Evidence:
`RuleBasedMetadataExtractor.extract`, `_extract_document_number`, `_extract_issue_date`, `_extract_subject`, `_extract_department`, `_extract_referenced_documents`

Notes:
Extraction is rule-based and pattern-dependent. Missing matches produce `None` fields.

---

Requirement:
Classify document type.

Status:
IMPLEMENTED

Implementation Location:
`app/classification/classifier.py`, `app/classification/rules.py`

Evidence:
`RuleBasedDocumentClassifier.classify`, `build_compiled_patterns`

Notes:
Classification uses deterministic regex patterns and falls back to `UNKNOWN`.

---

Requirement:
Chunk documents into 500-1000 token chunks.

Status:
IMPLEMENTED

Implementation Location:
`app/chunking/chunker.py`

Evidence:
`RuleBasedDocumentChunker.__init__`, `RuleBasedDocumentChunker._chunk_page`, `RuleBasedDocumentChunker._group_sentences`

Notes:
The implementation uses word-count estimates (`len(text.split())`) as token estimates. Defaults are `min_tokens=500` and `max_tokens=1000`.

---

Requirement:
Do not cross page boundaries during chunking.

Status:
IMPLEMENTED

Implementation Location:
`app/chunking/chunker.py`

Evidence:
`RuleBasedDocumentChunker.chunk`, `RuleBasedDocumentChunker._chunk_page`

Notes:
Each page is chunked independently, so chunks do not span pages.

---

Requirement:
Generate semantic embeddings.

Status:
IMPLEMENTED

Implementation Location:
`app/vectorstore/embedder.py`, `app/services/dependencies.py`

Evidence:
`HuggingFaceEmbeddingProvider`, `get_embedding_provider`

Notes:
The configured model is `BAAI/bge-small-en-v1.5`. A `HashEmbeddingProvider` also exists but is not used by the main ingestion/query dependency wiring.

---

Requirement:
Store embeddings in Qdrant.

Status:
IMPLEMENTED

Implementation Location:
`app/vectorstore/qdrant_store.py`, `app/services/ingestion.py`

Evidence:
`QdrantVectorStore.upsert`, `QdrantVectorStore._ensure_collection`, `DocumentIngestionService.ingest`

Notes:
The Qdrant collection name is `government_documents`. Vector size is inferred from the first batch of embeddings. Distance is cosine.

---

Requirement:
Store document metadata and chunk text in PostgreSQL.

Status:
IMPLEMENTED

Implementation Location:
`app/models/documents.py`, `app/repositories/documents.py`, `alembic/versions/20260612_0001_create_document_domain_tables.py`

Evidence:
`Document`, `DocumentChunk`, `DocumentRepository`, `DocumentChunkRepository`, Alembic migration `20260612_0001`

Notes:
PostgreSQL stores metadata rows, chunk text rows, and document relationships.

---

Requirement:
Retrieve relevant chunks by semantic similarity.

Status:
IMPLEMENTED

Implementation Location:
`app/retrieval/retriever.py`, `app/vectorstore/qdrant_store.py`

Evidence:
`QdrantDocumentRetriever.retrieve`, `QdrantVectorStore.search`

Notes:
Retrieval is dense-vector similarity search. There is no hybrid retrieval or reranking.

---

Requirement:
Support top-k retrieval.

Status:
IMPLEMENTED

Implementation Location:
`app/api/schemas.py`, `app/retrieval/retriever.py`, `app/services/query.py`

Evidence:
`QueryRequest.top_k`, `QdrantDocumentRetriever.retrieve`, `QueryService.query`

Notes:
Default `top_k` is 10. API validation allows values from 1 to 100.

---

Requirement:
Filter retrieval by document number.

Status:
IMPLEMENTED

Implementation Location:
`app/api/schemas.py`, `app/retrieval/retriever.py`, `app/vectorstore/qdrant_store.py`

Evidence:
`QueryRequest.document_numbers`, `QdrantDocumentRetriever.retrieve`, `QdrantVectorStore._build_filters`

Notes:
Filtering is limited to `document_numbers`. The API does not expose arbitrary metadata filters.

---

Requirement:
Prepare comparison input across multiple sources.

Status:
PARTIAL

Implementation Location:
`app/comparison/engine.py`

Evidence:
`ComparisonEngine.prepare`

Notes:
The engine groups chunks by source document and page. It does not perform explicit diff, contradiction, or policy-change analysis.

---

Requirement:
Generate deterministic citations.

Status:
IMPLEMENTED

Implementation Location:
`app/citations/builder.py`

Evidence:
`CitationBuilder.build`, `CitationBuilder._chunk_to_citation`, `CitationBuilder._build_header`

Notes:
Citations include document type and number when available, issue date when available, and page number.

---

Requirement:
Check supersession relationships.

Status:
PARTIAL

Implementation Location:
`app/supersession/engine.py`, `app/models/documents.py`, `app/services/query.py`

Evidence:
`DatabaseSupersessionEngine.check_document`, `DatabaseSupersessionEngine._build_chain`, `QueryService._check_supersession`

Notes:
The engine can traverse `SUPERSEDES` chains in PostgreSQL. Query flow checks only the first retrieved chunk's document id.

---

Requirement:
Generate citation-backed answers.

Status:
IMPLEMENTED

Implementation Location:
`app/generation/prompt_builder.py`, `app/generation/generator.py`, `app/generation/ollama_client.py`, `app/services/query.py`

Evidence:
`PromptBuilder.build`, `LLMAnswerGenerator.generate`, `OllamaClient.generate`, `QueryService.query`

Notes:
The prompt includes source chunks, citations, and supersession warnings. Answer faithfulness depends on retrieval quality and model behavior.

---

Requirement:
Use local Ollama inference.

Status:
IMPLEMENTED

Implementation Location:
`app/generation/ollama_client.py`, `app/services/dependencies.py`

Evidence:
`OllamaClient`, `LLMAnswerGenerator`, `get_query_service`

Notes:
The client calls `http://ollama:11434/api/generate` with model `qwen3:8b`, `stream=false`, `temperature=0`, and `num_predict=512`.

---

Requirement:
Expose ingestion and query APIs.

Status:
IMPLEMENTED

Implementation Location:
`app/api/routes/ingestion.py`, `app/api/routes/query.py`, `app/api/health.py`, `app/main.py`

Evidence:
`ingest_document`, `query_documents`, `health_check`, `create_app`

Notes:
Routes are included under `/api/v1`.

---

Requirement:
Provide local service orchestration.

Status:
IMPLEMENTED

Implementation Location:
`docker-compose.yml`, `Dockerfile`

Evidence:
Docker Compose services `postgres`, `qdrant`, `ollama`, and `app`

Notes:
Docker Compose starts local services. Model downloads or pulls may require network access before use.

---

Requirement:
Support authentication and authorization.

Status:
NOT IMPLEMENTED

Implementation Location:
Not found

Evidence:
No verified authentication or authorization implementation in `app/api`, `app/main.py`, or dependency wiring.

Notes:
Endpoints are publicly accessible.

---

Requirement:
Support streaming responses.

Status:
NOT IMPLEMENTED

Implementation Location:
Not found

Evidence:
`OllamaClient.generate` sends `stream=false`; API routes return complete response models.

Notes:
There is no `StreamingResponse` or streaming endpoint implementation.

---

Requirement:
Provide hybrid retrieval.

Status:
NOT IMPLEMENTED

Implementation Location:
Not found

Evidence:
No BM25, sparse vector, reciprocal rank fusion, or hybrid retrieval implementation found.

Notes:
Retrieval is dense-vector only.

---

Requirement:
Provide reranking.

Status:
NOT IMPLEMENTED

Implementation Location:
Not found

Evidence:
No cross-encoder, reranker, or post-retrieval ranking implementation found.

Notes:
Retrieved chunks are sorted by Qdrant score.

---

Requirement:
Provide automated RAG evaluation.

Status:
NOT IMPLEMENTED

Implementation Location:
Not found

Evidence:
No precision, recall, faithfulness, citation accuracy, or evaluation harness found.

Notes:
Tests exist for individual components, but there is no automated end-to-end RAG quality evaluation framework.
