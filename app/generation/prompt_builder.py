"""Prompt construction for generation layer."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from pydantic import BaseModel

from app.comparison.schemas import ComparisonInput
from app.citations.schemas import CitationBundle
from app.supersession.schemas import SupersessionResult

NO_ANSWER_TEXT = "The provided documents do not contain information about this."


class SourceLabel(BaseModel):
    """Short tag (e.g. "S1") the model uses to cite one page of one document."""

    label: str
    document_id: uuid.UUID
    page_number: int


def build_source_labels(comparison_input: ComparisonInput) -> list[SourceLabel]:
    """Assign S1, S2, ... to each (document, page) in prompt order."""

    labels: list[SourceLabel] = []
    for source in comparison_input.sources:
        for chunk in source.chunks:
            labels.append(
                SourceLabel(
                    label=f"S{len(labels) + 1}",
                    document_id=source.document_id,
                    page_number=chunk.page_number,
                )
            )
    return labels


def normalize_supersession(
    supersession_results: SupersessionResult | Sequence[SupersessionResult] | None,
) -> list[SupersessionResult]:
    """Accept one result, many, or none; return only the superseded ones."""

    if supersession_results is None:
        return []
    if isinstance(supersession_results, SupersessionResult):
        supersession_results = [supersession_results]
    return [result for result in supersession_results if result is not None and result.is_superseded]


class PromptBuilder:
    """Build structured prompts for an LLM from pipeline inputs."""

    def build(
        self,
        query: str,
        comparison_input: ComparisonInput,
        citation_bundle: CitationBundle,
        supersession_results: SupersessionResult | Sequence[SupersessionResult] | None = None,
    ) -> str:
        labels = build_source_labels(comparison_input)
        superseded = normalize_supersession(supersession_results)
        sections: list[str] = [self._rules(len(comparison_input.sources), bool(superseded))]

        sections.append(f"# Query\n{query}")

        if comparison_input.sources:
            sections.append("# Sources")
            label_iter = iter(labels)

            for source in comparison_input.sources:
                header = source.document_number or str(source.document_id)
                label = f"{source.document_type or ''} {header}".strip()
                sections.append(f"## {label}")

                for chunk in source.chunks:
                    tag = next(label_iter).label
                    sections.append(f"### [{tag}] Page {chunk.page_number}")
                    sections.append(chunk.text)

        if citation_bundle.citations:
            sections.append("# Citations")
            tag_by_page = {(l.document_id, l.page_number): l.label for l in labels}
            seen: set[tuple[uuid.UUID, int]] = set()

            for citation in citation_bundle.citations:
                key = (citation.document_id, citation.page_number)
                if key in seen:
                    continue
                seen.add(key)
                tag = tag_by_page.get(key)
                sections.append(f"[{tag}] {citation.citation_text}" if tag else citation.citation_text)

        if superseded:
            sections.append("# Supersession Warnings")
            for result in superseded:
                chain = " -> ".join(
                    ref.document_number or str(ref.document_id)
                    for ref in result.supersession_chain
                )
                sections.append(
                    f"Document {result.document_number} is superseded. "
                    f"Latest authoritative document: {result.latest_document_number}. "
                    f"Chain: {chain}"
                )

        if comparison_input.sources:
            # Small models drift after long source sections; restate the task last.
            sections.append(
                "# Reminder\n"
                f"Answer this question: {query}\n"
                "Use only the sources above and cite them with their [S#] tags. "
                "If they do not answer this exact question, reply exactly:\n"
                f"{NO_ANSWER_TEXT}"
            )

        return "\n\n".join(sections)

    @staticmethod
    def _rules(source_document_count: int, has_superseded: bool) -> str:
        rules = [
            "Answer ONLY using information explicitly present in the provided sources.",
            "Never infer, assume, speculate, extrapolate, or use outside knowledge.",
            f"If the answer is not explicitly contained in the sources, respond exactly:\n\n{NO_ANSWER_TEXT}",
            'Do not describe what is "likely", "suggested", "implied", or "can be inferred".',
            "If evidence is partial, clearly state only the supported facts.",
            "Treat missing information as unknown.",
            "Do not invent technologies, dates, organizations, people, or conclusions.",
            "Keep answers concise and factual. Write only the answer: no notes, no commentary "
            "about the question or the rules, and no remarks about the sources themselves.",
            "Cite every factual statement with the tag of the source it came from, "
            "for example [S1] or [S2][S4]. Use only tags that appear in the Sources section. "
            "Do not write a separate list of sources; it is added automatically.",
        ]
        if source_document_count > 1:
            rules.append(
                "The sources come from more than one document. Where they cover the same "
                "topic, say explicitly where they agree and where they differ, naming each document."
            )
        if has_superseded:
            rules.append(
                "Some documents are superseded (see Supersession Warnings). Prefer the latest "
                "authoritative document and clearly flag any statement taken from a superseded one."
            )
        numbered = "\n\n".join(f"{i}. {rule}" for i, rule in enumerate(rules, start=1))
        return f"You are a retrieval-grounded document assistant.\n\nSTRICT RULES:\n\n{numbered}"
