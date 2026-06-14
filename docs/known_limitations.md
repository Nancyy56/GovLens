# GovLens Known Limitations

This file records observed limitations in the current implementation. Claims are limited to what can be verified in code.

## Runtime and Hardware

- **CPU-only inference can be slow.** Embedding generation and Ollama generation may run on CPU unless the local environment provides acceleration.
- **Large prompts increase response time.** `PromptBuilder` includes source chunks, citations, and supersession warnings in the prompt.
- **Ollama response time depends on hardware.** `OllamaClient` waits for a non-streaming response with `stream=false`.
- **Model setup may require network access.** The code uses `BAAI/bge-small-en-v1.5` through `sentence-transformers` and `qwen3:8b` through Ollama.
- **OCR can be expensive.** `OCRDocumentLoader` uses `pdf2image` and `pytesseract`, which depend on system packages and image processing.

## Retrieval Quality

- **Retrieval quality depends on chunking.** The current chunker uses page-preserving word-count estimates and optional one-sentence overlap.
- **No hybrid retrieval.** The current retriever uses dense-vector similarity only.
- **No reranking.** Retrieved results are sorted by Qdrant score only.
- **Metadata filtering is limited.** Query API supports optional `document_numbers`; it does not expose arbitrary metadata filters.
- **Single Qdrant collection.** The implementation uses one collection named `government_documents`.

## Answer Generation

- **No streaming responses.** `OllamaClient` sends `stream=false` and returns the full response after generation.
- **No evaluation framework.** There is no automated precision, recall, faithfulness, or citation-accuracy evaluation in the current implementation.
- **Prompt grounding depends on retrieved chunks.** The prompt instructs the model to use only provided sources, but answer quality still depends on retrieval quality and model behavior.

## Security and Operations

- **No authentication.** API routes are not protected by authentication.
- **No authorization.** There is no role or permission model.
- **No rate limiting.** Endpoints can be called repeatedly without built-in throttling.
- **No observability stack.** The code uses basic logging and printed debug output, but there is no monitoring, tracing, metrics, or alerting implementation.
- **No deployment hardening claims.** Docker Compose is suitable for local orchestration, but the repository does not implement production authentication, TLS termination, backups, monitoring, or operational runbooks.

## Domain Coverage

- **Comparison is partial.** `ComparisonEngine` groups retrieved chunks by source document and page; it does not perform explicit diff, contradiction, or policy-change analysis.
- **Supersession coverage is partial in query flow.** `DatabaseSupersessionEngine` can traverse `SUPERSEDES` chains, but `QueryService` checks only the first retrieved document id.
- **Metadata extraction is rule-based.** It depends on regex patterns and can miss documents that do not match those patterns.
- **Classification is rule-based.** It depends on deterministic patterns and falls back to `UNKNOWN`.

## Testing and Documentation

- **Some tests may be stale.** Tests reference `DoclingDocumentLoader`, but the current `app/ingestion/pdf_loader.py` defines `PyMuPDFDocumentLoader` and `OCRDocumentLoader`.
- **Some tests may not match current Qdrant client API usage.** Current code calls `client.query_points`; older test code references `client.search`.
- **Documentation should remain conservative.** Do not describe the system as production-ready unless authentication, authorization, monitoring, deployment strategy, testing, and observability are implemented.
