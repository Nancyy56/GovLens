"""Comparison preparation engine."""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from app.schemas.processing import PageContent
from app.comparison.schemas import ComparisonInput, SourceContext
from app.models.enums import DocumentType
from app.retrieval.schemas import RetrievedChunk


class ComparisonEngine:
    """Group retrieved chunks by source document for downstream comparison.

    The engine never compares text. It only organizes chunks into the
    per-document bundles (`SourceContext`) that a future LLM or rule-based
    comparator will consume.
    """

    def prepare(
        self,
        query: str,
        retrieved_chunks: Sequence[RetrievedChunk],
    ) -> ComparisonInput:
        grouped: dict[uuid.UUID, dict] = defaultdict(
            lambda: {
                "document_number": None,
                "document_type": None,
                "pages": defaultdict(list),
            }
        )

        for chunk in retrieved_chunks:
            entry = grouped[chunk.document_id]
            entry["document_number"] = chunk.document_number
            entry["document_type"] = chunk.document_type or entry["document_type"]
            entry["pages"][chunk.page_number].append(chunk.chunk_text)

        sources = [
            SourceContext(
                document_id=document_id,
                document_number=entry["document_number"],
                document_type=entry["document_type"],
                chunks=[
                    PageContent(page_number=page_number, text="\n\n".join(texts))
                    for page_number, texts in sorted(entry["pages"].items())
                ],
            )
            for document_id, entry in sorted(grouped.items())
        ]

        return ComparisonInput(query=query, sources=sources)
