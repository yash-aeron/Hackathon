"""Gap analysis, week-by-week roadmap and the tailored application kit.

Two LLM calls run concurrently (gap analysis + application kit).  Each has a
deterministic fallback built only from profile and listing facts - that is what
keeps the demo working when the provider is down or mock mode is on.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

import prompts
from llm import LLMClient, get_llm_client
from matching import (
    canonical_year,
    level_fit,
    listing_summary,
    profile_summary,
    skill_overlap,
)
from models import GapAnalysis, ListingOut, Project, RoadmapStep, StudentProfile

logger = logging.getLogger("scoutly.kit")

MAX_COVER_NOTE_WORDS = 150

#: Free, well-known resources grouped by skill family. Names only - never URLs.
FALLBACK_RESOURCES: dict[str, list[str]] = {
    "python": ["Official Python tutorial (docs)", "Exercism Python track (problem set)"],
    "javascript": ["MDN JavaScript guide (docs)", "JavaScript.info (free book)"],
    "typescript": ["TypeScript handbook (docs)", "Total TypeScript beginner exercises (free)"],
    "react": ["React official 'Learn React' docs (docs)", "Scrimba free React course (interactive)"],
    "node": ["Node.js official getting-started guide (docs)", "Build a REST API tutorial (YouTube)"],
    "sql": ["SQLBolt (interactive lessons)", "PostgreSQL Tutorial (docs)"],
    "docker": ["Docker Get Started guide (docs)", "Play with Docker (free labs)"],
    "kubernetes": ["Kubernetes Basics tutorial (docs)", "KillerCoda Kubernetes labs (free labs)"],
    "machine learning": [
        "Kaggle Learn: Intro to Machine Learning (free course)",
        "scikit-learn user guide (docs)",
    ],
    "deep learning": ["fast.ai Practical Deep Learning (free course)", "PyTorch tutorials (docs)"],
    "nlp": ["Hugging Face NLP Course (free course)", "spaCy course (free course)"],
    "llm": ["Hugging Face LLM Course (free course)", "Prompt Engineering Guide (docs)"],
    "data": ["Kaggle Learn: Pandas (free course)", "pandas 10-minute guide (docs)"],
    "cloud": ["AWS Skill Builder free courses (free course)", "Google Cloud Skills Boost (labs)"],
    "aws": ["AWS Skill Builder free courses (free course)", "AWS getting-started docs (docs)"],
    "git": ["GitHub Skills interactive labs (free labs)", "Pro Git book (free e-book)"],
    "algorithms": ["NeetCode 150 (problem set)", "MIT OpenCourseWare 6.006 lectures (video)"],
    "data structures": ["NeetCode 150 (problem set)", "VisuAlgo visualisations (interactive)"],
    "system design": ["System Design Primer (free repo)", "ByteByteGo free articles (articles)"],
    "frontend": ["MDN Web Docs (docs)", "Frontend Mentor free challenges (practice)"],
    "ui": ["Refactoring UI free chapters (articles)", "Figma Learn (interactive lessons)"],
    "cybersecurity": ["TryHackMe free rooms (labs)", "PortSwigger Web Security Academy (free labs)"],
    "embedded": ["Embedded Systems with ARM free course (video)", "Arduino official tutorials (docs)"],
    "testing": ["Pytest official getting-started (docs)", "Testing Library docs (docs)"],
}

_DEFAULT_RESOURCES = [
    "freeCodeCamp curriculum (free course)",
    "Official documentation quickstart (docs)",
]

_VERB_RE = re.compile(
    r"^(built|developed|designed|created|shipped|implemented|led|automated|analysed|analyzed|"
    r"engineered|deployed|reduced|improved|trained|migrated|launched)\b",
    re.IGNORECASE,
)


class ApplicationKit(BaseModel):
    """LLM output schema for the application kit."""

    resume_bullets: list[str] = Field(default_factory=list)
    cover_note: str = ""
    why_me_one_liner: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skill_family(skill: str) -> str:
    """Map a free-text skill onto a key in :data:`FALLBACK_RESOURCES`."""
    lowered = (skill or "").lower()
    for key in FALLBACK_RESOURCES:
        if key in lowered:
            return key
    for token, key in (
        ("react", "react"),
        ("next", "react"),
        ("node", "node"),
        ("js", "javascript"),
        ("script", "javascript"),
        ("ml", "machine learning"),
        ("ai", "machine learning"),
        ("torch", "deep learning"),
        ("tensor", "deep learning"),
        ("data", "data"),
        ("cloud", "cloud"),
        ("docker", "docker"),
        ("kube", "kubernetes"),
        ("sql", "sql"),
        ("algorithm", "algorithms"),
        ("structure", "data structures"),
        ("design", "system design"),
        ("figma", "ui"),
        ("ux", "ui"),
    ):
        if token in lowered:
            return key
    return ""


def resources_for_skill(skill: str) -> list[str]:
    """Two free resource suggestions for a skill, by name only."""
    family = _skill_family(skill)
    return list(FALLBACK_RESOURCES.get(family, _DEFAULT_RESOURCES))


def _listing_skill_set(listing: ListingOut | Any) -> list[str]:
    return list(getattr(listing, "required_skills", []) or [])


def _truncate_words(text: str, limit: int) -> str:
    """Trim text to at most ``limit`` words, preferring a sentence boundary."""
    words = text.split()
    if len(words) <= limit:
        return text.strip()
    clipped = " ".join(words[:limit]).rstrip(",;:")
    if not clipped.endswith((".", "!", "?")):
        clipped += "."
    return clipped


def _first_sentence(text: str, limit: int = 180) -> str:
    """Return the first sentence of ``text`` (or a truncated prefix)."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""
    match = re.match(r"(.+?[.!?])\s", cleaned)
    sentence = match.group(1) if match else cleaned
    return sentence[:limit].rstrip(",;:")


# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------


def fallback_gap_analysis(profile: StudentProfile, listing: ListingOut | Any) -> dict[str, Any]:
    """Deterministic gap analysis + roadmap built from real overlaps only."""
    ratio, matched, missing = skill_overlap(_listing_skill_set(listing), profile.skills)
    matched_evidence: list[str] = []
    if matched:
        matched_evidence.append(
            f"Direct overlap on {', '.join(matched[:4])} - all of these are listed requirements"
        )
    else:
        matched_evidence.append(
            "No direct skill overlap yet - your closest evidence is your project work"
        )

    gaps = [
        f"{skill} is required but does not appear anywhere in your profile"
        for skill in missing[:4]
    ]
    if not gaps:
        gaps = [
            "No required skill is missing - the gap is depth, so add one shipped project "
            "with measurable outcomes to this listing's stack"
        ]

    roadmap: list[dict[str, Any]] = []
    if missing:
        for index, skill in enumerate(missing[:4], start=1):
            roadmap.append(
                {
                    "week": index,
                    "goal": f"Get to a working-basics level in {skill} and ship one small "
                    f"artefact you can show for it",
                    "resources": resources_for_skill(skill),
                }
            )

    # The spec requires 3-5 weekly steps: top up a short gap list with depth work.
    depth_steps = [
        {
            "goal": "Rebuild one existing project so it matches this listing's stack and "
            "write up the outcome",
            "resources": ["Your own project repository (project)", "GitHub README guide (docs)"],
        },
        {
            "goal": "Add tests and a deployment step so that project is demo-ready",
            "resources": ["Pytest official getting-started (docs)", "Vercel deployment guide (docs)"],
        },
        {
            "goal": "Practise explaining the project and its trade-offs out loud for interviews",
            "resources": ["System Design Primer (free repo)", "STAR method interview guide (article)"],
        },
    ]
    while len(roadmap) < 3 and depth_steps:
        step = depth_steps.pop(0)
        roadmap.append(
            {"week": len(roadmap) + 1, "goal": step["goal"], "resources": step["resources"]}
        )

    for index, step in enumerate(roadmap, start=1):
        step["week"] = index

    # Only list strengths the student can actually evidence.
    if profile.projects:
        top_project = next((project for project in profile.projects if project.tech), None)
        if top_project is not None:
            matched_evidence.append(
                f"{top_project.name} gives you concrete evidence with "
                f"{', '.join(top_project.tech[:3])}"
            )
    level_score = level_fit(profile.education.year, getattr(listing, "level", "any"))
    if level_score >= 1.0:
        matched_evidence.append(
            f"This listing targets {getattr(listing, 'level', 'any')} candidates, which matches your year"
        )
    elif level_score == 0.5:
        matched_evidence.append(
            f"This listing targets {getattr(listing, 'level', 'any')} candidates - one year away from yours"
        )

    return {
        "strengths": matched_evidence[:5],
        "gaps": gaps[:4],
        "roadmap": roadmap[:5],
    }


def student_descriptor(profile: StudentProfile) -> str:
    """Human-readable student descriptor, e.g. ``"third year B.Tech student at NIT Trichy"``.

    Falls back elegantly for ``"Expected 2028"``-style year strings so the copy
    never reads "a Expected 2028 B.Tech student".
    """
    education = profile.education
    degree = education.degree or "engineering"
    raw_year = (education.year or "").strip()
    canonical = canonical_year(raw_year)

    if canonical:
        prefix = f"{canonical.replace('-', ' ')} {degree} student"
    elif raw_year.lower().startswith(("expected", "graduating", "batch")):
        prefix = f"{degree} student ({raw_year.lower()})"
    elif raw_year:
        prefix = f"{raw_year} {degree} student"
    else:
        prefix = f"{degree} student"

    if education.college:
        prefix += f" at {education.college}"
    return prefix


def fallback_application_kit(profile: StudentProfile, listing: ListingOut | Any) -> dict[str, Any]:
    """Deterministic resume bullets + cover note, grounded in real project text."""
    title = getattr(listing, "title", "this role")
    org = getattr(listing, "organization", "your team")
    _, matched, missing = skill_overlap(_listing_skill_set(listing), profile.skills)

    bullets: list[str] = []
    for project in profile.projects[:4]:
        name = project.name or "an independent project"
        tech = ", ".join(project.tech[:3]) if project.tech else ", ".join(profile.skills[:3])
        tech = tech or "my current stack"
        summary = re.sub(r"\s+", " ", project.summary or "").strip()
        detail = _first_sentence(summary, 120).rstrip(". ")
        if not detail:
            bullets.append(f"Built {name} end to end with {tech}")
            continue
        # If the summary already names the stack, do not repeat it in the bullet.
        detail_lower = detail.lower()
        mentions_stack = any(
            skill.strip().lower() in detail_lower for skill in project.tech if skill.strip()
        )
        if mentions_stack:
            bullets.append(f"Built {name} - {detail}"[:250])
        else:
            bullets.append(f"Built {name} with {tech} - {detail}"[:250])

    for experience in profile.experience[:2]:
        cleaned = re.sub(r"\s+", " ", experience).strip().rstrip(".")
        if cleaned and len(bullets) < 5:
            bullets.append(cleaned[:250])

    if len(bullets) < 3:
        skills = ", ".join(profile.skills[:4]) or "my core stack"
        bullets.append(f"Applied {skills} across coursework and self-directed builds")

    descriptor = student_descriptor(profile)
    top_project = profile.projects[0] if profile.projects else None

    if matched:
        stack_line = f"the overlap with {', '.join(matched[:3])} is where most of my work sits"
    elif profile.skills:
        stack_line = f"my strongest work is in {', '.join(profile.skills[:3])}"
    else:
        stack_line = "I have been building small projects to close that gap"

    project_line = (
        f"Most relevant is {top_project.name}: {_first_sentence(top_project.summary, 170)}"
        if top_project and top_project.summary
        else "Most of my hands-on experience so far is self-directed project work"
    )

    if missing:
        learning_line = (
            f"The gap I am actively closing is {', '.join(missing[:2])}, which I am working on "
            "through a small project rather than only coursework."
        )
    else:
        learning_line = (
            "What I want next is depth: owning a feature end to end and seeing it used by real people."
        )

    cover_note = (
        f"I'm applying for the {title} role at {org}. I'm a {descriptor}, and {stack_line}.\n\n"
        f"{project_line.rstrip('.')}.\n\n"
        f"{learning_line} I'd welcome the chance to walk through my work and hear what your team "
        "needs next."
    )

    opportunity_type = getattr(listing, "type", "internship") or "internship"
    article = "an" if opportunity_type[:1].lower() in "aeiou" else "a"
    one_liner = (
        f"{descriptor[:1].upper() + descriptor[1:]}, building with "
        f"{(', '.join(profile.skills[:3]) if profile.skills else 'modern web tooling')}, "
        f"looking for {article} {opportunity_type} where I can ship real work."
    )

    return {
        "resume_bullets": bullets[:5],
        "cover_note": _truncate_words(re.sub(r"\s+", " ", cover_note), MAX_COVER_NOTE_WORDS),
        "why_me_one_liner": re.sub(r"\s+", " ", one_liner)[:220],
    }


# ---------------------------------------------------------------------------
# Prompt payload helpers (shared with the matcher)
# ---------------------------------------------------------------------------


def _profile_summary(profile: StudentProfile) -> str:
    """Backwards-compatible alias for :func:`matching.profile_summary`."""
    return profile_summary(profile)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_kit(
    profile: StudentProfile,
    listing: ListingOut | Any,
    *,
    client: LLMClient | None = None,
) -> tuple[GapAnalysis, ApplicationKit, bool, bool, str | None]:
    """Generate gap analysis and application kit in parallel.

    Returns:
        ``(gap_analysis, application_kit, gap_ai_available, kit_ai_available,
        note)`` where ``note`` is the first non-empty fallback explanation.
    """
    client = client or get_llm_client()
    profile_block = profile_summary(profile)
    listing_block = listing_summary(listing)

    gap_coro = client.complete_json(
        task="gap_analysis",
        system=prompts.GAP_ANALYSIS_SYSTEM,
        user=prompts.GAP_ANALYSIS_USER.format(
            profile_summary=profile_block, listing_summary=listing_block
        ),
        schema=GapAnalysis,
        fallback=lambda: fallback_gap_analysis(profile, listing),
        max_tokens=1600,
    )
    kit_coro = client.complete_json(
        task="application_kit",
        system=prompts.APPLICATION_KIT_SYSTEM,
        user=prompts.APPLICATION_KIT_USER.format(
            profile_summary=profile_block, listing_summary=listing_block
        ),
        schema=ApplicationKit,
        fallback=lambda: fallback_application_kit(profile, listing),
        max_tokens=1600,
    )

    gap_result, kit_result = await asyncio.gather(gap_coro, kit_coro)

    gap = _sanitise_gap(gap_result.value)
    kit = _sanitise_kit(kit_result.value, fallback_application_kit(profile, listing))
    note = gap_result.note or kit_result.note
    return gap, kit, gap_result.ai_available, kit_result.ai_available, note


def _sanitise_gap(gap: GapAnalysis) -> GapAnalysis:
    """Force the roadmap into 3-5 realistic weeks and trim empty entries."""
    steps: list[RoadmapStep] = []
    for index, step in enumerate(gap.roadmap[:5], start=1):
        goal = re.sub(r"\s+", " ", (step.goal or "")).strip()
        if not goal:
            continue
        cleaned_resources = [
            re.sub(r"\s+", " ", resource).strip()
            for resource in step.resources
            if resource and resource.strip()
        ][:3]
        steps.append(
            RoadmapStep(week=index, goal=goal[:220], resources=cleaned_resources or _DEFAULT_RESOURCES)
        )
    return GapAnalysis(
        strengths=[re.sub(r"\s+", " ", item).strip() for item in gap.strengths if item.strip()][:5],
        gaps=[re.sub(r"\s+", " ", item).strip() for item in gap.gaps if item.strip()][:4],
        roadmap=steps,
    )


def _sanitise_kit(kit: ApplicationKit, fallback: dict[str, Any]) -> ApplicationKit:
    """Enforce 3-5 bullets, <=150-word cover note, non-empty one-liner."""
    bullets = []
    for bullet in kit.resume_bullets:
        cleaned = re.sub(r"\s+", " ", (bullet or "")).strip().lstrip("-•* ").strip()
        if cleaned:
            bullets.append(cleaned[:240])
    if len(bullets) < 3:
        bullets = fallback["resume_bullets"]
    bullets = bullets[:5]

    cover_note = re.sub(r"\n{3,}", "\n\n", (kit.cover_note or "").strip())
    if len(cover_note.split()) < 40:
        cover_note = fallback["cover_note"]
    cover_note = _truncate_words(cover_note, MAX_COVER_NOTE_WORDS)

    one_liner = re.sub(r"\s+", " ", (kit.why_me_one_liner or "")).strip()
    if len(one_liner) < 12:
        one_liner = fallback["why_me_one_liner"]

    return ApplicationKit(
        resume_bullets=bullets,
        cover_note=cover_note,
        why_me_one_liner=one_liner[:240],
    )


def kit_from_project_names(profile: StudentProfile) -> list[str]:
    """Tiny helper used by tests: one bullet per real project."""
    return [project.name for project in profile.projects if project.name]

