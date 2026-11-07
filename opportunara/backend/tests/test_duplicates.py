"""Duplicate collapsing and ranking behaviour tests.

The brief calls for tests of near-duplicate collapsing specifically, plus the
ranking contract: expired listings dropped, filters honoured, high-risk listings
pinned below legitimate ones, breakdowns explainable and results capped.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from factories import make_listing
from matching import (
    collapse_duplicates,
    cosine_similarity,
    duplicate_conflict_ids,
    hashing_embed,
    heuristic_why_it_fits,
    rank_listings,
)
from models import MatchFilters


def _dupe(source: str, stipend: str, description: str = "Backend intern role.") -> object:
    """Same title + organisation, reposted by another source."""
    return make_listing(
        title="Data Science Intern",
        organization="Flipkart",
        source=source,
        stipend_or_prize=stipend,
        description=description,
        apply_url=f"https://{source.split()[0].lower()}.com/jobs/1",
    )


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def test_conflict_detected_when_reposts_disagree_on_pay() -> None:
    """A different stipend for the same role is a conflicting repost."""
    listings = [_dupe("Unstop", "₹45,000/month"), _dupe("LinkedIn", "₹50,000/month")]
    assert len(duplicate_conflict_ids(listings)) == 2


def test_no_conflict_when_reposts_are_identical() -> None:
    """Identical details are a duplicate but not a conflict."""
    listings = [_dupe("Unstop", "₹45,000/month"), _dupe("LinkedIn", "₹45,000/month")]
    assert duplicate_conflict_ids(listings) == set()


def test_single_listing_has_no_conflict() -> None:
    """A lone listing cannot conflict with itself."""
    assert duplicate_conflict_ids([_dupe("Unstop", "₹45,000/month")]) == set()


# ---------------------------------------------------------------------------
# Collapsing
# ---------------------------------------------------------------------------


def test_collapse_keeps_one_per_opportunity() -> None:
    """Title + organisation identifies one opportunity, not two."""
    listings = [
        _dupe("Unstop", "₹45,000/month"),
        _dupe("LinkedIn", "₹50,000/month"),
        make_listing(title="Other Role", organization="Zoho"),
    ]
    kept, index, _conflicts = collapse_duplicates(listings)
    assert len(kept) == 2
    keys = [(item.title, item.organization) for item in kept]
    assert keys.count(("Data Science Intern", "Flipkart")) == 1
    assert len(index) == len(kept)


def test_collapse_keeps_the_higher_trust_repost() -> None:
    """A payment-demanding repost loses to a clean one."""
    clean = make_listing(
        title="Data Science Intern",
        organization="Flipkart",
        source="LinkedIn",
        stipend_or_prize="₹45,000/month",
    )
    paid = make_listing(
        title="Data Science Intern",
        organization="Flipkart",
        source="Telegram channel",
        stipend_or_prize="₹45,000/month",
        requires_payment=True,
    )
    kept, _index, _conflicts = collapse_duplicates([paid, clean])
    assert len(kept) == 1
    assert kept[0].requires_payment is False


def test_collapse_is_case_and_punctuation_insensitive() -> None:
    """Casing and punctuation do not defeat duplicate detection."""
    first = make_listing(
        title="AI for Bharat Summit - Student Track",
        organization="NASSCOM FutureSkills",
    )
    second = make_listing(
        title="ai for bharat summit — student track",
        organization="nasscom futureskills",
    )
    kept, _index, _conflicts = collapse_duplicates([first, second])
    assert len(kept) == 1


def test_collapse_keeps_distinct_organisations_separate() -> None:
    """Same title at different organisations is not a duplicate."""
    listings = [
        make_listing(title="Software Intern", organization="Zoho"),
        make_listing(title="Software Intern", organization="Freshworks"),
    ]
    kept, _index, _conflicts = collapse_duplicates(listings)
    assert len(kept) == 2


# ---------------------------------------------------------------------------
# Ranking contract
# ---------------------------------------------------------------------------


def _rank(listings, profile, **kwargs):
    return rank_listings(profile, listings, today=date.today(), **kwargs)


def test_ranking_drops_expired_listings(sample_profile) -> None:
    """Expired deadlines are a hard filter."""
    expired = make_listing(deadline=date.today() - timedelta(days=1), title="Expired Intern")
    live = make_listing(deadline=date.today() + timedelta(days=10))
    matches, meta = _rank([expired, live], sample_profile)
    assert [match.listing.title for match in matches] == [live.title]
    assert meta["candidates"] == 1


def test_ranking_honours_type_and_mode_filters(sample_profile) -> None:
    """Server-side filters drop everything that does not match."""
    remote_internship = make_listing(mode="remote", type="internship", title="Remote Intern")
    onsite_internship = make_listing(mode="onsite", type="internship", title="Onsite Intern")
    remote_hackathon = make_listing(mode="remote", type="hackathon", title="Remote Hackathon")
    matches, _meta = _rank(
        [remote_internship, onsite_internship, remote_hackathon],
        sample_profile,
        filters=MatchFilters(types=["internship"], mode="remote"),
    )
    assert [match.listing.title for match in matches] == ["Remote Intern"]


def test_ranking_pins_high_risk_below_legit(sample_profile) -> None:
    """A great-fit risky listing still sorts after legitimate results."""
    scam = make_listing(
        title="Frontend Intern",
        organization="TechNova Solutions",
        required_skills=["React", "JavaScript", "TypeScript"],
        stipend_or_prize="₹1,50,000/month",
        level="first-year",
        requires_payment=True,
        description=(
            "Pay a refundable security deposit of ₹1,999. Only 2 seats, apply "
            "immediately. Guaranteed PPO."
        ),
    )
    legit = make_listing(
        title="Frontend Intern",
        organization="Meesho",
        required_skills=["React", "JavaScript"],
        level="third-year",
    )
    matches, _meta = _rank([scam, legit], sample_profile)
    assert matches[-1].trust.level == "high-risk"
    assert matches[-1].pinned_risky is True
    assert matches[0].trust.level != "high-risk"


def test_ranking_hide_risky_removes_high_risk(sample_profile) -> None:
    """hide_risky drops high-risk listings entirely."""
    scam = make_listing(
        organization="Top MNC (name withheld)",
        apply_url="",
        contact_email="https://wa.me/919876543210",
        description="Contact us on Telegram to receive the joining form.",
    )
    legit = make_listing()
    matches, _meta = _rank([scam, legit], sample_profile, hide_risky=True)
    assert [match.listing.organization for match in matches] == ["Nexus Labs"]


def test_ranking_explains_every_match(sample_profile) -> None:
    """Every match carries a 0-100 score, a breakdown and grounded copy."""
    matches, meta = _rank([make_listing()], sample_profile)
    assert len(matches) == 1
    match = matches[0]
    assert 0.0 <= match.score <= 100.0
    breakdown = match.score_breakdown
    assert breakdown.level_fit == 1.0
    assert 0.0 <= breakdown.skill_overlap <= 1.0
    assert "Nexus Labs" in match.why_it_fits
    assert meta["candidates"] == 1


def test_ranking_uses_vectors_when_provided(sample_profile) -> None:
    """Semantic similarity changes the score when vectors are supplied."""
    listing = make_listing()
    profile_vector = np.ones(384, dtype=np.float32)
    profile_vector /= np.linalg.norm(profile_vector)
    near, _ = _rank(
        [listing],
        sample_profile,
        profile_vector=profile_vector,
        listing_vectors=np.vstack([profile_vector]),
    )
    far = -profile_vector
    far_result, _ = _rank(
        [listing],
        sample_profile,
        profile_vector=profile_vector,
        listing_vectors=np.vstack([far]),
    )
    assert near[0].score > far_result[0].score
    assert near[0].score_breakdown.semantic_similarity == 1.0


def test_ranking_caps_results(sample_profile) -> None:
    """limit caps how many matches come back."""
    listings = [
        make_listing(title=f"Intern {index}", organization=f"Org {index}")
        for index in range(15)
    ]
    matches, meta = _rank(listings, sample_profile, limit=5)
    assert len(matches) == 5
    assert meta["returned"] == 5


def test_ranking_handles_empty_catalogue(sample_profile) -> None:
    """An empty catalogue yields an empty result, not an exception."""
    matches, meta = _rank([], sample_profile)
    assert matches == []
    assert meta["returned"] == 0


# ---------------------------------------------------------------------------
# Grounding and embeddings
# ---------------------------------------------------------------------------


def test_fallback_explanation_mentions_only_real_overlaps(sample_profile) -> None:
    """The deterministic explanation never claims a missing skill as a strength."""
    listing = make_listing(required_skills=["React", "Kubernetes"])
    text = heuristic_why_it_fits(sample_profile, listing, ["React"])
    assert "React" in text
    assert "Nexus Labs" in text
    assert "Kubernetes" not in text


def test_hashing_embeddings_are_deterministic_and_related_closer() -> None:
    """The offline embeddings are stable and semantically sensible."""
    first = hashing_embed(["python machine learning internship"])
    second = hashing_embed(["python machine learning internship"])
    assert np.allclose(first, second)

    vectors = hashing_embed(
        [
            "python machine learning data science internship",
            "python machine learning computer vision research",
            "graphic design internship with figma and illustration",
        ]
    )
    related = cosine_similarity(vectors[0], vectors[1])
    unrelated = cosine_similarity(vectors[0], vectors[2])
    assert related > unrelated
