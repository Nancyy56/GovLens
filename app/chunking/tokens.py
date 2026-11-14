"""Token counting and windowing with the embedding model's own tokenizer.

Chunks are sized in real tokens. Because the embedding model and the
reranker only read 512 tokens, longer chunks are split into overlapping
windows for embedding and scoring, so no part of a chunk is invisible to search.
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

logger = logging.getLogger(__name__)

# Leaves room under the models' 512-token limit for special tokens and the query.
WINDOW_TOKENS = 400
WINDOW_OVERLAP = 50


class TextTokenizer(Protocol):
    def count(self, text: str) -> int: ...

    def windows(self, text: str, size: int = WINDOW_TOKENS, overlap: int = WINDOW_OVERLAP) -> list[str]: ...


class WordTokenizer:
    """Whitespace words as tokens: a dependency-free approximation."""

    def count(self, text: str) -> int:
        return len(text.split())

    def windows(self, text: str, size: int = WINDOW_TOKENS, overlap: int = WINDOW_OVERLAP) -> list[str]:
        words = text.split()
        if len(words) <= size:
            return [text]
        step = max(1, size - overlap)
        return [" ".join(words[start:start + size]) for start in range(0, len(words) - overlap, step)]


class HuggingFaceTokenizer:
    """The embedding model's tokenizer, loaded lazily; falls back to words if unavailable."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._tokenizer = None
        self._fallback: WordTokenizer | None = None
        self._lock = threading.Lock()

    def count(self, text: str) -> int:
        tokenizer = self._load()
        if tokenizer is None:
            return self._fallback.count(text)
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    def windows(self, text: str, size: int = WINDOW_TOKENS, overlap: int = WINDOW_OVERLAP) -> list[str]:
        tokenizer = self._load()
        if tokenizer is None:
            return self._fallback.windows(text, size, overlap)
        offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
        if len(offsets) <= size:
            return [text]
        step = max(1, size - overlap)
        windows = []
        for start in range(0, len(offsets) - overlap, step):
            end = min(start + size, len(offsets))
            windows.append(text[offsets[start][0]:offsets[end - 1][1]])
        return windows

    def _load(self):
        if self._tokenizer is not None or self._fallback is not None:
            return self._tokenizer
        with self._lock:
            if self._tokenizer is None and self._fallback is None:
                try:
                    from transformers import AutoTokenizer

                    self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                except Exception:
                    logger.exception("Tokenizer %s unavailable; counting words instead", self.model_name)
                    self._fallback = WordTokenizer()
        return self._tokenizer
