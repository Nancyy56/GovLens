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
        assert prompt.startswith("# Query\ntax query")

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
