"""Scoring tests: the four components that decide the ranking order."""

from __future__ import annotations

import pytest

from matching import (
    WEIGHTS,
    calibrate_semantic,
    canonical_year,
    compute_score,
    deadline_urgency,
    level_fit,
    normalize_skill,
    skill_overlap,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("3rd year", "third-year"),
        ("Third Year", "third-year"),
        ("final year", "final-year"),
        ("Final-year", "final-year"),
        ("1st year", "first-year"),
        ("graduated", "final-year"),
        ("", None),
    ],
)
def test_canonical_year(raw: str, expected: str | None) -> None:
    assert canonical_year(raw) == expected


def test_level_fit_exact_and_any() -> None:
    assert level_fit("3rd year", "third-year") == 1.0
    assert level_fit("3rd year", "any") == 1.0


def test_level_fit_adjacent_and_far() -> None:
    assert level_fit("2nd year", "third-year") == 0.5
    assert level_fit("1st year", "final-year") == 0.2


def test_level_fit_neutral_when_profile_year_unknown() -> None:
    assert level_fit("", "third-year") == 0.5
    assert level_fit(None, "third-year") == 0.5


def test_deadline_urgency_is_zero_once_expired() -> None:
    assert deadline_urgency(-1) == 0.0
    assert deadline_urgency(0) > 0.0


def test_deadline_urgency_peaks_in_the_middle_window() -> None:
    values = [deadline_urgency(day) for day in range(0, 40)]
    peak = max(values)
    assert peak <= 1.0
    assert values[8] == peak
    assert deadline_urgency(45) < deadline_urgency(8)


def test_compute_score_weights_sum_to_one() -> None:
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_compute_score_is_a_perfect_100_for_a_perfect_match() -> None:
    score, breakdown = compute_score(1.0, 1.0, 1.0, 1.0)
    assert score == pytest.approx(100.0)
    assert breakdown.semantic_similarity == 1.0
    assert breakdown.weighted.skill_overlap == pytest.approx(
        WEIGHTS["skill_overlap"] * 100
    )


def test_compute_score_clamps_out_of_range_inputs() -> None:
    score, _ = compute_score(2.0, -1.0, 5.0, -3.0)
    assert 0.0 <= score <= 100.0
    assert score == pytest.approx(WEIGHTS["semantic_similarity"] * 100 + WEIGHTS["level_fit"] * 100)


def test_normalize_skill_handles_aliases_and_case() -> None:
    assert normalize_skill("React.js") == normalize_skill("react")
    assert normalize_skill("  NODE  ") == normalize_skill("node.js")


def test_skill_overlap_splits_matched_and_missing() -> None:
    ratio, matched, missing = skill_overlap(
        ["React", "TypeScript", "Docker"],
        ["React", "TypeScript", "Python"],
    )
    assert ratio == pytest.approx(2 / 3)
    assert matched == ["React", "TypeScript"]
    assert missing == ["Docker"]


def test_skill_overlap_with_no_required_skills_is_neutral() -> None:
    ratio, matched, missing = skill_overlap([], ["React"])
    assert ratio == 0.5
    assert matched == []
    assert missing == []


def test_calibrate_semantic_is_monotonic() -> None:
    scores = [calibrate_semantic(raw) for raw in (0.0, 0.2, 0.5, 0.8, 1.0)]
    assert scores == sorted(scores)
    assert all(0.0 <= score <= 1.0 for score in scores)
