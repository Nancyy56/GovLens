"""
FastAPI application factory and configuration.

Creates and configures the FastAPI application instance with
middleware, error handlers, background workers, and route registration.
"""

import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.core import metrics
from app.core.config import settings
from app.core.constants import API_V1_STR, PROJECT_NAME, PROJECT_DESCRIPTION
from app.core.logging import configure_logging, request_id_var
from app.generation.ollama_client import LLMUnavailableError
from app.api.routes import api_router
from app.api.security import require_admin
from app.ingestion.exceptions import DocumentLoadError
from app.services.exceptions import (
    AmbiguousDocumentError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    PathNotAllowedError,
    SourceUnavailableError,
)

configure_logging(settings.log_level, settings.log_format)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
INITIAL_PASSWORD_FILE = Path("data/initial_admin_password.txt")


def _bootstrap_admin() -> None:
    from app.db.database import SessionLocal
    from app.services.auth import AuthService

    if not settings.auth_enabled:
        logger.warning("AUTH_ENABLED is false: every request is treated as an admin.")
        return
    with SessionLocal() as session:
        generated = AuthService(session).ensure_initial_admin(
            settings.admin_username, settings.admin_password, INITIAL_PASSWORD_FILE
        )
    if generated:
        logger.warning(
            "Created admin user %r with a generated password, saved to %s. Sign in and change it.",
            settings.admin_username,
            INITIAL_PASSWORD_FILE,
        )


def _startup_repair() -> None:
    """Fix PostgreSQL/Qdrant drift left by a crash (runs in the background)."""

    from app.db.database import SessionLocal
    from app.services.dependencies import get_embedding_provider, get_text_tokenizer, get_vector_store
    from app.services.documents import DocumentService

    try:
        with SessionLocal() as session:
            DocumentService(
                session,
                get_vector_store(),
                embedding_provider=get_embedding_provider(),
                tokenizer=get_text_tokenizer(),
            ).reconcile()
    except Exception:
        logger.exception("Startup reconciliation failed; run POST /api/v1/documents/reconcile later")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.dependencies import get_job_runner

    logger.info("Starting %s in %s mode", PROJECT_NAME, settings.env)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    runner = get_job_runner()
    try:
        _bootstrap_admin()
        runner.recover_interrupted()
    except Exception:
        logger.exception("Startup database tasks failed")
    runner.start()
    threading.Thread(target=_startup_repair, name="startup-repair", daemon=True).start()
    yield
    runner.stop()
    logger.info("Shutting down %s", PROJECT_NAME)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Sets up:
    - Application metadata
    - Request IDs and metrics middleware
    - CORS middleware
    - API routes, metrics endpoint, and the web interface
    - Exception handlers

    Returns:
        FastAPI: Configured application instance.
    """
    app = FastAPI(
        title=PROJECT_NAME,
        description=PROJECT_DESCRIPTION,
        version="0.3.0",
        # Never True: Starlette's debug mode returns tracebacks to clients.
        # Errors are logged with their request id instead.
        debug=False,
        lifespan=lifespan,
    )

    origins = settings.cors_origin_list
    if origins:
        # Browsers reject credentials with a wildcard origin, so only allow
        # them for an explicit origin list.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials="*" not in origins,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id[:64]
        token = request_id_var.set(request.state.request_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id_var.get()
            return response
        finally:
            route = request.scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            if route_path.startswith(API_V1_STR):
                metrics.http_requests.inc(request.method, route_path, str(status_code))
                metrics.http_latency.observe(time.perf_counter() - started, route_path)
            request_id_var.reset(token)

    _register_exception_handlers(app)
    app.include_router(api_router, prefix=API_V1_STR)

    @app.get(f"{API_V1_STR}/metrics", response_class=PlainTextResponse, tags=["health"], dependencies=[Depends(require_admin)])
    def metrics_endpoint() -> str:
        """Prometheus text-format metrics (admins only)."""

        from app.services.dependencies import get_job_runner

        runner = get_job_runner()
        return metrics.render(
            {
                "govlens_ingestion_queue_depth": ("Pending ingestion jobs", runner.queue_depth),
                "govlens_ingestion_workers_running": ("1 if workers are alive", lambda: float(runner.running)),
            }
        )

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/", include_in_schema=False)
        def web_ui() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    def error(status_code: int, detail: str, **extra) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": detail, **extra})

    @app.exception_handler(DuplicateDocumentError)
    async def duplicate(_: Request, exc: DuplicateDocumentError):
        return error(
            409,
            str(exc),
            existing_document_id=str(exc.existing_document_id),
            document_number=exc.document_number,
        )

    @app.exception_handler(DocumentNotFoundError)
    async def not_found(_: Request, exc: DocumentNotFoundError):
        return error(404, str(exc))

    @app.exception_handler(AmbiguousDocumentError)
    async def ambiguous(_: Request, exc: AmbiguousDocumentError):
        return error(409, str(exc), document_ids=[str(i) for i in exc.document_ids])

    @app.exception_handler(SourceUnavailableError)
    async def source_unavailable(_: Request, exc: SourceUnavailableError):
        return error(409, str(exc))

    @app.exception_handler(PathNotAllowedError)
    async def path_not_allowed(_: Request, exc: PathNotAllowedError):
        return error(403, str(exc))

    @app.exception_handler(LLMUnavailableError)
    async def llm_unavailable(_: Request, exc: LLMUnavailableError):
        logger.error("Language model backend failed: %s", exc)
        return error(503, f"The language model is unavailable: {exc}", retryable=True)

    @app.exception_handler(DocumentLoadError)
    async def load_failed(_: Request, exc: DocumentLoadError):
        return error(422, str(exc))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        # Never leak internals; the request id links the response to the logged traceback.
        request_id = getattr(request.state, "request_id", "-")
        logger.error("Unhandled error in request %s", request_id, exc_info=exc)
        return error(500, "Internal server error", request_id=request_id)


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
