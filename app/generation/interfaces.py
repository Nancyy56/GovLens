"""Protocols for generation layer boundaries."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class LLMClient(Protocol):
    """Contract for plugging any text-generation backend."""

    def generate(self, prompt: str) -> str:
        """Return the raw text completion for the supplied prompt."""
        ...


class StreamingLLMClient(LLMClient, Protocol):
    """An LLM client that can also yield the completion incrementally."""

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Yield pieces of the completion as they are produced."""
        ...
