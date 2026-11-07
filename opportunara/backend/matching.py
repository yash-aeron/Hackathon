"""Explainable, mostly-deterministic matching.

Final score (scaled to 0-100)::

    0.45 * semantic_similarity + 0.30 * skill_overlap
  + 0.15 * level_fit          + 0.10 * deadline_urgency

* ``semantic_similarity`` - cosine between the profile document (skills +
  projects + interests) and the listing document, both embedded locally with
  ``all-MiniLM-L6-v2``.
* ``skill_overlap`` - share of the listing's required skills the profile covers,
  after lowercase normalisation and a small synonym map.
* ``level_fit`` - 1.0 exact or "any", 0.5 adjacent year, 0.2 otherwise.
* ``deadline_urgency`` - peaks for deadlines 3-14 days away, 0 once expired.

Hard filters drop expired listings and collapse near-duplicates before ranking.
High-risk listings are kept but pinned below legitimate results (unless the
caller asks to hide them), so scam detection stays visible in the demo.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
from collections import Counter
from datetime import date
from typing import Any, Iterable, Sequence

import numpy as np
from pydantic import BaseModel, Field

import prompts
from llm import LLMClient
from models import (
    Listing,
    ListingOut,
    MatchFilters,
    MatchOut,
    ScoreBreakdown,
    StudentProfile,
    WeightedBreakdown,
)
from verify import (
    assess_listing,
    normalize_org,
    normalize_title,
    opportunity_key,
)

logger = logging.getLogger("scoutly.matching")

EMBEDDING_DIM = 384
PRIMARY_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
HASHING_MODEL_NAME = "hashing-tfidf-v1"

WEIGHTS: dict[str, float] = {
    "semantic_similarity": 0.45,
    "skill_overlap": 0.30,
    "level_fit": 0.15,
    "deadline_urgency": 0.10,
}

# ---------------------------------------------------------------------------
# Skill normalisation
# ---------------------------------------------------------------------------

#: Maps common variants onto one canonical token. Lowercase keys.
SKILL_SYNONYMS: dict[str, str] = {
    "js": "javascript",
    "java script": "javascript",
    "ts": "typescript",
    "node": "node.js",
    "nodejs": "node.js",
    "node js": "node.js",
    "reactjs": "react",
    "react js": "react",
    "nextjs": "next.js",
    "next js": "next.js",
    "py": "python",
    "python3": "python",
    "ml": "machine learning",
    "machine-learning": "machine learning",
    "machinelearning": "machine learning",
    "dl": "deep learning",
    "deep-learning": "deep learning",
    "ai": "artificial intelligence",
    "artificial intelligence": "artificial intelligence",
    "gen ai": "generative ai",
    "genai": "generative ai",
    "llms": "llm",
    "large language models": "llm",
    "nlp": "natural language processing",
    "natural-language-processing": "natural language processing",
    "cv": "computer vision",
    "computer-vision": "computer vision",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "sci-kit learn": "scikit-learn",
    "tf": "tensorflow",
    "tensor flow": "tensorflow",
    "torch": "pytorch",
    "py torch": "pytorch",
    "postgres": "postgresql",
    "psql": "postgresql",
    "mongo": "mongodb",
    "mongo db": "mongodb",
    "k8s": "kubernetes",
    "aws": "amazon web services",
    "gcp": "google cloud platform",
    "google cloud": "google cloud platform",
    "azure": "microsoft azure",
    "dsa": "data structures and algorithms",
    "ds": "data structures",
    "data structures": "data structures and algorithms",
    "algo": "algorithms",
    "oop": "object oriented programming",
    "oops": "object oriented programming",
    "rest": "rest api",
    "restful": "rest api",
    "apis": "rest api",
    "html5": "html",
    "css3": "css",
    "tailwind": "tailwind css",
    "tailwindcss": "tailwind css",
    "rb": "ruby",
    "golang": "go",
    "excel": "microsoft excel",
    "powerbi": "power bi",
    "power-bi": "power bi",
    "figma": "figma",
    "ui": "ui design",
    "ux": "ux design",
    "ui/ux": "ui/ux design",
    "ux/ui": "ui/ux design",
    "ci cd": "ci/cd",
    "cicd": "ci/cd",
    "devops": "devops",
    "qa": "quality assurance",
    "sql server": "sql",
    "mysql": "sql",
    "sqlite": "sql",
}

_ALLOWED_SKILL_CHARS = re.compile(r"[^a-z0-9+#./ ]+")
_SPACE_RE = re.compile(r"\s+")


def normalize_skill(skill: str) -> str:
    """Lowercase and canonicalise a single skill token.

    ``"Node.js"``, ``"NodeJS"`` and ``"node js"`` all normalise to ``"node.js"``.
    """
    if not skill:
        return ""
    lowered = str(skill).strip().lower().replace("&", " and ")
    lowered = _ALLOWED_SKILL_CHARS.sub(" ", lowered)
    lowered = _SPACE_RE.sub(" ", lowered).strip()
    lowered = lowered.strip(". ")
    if not lowered:
        return ""
    if lowered in SKILL_SYNONYMS:
        return SKILL_SYNONYMS[lowered]
    spaced = lowered.replace(".", " ").replace("/", " ").strip()
    spaced = _SPACE_RE.sub(" ", spaced)
    return SKILL_SYNONYMS.get(spaced, lowered)


def normalize_skills(skills: Iterable[str]) -> set[str]:
    """Normalise a list of skills into a de-duplicated set."""
    return {normalized for skill in skills if (normalized := normalize_skill(skill))}


def skill_overlap(
    required_skills: Sequence[str], profile_skills: Iterable[str]
) -> tuple[float, list[str], list[str]]:
    """Fraction of required skills covered by the profile.

    Args:
        required_skills: Skills the listing asks for (display strings).
        profile_skills: Skills the student has.

    Returns:
        ``(ratio, matched_display_skills, missing_display_skills)``. When the
        listing requires no skills the ratio is a neutral ``0.5`` so that a
        skill-less hackathon is neither rewarded nor punished.
    """
    required_display = [skill for skill in required_skills if str(skill).strip()]
    if not required_display:
        return 0.5, [], []

    profile_set = normalize_skills(profile_skills)
    matched: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    for skill in required_display:
        canonical = normalize_skill(skill)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        if canonical in profile_set:
            matched.append(str(skill).strip())
        else:
            missing.append(str(skill).strip())

    total = len(seen) or 1
    return len(matched) / total, matched, missing


# ---------------------------------------------------------------------------
# Level and deadline components
# ---------------------------------------------------------------------------

_YEAR_ORDER = ["first-year", "second-year", "third-year", "final-year"]

_YEAR_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:1st|first)[\s-]*(?:year|yr)\b", re.I), "first-year"),
    (re.compile(r"\b(?:2nd|second)[\s-]*(?:year|yr)\b", re.I), "second-year"),
    (re.compile(r"\b(?:3rd|third)[\s-]*(?:year|yr)\b", re.I), "third-year"),
    (re.compile(r"\b(?:4th|fourth|final|last)[\s-]*(?:year|yr)\b", re.I), "final-year"),
)


def canonical_year(value: str) -> str | None:
    """Extract a canonical year label from free text like ``"3rd year"``."""
    if not value:
        return None
    lowered = value.lower()
    for pattern, label in _YEAR_PATTERNS:
        if pattern.search(lowered):
            return label
    if "fresher" in lowered or "graduate" in lowered:
        return "final-year"
    return None


def level_fit(profile_year: str | None, listing_level: str | None) -> float:
    """Score how well the student's year matches the listing's target level.

    1.0 for an exact match or an "any" listing, 0.5 for an adjacent year,
    0.2 otherwise. Unknown profile year scores a neutral 0.5.
    """
    listing = (listing_level or "any").strip().lower()
    if listing == "any":
        return 1.0

    student = canonical_year(profile_year or "")
    if student is None:
        return 0.5
    if student == listing:
        return 1.0

    try:
        distance = abs(_YEAR_ORDER.index(student) - _YEAR_ORDER.index(listing))
    except ValueError:
        return 0.2
    return 0.5 if distance == 1 else 0.2


def deadline_urgency(days_left: int) -> float:
    """Deadline pressure in 0..1, peaking for deadlines 3-14 days away."""
    if days_left < 0:
        return 0.0
    if days_left < 3:
        return 0.4
    if days_left <= 14:
        return round(0.7 + 0.3 * (1 - abs(days_left - 8) / 6), 4)
    if days_left <= 30:
        return round(0.6 - ((days_left - 14) / 16) * 0.35, 4)
    return 0.1


def compute_score(
    semantic_similarity: float,
    skill_overlap_ratio: float,
    level_fit_score: float,
    urgency: float,
) -> tuple[float, ScoreBreakdown]:
    """Blend the four components into a 0-100 score plus a full breakdown."""
    semantic = float(np.clip(semantic_similarity, 0.0, 1.0))
    skills = float(np.clip(skill_overlap_ratio, 0.0, 1.0))
    level = float(np.clip(level_fit_score, 0.0, 1.0))
    urgency_clipped = float(np.clip(urgency, 0.0, 1.0))

    weighted = WeightedBreakdown(
        semantic_similarity=round(semantic * WEIGHTS["semantic_similarity"] * 100, 2),
        skill_overlap=round(skills * WEIGHTS["skill_overlap"] * 100, 2),
        level_fit=round(level * WEIGHTS["level_fit"] * 100, 2),
        deadline_urgency=round(urgency_clipped * WEIGHTS["deadline_urgency"] * 100, 2),
    )
    total = (
        weighted.semantic_similarity
        + weighted.skill_overlap
        + weighted.level_fit
        + weighted.deadline_urgency
    )
    breakdown = ScoreBreakdown(
        semantic_similarity=round(semantic, 4),
        skill_overlap=round(skills, 4),
        level_fit=round(level, 4),
        deadline_urgency=round(urgency_clipped, 4),
        weighted=weighted,
    )
    return round(float(total), 1), breakdown


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


def profile_document(profile: StudentProfile) -> str:
    """Text representation of a profile, used for its embedding."""
    education = profile.education
    parts = [
        f"Student: {profile.name}",
        f"Degree: {education.degree} at {education.college} ({education.year})",
        f"Skills: {', '.join(profile.skills)}",
    ]
    if profile.projects:
        project_text = "; ".join(
            f"{project.name} - {project.summary} ({', '.join(project.tech)})"
            for project in profile.projects
        )
        parts.append(f"Projects: {project_text}")
    if profile.experience:
        parts.append(f"Experience: {', '.join(profile.experience)}")
    if profile.interests:
        parts.append(f"Interests: {', '.join(profile.interests)}")
    if profile.target_types:
        parts.append(f"Looking for: {', '.join(profile.target_types)}")
    if profile.location_pref:
        parts.append(f"Location preference: {profile.location_pref}")
    return "\n".join(parts)


def listing_document(listing: Any) -> str:
    """Text representation of a listing, used for its embedding."""
    skills = ", ".join(getattr(listing, "required_skills", []) or [])
    return (
        f"{getattr(listing, 'title', '')} at {getattr(listing, 'organization', '')}. "
        f"Type: {getattr(listing, 'type', '')}. "
        f"Level: {getattr(listing, 'level', '')}. "
        f"Location: {getattr(listing, 'location', '')} ({getattr(listing, 'mode', '')}). "
        f"Required skills: {skills}. "
        f"{getattr(listing, 'description', '')}"
    ).strip()


def hashing_embed(texts: Sequence[str], dim: int = EMBEDDING_DIM) -> np.ndarray:
    """Deterministic offline embedding (sublinear TF + hashed features).

    Used when ``sentence-transformers`` is unavailable so the app still ranks
    sensibly instead of failing. Vectors are L2-normalised.
    """
    matrix = np.zeros((len(texts), dim), dtype=np.float32)
    token_re = re.compile(r"[a-z0-9+#.]+")
    for row, text in enumerate(texts):
        tokens = token_re.findall((text or "").lower())
        if not tokens:
            continue
        counts = Counter(tokens)
        for token, count in counts.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            matrix[row, index] += sign * (1.0 + math.log(count))
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


class EmbeddingEngine:
    """Lazy wrapper around sentence-transformers with an offline fallback."""

    def __init__(self, model_name: str = PRIMARY_MODEL_NAME, *, prefer_hashing: bool = False) -> None:
        self.model_name = model_name
        self.prefer_hashing = prefer_hashing
        self._model: Any = None
        self._backend = ""
        self._lock = threading.Lock()

    @property
    def backend(self) -> str:
        """Name of the backend actually in use (loads the model on first use)."""
        if not self._backend:
            self._load()
        return self._backend

    def _load(self) -> None:
        with self._lock:
            if self._backend:
                return
            if self.prefer_hashing:
                self._model = None
                self._backend = "hashing"
                logger.info("Embeddings backend forced to hashing by EMBEDDING_BACKEND")
                return
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                self._backend = "sentence-transformers"
                logger.info("Embeddings backend: sentence-transformers (%s)", self.model_name)
            except Exception as exc:  # ImportError, download failure, torch missing...
                logger.warning(
                    "sentence-transformers unavailable (%s); falling back to hashing embeddings",
                    exc,
                )
                self._model = None
                self._backend = "hashing"

    @property
    def storage_model_name(self) -> str:
        """Key stored alongside vectors so a backend change invalidates the cache."""
        return self.model_name if self.backend == "sentence-transformers" else HASHING_MODEL_NAME

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Embed a batch of texts into an ``(n, dim)`` float32 matrix."""
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        if not self._backend:
            self._load()
        if self._model is not None:
            try:
                vectors = self._model.encode(
                    list(texts),
                    normalize_embeddings=True,
                    batch_size=32,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
                return np.asarray(vectors, dtype=np.float32)
            except Exception as exc:  # pragma: no cover - runtime guard
                logger.warning("SentenceTransformer encode failed (%s); using hashing", exc)
                self._model = None
                self._backend = "hashing"
        return hashing_embed(texts)


_engine: EmbeddingEngine | None = None


def get_embedding_engine() -> EmbeddingEngine:
    """Return the process-wide embedding engine singleton."""
    global _engine
    if _engine is None:
        from config import get_settings

        settings = get_settings()
        _engine = EmbeddingEngine(
            settings.embedding_model,
            prefer_hashing=settings.embedding_backend.strip().lower() == "hashing",
        )
    return _engine


def reset_embedding_engine() -> None:
    """Drop the cached engine (tests)."""
    global _engine
    _engine = None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors, clamped to 0..1."""
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, 0.0, 1.0))


#: Raw MiniLM cosine between a resume and a listing mostly sits in 0.1-0.5, which
#: would make excellent matches look mediocre. These bounds rescale that observed
#: band onto 0..1 so the 0-100 score is meaningful. Documented in the README.
SEMANTIC_FLOOR = 0.05
SEMANTIC_CEILING = 0.45


def calibrate_semantic(raw_cosine: float) -> float:
    """Map an observed embedding cosine onto the useful 0..1 range."""
    span = SEMANTIC_CEILING - SEMANTIC_FLOOR
    return float(np.clip((raw_cosine - SEMANTIC_FLOOR) / span, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Duplicate collapsing
# ---------------------------------------------------------------------------


def _obj_id(listing: Any) -> int:
    """Stable integer id for a listing, tolerating unsaved ORM objects."""
    value = getattr(listing, "id", None)
    if isinstance(value, int):
        return value
    return id(listing)


def duplicate_conflict_ids(listings: Sequence[Any]) -> set[int]:
    """Ids of listings that are reposted by another source with different details.

    "Conflicting" means the reposts disagree on compensation - a classic signal
    that one of them has been altered.
    """
    groups: dict[tuple[str, str], list[Any]] = {}
    for listing in listings:
        key = opportunity_key(
            getattr(listing, "title", ""), getattr(listing, "organization", "")
        )
        groups.setdefault(key, []).append(listing)

    conflicting: set[int] = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        stipends = {(getattr(m, "stipend_or_prize", None) or "").strip().lower() for m in members}
        if len(stipends) > 1:
            conflicting.update(_obj_id(member) for member in members)
    return conflicting


def collapse_duplicates(
    listings: Sequence[Any],
) -> tuple[list[Any], dict[int, Any], set[int]]:
    """Collapse near-duplicates, keeping the higher-trust repost.

    Returns:
        ``(kept_listings, kept_by_original_id, conflicting_ids)`` where
        ``kept_by_original_id`` maps every surviving id to itself (used by
        callers that need an id -> listing lookup).
    """
    conflicts = duplicate_conflict_ids(listings)
    groups: dict[tuple[str, str], list[Any]] = {}

    for listing in listings:
        key = opportunity_key(
            getattr(listing, "title", ""), getattr(listing, "organization", "")
        )
        groups.setdefault(key, []).append(listing)

    kept: list[Any] = []
    index: dict[int, Any] = {}
    for members in groups.values():
        if len(members) == 1:
            selected = members[0]
        else:
            # Higher trust wins; ties break on the more complete description.
            selected = max(
                members,
                key=lambda m: (
                    assess_listing(m, duplicate_conflict=_obj_id(m) in conflicts).score,
                    len(getattr(m, "description", "") or ""),
                    -_obj_id(m),
                ),
            )
        kept.append(selected)
        index[_obj_id(selected)] = selected

    kept.sort(key=lambda m: _obj_id(m))
    return kept, index, conflicts


def _days_left(deadline: date | None, today: date) -> int:
    if deadline is None:
        return 999
    return (deadline - today).days


# ---------------------------------------------------------------------------
# Why-it-fits fallback copy
# ---------------------------------------------------------------------------


def heuristic_why_it_fits(
    profile: StudentProfile, listing: Any, matched: Sequence[str]
) -> str:
    """Deterministic two-sentence "why it fits" used in mock/failure mode.

    Grounded strictly in the profile and listing - no invented claims.
    """
    title = getattr(listing, "title", "this role")
    org = getattr(listing, "organization", "the organisation")
    matched_list = [str(skill) for skill in matched if str(skill).strip()]

    if matched_list:
        first = (
            f"{title} at {org} asks for {', '.join(matched_list[:3])}, "
            f"which already appear in your profile."
        )
    else:
        first = (
            f"{title} at {org} does not overlap directly with your listed skills, "
            f"so treat it as a stretch opportunity."
        )

    projects = [project.name for project in profile.projects if project.name]
    year = profile.education.year or "your current year"
    if projects:
        second = (
            f"It targets {getattr(listing, 'level', 'any')} candidates, "
            f"and your {projects[0]} project is the closest evidence you have for it."
        )
    else:
        second = (
            f"It targets {getattr(listing, 'level', 'any')} candidates, "
            f"which lines up with {year}."
        )
    return f"{first} {second}"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def _listing_out(listing: Any) -> ListingOut:
    """Adapt an ORM listing (possibly unsaved) to the wire model."""
    if isinstance(listing, ListingOut):
        return listing

    def value(field: str, default: Any) -> Any:
        found = getattr(listing, field, None)
        return default if found is None else found

    return ListingOut(
        id=_obj_id(listing),
        title=value("title", ""),
        organization=value("organization", ""),
        type=value("type", "internship"),
        description=value("description", ""),
        required_skills=list(value("required_skills", [])),
        level=value("level", "any"),
        location=value("location", ""),
        mode=value("mode", "remote"),
        stipend_or_prize=getattr(listing, "stipend_or_prize", None),
        deadline=value("deadline", date.today()),
        apply_url=value("apply_url", ""),
        contact_email=getattr(listing, "contact_email", None),
        source=value("source", "unknown"),
        posted_date=getattr(listing, "posted_date", None),
        requires_payment=bool(getattr(listing, "requires_payment", False)),
    )


def rank_listings(
    profile: StudentProfile,
    listings: Sequence[Any],
    *,
    profile_vector: np.ndarray | None = None,
    listing_vectors: np.ndarray | None = None,
    filters: MatchFilters | None = None,
    hide_risky: bool = False,
    limit: int = 10,
    today: date | None = None,
) -> tuple[list[MatchOut], dict[str, Any]]:
    """Rank listings for a profile and explain every score.

    Args:
        profile: The (editable) student profile.
        listings: Candidate ORM listings.
        profile_vector: Pre-computed profile embedding.
        listing_vectors: Matrix aligned with ``listings`` (same order).
        filters: Hard filters on type and mode.
        hide_risky: Drop ``high-risk`` listings entirely.
        limit: Maximum number of matches to return.
        today: Date used for countdowns (injectable for tests).

    Returns:
        ``(matches, meta)`` where ``meta`` holds candidate counts and whether
        semantic scoring was available.
    """
    today = today or date.today()
    filters = filters or MatchFilters()
    allowed_types = {str(value).strip().lower() for value in filters.types if str(value).strip()}
    wanted_mode = (filters.mode or "").strip().lower()

    # 1. Hard filters -----------------------------------------------------
    candidates: list[Any] = []
    for listing in listings:
        days_left = _days_left(getattr(listing, "deadline", None), today)
        if days_left < 0:
            continue  # expired
        if allowed_types and str(getattr(listing, "type", "")).lower() not in allowed_types:
            continue
        if wanted_mode and str(getattr(listing, "mode", "")).lower() != wanted_mode:
            continue
        candidates.append(listing)

    vector_by_id: dict[int, np.ndarray] = {}
    if listing_vectors is not None and len(listing_vectors) == len(listings):
        vector_by_id = {
            _obj_id(listing): listing_vectors[index]
            for index, listing in enumerate(listings)
        }

    # 2. Collapse near-duplicates ----------------------------------------
    deduped, _, conflicts = collapse_duplicates(candidates)
    candidate_count = len(candidates)

    # 3. Score every survivor --------------------------------------------
    matches: list[MatchOut] = []
    for listing in deduped:
        listing_id = _obj_id(listing)
        days_left = _days_left(getattr(listing, "deadline", None), today)
        trust = assess_listing(listing, duplicate_conflict=listing_id in conflicts)

        ratio, matched, missing = skill_overlap(
            getattr(listing, "required_skills", []) or [], profile.skills
        )
        level = level_fit(profile.education.year, getattr(listing, "level", "any"))
        urgency = deadline_urgency(days_left)

        semantic = 0.5
        vector = vector_by_id.get(listing_id)
        if profile_vector is not None and vector is not None:
            semantic = calibrate_semantic(cosine_similarity(profile_vector, vector))

        total, breakdown = compute_score(semantic, ratio, level, urgency)
        matches.append(
            MatchOut(
                listing=_listing_out(listing),
                score=total,
                score_breakdown=breakdown,
                why_it_fits=heuristic_why_it_fits(profile, listing, matched),
                matched_skills=matched,
                missing_skills=missing,
                trust=trust,
                days_left=days_left,
                expired=False,
                pinned_risky=trust.level == "high-risk",
            )
        )

    # 4. Pin high-risk listings below the rest, then by score -------------
    matches.sort(
        key=lambda match: (
            match.trust.level == "high-risk",
            -match.score,
            -match.trust.score,
            match.listing.id,
        )
    )

    if hide_risky:
        matches = [match for match in matches if match.trust.level != "high-risk"]

    returned = matches[: max(1, limit)]

    meta = {
        "candidates": candidate_count,
        "returned": len(returned),
        "semantic_available": profile_vector is not None,
    }
    return returned, meta


# ---------------------------------------------------------------------------
# Prompt payloads + "why it fits"
# ---------------------------------------------------------------------------


def profile_summary(profile: StudentProfile, *, max_projects: int = 4) -> str:
    """Compact profile block used by prompts and deterministic fallbacks."""
    education = profile.education
    lines = [
        f"Name: {profile.name or '(not given)'}",
        f"Education: {education.degree or '(not given)'} at {education.college or '(not given)'}, "
        f"{education.year or '(year not given)'}",
        f"Skills: {', '.join(profile.skills) or '(none listed)'}",
    ]
    if profile.projects:
        lines.append("Projects:")
        for project in profile.projects[:max_projects]:
            tech = f" [tech: {', '.join(project.tech)}]" if project.tech else ""
            lines.append(f"  - {project.name}: {project.summary[:240]}{tech}")
    if profile.experience:
        lines.append(f"Experience: {' | '.join(item[:180] for item in profile.experience[:3])}")
    if profile.interests:
        lines.append(f"Interests: {', '.join(profile.interests)}")
    if profile.target_types:
        lines.append(f"Target opportunity types: {', '.join(profile.target_types)}")
    if profile.location_pref:
        lines.append(f"Location preference: {profile.location_pref}")
    return "\n".join(lines)


def listing_summary(listing: "ListingOut | Any") -> str:
    """Compact listing block used by prompts."""
    deadline = getattr(listing, "deadline", None)
    deadline_text = deadline.isoformat() if hasattr(deadline, "isoformat") else (deadline or "not stated")
    skills = ", ".join(getattr(listing, "required_skills", []) or []) or "(none listed)"
    return "\n".join(
        [
            f"Title: {getattr(listing, 'title', '')}",
            f"Organization: {getattr(listing, 'organization', '')}",
            f"Type: {getattr(listing, 'type', '')} | Level: {getattr(listing, 'level', '')} | "
            f"Mode: {getattr(listing, 'mode', '')}",
            f"Location: {getattr(listing, 'location', '')}",
            f"Stipend/Prize: {getattr(listing, 'stipend_or_prize', None) or 'not stated'}",
            f"Deadline: {deadline_text}",
            f"Required skills: {skills}",
            f"Description: {getattr(listing, 'description', '')[:1200]}",
        ]
    )


class WhyFits(BaseModel):
    """LLM output schema for the two-sentence fit explanation."""

    why_it_fits: str = ""


async def explain_match(
    profile: StudentProfile,
    listing: ListingOut | Any,
    *,
    client: LLMClient,
) -> tuple[str, bool, str | None]:
    """Generate the grounded two-sentence "why it fits" for one listing.

    Returns:
        ``(text, ai_available, note)``. Falls back to the deterministic,
        facts-only sentence pair from :func:`heuristic_why_it_fits`.
    """
    ratio, matched, _ = skill_overlap(getattr(listing, "required_skills", []) or [], profile.skills)
    fallback_text = heuristic_why_it_fits(profile, listing, matched)

    result = await client.complete_json(
        task="why_it_fits",
        system=prompts.WHY_FITS_SYSTEM,
        user=prompts.WHY_FITS_USER.format(
            profile_summary=profile_summary(profile, max_projects=3),
            listing_summary=listing_summary(listing),
        ),
        schema=WhyFits,
        fallback=lambda: {"why_it_fits": fallback_text},
        max_tokens=400,
    )
    text = " ".join((result.value.why_it_fits or "").split()).strip()
    if len(text) < 25:
        return fallback_text, False, result.note or "AI explanation was too short, used rules."
    return text, result.ai_available, result.note


# ---------------------------------------------------------------------------
# Embedding persistence (SQLite cache)
# ---------------------------------------------------------------------------


def text_hash(text: str) -> str:
    """SHA-256 of the document used to produce an embedding."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def compute_missing_embeddings(session: Any, engine: EmbeddingEngine, listings: Any = None) -> int:
    """Embed any listing that has no cached vector for the active model.

    Args:
        session: SQLAlchemy session.
        engine: Embedding engine in use.
        listings: Optional pre-fetched listings; all are loaded when omitted.

    Returns:
        Number of listings (re)embedded and persisted.
    """
    from sqlalchemy import select

    from models import Listing, ListingEmbedding

    if listings is None:
        listings = list(session.scalars(select(Listing)).all())
    if not listings:
        return 0

    model_name = engine.storage_model_name
    existing = {
        row.listing_id: row
        for row in session.scalars(
            select(ListingEmbedding).where(ListingEmbedding.model_name == model_name)
        ).all()
    }

    todo: list[tuple[Any, str, str]] = []
    for listing in listings:
        document = listing_document(listing)
        digest = text_hash(document)
        cached = existing.get(_obj_id(listing))
        if cached is None or cached.text_hash != digest:
            todo.append((listing, document, digest))

    if not todo:
        return 0

    vectors = engine.encode([document for _, document, _ in todo])
    for (listing, _document, digest), vector in zip(todo, vectors):
        blob = np.asarray(vector, dtype=np.float32).tobytes()
        cached = existing.get(_obj_id(listing))
        if cached is None:
            session.add(
                ListingEmbedding(
                    listing_id=_obj_id(listing),
                    model_name=model_name,
                    text_hash=digest,
                    dim=int(vector.shape[0]),
                    vector=blob,
                )
            )
        else:
            cached.text_hash = digest
            cached.dim = int(vector.shape[0])
            cached.vector = blob
    session.flush()
    logger.info("Embedded %s listing(s) with %s", len(todo), model_name)
    return len(todo)


def load_embeddings_matrix(
    session: Any, listings: Sequence[Any], engine: EmbeddingEngine
) -> np.ndarray | None:
    """Load cached vectors into a matrix aligned with ``listings``.

    Returns ``None`` when any listing is missing a vector (caller then scores
    without semantic similarity rather than failing).
    """
    from sqlalchemy import select

    from models import ListingEmbedding

    if not listings:
        return None
    model_name = engine.storage_model_name
    rows = {
        row.listing_id: row
        for row in session.scalars(
            select(ListingEmbedding).where(ListingEmbedding.model_name == model_name)
        ).all()
    }
    vectors: list[np.ndarray] = []
    for listing in listings:
        row = rows.get(_obj_id(listing))
        if row is None:
            return None
        vectors.append(np.frombuffer(row.vector, dtype=np.float32))
    return np.vstack(vectors) if vectors else None

