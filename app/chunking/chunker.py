"""Deterministic document chunker implementation."""

from __future__ import annotations

import re
from typing import List, Optional

from app.chunking.interfaces import DocumentChunker
from app.chunking.schemas import DocumentChunkData
from app.models.enums import DocumentType
from app.schemas.processing import DocumentMetadata, PageContent, RawDocument


class RuleBasedDocumentChunker(DocumentChunker):
    """Split documents into citation-preserving chunks using deterministic rules.

    Rules:
    1. Page boundaries are never crossed.
    2. A single page yields one or more chunks depending on token count.
    3. Chunk ordering is deterministic: page order then chunk order within page.
    4. Empty or whitespace-only chunks are discarded.
    5. Token estimation uses word count (`len(text.split())`).
    """

    def __init__(
        self,
        min_tokens: int = 500,
        max_tokens: int = 1000,
        overlap_sentences: int = 1,
    ) -> None:
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_sentences = overlap_sentences
        self._sentence_pattern = re.compile(r"[^.!?\n]+[.!?\n]+")

    def chunk(
        self,
        raw_document: RawDocument,
        metadata: DocumentMetadata | None = None,
    ) -> list[DocumentChunkData]:
        chunks: list[DocumentChunkData] = []
        doc_type = self._doc_type(metadata)
        doc_number = self._doc_number(metadata)
        document_id = raw_document.document_id

        for page in raw_document.pages:
            page_chunks = self._chunk_page(
                page,
                document_id,
                doc_type,
                doc_number,
            )
            chunks.extend(page_chunks)

        return chunks

    def _chunk_page(
        self,
        page: PageContent,
        document_id: "uuid.UUID",
        doc_type: DocumentType | None,
        doc_number: str | None,
    ) -> list[DocumentChunkData]:
        text = page.text.strip()
        if not text:
            return []

        sentences = self._split_sentences(text)
        if not sentences:
            return []

        groups = self._group_sentences(sentences)
        return self._build_chunks(groups, document_id, page.page_number, doc_type, doc_number)

    def _split_sentences(self, text: str) -> list[str]:
        parts = [m.group(0).strip() for m in self._sentence_pattern.finditer(text)]
        filtered = [p for p in parts if p]
        if not filtered:
            filtered = [line.strip() for line in text.splitlines() if line.strip()]
        return filtered

    def _group_sentences(self, sentences: list[str]) -> list[str]:
        groups: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            tokens = len(sentence.split())
            if current and current_tokens + tokens > self.max_tokens:
                groups.append(" ".join(current))
                if self.overlap_sentences > 0:
                    overlap = current[-self.overlap_sentences:]
                    current = overlap[:]
                    current_tokens = sum(len(s.split()) for s in current)
                else:
                    current = []
                    current_tokens = 0

            current.append(sentence)
            current_tokens += tokens

        if current:
            groups.append(" ".join(current))

        return groups

    def _build_chunks(
        self,
        texts: list[str],
        document_id: "uuid.UUID",
        page_number: int,
        doc_type: DocumentType | None,
        doc_number: str | None,
    ) -> list[DocumentChunkData]:
        chunks: list[DocumentChunkData] = []
        for index, text in enumerate(texts):
            stripped = text.strip()
            if not stripped:
                continue
            chunks.append(
                DocumentChunkData(
                    document_id=document_id,
                    document_number=doc_number,
                    document_type=doc_type,
                    page_number=page_number,
                    chunk_index=index,
                    chunk_text=stripped,
                    estimated_token_count=len(stripped.split()),
                )
            )
        return chunks

    @staticmethod
    def _doc_type(metadata: DocumentMetadata | None) -> DocumentType | None:
        if metadata is None:
            return None
        return metadata.document_type

    @staticmethod
    def _doc_number(metadata: DocumentMetadata | None) -> str | None:
        if metadata is None:
            return None
        return metadata.document_number
