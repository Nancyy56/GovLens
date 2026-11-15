"""Sentence-level document diffs."""

from __future__ import annotations

from app.comparison.differ import ChangeType, DocumentDiffer
from app.schemas.processing import PageContent


def _pages(*texts: str) -> list[PageContent]:
    return [PageContent(page_number=i, text=t) for i, t in enumerate(texts, start=1)]


def test_identical_documents_have_no_changes() -> None:
    diff = DocumentDiffer().diff(_pages("Rate is 5 percent. Filing is monthly."), _pages("Rate is 5 percent.\nFiling is monthly."))
    assert diff.changes == []
    assert diff.unchanged_sentence_count == 2


def test_detects_modified_added_and_removed_with_pages() -> None:
    base = _pages("The GST rate is 5 percent. Returns are filed monthly.", "Penalty is Rs 100 per day.")
    target = _pages("The GST rate is 12 percent. Returns are filed monthly.", "Interest applies at 18 percent per year.")

    diff = DocumentDiffer().diff(base, target)
    by_type = {c.change_type: c for c in diff.changes}

    modified = by_type[ChangeType.MODIFIED]
    assert "5 percent" in modified.base_text and "12 percent" in modified.target_text
    assert (modified.base_page, modified.target_page) == (1, 1)
    assert diff.unchanged_sentence_count == 1
    assert {c.change_type for c in diff.changes} >= {ChangeType.MODIFIED}
    # The penalty sentence was replaced by an unrelated one: removal + addition, not a modification.
    assert any(c.change_type == ChangeType.REMOVED and c.base_page == 2 for c in diff.changes)
    assert any(c.change_type == ChangeType.ADDED and c.target_page == 2 for c in diff.changes)


def test_chunk_overlap_sentence_is_not_counted_twice() -> None:
    # Pages rebuilt from chunks repeat the boundary sentence once.
    base = _pages("First sentence. Boundary sentence.\nBoundary sentence. Last sentence.")
    target = _pages("First sentence. Boundary sentence. Last sentence.")

    diff = DocumentDiffer().diff(base, target)

    assert diff.changes == []
    assert diff.base_sentence_count == 3


def test_abbreviations_do_not_split_sentences() -> None:
    diff = DocumentDiffer().diff(
        _pages("In supersession of Notification No. 12/2023 the rate is Rs. 100. Signed by S. K. Rao."),
        _pages("In supersession of Notification No. 12/2023 the rate is Rs. 200. Signed by S. K. Rao."),
    )
    assert diff.base_sentence_count == 2
    assert [(c.change_type, c.base_text) for c in diff.changes] == [
        (ChangeType.MODIFIED, "In supersession of Notification No. 12/2023 the rate is Rs. 100.")
    ]


def test_heading_lines_are_compared_separately() -> None:
    diff = DocumentDiffer().diff(
        _pages("Notification No. 12/2023\nSubject: GST rates\nThe rate is 5 percent."),
        _pages("Notification No. 25/2024\nSubject: GST rates\nThe rate is 5 percent."),
    )
    assert [(c.base_text, c.target_text) for c in diff.changes] == [("Notification No. 12/2023", "Notification No. 25/2024")]


def test_inserted_sentence_does_not_hide_a_modification() -> None:
    diff = DocumentDiffer().diff(
        _pages("Header.\nThe GST rate on food is 5 percent.\nFooter."),
        _pages("Header.\nIn supersession of the earlier order, it is notified.\nThe GST rate on food is 12 percent.\nFooter."),
    )
    kinds = sorted((c.change_type.value, c.target_text) for c in diff.changes)
    assert kinds == [
        ("ADDED", "In supersession of the earlier order, it is notified."),
        ("MODIFIED", "The GST rate on food is 12 percent."),
    ]
