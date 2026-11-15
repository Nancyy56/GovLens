"""Query history, feedback, and analytics."""

from __future__ import annotations

import uuid

import pytest

from app.generation.verification import VerificationReport
from app.services.history import HistoryService
from app.services.schemas import QueryResult, SourceCitation


@pytest.fixture
def history_service(sqlite_session):
    return HistoryService(sqlite_session)


def _result(question: str, *, sources: int = 1, unsupported: int = 0) -> QueryResult:
    return QueryResult(
        query=question,
        answer_markdown=f"Answer to {question} [S1]",
        sources=[
            SourceCitation(label=f"S{i + 1}", document_id=uuid.uuid4(), document_number="12/2023", page_number=1, citation_text="text")
            for i in range(sources)
        ],
        verification=VerificationReport(checked=2, supported=2 - unsupported, unsupported=unsupported, all_supported=unsupported == 0),
    )


def test_history_is_private_to_each_user(history_service):
    mine = history_service.record(user_id=None, username="alice", result=_result("What is the GST rate?"), latency_ms=120)
    history_service.record(user_id=None, username="bob", result=_result("Bob's question"), latency_ms=90)

    page = history_service.list("alice", limit=10, offset=0, search=None)
    assert [i.question for i in page.items] == ["What is the GST rate?"]
    assert history_service.get("bob", mine.id) is None
    assert history_service.delete("bob", mine.id) is False
    assert history_service.get("alice", mine.id).result["query"] == "What is the GST rate?"


def test_history_search_and_clear(history_service):
    history_service.record(user_id=None, username="alice", result=_result("penalty for late filing"), latency_ms=1)
    history_service.record(user_id=None, username="alice", result=_result("tax rate"), latency_ms=1)
    assert history_service.list("alice", limit=10, offset=0, search="PENALTY").total == 1
    assert history_service.clear("alice") == 2
    assert history_service.list("alice", limit=10, offset=0, search=None).total == 0


def test_feedback_can_be_set_changed_and_cleared(history_service):
    row = history_service.record(user_id=None, username="alice", result=_result("q"), latency_ms=1)
    assert history_service.set_feedback("alice", row.id, 1, None)
    assert history_service.get("alice", row.id).feedback == 1
    assert history_service.set_feedback("alice", row.id, -1, "  wrong page  ")
    detail = history_service.get("alice", row.id)
    assert (detail.feedback, detail.feedback_note) == (-1, "wrong page")
    assert history_service.set_feedback("alice", row.id, 0, None)
    assert history_service.get("alice", row.id).feedback is None
    with pytest.raises(ValueError):
        history_service.set_feedback("alice", row.id, 5, None)
    assert history_service.set_feedback("bob", row.id, 1, None) is False


def test_analytics_summarises_usage_and_flags_problem_questions(history_service):
    good = history_service.record(user_id=None, username="alice", result=_result("good"), latency_ms=100)
    history_service.record(user_id=None, username="bob", result=_result("nothing found", sources=0), latency_ms=300)
    history_service.record(user_id=None, username="bob", result=_result("shaky", unsupported=1), latency_ms=200)
    history_service.set_feedback("alice", good.id, 1, None)

    stats = history_service.analytics(days=7)
    assert stats.total_queries == 3
    assert stats.unique_users == 2
    assert stats.answered_rate == pytest.approx(2 / 3)
    assert stats.avg_latency_ms == 200
    assert (stats.helpful, stats.not_helpful, stats.satisfaction) == (1, 0, 1.0)
    assert stats.top_documents[0].document_number == "12/2023"
    assert len(stats.per_day) == 7 and sum(d.queries for d in stats.per_day) == 3
    assert {f.reason for f in stats.flagged} == {"No sources found", "Unsupported statements"}
