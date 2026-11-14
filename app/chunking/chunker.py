"""Deterministic document chunker implementation."""

from __future__ import annotations

import re
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
    5. Tokens are counted with ``token_counter`` (the embedding model's
       tokenizer in the pipeline; whitespace words by default).
    """

    def __init__(
        self,
        min_tokens: int = 500,
        max_tokens: int = 1000,
        overlap_sentences: int = 1,
        token_counter=None,
    ) -> None:
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_sentences = overlap_sentences
        self.count_tokens = token_counter or (lambda text: len(text.split()))
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
        """Split text into sentences, marking ones followed by a line break.

        A trailing "\n" is kept on sentences that ended a line, so joining
        them back preserves headings and list items as separate lines.
        """
        parts: list[str] = []
        for match in self._sentence_pattern.finditer(text):
            sentence = match.group(0).strip()
            if sentence:
                ends_line = match.group(0).rstrip(" \t").endswith("\n")
                parts.append(sentence + "\n" if ends_line else sentence)
        if not parts:
            parts = [line.strip() + "\n" for line in text.splitlines() if line.strip()]
        return parts

    @staticmethod
    def _join(sentences: list[str]) -> str:
        joined = ""
        for sentence in sentences:
            if joined and not joined.endswith("\n"):
                joined += " "
            joined += sentence
        return joined

    def _group_sentences(self, sentences: list[str]) -> list[str]:
        groups: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            tokens = self.count_tokens(sentence)
            if current and current_tokens + tokens > self.max_tokens:
                groups.append(self._join(current))
                if self.overlap_sentences > 0:
                    overlap = current[-self.overlap_sentences:]
                    current = overlap[:]
                    current_tokens = sum(self.count_tokens(s) for s in current)
                else:
                    current = []
                    current_tokens = 0

            current.append(sentence)
            current_tokens += tokens

        if current:
            groups.append(self._join(current))

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
                    estimated_token_count=self.count_tokens(stripped),
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
