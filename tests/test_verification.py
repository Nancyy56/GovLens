"""Sentence-level verification of answers against cited pages."""

from __future__ import annotations

from app.generation.prompt_builder import NO_ANSWER_TEXT
from app.generation.verification import SentenceStatus, verify_answer

SOURCES = {
    "S1": "The GST rate on packaged food items is 5 percent. Late filing attracts a penalty of Rs 100 per day.",
    "S2": "The GST rate on packaged food items is 12 percent. Late filing attracts interest at 18 percent per annum.",
}


def _statuses(answer: str) -> list[SentenceStatus]:
    return [s.status for s in verify_answer(answer, SOURCES).sentences]


def test_supported_sentences_pass() -> None:
    report = verify_answer("The GST rate on packaged food items is 12 percent [S2].", SOURCES)
    assert report.all_supported and report.supported == 1


def test_wrong_number_is_flagged_even_with_citation() -> None:
    report = verify_answer("The GST rate on packaged food items is 15 percent [S2].", SOURCES)
    assert report.sentences[0].status == SentenceStatus.UNSUPPORTED
    assert "15" in report.sentences[0].reason
    assert not report.all_supported


def test_number_from_another_source_is_flagged() -> None:
    # 12 appears only in S2, but the sentence cites S1.
    assert _statuses("Packaged food items are taxed at 12 percent [S1].") == [SentenceStatus.UNSUPPORTED]


def test_sentence_combining_two_cited_sources_passes() -> None:
    assert _statuses("The rate on packaged food items rose from 5 percent [S1] to 12 percent [S2].") == [SentenceStatus.SUPPORTED]


def test_unrelated_claim_with_citation_is_flagged() -> None:
    report = verify_answer("Senior citizens receive a complete exemption from income taxation [S1].", SOURCES)
    assert report.sentences[0].status == SentenceStatus.UNSUPPORTED
    assert "key words" in report.sentences[0].reason


def test_uncited_claim_is_reported() -> None:
    report = verify_answer("Late filing attracts interest at 18 percent per annum.", SOURCES)
    assert report.uncited == 1 and not report.all_supported


def test_unknown_tag_counts_as_uncited() -> None:
    assert _statuses("Late filing attracts interest at 18 percent per annum [S7].") == [SentenceStatus.UNCITED]


def test_markdown_and_short_fragments_are_skipped() -> None:
    answer = "## Summary\n- **Rate**: The GST rate on packaged food items is 12 percent [S2].\n- In short:"
    report = verify_answer(answer, SOURCES)
    assert report.checked == 1 and report.all_supported


def test_no_answer_reply_needs_no_verification() -> None:
    report = verify_answer(NO_ANSWER_TEXT, SOURCES)
    assert report.checked == 0 and report.all_supported


def test_document_numbers_do_not_split_sentences() -> None:
    sources = {"S1": "In supersession of the Notification No. 12/2023, the GST rate on packaged food items is 12 percent."}
    report = verify_answer("Notification No. 12/2023 is superseded and the GST rate on packaged food items is 12 percent [S1].", sources)
    assert report.checked == 1 and report.all_supported


def test_tag_after_full_stop_belongs_to_previous_sentence() -> None:
    report = verify_answer("The GST rate on packaged food items is 12 percent. [S2]\nLate filing attracts interest at 18 percent per annum.\n[S2]", SOURCES)
    assert report.checked == 2 and report.all_supported


def test_word_forms_match_by_stem() -> None:
    sources = {"S2": "In supersession of the Notification No. 12/2023, the Government hereby notifies the following."}
    report = verify_answer("Notification No. 12/2023 has been superseded by this notification [S2].", sources)
    assert report.all_supported


def test_supersession_warning_counts_as_evidence() -> None:
    sources = {"S1": "The GST rate on packaged food items is 5 percent."}
    answer = "Notification No. 12/2023 is superseded by Notification No. 25/2024 [S1]."
    assert not verify_answer(answer, sources).all_supported
    assert verify_answer(answer, sources, "Document 12/2023 is superseded by 25/2024.").all_supported
