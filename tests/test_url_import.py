"""Import-from-URL: the allow-list, private-network protection, redirects, and file checks."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import dependencies, url_import
from app.services.url_import import NotAPdfError, TooLargeError, UrlNotAllowedError, DownloadFailedError

PDF = b"%PDF-1.7\n" + b"x" * 200


@pytest.fixture
def net(monkeypatch, tmp_path):
    """Fake DNS and HTTP. `routes` maps URL -> httpx.Response; `dns` maps host -> addresses."""

    state = SimpleNamespace(routes={}, dns={}, requested=[])
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "import_allowed_domains", "gov.in,nic.in,gov.uk")
    monkeypatch.setattr(url_import, "_resolve", lambda host, port: state.dns.get(host, ["93.184.216.34"]))

    def handler(request: httpx.Request) -> httpx.Response:
        state.requested.append(str(request.url))
        return state.routes[str(request.url)]

    monkeypatch.setattr(url_import, "client_factory", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    state.uploads = tmp_path / "uploads"
    return state


def test_downloads_a_pdf_from_an_approved_site(net) -> None:
    net.routes["https://cbic.gov.in/files/notif-12-2023.pdf"] = httpx.Response(200, content=PDF)
    path, name = url_import.download_pdf("https://cbic.gov.in/files/notif-12-2023.pdf")
    assert name == "notif-12-2023.pdf"
    assert Path(path).read_bytes() == PDF


def test_filename_comes_from_content_disposition(net) -> None:
    net.routes["https://www.cbic.gov.in/download?id=7"] = httpx.Response(
        200, content=PDF, headers={"content-disposition": 'attachment; filename="Circular 4/2024.pdf"'}
    )
    _, name = url_import.download_pdf("https://www.cbic.gov.in/download?id=7")
    # Path components in the header are dropped; nothing can escape the upload folder.
    assert name == "2024.pdf"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/a.pdf",  # not on the approved list
        "ftp://cbic.gov.in/a.pdf",
        "file:///etc/passwd",
        "https://user:pass@cbic.gov.in/a.pdf",
        "https://cbic.gov.in:8443/a.pdf",
        "https://evilgov.in/a.pdf",  # suffix trick: must be a real subdomain
        "not a url",
    ],
)
def test_rejects_unsafe_or_unapproved_urls(net, url) -> None:
    with pytest.raises(UrlNotAllowedError):
        url_import.download_pdf(url)
    assert net.requested == []


@pytest.mark.parametrize("address", ["10.0.0.5", "127.0.0.1", "169.254.169.254", "192.168.1.10", "::1", "172.16.0.9"])
def test_refuses_hosts_that_resolve_to_private_addresses(net, address) -> None:
    net.dns["intranet.gov.in"] = [address]
    with pytest.raises(UrlNotAllowedError):
        url_import.download_pdf("https://intranet.gov.in/a.pdf")
    assert net.requested == []


def test_literal_private_ip_is_refused_even_when_any_host_is_allowed(net, monkeypatch) -> None:
    monkeypatch.setattr(settings, "import_allowed_domains", "*")
    with pytest.raises(UrlNotAllowedError):
        url_import.download_pdf("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(UrlNotAllowedError):
        url_import.download_pdf("http://127.0.0.1/a.pdf")


def test_redirects_are_followed_and_revalidated(net) -> None:
    net.routes["https://a.gov.in/start"] = httpx.Response(302, headers={"location": "/final.pdf"})
    net.routes["https://a.gov.in/final.pdf"] = httpx.Response(200, content=PDF)
    _, name = url_import.download_pdf("https://a.gov.in/start")
    assert name == "final.pdf"

    net.routes["https://a.gov.in/evil"] = httpx.Response(302, headers={"location": "https://attacker.example/a.pdf"})
    with pytest.raises(UrlNotAllowedError):
        url_import.download_pdf("https://a.gov.in/evil")

    net.dns["internal.gov.in"] = ["10.1.2.3"]
    net.routes["https://a.gov.in/to-internal"] = httpx.Response(302, headers={"location": "https://internal.gov.in/x.pdf"})
    with pytest.raises(UrlNotAllowedError):
        url_import.download_pdf("https://a.gov.in/to-internal")
    assert "https://attacker.example/a.pdf" not in net.requested and "https://internal.gov.in/x.pdf" not in net.requested


def test_redirect_loop_is_stopped(net) -> None:
    net.routes["https://a.gov.in/loop"] = httpx.Response(302, headers={"location": "/loop"})
    with pytest.raises(DownloadFailedError):
        url_import.download_pdf("https://a.gov.in/loop")


def test_html_pages_are_rejected_and_leave_nothing_behind(net) -> None:
    net.routes["https://a.gov.in/page.pdf"] = httpx.Response(200, content=b"<html>Not found</html>")
    with pytest.raises(NotAPdfError):
        url_import.download_pdf("https://a.gov.in/page.pdf")
    assert not list(net.uploads.rglob("*.pdf"))


def test_oversized_files_are_rejected(net, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    net.routes["https://a.gov.in/big.pdf"] = httpx.Response(200, content=b"%PDF-" + b"0" * (2 * 1024 * 1024))
    with pytest.raises(TooLargeError):
        url_import.download_pdf("https://a.gov.in/big.pdf")
    assert not list(net.uploads.rglob("*.pdf"))


def test_server_errors_are_reported(net) -> None:
    net.routes["https://a.gov.in/missing.pdf"] = httpx.Response(404)
    with pytest.raises(DownloadFailedError, match="404"):
        url_import.download_pdf("https://a.gov.in/missing.pdf")


def test_api_maps_errors_and_queues_a_job(net, monkeypatch) -> None:
    from app.db.database import get_session

    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)
    runner = MagicMock()
    runner.submit.return_value = SimpleNamespace(
        id="8c0c7a0e-6a39-4a39-9c6f-1f1f1f1f1f1f", status="PENDING", file_path="x", original_filename="a.pdf", document_id=None,
        error=None, attempts=0, submitted_by=None, created_at="2026-11-15T00:00:00Z", started_at=None, finished_at=None,
    )
    app.dependency_overrides[get_session] = lambda: MagicMock()
    app.dependency_overrides[dependencies.get_job_runner] = lambda: runner
    try:
        client = TestClient(app)
        bad = client.post("/api/v1/ingest/url", json={"url": "https://example.com/a.pdf"})
        assert bad.status_code == 403 and "approved list" in bad.json()["detail"]

        net.routes["https://a.gov.in/ok.pdf"] = httpx.Response(200, content=PDF)
        ok = client.post("/api/v1/ingest/url", json={"url": "https://a.gov.in/ok.pdf"})
        assert ok.status_code == 202
        runner.submit.assert_called_once()
        assert runner.submit.call_args.kwargs["original_filename"] == "ok.pdf"

        domains = client.get("/api/v1/ingest/url/allowed-domains").json()
        assert "gov.in" in domains
    finally:
        app.dependency_overrides.clear()


def test_waits_while_a_site_prepares_the_pdf(net, monkeypatch) -> None:
    monkeypatch.setattr(url_import, "PREPARING_WAIT_SECONDS", 0)
    replies = iter([httpx.Response(202), httpx.Response(202), httpx.Response(200, content=PDF)])

    class Route(dict):
        def __getitem__(self, key):
            return next(replies)

    net.routes = Route()
    _, name = url_import.download_pdf("https://www.legislation.gov.uk/ukpga/2018/12/data.pdf")
    assert name == "data.pdf"


def test_gives_up_if_the_pdf_is_never_ready(net, monkeypatch) -> None:
    monkeypatch.setattr(url_import, "PREPARING_WAIT_SECONDS", 0)
    net.routes["https://a.gov.in/slow.pdf"] = httpx.Response(202)
    with pytest.raises(DownloadFailedError, match="202"):
        url_import.download_pdf("https://a.gov.in/slow.pdf")
