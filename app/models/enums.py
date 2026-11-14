"""Domain enums persisted by SQLAlchemy and reused by Pydantic schemas."""

from enum import StrEnum


class DocumentStatus(StrEnum):
    """Lifecycle state for a government document record."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class DocumentType(StrEnum):
    """Coarse document classes used before downstream classification matures."""

    UNKNOWN = "UNKNOWN"
    CIRCULAR = "CIRCULAR"
    NOTIFICATION = "NOTIFICATION"
    ORDER = "ORDER"
    GAZETTE = "GAZETTE"
    POLICY = "POLICY"
    ADVISORY = "ADVISORY"
    REPORT = "REPORT"


class RelationshipType(StrEnum):
    """Directed lineage and citation edges between documents."""

    SUPERSEDES = "SUPERSEDES"
    AMENDS = "AMENDS"
    REFERENCES = "REFERENCES"


class IngestionJobStatus(StrEnum):
    """Lifecycle state for a background ingestion job."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class UserRole(StrEnum):
    """Access level. Each role includes the permissions of the ones below it."""

    VIEWER = "VIEWER"  # ask questions, search, compare, browse documents
    EDITOR = "EDITOR"  # + ingest, re-ingest, delete documents, edit relationships
    ADMIN = "ADMIN"  # + manage users, reconcile stores, metrics

    @property
    def rank(self) -> int:
        return {"VIEWER": 0, "EDITOR": 1, "ADMIN": 2}[self.value]


class RelationshipOrigin(StrEnum):
    """Whether a relationship was detected from text or added by a person."""

    AUTO = "AUTO"
    MANUAL = "MANUAL"
