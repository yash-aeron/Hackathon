"""Load ``data/listings.json`` into SQLite.

Seed deadlines are stored as offsets (``deadline_offset_days``) so they are
recomputed relative to *today* every time seeding runs - the dataset never goes
stale. Run it with::

    python seed.py            # reset and load
    python seed.py --keep     # only load if the table is empty
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db import SessionLocal, init_db
from models import Listing, ListingEmbedding

logger = logging.getLogger("scoutly.seed")

DATA_DIR = Path(__file__).resolve().parent / "data"
LISTINGS_PATH = DATA_DIR / "listings.json"

REQUIRED_KEYS = {
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

VALID_TYPES = {"internship", "hackathon", "scholarship", "job", "event"}
VALID_LEVELS = {"first-year", "second-year", "third-year", "final-year", "any"}
VALID_MODES = {"remote", "onsite", "hybrid"}


class SeedError(RuntimeError):
    """Raised when the seed file is missing or malformed."""


def load_seed_rows(path: Path | str = LISTINGS_PATH) -> list[dict[str, Any]]:
    """Read and validate the seed JSON file.

    Args:
        path: Path to ``listings.json``.

    Returns:
        The list of raw seed dictionaries.

    Raises:
        SeedError: if the file is missing, empty, or has invalid records.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise SeedError(
            f"Seed file not found at {file_path}. Expected backend/data/listings.json."
        )
    try:
        rows = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SeedError(f"Seed file is not valid JSON: {exc}") from exc

    if not isinstance(rows, list) or not rows:
        raise SeedError("Seed file must contain a non-empty JSON array.")

    problems: list[str] = []
    for index, row in enumerate(rows):
        missing = REQUIRED_KEYS - set(row)
        if missing:
            problems.append(f"record {index} missing keys: {sorted(missing)}")
        elif row["type"] not in VALID_TYPES:
            problems.append(f"record {index} has invalid type {row['type']!r}")
        elif row["level"] not in VALID_LEVELS:
            problems.append(f"record {index} has invalid level {row['level']!r}")
        elif row["mode"] not in VALID_MODES:
            problems.append(f"record {index} has invalid mode {row['mode']!r}")
    if problems:
        raise SeedError("Invalid seed records: " + "; ".join(problems[:5]))
    return rows


def row_to_listing(row: dict[str, Any], today: date | None = None) -> Listing:
    """Convert one seed row into an ORM :class:`Listing` with real dates."""
    today = today or date.today()
    deadline = today + timedelta(days=int(row["deadline_offset_days"]))
    posted = today + timedelta(days=int(row.get("posted_offset_days") or 0))
    return Listing(
        title=str(row["title"]).strip(),
        organization=str(row["organization"]).strip(),
        type=str(row["type"]),
        description=str(row["description"]).strip(),
        required_skills=[str(skill).strip() for skill in row.get("required_skills") or []],
        level=str(row["level"]),
        location=str(row["location"]).strip(),
        mode=str(row["mode"]),
        stipend_or_prize=(str(row["stipend_or_prize"]).strip() if row.get("stipend_or_prize") else None),
        deadline=deadline,
        apply_url=str(row.get("apply_url") or "").strip(),
        contact_email=(str(row["contact_email"]).strip() if row.get("contact_email") else None),
        source=str(row.get("source") or "seed").strip(),
        posted_date=posted,
        requires_payment=bool(row.get("requires_payment", False)),
    )


def seed_database(
    session: Session | None = None,
    *,
    path: Path | str = LISTINGS_PATH,
    reset: bool = True,
    today: date | None = None,
) -> int:
    """Insert seed listings into the database.

    Args:
        session: Optional existing session (tests); a new one is created otherwise.
        path: Seed JSON path.
        reset: Delete existing listings and cached embeddings first.
        today: Anchor date for the relative offsets.

    Returns:
        Number of listings inserted.
    """
    rows = load_seed_rows(path)
    today = today or date.today()
    owns_session = session is None
    session = session or SessionLocal()
    try:
        if reset:
            session.execute(delete(ListingEmbedding))
            session.execute(delete(Listing))
            session.flush()

        listings = [row_to_listing(row, today=today) for row in rows]
        session.add_all(listings)
        session.flush()
        inserted = len(listings)
        if owns_session:
            session.commit()
        logger.info("Seeded %s listings (reset=%s)", inserted, reset)
        return inserted
    except Exception:
        if owns_session:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def ensure_seeded(*, path: Path | str = LISTINGS_PATH) -> int:
    """Seed automatically when the listings table is empty.

    Returns the number of listings now present, or 0 when the seed file is
    unavailable (the API then starts with an empty catalogue instead of dying).
    """
    init_db()
    session = SessionLocal()
    try:
        existing = session.scalar(select(func.count(Listing.id))) or 0
        if existing:
            return int(existing)
        try:
            count = seed_database(session, path=path, reset=False)
            session.commit()
        except SeedError as exc:
            logger.error("Could not auto-seed: %s", exc)
            session.rollback()
            return 0
        logger.info("Auto-seeded %s listings on startup", count)
        return count
    finally:
        session.close()


def main() -> None:
    """CLI entry point: ``python seed.py [--keep]``."""
    parser = argparse.ArgumentParser(description="Seed the Scoutly SQLite database.")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep existing rows; only seed when the table is empty.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    init_db()
    if args.keep:
        count = ensure_seeded()
        print(f"Database contains {count} listings (skipped reseed).")
        return

    session = SessionLocal()
    try:
        count = seed_database(session, reset=True)
        session.commit()
        print(f"Seeded {count} listings into the database.")
        print(f"Deadlines are relative to {date.today().isoformat()}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
