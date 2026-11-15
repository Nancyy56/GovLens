"""The audit log, for administrators."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.security import require_admin
from app.db.database import get_session
from app.services.audit import AuditPage, AuditService

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("", response_model=AuditPage)
def list_audit(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None, max_length=48),
    search: str | None = Query(None, max_length=200),
    session: Session = Depends(get_session),
):
    return AuditService(session).list(limit=limit, offset=offset, action=action, search=search)
