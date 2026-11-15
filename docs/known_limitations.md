# GovLens Known Limitations

This file records the limitations that remain. Claims are limited to what can be verified in code or was observed on the development machine (16 GB laptop, CPU only).

## Answer Quality

- **A small local model.** The default `qwen3:4b-instruct` answers in about 20 seconds to 3 minutes on a laptop CPU (71 s on average in the evaluation), but it follows instructions less reliably than larger models: it sometimes cites the wrong source tag or adds commentary, which verification then flags. `qwen3:8b` answers better and needs considerably more memory.
- **Ollama's prompt cache can exhaust RAM.** Ollama 0.40 keeps up to 8 GB of earlier prompts in memory, and it cannot be capped by a setting. On the 15 GB development laptop this let the out-of-memory killer stop the model (with both the 8B and the 4B models). GovLens therefore unloads the model after each answer by default (`OLLAMA_KEEP_ALIVE=0`, about 5 s extra per answer) and retries once if the model process dies before answering. On machines with more memory, set `OLLAMA_KEEP_ALIVE=5m` for faster answers.
- **Verification flags, it does not prove.** Each sentence must have its numbers and most of its key words in the cited pages. A sentence that reuses the source's words but draws a wrong conclusion passes; a correct sentence that paraphrases heavily can be flagged. Treat "could not be confirmed" as "check by hand", and "all confirmed" as "the evidence is there", not "the answer is correct".
- **Relevance cut-off is a fixed threshold.** `RERANKER_MIN_SCORE` (0.01) separates relevant from unrelated chunks on the evaluation set by a wide margin (see `min_correct_chunk_score` and `max_unanswerable_score` in the evaluation output), but other corpora may need tuning. It does not apply when the reranker is disabled.
- **Citation fallback.** If the model cites no valid `[S#]` tags, all retrieved sources are listed and `citations_inferred` is true.
- **The evaluation set is modest.** 22 questions over five documents plus relationship checks. It catches regressions and shows trends; it is not a statistically strong benchmark.

## Extraction and Relationships

- **Pattern-based first.** Document numbers, dates, subjects, departments, and types come from regular expressions; the LLM fills only the fields those miss, and only values verifiable in the text are kept. Documents in unusual formats can still end up with empty fields.
- **OCR quality limits everything downstream.** Tesseract misreads tables and some digits in scanned PDFs (for example "7]" for "71"); answers about such pages can be wrong even when retrieval is right.
- **Relationship wording.** Detection handles "in supersession of X", "X is hereby rescinded/withdrawn", "amends X", and lists of numbers, from the clause around each mention. Unusual phrasing ("X shall cease to have effect") is classified as a plain reference. Links can be added manually and survive re-ingestion.
- **Number variants.** Matching ignores case and spaces, but "1/2017-Central Tax (Rate)" is captured as `1/2017-Central`, and a document cited by a different form of its number ("No. 01/2017") is not matched.

## Security and Operations (local deployment)

- **No HTTPS.** GovLens targets a single machine; passwords and tokens cross the network in clear text if the port is exposed beyond `localhost`. Put a TLS reverse proxy in front before exposing it.
- **No per-document permissions.** Roles control actions (view, edit, administer), not which documents a user can see.
- **Sessions are bearer tokens in the browser's session storage.** They end when the tab closes or after `TOKEN_TTL_HOURS`; there is no single sign-on or multi-factor authentication.
- **One machine.** The job queue and rate limits work across several API processes sharing one PostgreSQL, but there is no configuration for multiple machines, autoscaling, or high availability.
- **Backups are manual.** `scripts/backup.sh` must be run (or scheduled with cron); there is no automatic off-site copy.
- **Metrics without dashboards.** `/api/v1/metrics` exposes Prometheus metrics; no Prometheus/Grafana is bundled and there are no alerts.

## Testing

- Unit and API tests use SQLite and fakes. PostgreSQL-specific code (full-text search, migrations, the upsert-based rate limiter on PostgreSQL) is exercised by the end-to-end runs against the Docker stack, not by `pytest`.
- The web interface is checked with a scripted headless-browser run, not an automated test suite.
