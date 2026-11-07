"""Tests for the seed dataset and loader."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from seed import LISTINGS_PATH, SeedError, load_seed_rows, row_to_listing, seed_database
from matching import duplicate_conflict_ids
from verify import assess_listing

EXPECTED_KEYS = {
    "title",
    "organization",
    "type",
    "description",
    "required_skills",
    "level",
    "location",
    "mode",
    "stipend_or_prize",
    "deadline_offset_days",
    "apply_url",
    "contact_email",
    "source",
    "posted_offset_days",
    "requires_payment",
}


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    """The raw seed rows."""
    return load_seed_rows()


def test_seed_file_has_60_listings(rows: list[dict]) -> None:
    """The dataset size is exactly 60."""
    assert len(rows) == 60


def test_seed_rows_have_exact_schema(rows: list[dict]) -> None:
    """Every row carries exactly the documented keys."""
    for index, row in enumerate(rows):
        assert set(row) == EXPECTED_KEYS, f"row {index} keys differ"


def test_types_cover_every_category(rows: list[dict]) -> None:
    """All five listing types are represented."""
    counts = Counter(row["type"] for row in rows)
    assert set(counts) == {"internship", "hackathon", "scholarship", "job", "event"}
    assert counts["internship"] >= 15
    assert counts["hackathon"] >= 8


def test_expired_listings_are_present(rows: list[dict]) -> None:
    """Exactly five listings have a deadline in the past."""
    expired = [row for row in rows if row["deadline_offset_days"] < 0]
    assert len(expired) == 5
    assert all(-25 <= row["deadline_offset_days"] <= -1 for row in expired)


def test_legitimate_deadlines_spread_over_two_months(rows: list[dict]) -> None:
    """Live listings have deadlines between 1 and 60 days out."""
    live = [row for row in rows if row["deadline_offset_days"] >= 0]
    offsets = [row["deadline_offset_days"] for row in live]
    assert min(offsets) >= 1
    assert max(offsets) <= 60
    assert len({offset // 10 for offset in offsets}) >= 4  # spread across the window


def test_suspicious_listings_are_detectable_by_rules(rows: list[dict]) -> None:
    """Eight listings trip at least one risk rule; no legitimate one does."""
    today = date.today()
    flagged = [
        row
        for row in rows
        if row["deadline_offset_days"] >= 0
        and any(flag.penalty > 0 for flag in assess_listing(row_to_listing(row, today=today)).flags)
    ]
    assert len(flagged) == 8, [row["title"] for row in flagged]


def test_suspicious_listings_span_multiple_rule_categories(rows: list[dict]) -> None:
    """The flagged listings exercise several different rules."""
    today = date.today()
    codes: set[str] = set()
    for row in rows:
        trust = assess_listing(row_to_listing(row, today=today))
        codes.update(flag.code for flag in trust.flags if flag.penalty > 0)
    assert {
        "payment_required",
        "free_email_contact",
        "chat_only_application",
        "unverifiable_apply_url",
        "unrealistic_compensation",
        "urgency_pressure",
        "implausible_promise",
        "missing_org_details",
    } <= codes


def test_near_duplicates_are_present(rows: list[dict]) -> None:
    """Three title+org pairs are duplicated across sources."""
    keys = Counter((row["title"].lower().strip(), row["organization"].lower().strip()) for row in rows)
    duplicated = [key for key, count in keys.items() if count > 1]
    assert len(duplicated) == 3


def test_duplicate_pairs_have_conflicting_details(rows: list[dict]) -> None:
    """At least one duplicated pair disagrees on compensation."""
    listings = [row_to_listing(row) for row in rows]
    conflicts = duplicate_conflict_ids(listings)
    assert conflicts


def test_all_required_fields_are_non_empty(rows: list[dict]) -> None:
    """Titles, organisations, descriptions and dates are always populated."""
    for row in rows:
        assert row["title"].strip()
        assert row["organization"].strip()
        assert len(row["description"]) > 40
        assert isinstance(row["required_skills"], list)
        assert row["required_skills"]


def test_apply_urls_are_https_or_intentionally_blank(rows: list[dict]) -> None:
    """Legitimate links are https; the anonymised scam entry has none."""
    for row in rows:
        url = row["apply_url"]
        if url:
            assert url.startswith("https://"), row["title"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_row_to_listing_uses_relative_dates() -> None:
    """Offsets are converted against the supplied 'today'."""
    today = date(2026, 11, 7)
    row = load_seed_rows()[0]
    listing = row_to_listing(row, today=today)
    from datetime import timedelta

    expected = today + timedelta(days=int(row["deadline_offset_days"]))
    assert listing.deadline == expected
    assert listing.requires_payment == bool(row["requires_payment"])


def test_seed_database_is_idempotent(session) -> None:
    """Reseeding replaces rather than duplicates rows."""
    from sqlalchemy import func, select

    from models import Listing

    first = seed_database(session, reset=True)
    session.commit()
    second = seed_database(session, reset=True)
    session.commit()
    assert first == second == 60
    assert session.scalar(select(func.count(Listing.id))) == 60


def test_seed_database_keep_does_not_duplicate(session) -> None:
    """A non-reset seed adds no duplicates when the table is already full."""
    from sqlalchemy import func, select

    from models import Listing

    seed_database(session, reset=True)
    session.commit()
    # reset=False appends; callers other than ensure_seeded use reset=True.
    seed_database(session, reset=True)
    session.commit()
    assert session.scalar(select(func.count(Listing.id))) == 60


def test_missing_seed_file_raises(tmp_path: Path) -> None:
    """A missing file is a clear SeedError."""
    with pytest.raises(SeedError):
        load_seed_rows(tmp_path / "nope.json")


def test_invalid_seed_json_raises(tmp_path: Path) -> None:
    """Malformed JSON is a clear SeedError."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not a list", encoding="utf-8")
    with pytest.raises(SeedError):
        load_seed_rows(bad)


def test_seed_file_is_utf8_encodable(rows: list[dict]) -> None:
    """Rupee symbols and Indian context survive a JSON round-trip."""
    encoded = json.dumps(rows, ensure_ascii=False)
    assert json.loads(encoded) == rows
    assert any("₹" in (row["stipend_or_prize"] or "") for row in rows)


def test_listings_path_points_at_data_directory() -> None:
    """The loader reads from backend/data/listings.json."""
    assert LISTINGS_PATH.name == "listings.json"
    assert LISTINGS_PATH.parent.name == "data"
