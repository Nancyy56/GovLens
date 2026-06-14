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


class RelationshipType(StrEnum):
    """Directed lineage and citation edges between documents."""

    SUPERSEDES = "SUPERSEDES"
    AMENDS = "AMENDS"
    REFERENCES = "REFERENCES"
