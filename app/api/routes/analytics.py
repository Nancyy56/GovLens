"""Usage analytics for administrators."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.security import require_admin
from app.db.database import get_session
from app.services.history import Analytics, HistoryService

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_admin)])


@router.get("", response_model=Analytics)
def usage_analytics(days: int = Query(14, ge=1, le=180), session: Session = Depends(get_session)):
    """Question volume, answer quality signals, most cited documents, and questions worth a look."""

    return HistoryService(session).analytics(days)
