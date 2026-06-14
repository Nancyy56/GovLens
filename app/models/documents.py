"""SQLAlchemy models for the core GovLens document domain."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from sqlalchemy import CheckConstraint, Date, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import DocumentStatus, DocumentType, RelationshipType

class Document(Base):
    """Canonical metadata row for an ingested government document."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("file_hash", name="uq_documents_file_hash"),
        Index("ix_documents_document_number", "document_number"),
        Index("ix_documents_document_type", "document_type"),
        Index("ix_documents_issue_date", "issue_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    document_number: Mapped[str] = mapped_column(String(128), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, native_enum=False, length=32, validate_strings=True),
        nullable=False,
        default=DocumentType.UNKNOWN,
        comment="Stored as text so enum additions do not require PostgreSQL enum DDL.",
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    department: Mapped[str | None] = mapped_column(String(256), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, native_enum=False, length=32, validate_strings=True),
        nullable=False,
        default=DocumentStatus.ACTIVE,
        comment="Application enum persisted as text for forward-compatible lifecycle values.",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    outgoing_relationships: Mapped[list[DocumentRelationship]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentRelationship.source_document_id",
        passive_deletes=True,
    )
    incoming_relationships: Mapped[list[DocumentRelationship]] = relationship(
        back_populates="target_document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentRelationship.target_document_id",
        passive_deletes=True,
    )


class DocumentRelationship(Base):
    """Directed relationship from one document to another.

    For example, source A with relationship_type SUPERSEDES targeting B means
    document A supersedes document B.
    """

    __tablename__ = "document_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "target_document_id",
            "relationship_type",
            name="uq_document_relationships_edge",
        ),
        CheckConstraint("source_document_id <> target_document_id", name="ck_document_relationships_not_self"),
        Index("ix_document_relationships_source_document_id", "source_document_id"),
        Index("ix_document_relationships_target_document_id", "target_document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        SQLEnum(RelationshipType, native_enum=False, length=32, validate_strings=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    source_document: Mapped[Document] = relationship(
        back_populates="outgoing_relationships",
        foreign_keys=[source_document_id],
    )
    target_document: Mapped[Document] = relationship(
        back_populates="incoming_relationships",
        foreign_keys=[target_document_id],
    )


class DocumentChunk(Base):
    """Searchable text unit belonging to a document.

    Embeddings intentionally stay out of PostgreSQL; vector storage is reserved
    for Qdrant so this table remains the relational source of chunk text.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index_nonnegative"),
        CheckConstraint("page_number >= 1", name="ck_document_chunks_page_number_positive"),
        CheckConstraint("token_count >= 0", name="ck_document_chunks_token_count_nonnegative"),
        Index("ix_document_chunks_document_id", "document_id"),
        Index("ix_document_chunks_page_number", "page_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="chunks")
