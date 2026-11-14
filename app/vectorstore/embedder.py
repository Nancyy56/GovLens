"""Embedding provider implementations."""

from __future__ import annotations

import logging
import hashlib
import threading
from typing import TYPE_CHECKING, Sequence

from app.vectorstore.interfaces import EmbeddingProvider

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class HashEmbeddingProvider:
    """Generate deterministic fixed-size embeddings without external models."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = text.lower().split()
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        magnitude = sum(value * value for value in vector) ** 0.5
        if magnitude == 0:
            return vector
        return [value / magnitude for value in vector]


class HuggingFaceEmbeddingProvider:
    """Embed text using a local HuggingFace sentence-transformers model.

    The model is loaded lazily on the first call to ``embed`` so that imports
    do not fail when the optional dependency is absent. Batch size is
    configurable to control GPU/CPU memory usage.

    Default model: ``BAAI/bge-small-en-v1.5`` (384 dimensions).
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        batch_size: int = 32,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.device = device
        self._model: "SentenceTransformer | None" = None
        self._lock = threading.Lock()

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load_model()
        embeddings = model.encode(
            list(texts),
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            device=self.device,
        )
        return embeddings.tolist()

    def _load_model(self) -> "SentenceTransformer":
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is required for HuggingFaceEmbeddingProvider. "
                    "Install it with: pip install sentence-transformers"
                ) from exc
            logger.info("Loading embedding model %s", self.model_name)
            self._model = SentenceTransformer(self.model_name, device=self.device)
            return self._model
