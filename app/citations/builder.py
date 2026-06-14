"""Deterministic legal citation builder."""

from __future__ import annotations

from typing import Sequence

from app.citations.schemas import Citation, CitationBundle
from app.retrieval.schemas import RetrievedChunk


class CitationBuilder:
    """Convert retrieved chunks into deterministic legal citations.

    Citations preserve the exact page number and document identifier needed
    for legal references. No LLM or external service is involved.
    """

    def build(self, retrieved_chunks: Sequence[RetrievedChunk]) -> CitationBundle:
        citations = [self._chunk_to_citation(chunk) for chunk in retrieved_chunks]
        return CitationBundle(citations=citations)

    def _chunk_to_citation(self, chunk: RetrievedChunk) -> Citation:
        header = self._build_header(chunk)
        lines = [header]

        if chunk.issue_date is not None:
            lines.append(f"Dated: {chunk.issue_date.isoformat()}")

        lines.append(f"(Page {chunk.page_number})")

        return Citation(
            document_id=chunk.document_id,
            document_number=chunk.document_number,
            document_type=chunk.document_type,
            page_number=chunk.page_number,
            issue_date=chunk.issue_date,
            citation_text="\n".join(lines),
        )

    @staticmethod
    def _build_header(chunk: RetrievedChunk) -> str:
        doc_type = chunk.document_type
        doc_number = chunk.document_number

        type_label = doc_type.title() if doc_type else ""

        if type_label and doc_number:
            return f"{type_label} No. {doc_number}"

        if chunk.title:
            return chunk.title

        if chunk.file_name:
            return chunk.file_name

        if type_label:
            return type_label

        if doc_number:
            return str(doc_number)

        return "Unknown Document"