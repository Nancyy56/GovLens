"""HTTP-level behaviour: auth, rate limits, error mapping, uploads, streaming."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import health
from app.api.security import memory_rate_limiter
from app.core.config import settings
from app.db.database import get_session
from app.main import app
from app.services import dependencies
from app.services.exceptions import DuplicateDocumentError
from app.services.schemas import IngestionResult


@pytest.fixture
def client(monkeypatch):
    # Most tests exercise one route's behaviour; auth has its own tests below and in test_auth.py.
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "api_keys", "")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")
    memory_rate_limiter.reset()
    app.dependency_overrides[get_session] = lambda: MagicMock()
    # No `with` block: the lifespan (which touches the real database) does not run.
    yield TestClient(app)
    app.dependency_overrides.clear()


def _override(dependency, value) -> None:
    app.dependency_overrides[dependency] = lambda: value


def _fake_documents_service():
    service = MagicMock()
    service.list.return_value = {"items": [], "total": 0, "limit": 50, "offset": 0}
    return service


def test_health_is_public_even_with_auth(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_service_api_keys_and_their_roles(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "secret,viewer-key:VIEWER")
    _override(dependencies.get_document_service, _fake_documents_service())

    assert client.get("/api/v1/documents").status_code == 401
    assert client.get("/api/v1/documents", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/v1/documents", headers={"X-API-Key": "secret"}).status_code == 200
    assert client.get("/api/v1/documents", headers={"Authorization": "Bearer secret"}).status_code == 200
    assert client.get("/api/v1/documents", headers={"X-API-Key": "viewer-key"}).status_code == 200
    denied = client.delete(f"/api/v1/documents/{uuid.uuid4()}", headers={"X-API-Key": "viewer-key"})
    assert denied.status_code == 403


def test_rate_limit_returns_429_with_retry_after(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    memory_rate_limiter.reset()
    _override(dependencies.get_document_service, _fake_documents_service())

    codes = [client.get("/api/v1/documents").status_code for _ in range(3)]

    assert codes == [200, 200, 429]
    assert int(client.get("/api/v1/documents").headers["Retry-After"]) >= 1


def test_ingest_path_outside_allowed_dirs_is_forbidden(client) -> None:
    _override(dependencies.get_ingestion_service, MagicMock())
    response = client.post("/api/v1/ingest", json={"file_path": "/etc/secret.pdf"})
    assert response.status_code == 403


def test_duplicate_ingestion_maps_to_409(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ingest_allowed_dirs", str(tmp_path))
    existing = uuid.uuid4()
    service = MagicMock()
    service.ingest.side_effect = DuplicateDocumentError(existing, "17/2024")
    _override(dependencies.get_ingestion_service, service)

    response = client.post("/api/v1/ingest", json={"file_path": str(tmp_path / "a.pdf")})

    assert response.status_code == 409
    assert response.json()["existing_document_id"] == str(existing)


def test_upload_rejects_non_pdf(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    _override(dependencies.get_ingestion_service, MagicMock())
    _override(dependencies.get_job_runner, MagicMock())

    wrong_extension = client.post("/api/v1/ingest/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    fake_pdf = client.post("/api/v1/ingest/upload", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})

    assert wrong_extension.status_code == 415
    assert fake_pdf.status_code == 415
    assert list(tmp_path.iterdir()) == []


def test_upload_enforces_size_limit(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    _override(dependencies.get_ingestion_service, MagicMock())
    _override(dependencies.get_job_runner, MagicMock())

    big = b"%PDF-" + b"0" * (2 * 1024 * 1024)
    response = client.post("/api/v1/ingest/upload", files={"file": ("big.pdf", big, "application/pdf")})

    assert response.status_code == 413
    assert list(tmp_path.iterdir()) == []


def test_upload_ingests_and_reports_result(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    service = MagicMock()
    service.ingest.return_value = IngestionResult(
        document_id=uuid.uuid4(), status="ACTIVE", chunk_count=2, embedded_count=2, document_number="17/2024"
    )
    _override(dependencies.get_ingestion_service, service)
    _override(dependencies.get_job_runner, MagicMock())

    response = client.post("/api/v1/ingest/upload", files={"file": ("My Notice.pdf", b"%PDF-1.7 body", "application/pdf")})

    assert response.status_code == 201
    assert response.json()["document_number"] == "17/2024"
    saved_path, = service.ingest.call_args.args
    assert saved_path.endswith("My_Notice.pdf")
    assert service.ingest.call_args.kwargs["original_filename"] == "My Notice.pdf"


def test_failed_upload_ingestion_removes_file(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    service = MagicMock()
    service.ingest.side_effect = DuplicateDocumentError(uuid.uuid4())
    _override(dependencies.get_ingestion_service, service)
    _override(dependencies.get_job_runner, MagicMock())

    response = client.post("/api/v1/ingest/upload", files={"file": ("a.pdf", b"%PDF-1.7", "application/pdf")})

    assert response.status_code == 409
    assert list(tmp_path.iterdir()) == []


def test_background_upload_returns_job(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    runner = MagicMock()
    runner.submit.return_value = SimpleNamespace(
        id=uuid.uuid4(), status="PENDING", file_path="x", original_filename="a.pdf", document_id=None,
        error=None, created_at="2026-01-01T00:00:00Z", started_at=None, finished_at=None,
    )
    _override(dependencies.get_ingestion_service, MagicMock())
    _override(dependencies.get_job_runner, runner)

    response = client.post(
        "/api/v1/ingest/upload?background=true", files={"file": ("a.pdf", b"%PDF-1.7", "application/pdf")}
    )

    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"


def test_stream_uses_server_sent_events(client) -> None:
    service = MagicMock()
    service.stream.return_value = iter(
        [
            {"event": "retrieval", "data": {"retrieved_chunks": 1}},
            {"event": "token", "data": {"text": "Hi"}},
            {"event": "done", "data": {"answer_markdown": "Hi"}},
        ]
    )
    _override(dependencies.get_query_service, service)

    response = client.post("/api/v1/query/stream", json={"query": "q"})

    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: token\ndata: {"text": "Hi"}\n\n' in response.text
    assert response.text.rstrip().endswith('data: {"answer_markdown": "Hi"}')


def test_stream_reports_errors_as_event(client) -> None:
    def failing():
        yield {"event": "retrieval", "data": {}}
        raise RuntimeError("ollama down")

    service = MagicMock()
    service.stream.return_value = failing()
    _override(dependencies.get_query_service, service)

    response = client.post("/api/v1/query/stream", json={"query": "q"})

    assert 'event: error\ndata: {"detail": "ollama down"}' in response.text


def test_query_rejects_empty_question(client) -> None:
    _override(dependencies.get_query_service, MagicMock())
    assert client.post("/api/v1/query", json={"query": ""}).status_code == 422


def test_compare_invalid_request_is_400(client) -> None:
    service = MagicMock()
    service.compare.side_effect = ValueError("Choose two different documents to compare")
    _override(dependencies.get_comparison_service, service)

    response = client.post("/api/v1/compare", json={"base": "1/2024", "target": "1/2024"})

    assert response.status_code == 400


def test_readiness_reports_each_dependency(client, monkeypatch) -> None:
    monkeypatch.setattr(health, "_ping_database", lambda: None)
    monkeypatch.setattr(health, "get_vector_store", lambda: SimpleNamespace(ping=lambda: None))

    def ollama_down():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(health, "get_llm_client", lambda: SimpleNamespace(ping=ollama_down))
    monkeypatch.setattr(health, "get_reranker", lambda: None)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["ollama"] == {"ok": False, "detail": "connection refused"}


def test_llm_failure_maps_to_503(client) -> None:
    from app.generation.ollama_client import LLMUnavailableError

    service = MagicMock()
    service.query.side_effect = LLMUnavailableError("Ollama returned HTTP 500: model runner has unexpectedly stopped")
    _override(dependencies.get_query_service, service)

    response = client.post("/api/v1/query", json={"query": "q"})

    assert response.status_code == 503
    assert "model runner has unexpectedly stopped" in response.json()["detail"]
    assert response.json()["retryable"] is True


def test_ollama_http_error_becomes_llm_unavailable(monkeypatch) -> None:
    import io
    from urllib.error import HTTPError

    from app.generation import ollama_client

    def failing_urlopen(*args, **kwargs):
        raise HTTPError("http://ollama/api/generate", 500, "err", {}, io.BytesIO(b'{"error": "runner killed"}'))

    monkeypatch.setattr(ollama_client, "urlopen", failing_urlopen)

    with pytest.raises(ollama_client.LLMUnavailableError, match="HTTP 500: runner killed"):
        ollama_client.OllamaClient().generate("prompt")


def _fake_urlopen(responses):
    """Return an urlopen replacement yielding each response (or raising each exception) in turn."""
    import io
    import json

    calls = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout=None):
        calls.append(json.loads(request.data.decode()))
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return Response(json.dumps(item).encode())

    return urlopen, calls


def test_ollama_retries_once_after_runner_crash(monkeypatch) -> None:
    import io
    from urllib.error import HTTPError

    from app.generation import ollama_client

    crash = HTTPError("u", 500, "err", {}, io.BytesIO(b'{"error": "model runner has unexpectedly stopped"}'))
    urlopen, calls = _fake_urlopen([crash, {"response": "recovered"}])
    monkeypatch.setattr(ollama_client, "urlopen", urlopen)
    monkeypatch.setattr(ollama_client.time, "sleep", lambda s: None)

    assert ollama_client.OllamaClient(keep_alive=0).generate("p") == "recovered"
    assert len(calls) == 2
    assert calls[0]["keep_alive"] == 0


def test_ollama_does_not_retry_client_errors(monkeypatch) -> None:
    import io
    from urllib.error import HTTPError

    from app.generation import ollama_client

    missing = HTTPError("u", 404, "err", {}, io.BytesIO(b'{"error": "model not found"}'))
    urlopen, calls = _fake_urlopen([missing, {"response": "unused"}])
    monkeypatch.setattr(ollama_client, "urlopen", urlopen)

    with pytest.raises(ollama_client.LLMUnavailableError, match="404"):
        ollama_client.OllamaClient().generate("p")
    assert len(calls) == 1
