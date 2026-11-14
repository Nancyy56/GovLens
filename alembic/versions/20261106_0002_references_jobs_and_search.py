"""document references, ingestion jobs, nullable issue date, chunk full-text index

Revision ID: 20261106_0002
Revises: 20260612_0001
Create Date: 2026-11-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261106_0002"
down_revision: str | None = "20260612_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOCUMENT_TYPES = ("UNKNOWN", "CIRCULAR", "NOTIFICATION", "ORDER", "GAZETTE", "POLICY", "ADVISORY")
RELATIONSHIP_TYPES = ("SUPERSEDES", "AMENDS", "REFERENCES")
JOB_STATUSES = ("PENDING", "RUNNING", "SUCCEEDED", "FAILED")


def upgrade() -> None:
    # Documents without a detectable issue date are stored with NULL instead
    # of a fabricated "today" value.
    op.alter_column("documents", "issue_date", existing_type=sa.Date(), nullable=True)

    op.create_table(
        "document_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referenced_number", sa.String(length=128), nullable=False),
        sa.Column("referenced_number_raw", sa.String(length=128), nullable=False),
        sa.Column("referenced_type", sa.Enum(*DOCUMENT_TYPES, native_enum=False, length=32), nullable=True),
        sa.Column("relationship_type", sa.Enum(*RELATIONSHIP_TYPES, native_enum=False, length=32), nullable=False),
        sa.Column("resolved_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_document_id",
            "referenced_number",
            "relationship_type",
            name="uq_document_references_mention",
        ),
    )
    op.create_index("ix_document_references_referenced_number", "document_references", ["referenced_number"])
    op.create_index("ix_document_references_source_document_id", "document_references", ["source_document_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum(*JOB_STATUSES, native_enum=False, length=32), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])

    # Full-text index backing the keyword half of hybrid retrieval.
    op.execute(
        "CREATE INDEX ix_document_chunks_fts ON document_chunks "
        "USING gin (to_tsvector('english', chunk_text))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_fts")
    op.drop_index("ix_ingestion_jobs_status", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_document_references_source_document_id", table_name="document_references")
    op.drop_index("ix_document_references_referenced_number", table_name="document_references")
    op.drop_table("document_references")
    op.execute("UPDATE documents SET issue_date = CURRENT_DATE WHERE issue_date IS NULL")
    op.alter_column("documents", "issue_date", existing_type=sa.Date(), nullable=False)
