"""Delete old stored questions and audit entries, so personal data is not kept forever."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.documents import AuditLog, QueryLog

logger = logging.getLogger(__name__)


def purge_old_records(session: Session, *, query_days: int, audit_days: int, now: datetime | None = None) -> dict[str, int]:
    """Remove rows older than the given number of days (0 keeps everything). Returns counts."""

    now = now or datetime.now(UTC)
    removed = {"query_logs": 0, "audit_logs": 0}
    if query_days > 0:
        removed["query_logs"] = session.execute(delete(QueryLog).where(QueryLog.created_at < now - timedelta(days=query_days))).rowcount or 0
    if audit_days > 0:
        removed["audit_logs"] = session.execute(delete(AuditLog).where(AuditLog.created_at < now - timedelta(days=audit_days))).rowcount or 0
    session.commit()
    return removed


def run_retention() -> None:
    """Entry point for the background job. Never raises."""

    from app.core.config import settings
    from app.db.database import SessionLocal

    try:
        with SessionLocal() as session:
            removed = purge_old_records(
                session, query_days=settings.query_log_retention_days, audit_days=settings.audit_log_retention_days
            )
        if any(removed.values()):
            logger.info("Retention removed %s", removed)
    except Exception:
        logger.exception("Retention job failed")
