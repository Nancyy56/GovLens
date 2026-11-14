"""Answer generator implementation."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Iterator, Sequence

from app.comparison.schemas import ComparisonInput
from app.citations.schemas import Citation, CitationBundle
from app.generation.interfaces import LLMClient
from app.generation.prompt_builder import (
    NO_ANSWER_TEXT,
    PromptBuilder,
    SourceLabel,
    build_source_labels,
    normalize_supersession,
)
from app.generation.schemas import GeneratedAnswer, LabeledCitation
from app.generation.verification import verify_answer
from app.supersession.schemas import SupersessionResult

logger = logging.getLogger(__name__)

# Matches the tags inside "[S1]", "[S2][S4]" and "[S1, S3]".
_BRACKET = re.compile(r"\[([^\[\]]{1,40})\]")
_TAG = re.compile(r"\bS(\d+)\b")


def extract_used_labels(answer: str) -> list[str]:
    """Return the source tags cited in an answer, in first-use order."""

    used: list[str] = []
    for bracket in _BRACKET.finditer(answer):
        for number in _TAG.findall(bracket.group(1)):
            label = f"S{number}"
            if label not in used:
                used.append(label)
    return used


class LLMAnswerGenerator:
    """Generate final markdown answers from structured pipeline inputs.

    The generator never retrieves, compares, or formats citations itself.
    It delegates prompt construction to ``PromptBuilder`` and calls an
    injected ``LLMClient`` to produce the final answer text. Afterwards it
    keeps only the citations whose tags the answer used and appends a
    deterministic Sources list, so citations never come from the model.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.llm_client = llm_client or self._default_client()
        self.prompt_builder = prompt_builder or PromptBuilder()

    def generate(
        self,
        query: str,
        comparison_input: ComparisonInput,
        citation_bundle: CitationBundle,
        supersession_results: SupersessionResult | Sequence[SupersessionResult] | None = None,
    ) -> GeneratedAnswer:
        prompt = self._build_prompt(query, comparison_input, citation_bundle, supersession_results)
        raw_answer = self.llm_client.generate(prompt)
        logger.debug("LLM response (%s chars)", len(raw_answer))
        return self.finalize(query, raw_answer, comparison_input, citation_bundle, supersession_results)

    def stream(
        self,
        query: str,
        comparison_input: ComparisonInput,
        citation_bundle: CitationBundle,
        supersession_results: SupersessionResult | Sequence[SupersessionResult] | None = None,
    ) -> Iterator[str | GeneratedAnswer]:
        """Yield answer text pieces, then the finalized ``GeneratedAnswer`` last."""

        prompt = self._build_prompt(query, comparison_input, citation_bundle, supersession_results)
        stream_fn = getattr(self.llm_client, "generate_stream", None)
        pieces: list[str] = []
        if stream_fn is None:
            text = self.llm_client.generate(prompt)
            pieces.append(text)
            yield text
        else:
            for piece in stream_fn(prompt):
                pieces.append(piece)
                yield piece
        yield self.finalize(query, "".join(pieces), comparison_input, citation_bundle, supersession_results)

    def finalize(
        self,
        query: str,
        raw_answer: str,
        comparison_input: ComparisonInput,
        citation_bundle: CitationBundle,
        supersession_results: SupersessionResult | Sequence[SupersessionResult] | None = None,
    ) -> GeneratedAnswer:
        labels = build_source_labels(comparison_input)
        labeled = self._select_citations(raw_answer, labels, citation_bundle.citations)
        source_texts = {
            label.label: chunk.text
            for label, chunk in zip(labels, (c for source in comparison_input.sources for c in source.chunks))
        }
        used = set(extract_used_labels(raw_answer)) & set(source_texts)
        superseded = normalize_supersession(supersession_results)
        system_facts = " ".join(
            f"Document {r.document_number} is superseded by {r.latest_document_number}. "
            + " ".join(ref.document_number or "" for ref in r.supersession_chain)
            for r in superseded
        )
        return GeneratedAnswer(
            query=query,
            answer_markdown=raw_answer.rstrip() + self._sources_section(labeled),
            citations=[item.citation for item in labeled],
            labeled_citations=labeled,
            supersession_warnings=superseded,
            verification=verify_answer(raw_answer, source_texts, system_facts),
            citations_inferred=bool(labeled) and not used,
        )

    def _build_prompt(self, query, comparison_input, citation_bundle, supersession_results) -> str:
        prompt = self.prompt_builder.build(
            query=query,
            comparison_input=comparison_input,
            citation_bundle=citation_bundle,
            supersession_results=supersession_results,
        )
        logger.debug("Prompt built: %s chars, %s words", len(prompt), len(prompt.split()))
        return prompt

    @staticmethod
    def _select_citations(
        raw_answer: str,
        labels: Sequence[SourceLabel],
        citations: Sequence[Citation],
    ) -> list[LabeledCitation]:
        # One citation per (document, page); several chunks can share a page.
        by_page: dict[tuple[uuid.UUID, int], Citation] = {}
        for citation in citations:
            by_page.setdefault((citation.document_id, citation.page_number), citation)

        label_by_page = {(l.document_id, l.page_number): l.label for l in labels}
        page_by_label = {l.label: (l.document_id, l.page_number) for l in labels}

        used = [label for label in extract_used_labels(raw_answer) if page_by_label.get(label) in by_page]
        if used:
            return [LabeledCitation(label=label, citation=by_page[page_by_label[label]]) for label in used]

        if NO_ANSWER_TEXT.casefold() in raw_answer.casefold():
            return []

        # The model cited nothing usable; fall back to every retrieved source.
        return [
            LabeledCitation(label=label_by_page.get(key, ""), citation=citation)
            for key, citation in by_page.items()
        ]

    @staticmethod
    def _sources_section(labeled: Sequence[LabeledCitation]) -> str:
        if not labeled:
            return ""
        lines = []
        for item in labeled:
            text = item.citation.citation_text.replace("\n", ", ")
            lines.append(f"- [{item.label}] {text}" if item.label else f"- {text}")
        return "\n\n**Sources**\n" + "\n".join(lines)

    @staticmethod
    def _default_client() -> LLMClient:
        class _EchoClient:
            def generate(self, prompt: str) -> str:
                return "# Answer\n\nEcho response.\n\n# Citations\n\nSee below.\n\n# Supersession Warnings\n\nNone."

        return _EchoClient()
