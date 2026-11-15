"""Bookmarks with notes, the audit log, and serving the original PDF."""

from __future__ import annotations

import uuid

import pytest

from app.services.audit import AuditService
from app.services.bookmarks import BookmarkService
from app.services.documents import DocumentService
from app.services.exceptions import DocumentNotFoundError


def test_bookmarks_are_private_and_notes_can_be_edited(sqlite_session, make_document) -> None:
    doc = make_document("12/2023")
    service = BookmarkService(sqlite_session)

    saved = service.save("alice", doc.id, "Check the penalty clause")
    assert (saved.document_number, saved.note) == ("12/2023", "Check the penalty clause")

    # Saving again without a note keeps the existing one; a new note replaces it.
    assert service.save("alice", doc.id, None).note == "Check the penalty clause"
    assert service.save("alice", doc.id, "  Updated  ").note == "Updated"
    assert len(service.list("alice")) == 1

    assert service.list("bob") == []
    assert service.remove("bob", doc.id) is False
    assert service.remove("alice", doc.id) is True
    assert service.list("alice") == []


def test_bookmarking_an_unknown_document_fails(sqlite_session) -> None:
    with pytest.raises(DocumentNotFoundError):
        BookmarkService(sqlite_session).save("alice", uuid.uuid4(), None)


def test_bookmarks_disappear_when_the_document_is_deleted(sqlite_session, make_document) -> None:
    doc = make_document("X/1")
    service = BookmarkService(sqlite_session)
    service.save("alice", doc.id, "n")
    sqlite_session.delete(doc)
    sqlite_session.commit()
    assert service.list("alice") == []


def test_audit_log_filters_and_lists_newest_first(sqlite_session) -> None:
    service = AuditService(sqlite_session)
    service.add("admin", "auth.login", target=None, detail=None, ip="10.0.0.1")
    service.add("bob", "document.delete", target="12/2023", detail="GST notification", ip=None)
    service.add("admin", "user.create", target="carol", detail="role VIEWER", ip=None)

    page = service.list(limit=10, offset=0, action=None, search=None)
    assert page.total == 3
    assert page.actions == ["auth.login", "document.delete", "user.create"]
    assert service.list(limit=10, offset=0, action="document.delete", search=None).items[0].target == "12/2023"
    assert service.list(limit=10, offset=0, action=None, search="carol").total == 1
    assert service.list(limit=2, offset=0, action=None, search=None).total == 3  # total ignores paging


def test_original_pdf_is_only_served_from_allowed_folders(sqlite_session, make_document, tmp_path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    inside = uploads / "a.pdf"
    inside.write_bytes(b"%PDF-1.7 test")
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"%PDF-1.7 secret")

    ok = make_document("A/1", source_url=str(inside))
    escaped = make_document("B/1", source_url=str(outside))
    missing = make_document("C/1", source_url=str(uploads / "gone.pdf"))
    unset = make_document("D/1", source_url=None)
    traversal = make_document("E/1", source_url=str(uploads / ".." / "secret.pdf"))

    service = DocumentService(sqlite_session, vector_store=None)
    allowed = [str(uploads)]
    assert service.source_file(ok.id, allowed) == str(inside.resolve())
    for doc in (escaped, missing, unset, traversal):
        assert service.source_file(doc.id, allowed) is None
