"""Unit tests for generation layer."""

from __future__ import annotations

from typing import Any

import pytest

from app.comparison.schemas import ComparisonInput, SourceContext
from app.citations.schemas import Citation, CitationBundle
from app.generation import LLMAnswerGenerator, PromptBuilder
from app.generation.interfaces import LLMClient
from app.generation.schemas import GeneratedAnswer
from app.models.enums import DocumentType
from app.schemas.processing import PageContent
from app.supersession.schemas import DocumentReference, SupersessionResult


class FakeLLMClient:
    def __init__(self, response: str = "fake answer") -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class TestPromptBuilder:
    def test_prompt_includes_query(self) -> None:
        builder = PromptBuilder()
        prompt = builder.build("tax query", ComparisonInput(query="tax query"), CitationBundle())
        assert prompt.startswith("You are a retrieval-grounded document assistant.")
        assert "# Query\ntax query" in prompt

    def test_prompt_includes_sources(self) -> None:
        builder = PromptBuilder()
        comparison = ComparisonInput(
            query="q",
            sources=[
                SourceContext(
                    document_id="11111111-1111-1111-1111-111111111111",
                    document_number="N1",
                    document_type=DocumentType.NOTIFICATION,
                    chunks=[PageContent(page_number=1, text="chunk text")],
                )
            ],
        )
        prompt = builder.build("q", comparison, CitationBundle())
        assert "## NOTIFICATION N1" in prompt
        assert "chunk text" in prompt

    def test_prompt_includes_citations(self) -> None:
        citation = Citation(
            document_id="11111111-1111-1111-1111-111111111111",
            document_number="N1",
            document_type=DocumentType.NOTIFICATION,
            page_number=3,
            citation_text="Notification No. N1\n(Page 3)",
        )
        builder = PromptBuilder()
        prompt = builder.build("q", ComparisonInput(query="q"), CitationBundle(citations=[citation]))
        assert "# Citations" in prompt
        assert "Notification No. N1" in prompt

    def test_prompt_includes_supersession_warnings(self) -> None:
        supersession = SupersessionResult(
            document_id="11111111-1111-1111-1111-111111111111",
            document_number="OLD",
            is_superseded=True,
            latest_document_id="22222222-2222-2222-2222-222222222222",
            latest_document_number="NEW",
            supersession_chain=[
                DocumentReference(document_id="11111111-1111-1111-1111-111111111111", document_number="OLD"),
                DocumentReference(document_id="22222222-2222-2222-2222-222222222222", document_number="NEW"),
            ],
        )
        builder = PromptBuilder()
        prompt = builder.build("q", ComparisonInput(query="q"), CitationBundle(), supersession_results=supersession)
        assert "# Supersession Warnings" in prompt
        assert "OLD -> NEW" in prompt

    def test_empty_citations_and_warnings(self) -> None:
        builder = PromptBuilder()
        prompt = builder.build("q", ComparisonInput(query="q"), CitationBundle())
        assert "# Citations" not in prompt
        assert "# Supersession Warnings" not in prompt


class TestLLMAnswerGenerator:
    def test_generate_returns_answer(self) -> None:
        client = FakeLLMClient(response="custom answer")
        generator = LLMAnswerGenerator(llm_client=client)
        result = generator.generate("q", ComparisonInput(query="q"), CitationBundle())
        assert isinstance(result, GeneratedAnswer)
        assert result.answer_markdown == "custom answer"

    def test_generate_includes_citations(self) -> None:
        citation = Citation(
            document_id="11111111-1111-1111-1111-111111111111",
            document_number="N1",
            page_number=1,
            citation_text="N1 (Page 1)",
        )
        generator = LLMAnswerGenerator(llm_client=FakeLLMClient())
        result = generator.generate("q", ComparisonInput(query="q"), CitationBundle(citations=[citation]))
        assert len(result.citations) == 1
        assert result.citations[0].document_number == "N1"

    def test_generate_includes_supersession_warnings(self) -> None:
        supersession = SupersessionResult(
            document_id="11111111-1111-1111-1111-111111111111",
            document_number="OLD",
            is_superseded=True,
            latest_document_id="22222222-2222-2222-2222-222222222222",
            latest_document_number="NEW",
        )
        generator = LLMAnswerGenerator(llm_client=FakeLLMClient())
        result = generator.generate("q", ComparisonInput(query="q"), CitationBundle(), supersession_results=supersession)
        assert len(result.supersession_warnings) == 1
        assert result.supersession_warnings[0].latest_document_number == "NEW"

    def test_generate_skips_non_superseded_warnings(self) -> None:
        supersession = SupersessionResult(
            document_id="11111111-1111-1111-1111-111111111111",
            document_number="CURRENT",
            is_superseded=False,
            latest_document_id="11111111-1111-1111-1111-111111111111",
            latest_document_number="CURRENT",
        )
        generator = LLMAnswerGenerator(llm_client=FakeLLMClient())
        result = generator.generate("q", ComparisonInput(query="q"), CitationBundle(), supersession_results=supersession)
        assert result.supersession_warnings == []

    def test_generate_empty_citations(self) -> None:
        generator = LLMAnswerGenerator(llm_client=FakeLLMClient())
        result = generator.generate("q", ComparisonInput(query="q"), CitationBundle())
        assert result.citations == []
        assert result.supersession_warnings == []


def _two_page_input() -> tuple[ComparisonInput, CitationBundle]:
    doc_id = "11111111-1111-1111-1111-111111111111"
    comparison = ComparisonInput(
        query="q",
        sources=[
            SourceContext(
                document_id=doc_id,
                document_number="N1",
                document_type=DocumentType.NOTIFICATION,
                chunks=[PageContent(page_number=1, text="one"), PageContent(page_number=2, text="two")],
            )
        ],
    )
    citations = CitationBundle(
        citations=[
            Citation(document_id=doc_id, document_number="N1", page_number=1, citation_text="Notification No. N1\n(Page 1)"),
            Citation(document_id=doc_id, document_number="N1", page_number=1, citation_text="Notification No. N1\n(Page 1)"),
            Citation(document_id=doc_id, document_number="N1", page_number=2, citation_text="Notification No. N1\n(Page 2)"),
        ]
    )
    return comparison, citations


class TestSourceLabelsAndCitationFiltering:
    def test_prompt_tags_each_page_and_dedupes_citations(self) -> None:
        comparison, citations = _two_page_input()
        prompt = PromptBuilder().build("q", comparison, citations)
        assert "### [S1] Page 1" in prompt and "### [S2] Page 2" in prompt
        assert prompt.count("[S1] Notification No. N1") == 1

    def test_only_cited_sources_are_returned(self) -> None:
        comparison, citations = _two_page_input()
        generator = LLMAnswerGenerator(llm_client=FakeLLMClient("Rates changed [S2]."))
        result = generator.generate("q", comparison, citations)
        assert [c.page_number for c in result.citations] == [2]
        assert [c.label for c in result.labeled_citations] == ["S2"]
        assert result.answer_markdown.endswith("**Sources**\n- [S2] Notification No. N1, (Page 2)")

    def test_combined_tags_are_understood(self) -> None:
        comparison, citations = _two_page_input()
        generator = LLMAnswerGenerator(llm_client=FakeLLMClient("Both [S2, S1] and again [S1][S2]."))
        result = generator.generate("q", comparison, citations)
        assert [c.label for c in result.labeled_citations] == ["S2", "S1"]

    def test_unknown_tags_are_ignored(self) -> None:
        comparison, citations = _two_page_input()
        generator = LLMAnswerGenerator(llm_client=FakeLLMClient("Made up [S9] but real [S1]."))
        result = generator.generate("q", comparison, citations)
        assert [c.label for c in result.labeled_citations] == ["S1"]

    def test_no_answer_returns_no_citations(self) -> None:
        from app.generation.prompt_builder import NO_ANSWER_TEXT

        comparison, citations = _two_page_input()
        result = LLMAnswerGenerator(llm_client=FakeLLMClient(NO_ANSWER_TEXT)).generate("q", comparison, citations)
        assert result.citations == []
        assert result.answer_markdown == NO_ANSWER_TEXT

    def test_untagged_answer_falls_back_to_all_unique_sources(self) -> None:
        comparison, citations = _two_page_input()
        result = LLMAnswerGenerator(llm_client=FakeLLMClient("An answer without tags.")).generate("q", comparison, citations)
        assert [c.page_number for c in result.citations] == [1, 2]

    def test_multi_document_rule_only_with_several_documents(self) -> None:
        comparison, citations = _two_page_input()
        assert "more than one document" not in PromptBuilder().build("q", comparison, citations)
        second = SourceContext(
            document_id="22222222-2222-2222-2222-222222222222",
            document_number="N2",
            chunks=[PageContent(page_number=1, text="x")],
        )
        both = ComparisonInput(query="q", sources=[*comparison.sources, second])
        assert "more than one document" in PromptBuilder().build("q", both, citations)

    def test_prompt_lists_every_superseded_document(self) -> None:
        def superseded(old: str, new: str) -> SupersessionResult:
            return SupersessionResult(
                document_id="11111111-1111-1111-1111-111111111111",
                document_number=old,
                is_superseded=True,
                latest_document_id="22222222-2222-2222-2222-222222222222",
                latest_document_number=new,
            )

        prompt = PromptBuilder().build(
            "q", ComparisonInput(query="q"), CitationBundle(), [superseded("A", "B"), superseded("C", "D")]
        )
        assert "Document A is superseded" in prompt and "Document C is superseded" in prompt
        assert "Prefer the latest authoritative document" in prompt


class StreamingFakeClient(FakeLLMClient):
    def generate_stream(self, prompt: str):
        self.prompts.append(prompt)
        yield "Rates "
        yield "changed [S1]."


class TestStreaming:
    def test_stream_yields_pieces_then_final_answer(self) -> None:
        comparison, citations = _two_page_input()
        items = list(LLMAnswerGenerator(llm_client=StreamingFakeClient()).stream("q", comparison, citations))

        assert items[:2] == ["Rates ", "changed [S1]."]
        final = items[-1]
        assert isinstance(final, GeneratedAnswer)
        assert [c.page_number for c in final.citations] == [1]

    def test_stream_falls_back_to_generate(self) -> None:
        comparison, citations = _two_page_input()
        items = list(LLMAnswerGenerator(llm_client=FakeLLMClient("whole [S2]")).stream("q", comparison, citations))
        assert items[0] == "whole [S2]"
        assert isinstance(items[1], GeneratedAnswer)


def test_prompt_restates_question_after_sources() -> None:
    comparison, citations = _two_page_input()
    prompt = PromptBuilder().build("What is the rate?", comparison, citations)
    assert prompt.rindex("Answer this question: What is the rate?") > prompt.index("### [S2] Page 2")
