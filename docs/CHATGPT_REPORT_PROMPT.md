# Prompts for writing the GovLens college report with ChatGPT

How to use:
1. Open a **new ChatGPT chat** (a model that accepts file uploads or long pastes works best).
2. Attach `docs/PROJECT_REPORT.md` (or paste its contents). This is the **single source of truth** with every verified fact and number.
3. Paste **Prompt 1** below. Fill the three `[...]` brackets first.
4. Then send the **chapter prompts (Prompt 2 onwards)** one at a time. Doing it chapter by chapter avoids ChatGPT cutting the answer short.
5. Paste the results into your college template. Add real screenshots where marked.

---

## Prompt 1 (master prompt, paste this first)

```text
You are helping me write my final-year college project report. I have attached a file called PROJECT_REPORT.md. It is the ONLY source of truth about my project, called GovLens (a Retrieval-Augmented Generation system for question answering and comparison over government documents).

ABOUT ME AND THE REPORT
- Programme / department: [e.g. B.Tech Computer Science and Engineering]
- Institution and academic year: [college, university, year]
- Required length and format: [e.g. 80-100 pages, 12 pt Times New Roman, 1.5 line spacing, chapters numbered 1, 2, 3, with IEEE-style references]
- Chapters my college requires: [paste the college's chapter list, or write "use a standard project-report structure"]

YOUR RULES (very important)
1. Use ONLY facts, numbers, file names, endpoint names, table names, algorithms and results that appear in PROJECT_REPORT.md. Never invent features, statistics, accuracy figures, users, datasets, dates or references. If something I ask for is not in the file, write "[NOT IN SOURCE: please provide]" instead of guessing.
2. Keep every number exactly as in the file (for example 274 tests, 42 API endpoints, 11 tables, 6 migrations, 9,287 lines of Python, 2.45 GB image, about 8 seconds per answer on GPU, 10 to 137 tokens per second).
3. Write in formal academic English, in my voice ("In this project we..."), in full paragraphs (not only bullet points), with clear headings. Explain concepts for a reader who is not an expert, then give the technical detail.
4. Where a diagram would help, produce it as a Mermaid diagram (flowchart, sequence diagram or ER diagram) that I can render, and add a caption "Figure X.Y: ...". Where a table helps, use a Markdown table with a caption "Table X.Y: ...".
5. Where a screenshot is needed, insert a placeholder line: "[INSERT SCREENSHOT: name of page and what it should show]".
6. Be honest about limitations. Do not exaggerate. Do not claim the system is perfect, certified, or "state of the art".
7. Do not shorten on your own. If a chapter is long, finish it fully; if you are about to run out of space, stop at a clean section end and write "CONTINUE" so I can ask you to go on.

HOW WE WILL WORK
I will ask for one chapter at a time. Before writing anything now, reply ONLY with: (a) the full chapter outline you propose (chapter and section headings, matching my college's chapter list if I gave one), (b) a list of any information you still need from me (names, guide, college details, screenshots, etc.), and (c) the list of Mermaid diagrams and tables you plan to include. Then wait.
```

---

## Prompt 2 onwards (send one at a time, after ChatGPT answers Prompt 1)

### Front matter

```text
Write the front matter: title page text, certificate, declaration, acknowledgement (leave names as [bracketed placeholders]), abstract (about 300 words, from section 1 of PROJECT_REPORT.md), keywords, table of contents, list of figures, list of tables, and list of abbreviations (RAG, LLM, OCR, API, REST, SSE, SSRF, CSP, RRF, FTS, GPU, CPU, CI/CD, etc.). Follow my rules from Prompt 1.
```

### Chapter 1: Introduction

```text
Write Chapter 1 (Introduction) using sections 1 and 2 of PROJECT_REPORT.md: background, problem statement, why existing approaches fall short (include the comparison table), objectives, scope (in and out of scope), and a summary of contributions. About 5 to 7 pages. Follow my rules.
```

### Chapter 2: Literature survey and background

```text
Write Chapter 2 (Literature survey and background concepts) using section 3 and the references in section 17 of PROJECT_REPORT.md. Explain: LLMs and hallucination, RAG, embeddings and vector search, keyword search, hybrid search and Reciprocal Rank Fusion (with the formula 1/(k+rank), k=60), cross-encoder re-ranking, OCR, supersession in legal text, server-sent events, scrypt password hashing, and SSRF. Cite ONLY the references listed in section 17 (do not add new ones). End with a "research gap" subsection that explains what this project adds. About 8 to 10 pages.
```

### Chapter 3: Requirements and analysis

```text
Write Chapter 3 (System analysis and requirements) from section 4: actors and roles, functional requirements (use the F1 to F25 table), non-functional requirements table, and the four use cases. Add a Mermaid use-case-style diagram or flowchart for the main use cases, and a sequence diagram for "ask a question". Include feasibility (technical, operational, economic: all components are open source and run locally). About 8 pages.
```

### Chapter 4: System design

```text
Write Chapter 4 (System design and architecture) from sections 5, 7, 8 and 10 of PROJECT_REPORT.md. Include: logical architecture (Mermaid diagram of browser, proxy, FastAPI, PostgreSQL, Qdrant, Ollama, files), why each technology was chosen (table), layered code organisation, request lifecycle, the ER diagram (Mermaid erDiagram) for all 11 tables, the data dictionary for every table, the vector store, migrations, and the API design including the full 42-endpoint table and the streaming (SSE) protocol. About 15 pages.
```

### Chapter 5: Implementation (back end)

```text
Write Chapter 5 (Implementation: back end) from section 6 of PROJECT_REPORT.md, one subsection per module, each with purpose, algorithm in plain steps, important constants and parameters, and why that design was chosen: ingestion pipeline (with a Mermaid flowchart), OCR decision rule (50 characters per page, 50% of pages), metadata extraction patterns, classification, chunking (500 to 1000 tokens, never crossing a page, 400-token windows with 50 overlap), relationship and supersession graph (include the worked example of notifications 12/2023 and 25/2024), hybrid retrieval (dense + full-text + RRF k=60 + cross-encoder + threshold 0.01), answer generation and prompt rules, citation building, the sentence-level verifier (numbers must appear; at least 50% word overlap), document comparison (difflib, 0.4 similarity), plain-language brief, background jobs (claiming, 3 attempts), history and analytics, the safe URL importer (table of controls), bookmarks, PDF serving, audit log, reconciliation, retention and warm-up. Do NOT paste long code; quote at most short snippets that appear in the source file. About 20 pages.
```

### Chapter 6: Implementation (front end)

```text
Write Chapter 6 (Implementation: front end) from section 9 of PROJECT_REPORT.md: technology and architecture (routing with code splitting, TanStack Query, auth context, typed API client, streaming with fetch, design tokens and themes), then one subsection per page (Sign in, Overview, Ask, Search, Documents, Document view, Compare, Timeline, Saved, Find documents, Analytics, Admin, command palette). For each page, insert a "[INSERT SCREENSHOT: ...]" placeholder and describe features and user flow. Include usability and accessibility, and performance. About 12 pages.
```

### Chapter 7: Security

```text
Write Chapter 7 (Security) from section 10 of PROJECT_REPORT.md: present the threat model table (16 threats and their controls) as a table, then explain in prose the most important controls: authentication and roles, scrypt and token hashing, lockout and rate limiting, the startup configuration guard, SSRF defence in depth, CSP and security headers, audit logging, container hardening, and data retention. End with the residual risks stated honestly. About 8 pages.
```

### Chapter 8: Deployment

```text
Write Chapter 8 (Deployment, DevOps and operations) from section 11 and Appendices B and C: development, GPU and production environments, the multi-stage Docker image and the 9.92 GB to 2.45 GB reduction, the production stack (Caddy HTTPS, hardened app container, internal-only databases, daily backups), configuration (summarise Appendix B as a table), CI with GitHub Actions, Dependabot, Makefile, and observability. Add a Mermaid deployment diagram. About 8 pages.
```

### Chapter 9: Testing and results

```text
Write Chapter 9 (Testing, evaluation and results) from sections 12 and 13 of PROJECT_REPORT.md: the test strategy and the 274 tests (use the table by area), what was tested live end-to-end, the evaluation method and metrics (hit@k, MRR, abstention, citation precision, verified share, threshold margin), the measured evaluation results exactly as given in section 13.2, and the performance measurements table (CPU versus GPU) with the explanation of cause and fix. Add a short discussion. Do not invent any metric that is not in the file. About 8 pages.
```

### Chapter 10: Challenges, limitations, future work, conclusion

```text
Write Chapter 10 (Challenges, limitations, future work and conclusion) from sections 14, 15 and 16 of PROJECT_REPORT.md. Present the 12 problems and solutions as a table and then discuss the three most instructive ones in prose (GPU not visible to Docker, the production admin-password bug found by live testing, and users pasting web-search queries into the app). List limitations honestly and the ten future-work items. Finish with a conclusion of 3 to 4 paragraphs. About 8 pages.
```

### References and appendices

```text
Produce the References chapter in IEEE style using ONLY the 12 items in section 17 of PROJECT_REPORT.md (do not add or alter any facts; where details are missing, mark "[verify]"). Then produce the appendices: A repository structure (keep the tree), B configuration reference table, C how to run, D sample questions and expected behaviour, E glossary, F source directory summary, G project statistics. Use the exact figures from the file.
```

### Final review pass

```text
Now act as a strict examiner. Read everything you wrote against PROJECT_REPORT.md and list: (1) any statement or number that is not supported by the file, (2) places where I overclaim, (3) inconsistencies between chapters (numbers, names, terms), (4) sections that are too thin for an 80-100 page report and what real material from the file could be added. Do not rewrite yet; just list the issues with the section name for each.
```

---

## Before you submit

- **Replace every `[bracket]`** (names, guide, college) and every `[INSERT SCREENSHOT: ...]` with a real screenshot taken from http://localhost:8000.
- **Check the numbers** against `docs/PROJECT_REPORT.md` and the running project. Examiners may ask you to demonstrate it live.
- **Declare tool use honestly** according to your institution's policy (for example, if you used AI assistance to write code or the report, add an acknowledgement line as your college requires).
- **Be ready to explain** the design choices in your own words: why two databases, why hybrid retrieval, how verification works, how supersession is detected, and what the limitations are.
