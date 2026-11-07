"""SQLAlchemy tables and Pydantic schemas for Scoutly.

Two layers live together here on purpose: the ORM tables are what SQLite
stores, and the Pydantic models are the wire format the frontend consumes.
Listing embeddings are kept in a separate table so the main ``listings`` table
stays cheap to scan.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Literal enums (kept as plain strings in SQLite for portability)
# ---------------------------------------------------------------------------

ListingType = Literal["internship", "hackathon", "scholarship", "job", "event"]
Level = Literal["first-year", "second-year", "third-year", "final-year", "any"]
Mode = Literal["remote", "onsite", "hybrid"]
TrustLevel = Literal["verified", "caution", "high-risk"]


# ---------------------------------------------------------------------------
# SQLAlchemy ORM
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base for all Scoutly tables."""


class Listing(Base):
    """An opportunity a student could apply to."""

    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="any")
    location: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="remote")
    stipend_or_prize: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deadline: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    apply_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    posted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    requires_payment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Listing id={self.id} title={self.title!r}>"


class ListingEmbedding(Base):
    """Cached embedding vector for a listing (``float32`` bytes).

    Embeddings live in their own table so they can be recomputed independently
    of listing content and so the ``listings`` table stays small.
    """

    __tablename__ = "listing_embeddings"

    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True
    )
    model_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class Education(BaseModel):
    """The student's current degree."""

    degree: str = ""
    college: str = ""
    year: str = ""


class Project(BaseModel):
    """A project the student has built."""

    name: str = ""
    summary: str = ""
    tech: list[str] = Field(default_factory=list)


class StudentProfile(BaseModel):
    """Structured view of the student's resume."""

    name: str = ""
    education: Education = Field(default_factory=Education)
    skills: list[str] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    target_types: list[str] = Field(default_factory=list)
    location_pref: str = ""
    raw_text: str = ""


class ListingOut(BaseModel):
    """Wire format for a listing."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    organization: str
    type: str
    description: str
    required_skills: list[str] = Field(default_factory=list)
    level: str
    location: str
    mode: str
    stipend_or_prize: str | None = None
    deadline: date
    apply_url: str
    contact_email: str | None = None
    source: str
    posted_date: date | None = None
    requires_payment: bool = False


class ListingsResponse(BaseModel):
    """Response for ``GET /api/listings``."""

    count: int
    listings: list[ListingOut]


class TrustFlag(BaseModel):
    """One human-readable risk signal."""

    code: str
    reason: str
    penalty: int


class Trust(BaseModel):
    """Result of the rule-based (plus optional LLM) verification pass."""

    score: int
    level: TrustLevel
    flags: list[TrustFlag] = Field(default_factory=list)


class WeightedBreakdown(BaseModel):
    """Each scoring component after its weight is applied (in 0-100 points)."""

    semantic_similarity: float
    skill_overlap: float
    level_fit: float
    deadline_urgency: float


class ScoreBreakdown(BaseModel):
    """Per-component match score, each component in 0..1."""

    semantic_similarity: float
    skill_overlap: float
    level_fit: float
    deadline_urgency: float
    weighted: WeightedBreakdown


class MatchOut(BaseModel):
    """One ranked match with everything the UI needs to explain it."""

    listing: ListingOut
    score: float
    score_breakdown: ScoreBreakdown
    why_it_fits: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    trust: Trust
    days_left: int
    expired: bool = False
    pinned_risky: bool = False


class MatchFilters(BaseModel):
    """Optional hard filters for matching."""

    types: list[str] = Field(default_factory=list)
    mode: str | None = None


class MatchRequest(BaseModel):
    """Body of ``POST /api/match``."""

    profile: StudentProfile
    filters: MatchFilters = Field(default_factory=MatchFilters)
    hide_risky: bool = False
    #: Default returns the top 10. The UI asks for a wider ranked list (60) and
    #: filters client-side; only the top 10 get an LLM-written explanation.
    limit: int = Field(default=10, ge=1, le=200)


class MatchMeta(BaseModel):
    """Explains how the result set was produced."""

    candidates: int
    returned: int
    ai_available: bool
    note: str | None = None
    embeddings_backend: str


class MatchResponse(BaseModel):
    """Body of the ``POST /api/match`` response."""

    matches: list[MatchOut]
    meta: MatchMeta


class ProfileParseResponse(BaseModel):
    """Body of ``POST /api/profile/parse``."""

    profile: StudentProfile
    raw_text: str
    ai_available: bool
    note: str | None = None
    source: Literal["pdf", "text"]


class VerifyRequest(BaseModel):
    """Body of ``POST /api/verify`` — either a stored listing or raw text."""

    listing_id: int | None = None
    text: str | None = None


class VerifyResponse(BaseModel):
    """Body of the ``POST /api/verify`` response."""

    trust: Trust
    listing: ListingOut | None = None
    ai_available: bool
    note: str | None = None


class RoadmapStep(BaseModel):
    """One week of the improvement roadmap."""

    week: int
    goal: str
    resources: list[str] = Field(default_factory=list)


class GapAnalysis(BaseModel):
    """Strengths, gaps and a week-by-week plan to close them."""

    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    roadmap: list[RoadmapStep] = Field(default_factory=list)


class KitRequest(BaseModel):
    """Body of ``POST /api/kit``."""

    profile: StudentProfile
    listing_id: int
    regenerate: bool = False


class KitResponse(BaseModel):
    """The tailored application kit."""

    listing: ListingOut
    gap_analysis: GapAnalysis
    resume_bullets: list[str] = Field(default_factory=list)
    cover_note: str
    why_me_one_liner: str
    ai_available: bool
    note: str | None = None


class HealthResponse(BaseModel):
    """Body of ``GET /api/health``."""

    status: str = "ok"
    version: str
    mock_llm: bool
    llm_provider: str
    listings: int
    embeddings_backend: str


class SampleResumeResponse(BaseModel):
    """Body of ``GET /api/sample-resume``."""

    text: str
    profile: StudentProfile
