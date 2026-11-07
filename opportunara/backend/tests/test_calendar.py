"""Calendar export tests: one event per deadline, with 7/3/1-day reminders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from calendar_utils import build_calendar, calendar_filename, upcoming_deadlines


@dataclass
class FakeListing:
    id: int
    title: str
    organization: str
    deadline: date | None
    apply_url: str = "https://example.com/apply"


def test_calendar_contains_one_event_per_listing() -> None:
    listings = [
        FakeListing(1, "Frontend Intern", "TechNova", date(2026, 12, 15)),
        FakeListing(2, "Backend Intern", "DataWorks", date(2026, 12, 20)),
    ]
    ics = build_calendar(listings)
    assert ics.startswith("BEGIN:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == 2
    assert "SUMMARY:Apply: Frontend Intern" in ics

def test_calendar_adds_three_reminders_by_default() -> None:
    ics = build_calendar([FakeListing(1, "Internship", "Acme", date(2026, 12, 15))])
    assert ics.count("BEGIN:VALARM") == 3
    assert "TRIGGER:-P7D" in ics or "TRIGGER:-P1W" in ics


def test_calendar_respects_custom_reminders() -> None:
    ics = build_calendar(
        [FakeListing(1, "Internship", "Acme", date(2026, 12, 15))],
        reminders=[2],
    )
    assert ics.count("BEGIN:VALARM") == 1


def test_calendar_skips_listings_without_a_deadline() -> None:
    ics = build_calendar(
        [
            FakeListing(1, "No deadline", "Acme", None),
            FakeListing(2, "Has deadline", "Acme", date(2026, 12, 15)),
        ]
    )
    assert ics.count("BEGIN:VEVENT") == 1


def test_calendar_raises_when_nothing_is_schedulable() -> None:
    with pytest.raises(ValueError):
        build_calendar([FakeListing(1, "No deadline", "Acme", None)])


def test_calendar_filename_is_a_ics_file() -> None:
    assert calendar_filename().endswith(".ics")


def test_upcoming_deadlines_filters_and_sorts() -> None:
    today = date(2026, 11, 7)
    listings = [
        FakeListing(1, "Later", "Acme", date(2026, 12, 1)),
        FakeListing(2, "Past", "Acme", date(2026, 11, 1)),
        FakeListing(3, "Sooner", "Acme", date(2026, 11, 20)),
        FakeListing(4, "Far off", "Acme", date(2027, 6, 1)),
        FakeListing(5, "No deadline", "Acme", None),
    ]
    result = upcoming_deadlines(listings, days=30, today=today)
    assert [listing.id for listing in result] == [3, 1]
