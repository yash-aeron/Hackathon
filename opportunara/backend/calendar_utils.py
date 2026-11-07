"""Deadline calendar generation (.ics) with 7/3/1-day reminders."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Iterable, Sequence

logger = logging.getLogger("scoutly.calendar")

#: Reminder offsets (in days before the deadline) attached to every event.
DEFAULT_REMINDER_DAYS: tuple[int, ...] = (7, 3, 1)

#: Suffix for generated UIDs; deterministic so re-imports update instead of duplicating.
UID_DOMAIN = "scoutly.app"

_MAX_SUMMARY = 72


def _shorten(text: str, limit: int) -> str:
    """Trim a string to ``limit`` characters on a word boundary."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip(" ,;:-") + "…"


def _event_summary(listing: Any) -> str:
    """Build the calendar event title: ``"Apply: Role — Organisation"``."""
    title = _shorten(getattr(listing, "title", "Opportunity"), 44)
    org = _shorten(getattr(listing, "organization", ""), 22)
    summary = f"Apply: {title}" + (f" — {org}" if org else "")
    return _shorten(summary, _MAX_SUMMARY)


def _event_description(listing: Any) -> str:
    """Build the calendar event body with the facts a student needs."""
    lines = [
        f"Type: {getattr(listing, 'type', '')}",
        f"Organization: {getattr(listing, 'organization', '')}",
        f"Level: {getattr(listing, 'level', '')}",
        f"Mode: {getattr(listing, 'mode', '')}",
    ]
    stipend = getattr(listing, "stipend_or_prize", None)
    if stipend:
        lines.append(f"Stipend/Prize: {stipend}")
    apply_url = getattr(listing, "apply_url", "")
    if apply_url:
        lines.append(f"Apply: {apply_url}")
    lines.append("Deadline added via Scoutly")
    return "\n".join(lines)


def build_calendar(
    listings: Iterable[Any],
    *,
    reminders: Sequence[int] = DEFAULT_REMINDER_DAYS,
) -> str:
    """Serialise listings into an iCalendar string.

    Each listing becomes one all-day event on its deadline date, with a VALARM
    display reminder for every offset in ``reminders``.

    Args:
        listings: Objects (ORM ``Listing`` or ``ListingOut``) with ``title``,
            ``organization``, ``deadline`` and optional detail fields.
        reminders: Days-before offsets for reminders; defaults to 7, 3 and 1.

    Returns:
        The ``.ics`` document as a string.

    Raises:
        ValueError: if no listings with a deadline were supplied.
    """
    from ics import Calendar, DisplayAlarm, Event

    calendar = Calendar()
    calendar.creator = "Scoutly"
    calendar.scale = "GREGORIAN"

    count = 0
    for listing in listings:
        deadline = getattr(listing, "deadline", None)
        if not isinstance(deadline, date):
            logger.debug("Skipping listing without a deadline: %r", listing)
            continue

        event = Event()
        event.name = _event_summary(listing)
        event.begin = deadline
        event.make_all_day()
        event.description = _event_description(listing)
        event.uid = f"scoutly-{getattr(listing, 'id', count)}@{UID_DOMAIN}"
        apply_url = getattr(listing, "apply_url", "")
        if apply_url:
            event.url = apply_url

        for days_before in reminders:
            if days_before <= 0:
                continue
            event.alarms.append(
                DisplayAlarm(
                    trigger=timedelta(days=-int(days_before)),
                    display_text=f"Scoutly reminder: {days_before} day(s) left to apply",
                )
            )

        calendar.events.add(event)
        count += 1

    if count == 0:
        raise ValueError("No listings with deadlines were supplied for the calendar.")

    return calendar.serialize()


def calendar_filename() -> str:
    """Suggested download filename."""
    return "scoutly-deadlines.ics"


def upcoming_deadlines(listings: Iterable[Any], *, days: int = 30, today: date | None = None) -> list[Any]:
    """Listings with a deadline inside the next ``days`` days (inclusive)."""
    today = today or date.today()
    horizon = today + timedelta(days=days)
    result = []
    for listing in listings:
        deadline = getattr(listing, "deadline", None)
        if isinstance(deadline, date) and today <= deadline <= horizon:
            result.append(listing)
    result.sort(key=lambda item: item.deadline)
    return result
