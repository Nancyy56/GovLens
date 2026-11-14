"""users and sessions, durable job retries, shared rate limits, relationship origin, stored search vector

Revision ID: 20261106_0003
Revises: 20261106_0002
Create Date: 2026-11-06 01:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261106_0003"
down_revision: str | None = "20261106_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role", sa.Enum("VIEWER", "EDITOR", "ADMIN", native_enum=False, length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "auth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
    )
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])

    op.create_table(
        "rate_limit_windows",
        sa.Column("identity", sa.String(length=128), nullable=False),
        sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("identity", "window_start"),
    )

    op.add_column("ingestion_jobs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ingestion_jobs", sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_ingestion_jobs_submitted_by", "ingestion_jobs", "users", ["submitted_by"], ["id"], ondelete="SET NULL"
    )

    op.add_column(
        "document_relationships",
        sa.Column("origin", sa.Enum("AUTO", "MANUAL", native_enum=False, length=16), nullable=False, server_default="AUTO"),
    )

    # Store the full-text vector instead of recomputing it for every row at query time.
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_fts")
    op.execute(
        "ALTER TABLE document_chunks ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED"
    )
    op.execute("CREATE INDEX ix_document_chunks_search_vector ON document_chunks USING gin (search_vector)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_vector")
    op.execute(
        "CREATE INDEX ix_document_chunks_fts ON document_chunks USING gin (to_tsvector('english', chunk_text))"
    )
    op.drop_column("document_relationships", "origin")
    op.drop_constraint("fk_ingestion_jobs_submitted_by", "ingestion_jobs", type_="foreignkey")
    op.drop_column("ingestion_jobs", "submitted_by")
    op.drop_column("ingestion_jobs", "attempts")
    op.drop_table("rate_limit_windows")
    op.drop_index("ix_auth_tokens_user_id", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_table("users")
