"""Rule-based trust scoring for opportunity listings.

A listing starts at 100 and loses points for each verifiable risk signal.  The
rules are deterministic and every deduction carries a short, human-readable
reason that the UI shows next to the badge.  An optional LLM second opinion can
only lower the score, never raise it above what the rules produced.

Levels: ``>= 75`` verified, ``45-74`` caution, ``< 45`` high-risk.
The product never says a listing is definitely a scam - only that it "shows
risk signals".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from pydantic import BaseModel, Field

import prompts
from models import Trust, TrustFlag

# ---------------------------------------------------------------------------
# Constants used by the rules
# ---------------------------------------------------------------------------

FREE_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.in",
        "yahoo.co.in",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "rediffmail.com",
        "protonmail.com",
        "proton.me",
        "icloud.com",
        "aol.com",
        "yopmail.com",
        "mailinator.com",
        "tempmail.com",
    }
)

#: Domains that hide the true destination of an apply link.
URL_SHORTENERS: frozenset[str] = frozenset(
    {
        "bit.ly",
        "tinyurl.com",
        "t.co",
        "goo.gl",
        "rb.gy",
        "cutt.ly",
        "is.gd",
        "ow.ly",
        "shorturl.at",
        "rebrand.ly",
        "tiny.cc",
        "shorte.st",
        "adf.ly",
    }
)

#: Chat channels that are not a verifiable application destination.
MESSAGING_DOMAINS: frozenset[str] = frozenset(
    {"t.me", "telegram.me", "wa.me", "chat.whatsapp.com", "api.whatsapp.com", "discord.gg"}
)

URGENCY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"apply\s+(?:within|in)\s+(?:\d+|a\s+few)\s*(?:hours?|hrs?|minutes?)",
        r"(?:only|just)\s+\d+\s+(?:seats?|slots?|vacanc(?:y|ies))",
        r"\d+\s+(?:seats?|slots?)\s+(?:left|remaining)",
        r"limited\s+(?:seats?|slots?|time)",
        r"hurry",
        r"last\s+chance",
        r"apply\s+(?:immediately|right\s+away|today)",
        r"approaching\s+fast",
        r"urgent(?:ly)?\s+(?:hiring|requirement|opening)",
    )
)

#: Promises that are implausible for a student opportunity (a distinct signal
#: from mere time pressure: nobody can guarantee an outcome before interviewing).
IMPLAUSIBLE_PROMISE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"guaranteed\s+ppo\b",
        r"guaranteed\s+(?:internship|job)\s+(?:offer|after)",
        r"no\s+interview\s+(?:required|needed|process)",
        r"(?:joining|start)\s+(?:with\s+)?no\s+interview",
        r"immediate\s+joining",
        r"100\s*%\s+(?:placement|job\s+guarantee)",
        r"direct\s+joining",
    )
)

FEE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"registration\s+(?:fee|charge|amount)",
        r"security\s+deposit",
        r"refundable\s+deposit",
        r"(?:training|onboarding|kit|processing|documentation)\s+(?:fee|charge|kit)",
        r"pay\s+(?:a\s+)?(?:fee|₹|rs\.?|inr)",
        r"fee\s+of\s+(?:₹|rs\.?|inr)",
        r"\bdeposit\b",
    )
)

#: Organizations that do not identify themselves - a real risk signal.
VAGUE_ORGANISATIONS: tuple[str, ...] = (
    "confidential",
    "name withheld",
    "top mnc",
    "a leading company",
    "a fast-growing",
    "fast-growing",
    "a tech startup",
    "tech startup",
    "startup (stealth)",
    "stealth startup",
    "unknown",
    "na",
    "n/a",
    "tbd",
)

MONTHS = ("month", "monthly", "per month", "/month", "p.m.")

#: Monthly INR ceiling above which compensation looks implausible, by level.
#: A listing is flagged when the stated amount exceeds 1.8x the ceiling.
MONTHLY_CEILING_INR: dict[str, int] = {
    "first-year": 45_000,
    "second-year": 60_000,
    "third-year": 80_000,
    "final-year": 120_000,
    "any": 90_000,
}

PENALTIES: dict[str, int] = {
    "payment_required": 40,
    "free_email_contact": 20,
    "chat_only_application": 20,
    "unverifiable_apply_url": 15,
    "unrealistic_compensation": 20,
    "urgency_pressure": 10,
    "implausible_promise": 10,
    "missing_org_details": 10,
    "conflicting_duplicates": 10,
}

#: Two independent risk signals downgrade a listing out of "verified"; three or
#: more make it high-risk regardless of how small the individual penalties were.
DENSITY_CAUTION_THRESHOLD = 2
DENSITY_HIGH_RISK_THRESHOLD = 3
CAUTION_SCORE_CAP = 74
HIGH_RISK_SCORE_CAP = 44

#: Penalty attached to a risk signal the LLM found that the rules did not.
AI_FLAG_PENALTY = 5


# ---------------------------------------------------------------------------
# Facts object - lets the same rules run on DB rows and pasted text
# ---------------------------------------------------------------------------


@dataclass
class ListingFacts:
    """The subset of listing fields the trust rules need."""

    title: str = ""
    organization: str = ""
    description: str = ""
    type: str = "internship"
    level: str = "any"
    stipend_or_prize: str | None = None
    apply_url: str = ""
    contact_email: str | None = None
    requires_payment: bool = False
    deadline: date | None = None
    source: str = ""
    mode: str = ""
    location: str = ""
    required_skills: list[str] = field(default_factory=list)
    duplicate_conflict: bool = False

    def to_summary(self) -> str:
        """Compact text block handed to the LLM second-opinion prompt."""
        lines = [
            f"Title: {self.title or '(unknown)'}",
            f"Organization: {self.organization or '(unknown)'}",
            f"Type: {self.type} | Level: {self.level} | Mode: {self.mode or 'unknown'}",
            f"Location: {self.location or 'unknown'}",
            f"Stipend/Prize: {self.stipend_or_prize or 'not stated'}",
            f"Deadline: {self.deadline.isoformat() if self.deadline else 'not stated'}",
            f"Apply URL: {self.apply_url or '(missing)'}",
            f"Contact email: {self.contact_email or '(none)'}",
            f"Requires payment: {self.requires_payment}",
            f"Source: {self.source or 'unknown'}",
            f"Description: {self.description[:900]}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace for comparisons."""
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_org(org: str) -> str:
    """Lowercase an organisation name for duplicate detection."""
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", (org or "").lower())
    cleaned = re.sub(r"\b(?:pvt|private|ltd|limited|inc|llp|technologies|technology)\b", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def opportunity_key(title: str, organization: str) -> tuple[str, str]:
    """Key used to detect the same opportunity reposted by different sources."""
    return normalize_title(title), normalize_org(organization)


def domain_of(url: str) -> str:
    """Extract a lowercase hostname from a URL-ish string, or ``""``."""
    if not url:
        return ""
    candidate = url.strip().lower()
    candidate = re.sub(r"^(?:https?:)?//", "", candidate)
    candidate = candidate.split("/")[0].split("?")[0]
    candidate = candidate.split("@")[-1]
    return candidate.strip(".")


def parse_amount_inr(text: str | None) -> float | None:
    """Parse the first INR amount in a string (handles lakhs, k, commas).

    Examples: ``"₹1,50,000/month"`` -> 150000.0, ``"1.5 lakh"`` -> 150000.0,
    ``"₹50k"`` -> 50000.0, ``"INR 20,000"`` -> 20000.0.
    """
    if not text:
        return None
    lowered = text.lower().replace(",", "")
    match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(lakh|lac|l|k|crore|cr)?", lowered)
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "").strip()
    if unit in {"lakh", "lac", "l"}:
        value *= 100_000
    elif unit == "k":
        value *= 1_000
    elif unit in {"crore", "cr"}:
        value *= 10_000_000
    return value


def _monthly_equivalent_inr(text: str | None) -> float | None:
    """Normalise a compensation string to an approximate monthly INR figure."""
    amount = parse_amount_inr(text)
    if amount is None:
        return None
    lowered = (text or "").lower()
    annual = any(marker in lowered for marker in ("year", "annual", "annum", "lpa", "/yr"))
    if annual:
        return amount / 12.0
    if "week" in lowered:
        return amount * 4.0
    if "day" in lowered:
        return amount * 22.0
    return amount


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------


def rule_payment_required(facts: ListingFacts) -> list[TrustFlag]:
    """Flag listings that ask the student for money to register or 'deposit'."""
    if facts.requires_payment:
        return [
            TrustFlag(
                code="payment_required",
                reason="Requires an upfront payment or 'security deposit' before applying",
                penalty=PENALTIES["payment_required"],
            )
        ]
    combined = f"{facts.description} {facts.stipend_or_prize or ''}"
    if any(pattern.search(combined) for pattern in FEE_PATTERNS):
        return [
            TrustFlag(
                code="payment_required",
                reason="Description mentions a fee or deposit is required from applicants",
                penalty=PENALTIES["payment_required"],
            )
        ]
    return []


def _chat_channel_in(text: str) -> str | None:
    """Return the chat app named in ``text``, if any."""
    lowered = text.lower()
    for channel, pattern in (
        ("Telegram", r"telegram|t\.me"),
        ("WhatsApp", r"whatsapp|wa\.me"),
        ("DM", r"\bdm\b|direct message"),
    ):
        if re.search(pattern, lowered):
            return channel
    return None


def rule_free_email_contact(facts: ListingFacts) -> list[TrustFlag]:
    """Flag when the only contact is a personal/free email provider."""
    email = (facts.contact_email or "").strip()
    if "@" not in email:
        return []
    email_domain = email.split("@")[-1].lower().strip(".")
    if email_domain not in FREE_EMAIL_DOMAINS:
        return []
    return [
        TrustFlag(
            code="free_email_contact",
            reason=f"Only contact is a personal {email_domain} address, not an organisation domain",
            penalty=PENALTIES["free_email_contact"],
        )
    ]


def rule_chat_only_application(facts: ListingFacts) -> list[TrustFlag]:
    """Flag when an application is completed over Telegram/WhatsApp/DM."""
    combined = f"{facts.description} {facts.contact_email or ''} {facts.apply_url or ''}"
    channel = _chat_channel_in(combined)
    if channel is None:
        return []
    # Only a risk when the chat app is the channel rather than a support mention.
    lowered = combined.lower()
    is_channel = any(
        marker in lowered
        for marker in (
            "contact us on",
            "dm ",
            "dm on",
            "dm us",
            "message us",
            "apply via",
            "telegram only",
            "whatsapp only",
            "register on telegram",
            "receive the application form",
            "receive the joining form",
            "wa.me/",
            "t.me/",
        )
    )
    if not is_channel:
        return []
    return [
        TrustFlag(
            code="chat_only_application",
            reason=f"Application is handled over {channel} rather than a verifiable form or portal",
            penalty=PENALTIES["chat_only_application"],
        )
    ]


def rule_apply_url(facts: ListingFacts) -> list[TrustFlag]:
    """Flag missing, shortened or non-web application destinations."""
    url = (facts.apply_url or "").strip()
    if not url:
        return [
            TrustFlag(
                code="unverifiable_apply_url",
                reason="No application link is provided",
                penalty=PENALTIES["unverifiable_apply_url"],
            )
        ]

    host = domain_of(url)
    if not host or "." not in host:
        return [
            TrustFlag(
                code="unverifiable_apply_url",
                reason="Application link has no recognisable domain",
                penalty=PENALTIES["unverifiable_apply_url"],
            )
        ]
    if host in URL_SHORTENERS:
        return [
            TrustFlag(
                code="unverifiable_apply_url",
                reason=f"Apply link is a URL shortener ({host}) that hides the real destination",
                penalty=PENALTIES["unverifiable_apply_url"],
            )
        ]
    if host in MESSAGING_DOMAINS:
        return [
            TrustFlag(
                code="unverifiable_apply_url",
                reason=f"Application happens over a chat link ({host}), not a real careers page",
                penalty=PENALTIES["unverifiable_apply_url"],
            )
        ]
    return []


def rule_compensation(facts: ListingFacts) -> list[TrustFlag]:
    """Flag compensation that is implausible for the role type and level.

    Prize pools and scholarship awards are lump sums; only salaried-style roles
    (internship/job) are compared against a monthly market ceiling.
    """
    text = facts.stipend_or_prize or ""
    lowered = text.lower()
    monthly = _monthly_equivalent_inr(text)
    if monthly is None and not text:
        return []

    is_prize = "prize" in lowered or "pool" in lowered
    is_award = "scholarship" in lowered or "fellowship" in lowered or "grant" in lowered

    if facts.type == "hackathon" or is_prize:
        prize = parse_amount_inr(text) or 0.0
        if prize > 3_000_000:
            return [
                TrustFlag(
                    code="unrealistic_compensation",
                    reason="Stated prize pool is implausible for a student hackathon",
                    penalty=PENALTIES["unrealistic_compensation"],
                )
            ]
        return []

    if facts.type == "scholarship" or is_award:
        award = parse_amount_inr(text) or 0.0
        if award > 600_000:
            return [
                TrustFlag(
                    code="unrealistic_compensation",
                    reason="Scholarship amount is far above typical student scholarships",
                    penalty=PENALTIES["unrealistic_compensation"],
                )
            ]
        return []

    if monthly is None:
        return []

    ceiling = MONTHLY_CEILING_INR.get(facts.level, MONTHLY_CEILING_INR["any"])
    if monthly > ceiling * 1.8:
        return [
            TrustFlag(
                code="unrealistic_compensation",
                reason=(
                    f"Pay of about ₹{int(monthly):,}/month is far above the market for a "
                    f"{facts.level} {facts.type}"
                ),
                penalty=PENALTIES["unrealistic_compensation"],
            )
        ]
    return []


def rule_urgency(facts: ListingFacts) -> list[TrustFlag]:
    """Flag artificial time pressure in the description."""
    combined = f"{facts.title} {facts.description}"
    for pattern in URGENCY_PATTERNS:
        match = pattern.search(combined)
        if match:
            return [
                TrustFlag(
                    code="urgency_pressure",
                    reason=f'Uses pressure language ("{match.group(0).strip()[:48]}")',
                    penalty=PENALTIES["urgency_pressure"],
                )
            ]
    return []


def rule_implausible_promise(facts: ListingFacts) -> list[TrustFlag]:
    """Flag promises no legitimate employer can make before interviewing."""
    combined = f"{facts.title} {facts.description}"
    for pattern in IMPLAUSIBLE_PROMISE_PATTERNS:
        match = pattern.search(combined)
        if match:
            return [
                TrustFlag(
                    code="implausible_promise",
                    reason=f'Promises an outcome upfront ("{match.group(0).strip()[:48]}")',
                    penalty=PENALTIES["implausible_promise"],
                )
            ]
    return []


def _first_vague_phrase(org: str) -> str | None:
    """Return the vague phrase inside ``org``, using word boundaries."""
    lowered = org.lower()
    for phrase in VAGUE_ORGANISATIONS:
        if re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", lowered):
            return phrase
    return None


def rule_org_details(facts: ListingFacts) -> list[TrustFlag]:
    """Flag listings from organisations that do not identify themselves."""
    org = (facts.organization or "").strip()
    if not org:
        return [
            TrustFlag(
                code="missing_org_details",
                reason="No organisation name is given",
                penalty=PENALTIES["missing_org_details"],
            )
        ]
    if _first_vague_phrase(org) and len(org) < 45:
        return [
            TrustFlag(
                code="missing_org_details",
                reason=f'Organisation is not identifiable ("{org[:48]}")',
                penalty=PENALTIES["missing_org_details"],
            )
        ]
    return []


def rule_duplicates(facts: ListingFacts) -> list[TrustFlag]:
    """Flag the same opportunity listed by multiple sources with conflicting details."""
    if not facts.duplicate_conflict:
        return []
    return [
        TrustFlag(
            code="conflicting_duplicates",
            reason="Same opportunity appears on multiple sources with conflicting details",
            penalty=PENALTIES["conflicting_duplicates"],
        )
    ]


def rule_expired(facts: ListingFacts, today: date | None = None) -> list[TrustFlag]:
    """Flag expired deadlines - informational, never treated as a scam signal."""
    today = today or date.today()
    if facts.deadline is not None and facts.deadline < today:
        return [
            TrustFlag(
                code="expired",
                reason=f"Deadline passed on {facts.deadline.isoformat()}",
                penalty=0,
            )
        ]
    return []


#: Rules applied in order.  Each returns zero or one flag.
RULES = (
    rule_payment_required,
    rule_free_email_contact,
    rule_chat_only_application,
    rule_apply_url,
    rule_compensation,
    rule_urgency,
    rule_implausible_promise,
    rule_org_details,
    rule_duplicates,
    rule_expired,
)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def level_from_score(score: int) -> str:
    """Map a numeric trust score to ``verified`` / ``caution`` / ``high-risk``."""
    if score >= 75:
        return "verified"
    if score >= 45:
        return "caution"
    return "high-risk"


def score_from_flags(flags: Iterable[TrustFlag]) -> int:
    """Start at 100 and subtract each flag's penalty (never below 0)."""
    total = 100 - sum(flag.penalty for flag in flags)
    return max(0, min(100, total))


def _finalise_trust(flags: list[TrustFlag], *, score_cap: int | None = None) -> Trust:
    """Turn a flag list into a scored, density-adjusted :class:`Trust`."""
    score = score_from_flags(flags)
    if score_cap is not None:
        score = min(score, score_cap)

    risk_flags = [flag for flag in flags if flag.penalty > 0]
    level = level_from_score(score)

    if len(risk_flags) >= DENSITY_HIGH_RISK_THRESHOLD:
        level = "high-risk"
        score = min(score, HIGH_RISK_SCORE_CAP)
    elif len(risk_flags) >= DENSITY_CAUTION_THRESHOLD and level == "verified":
        level = "caution"
        score = min(score, CAUTION_SCORE_CAP)

    return Trust(score=score, level=level, flags=flags)


def assess_facts(facts: ListingFacts, today: date | None = None) -> Trust:
    """Run every rule against a :class:`ListingFacts` and build a :class:`Trust`.

    Scoring is additive (100 minus penalties) and then density-adjusted: two
    independent risk signals can never be ``verified``, and three or more are
    always ``high-risk``. This keeps single weak signals mild while making
    listings that pile up red flags unmistakable.
    """
    flags: list[TrustFlag] = []
    for rule in RULES:
        if rule is rule_expired:
            flags.extend(rule(facts, today))  # type: ignore[call-arg]
        else:
            flags.extend(rule(facts))  # type: ignore[operator]
    return _finalise_trust(flags)


def facts_from_listing(listing: Any, *, duplicate_conflict: bool = False) -> ListingFacts:
    """Adapt an ORM ``Listing`` (or any object with those attributes)."""
    return ListingFacts(
        title=getattr(listing, "title", "") or "",
        organization=getattr(listing, "organization", "") or "",
        description=getattr(listing, "description", "") or "",
        type=getattr(listing, "type", "internship") or "internship",
        level=getattr(listing, "level", "any") or "any",
        stipend_or_prize=getattr(listing, "stipend_or_prize", None),
        apply_url=getattr(listing, "apply_url", "") or "",
        contact_email=getattr(listing, "contact_email", None),
        requires_payment=bool(getattr(listing, "requires_payment", False)),
        deadline=getattr(listing, "deadline", None),
        source=getattr(listing, "source", "") or "",
        mode=getattr(listing, "mode", "") or "",
        location=getattr(listing, "location", "") or "",
        required_skills=list(getattr(listing, "required_skills", []) or []),
        duplicate_conflict=duplicate_conflict,
    )


def assess_listing(listing: Any, *, duplicate_conflict: bool = False) -> Trust:
    """Convenience wrapper: ORM listing in, :class:`Trust` out."""
    return assess_facts(facts_from_listing(listing, duplicate_conflict=duplicate_conflict))


# ---------------------------------------------------------------------------
# Pasted-text verification
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)


def facts_from_text(text: str) -> ListingFacts:
    """Best-effort extraction of listing facts from free-form pasted text.

    Used by ``POST /api/verify`` so a student can check a listing found
    anywhere (a chat forward, a screenshot transcription, an email).
    """
    raw = (text or "").strip()
    emails = [match.rstrip(".,;:") for match in _EMAIL_RE.findall(raw)]
    urls = [match.rstrip(".,;:") for match in _URL_RE.findall(raw)]

    contact_email = next((email for email in emails if "@" in email), None)
    apply_url = ""
    for url in urls:
        host = domain_of(url)
        if host and not any(marker in host for marker in ("telegram", "whatsapp")):
            apply_url = url
            break
    if not apply_url and urls:
        apply_url = urls[0]

    lowered = raw.lower()
    type_guess = "internship"
    if "hackathon" in lowered:
        type_guess = "hackathon"
    elif any(word in lowered for word in ("scholarship", "fellowship", "grant")):
        type_guess = "scholarship"
    elif any(word in lowered for word in ("full-time", "full time", "job opening")):
        type_guess = "job"

    level = "any"
    for token, value in (
        ("first-year", "first-year"),
        ("second-year", "second-year"),
        ("third-year", "third-year"),
        ("final-year", "final-year"),
    ):
        if token.replace("-", " ") in lowered:
            level = value
            break

    money_line = ""
    for line in raw.splitlines():
        if any(symbol in line for symbol in ("₹", "rs", "inr", "lpa", "lakh")):
            money_line = line.strip()
            break

    org_guess = ""
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(("company:", "organisation:", "organization:", "employer:")):
            org_guess = stripped.split(":", 1)[1].strip()
            break

    return ListingFacts(
        title=raw.splitlines()[0].strip()[:180] if raw else "",
        organization=org_guess,
        description=raw,
        type=type_guess,
        level=level,
        stipend_or_prize=money_line or None,
        apply_url=apply_url,
        contact_email=contact_email,
        requires_payment=any(pattern.search(raw) for pattern in FEE_PATTERNS),
        deadline=None,
    )


def assess_text(text: str) -> Trust:
    """Verify a pasted listing description with the same rule engine."""
    return assess_facts(facts_from_text(text))


# ---------------------------------------------------------------------------
# Optional LLM second opinion
# ---------------------------------------------------------------------------


def apply_llm_flags(base: Trust, extra: list[dict[str, Any]], adjustment: int) -> Trust:
    """Merge LLM-identified flags into a rule-based trust result.

    The LLM may only *lower* the score: negative adjustments are honoured,
    positive ones are ignored, and the final score never exceeds the rule score.
    """
    flags = list(base.flags)
    for item in extra[:2]:
        code = str(item.get("code") or "ai_risk_signal")[:64]
        reason = str(item.get("reason") or "").strip()[:180]
        if not reason:
            continue
        if any(existing.code == code for existing in flags):
            continue
        flags.append(TrustFlag(code=code, reason=reason, penalty=AI_FLAG_PENALTY))

    if adjustment < 0:
        # Fold the adjustment in as an extra deduction so density still applies.
        flags.append(
            TrustFlag(
                code="ai_severity_adjustment",
                reason="An additional risk review lowered the confidence in this listing",
                penalty=abs(int(adjustment)),
            )
        )
    return _finalise_trust(flags, score_cap=base.score)


# ---------------------------------------------------------------------------
# LLM second opinion
# ---------------------------------------------------------------------------


class SecondOpinion(BaseModel):
    """LLM output schema for the optional verification second opinion."""

    extra_flags: list[dict[str, Any]] = Field(default_factory=list)
    score_adjustment: int = 0
    summary: str = ""


async def second_opinion(
    facts: ListingFacts,
    trust: Trust,
    *,
    client: Any,
) -> tuple[Trust, bool, str | None]:
    """Ask the LLM for risk signals the rules may have missed.

    The result can only lower the score (see :func:`apply_llm_flags`). In mock
    mode or on failure the rule-based trust is returned unchanged.
    """
    if client.mock_mode:
        # The rule engine alone produces a complete verdict; the LLM adds an
        # optional second opinion. In mock mode nothing is missing from the
        # user's perspective, so do not surface an "AI unavailable" state.
        return trust, True, "Mock mode: rule-based verification only."

    flag_text = "; ".join(f"{flag.code}: {flag.reason}" for flag in trust.flags) or "none"
    result = await client.complete_json(
        task="verify_second_opinion",
        system=prompts.VERIFY_SECOND_OPINION_SYSTEM,
        user=prompts.VERIFY_SECOND_OPINION_USER.format(
            listing_summary=facts.to_summary(), score=trust.score, flags=flag_text
        ),
        schema=SecondOpinion,
        fallback=lambda: {"extra_flags": [], "score_adjustment": 0, "summary": ""},
        max_tokens=900,
    )
    if not result.ai_available:
        return trust, False, result.note

    merged = apply_llm_flags(
        trust, list(result.value.extra_flags or []), int(result.value.score_adjustment or 0)
    )
    return merged, True, None

