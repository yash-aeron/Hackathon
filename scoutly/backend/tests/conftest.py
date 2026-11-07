"""Shared pytest setup for the Scoutly backend.

The backend is a flat module layout (``backend/main.py`` imports ``matching``,
``verify`` and friends by bare name), so tests add the backend directory to
``sys.path`` before importing anything.

Environment is configured *before* the backend modules import, because
``config.get_settings`` and the SQLAlchemy engine are created at import time.
Tests therefore always run offline and deterministic: throwaway SQLite file,
mock LLM, hashed embeddings.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TMP_DIR = Path(tempfile.mkdtemp(prefix="scoutly-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["MOCK_LLM"] = "true"
os.environ["LLM_API_KEY"] = ""
os.environ["EMBEDDING_BACKEND"] = "hashing"

import pytest  # noqa: E402

from models import Education, ListingOut, Project, StudentProfile  # noqa: E402


@pytest.fixture
def student() -> StudentProfile:
    """A realistic student profile used across the matching and kit tests."""
    return StudentProfile(
        name="Aarav Sharma",
        education=Education(
            degree="B.Tech Computer Science",
            college="National Institute of Technology Tiruchirappalli",
            year="3rd year",
        ),
        skills=["React", "JavaScript", "TypeScript", "Python", "SQL", "Git"],
        projects=[
            Project(
                name="CampusHire",
                summary=(
                    "A role-based job board used by more than 400 students across "
                    "three colleges, built with Next.js and FastAPI."
                ),
                tech=["Next.js", "FastAPI", "PostgreSQL"],
            )
        ],
        experience=["Frontend intern at a local startup (Summer 2025)"],
        interests=["developer tooling", "education"],
        target_types=["internship", "hackathon"],
        location_pref="Bengaluru",
    )


@pytest.fixture
def listing() -> ListingOut:
    """A clean, verifiable frontend internship."""
    return ListingOut(
        id=1,
        title="Frontend Developer Intern",
        organization="TechNova Solutions",
        type="internship",
        description=(
            "Build product surfaces in React and TypeScript alongside the "
            "frontend team. Remote-friendly, 6 months, mentorship provided."
        ),
        required_skills=["React", "TypeScript", "Git"],
        level="third-year",
        location="Remote",
        mode="remote",
        stipend_or_prize="₹35,000/month",
        deadline=date(2026, 12, 15),
        apply_url="https://technova.io/careers/frontend-intern",
        contact_email="careers@technova.io",
        source="Internshala",
        posted_date=date(2026, 11, 1),
        requires_payment=False,
    )


@pytest.fixture
def sample_profile() -> StudentProfile:
    """A fuller third-year CSE profile for ranking tests."""
    return StudentProfile(
        name="Aarav Sharma",
        education=Education(
            degree="B.Tech",
            college="National Institute of Technology Tiruchirappalli",
            year="third-year",
        ),
        skills=[
            "Python",
            "JavaScript",
            "TypeScript",
            "React",
            "Next.js",
            "Node.js",
            "FastAPI",
            "SQL",
            "PostgreSQL",
            "Git",
            "Docker",
            "pandas",
            "scikit-learn",
            "PyTorch",
            "Figma",
        ],
        projects=[
            Project(
                name="CampusHire",
                summary="Next.js and FastAPI job board used by 400+ students.",
                tech=["Next.js", "FastAPI", "PostgreSQL"],
            ),
            Project(
                name="RetinaScan",
                summary="PyTorch CNN for diabetic retinopathy screening.",
                tech=["PyTorch", "OpenCV"],
            ),
        ],
        experience=["Software Engineering Intern at Nexus Labs"],
        interests=["AI for social good", "developer tooling"],
        target_types=["internship"],
        location_pref="Bengaluru",
    )


@pytest.fixture(scope="session")
def seeded_db():
    """Create the schema and load the 60 seed listings once per test session."""
    from db import SessionLocal, init_db
    from seed import seed_database

    init_db()
    session = SessionLocal()
    try:
        seed_database(session, reset=True)
        session.commit()
    finally:
        session.close()
    return True


@pytest.fixture()
def session(seeded_db):
    """A database session with the seed catalogue loaded."""
    from db import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def all_listings(session):
    """Every seeded listing, ordered by id."""
    from models import Listing as ListingModel

    return list(session.query(ListingModel).order_by(ListingModel.id).all())
