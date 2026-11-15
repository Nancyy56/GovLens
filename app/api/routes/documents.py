"""Document management routes."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.dependencies import get_document_service, get_ingestion_service, get_llm_client
from app.api.schemas import RelationshipCreateRequest
from app.api.security import Principal, require_admin, require_editor
from app.core.config import settings
from app.services import audit
from app.generation.interfaces import LLMClient
from app.models.enums import DocumentStatus, DocumentType
from app.schemas.documents import DocumentRelationshipRead
from app.schemas.processing import PageContent
from app.services.brief import BriefService, DocumentBrief
from app.services.documents import DocumentDetail, DocumentPage, DocumentService, ReconcileReport
from app.services.exceptions import SourceUnavailableError
from app.services.ingestion import DocumentIngestionService
from app.services.schemas import IngestionResult

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentPage)
def list_documents(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    document_type: DocumentType | None = None,
    document_status: DocumentStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, description="Matches number, title, subject, or department"),
    service: DocumentService = Depends(get_document_service),
):
    return service.list(
        limit=limit,
        offset=offset,
        document_type=document_type,
        status=document_status,
        search=search,
    )


@router.post("/reconcile", response_model=ReconcileReport)
def reconcile_stores(principal: Principal = Depends(require_admin), service: DocumentService = Depends(get_document_service)):
    """Remove vectors for documents that no longer exist and list documents missing vectors."""

    report = service.reconcile()
    audit.record(principal.username, "index.reconcile", detail=f"{len(report.documents_repaired)} document(s) repaired")
    return report


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: uuid.UUID, service: DocumentService = Depends(get_document_service)):
    return service.get(document_id)


@router.post("/{document_id}/brief", response_model=DocumentBrief)
def document_brief(
    document_id: uuid.UUID,
    refresh: bool = Query(False, description="Ignore the cached brief and write a new one."),
    service: DocumentService = Depends(get_document_service),
    llm: LLMClient = Depends(get_llm_client),
):
    """A short plain-language summary: who is affected, what to do, deadlines, penalties."""

    return BriefService(service, llm).brief(document_id, refresh=refresh)


@router.get("/{document_id}/pages/{page_number}", response_model=PageContent)
def get_page(document_id: uuid.UUID, page_number: int, service: DocumentService = Depends(get_document_service)):
    """Stored text of one page, e.g. to show the passage behind a citation."""

    return service.page_text(document_id, page_number)


@router.get("/{document_id}/file", response_class=FileResponse)
def original_pdf(document_id: uuid.UUID, service: DocumentService = Depends(get_document_service)):
    """The original uploaded PDF, for viewing in the browser."""

    path = service.source_file(document_id, [settings.upload_dir, *settings.ingest_allowed_dir_list])
    if path is None:
        raise HTTPException(status_code=404, detail="The original file is not available for this document")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=Path(path).name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(require_editor),
    service: DocumentService = Depends(get_document_service),
):
    """Delete a document, its chunks, vectors, and links. Documents it superseded become active again."""

    detail = service.get(document_id)
    service.delete(document_id)
    audit.record(principal.username, "document.delete", target=detail.document_number, detail=detail.title)


@router.post("/{document_id}/reingest", response_model=IngestionResult)
def reingest_document(
    document_id: uuid.UUID,
    principal: Principal = Depends(require_editor),
    documents: DocumentService = Depends(get_document_service),
    ingestion: DocumentIngestionService = Depends(get_ingestion_service),
):
    """Re-run ingestion from the stored source file, e.g. after extraction rules improve.

    The existing record is kept until the new one is stored, so a failed
    re-ingest changes nothing. Links are re-detected from the text and
    manually added links are carried over.
    """

    try:
        result = documents.reingest(document_id, ingestion)
        audit.record(principal.username, "document.reingest", target=result.document_number)
        return result
    except SourceUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/{document_id}/relationships",
    response_model=DocumentRelationshipRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_editor)],
)
def add_relationship(
    document_id: uuid.UUID,
    request: RelationshipCreateRequest,
    service: DocumentService = Depends(get_document_service),
):
    """Manually link this document to another, e.g. when automatic detection missed it."""

    try:
        return service.add_relationship(document_id, request.target_document_id, request.relationship_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/relationships/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_editor)],
)
def delete_relationship(relationship_id: uuid.UUID, service: DocumentService = Depends(get_document_service)):
    service.delete_relationship(relationship_id)
