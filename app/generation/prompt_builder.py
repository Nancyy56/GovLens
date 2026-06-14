"""Prompt construction for generation layer."""

from __future__ import annotations

from app.comparison.schemas import ComparisonInput
from app.citations.schemas import CitationBundle
from app.supersession.schemas import SupersessionResult


class PromptBuilder:
    """Build structured prompts for an LLM from pipeline inputs."""

    def build(
        self,
        query: str,
        comparison_input: ComparisonInput,
        citation_bundle: CitationBundle,
        supersession_results: SupersessionResult | None = None,
    ) -> str:
        sections: list[str] = []

        sections.append(
            """
You are a retrieval-grounded document assistant.

STRICT RULES:

1. Answer ONLY using information explicitly present in the provided sources.

2. Never infer, assume, speculate, extrapolate, or use outside knowledge.

3. If the answer is not explicitly contained in the sources, respond exactly:

The provided documents do not contain information about this.

4. Do not describe what is "likely", "suggested", "implied", or "can be inferred".

5. If evidence is partial, clearly state only the supported facts.

6. Treat missing information as unknown.

7. Do not invent technologies, dates, organizations, people, or conclusions.

8. Keep answers concise and factual.

9. At the end of the answer include a section:

Sources:
- citation

using the provided citations.
"""
        )

        sections.append(f"# Query\n{query}")

        if comparison_input.sources:
            sections.append("# Sources")

            for source in comparison_input.sources:
                header = source.document_number or str(source.document_id)

                label = f"{source.document_type} {header}".strip()

                sections.append(f"## {label}")

                for i, chunk in enumerate(source.chunks, 1):
                    sections.append(
                        f"### Chunk {i} (Page {chunk.page_number})"
                    )
                    sections.append(chunk.text)

        if citation_bundle.citations:
            sections.append("# Citations")

            for citation in citation_bundle.citations:
                sections.append(citation.citation_text)

        if (
            supersession_results is not None
            and supersession_results.is_superseded
        ):
            sections.append("# Supersession Warnings")

            chain = " -> ".join(
                ref.document_number or str(ref.document_id)
                for ref in supersession_results.supersession_chain
            )

            sections.append(
                f"Document {supersession_results.document_number} "
                f"is superseded. Latest authoritative document: "
                f"{supersession_results.latest_document_number}. "
                f"Chain: {chain}"
            )

        return "\n\n".join(sections)
