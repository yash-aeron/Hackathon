"""End-to-end smoke test against a running Scoutly API."""

from __future__ import annotations

import json
import time
import traceback

import httpx

BASE = "http://127.0.0.1:8000"
client = httpx.Client(base_url=BASE, timeout=180)


def check(label: str, response: httpx.Response, keys: list[str] | None = None) -> dict:
    print(f"{label}: {response.status_code}", end="")
    if response.status_code >= 400:
        print("  ERROR:", response.text[:400])
        raise SystemExit(f"{label} failed")
    data = response.json()
    if keys:
        summary = []
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                summary.append(f"{key}=list[{len(value)}]")
            elif isinstance(value, dict):
                summary.append(f"{key}=dict")
            elif isinstance(value, str) and len(value) > 40:
                summary.append(f"{key}=str({len(value)})")
            else:
                summary.append(f"{key}={value}")
        print(" | " + ", ".join(summary))
    else:
        print()
    return data


try:
    health = check("HEALTH", client.get("/api/health"), ["status", "mock_llm", "listings", "embeddings_backend"])
    listings = check("LISTINGS", client.get("/api/listings", params={"limit": 5}), ["count"])
    sample = check("SAMPLE", client.get("/api/sample-resume"), ["text", "profile"])
    print("   resume chars:", len(sample["text"]), "| sample skills:", len(sample["profile"]["skills"]))

    t0 = time.time()
    parsed = check("PARSE", client.post("/api/profile/parse", json={"text": sample["text"]}),
                   ["ai_available", "source", "note"])
    print(f"   took {time.time() - t0:.1f}s | ai={parsed['ai_available']} note={parsed['note']}")
    profile = parsed["profile"]
    print("   name:", profile["name"], "| education:", profile["education"])
    print("   skills:", len(profile["skills"]), "| projects:", [p["name"] for p in profile["projects"]])
    print("   experience entries:", len(profile["experience"]), "| interests:", profile["interests"])
    print("   targets:", profile["target_types"], "| location:", profile["location_pref"])

    t0 = time.time()
    matched = check("MATCH(60)", client.post("/api/match", json={
        "profile": profile, "filters": {}, "hide_risky": False, "limit": 60,
    }), ["matches", "meta"])
    print(f"   took {time.time() - t0:.1f}s | meta:", json.dumps(matched["meta"]))
    matches = matched["matches"]
    print("   top 6:")
    for match in matches[:6]:
        print(f"     {match['score']:5.1f}  {match['trust']['level']:<9} "
              f"{match['listing']['title'][:40]:40s} | {match['why_it_fits'][:78]}")
    risky = [m for m in matches if m["trust"]["level"] == "high-risk"]
    print("   high-risk:", [(m["listing"]["title"][:28], m["trust"]["score"]) for m in risky])
    print("   breakdown[0]:", json.dumps(matches[0]["score_breakdown"]))
    print("   dates:", matches[0]["listing"]["deadline"], "| days_left:", matches[0]["days_left"])

    filtered = check("MATCH(filters)", client.post("/api/match", json={
        "profile": profile, "filters": {"types": ["internship"], "mode": "remote"},
        "hide_risky": True, "limit": 10,
    }), ["matches"])
    print("   all remote internships:",
          all(m["listing"]["type"] == "internship" and m["listing"]["mode"] == "remote" for m in filtered["matches"]),
          "| no risky:", all(m["trust"]["level"] != "high-risk" for m in filtered["matches"]))

    verified = check("VERIFY(id)", client.post("/api/verify", json={"listing_id": risky[0]["listing"]["id"]}),
                     ["trust", "ai_available"])
    print("   trust:", verified["trust"]["score"], verified["trust"]["level"],
          [f["code"] for f in verified["trust"]["flags"]])

    pasted = check("VERIFY(text)", client.post("/api/verify", json={"text": (
        "URGENT internship! Apply within 2 hours. Pay a refundable security deposit of Rs 1999. "
        "Contact hr.quickjobs@gmail.com or WhatsApp only for the application form. "
        "Guaranteed placement, no interview. Register at https://bit.ly/xyz"
    )}), ["trust"])
    print("   trust:", pasted["trust"]["score"], pasted["trust"]["level"],
          [f["code"] for f in pasted["trust"]["flags"]])

    kit = check("KIT", client.post("/api/kit", json={"profile": profile, "listing_id": matches[0]["listing"]["id"]}),
                ["gap_analysis", "resume_bullets", "cover_note", "why_me_one_liner", "ai_available"])
    gap = kit["gap_analysis"]
    print("   strengths:", len(gap["strengths"]), "| gaps:", len(gap["gaps"]),
          "| roadmap:", [w["week"] for w in gap["roadmap"]])
    for strength in gap["strengths"]:
        print("      + ", strength[:100])
    for g in gap["gaps"]:
        print("      - ", g[:100])
    for step in gap["roadmap"]:
        print(f"      week {step['week']}: {step['goal'][:80]} | {step['resources'][:2]}")
    for bullet in kit["resume_bullets"]:
        print("      * ", bullet[:120])
    print("   cover words:", len(kit["cover_note"].split()))
    print("   cover:", kit["cover_note"][:400])
    print("   one-liner:", kit["why_me_one_liner"])

    calendar = client.get("/api/calendar.ics", params={
        "listing_ids": ",".join(str(m["listing"]["id"]) for m in matches[:3]),
    })
    print("CALENDAR:", calendar.status_code, calendar.headers.get("content-type"),
          "| bytes:", len(calendar.text), "| events:", calendar.text.count("BEGIN:VEVENT"),
          "| alarms:", calendar.text.count("BEGIN:VALARM"),
          "| has 7/3/1 day reminders:",
          all(token in calendar.text for token in ("-P1W", "-P3D", "-P1D")))

    print("\nERROR PATHS")
    print("  bad kit id:", client.post("/api/kit", json={"profile": profile, "listing_id": 9999}).status_code)
    print("  bad verify:", client.post("/api/verify", json={}).status_code)
    print("  short parse:", client.post("/api/profile/parse", json={"text": "hi"}).status_code)
    print("  bad calendar:", client.get("/api/calendar.ics", params={"listing_ids": ""}).status_code)
    print("  bad listing ids:", client.get("/api/calendar.ics", params={"listing_ids": "9998,9999"}).status_code)
    print("\nALL CHECKS PASSED")
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    raise SystemExit(1)
