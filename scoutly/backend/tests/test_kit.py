"""Application-kit tests: gaps, roadmap, bullets and the cover note fallback."""

from __future__ import annotations

from kit import (
    fallback_application_kit,
    fallback_gap_analysis,
    kit_from_project_names,
    student_descriptor,
)
from models import Education, Project, StudentProfile


def test_student_descriptor_reads_naturally() -> None:
    profile = StudentProfile(
        education=Education(
            degree="B.Tech Computer Science",
            college="NIT Trichy",
            year="3rd year",
        )
    )
    assert student_descriptor(profile) == (
        "third year B.Tech Computer Science student at NIT Trichy"
    )


def test_student_descriptor_handles_expected_graduation_year() -> None:
    profile = StudentProfile(
        education=Education(degree="B.Tech", college="PICT", year="Expected 2028")
    )
    assert student_descriptor(profile) == "B.Tech student (expected 2028) at PICT"


def test_student_descriptor_survives_a_missing_education_block() -> None:
    assert student_descriptor(StudentProfile()) == "engineering student"


def test_gap_analysis_has_the_expected_shape(student, listing) -> None:
    analysis = fallback_gap_analysis(student, listing)
    assert set(analysis) == {"strengths", "gaps", "roadmap"}
    assert 1 <= len(analysis["strengths"]) <= 5
    assert 1 <= len(analysis["gaps"]) <= 4
    assert 3 <= len(analysis["roadmap"]) <= 5


def test_gap_analysis_never_invents_missing_skills(student, listing) -> None:
    analysis = fallback_gap_analysis(student, listing)
    # The student already has every required skill for this listing.
    assert all("does not appear anywhere" not in gap for gap in analysis["gaps"])


def test_gap_analysis_lists_real_gaps(student, listing) -> None:
    listing.required_skills = ["React", "Kubernetes", "GraphQL"]
    analysis = fallback_gap_analysis(student, listing)
    gaps = " ".join(analysis["gaps"])
    assert "Kubernetes" in gaps
    assert "GraphQL" in gaps
    assert "React is required" not in gaps


def test_roadmap_weeks_are_numbered_contiguously(student, listing) -> None:
    analysis = fallback_gap_analysis(student, listing)
    weeks = [step["week"] for step in analysis["roadmap"]]
    assert weeks == list(range(1, len(weeks) + 1))


def test_roadmap_resources_are_free(student, listing) -> None:
    listing.required_skills = ["Kubernetes", "GraphQL", "Rust", "Go"]
    analysis = fallback_gap_analysis(student, listing)
    resources = [
        resource for step in analysis["roadmap"] for resource in step["resources"]
    ]
    assert resources
    assert all(resource.strip() for resource in resources)
    assert not any("paid" in resource.lower() for resource in resources)


def test_bullets_are_grounded_in_real_projects(student, listing) -> None:
    kit = fallback_application_kit(student, listing)
    bullets = kit["resume_bullets"]
    assert 1 <= len(bullets) <= 5
    assert any("CampusHire" in bullet for bullet in bullets)


def test_cover_note_names_the_role_and_the_organisation(student, listing) -> None:
    kit = fallback_application_kit(student, listing)
    note = kit["cover_note"]
    assert "Frontend Developer Intern" in note
    assert "TechNova Solutions" in note
    assert len(note.split()) <= 150


def test_one_line_pitch_starts_with_the_descriptor(student, listing) -> None:
    kit = fallback_application_kit(student, listing)
    pitch = kit["why_me_one_liner"]
    assert pitch[0].isupper()
    assert "internship" in pitch
    assert len(pitch) <= 240


def test_bullets_fall_back_to_skills_without_projects(listing) -> None:
    profile = StudentProfile(skills=["React", "Python"], education=Education(degree="B.Tech"))
    kit = fallback_application_kit(profile, listing)
    assert kit["resume_bullets"]
    assert any("React" in bullet for bullet in kit["resume_bullets"])


def test_kit_from_project_names_lists_every_project() -> None:
    profile = StudentProfile(
        projects=[
            Project(name="CampusHire", summary="A job board."),
            Project(name="RetinaScan", summary="A screening tool."),
        ]
    )
    assert kit_from_project_names(profile) == ["CampusHire", "RetinaScan"]
