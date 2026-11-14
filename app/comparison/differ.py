"""Sentence-level diff between two documents."""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.text import split_sentences
from app.schemas.processing import PageContent

_WHITESPACE = re.compile(r"\s+")
# Below this similarity, a "replaced" sentence pair is reported as one
# removal plus one addition instead of a modification.
_MODIFIED_MIN_SIMILARITY = 0.4
_MIN_SENTENCE_CHARS = 3


class ChangeType(StrEnum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"


class TextChange(BaseModel):
    change_type: ChangeType
    base_text: str | None = None
    base_page: int | None = None
    target_text: str | None = None
    target_page: int | None = None
    similarity: float | None = None


class DocumentDiff(BaseModel):
    changes: list[TextChange] = Field(default_factory=list)
    base_sentence_count: int = 0
    target_sentence_count: int = 0
    unchanged_sentence_count: int = 0


class _Sentence(BaseModel):
    page: int
    text: str
    key: str


class DocumentDiffer:
    """Compare two documents sentence by sentence.

    Sentences are compared after normalizing case and whitespace, so layout
    differences between PDFs do not show up as changes. Each change keeps the
    page number it came from in both documents for citation.
    """

    def diff(self, base_pages: Sequence[PageContent], target_pages: Sequence[PageContent]) -> DocumentDiff:
        base = self._sentences(base_pages)
        target = self._sentences(target_pages)
        matcher = SequenceMatcher(None, [s.key for s in base], [s.key for s in target], autojunk=False)

        changes: list[TextChange] = []
        unchanged = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                unchanged += i2 - i1
            elif tag == "delete":
                changes.extend(self._removed(s) for s in base[i1:i2])
            elif tag == "insert":
                changes.extend(self._added(s) for s in target[j1:j2])
            else:
                changes.extend(self._replaced(base[i1:i2], target[j1:j2]))

        return DocumentDiff(
            changes=changes,
            base_sentence_count=len(base),
            target_sentence_count=len(target),
            unchanged_sentence_count=unchanged,
        )

    def _replaced(self, removed: list[_Sentence], added: list[_Sentence]) -> list[TextChange]:
        """Pair each removed sentence with its most similar added one.

        Position-wise pairing breaks when a sentence is inserted in the middle
        of a replaced block, so pairs are chosen by similarity instead.
        """

        candidates = sorted(
            (
                (SequenceMatcher(None, old.key, new.key, autojunk=False).ratio(), i, j)
                for i, old in enumerate(removed)
                for j, new in enumerate(added)
            ),
            reverse=True,
        )
        pair_for_added: dict[int, tuple[int, float]] = {}
        used_removed: set[int] = set()
        for similarity, i, j in candidates:
            if similarity < _MODIFIED_MIN_SIMILARITY:
                break
            if i in used_removed or j in pair_for_added:
                continue
            used_removed.add(i)
            pair_for_added[j] = (i, similarity)

        changes = [self._removed(old) for i, old in enumerate(removed) if i not in used_removed]
        for j, new in enumerate(added):
            if j not in pair_for_added:
                changes.append(self._added(new))
                continue
            i, similarity = pair_for_added[j]
            changes.append(
                TextChange(
                    change_type=ChangeType.MODIFIED,
                    base_text=removed[i].text,
                    base_page=removed[i].page,
                    target_text=new.text,
                    target_page=new.page,
                    similarity=round(similarity, 3),
                )
            )
        return changes

    @staticmethod
    def _removed(sentence: _Sentence) -> TextChange:
        return TextChange(change_type=ChangeType.REMOVED, base_text=sentence.text, base_page=sentence.page)

    @staticmethod
    def _added(sentence: _Sentence) -> TextChange:
        return TextChange(change_type=ChangeType.ADDED, target_text=sentence.text, target_page=sentence.page)

    @staticmethod
    def _sentences(pages: Sequence[PageContent]) -> list[_Sentence]:
        sentences: list[_Sentence] = []
        for page in pages:
            previous_key: str | None = None
            for raw in split_sentences(page.text):
                text = _WHITESPACE.sub(" ", raw).strip()
                if len(text) < _MIN_SENTENCE_CHARS:
                    continue
                key = text.casefold()
                # Chunks overlap by one sentence; drop the repeat when pages are rebuilt from chunks.
                if key == previous_key:
                    continue
                previous_key = key
                sentences.append(_Sentence(page=page.page_number, text=text, key=key))
        return sentences
