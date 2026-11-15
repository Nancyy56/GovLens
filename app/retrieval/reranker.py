"""Cross-encoder reranking of retrieved chunks."""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Sequence
from typing import Protocol

from app.retrieval.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class Reranker(Protocol):
    def rerank(self, query: str, chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
        ...


class CrossEncoderReranker:
    """Re-score (query, chunk) pairs with a cross-encoder and sort by that score.

    A cross-encoder reads the query and the chunk together, so it judges
    relevance more accurately than comparing two separately computed
    embeddings. It is slower, which is why it only runs on the short list
    produced by first-stage retrieval.

    The model loads lazily. If it cannot be loaded (for example, no network
    on first use), reranking is disabled with a logged error and chunks are
    returned in their original order.
    """

    def __init__(self, model_name: str, batch_size: int = 16, device: str | None = None, tokenizer=None) -> None:
        self.model_name = model_name
        # Splits long chunks into windows the cross-encoder can read in full.
        self.tokenizer = tokenizer
        self.batch_size = batch_size
        self.device = device
        self._model = None
        self._failed = False
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return not self._failed

    def rerank(self, query: str, chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
        if not chunks:
            return []
        model = self._load_model()
        if model is None:
            return list(chunks)

        import torch

        # Score every window of every chunk; a chunk is as relevant as its best window.
        pairs: list[tuple[str, str]] = []
        owners: list[int] = []
        for index, chunk in enumerate(chunks):
            windows = self.tokenizer.windows(chunk.chunk_text) if self.tokenizer else [chunk.chunk_text]
            for window in windows:
                pairs.append((query, window))
                owners.append(index)
        logits = model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False, activation_fn=torch.nn.Identity())
        best = [float("-inf")] * len(chunks)
        for owner, logit in zip(owners, logits):
            best[owner] = max(best[owner], float(logit))
        rescored = [
            chunk.model_copy(update={"score": 1.0 / (1.0 + math.exp(-logit))})
            for chunk, logit in zip(chunks, best)
        ]
        rescored.sort(key=lambda chunk: chunk.score, reverse=True)
        return rescored

    def _load_model(self):
        if self._model is not None or self._failed:
            return self._model
        with self._lock:
            if self._model is not None or self._failed:
                return self._model
            try:
                from sentence_transformers import CrossEncoder

                logger.info("Loading reranker model %s", self.model_name)
                self._model = CrossEncoder(self.model_name, device=self.device)
            except Exception:
                self._failed = True
                logger.exception("Reranker %s could not be loaded; reranking is disabled", self.model_name)
            return self._model
