"""
FastAPI backend for the candidate social-media behavior scoring prototype.

Run with:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000 for the built-in test UI, or
http://127.0.0.1:8000/docs for interactive API docs (Swagger UI).
"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app import db, ollama_client
from app.schemas import CandidateProfileInput, ScoreResult
from app.scoring import score_candidate, ScoringError
from app.rubric import DIMENSIONS, RED_FLAG_WEIGHT_NOTE, EXCLUDED_ATTRIBUTES

app = FastAPI(
    title="Candidate Social Media Behavior Scoring — Prototype API",
    description=(
        "Internal R&D prototype. Scores candidate text against a rubric "
        "using a local LLM via Ollama. NOT for production hiring decisions."
    ),
    version="0.1.0",
)

# Permissive CORS for local prototype use only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    db.init_db()


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
    }


@app.post("/api/score", response_model=ScoreResult)
async def create_score(profile: CandidateProfileInput):
    try:
        result = await score_candidate(profile)
    except ScoringError as e:
        raise HTTPException(status_code=502, detail=str(e))

    score_id = db.save_score(result)
    result.id = score_id
    return result


@app.get("/api/scores")
def get_scores(limit: int = 50):
    return db.list_scores(limit=limit)


@app.get("/api/scores/{score_id}")
def get_score_detail(score_id: int):
    result = db.get_score(score_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Score not found")
    return result


# Serve the minimal test UI (static/index.html) at the root path.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
