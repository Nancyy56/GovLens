"""Saved documents with private notes."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.documents import Bookmark, Document
from app.models.enums import DocumentStatus, DocumentType
from app.services.exceptions import DocumentNotFoundError

MAX_NOTE_CHARS = 4000


class BookmarkRead(BaseModel):
    document_id: uuid.UUID
    document_number: str
    title: str
    document_type: DocumentType
    status: DocumentStatus
    note: str
    created_at: datetime
    updated_at: datetime


class BookmarkService:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _read(bookmark: Bookmark, document: Document) -> BookmarkRead:
        return BookmarkRead(
            document_id=document.id, document_number=document.document_number, title=document.title,
            document_type=document.document_type, status=document.status, note=bookmark.note,
            created_at=bookmark.created_at, updated_at=bookmark.updated_at,
        )

    def list(self, username: str) -> list[BookmarkRead]:
        rows = self.session.execute(
            select(Bookmark, Document).join(Document, Document.id == Bookmark.document_id)
            .where(Bookmark.username == username).order_by(Bookmark.updated_at.desc())
        ).all()
        return [self._read(b, d) for b, d in rows]

    def save(self, username: str, document_id: uuid.UUID, note: str | None) -> BookmarkRead:
        document = self.session.get(Document, document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        bookmark = self.session.scalar(select(Bookmark).where(Bookmark.username == username, Bookmark.document_id == document_id))
        if bookmark is None:
            bookmark = Bookmark(username=username, document_id=document_id, note="")
            self.session.add(bookmark)
        if note is not None:
            bookmark.note = note.strip()[:MAX_NOTE_CHARS]
        self.session.commit()
        self.session.refresh(bookmark)
        return self._read(bookmark, document)

    def remove(self, username: str, document_id: uuid.UUID) -> bool:
        bookmark = self.session.scalar(select(Bookmark).where(Bookmark.username == username, Bookmark.document_id == document_id))
        if bookmark is None:
            return False
        self.session.delete(bookmark)
        self.session.commit()
        return True
