"""Query orchestration service."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Sequence

from pydantic import BaseModel

from app.citations.builder import CitationBuilder
from app.core import metrics
from app.citations.schemas import CitationBundle
from app.comparison.engine import ComparisonEngine
from app.comparison.schemas import ComparisonInput
from app.generation.generator import LLMAnswerGenerator
from app.generation.prompt_builder import NO_ANSWER_TEXT
from app.generation.schemas import GeneratedAnswer
from app.retrieval.interfaces import DocumentRetriever
from app.retrieval.schemas import RetrievedChunk
from app.services.schemas import QueryResult, SourceCitation
from app.supersession.interfaces import SupersessionEngine
from app.supersession.schemas import SupersessionResult

logger = logging.getLogger(__name__)


class _PreparedQuery(BaseModel):
    query: str
    chunks: list[RetrievedChunk]
    comparison_input: ComparisonInput
    citation_bundle: CitationBundle
    supersession_results: list[SupersessionResult]


class QueryService:
    """Orchestrate retrieval, comparison, citation, supersession, and generation
    for a user query.

    Each dependency is injected as an interface so the service can be tested
    with fakes and swapped for production implementations without rework.
    """

    def __init__(
        self,
        retriever: DocumentRetriever,
        comparison_engine: ComparisonEngine,
        citation_builder: CitationBuilder,
        supersession_engine: SupersessionEngine,
        llm_client: LLMAnswerGenerator,
    ) -> None:
        self.retriever = retriever
        self.comparison_engine = comparison_engine
        self.citation_builder = citation_builder
        self.supersession_engine = supersession_engine
        self.llm_client = llm_client

    def query(self, query: str, top_k: int = 10, document_numbers: Sequence[str] | None = None) -> QueryResult:
        prepared = self._prepare(query, top_k, document_numbers)
        if not prepared.chunks:
            metrics.queries.inc("no_relevant_sources")
            return QueryResult(query=query, answer_markdown=NO_ANSWER_TEXT)

        generated_answer = self.llm_client.generate(
            query=query,
            comparison_input=prepared.comparison_input,
            citation_bundle=prepared.citation_bundle,
            supersession_results=prepared.supersession_results,
        )
        metrics.queries.inc("verified" if generated_answer.verification.all_supported else "needs_review")
        return self._to_result(query, generated_answer)

    def search(
        self,
        query: str,
        top_k: int = 10,
        document_numbers: Sequence[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Return ranked chunks without generating an answer."""

        return list(
            self.retriever.retrieve(
                query,
                top_k=top_k,
                document_numbers=list(document_numbers) if document_numbers else None,
            ).retrieved_chunks
        )

    def stream(
        self,
        query: str,
        top_k: int = 10,
        document_numbers: Sequence[str] | None = None,
    ) -> Iterator[dict]:
        """Yield server-sent-event payloads: ``retrieval``, then ``token``s, then ``done``.

        Retrieval and the supersession check run eagerly, before the iterator
        is returned, so every database read finishes while the request's
        session is still guaranteed to be open.
        """

        prepared = self._prepare(query, top_k, document_numbers)
        return self._stream_events(prepared)

    def _stream_events(self, prepared: _PreparedQuery) -> Iterator[dict]:
        yield {
            "event": "retrieval",
            "data": {
                "retrieved_chunks": len(prepared.chunks),
                "documents": len(prepared.comparison_input.sources),
                "supersession_warnings": [
                    result.model_dump(mode="json")
                    for result in prepared.supersession_results
                    if result.is_superseded
                ],
            },
        }
        if not prepared.chunks:
            yield {"event": "token", "data": {"text": NO_ANSWER_TEXT}}
            result = QueryResult(query=prepared.query, answer_markdown=NO_ANSWER_TEXT)
            yield {"event": "done", "data": result.model_dump(mode="json")}
            return

        for item in self.llm_client.stream(
            query=prepared.query,
            comparison_input=prepared.comparison_input,
            citation_bundle=prepared.citation_bundle,
            supersession_results=prepared.supersession_results,
        ):
            if isinstance(item, GeneratedAnswer):
                result = self._to_result(prepared.query, item)
                yield {"event": "done", "data": result.model_dump(mode="json")}
            else:
                yield {"event": "token", "data": {"text": item}}

    def _prepare(self, query: str, top_k: int, document_numbers: Sequence[str] | None) -> _PreparedQuery:
        retrieval_result = self.retriever.retrieve(
            query,
            top_k=top_k,
            document_numbers=list(document_numbers) if document_numbers else None,
        )
        chunks = list(retrieval_result.retrieved_chunks)
        for rank, chunk in enumerate(chunks, start=1):
            logger.debug(
                "Retrieved #%s score=%.4f doc=%s page=%s",
                rank,
                chunk.score,
                chunk.document_number or chunk.document_id,
                chunk.page_number,
            )

        return _PreparedQuery.model_construct(
            query=query,
            chunks=chunks,
            comparison_input=self.comparison_engine.prepare(query, chunks),
            citation_bundle=self.citation_builder.build(chunks),
            supersession_results=self._check_supersession(chunks),
        )

    def _check_supersession(self, retrieved_chunks: Sequence[RetrievedChunk]) -> list[SupersessionResult]:
        """Check every distinct retrieved document, not just the top-ranked one."""

        seen: set[uuid.UUID] = set()
        results: list[SupersessionResult] = []
        for chunk in retrieved_chunks:
            if chunk.document_id in seen:
                continue
            seen.add(chunk.document_id)
            result = self.supersession_engine.check_document(chunk.document_id)
            if result is not None:
                results.append(result)
        return results

    @staticmethod
    def _to_result(query: str, generated_answer: GeneratedAnswer) -> QueryResult:
        sources = [
            SourceCitation(
                label=item.label,
                document_id=item.citation.document_id,
                document_number=item.citation.document_number,
                document_type=item.citation.document_type,
                page_number=item.citation.page_number,
                issue_date=item.citation.issue_date,
                citation_text=item.citation.citation_text,
            )
            for item in generated_answer.labeled_citations
        ]
        return QueryResult(
            query=query,
            answer_markdown=generated_answer.answer_markdown,
            citations=[
                f"[{source.label}] {source.citation_text}" if source.label else source.citation_text
                for source in sources
            ],
            sources=sources,
            supersession_warnings=list(generated_answer.supersession_warnings),
            verification=generated_answer.verification,
            citations_inferred=generated_answer.citations_inferred,
        )
