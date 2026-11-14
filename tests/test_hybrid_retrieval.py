"""Hybrid retrieval: rank fusion, keyword search, and reranking."""

from __future__ import annotations

import sys
import uuid
from types import SimpleNamespace

from app.retrieval.hybrid import HybridDocumentRetriever, reciprocal_rank_fusion
from app.retrieval.keyword import PostgresKeywordSearcher
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.schemas import RetrievalResult, RetrievedChunk

DOC_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DOC_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _chunk(document_id: uuid.UUID, page: int, text: str = "t", score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(document_id=document_id, page_number=page, chunk_index=0, chunk_text=text, score=score)


class FakeDense:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    def retrieve(self, query, top_k=10, document_numbers=None):
        self.calls.append((query, top_k, document_numbers))
        return RetrievalResult(query=query, retrieved_chunks=self.chunks[:top_k])


class FakeKeyword:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    def search(self, query, limit, document_numbers=None):
        self.calls.append((query, limit, document_numbers))
        return self.chunks[:limit]


class ReverseReranker:
    def rerank(self, query, chunks):
        return [c.model_copy(update={"score": 0.9 - i * 0.1}) for i, c in enumerate(reversed(list(chunks)))]


def test_rrf_rewards_chunks_found_by_both_lists() -> None:
    shared = _chunk(DOC_A, 1)
    fused = reciprocal_rank_fusion([[_chunk(DOC_B, 9), shared], [shared, _chunk(DOC_B, 8)]])

    assert (fused[0].document_id, fused[0].page_number) == (DOC_A, 1)
    assert 0 < fused[-1].score < fused[0].score <= 1.0


def test_rrf_score_is_one_when_ranked_first_everywhere() -> None:
    chunk = _chunk(DOC_A, 1)
    assert reciprocal_rank_fusion([[chunk], [chunk]])[0].score == 1.0


def test_hybrid_fetches_extra_candidates_and_trims_to_top_k() -> None:
    dense = FakeDense([_chunk(DOC_A, p) for p in range(1, 10)])
    keyword = FakeKeyword([_chunk(DOC_B, p) for p in range(1, 10)])
    retriever = HybridDocumentRetriever(dense, keyword, candidate_multiplier=3)

    result = retriever.retrieve("q", top_k=2, document_numbers=["17/2024"])

    assert dense.calls == [("q", 6, ["17/2024"])]
    assert keyword.calls == [("q", 6, ["17/2024"])]
    assert len(result.retrieved_chunks) == 2


def test_hybrid_applies_reranker_order() -> None:
    dense = FakeDense([_chunk(DOC_A, 1), _chunk(DOC_A, 2)])
    retriever = HybridDocumentRetriever(dense, keyword_searcher=None, reranker=ReverseReranker())

    result = retriever.retrieve("q", top_k=2)

    assert [c.page_number for c in result.retrieved_chunks] == [2, 1]


def test_hybrid_without_keyword_keeps_dense_scores() -> None:
    dense = FakeDense([_chunk(DOC_A, 1, score=-0.2)])
    result = HybridDocumentRetriever(dense).retrieve("q", top_k=1)
    # Negative cosine scores are valid and must not fail validation.
    assert result.retrieved_chunks[0].score == -0.2


def test_keyword_fallback_finds_terms_and_exact_numbers(sqlite_session, make_document) -> None:
    make_document("17/2024", pages=["GST rate on packaged goods is revised to 12 percent."])
    make_document("3/2020", pages=["Unrelated text about railway timetables."])
    make_document("9/2021", pages=["As per Notification No. 17/2024 the fee applies."])

    results = PostgresKeywordSearcher(sqlite_session).search("What is the GST rate in 17/2024?", limit=5)

    numbers = [c.document_number for c in results]
    assert "3/2020" not in numbers
    assert set(numbers) == {"17/2024", "9/2021"}


def test_keyword_fallback_respects_document_filter(sqlite_session, make_document) -> None:
    make_document("17/2024", pages=["GST rate revised."])
    make_document("18/2024", pages=["GST rate revised again."])

    results = PostgresKeywordSearcher(sqlite_session).search("GST rate", limit=5, document_numbers=["18/2024"])

    assert [c.document_number for c in results] == ["18/2024"]


def test_reranker_disables_itself_when_model_cannot_load(monkeypatch) -> None:
    def broken(*args, **kwargs):
        raise OSError("no network")

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(CrossEncoder=broken))
    reranker = CrossEncoderReranker("some/model")
    chunks = [_chunk(DOC_A, 1), _chunk(DOC_A, 2)]

    assert reranker.rerank("q", chunks) == chunks
    assert reranker.available is False


class FixedScoreReranker:
    available = True

    def __init__(self, scores):
        self.scores = scores

    def rerank(self, query, chunks):
        return [c.model_copy(update={"score": s}) for c, s in zip(chunks, self.scores)]


def test_low_rerank_scores_are_dropped() -> None:
    dense = FakeDense([_chunk(DOC_A, 1), _chunk(DOC_A, 2), _chunk(DOC_A, 3)])
    retriever = HybridDocumentRetriever(dense, reranker=FixedScoreReranker([0.98, 0.004, 0.3]), min_rerank_score=0.01)

    result = retriever.retrieve("q", top_k=3)

    assert [c.page_number for c in result.retrieved_chunks] == [1, 3]


def test_unanswerable_question_returns_no_chunks() -> None:
    dense = FakeDense([_chunk(DOC_A, 1), _chunk(DOC_A, 2)])
    retriever = HybridDocumentRetriever(dense, reranker=FixedScoreReranker([0.0001, 0.0]), min_rerank_score=0.01)

    assert retriever.retrieve("q", top_k=2).retrieved_chunks == []


def test_threshold_ignored_when_reranker_unavailable() -> None:
    reranker = FixedScoreReranker([0.0, 0.0])
    reranker.available = False
    dense = FakeDense([_chunk(DOC_A, 1), _chunk(DOC_A, 2)])

    result = HybridDocumentRetriever(dense, reranker=reranker, min_rerank_score=0.01).retrieve("q", top_k=2)

    assert len(result.retrieved_chunks) == 2


def test_word_tokenizer_windows_overlap_and_cover_text() -> None:
    from app.chunking.tokens import WordTokenizer

    words = [f"w{i}" for i in range(1000)]
    windows = WordTokenizer().windows(" ".join(words), size=400, overlap=50)

    assert [len(w.split()) for w in windows] == [400, 400, 300]
    assert windows[1].split()[0] == "w350"
    assert windows[-1].split()[-1] == "w999"


def test_short_text_is_one_window() -> None:
    from app.chunking.tokens import WordTokenizer

    assert WordTokenizer().windows("a short chunk") == ["a short chunk"]


def test_dense_retriever_dedupes_windows_of_same_chunk() -> None:
    from app.retrieval.retriever import QdrantDocumentRetriever

    def hit(window_score, page):
        return {"score": window_score, "payload": {"document_id": str(DOC_A), "page_number": page, "chunk_index": 0, "chunk_text": "t"}}

    class Store:
        def search(self, query_vector, limit=10, filters=None):
            return [hit(0.5, 1), hit(0.9, 1), hit(0.7, 2)]

    class Embedder:
        def embed(self, texts):
            return [[0.0]]

    result = QdrantDocumentRetriever(Embedder(), Store()).retrieve("q")
    assert [(c.page_number, c.score) for c in result.retrieved_chunks] == [(1, 0.9), (2, 0.7)]


def test_long_chunk_gets_one_point_per_window() -> None:
    from app.chunking.tokens import WordTokenizer
    from app.vectorstore.windows import build_embedded_chunks
    from types import SimpleNamespace

    chunk = SimpleNamespace(page_number=1, chunk_index=0, chunk_text=" ".join(["word"] * 900), metadata=None)

    class Embedder:
        def embed(self, texts):
            return [[float(len(t))] for t in texts]

    embedded = build_embedded_chunks(
        document_id=DOC_A, document_number="1/2024", document_type=None, chunks=[chunk],
        embedding_provider=Embedder(), tokenizer=WordTokenizer(), title="t", file_name="f.pdf",
        department=None, subject=None, issue_date=None,
    )
    assert [e.window_index for e in embedded] == [0, 1, 2]
    assert all(e.chunk_text == chunk.chunk_text for e in embedded)
