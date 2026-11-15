"""Download a PDF from an approved government website so it can be ingested.

Fetching a user-supplied URL is a classic server-side request forgery (SSRF) risk, so
every request is restricted:

* only http(s) on the standard ports, without credentials in the URL;
* the host must be on ``IMPORT_ALLOWED_DOMAINS`` (or that setting must be ``*``);
* the host must resolve only to public internet addresses, never to loopback, private,
  link-local or cloud-metadata ranges, and the address actually connected to is checked too;
* redirects are followed manually (at most 5) and each hop is validated again;
* the body is capped at ``MAX_UPLOAD_MB`` and must start with the ``%PDF-`` signature.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import time
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
# Some sites (e.g. legislation.gov.uk) answer 202 while they build a PDF; wait and ask again.
MAX_PREPARING_RETRIES = 4
PREPARING_WAIT_SECONDS = 3.0
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_FILENAME_IN_HEADER = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.IGNORECASE)


class ImportError_(Exception):
    """Base class; ``status_code`` is the HTTP status the API should answer with."""

    status_code = 400


class UrlNotAllowedError(ImportError_):
    status_code = 403


class DownloadFailedError(ImportError_):
    status_code = 502


class NotAPdfError(ImportError_):
    status_code = 415


class TooLargeError(ImportError_):
    status_code = 413


def _host_allowed(host: str, allowed: Sequence[str]) -> bool:
    if "*" in allowed:
        return True
    return any(host == domain or host.endswith("." + domain) for domain in allowed)


def _is_public(address: str) -> bool:
    try:
        return ipaddress.ip_address(address.split("%")[0]).is_global
    except ValueError:
        return False


def _resolve(host: str, port: int) -> list[str]:
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    except socket.gaierror as exc:
        raise DownloadFailedError(f"Could not find the server {host!r}") from exc


def validate_url(url: str, allowed_domains: Sequence[str] | None = None) -> httpx.URL:
    """Raise ``UrlNotAllowedError`` unless the URL is safe to fetch; return the parsed URL."""

    allowed = list(settings.import_allowed_domain_list if allowed_domains is None else allowed_domains)
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise UrlNotAllowedError("Only http and https links can be imported")
    if parts.username or parts.password:
        raise UrlNotAllowedError("Links with embedded credentials are not allowed")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise UrlNotAllowedError("That does not look like a valid link")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port not in (80, 443):
        raise UrlNotAllowedError("Only the standard web ports are allowed")
    if not _host_allowed(host, allowed):
        raise UrlNotAllowedError(
            f"{host} is not on the approved list of government sites. Download the PDF and upload it instead, "
            "or ask an administrator to add the domain (IMPORT_ALLOWED_DOMAINS)."
        )
    # A literal IP is checked directly; names are resolved and every address must be public.
    addresses = [host] if _looks_like_ip(host) else _resolve(host, port)
    if not addresses or not all(_is_public(address) for address in addresses):
        raise UrlNotAllowedError("That address points to a private or internal network and cannot be imported")
    return httpx.URL(parts.geturl())


def _looks_like_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def _filename(response: httpx.Response, url: httpx.URL) -> str:
    candidate = ""
    match = _FILENAME_IN_HEADER.search(response.headers.get("content-disposition", ""))
    if match:
        candidate = unquote(match.group(1))
    if not candidate:
        candidate = unquote(Path(url.path).name)
    candidate = Path(candidate).name
    safe = _UNSAFE_FILENAME_CHARS.sub("_", candidate).strip("._") or "document"
    return safe if safe.lower().endswith(".pdf") else safe + ".pdf"


def _default_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=False,
        timeout=httpx.Timeout(settings.import_timeout_seconds, connect=10),
        headers={"User-Agent": "GovLens-importer/1.0", "Accept": "application/pdf,*/*;q=0.5"},
    )


# Replaced in tests so no real network access is needed.
client_factory: Callable[[], httpx.Client] = _default_client


def _check_connected_peer(response: httpx.Response) -> None:
    """Re-check the address we actually connected to (guards against DNS changing mid-request)."""

    stream = response.extensions.get("network_stream")
    peer = stream.get_extra_info("server_addr") if stream is not None else None
    if peer and not _is_public(str(peer[0])):
        raise UrlNotAllowedError("The server resolved to a private address and was refused")


def download_pdf(url: str) -> tuple[str, str]:
    """Download ``url`` into the upload folder. Returns ``(saved_path, original_filename)``."""

    max_bytes = settings.max_upload_mb * 1024 * 1024
    current = validate_url(url)
    preparing = 0
    with client_factory() as client:
        for _ in range(MAX_REDIRECTS + MAX_PREPARING_RETRIES + 1):
            try:
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise DownloadFailedError("The server sent a redirect without a destination")
                        current = validate_url(urljoin(str(current), location))
                        continue
                    _check_connected_peer(response)
                    if response.status_code == 202 and preparing < MAX_PREPARING_RETRIES:
                        preparing += 1
                        response.read()
                        time.sleep(PREPARING_WAIT_SECONDS)
                        continue
                    if response.status_code != 200:
                        raise DownloadFailedError(f"The server answered {response.status_code} for that link")
                    declared = response.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > max_bytes:
                        raise TooLargeError(f"The file is larger than the {settings.max_upload_mb} MB limit")
                    return _save(response, current, max_bytes)
            except httpx.TimeoutException as exc:
                raise DownloadFailedError("The server took too long to respond") from exc
            except httpx.HTTPError as exc:
                logger.info("Import download failed: %s", exc)
                raise DownloadFailedError("Could not download that link") from exc
    raise DownloadFailedError("Too many redirects")


def _save(response: httpx.Response, url: httpx.URL, max_bytes: int) -> tuple[str, str]:
    name = _filename(response, url)
    folder = Path(settings.upload_dir).resolve() / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    destination = folder / name
    written = 0
    try:
        with open(destination, "wb") as out:
            for block in response.iter_bytes(1024 * 1024):
                if written == 0 and not block.startswith(b"%PDF-"):
                    raise NotAPdfError("That link is not a PDF file (it may be a web page; open it and copy the PDF link)")
                written += len(block)
                if written > max_bytes:
                    raise TooLargeError(f"The file is larger than the {settings.max_upload_mb} MB limit")
                out.write(block)
        if written == 0:
            raise NotAPdfError("The server returned an empty file")
    except Exception:
        destination.unlink(missing_ok=True)
        try:
            folder.rmdir()
        except OSError:
            pass
        raise
    return str(destination), name
