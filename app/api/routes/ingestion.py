"""Document ingestion routes: by path, by upload, and as background jobs."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_ingestion_service, get_job_runner
from app.api.schemas import ImportUrlRequest, IngestRequest, IngestionJobRead
from app.api.security import Principal, require_editor
from app.core.config import settings
from app.db.database import get_session
from app.models.enums import IngestionJobStatus
from app.services.ingestion import DocumentIngestionService
from app.services.jobs import IngestionJobRunner, discard_upload
from app.services.paths import ensure_path_allowed
from app.services import audit, url_import
from app.services.schemas import IngestionResult

router = APIRouter(prefix="/ingest", tags=["ingestion"])

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_CHUNK_BYTES = 1024 * 1024


@router.post("", response_model=IngestionResult, status_code=status.HTTP_201_CREATED)
def ingest_document(
    request: IngestRequest,
    principal: Principal = Depends(require_editor),
    service: DocumentIngestionService = Depends(get_ingestion_service),
):
    """Ingest a PDF that already exists on the server (inside INGEST_ALLOWED_DIRS)."""

    path = ensure_path_allowed(request.file_path, settings.ingest_allowed_dir_list)
    return service.ingest(path)


@router.post(
    "/upload",
    response_model=IngestionResult | IngestionJobRead,
    status_code=status.HTTP_201_CREATED,
    responses={202: {"model": IngestionJobRead, "description": "Queued as a background job"}},
)
def upload_document(
    file: UploadFile = File(..., description="PDF file"),
    background: bool = Query(False, description="Queue the ingestion and return a job id immediately."),
    principal: Principal = Depends(require_editor),
    service: DocumentIngestionService = Depends(get_ingestion_service),
    runner: IngestionJobRunner = Depends(get_job_runner),
    session: Session = Depends(get_session),
):
    """Upload a PDF and ingest it, either now or as a background job."""

    saved_path = _save_upload(file)
    if background:
        job = runner.submit(session, saved_path, original_filename=file.filename, submitted_by=principal.user_id)
        audit.record(principal.username, "document.upload", target=file.filename, detail="queued")
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=IngestionJobRead.model_validate(job).model_dump(mode="json"),
        )
    try:
        result = service.ingest(saved_path, original_filename=file.filename)
    except Exception:
        discard_upload(saved_path, settings.upload_dir)
        raise
    audit.record(principal.username, "document.upload", target=file.filename)
    return result


@router.post("/url", response_model=IngestionJobRead, status_code=status.HTTP_202_ACCEPTED)
def import_from_url(
    request: ImportUrlRequest,
    principal: Principal = Depends(require_editor),
    runner: IngestionJobRunner = Depends(get_job_runner),
    session: Session = Depends(get_session),
):
    """Download a PDF from an approved government website and queue it for ingestion."""

    try:
        saved_path, filename = url_import.download_pdf(request.url)
    except url_import.ImportError_ as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    job = runner.submit(session, saved_path, original_filename=filename, submitted_by=principal.user_id)
    audit.record(principal.username, "document.import_url", target=filename, detail=request.url)
    return job


@router.get("/url/allowed-domains", response_model=list[str])
def allowed_import_domains():
    """Sites that "import from URL" accepts (an empty list never happens; ``*`` means any public site)."""

    return settings.import_allowed_domain_list


@router.post("/jobs", response_model=IngestionJobRead, status_code=status.HTTP_202_ACCEPTED)
def submit_job(
    request: IngestRequest,
    principal: Principal = Depends(require_editor),
    runner: IngestionJobRunner = Depends(get_job_runner),
    session: Session = Depends(get_session),
):
    """Queue ingestion of a server-side PDF and return immediately."""

    path = ensure_path_allowed(request.file_path, settings.ingest_allowed_dir_list)
    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
    return runner.submit(session, path, submitted_by=principal.user_id)


@router.get("/jobs", response_model=list[IngestionJobRead])
def list_jobs(
    limit: int = Query(50, ge=1, le=500),
    job_status: IngestionJobStatus | None = Query(None, alias="status"),
    runner: IngestionJobRunner = Depends(get_job_runner),
    session: Session = Depends(get_session),
):
    return runner.list(session, limit=limit, status=job_status)


@router.get("/jobs/{job_id}", response_model=IngestionJobRead)
def get_job(
    job_id: uuid.UUID,
    runner: IngestionJobRunner = Depends(get_job_runner),
    session: Session = Depends(get_session),
):
    job = runner.get(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No ingestion job {job_id}")
    return job


def _save_upload(file: UploadFile) -> str:
    """Validate and store an upload under its own folder in UPLOAD_DIR."""

    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are supported")

    header = file.file.read(5)
    if header != b"%PDF-":
        raise HTTPException(status_code=415, detail="File is not a valid PDF")

    safe_name = _UNSAFE_FILENAME_CHARS.sub("_", filename).strip("._") or "upload.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
    folder = Path(settings.upload_dir).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    destination = folder / safe_name

    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = len(header)
    try:
        with open(destination, "wb") as out:
            out.write(header)
            while block := file.file.read(_CHUNK_BYTES):
                written += len(block)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {settings.max_upload_mb} MB upload limit",
                    )
                out.write(block)
    except Exception:
        discard_upload(str(destination), settings.upload_dir)
        raise
    return str(destination)
