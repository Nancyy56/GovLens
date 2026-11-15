"""Persisting detected mentions as relationship edges."""

from __future__ import annotations

from sqlalchemy import select

from app.models.documents import DocumentReference, DocumentRelationship
from app.models.enums import DocumentStatus, DocumentType, RelationshipType
from app.schemas.processing import DocumentMention
from app.supersession.engine import DatabaseSupersessionEngine
from app.supersession.linker import DocumentRelationshipLinker


def _mention(number: str, relationship: RelationshipType, doc_type=DocumentType.NOTIFICATION) -> DocumentMention:
    return DocumentMention(document_number=number, document_type=doc_type, relationship_type=relationship)


def test_links_to_existing_document_and_marks_it_superseded(sqlite_session, make_document) -> None:
    old = make_document("12/2023")
    new = make_document("25/2024")

    report = DocumentRelationshipLinker(sqlite_session).link_new_document(
        new, [_mention("12/2023", RelationshipType.SUPERSEDES)]
    )

    assert [(l.source_document_number, l.relationship_type, l.target_document_number) for l in report.created] == [
        ("25/2024", RelationshipType.SUPERSEDES, "12/2023")
    ]
    assert old.status == DocumentStatus.SUPERSEDED
    assert report.pending_references == []
    result = DatabaseSupersessionEngine(sqlite_session).check_document(old.id)
    assert result.is_superseded and result.latest_document_number == "25/2024"


def test_reference_resolves_when_target_arrives_later(sqlite_session, make_document) -> None:
    linker = DocumentRelationshipLinker(sqlite_session)
    new = make_document("25/2024")
    first = linker.link_new_document(new, [_mention("12/2023", RelationshipType.SUPERSEDES)])
    assert first.created == [] and first.pending_references == ["12/2023"]

    old = make_document("12/2023")
    second = linker.link_new_document(old, [])

    assert [(l.source_document_id, l.target_document_id) for l in second.created] == [(new.id, old.id)]
    assert old.status == DocumentStatus.SUPERSEDED
    reference = sqlite_session.scalars(select(DocumentReference)).one()
    assert reference.resolved_document_id == old.id


def test_number_matching_ignores_case_and_spacing(sqlite_session, make_document) -> None:
    make_document("04/2025-GST", document_type=DocumentType.CIRCULAR)
    new = make_document("09/2025-GST", document_type=DocumentType.CIRCULAR)

    report = DocumentRelationshipLinker(sqlite_session).link_new_document(
        new, [_mention("04/2025-gst", RelationshipType.AMENDS, DocumentType.CIRCULAR)]
    )

    assert len(report.created) == 1


def test_type_mismatch_is_not_linked(sqlite_session, make_document) -> None:
    make_document("5/2024", document_type=DocumentType.ORDER)
    new = make_document("6/2024")

    report = DocumentRelationshipLinker(sqlite_session).link_new_document(
        new, [_mention("5/2024", RelationshipType.SUPERSEDES, DocumentType.CIRCULAR)]
    )

    assert report.created == []
    assert report.pending_references == ["5/2024"]


def test_references_do_not_change_status(sqlite_session, make_document) -> None:
    old = make_document("1/2020")
    new = make_document("2/2020")

    DocumentRelationshipLinker(sqlite_session).link_new_document(new, [_mention("1/2020", RelationshipType.REFERENCES)])

    assert old.status == DocumentStatus.ACTIVE
    edge = sqlite_session.scalars(select(DocumentRelationship)).one()
    assert edge.relationship_type == RelationshipType.REFERENCES


def test_recompute_status_restores_active(sqlite_session, make_document) -> None:
    old = make_document("12/2023")
    new = make_document("25/2024")
    linker = DocumentRelationshipLinker(sqlite_session)
    linker.link_new_document(new, [_mention("12/2023", RelationshipType.SUPERSEDES)])

    sqlite_session.delete(new)
    sqlite_session.flush()
    linker.recompute_status(old.id)

    assert old.status == DocumentStatus.ACTIVE
