"""FastAPI application for Scoutly.

Routes
------
``GET  /api/health``            service + catalogue status
``GET  /api/listings``          browse the catalogue
``GET  /api/sample-resume``     demo resume text + instant rule-based profile
``POST /api/profile/parse``     PDF upload or ``{text}`` -> StudentProfile
``POST /api/match``             ranked matches with trust + explanations
``POST /api/verify``            verify a stored listing or pasted listing text
``POST /api/kit``               gap analysis + resume bullets + cover note
``GET  /api/calendar.ics``      deadline calendar with 7/3/1-day reminders
"""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager, suppress
from typing import Any, AsyncIterator, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import calendar_utils
import kit as kit_module
import matching
import profile as profile_module
import seed as seed_module
import verify as verify_module
from config import APP_VERSION, get_settings
from db import get_db, init_db, session_scope
from llm import get_llm_client
from models import (
    HealthResponse,
    KitRequest,
    KitResponse,
    Listing,
    ListingOut,
    ListingsResponse,
    MatchMeta,
    MatchRequest,
    MatchResponse,
    ProfileParseResponse,
    SampleResumeResponse,
    VerifyRequest,
    VerifyResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
logger = logging.getLogger("scoutly.api")

settings = get_settings()

#: Startup warm-up state for the embedding model.
_warm: dict[str, Any] = {"done": False, "task": None, "backend": "", "count": 0, "error": None}

MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_RESUME_CHARS = 20_000


# ---------------------------------------------------------------------------
# Startup / embedding warm-up
# ---------------------------------------------------------------------------


def _warm_sync() -> int:
    """Load the embedding model and embed any uncached listings (blocking)."""
    engine = matching.get_embedding_engine()
    with session_scope() as session:
        listings = list(session.scalars(select(Listing)).all())
        count = matching.compute_missing_embeddings(session, engine, listings)
        _warm["backend"] = engine.backend
    return count


async def _warm_embeddings() -> None:
    """Warm embeddings off the event loop so the API is usable immediately."""
    try:
        count = await asyncio.to_thread(_warm_sync)
        _warm["count"] = count
        logger.info(
            "Embeddings ready (backend=%s, newly embedded=%s listings)",
            _warm.get("backend"),
            count,
        )
    except Exception as exc:  # never crash the app because of embeddings
        _warm["error"] = str(exc)
        logger.exception("Embedding warm-up failed; matching will fall back to keyword signals")
    finally:
        _warm["done"] = True


async def ensure_embeddings_ready(timeout: float = 120.0) -> None:
    """Wait for the warm-up task, but never longer than ``timeout`` seconds."""
    task = _warm.get("task")
    if task is None or task.done():
        return
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("Embedding warm-up still running after %.0fs; ranking without it", timeout)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create tables, auto-seed when empty, then warm embeddings in the background."""
    init_db()
    try:
        count = seed_module.ensure_seeded()
        logger.info(
            "Startup complete: %s listings | mock_llm=%s | provider=%s | model=%s",
            count,
            settings.mock_mode,
            settings.provider,
            settings.llm_model,
        )
    except Exception:
        logger.exception("Database initialisation failed")
    _warm["task"] = asyncio.create_task(_warm_embeddings())
    yield
    task = _warm.get("task")
    if task is not None and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Scoutly API",
    description=(
        "Finds, verifies and explains student opportunities, then generates a tailored "
        "application kit. Sample data - not live listings."
    ),
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_listing_or_404(db: Session, listing_id: int) -> Listing:
    """Fetch a listing or raise a 404 with a helpful message."""
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} was not found.")
    return listing


def _wipe_note(notes: list[str | None]) -> str | None:
    """Return the first non-empty note from a set of LLM results."""
    for note in notes:
        if note:
            return note
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """Tiny landing payload so hitting the base URL is not a 404."""
    return {
        "name": "Scoutly API",
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
def health(db: Session = Depends(get_db)) -> HealthResponse:
    """Service status: LLM mode, catalogue size and embedding backend."""
    llm = get_llm_client()
    listing_count = db.scalar(select(func.count(Listing.id))) or 0
    backend = _warm.get("backend") or ("loading" if not _warm.get("done") else "unavailable")
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        mock_llm=llm.mock_mode,
        llm_provider=llm.provider,
        listings=int(listing_count),
        embeddings_backend=str(backend),
    )


@app.get("/api/listings", response_model=ListingsResponse, tags=["listings"])
def list_listings(
    types: str | None = Query(default=None, description="Comma-separated types, e.g. internship,hackathon"),
    mode: str | None = Query(default=None, description="remote | onsite | hybrid"),
    limit: int = Query(default=60, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ListingsResponse:
    """Browse the seeded catalogue, soonest deadline first."""
    stmt = select(Listing)
    if types:
        wanted = [value.strip().lower() for value in types.split(",") if value.strip()]
        if wanted:
            stmt = stmt.where(Listing.type.in_(wanted))
    if mode:
        stmt = stmt.where(Listing.mode == mode.strip().lower())
    stmt = stmt.order_by(Listing.deadline.asc(), Listing.id.asc()).limit(limit)

    rows = list(db.scalars(stmt).all())
    return ListingsResponse(
        count=len(rows), listings=[ListingOut.model_validate(row) for row in rows]
    )


@app.get("/api/sample-resume", response_model=SampleResumeResponse, tags=["profile"])
def sample_resume() -> SampleResumeResponse:
    """Demo button: the bundled sample resume plus an instantly-parsed profile."""
    text = profile_module.load_sample_resume()
    extraction = profile_module.ProfileExtraction.model_validate(
        profile_module.heuristic_profile(text)
    )
    profile = profile_module.StudentProfile(**extraction.model_dump(), raw_text=text)
    return SampleResumeResponse(text=text, profile=profile)


@app.post("/api/profile/parse", response_model=ProfileParseResponse, tags=["profile"])
async def parse_profile(request: Request) -> ProfileParseResponse:
    """Extract an editable :class:`StudentProfile` from a PDF or pasted text."""
    content_type = (request.headers.get("content-type") or "").lower()

    source: Literal["pdf", "text"]
    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(
                status_code=400, detail="Attach your resume PDF in the 'file' field."
            )
        data = await upload.read()  # type: ignore[union-attr]
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(status_code=400, detail="That PDF is larger than 8 MB.")
        try:
            text = profile_module.extract_text_from_pdf(data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        source = "pdf"
    elif "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
        text = str((payload or {}).get("text") or "")
        source = "text"
    else:
        raise HTTPException(
            status_code=415,
            detail="Send a PDF as multipart/form-data, or JSON {\"text\": \"...\"}.",
        )

    if len(text.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail="That looks too short to read a profile from. Paste at least a few lines.",
        )

    try:
        profile, ai_available, note = await profile_module.parse_profile(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ProfileParseResponse(
        profile=profile,
        raw_text=text[:MAX_RESUME_CHARS],
        ai_available=ai_available,
        note=note,
        source=source,
    )


@app.post("/api/match", response_model=MatchResponse, tags=["matching"])
async def match_listings(req: MatchRequest, db: Session = Depends(get_db)) -> MatchResponse:
    """Rank listings for a profile, explaining every score and risk signal."""
    await ensure_embeddings_ready()

    listings = list(db.scalars(select(Listing).order_by(Listing.id)).all())
    if not listings:
        raise HTTPException(
            status_code=503,
            detail="The listing catalogue is empty. Run `python seed.py` in backend/ and retry.",
        )

    engine = matching.get_embedding_engine()
    profile_vector = engine.encode([matching.profile_document(req.profile)])[0]
    matrix = matching.load_embeddings_matrix(db, listings, engine)

    matches, meta = matching.rank_listings(
        req.profile,
        listings,
        profile_vector=profile_vector,
        listing_vectors=matrix,
        filters=req.filters,
        hide_risky=req.hide_risky,
        limit=req.limit,
    )

    client = get_llm_client()
    # Only the top 10 matches get a per-listing LLM explanation (as specified);
    # the rest keep the deterministic, facts-only copy from rank_listings.
    explained = matches[:10]
    results = await asyncio.gather(
        *(
            matching.explain_match(req.profile, match.listing, client=client)
            for match in explained
        )
    )
    notes: list[str | None] = []
    ai_flags: list[bool] = []
    for match, (why, ai_available, note) in zip(explained, results):
        match.why_it_fits = why
        ai_flags.append(ai_available)
        notes.append(note)

    return MatchResponse(
        matches=matches,
        meta=MatchMeta(
            candidates=int(meta["candidates"]),
            returned=len(matches),
            ai_available=bool(explained) and all(ai_flags),
            note=_wipe_note(notes),
            embeddings_backend=engine.backend,
        ),
    )


@app.post("/api/verify", response_model=VerifyResponse, tags=["verification"])
async def verify_listing(req: VerifyRequest, db: Session = Depends(get_db)) -> VerifyResponse:
    """Trust analysis for a stored listing, or for text pasted from anywhere."""
    client = get_llm_client()

    if req.listing_id is not None:
        listing = _get_listing_or_404(db, req.listing_id)
        all_listings = list(db.scalars(select(Listing)).all())
        conflicts = matching.duplicate_conflict_ids(all_listings)
        facts = verify_module.facts_from_listing(listing, duplicate_conflict=listing.id in conflicts)
        trust = verify_module.assess_facts(facts)
        trust, ai_available, note = await verify_module.second_opinion(facts, trust, client=client)
        return VerifyResponse(
            trust=trust,
            listing=ListingOut.model_validate(listing),
            ai_available=ai_available,
            note=note,
        )

    text = (req.text or "").strip()
    if len(text) < 20:
        raise HTTPException(
            status_code=400,
            detail="Provide either a listing_id or at least a couple of lines of listing text.",
        )

    facts = verify_module.facts_from_text(text)
    trust = verify_module.assess_facts(facts)
    trust, ai_available, note = await verify_module.second_opinion(facts, trust, client=client)
    return VerifyResponse(trust=trust, listing=None, ai_available=ai_available, note=note)


@app.post("/api/kit", response_model=KitResponse, tags=["kit"])
async def generate_kit(req: KitRequest, db: Session = Depends(get_db)) -> KitResponse:
    """Gap analysis, resume bullets and a cover note tailored to one listing."""
    listing = _get_listing_or_404(db, req.listing_id)
    listing_out = ListingOut.model_validate(listing)

    gap_analysis, application_kit, gap_ai, kit_ai, note = await kit_module.generate_kit(
        req.profile, listing_out, client=get_llm_client()
    )

    return KitResponse(
        listing=listing_out,
        gap_analysis=gap_analysis,
        resume_bullets=application_kit.resume_bullets,
        cover_note=application_kit.cover_note,
        why_me_one_liner=application_kit.why_me_one_liner,
        ai_available=bool(gap_ai and kit_ai),
        note=note,
    )


@app.get("/api/calendar.ics", tags=["calendar"])
def calendar_ics(
    listing_ids: str = Query(..., description="Comma-separated listing ids, e.g. 1,4,9"),
    db: Session = Depends(get_db),
) -> Response:
    """Download deadline events (with 7/3/1-day reminders) as an .ics file."""
    ids = [int(value) for value in re.findall(r"\d+", listing_ids)]
    if not ids:
        raise HTTPException(status_code=400, detail="Provide at least one listing id.")

    rows = list(db.scalars(select(Listing).where(Listing.id.in_(ids))).all())
    if not rows:
        raise HTTPException(status_code=404, detail="None of those listing ids exist.")

    rows.sort(key=lambda row: (row.deadline, row.id))
    try:
        content = calendar_utils.build_calendar(rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{calendar_utils.calendar_filename()}"'
        },
    )
