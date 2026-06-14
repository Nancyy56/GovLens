"""Repository classes for basic document-domain CRUD operations."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.documents import Document, DocumentChunk, DocumentRelationship
from app.schemas import DocumentChunkCreate, DocumentCreate, DocumentRelationshipCreate

ModelT = TypeVar("ModelT", Document, DocumentChunk, DocumentRelationship)
CreateSchemaT = TypeVar("CreateSchemaT", DocumentCreate, DocumentChunkCreate, DocumentRelationshipCreate)


def _to_values(data: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    """Normalize schema or mapping input without adding domain behavior."""

    if isinstance(data, BaseModel):
        return data.model_dump()
    return dict(data)


class _CrudRepository(Generic[ModelT, CreateSchemaT]):
    """Small transaction-neutral CRUD base shared by concrete repositories."""

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, data: CreateSchemaT | Mapping[str, Any]) -> ModelT:
        item = self.model(**_to_values(data))
        self.session.add(item)
        self.session.flush()
        self.session.refresh(item)
        return item

    def get(self, item_id: uuid.UUID) -> ModelT | None:
        return self.session.get(self.model, item_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        statement: Select[tuple[ModelT]] = select(self.model).limit(limit).offset(offset)
        return self.session.scalars(statement).all()

    def update(self, item_id: uuid.UUID, values: Mapping[str, Any]) -> ModelT | None:
        item = self.get(item_id)
        if item is None:
            return None

        for field_name, value in values.items():
            setattr(item, field_name, value)

        self.session.flush()
        self.session.refresh(item)
        return item

    def delete(self, item_id: uuid.UUID) -> bool:
        item = self.get(item_id)
        if item is None:
            return False

        self.session.delete(item)
        self.session.flush()
        return True


class DocumentRepository(_CrudRepository[Document, DocumentCreate]):
    """CRUD access for document metadata rows."""

    model = Document


class DocumentChunkRepository(_CrudRepository[DocumentChunk, DocumentChunkCreate]):
    """CRUD access for persisted chunk text rows."""

    model = DocumentChunk


class DocumentRelationshipRepository(_CrudRepository[DocumentRelationship, DocumentRelationshipCreate]):
    """CRUD access for directed document relationship rows."""

    model = DocumentRelationship
