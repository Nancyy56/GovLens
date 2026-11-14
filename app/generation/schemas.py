"""Pydantic schemas for generation results."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.citations.schemas import Citation
from app.generation.verification import VerificationReport
from app.supersession.schemas import SupersessionResult


class LabeledCitation(BaseModel):
    """A citation together with the tag (e.g. "S1") used for it in the answer."""

    label: str
    citation: Citation


class GeneratedAnswer(BaseModel):
    """Final answer bundle produced by the generation layer."""

    query: str
    answer_markdown: str
    # Only the citations the answer actually used (all, if it used no tags).
    citations: list[Citation] = Field(default_factory=list)
    labeled_citations: list[LabeledCitation] = Field(default_factory=list)
    supersession_warnings: list[SupersessionResult] = Field(default_factory=list)
    # Sentence-by-sentence check of the answer against the pages it cites.
    verification: VerificationReport = Field(default_factory=VerificationReport)
    # True when the model cited no valid tags and all retrieved sources are listed instead.
    citations_inferred: bool = False


GeneratedAnswer.model_rebuild()
