"""Helpers for comparing document numbers written in different ways."""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")


def normalize_document_number(value: str) -> str:
    """Return a canonical form so "17/2024" and " 17 / 2024 ." compare equal."""

    return _WHITESPACE.sub("", value).strip(".,;:").casefold()
