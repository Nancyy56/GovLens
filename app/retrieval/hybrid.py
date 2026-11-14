"""Hybrid retrieval: dense + keyword search, fused, then optionally reranked."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.retrieval.interfaces import DocumentRetriever
from app.retrieval.keyword import KeywordSearcher
from app.retrieval.reranker import Reranker
from app.retrieval.schemas import RetrievalResult, RetrievedChunk

logger = logging.getLogger(__name__)

# Standard Reciprocal Rank Fusion constant; dampens the advantage of rank 1.
RRF_K = 60


def _chunk_key(chunk: RetrievedChunk) -> tuple[str, int, int]:
    return (str(chunk.document_id), chunk.page_number, chunk.chunk_index)


def reciprocal_rank_fusion(result_lists: Sequence[Sequence[RetrievedChunk]], k: int = RRF_K) -> list[RetrievedChunk]:
    """Merge ranked lists by summing 1/(k + rank) for each chunk.

    RRF only uses ranks, so it can combine cosine similarities and full-text
    ranks without calibrating them against each other. Scores are scaled to
    0..1, where 1 means "ranked first by every list".
    """

    scores: dict[tuple[str, int, int], float] = {}
    chunks: dict[tuple[str, int, int], RetrievedChunk] = {}
    for results in result_lists:
        for rank, chunk in enumerate(results, start=1):
            key = _chunk_key(chunk)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            chunks.setdefault(key, chunk)

    best_possible = len(result_lists) / (k + 1) if result_lists else 1.0
    fused = [
        chunks[key].model_copy(update={"score": score / best_possible})
        for key, score in scores.items()
    ]
    fused.sort(key=lambda chunk: chunk.score, reverse=True)
    return fused


class HybridDocumentRetriever(DocumentRetriever):
    """Combine semantic and keyword retrieval, then rerank the short list.

    1. Dense search finds chunks with similar meaning.
    2. Keyword search finds exact terms and document numbers.
    3. Reciprocal Rank Fusion merges the two rankings.
    4. A cross-encoder (if configured) re-scores the merged candidates, and
       chunks below ``min_rerank_score`` are dropped. Cross-encoder scores
       separate relevant from unrelated text sharply, so when nothing passes,
       the corpus has no answer and the LLM need not be asked.
    """

    def __init__(
        self,
        dense_retriever: DocumentRetriever,
        keyword_searcher: KeywordSearcher | None = None,
        reranker: Reranker | None = None,
        candidate_multiplier: int = 3,
        min_rerank_score: float = 0.0,
    ) -> None:
        self.dense_retriever = dense_retriever
        self.keyword_searcher = keyword_searcher
        self.reranker = reranker
        self.candidate_multiplier = max(1, candidate_multiplier)
        self.min_rerank_score = min_rerank_score

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        document_numbers: list[str] | None = None,
    ) -> RetrievalResult:
        candidates = top_k * self.candidate_multiplier
        dense = self.dense_retriever.retrieve(query, top_k=candidates, document_numbers=document_numbers)
        result_lists = [list(dense.retrieved_chunks)]

        if self.keyword_searcher is not None:
            result_lists.append(self.keyword_searcher.search(query, candidates, document_numbers))

        fused = reciprocal_rank_fusion(result_lists) if len(result_lists) > 1 else result_lists[0]
        if self.reranker is not None:
            fused = self.reranker.rerank(query, fused[:candidates])
            # Only filter on real cross-encoder scores, not on a disabled reranker's passthrough.
            if self.min_rerank_score > 0 and getattr(self.reranker, "available", True):
                fused = [chunk for chunk in fused if chunk.score >= self.min_rerank_score]

        logger.debug(
            "Hybrid retrieval: dense=%s keyword=%s fused=%s returned=%s",
            len(result_lists[0]),
            len(result_lists[1]) if len(result_lists) > 1 else 0,
            len(fused),
            min(top_k, len(fused)),
        )
        return RetrievalResult(query=query, retrieved_chunks=fused[:top_k])
