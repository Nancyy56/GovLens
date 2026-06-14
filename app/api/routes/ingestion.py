"""Document ingestion route."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_ingestion_service
from app.api.schemas import IngestRequest
from app.db.database import get_session
from app.services.ingestion import DocumentIngestionService
from app.services.schemas import IngestionResult

router = APIRouter(prefix="/ingest", tags=["ingestion"])


class IngestResponse:
    def __init__(self, result: IngestionResult, document_number: str | None = None, document_type: str | None = None):
        self.document_id = str(result.document_id)
        self.document_number = document_number or ""
        self.document_type = document_type or ""
        self.chunk_count = result.chunk_count


@router.post("/", response_model=dict)
async def ingest_document(
    request: IngestRequest,
    service: DocumentIngestionService = Depends(get_ingestion_service),
):
    try:
        result = service.ingest(request.file_path)
        return IngestResponse(result).__dict__
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(exc))
