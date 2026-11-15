"""Query history, answer feedback, and usage analytics.

Every answered question is stored with its full result, so a user can reopen
earlier answers, rate them, and administrators can see what is (not) working.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.documents import QueryLog
from app.services.schemas import QueryResult

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 4000


class HistoryItem(BaseModel):
    id: uuid.UUID
    question: str
    answer_preview: str
    source_count: int
    unsupported_count: int
    feedback: int | None
    created_at: datetime


class HistoryDetail(HistoryItem):
    result: dict[str, Any]
    latency_ms: int
    feedback_note: str | None


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int


class FeedbackRequest(BaseModel):
    rating: int = Field(description="1 = helpful, -1 = not helpful, 0 clears the rating")
    note: str | None = Field(default=None, max_length=2000)


class DayCount(BaseModel):
    day: str
    queries: int
    helpful: int = 0
    not_helpful: int = 0


class TopDocument(BaseModel):
    document_number: str
    citations: int


class FlaggedQuestion(BaseModel):
    id: uuid.UUID
    question: str
    username: str
    reason: str
    created_at: datetime


class Analytics(BaseModel):
    days: int
    total_queries: int
    unique_users: int
    answered_rate: float
    avg_latency_ms: int
    p95_latency_ms: int
    rated: int
    helpful: int
    not_helpful: int
    satisfaction: float | None
    verified_rate: float | None
    per_day: list[DayCount]
    top_documents: list[TopDocument]
    flagged: list[FlaggedQuestion]


def _preview(text: str, limit: int = 160) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _item(row: QueryLog) -> HistoryItem:
    return HistoryItem(
        id=row.id,
        question=row.question,
        answer_preview=_preview(row.answer_markdown),
        source_count=row.source_count,
        unsupported_count=row.unsupported_count,
        feedback=row.feedback,
        created_at=row.created_at,
    )


class HistoryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(self, *, user_id: uuid.UUID | None, username: str, result: QueryResult, latency_ms: int) -> QueryLog:
        verification = result.verification
        row = QueryLog(
            user_id=user_id,
            username=username[:64],
            question=result.query[:MAX_QUESTION_CHARS],
            answer_markdown=result.answer_markdown,
            result=result.model_dump(mode="json"),
            source_count=len(result.sources),
            supported_count=verification.supported,
            unsupported_count=verification.unsupported + verification.uncited,
            latency_ms=max(0, latency_ms),
        )
        self.session.add(row)
        self.session.commit()
        return row

    # --- per-user history -------------------------------------------------

    def _owned(self, username: str):
        return select(QueryLog).where(QueryLog.username == username)

    def list(self, username: str, *, limit: int, offset: int, search: str | None) -> HistoryPage:
        stmt = self._owned(username)
        if search:
            stmt = stmt.where(QueryLog.question.ilike(f"%{search.strip()}%"))
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.session.scalars(stmt.order_by(QueryLog.created_at.desc()).limit(limit).offset(offset)).all()
        return HistoryPage(items=[_item(r) for r in rows], total=total)

    def get(self, username: str, log_id: uuid.UUID) -> HistoryDetail | None:
        row = self.session.scalar(self._owned(username).where(QueryLog.id == log_id))
        if row is None:
            return None
        return HistoryDetail(**_item(row).model_dump(), result=row.result, latency_ms=row.latency_ms, feedback_note=row.feedback_note)

    def delete(self, username: str, log_id: uuid.UUID) -> bool:
        row = self.session.scalar(self._owned(username).where(QueryLog.id == log_id))
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    def clear(self, username: str) -> int:
        rows = self.session.scalars(self._owned(username)).all()
        for row in rows:
            self.session.delete(row)
        self.session.commit()
        return len(rows)

    def set_feedback(self, username: str, log_id: uuid.UUID, rating: int, note: str | None) -> bool:
        if rating not in (-1, 0, 1):
            raise ValueError("rating must be 1, -1, or 0")
        row = self.session.scalar(self._owned(username).where(QueryLog.id == log_id))
        if row is None:
            return False
        row.feedback = rating or None
        row.feedback_note = (note or "").strip() or None
        self.session.commit()
        return True

    # --- analytics (all users) -------------------------------------------

    def analytics(self, days: int) -> Analytics:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self.session.scalars(
            select(QueryLog).where(QueryLog.created_at >= since).order_by(QueryLog.created_at.desc()).limit(20000)
        ).all()

        total = len(rows)
        answered = sum(1 for r in rows if r.source_count > 0)
        latencies = sorted(r.latency_ms for r in rows)
        helpful = sum(1 for r in rows if r.feedback == 1)
        not_helpful = sum(1 for r in rows if r.feedback == -1)
        rated = helpful + not_helpful
        checked = sum(r.supported_count + r.unsupported_count for r in rows)
        supported = sum(r.supported_count for r in rows)

        per_day: dict[str, DayCount] = {}
        for offset in range(days):
            day = (datetime.now(timezone.utc) - timedelta(days=days - 1 - offset)).date().isoformat()
            per_day[day] = DayCount(day=day, queries=0)
        cited: Counter[str] = Counter()
        for r in rows:
            created = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)
            bucket = per_day.get(created.date().isoformat())
            if bucket:
                bucket.queries += 1
                bucket.helpful += r.feedback == 1
                bucket.not_helpful += r.feedback == -1
            for source in (r.result or {}).get("sources", []):
                if source.get("document_number"):
                    cited[source["document_number"]] += 1

        flagged: list[FlaggedQuestion] = []
        for r in rows:
            reason = (
                "Rated not helpful" if r.feedback == -1
                else "No sources found" if r.source_count == 0
                else "Unsupported statements" if r.unsupported_count > 0
                else None
            )
            if reason:
                flagged.append(FlaggedQuestion(id=r.id, question=_preview(r.question, 140), username=r.username, reason=reason, created_at=r.created_at))
            if len(flagged) >= 15:
                break

        return Analytics(
            days=days,
            total_queries=total,
            unique_users=len({r.username for r in rows}),
            answered_rate=(answered / total) if total else 0.0,
            avg_latency_ms=int(sum(latencies) / total) if total else 0,
            p95_latency_ms=latencies[min(total - 1, int(total * 0.95))] if total else 0,
            rated=rated,
            helpful=helpful,
            not_helpful=not_helpful,
            satisfaction=(helpful / rated) if rated else None,
            verified_rate=(supported / checked) if checked else None,
            per_day=list(per_day.values()),
            top_documents=[TopDocument(document_number=n, citations=c) for n, c in cited.most_common(8)],
            flagged=flagged,
        )


def record_query(*, user_id: uuid.UUID | None, username: str, result: QueryResult, latency_ms: int) -> uuid.UUID | None:
    """Store an answered question. Never raises: failing to log must not fail the answer."""

    from app.db.database import SessionLocal

    try:
        with SessionLocal() as session:
            return HistoryService(session).record(user_id=user_id, username=username, result=result, latency_ms=latency_ms).id
    except Exception:
        logger.exception("Could not record query history")
        return None
