"""Guard for path-based ingestion requests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from app.services.exceptions import PathNotAllowedError


def ensure_path_allowed(file_path: str, allowed_dirs: Sequence[str]) -> str:
    """Resolve ``file_path`` and reject it unless it lies inside an allowed directory.

    Without this check, the ingest endpoint could be used to read any PDF the
    server process can access.
    """

    resolved = Path(file_path).resolve()
    for allowed in allowed_dirs:
        root = Path(allowed).resolve()
        if resolved == root or root in resolved.parents:
            return str(resolved)
    raise PathNotAllowedError(f"Path {file_path} is outside the allowed ingestion directories")
