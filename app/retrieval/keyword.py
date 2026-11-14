"""Keyword (lexical) search over chunk text stored in PostgreSQL."""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.documents import Document, DocumentChunk
from app.retrieval.schemas import RetrievedChunk

_TOKEN = re.compile(r"[A-Za-z0-9]+")
# Document numbers such as 17/2024 or 04/2025-GST. Exact matches matter more
# than semantics for these, which is what dense search is weakest at.
_DOCUMENT_NUMBER = re.compile(r"\b\d+/\d{2,4}(?:-[A-Za-z0-9]+)?\b")
_EXACT_NUMBER_BOOST = 1.0


class KeywordSearcher(Protocol):
    def search(
        self,
        query: str,
        limit: int,
        document_numbers: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        ...


class PostgresKeywordSearcher:
    """Rank chunks by full-text match, boosting exact document-number hits.

    Uses PostgreSQL full-text search over the stored ``search_vector`` column (GIN index) in
    production. Other dialects, such as SQLite in tests, fall back to a simple
    in-Python term-overlap score.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self,
        query: str,
        limit: int,
        document_numbers: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        tokens = [t.lower() for t in _TOKEN.findall(query)]
        numbers = _DOCUMENT_NUMBER.findall(query)
        if not tokens and not numbers:
            return []
        if self.session.get_bind().dialect.name == "postgresql":
            return self._search_postgres(tokens, numbers, limit, document_numbers)
        return self._search_fallback(tokens, numbers, limit, document_numbers)

    def _search_postgres(
        self,
        tokens: list[str],
        numbers: list[str],
        limit: int,
        document_numbers: Sequence[str] | None,
    ) -> list[RetrievedChunk]:
        # OR the terms together: a natural-language question rarely has every
        # word in one chunk. Tokens are alphanumeric, so they are safe in tsquery syntax.
        tsquery = " | ".join(dict.fromkeys(tokens)) or "''"
        number_clauses = " OR ".join(f"c.chunk_text ILIKE :num{i}" for i in range(len(numbers)))
        boost = f"CASE WHEN {number_clauses} THEN {_EXACT_NUMBER_BOOST} ELSE 0 END" if numbers else "0"
        # search_vector is a stored, GIN-indexed to_tsvector('english', chunk_text).
        match = "c.search_vector @@ q.query"
        if numbers:
            match = f"({match} OR {number_clauses})"
        doc_filter = "AND d.document_number = ANY(:document_numbers)" if document_numbers else ""

        sql = text(
            f"""
            SELECT c.document_id, c.page_number, c.chunk_index, c.chunk_text,
                   d.document_number, d.document_type, d.title, d.file_name,
                   d.department, d.subject, d.issue_date,
                   ts_rank_cd(c.search_vector, q.query) + {boost} AS rank
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id,
                 to_tsquery('english', :tsquery) AS q(query)
            WHERE {match} {doc_filter}
            ORDER BY rank DESC
            LIMIT :limit
            """
        )
        params: dict = {"tsquery": tsquery, "limit": limit}
        for i, number in enumerate(numbers):
            params[f"num{i}"] = f"%{number}%"
        if document_numbers:
            params["document_numbers"] = list(document_numbers)

        rows = self.session.execute(sql, params).mappings().all()
        return [self._row_to_chunk(row, row["rank"]) for row in rows]

    def _search_fallback(
        self,
        tokens: list[str],
        numbers: list[str],
        limit: int,
        document_numbers: Sequence[str] | None,
    ) -> list[RetrievedChunk]:
        statement = select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id)
        if document_numbers:
            statement = statement.where(Document.document_number.in_(list(document_numbers)))

        scored: list[tuple[float, RetrievedChunk]] = []
        wanted = set(tokens)
        for chunk, document in self.session.execute(statement).all():
            text_lower = chunk.chunk_text.lower()
            chunk_tokens = set(_TOKEN.findall(text_lower))
            score = len(wanted & chunk_tokens) / max(len(wanted), 1)
            if any(number.lower() in text_lower for number in numbers):
                score += _EXACT_NUMBER_BOOST
            if score > 0:
                scored.append((score, self._row_to_chunk(self._orm_row(chunk, document), score)))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    @staticmethod
    def _orm_row(chunk: DocumentChunk, document: Document) -> dict:
        return {
            "document_id": chunk.document_id,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "chunk_text": chunk.chunk_text,
            "document_number": document.document_number,
            "document_type": document.document_type,
            "title": document.title,
            "file_name": document.file_name,
            "department": document.department,
            "subject": document.subject,
            "issue_date": document.issue_date,
        }

    @staticmethod
    def _row_to_chunk(row, score: float) -> RetrievedChunk:
        document_id = row["document_id"]
        return RetrievedChunk(
            document_id=document_id if isinstance(document_id, uuid.UUID) else uuid.UUID(str(document_id)),
            document_number=row["document_number"] or None,
            document_type=row["document_type"],
            title=row["title"],
            file_name=row["file_name"],
            department=row["department"],
            subject=row["subject"],
            page_number=row["page_number"],
            chunk_index=row["chunk_index"],
            chunk_text=row["chunk_text"],
            score=float(score),
            issue_date=row["issue_date"],
        )
