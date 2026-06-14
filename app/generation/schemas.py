"""Pydantic schemas for generation results."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.citations.schemas import CitationBundle
from app.supersession.schemas import SupersessionResult


class GeneratedAnswer(BaseModel):
    """Final answer bundle produced by the generation layer."""

    query: str
    answer_markdown: str
    citations: list = Field(default_factory=list)
    supersession_warnings: list = Field(default_factory=list)


GeneratedAnswer.model_rebuild()
