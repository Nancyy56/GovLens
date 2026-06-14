"""Unit tests for supersession engine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.models.documents import Document, DocumentRelationship
from app.models.enums import DocumentStatus, DocumentType, RelationshipType
from app.supersession import DatabaseSupersessionEngine, SupersessionResult
from app.supersession.schemas import DocumentReference


@pytest.fixture(name="db_session")
def db_session_fixture(tmp_path: Any) -> Session:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _make_document(session: Session, file_hash: str | None = None, **kwargs: Any) -> Document:
    if file_hash is None:
        import random
        file_hash = f"{random.randint(0, 0xFFFFFFFF):08x}"
    defaults: dict[str, Any] = dict(
        title="Doc",
        document_number="X",
        document_type=DocumentType.ORDER,
        issue_date=datetime.now(UTC).date(),
        file_name="x.pdf",
        file_hash=file_hash,
        status=DocumentStatus.ACTIVE,
    )
    defaults.update(kwargs)
    document = Document(**defaults)
    session.add(document)
    session.flush()
    session.refresh(document)
    return document


def _supersede(session: Session, source: Document, target: Document) -> DocumentRelationship:
    rel = DocumentRelationship(
        source_document_id=source.id,
        target_document_id=target.id,
        relationship_type=RelationshipType.SUPERSEDES,
    )
    session.add(rel)
    session.flush()
    session.refresh(rel)
    return rel


def test_single_supersession(db_session: Session) -> None:
    a = _make_document(db_session, document_number="A")
    b = _make_document(db_session, document_number="B")
    _supersede(db_session, source=a, target=b)

    engine = DatabaseSupersessionEngine(db_session)
    result = engine.check_document(b.id)

    assert result.is_superseded is True
    assert result.latest_document_id == a.id
    assert result.latest_document_number == "A"
    assert result.superseded_by_document_id == a.id
    assert result.superseded_by_document_number == "A"
    assert [ref.document_number for ref in result.supersession_chain] == ["B", "A"]


def test_chain_supersession(db_session: Session) -> None:
    a = _make_document(db_session, document_number="A")
    b = _make_document(db_session, document_number="B")
    c = _make_document(db_session, document_number="C")
    _supersede(db_session, source=a, target=b)
    _supersede(db_session, source=b, target=c)

    engine = DatabaseSupersessionEngine(db_session)
    result = engine.check_document(c.id)

    assert result.is_superseded is True
    assert result.latest_document_id == a.id
    assert result.latest_document_number == "A"
    assert [ref.document_number for ref in result.supersession_chain] == ["C", "B", "A"]


def test_active_document(db_session: Session) -> None:
    doc = _make_document(db_session, document_number="A")

    engine = DatabaseSupersessionEngine(db_session)
    result = engine.check_document(doc.id)

    assert result.is_superseded is False
    assert result.latest_document_id == doc.id
    assert result.latest_document_number == "A"
    assert result.superseded_by_document_id is None
    assert result.supersession_chain == [
        DocumentReference(document_id=doc.id, document_number="A")
    ]


def test_cycle_protection(db_session: Session) -> None:
    a = _make_document(db_session, document_number="A")
    b = _make_document(db_session, document_number="B")
    _supersede(db_session, source=a, target=b)
    _supersede(db_session, source=b, target=a)

    engine = DatabaseSupersessionEngine(db_session)
    result_a = engine.check_document(a.id)
    result_b = engine.check_document(b.id)

    assert [
        ref.document_number for ref in result_a.supersession_chain
    ] == ["A", "B"]
    assert [
        ref.document_number for ref in result_b.supersession_chain
    ] == ["B", "A"]


def test_missing_document(db_session: Session) -> None:
    missing_id = uuid.uuid4()

    engine = DatabaseSupersessionEngine(db_session)
    result = engine.check_document(missing_id)

    assert result.is_superseded is False
    assert result.latest_document_id == missing_id
    assert result.latest_document_number is None
    assert result.supersession_chain == []


def test_document_status_propagated(db_session: Session) -> None:
    doc = _make_document(db_session, document_number="X", status=DocumentStatus.SUPERSEDED)

    engine = DatabaseSupersessionEngine(db_session)
    result = engine.check_document(doc.id)

    assert result.status == DocumentStatus.SUPERSEDED
