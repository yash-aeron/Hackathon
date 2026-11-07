"""Tiny factories for building listing/profile fixtures in tests."""

from __future__ import annotations

from datetime import date, timedelta

from models import Listing, ListingOut


def make_listing(**overrides) -> Listing:
    """Build an in-memory :class:`Listing` for rule and ranking tests."""
    defaults = dict(
        title="Backend Engineering Intern",
        organization="Nexus Labs",
        type="internship",
        description=(
            "Build FastAPI services and maintain the PostgreSQL data model for a "
            "student-facing product. You will write tests and ship small features weekly."
        ),
        required_skills=["Python", "FastAPI", "SQL"],
        level="third-year",
        location="Bengaluru, India",
        mode="onsite",
        stipend_or_prize="₹40,000/month",
        deadline=date.today() + timedelta(days=12),
        apply_url="https://careers.nexuslabs.io/intern-backend",
        contact_email="talent@nexuslabs.io",
        source="Company careers page",
        posted_date=None,
        requires_payment=False,
    )
    defaults.update(overrides)
    return Listing(**defaults)


def make_listing_out(**overrides) -> ListingOut:
    """Build a :class:`ListingOut` (wire model) for kit and calendar tests.

    Unsaved listings have no primary key, so an id is synthesised here.
    """
    listing = make_listing(**overrides)
    return ListingOut(
        id=overrides.get("id", 1),
        title=listing.title,
        organization=listing.organization,
        type=listing.type,
        description=listing.description,
        required_skills=list(listing.required_skills or []),
        level=listing.level,
        location=listing.location,
        mode=listing.mode,
        stipend_or_prize=listing.stipend_or_prize,
        deadline=listing.deadline,
        apply_url=listing.apply_url,
        contact_email=listing.contact_email,
        source=listing.source,
        posted_date=listing.posted_date,
        requires_payment=bool(listing.requires_payment),
    )
