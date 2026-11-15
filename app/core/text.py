"""Sentence splitting that understands abbreviations common in government text."""

from __future__ import annotations

import re

# A sentence ends at . ! or ? followed by whitespace, except after common
# abbreviations ("Notification No. 12/2023", "Rs. 100") and initials ("S. K. Rao").
_SENTENCE_END = re.compile(r"[.!?]+\s+")
ABBREVIATIONS = frozenset({
    "no", "nos", "rs", "dr", "mr", "mrs", "ms", "smt", "shri", "sh", "sl", "dt", "viz",
    "i.e", "e.g", "vs", "govt", "dept", "sec", "art", "cl", "para", "fig", "vol", "ltd", "pvt", "co", "st",
})


def split_sentences(text: str) -> list[str]:
    """Split into lines, then split each line at real sentence ends."""

    pieces: list[str] = []
    for line in text.splitlines():
        start = 0
        for match in _SENTENCE_END.finditer(line):
            before = line[start:match.start()]
            word = before.rsplit(None, 1)[-1] if before.strip() else ""
            if word.casefold().strip("(") in ABBREVIATIONS or len(word) == 1:
                continue
            pieces.append(line[start:match.end()])
            start = match.end()
        pieces.append(line[start:])
    return [piece for piece in pieces if piece.strip()]
