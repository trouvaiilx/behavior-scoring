"""
FastAPI backend for the candidate social-media behavior scoring prototype.

Run with:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000 for the built-in test UI, or
http://127.0.0.1:8000/docs for interactive API docs (Swagger UI).
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db, ollama_client
from app.config import CORS_ALLOW_ORIGINS, DEFAULT_SCORES_LIMIT, MAX_SCORES_LIMIT, RUBRIC_VERSION
from app.rubric import DIMENSIONS, EXCLUDED_ATTRIBUTES, RED_FLAG_WEIGHT_NOTE, rubric_hash
from app.schemas import CandidateProfileInput, ScoreResult
from app.scoring import ScoringError, score_candidate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    logger.info("Database initialized.")
    yield


app = FastAPI(
    title="Candidate Social Media Behavior Scoring — Prototype API",
    description=(
        "Internal R&D prototype. Scores candidate text against a rubric "
        "using a local LLM via Ollama. NOT for production hiring decisions."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS is wide open by default because this is meant for local,
# single-user use bound to 127.0.0.1. Set CORS_ALLOW_ORIGINS in .env to an
# explicit list before exposing this beyond localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    """Reports whether the backend and Ollama are reachable, and whether
    the configured model is actually pulled locally."""
    ollama_status = await ollama_client.check_connection()
    return {"backend": "ok", "ollama": ollama_status}


@app.get("/api/rubric")
def get_rubric():
    """Returns the active rubric so the frontend (or a curious reviewer)
    can see exactly what's being scored and why, without reading the code."""
    return {
        "dimensions": DIMENSIONS,
        "red_flag_note": RED_FLAG_WEIGHT_NOTE,
        "excluded_attributes": EXCLUDED_ATTRIBUTES,
        "rubric_version": RUBRIC_VERSION,
        "rubric_hash": rubric_hash(),
    }


@app.post("/api/score", response_model=ScoreResult)
async def create_score(profile: CandidateProfileInput):
    try:
        result = await score_candidate(profile)
    except ScoringError as e:
        logger.error("Scoring failed for candidate '%s': %s", profile.candidate_label, e)
        raise HTTPException(status_code=502, detail=str(e))

    score_id = db.save_score(result)
    result.id = score_id
    logger.info("Saved score run id=%s for candidate '%s'.", score_id, profile.candidate_label)
    return result


@app.get("/api/scores")
def get_scores(
    limit: int = Query(default=DEFAULT_SCORES_LIMIT, ge=1, le=MAX_SCORES_LIMIT),
    offset: int = Query(default=0, ge=0),
):
    return {
        "results": db.list_scores(limit=limit, offset=offset),
        "total": db.count_scores(),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/scores/{score_id}")
def get_score_detail(score_id: int):
    result = db.get_score(score_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Score not found")
    return result


# Serve the minimal test UI (static/index.html) at the root path.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
