"""Query route."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_query_service
from app.api.schemas import QueryRequest
from app.db.database import get_session
from app.services.query import QueryService
from app.services.schemas import QueryResult

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/", response_model=QueryResult)
async def query_documents(
    request: QueryRequest,
    service: QueryService = Depends(get_query_service),
):
    return service.query(
        query=request.query,
        top_k=request.top_k,
        document_numbers=request.document_numbers,
    )