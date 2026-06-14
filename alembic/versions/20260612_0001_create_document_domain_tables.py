"""create document domain tables

Revision ID: 20260612_0001
Revises:
Create Date: 2026-06-12 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260612_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("document_number", sa.String(length=128), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum(
                "UNKNOWN",
                "CIRCULAR",
                "NOTIFICATION",
                "ORDER",
                "GAZETTE",
                "POLICY",
                "ADVISORY",
                native_enum=False,
                length=32,
            ),
            nullable=False,
            comment="Stored as text so enum additions do not require PostgreSQL enum DDL.",
        ),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("department", sa.String(length=256), nullable=True),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "SUPERSEDED", "ARCHIVED", native_enum=False, length=32),
            nullable=False,
            comment="Application enum persisted as text for forward-compatible lifecycle values.",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_hash", name="uq_documents_file_hash"),
    )
    op.create_index("ix_documents_document_number", "documents", ["document_number"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_issue_date", "documents", ["issue_date"])

    op.create_table(
        "document_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "relationship_type",
            sa.Enum("SUPERSEDES", "AMENDS", "REFERENCES", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_document_id <> target_document_id", name="ck_document_relationships_not_self"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_document_id",
            "target_document_id",
            "relationship_type",
            name="uq_document_relationships_edge",
        ),
    )
    op.create_index(
        "ix_document_relationships_source_document_id",
        "document_relationships",
        ["source_document_id"],
    )
    op.create_index(
        "ix_document_relationships_target_document_id",
        "document_relationships",
        ["target_document_id"],
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("chunk_index >= 0", name="ck_document_chunks_chunk_index_nonnegative"),
        sa.CheckConstraint("page_number >= 1", name="ck_document_chunks_page_number_positive"),
        sa.CheckConstraint("token_count >= 0", name="ck_document_chunks_token_count_nonnegative"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_page_number", "document_chunks", ["page_number"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_page_number", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("ix_document_relationships_target_document_id", table_name="document_relationships")
    op.drop_index("ix_document_relationships_source_document_id", table_name="document_relationships")
    op.drop_table("document_relationships")

    op.drop_index("ix_documents_issue_date", table_name="documents")
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_document_number", table_name="documents")
    op.drop_table("documents")
