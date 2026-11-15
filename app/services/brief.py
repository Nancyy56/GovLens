"""Plain-language briefs of a single document.

The model sees only the document's own text (the first ``MAX_CHARS`` characters, so it fits the
model's context window), is told to cite pages, and to say "Not stated" instead of guessing.
Briefs are cached per document version, since the same document is opened many times.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict

from pydantic import BaseModel

from app.generation.interfaces import LLMClient
from app.services.documents import DocumentService

MAX_CHARS = 7000
CACHE_SIZE = 128

PROMPT = """You explain government documents to busy readers in plain language.
Use ONLY the document text below. Do not add outside knowledge. If something is not stated, write "Not stated".
Cite page numbers like (p.2). Keep every section short; use bullet points where there are several items.

Document: {number} - {title}
Type: {doc_type}. Issued: {issued}.

Document text:
{text}

Write the brief in Markdown with exactly these sections:
## In one sentence
## Who is affected
## What changes or must be done
## Deadlines and dates
## Penalties or consequences
"""


class DocumentBrief(BaseModel):
    document_id: uuid.UUID
    markdown: str
    pages_used: int
    total_pages: int
    # True when the document is longer than the model can read in one go.
    truncated: bool
    cached: bool = False


class BriefService:
    _cache: OrderedDict[tuple[str, str], DocumentBrief] = OrderedDict()
    _lock = threading.Lock()

    def __init__(self, documents: DocumentService, llm: LLMClient) -> None:
        self.documents = documents
        self.llm = llm

    def brief(self, document_id: uuid.UUID, *, refresh: bool = False) -> DocumentBrief:
        detail = self.documents.get(document_id)  # raises DocumentNotFoundError for unknown ids
        key = (str(document_id), detail.updated_at.isoformat())
        if not refresh:
            with self._lock:
                hit = self._cache.get(key)
                if hit is not None:
                    self._cache.move_to_end(key)
                    return hit.model_copy(update={"cached": True})

        text, used, total = self._read(document_id)
        prompt = PROMPT.format(
            number=detail.document_number,
            title=detail.title,
            doc_type=detail.document_type.value.title(),
            issued=detail.issue_date.isoformat() if detail.issue_date else "unknown date",
            text=text,
        )
        result = DocumentBrief(
            document_id=document_id,
            markdown=self.llm.generate(prompt).strip(),
            pages_used=used,
            total_pages=total,
            truncated=used < total or text.endswith("[…]"),
        )
        with self._lock:
            self._cache[key] = result
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return result

    def _read(self, document_id: uuid.UUID) -> tuple[str, int, int]:
        pages = self.documents.load_pages(document_id)
        parts: list[str] = []
        remaining = MAX_CHARS
        used = 0
        for page in pages:
            body = page.text.strip()
            if not body:
                used += 1
                continue
            header = f"[Page {page.page_number}]\n"
            if remaining <= len(header) + 40:
                break
            piece = body[: remaining - len(header)]
            parts.append(header + piece + ("\n[…]" if len(piece) < len(body) else ""))
            remaining -= len(header) + len(piece)
            used += 1
            if len(piece) < len(body):
                break
        return "\n\n".join(parts), used, len(pages)
