"""Plain-language document briefs."""

from __future__ import annotations

import pytest

from app.services.brief import MAX_CHARS, BriefService
from app.services.documents import DocumentService


class FakeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "  ## In one sentence\nRates changed (p.1).  "


@pytest.fixture(autouse=True)
def _clear_cache():
    BriefService._cache.clear()
    yield
    BriefService._cache.clear()


def _service(session, llm):
    return BriefService(DocumentService(session, vector_store=None), llm)


def test_brief_uses_the_document_text_and_is_cached(sqlite_session, make_document) -> None:
    doc = make_document("12/2023", pages=["GST on packaged food is 5 percent.", "Late filing: Rs 100 per day."])
    llm = FakeLLM()
    service = _service(sqlite_session, llm)

    first = service.brief(doc.id)
    assert first.markdown.startswith("## In one sentence")
    assert (first.pages_used, first.total_pages, first.truncated, first.cached) == (2, 2, False, False)
    prompt = llm.prompts[0]
    assert "[Page 1]" in prompt and "Rs 100 per day" in prompt and "12/2023" in prompt
    assert "Not stated" in prompt  # the model is told not to guess

    again = service.brief(doc.id)
    assert again.cached is True and len(llm.prompts) == 1
    service.brief(doc.id, refresh=True)
    assert len(llm.prompts) == 2


def test_long_documents_are_truncated_to_fit_the_model(sqlite_session, make_document) -> None:
    doc = make_document("BIG/1", pages=["a" * 5000, "b" * 5000, "c" * 5000])
    llm = FakeLLM()
    result = _service(sqlite_session, llm).brief(doc.id)

    assert result.truncated is True
    assert result.pages_used < result.total_pages
    assert len(llm.prompts[0]) < MAX_CHARS + 1200
    assert "ccccc" not in llm.prompts[0]


def test_unknown_document_raises(sqlite_session) -> None:
    import uuid

    from app.services.exceptions import DocumentNotFoundError

    with pytest.raises(DocumentNotFoundError):
        _service(sqlite_session, FakeLLM()).brief(uuid.uuid4())
