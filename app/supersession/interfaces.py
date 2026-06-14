"""Protocol for supersession analysis boundary."""

from __future__ import annotations

from typing import Protocol

from app.supersession.schemas import SupersessionResult


class SupersessionEngine(Protocol):
    """Contract for computing document supersession lineage."""

    def check_document(self, document_id: "uuid.UUID") -> SupersessionResult:
        """Return the supersession analysis for the supplied document id."""
        ...
