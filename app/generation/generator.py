"""Answer generator implementation."""

from __future__ import annotations

from app.comparison.schemas import ComparisonInput
from app.citations.schemas import CitationBundle
from app.generation.interfaces import LLMClient
from app.generation.prompt_builder import PromptBuilder
from app.generation.schemas import GeneratedAnswer
from app.supersession.schemas import DocumentReference, SupersessionResult


class LLMAnswerGenerator:
    """Generate final markdown answers from structured pipeline inputs.

    The generator never retrieves, compares, or formats citations itself.
    It delegates prompt construction to ``PromptBuilder`` and calls an
    injected ``LLMClient`` to produce the final answer text. This keeps
    the generation layer independent of any provider SDK.
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
        supersession_results: SupersessionResult | None = None,
    ) -> GeneratedAnswer:
        prompt = self.prompt_builder.build(
            query=query,
            comparison_input=comparison_input,
            citation_bundle=citation_bundle,
            supersession_results=supersession_results,
        )

        print("\n" + "=" * 80)
        print("PROMPT SENT TO OLLAMA")
        print("=" * 80)
        print(prompt)
        print("=" * 80 + "\n")

        print(f"PROMPT CHARS: {len(prompt)}")
        print(f"PROMPT WORDS: {len(prompt.split())}")

        answer_markdown = self.llm_client.generate(prompt)

        print("\n" + "=" * 80)
        print("OLLAMA RESPONSE")
        print("=" * 80)
        print(answer_markdown)
        print("=" * 80 + "\n")

        return GeneratedAnswer(
            query=query,
            answer_markdown=answer_markdown,
            citations=list(citation_bundle.citations),
            supersession_warnings=[
                supersession_results
            ] if supersession_results and supersession_results.is_superseded else [],
        )

    @staticmethod
    def _default_client() -> LLMClient:
        class _EchoClient:
            def generate(self, prompt: str) -> str:
                return "# Answer\n\nEcho response.\n\n# Citations\n\nSee below.\n\n# Supersession Warnings\n\nNone."

        return _EchoClient()
