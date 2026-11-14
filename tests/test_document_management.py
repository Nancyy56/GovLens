"""Document management and comparison services."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import DocumentStatus, RelationshipType
from app.schemas.processing import DocumentMention
from app.services.comparison import NO_DIFFERENCES_TEXT, ComparisonService
from app.services.documents import DocumentService
from app.services.exceptions import AmbiguousDocumentError, DocumentNotFoundError
from app.supersession.linker import DocumentRelationshipLinker


class FakeVectorStore:
    def __init__(self, stored: set[str] | None = None) -> None:
        self.stored = set(stored or [])
        self.deleted: list[str] = []

    def delete_document(self, document_id) -> None:
        self.deleted.append(str(document_id))
        self.stored.discard(str(document_id))

    def list_document_ids(self) -> set[str]:
        return set(self.stored)


class RecordingLLM:
    def __init__(self, answer: str = "- Rate rose from 5% to 12% [Base p.1] [Target p.1]") -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


def _supersede(session, new, old) -> None:
    DocumentRelationshipLinker(session).link_new_document(
        new,
        [DocumentMention(document_number=old.document_number, relationship_type=RelationshipType.SUPERSEDES)],
    )


def test_list_filters_and_counts_chunks(sqlite_session, make_document) -> None:
    make_document("1/2024", pages=["a", "b"], subject="GST rates")
    make_document("2/2024", pages=["c"], subject="Customs duty")
    service = DocumentService(sqlite_session, FakeVectorStore())

    page = service.list(search="gst")

    assert page.total == 1
    assert page.items[0].document_number == "1/2024"
    assert page.items[0].chunk_count == 2


def test_get_shows_relationships_both_ways(sqlite_session, make_document) -> None:
    old = make_document("12/2023")
    new = make_document("25/2024")
    _supersede(sqlite_session, new, old)
    service = DocumentService(sqlite_session, FakeVectorStore())

    new_detail = service.get(new.id)
    old_detail = service.get(old.id)

    assert [(r.relationship_type, r.document_number) for r in new_detail.outgoing] == [(RelationshipType.SUPERSEDES, "12/2023")]
    assert [r.document_number for r in old_detail.incoming] == ["25/2024"]
    assert old_detail.status == DocumentStatus.SUPERSEDED


def test_delete_removes_vectors_and_restores_superseded_document(sqlite_session, make_document) -> None:
    old = make_document("12/2023")
    new = make_document("25/2024", pages=["text"])
    _supersede(sqlite_session, new, old)
    sqlite_session.commit()
    store = FakeVectorStore({str(new.id)})

    DocumentService(sqlite_session, store).delete(new.id)

    assert store.deleted == [str(new.id)]
    sqlite_session.refresh(old)
    assert old.status == DocumentStatus.ACTIVE
    with pytest.raises(DocumentNotFoundError):
        DocumentService(sqlite_session, store).get(new.id)


def test_manual_relationship_add_and_remove(sqlite_session, make_document) -> None:
    old = make_document("1/2020")
    new = make_document("2/2021")
    service = DocumentService(sqlite_session, FakeVectorStore())

    relationship = service.add_relationship(new.id, old.id, RelationshipType.SUPERSEDES)
    assert service.get(old.id).status == DocumentStatus.SUPERSEDED
    # Adding the same link twice is idempotent.
    assert service.add_relationship(new.id, old.id, RelationshipType.SUPERSEDES).id == relationship.id

    service.delete_relationship(relationship.id)
    assert service.get(old.id).status == DocumentStatus.ACTIVE


def test_self_relationship_rejected(sqlite_session, make_document) -> None:
    doc = make_document("1/2020")
    with pytest.raises(ValueError):
        DocumentService(sqlite_session, FakeVectorStore()).add_relationship(doc.id, doc.id, RelationshipType.AMENDS)


def test_resolve_by_id_number_and_ambiguity(sqlite_session, make_document) -> None:
    doc = make_document("17/2024")
    make_document("5/2024")
    make_document("5/2024")
    service = DocumentService(sqlite_session, FakeVectorStore())

    assert service.resolve(str(doc.id)).id == doc.id
    assert service.resolve(" 17/2024 ").id == doc.id
    with pytest.raises(AmbiguousDocumentError):
        service.resolve("5/2024")
    with pytest.raises(DocumentNotFoundError):
        service.resolve("99/1999")


def test_reconcile_removes_orphans_and_reports_missing(sqlite_session, make_document) -> None:
    indexed = make_document("1/2024", pages=["a"])
    unindexed = make_document("2/2024", pages=["b"])
    orphan = str(uuid.uuid4())
    store = FakeVectorStore({str(indexed.id), orphan})

    report = DocumentService(sqlite_session, store).reconcile()

    assert report.orphaned_vector_documents_removed == [orphan]
    assert report.documents_missing_vectors == [unindexed.id]


def _comparison(session, llm=None) -> ComparisonService:
    return ComparisonService(session, DocumentService(session, FakeVectorStore()), llm)


def test_compare_reports_changes_relationship_and_summary(sqlite_session, make_document) -> None:
    old = make_document("12/2023", pages=["The GST rate is 5 percent. Returns are filed monthly."])
    new = make_document("25/2024", pages=["The GST rate is 12 percent. Returns are filed monthly."])
    _supersede(sqlite_session, new, old)
    llm = RecordingLLM()

    result = _comparison(sqlite_session, llm).compare("12/2023", "25/2024", focus="rate")

    assert result.modified == 1 and result.total_changes == 1
    assert result.relationship == "target SUPERSEDES base"
    assert result.summary_markdown == llm.answer
    assert "Base p.1: The GST rate is 5 percent." in llm.prompts[0]
    assert "Focus the summary on: rate" in llm.prompts[0]


def test_compare_identical_documents_skips_llm(sqlite_session, make_document) -> None:
    make_document("1/2024", pages=["Same text."])
    make_document("2/2024", pages=["Same text."])
    llm = RecordingLLM()

    result = _comparison(sqlite_session, llm).compare("1/2024", "2/2024")

    assert result.total_changes == 0
    assert result.summary_markdown == NO_DIFFERENCES_TEXT
    assert llm.prompts == []


def test_compare_same_document_rejected(sqlite_session, make_document) -> None:
    make_document("1/2024", pages=["x"])
    with pytest.raises(ValueError):
        _comparison(sqlite_session).compare("1/2024", "1/2024")


class RecordingVectorStore(FakeVectorStore):
    def __init__(self, stored=None) -> None:
        super().__init__(stored)
        self.upserted = []

    def upsert(self, chunks) -> None:
        self.upserted.extend(chunks)
        for chunk in chunks:
            self.stored.add(str(chunk.document_id))


class FakeEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2] for _ in texts]


def test_reconcile_rebuilds_missing_vectors_from_chunks(sqlite_session, make_document) -> None:
    doc = make_document("2/2024", pages=["page one", "page two"])
    store = RecordingVectorStore()

    report = DocumentService(sqlite_session, store, embedding_provider=FakeEmbedder()).reconcile()

    assert report.documents_repaired == [doc.id]
    assert [(c.page_number, c.chunk_text) for c in store.upserted] == [(1, "page one"), (2, "page two")]
    assert store.upserted[0].document_number == "2/2024"
