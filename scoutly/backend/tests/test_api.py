"""HTTP-level tests for every documented endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    """A TestClient that runs the real startup (auto-seed + embedding warm-up)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def profile(client: TestClient) -> dict:
    """The sample profile used across the API tests."""
    response = client.get("/api/sample-resume")
    assert response.status_code == 200
    return response.json()["profile"]


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


def test_root_is_not_404(client: TestClient) -> None:
    """The base URL returns a small JSON landing payload."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "Scoutly API"


def test_health(client: TestClient) -> None:
    """Health reports version, catalogue size and LLM mode."""
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["listings"] == 60
    assert isinstance(body["mock_llm"], bool)
    assert body["embeddings_backend"] in {"hashing", "sentence-transformers", "loading"}


def test_cors_allows_frontend_origin(client: TestClient) -> None:
    """CORS is configured for the Next.js dev server."""
    response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_preflight_for_post(client: TestClient) -> None:
    """Preflight requests from the frontend succeed."""
    response = client.options(
        "/api/match",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code in {200, 204}


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------


def test_listings(client: TestClient) -> None:
    """The catalogue is returned, soonest deadline first."""
    response = client.get("/api/listings", params={"limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 10
    deadlines = [item["deadline"] for item in body["listings"]]
    assert deadlines == sorted(deadlines)
    first = body["listings"][0]
    assert set(first) >= {
        "id",
        "title",
        "organization",
        "type",
        "required_skills",
        "level",
        "mode",
        "deadline",
        "apply_url",
        "requires_payment",
    }


def test_listings_type_filter(client: TestClient) -> None:
    """The type filter is honoured."""
    response = client.get("/api/listings", params={"types": "hackathon", "limit": 50})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] > 0
    assert {item["type"] for item in body["listings"]} == {"hackathon"}


def test_listings_mode_filter(client: TestClient) -> None:
    """The mode filter is honoured."""
    response = client.get("/api/listings", params={"mode": "remote", "limit": 50})
    assert response.status_code == 200
    assert {item["mode"] for item in response.json()["listings"]} == {"remote"}


# ---------------------------------------------------------------------------
# Profile parsing
# ---------------------------------------------------------------------------


def test_sample_resume(client: TestClient) -> None:
    """The demo sample resume and an instant profile are available."""
    response = client.get("/api/sample-resume")
    assert response.status_code == 200
    body = response.json()
    assert "yash" in body["text"].lower()
    assert body["profile"]["skills"]
    assert body["profile"]["projects"]


def test_parse_text_profile(client: TestClient, profile: dict) -> None:
    """Posting resume text returns an editable profile."""
    resume = client.get("/api/sample-resume").json()["text"]
    response = client.post("/api/profile/parse", json={"text": resume})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "text"
    assert body["profile"]["name"]
    assert body["profile"]["skills"]
    assert body["profile"]["projects"]
    assert body["raw_text"]
    assert isinstance(body["ai_available"], bool)


def test_parse_rejects_short_text(client: TestClient) -> None:
    """Too-short input is a 400 with a helpful message."""
    response = client.post("/api/profile/parse", json={"text": "hi"})
    assert response.status_code == 400
    assert "detail" in response.json()


def test_parse_rejects_unsupported_content_type(client: TestClient) -> None:
    """Plain text bodies get a 415 explaining the two supported formats."""
    response = client.post(
        "/api/profile/parse",
        content="not json",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415


def test_parse_rejects_non_pdf_upload(client: TestClient) -> None:
    """An unreadable upload is a 400, not a crash."""
    response = client.post(
        "/api/profile/parse",
        files={"file": ("resume.pdf", b"this is not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _match(client: TestClient, profile: dict, **overrides) -> dict:
    payload = {"profile": profile, "limit": 10, **overrides}
    response = client.post("/api/match", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_match_returns_ranked_explainable_results(client: TestClient, profile: dict) -> None:
    """Every match carries score, breakdown, explanation and trust."""
    body = _match(client, profile)
    matches = body["matches"]
    assert matches
    assert body["meta"]["candidates"] >= len(matches)
    assert body["meta"]["embeddings_backend"] in {"hashing", "sentence-transformers"}

    for match in matches:
        assert 0.0 <= match["score"] <= 100.0
        breakdown = match["score_breakdown"]
        assert 0.0 <= breakdown["semantic_similarity"] <= 1.0
        assert 0.0 <= breakdown["skill_overlap"] <= 1.0
        assert 0.0 <= breakdown["level_fit"] <= 1.0
        assert 0.0 <= breakdown["deadline_urgency"] <= 1.0
        assert match["why_it_fits"].strip()
        assert match["listing"]["title"]
        assert match["trust"]["level"] in {"verified", "caution", "high-risk"}
        assert isinstance(match["trust"]["flags"], list)
        assert match["days_left"] >= 0
        assert match["expired"] is False

    # Scores descend, except that high-risk listings are pinned last.
    legit_scores = [m["score"] for m in matches if not m["pinned_risky"]]
    assert legit_scores == sorted(legit_scores, reverse=True)
    if any(m["pinned_risky"] for m in matches):
        assert matches[-1]["pinned_risky"] is True


def test_match_never_returns_expired_listings(client: TestClient, profile: dict) -> None:
    """Expired listings are a hard filter."""
    body = _match(client, profile, limit=60)
    assert all(match["days_left"] >= 0 for match in body["matches"])


def test_match_collapses_duplicates(client: TestClient, profile: dict) -> None:
    """No two matches share the same title and organisation."""
    body = _match(client, profile, limit=60)
    keys = [
        (match["listing"]["title"].lower(), match["listing"]["organization"].lower())
        for match in body["matches"]
    ]
    assert len(keys) == len(set(keys))


def test_match_surfaces_risky_listings(client: TestClient, profile: dict) -> None:
    """High-risk listings are included (pinned) so the demo can show detection."""
    body = _match(client, profile, limit=60, hide_risky=False)
    risky = [match for match in body["matches"] if match["trust"]["level"] == "high-risk"]
    assert risky
    for match in risky:
        assert match["trust"]["flags"]
        assert all(flag["reason"] for flag in match["trust"]["flags"])


def test_match_hide_risky(client: TestClient, profile: dict) -> None:
    """hide_risky removes every high-risk match."""
    body = _match(client, profile, limit=60, hide_risky=True)
    assert all(match["trust"]["level"] != "high-risk" for match in body["matches"])


def test_match_type_and_mode_filters(client: TestClient, profile: dict) -> None:
    """Filters are applied server-side."""
    body = _match(
        client,
        profile,
        limit=20,
        filters={"types": ["hackathon"], "mode": "remote"},
    )
    for match in body["matches"]:
        assert match["listing"]["type"] == "hackathon"
        assert match["listing"]["mode"] == "remote"


def test_match_all_types_filter(client: TestClient, profile: dict) -> None:
    """A single-type filter only returns that type."""
    body = _match(client, profile, limit=20, filters={"types": ["scholarship"]})
    assert body["matches"]
    assert {match["listing"]["type"] for match in body["matches"]} == {"scholarship"}


def test_match_rejects_invalid_limit(client: TestClient, profile: dict) -> None:
    """An out-of-range limit is a 422 from Pydantic."""
    response = client.post("/api/match", json={"profile": profile, "limit": 0})
    assert response.status_code == 422


def test_match_requires_profile(client: TestClient) -> None:
    """A missing profile is a 422."""
    response = client.post("/api/match", json={"limit": 10})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def test_verify_stored_risky_listing(client: TestClient) -> None:
    """A seeded scam listing returns high-risk with reasons."""
    listings = client.get("/api/listings", params={"limit": 60}).json()["listings"]
    scam = next(
        item for item in listings if "name withheld" in item["organization"].lower()
    )
    response = client.post("/api/verify", json={"listing_id": scam["id"]})
    assert response.status_code == 200
    body = response.json()
    assert body["listing"]["id"] == scam["id"]
    assert body["trust"]["level"] == "high-risk"
    assert body["trust"]["flags"]
    assert body["trust"]["score"] < 45


def test_verify_clean_listing(client: TestClient) -> None:
    """A clean listing verifies successfully."""
    listings = client.get("/api/listings", params={"limit": 60}).json()["listings"]
    clean = next(
        item
        for item in listings
        if item["apply_url"].startswith("https://careers.")
        and not item["requires_payment"]
        and item["contact_email"] is None
    )
    response = client.post("/api/verify", json={"listing_id": clean["id"]})
    assert response.status_code == 200
    assert response.json()["trust"]["level"] == "verified"


def test_verify_unknown_listing_is_404(client: TestClient) -> None:
    """An unknown id is a 404."""
    response = client.post("/api/verify", json={"listing_id": 999_999})
    assert response.status_code == 404


def test_verify_pasted_text(client: TestClient) -> None:
    """Pasted listing text is analysed with the same rules."""
    response = client.post(
        "/api/verify",
        json={
            "text": (
                "URGENT - apply within 2 hours. Pay a refundable security deposit of Rs 1,999. "
                "Contact hr.quickjobs@gmail.com or WhatsApp only for the application form. "
                "Guaranteed placement with no interview. Register at https://bit.ly/xyz"
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["listing"] is None
    assert body["trust"]["level"] == "high-risk"
    codes = {flag["code"] for flag in body["trust"]["flags"]}
    assert "payment_required" in codes
    assert "free_email_contact" in codes


def test_verify_pasted_clean_text(client: TestClient) -> None:
    """A clean paste scores well."""
    response = client.post(
        "/api/verify",
        json={
            "text": (
                "Backend Engineering Intern at Nexus Labs. Build FastAPI services with "
                "PostgreSQL. Stipend 40,000 per month. Apply at "
                "https://careers.nexuslabs.io/intern. Applications close in three weeks."
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["trust"]["level"] == "verified"


def test_verify_empty_request_is_400(client: TestClient) -> None:
    """Neither id nor text is a 400."""
    response = client.post("/api/verify", json={})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Application kit
# ---------------------------------------------------------------------------


def test_kit_for_top_match(client: TestClient, profile: dict) -> None:
    """The kit endpoint returns gaps, roadmap, bullets and a cover note."""
    match = client.post("/api/match", json={"profile": profile, "limit": 5}).json()["matches"][0]
    response = client.post(
        "/api/kit", json={"profile": profile, "listing_id": match["listing"]["id"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["listing"]["id"] == match["listing"]["id"]
    assert 3 <= len(body["gap_analysis"]["roadmap"]) <= 5
    assert body["gap_analysis"]["strengths"]
    assert body["gap_analysis"]["gaps"]
    assert 3 <= len(body["resume_bullets"]) <= 5
    assert len(body["cover_note"].split()) <= 150
    assert body["why_me_one_liner"]
    for step in body["gap_analysis"]["roadmap"]:
        assert step["resources"]
        assert all("http" not in resource for resource in step["resources"])


def test_kit_unknown_listing_is_404(client: TestClient, profile: dict) -> None:
    """An unknown listing id is a 404."""
    response = client.post("/api/kit", json={"profile": profile, "listing_id": 999_999})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


def test_calendar_export(client: TestClient) -> None:
    """Three listings produce an .ics attachment with reminders."""
    ids = [item["id"] for item in client.get("/api/listings", params={"limit": 3}).json()["listings"]]
    response = client.get("/api/calendar.ics", params={"listing_ids": ",".join(map(str, ids))})
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert body.count("BEGIN:VEVENT") == 3
    assert body.count("BEGIN:VALARM") == 9
    assert all(token in body for token in ("-P1W", "-P3D", "-P1D"))


def test_calendar_requires_ids(client: TestClient) -> None:
    """No ids is a 400."""
    response = client.get("/api/calendar.ics", params={"listing_ids": ""})
    assert response.status_code == 400


def test_calendar_unknown_ids_is_404(client: TestClient) -> None:
    """Unknown ids are a 404."""
    response = client.get("/api/calendar.ics", params={"listing_ids": "999998,999999"})
    assert response.status_code == 404
