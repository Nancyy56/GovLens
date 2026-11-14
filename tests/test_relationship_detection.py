"""Detection of supersedes/amends/references links in document text."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.metadata.extractors import RuleBasedMetadataExtractor
from app.metadata.normalization import normalize_document_number
from app.models.enums import DocumentType, RelationshipType
from app.schemas.processing import PageContent, RawDocument


def _mentions(text: str) -> dict[str, RelationshipType]:
    raw = RawDocument(
        document_id=uuid.uuid4(),
        source_type="pdf",
        source_path="doc.pdf",
        pages=[PageContent(page_number=1, text=text)],
        ingested_at=datetime.now(UTC),
    )
    metadata = RuleBasedMetadataExtractor().extract(raw)
    return {m.document_number: m.relationship_type for m in metadata.mentions}


def test_in_supersession_of_marks_supersedes() -> None:
    mentions = _mentions("Notification No. 25/2024\nIn supersession of the Notification No. 12/2023, the Government notifies.")
    assert mentions == {"12/2023": RelationshipType.SUPERSEDES}


def test_hereby_rescinded_after_mention_marks_supersedes() -> None:
    mentions = _mentions("Order No. 8/2024\nOrder No. 7/2020 is hereby rescinded.")
    assert mentions == {"7/2020": RelationshipType.SUPERSEDES}


def test_amendment_marks_amends_including_long_form() -> None:
    mentions = _mentions(
        "Notification No. 3/2024\nThis notification further amends the notification of the Government of India "
        "in the Ministry of Finance (Department of Revenue), No. 1/2017-Central Tax (Rate), dated the 28th June, 2017."
    )
    assert mentions == {"1/2017-Central": RelationshipType.AMENDS}


def test_keyword_in_another_clause_does_not_leak() -> None:
    mentions = _mentions(
        "Notification No. 25/2024\nIn supersession of the Notification No. 12/2023, except as respects things "
        "done before such supersession, and under Circular No. 4/2022, the Government notifies."
    )
    assert mentions["12/2023"] == RelationshipType.SUPERSEDES
    assert mentions["4/2022"] == RelationshipType.REFERENCES


def test_commas_inside_issuer_name_do_not_break_context() -> None:
    mentions = _mentions(
        "Circular No. 9/2024\nIn supersession of the Ministry of Finance, Department of Revenue, "
        "Notification No. 3/2019, the Board directs."
    )
    assert mentions == {"3/2019": RelationshipType.SUPERSEDES}


def test_plain_reference_and_own_number_excluded() -> None:
    mentions = _mentions("Order No. 5/2024\nAs stated in Circular No. 2/2020 and Order No. 5/2024, the scheme continues.")
    assert mentions == {"2/2020": RelationshipType.REFERENCES}


def test_strongest_relationship_wins_for_repeated_number() -> None:
    mentions = _mentions(
        "Notification No. 30/2024\nSee Notification No. 12/2023. In supersession of Notification No. 12/2023, it is notified."
    )
    assert mentions == {"12/2023": RelationshipType.SUPERSEDES}


def test_supersedes_and_amends_lists_populated() -> None:
    raw = RawDocument(
        document_id=uuid.uuid4(),
        source_type="pdf",
        source_path="doc.pdf",
        pages=[
            PageContent(
                page_number=1,
                text="Notification No. 9/2024\nIn supersession of Notification No. 1/2020, and to amend Circular No. 2/2021, it is notified.",
            )
        ],
        ingested_at=datetime.now(UTC),
    )
    metadata = RuleBasedMetadataExtractor().extract(raw)
    assert metadata.supersedes_documents == ["1/2020"]
    assert metadata.amends_documents == ["2/2021"]
    assert metadata.mentions[1].document_type == DocumentType.CIRCULAR


def test_normalize_document_number() -> None:
    assert normalize_document_number(" 17 / 2024. ") == "17/2024"
    assert normalize_document_number("04/2025-GST") == normalize_document_number("04/2025-gst")


def test_numbered_list_shares_relationship() -> None:
    mentions = _mentions("Order No. 9/2024\nNotifications Nos. 1/2020, 2/2020 and 3/2020 are hereby rescinded.")
    assert mentions == {
        "1/2020": RelationshipType.SUPERSEDES,
        "2/2020": RelationshipType.SUPERSEDES,
        "3/2020": RelationshipType.SUPERSEDES,
    }


def test_separate_mentions_joined_by_and_share_relationship() -> None:
    mentions = _mentions("Order No. 9/2024\nNotification No. 4/2021 and Circular No. 7/2021 are hereby withdrawn.")
    assert mentions == {"4/2021": RelationshipType.SUPERSEDES, "7/2021": RelationshipType.SUPERSEDES}


def test_list_does_not_swallow_following_words() -> None:
    mentions = _mentions("Order No. 9/2024\nAs per Circular No. 5/2024 and the earlier guidance, staff shall comply.")
    assert mentions == {"5/2024": RelationshipType.REFERENCES}


def test_own_number_excluded_from_lists() -> None:
    mentions = _mentions("Notification No. 9/2024\nNotifications Nos. 9/2024 and 8/2024 are published together.")
    assert mentions == {"8/2024": RelationshipType.REFERENCES}
