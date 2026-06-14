"""Query orchestration service."""

from __future__ import annotations

from typing import Sequence

from app.citations.builder import CitationBuilder
from app.comparison.engine import ComparisonEngine
from app.generation.generator import LLMAnswerGenerator
from app.retrieval.interfaces import DocumentRetriever
from app.services.schemas import QueryResult
from app.supersession.interfaces import SupersessionEngine
from app.retrieval.schemas import RetrievalResult


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
        llm_client: LLMClient,
    ) -> None:
        self.retriever = retriever
        self.comparison_engine = comparison_engine
        self.citation_builder = citation_builder
        self.supersession_engine = supersession_engine
        self.llm_client = llm_client

    def query(self, query: str, top_k: int = 10, document_numbers: Sequence[str] | None = None) -> QueryResult:
        retrieval_result = self.retriever.retrieve(query, top_k=top_k, document_numbers=list(document_numbers) if document_numbers else None)
        print("\nRETRIEVED CHUNKS\n")
        for i, chunk in enumerate(retrieval_result.retrieved_chunks):
            print(f"{i+1}. score={chunk.score:.4f} page={chunk.page_number}")
            print(chunk.chunk_text[:300])
            print("-" * 80)

        comparison_input = self.comparison_engine.prepare(query, retrieval_result.retrieved_chunks)
        citation_bundle = self.citation_builder.build(retrieval_result.retrieved_chunks)

        supersession_result = self._check_supersession(retrieval_result.retrieved_chunks)
        generated_answer = self.llm_client.generate(
            query=query,
            comparison_input=comparison_input,
            citation_bundle=citation_bundle,
            supersession_results=supersession_result,
        )

        return QueryResult(
            query=query,
            answer_markdown=generated_answer.answer_markdown,
            citations=[c.citation_text for c in citation_bundle.citations],
            supersession_warnings=list(generated_answer.supersession_warnings),
        )

    def _check_supersession(self, retrieved_chunks: Sequence["RetrievedChunk"]) -> "SupersessionResult | None":
        if not retrieved_chunks:
            return None

        first_document_id = retrieved_chunks[0].document_id
        return self.supersession_engine.check_document(first_document_id)
