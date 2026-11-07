"""Resume-parsing tests for the deterministic extractor (the LLM fallback)."""

from __future__ import annotations

import pytest

from profile import heuristic_profile, load_sample_resume, split_sections


@pytest.fixture(scope="module")
def sample_text() -> str:
    return load_sample_resume()


@pytest.fixture(scope="module")
def parsed(sample_text: str) -> dict:
    return heuristic_profile(sample_text)


def test_sample_resume_is_bundled_and_substantial() -> None:
    text = load_sample_resume()
    assert len(text) > 500
    assert "AARAV SHARMA" in text


def test_split_sections_finds_the_expected_headings(sample_text: str) -> None:
    sections = split_sections(sample_text)
    assert set(sections) >= {"header", "education", "skills", "projects", "experience"}
    assert any("CampusHire" in line for line in sections["projects"])


def test_name_is_extracted_from_the_header(parsed: dict) -> None:
    assert parsed["name"] == "Aarav Sharma"


def test_education_is_extracted(parsed: dict) -> None:
    education = parsed["education"]
    assert "B.Tech" in education["degree"]
    assert "Tiruchirappalli" in education["college"]
    assert education["year"]


def test_skills_cover_the_stated_stack(parsed: dict) -> None:
    skills = {skill.lower() for skill in parsed["skills"]}
    assert {"react", "python", "typescript", "postgresql"} <= skills
    assert len(parsed["skills"]) >= 12


def test_projects_are_extracted_with_tech(parsed: dict) -> None:
    projects = parsed["projects"]
    names = {project["name"] for project in projects}
    assert {"CampusHire", "RetinaScan", "SplitKar", "SkillGraph"} <= names
    campushire = next(project for project in projects if project["name"] == "CampusHire")
    assert campushire["summary"]
    assert campushire["tech"]


def test_experience_lines_are_extracted(parsed: dict) -> None:
    experience = " ".join(parsed["experience"]).lower()
    assert "document ingestion pipeline" in experience
    assert len(parsed["experience"]) >= 2


def test_interests_are_extracted(parsed: dict) -> None:
    interests = " ".join(parsed["interests"]).lower()
    assert "developer tooling" in interests


def test_target_types_are_inferred(parsed: dict) -> None:
    assert parsed["target_types"]
    assert all(
        value in {"internship", "hackathon", "scholarship", "job", "event"}
        for value in parsed["target_types"]
    )


def test_location_preference_is_inferred(parsed: dict) -> None:
    assert parsed["location_pref"].lower() in {"bengaluru", "bengaluru, karnataka, india"}


def test_heuristic_profile_is_deterministic(sample_text: str) -> None:
    assert heuristic_profile(sample_text) == heuristic_profile(sample_text)
