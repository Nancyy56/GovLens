"""Shared fixtures: an isolated SQLite database with the GovLens schema."""

from __future__ import annotations

import itertools
from datetime import date
from typing import Any

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.models.documents import Document, DocumentChunk
from app.models.enums import DocumentStatus, DocumentType

_hash_counter = itertools.count()


@pytest.fixture
def sqlite_session_factory(tmp_path: Any):
    engine = create_engine(f"sqlite:///{tmp_path / 'govlens.db'}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        # PostgreSQL enforces ON DELETE CASCADE / SET NULL; SQLite only does with this pragma.
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


@pytest.fixture
def sqlite_session(sqlite_session_factory) -> Session:
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_document(sqlite_session: Session):
    """Create a document (optionally with page texts stored as chunks)."""

    def _make(
        document_number: str = "X",
        document_type: DocumentType = DocumentType.NOTIFICATION,
        pages: list[str] | None = None,
        **kwargs: Any,
    ) -> Document:
        values: dict[str, Any] = dict(
            title=f"Doc {document_number}",
            document_number=document_number,
            document_type=document_type,
            issue_date=date(2024, 1, 1),
            file_name=f"{document_number.replace('/', '-')}.pdf",
            file_hash=f"hash-{next(_hash_counter)}",
            status=DocumentStatus.ACTIVE,
        )
        values.update(kwargs)
        document = Document(**values)
        sqlite_session.add(document)
        sqlite_session.flush()
        for page_number, text in enumerate(pages or [], start=1):
            sqlite_session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=0,
                    page_number=page_number,
                    chunk_text=text,
                    token_count=len(text.split()),
                )
            )
        sqlite_session.flush()
        return document

    return _make
