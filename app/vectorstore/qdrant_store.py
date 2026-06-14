"""Qdrant vector store implementation."""

from __future__ import annotations

import logging
import uuid
from typing import Sequence

from app.vectorstore.interfaces import VectorStore
from app.vectorstore.schemas import EmbeddedChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "government_documents"


class QdrantVectorStore:
    """Persist embedded chunks in Qdrant with full payload metadata.

    The collection is created on first use if it does not already exist.
    Vector dimension is inferred from the first batch of embeddings so callers
    do not need to know the model output size ahead of time.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection: str = COLLECTION_NAME,
        api_key: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.collection = collection
        self.api_key = api_key
        self._client = None
        self._vector_size: int | None = None

    def upsert(self, chunks: Sequence[EmbeddedChunk]) -> None:
        if not chunks:
            return

        client = self._get_client()
        vectors = [chunk.embedding for chunk in chunks]

        if self._vector_size is None:
            self._vector_size = len(vectors[0])
            self._ensure_collection(client)

        points = []
        for chunk, vector in zip(chunks, vectors):
            point_id = str(uuid.uuid5(chunk.document_id, f"{chunk.page_number}:{chunk.chunk_index}"))
            payload = self._build_payload(chunk)
            points.append({"id": point_id, "vector": vector, "payload": payload})

        client.upsert(collection_name=self.collection, points=points)
    def search(
        self,
        query_vector: Sequence[float],
        limit: int = 10,
        filters: dict | None = None,
    ) -> list[dict]:
        client = self._get_client()

        qdrant_filters = (
            self._build_filters(filters)
            if filters
            else None
        )

        response = client.query_points(
            collection_name=self.collection,
            query=list(query_vector),
            limit=limit,
            query_filter=qdrant_filters,
            with_payload=True,
            with_vectors=False,
        )

        return [
            {
                "id": point.id,
                "score": point.score,
                "payload": point.payload or {},
            }
            for point in response.points
        ]

    def _get_client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as exc:
                raise RuntimeError(
                    "qdrant-client is required for QdrantVectorStore. "
                    "Install it with: pip install qdrant-client"
                ) from exc
            host=self.host
            self._client = QdrantClient(url=f"http://{self.host}:{self.port}")
        return self._client

    def _ensure_collection(self, client) -> None:
        from qdrant_client.http.models import Distance, VectorParams

        existing = [c.name for c in client.get_collections().collections]
        if self.collection not in existing:
            client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self._vector_size, distance=Distance.COSINE),
            )

    @staticmethod
    def _build_payload(chunk: EmbeddedChunk) -> dict:
        return {
            "document_id": str(chunk.document_id),
            "document_number": chunk.document_number,
            "document_type": chunk.document_type.value if chunk.document_type else None,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "chunk_text": chunk.chunk_text,
            "issue_date": chunk.metadata.get("issue_date") if chunk.metadata else None,
            **(chunk.metadata or {}),
        }

    @staticmethod
    def _build_filters(filters: dict) -> dict:
        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append({"key": key, "match": {"any": value}})
            else:
                conditions.append({"key": key, "match": {"value": value}})
        return {"must": conditions}
