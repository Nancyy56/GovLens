"""Turn stored chunks into embedded windows for Qdrant."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

from app.chunking.tokens import TextTokenizer, WordTokenizer
from app.models.enums import DocumentType
from app.vectorstore.interfaces import EmbeddingProvider
from app.vectorstore.schemas import EmbeddedChunk


def _chunk_metadata(chunk) -> dict:
    # Pipeline chunks may carry a metadata dict; ORM rows have SQLAlchemy's
    # unrelated `metadata` attribute, so only accept real dicts.
    value = getattr(chunk, "metadata", None)
    return value if isinstance(value, dict) else {}


def build_embedded_chunks(
    *,
    document_id: uuid.UUID,
    document_number: str | None,
    document_type: DocumentType | None,
    chunks: Sequence,  # objects with page_number, chunk_index, chunk_text
    embedding_provider: EmbeddingProvider,
    tokenizer: TextTokenizer | None,
    title: str | None,
    file_name: str | None,
    department: str | None,
    subject: str | None,
    issue_date: date | None,
) -> list[EmbeddedChunk]:
    """Embed every window of every chunk; each point carries the full chunk text for citations."""

    tokenizer = tokenizer or WordTokenizer()
    payload = {
        "title": title,
        "file_name": file_name,
        "department": department,
        "subject": subject,
        "issue_date": issue_date.isoformat() if issue_date else None,
    }
    windows: list[tuple[object, int, str]] = [
        (chunk, index, window)
        for chunk in chunks
        for index, window in enumerate(tokenizer.windows(chunk.chunk_text))
    ]
    if not windows:
        return []
    embeddings = embedding_provider.embed([window for _, _, window in windows])
    return [
        EmbeddedChunk(
            document_id=document_id,
            document_number=document_number or None,
            document_type=document_type,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            window_index=window_index,
            chunk_text=chunk.chunk_text,
            embedding=embedding,
            metadata={**_chunk_metadata(chunk), **payload},
        )
        for (chunk, window_index, _), embedding in zip(windows, embeddings)
    ]
