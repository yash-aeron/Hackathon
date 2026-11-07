"""Trust-rule tests: the risk signals that keep scams off the top of the list."""

from __future__ import annotations

from datetime import date

import pytest

from verify import (
    ListingFacts,
    assess_facts,
    assess_text,
    facts_from_listing,
    level_from_score,
    parse_amount_inr,
    score_from_flags,
)


def clean_facts(**overrides: object) -> ListingFacts:
    """A listing that should score as verified, with fields overridable per test."""
    base = ListingFacts(
        title="Frontend Developer Intern",
        organization="TechNova Solutions",
        description="Build React interfaces with the product team.",
        type="internship",
        level="third-year",
        stipend_or_prize="₹35,000/month",
        apply_url="https://technova.example/careers",
        contact_email="careers@technova.example",
        deadline=date(2026, 12, 15),
        source="Internshala",
        mode="remote",
        location="Remote",
        required_skills=["React", "TypeScript"],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def flag_codes(facts: ListingFacts) -> set[str]:
    return {flag.code for flag in assess_facts(facts, today=date(2026, 11, 7)).flags}


def test_clean_listing_is_verified() -> None:
    trust = assess_facts(clean_facts(), today=date(2026, 11, 7))
    assert trust.level == "verified"
    assert trust.score == 100
    assert trust.flags == []


def test_payment_demand_is_the_heaviest_signal() -> None:
    trust = assess_facts(clean_facts(requires_payment=True), today=date(2026, 11, 7))
    assert "payment_required" in {flag.code for flag in trust.flags}
    assert trust.score <= 60
    assert trust.level != "verified"


def test_payment_mentioned_in_description_alone_is_flagged() -> None:
    facts = clean_facts(
        description="Pay a refundable security deposit of ₹2,000 to confirm your seat."
    )
    assert "payment_required" in flag_codes(facts)


def test_free_email_contact_is_flagged() -> None:
    facts = clean_facts(contact_email="technova.hr@gmail.com")
    assert "free_email_contact" in flag_codes(facts)


def test_chat_only_application_is_flagged() -> None:
    facts = clean_facts(apply_url="https://t.me/technova_hiring")
    codes = flag_codes(facts)
    assert "chat_only_application" in codes
    assert "unverifiable_apply_url" in codes


def test_url_shortener_is_unverifiable() -> None:
    facts = clean_facts(apply_url="https://bit.ly/apply-now")
    assert "unverifiable_apply_url" in flag_codes(facts)


def test_urgency_and_implausible_promises_are_separate_signals() -> None:
    facts = clean_facts(
        description=(
            "Only 3 seats left - apply within 24 hours. Guaranteed internship offer "
            "after training with immediate joining."
        )
    )
    codes = flag_codes(facts)
    assert "urgency_pressure" in codes
    assert "implausible_promise" in codes


def test_vague_organisation_is_flagged() -> None:
    facts = clean_facts(organization="Confidential")
    assert "missing_org_details" in flag_codes(facts)


def test_expired_listing_is_flagged() -> None:
    facts = clean_facts(deadline=date(2026, 1, 1))
    assert "expired" in flag_codes(facts)


def test_density_rule_downgrades_stacked_signals() -> None:
    # Two independent signals can never stay "verified".
    two = clean_facts(
        contact_email="technova.hr@gmail.com",
        description="Only 3 seats left, apply within 24 hours.",
    )
    trust = assess_facts(two, today=date(2026, 11, 7))
    assert len(trust.flags) >= 2
    assert trust.level == "caution"
    assert trust.score <= 74

    # Three or more are always high-risk, however small each penalty is.
    three = clean_facts(
        organization="A leading company",
        contact_email="technova.hr@gmail.com",
        description="Only 3 seats left, apply within 24 hours.",
    )
    trust = assess_facts(three, today=date(2026, 11, 7))
    assert len(trust.flags) >= 3
    assert trust.level == "high-risk"
    assert trust.score <= 44


def test_level_thresholds() -> None:
    assert level_from_score(100) == "verified"
    assert level_from_score(75) == "verified"
    assert level_from_score(74) == "caution"
    assert level_from_score(45) == "caution"
    assert level_from_score(44) == "high-risk"


def test_score_never_goes_below_zero() -> None:
    facts = clean_facts(
        organization="Confidential",
        contact_email="hr@yopmail.com",
        apply_url="https://t.me/join",
        requires_payment=True,
        description=(
            "Registration fee of ₹5,000. Only 2 seats left. Guaranteed PPO. "
            "₹5,00,000 per month salary."
        ),
    )
    trust = assess_facts(facts, today=date(2026, 11, 7))
    assert trust.score == 0
    assert trust.level == "high-risk"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("₹1,50,000/month", 150_000.0),
        ("1.5 lakh", 150_000.0),
        ("₹50k", 50_000.0),
        ("INR 20,000", 20_000.0),
        ("no numbers here", None),
        (None, None),
    ],
)
def test_parse_amount_inr(text: str | None, expected: float | None) -> None:
    assert parse_amount_inr(text) == expected


def test_pasted_text_verification_flags_a_payment_scam() -> None:
    trust = assess_text(
        "Work from home internship at Global Tech. Earn 50k/month guaranteed! "
        "Pay Rs 499 registration fee to confirm your slot. "
        "Contact hr@globaltech-intern.example"
    )
    codes = {flag.code for flag in trust.flags}
    assert "payment_required" in codes
    assert trust.level in {"caution", "high-risk"}


def test_pasted_text_verification_passes_a_clean_listing() -> None:
    trust = assess_text(
        "Frontend Developer Intern at TechNova Solutions. Build React and TypeScript "
        "interfaces with the product team. Stipend ₹35,000 per month. "
        "Apply at https://technova.example/careers/frontend-intern by 15 Dec 2026. "
        "Contact careers@technova.example"
    )
    assert trust.level != "high-risk"
    assert "payment_required" not in {flag.code for flag in trust.flags}


def test_facts_from_listing_copies_every_rule_input(listing) -> None:
    facts = facts_from_listing(listing)
    assert facts.title == listing.title
    assert facts.required_skills == listing.required_skills
    assert facts.deadline == listing.deadline


def test_score_from_flags_sums_penalties() -> None:
    trust = assess_facts(clean_facts(requires_payment=True), today=date.today())
    assert score_from_flags(trust.flags) == trust.score


def test_future_deadline_is_not_expired() -> None:
    facts = clean_facts(deadline=date(2026, 11, 17))
    assert "expired" not in flag_codes(facts)
