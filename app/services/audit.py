"""Append-only audit trail of sensitive actions (sign-ins, uploads, deletions, user changes)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.documents import AuditLog

logger = logging.getLogger(__name__)


class AuditEntry(BaseModel):
    id: uuid.UUID
    created_at: datetime
    username: str
    action: str
    target: str | None
    detail: str | None
    ip: str | None


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int
    actions: list[str]


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, username: str, action: str, *, target: str | None, detail: str | None, ip: str | None) -> None:
        self.session.add(
            AuditLog(username=username[:64], action=action[:48], target=(target or None) and target[:200],
                     detail=(detail or None) and detail[:2000], ip=ip)
        )
        self.session.commit()

    def list(self, *, limit: int, offset: int, action: str | None, search: str | None) -> AuditPage:
        stmt = select(AuditLog)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(or_(AuditLog.username.ilike(like), AuditLog.target.ilike(like), AuditLog.detail.ilike(like)))
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.session.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)).all()
        actions = self.session.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action)).all()
        return AuditPage(
            items=[AuditEntry(id=r.id, created_at=r.created_at, username=r.username, action=r.action,
                              target=r.target, detail=r.detail, ip=r.ip) for r in rows],
            total=total,
            actions=list(actions),
        )


def record(username: str, action: str, *, target: str | None = None, detail: str | None = None, ip: str | None = None) -> None:
    """Write an audit entry. Never raises: auditing must not break the action being audited."""

    from app.db.database import SessionLocal

    try:
        with SessionLocal() as session:
            AuditService(session).add(username, action, target=target, detail=detail, ip=ip)
    except Exception:
        logger.exception("Could not write audit entry %s", action)
