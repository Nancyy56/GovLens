"""Protocols for generation layer boundaries."""

from __future__ import annotations

from typing import Protocol

from app.generation.schemas import GeneratedAnswer


class LLMClient(Protocol):
    """Contract for plugging any text-generation backend."""

    def generate(self, prompt: str) -> str:
        """Return the raw text completion for the supplied prompt."""
        ...
