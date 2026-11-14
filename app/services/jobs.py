"""Background ingestion jobs backed by PostgreSQL.

Large or scanned PDFs can take minutes to OCR and embed, so the API can
queue them and return a job id. Jobs live in the ``ingestion_jobs`` table.
Worker threads claim the oldest PENDING job with a conditional UPDATE, which
is safe even when several API processes share the database.

A job interrupted by a restart is put back in the queue on startup and
retried, up to ``max_attempts`` times. A job that fails because the file
itself is bad is not retried.
"""

from __future__ import annotations

import logging
import shutil
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.documents import IngestionJob
from app.models.enums import IngestionJobStatus
from app.services.exceptions import DuplicateDocumentError
from app.services.ingestion import DocumentIngestionService

logger = logging.getLogger(__name__)


def discard_upload(file_path: str, upload_dir: str) -> None:
    """Delete an uploaded file (and its private folder) after a failed ingestion."""

    path = Path(file_path).resolve()
    root = Path(upload_dir).resolve()
    if root not in path.parents:
        return
    folder = path.parent
    if folder != root and folder.parent == root:
        shutil.rmtree(folder, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


class IngestionJobRunner:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        service_factory: Callable[[Session], DocumentIngestionService],
        upload_dir: str,
        max_workers: int = 1,
        poll_seconds: float = 2.0,
        max_attempts: int = 3,
    ) -> None:
        self.session_factory = session_factory
        self.service_factory = service_factory
        self.upload_dir = upload_dir
        self.max_workers = max(1, max_workers)
        self.poll_seconds = poll_seconds
        self.max_attempts = max_attempts
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()

    # --- lifecycle ------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._threads:
                return
            self._stop.clear()
            for index in range(self.max_workers):
                thread = threading.Thread(target=self._worker_loop, name=f"ingest-worker-{index}", daemon=True)
                thread.start()
                self._threads.append(thread)
        logger.info("Started %s ingestion worker(s)", self.max_workers)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads = []

    @property
    def running(self) -> bool:
        return any(thread.is_alive() for thread in self._threads)

    # --- API ------------------------------------------------------------

    def submit(
        self,
        session: Session,
        file_path: str,
        original_filename: str | None = None,
        submitted_by: uuid.UUID | None = None,
    ) -> IngestionJob:
        job = IngestionJob(
            status=IngestionJobStatus.PENDING,
            file_path=file_path,
            original_filename=original_filename,
            submitted_by=submitted_by,
            attempts=0,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        self._wake.set()
        logger.info("Queued ingestion job %s for %s", job.id, file_path)
        return job

    def get(self, session: Session, job_id: uuid.UUID) -> IngestionJob | None:
        return session.get(IngestionJob, job_id)

    def list(self, session: Session, limit: int = 50, status: IngestionJobStatus | None = None) -> list[IngestionJob]:
        statement = select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)
        if status is not None:
            statement = statement.where(IngestionJob.status == status)
        return list(session.scalars(statement).all())

    def queue_depth(self) -> int:
        with self.session_factory() as session:
            return session.scalar(
                select(func.count()).select_from(IngestionJob).where(IngestionJob.status == IngestionJobStatus.PENDING)
            ) or 0

    def recover_interrupted(self) -> tuple[int, int]:
        """Requeue jobs left RUNNING by a stopped process; fail those out of attempts.

        Returns (requeued, failed). Call once at startup, before workers start.
        """

        with self.session_factory() as session:
            requeued = session.execute(
                update(IngestionJob)
                .where(IngestionJob.status == IngestionJobStatus.RUNNING, IngestionJob.attempts < self.max_attempts)
                .values(status=IngestionJobStatus.PENDING, started_at=None)
            ).rowcount or 0
            failed = session.execute(
                update(IngestionJob)
                .where(IngestionJob.status == IngestionJobStatus.RUNNING)
                .values(
                    status=IngestionJobStatus.FAILED,
                    error=f"Interrupted {self.max_attempts} times; giving up. Submit the file again.",
                    finished_at=datetime.now(UTC),
                )
            ).rowcount or 0
            session.commit()
        if requeued or failed:
            logger.warning("Recovered interrupted ingestion jobs: %s requeued, %s failed", requeued, failed)
        return requeued, failed

    def run_pending_once(self) -> uuid.UUID | None:
        """Claim and run one pending job in the calling thread (used by tests)."""

        job_id = self._claim_next()
        if job_id is not None:
            self._run(job_id)
        return job_id

    # --- internals ------------------------------------------------------

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self._claim_next()
            except Exception:
                logger.exception("Could not poll for ingestion jobs")
                job_id = None
            if job_id is not None:
                self._run(job_id)
                continue
            self._wake.wait(self.poll_seconds)
            self._wake.clear()

    def _claim_next(self) -> uuid.UUID | None:
        with self.session_factory() as session:
            while True:
                candidate = session.scalar(
                    select(IngestionJob.id)
                    .where(IngestionJob.status == IngestionJobStatus.PENDING)
                    .order_by(IngestionJob.created_at, IngestionJob.id)
                    .limit(1)
                )
                if candidate is None:
                    return None
                # Conditional update: only one worker can move a given job out of PENDING.
                claimed = session.execute(
                    update(IngestionJob)
                    .where(IngestionJob.id == candidate, IngestionJob.status == IngestionJobStatus.PENDING)
                    .values(
                        status=IngestionJobStatus.RUNNING,
                        started_at=datetime.now(UTC),
                        attempts=IngestionJob.attempts + 1,
                    )
                ).rowcount
                session.commit()
                if claimed == 1:
                    return candidate

    def _run(self, job_id: uuid.UUID) -> None:
        with self.session_factory() as session:
            job = session.get(IngestionJob, job_id)
            if job is None:
                return
            file_path, original_filename = job.file_path, job.original_filename
            logger.info("Running ingestion job %s (attempt %s)", job_id, job.attempts)

            document_id: uuid.UUID | None = None
            error: str | None = None
            try:
                result = self.service_factory(session).ingest(file_path, original_filename)
                document_id = result.document_id
            except DuplicateDocumentError as exc:
                document_id = exc.existing_document_id
                error = f"Duplicate: this file was already ingested as document {exc.existing_document_id}"
            except Exception as exc:
                logger.exception("Ingestion job %s failed", job_id)
                error = str(exc) or exc.__class__.__name__

            if error is not None:
                discard_upload(file_path, self.upload_dir)

            job = session.get(IngestionJob, job_id)
            job.status = IngestionJobStatus.FAILED if error else IngestionJobStatus.SUCCEEDED
            job.document_id = document_id
            job.error = error
            job.finished_at = datetime.now(UTC)
            session.commit()
            logger.info("Ingestion job %s finished: %s", job_id, job.status.value)
