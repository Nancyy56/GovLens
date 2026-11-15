"""Check each sentence of an answer against the sources it cites.

The check is deliberately simple and explainable rather than another model:

* every number in a sentence (rates, amounts, dates, document numbers) must
  appear in the cited pages, since wrong numbers are the costliest mistake in
  legal text;
* at least ``MIN_WORD_OVERLAP`` of the sentence's content words must appear
  in the cited pages.

A sentence that cites nothing is reported as uncited. Passing the check does
not prove a sentence is correct, but failing it reliably flags statements a
reader should verify by hand.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.text import split_sentences
from app.generation.prompt_builder import NO_ANSWER_TEXT

MIN_WORD_OVERLAP = 0.5
_MIN_CONTENT_WORDS = 3

_TAG = re.compile(r"\[[^\[\]]*\bS\d+\b[^\[\]]*\]")
_LABEL = re.compile(r"\bS(\d+)\b")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD = re.compile(r"[a-z][a-z'-]+")
_MARKDOWN = re.compile(r"[*_`#>|]+")
_STOPWORDS = frozenset(
    """a an the and or but if of to in on at by for with from as is are was were be been being this that these
    those it its which who whom whose what when where why how not no nor so than then there their they them he she
    his her we our you your i me my also any all each such may shall will would can could should must has have had
    do does did per under above below into about after before between during within without upon over same other
    only very more most less least further according said says stated states provided document documents source
    sources notification circular order""".split()
)


class SentenceStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNCITED = "UNCITED"


class SentenceCheck(BaseModel):
    text: str
    citations: list[str] = Field(default_factory=list)
    status: SentenceStatus
    reason: str | None = None


class VerificationReport(BaseModel):
    checked: int = 0
    supported: int = 0
    unsupported: int = 0
    uncited: int = 0
    all_supported: bool = True
    sentences: list[SentenceCheck] = Field(default_factory=list)


_STEM_LENGTH = 6


def _stem(word: str) -> str:
    # Light stemming by prefix, so "superseded"/"supersession" or
    # "notified"/"notification" count as the same word.
    return word[:_STEM_LENGTH]


def _content_words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.casefold()) if len(w) > 2 and w not in _STOPWORDS]


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUMBER.findall(text)}


def answer_sentences(answer: str) -> list[str]:
    cleaned = "\n".join(_MARKDOWN.sub(" ", line).strip(" -•\t") for line in answer.splitlines())
    sentences: list[str] = []
    for sentence in (s.strip() for s in split_sentences(cleaned)):
        # Models often put the tag after the full stop ("... 225 units. [S2]");
        # a fragment that is only tags belongs to the sentence before it.
        if sentences and not _TAG.sub("", sentence).strip(" .,;:"):
            sentences[-1] = f"{sentences[-1]} {sentence}"
        else:
            sentences.append(sentence)
    return sentences


def verify_answer(answer: str, sources: Mapping[str, str], system_facts: str = "") -> VerificationReport:
    """Check ``answer`` (without the appended Sources list) against ``sources`` (label -> page text).

    ``system_facts`` is trusted text GovLens itself supplied, such as
    supersession warnings built from stored links; it counts as evidence for
    every cited sentence.
    """

    report = VerificationReport()
    if NO_ANSWER_TEXT.casefold() in answer.casefold():
        return report

    folded_sources = {label: " ".join(text.split()).casefold() for label, text in sources.items()}
    for sentence in answer_sentences(answer):
        labels = []
        for tag in _TAG.findall(sentence):
            labels += [f"S{n}" for n in _LABEL.findall(tag)]
        claim = _TAG.sub(" ", sentence)
        words = _content_words(claim)
        numbers = _numbers(claim)
        if len(words) < _MIN_CONTENT_WORDS and not numbers:
            continue  # headings, connectives, and other non-claims

        report.checked += 1
        known = [label for label in dict.fromkeys(labels) if label in folded_sources]
        if not known:
            report.uncited += 1
            report.sentences.append(SentenceCheck(text=sentence, status=SentenceStatus.UNCITED, reason="No valid source tag"))
            continue

        evidence = " ".join([*(folded_sources[label] for label in known), system_facts.casefold()])
        evidence_numbers = _numbers(evidence)
        evidence_stems = {_stem(w) for w in _WORD.findall(evidence)}
        missing_numbers = sorted(numbers - evidence_numbers)
        overlap = sum(_stem(w) in evidence_stems for w in words) / len(words) if words else 1.0

        if missing_numbers:
            reason = f"Not found in cited pages: {', '.join(missing_numbers)}"
        elif overlap < MIN_WORD_OVERLAP:
            reason = f"Only {overlap:.0%} of key words appear in the cited pages"
        else:
            reason = None
        status = SentenceStatus.SUPPORTED if reason is None else SentenceStatus.UNSUPPORTED
        if status == SentenceStatus.SUPPORTED:
            report.supported += 1
        else:
            report.unsupported += 1
        report.sentences.append(SentenceCheck(text=sentence, citations=known, status=status, reason=reason))

    report.all_supported = report.unsupported == 0 and report.uncited == 0
    return report
