import csv
import io
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db, ollama_client
from app.config import (
    CORS_ALLOW_ORIGINS,
    DEFAULT_SCORES_LIMIT,
    MAX_SCORES_LIMIT,
    RUBRIC_VERSION,
)
from app.rubric import (
    DIMENSIONS,
    EXCLUDED_ATTRIBUTES,
    RED_FLAG_WEIGHT_NOTE,
    rubric_hash,
)
from app.schemas import (
    AnalyticsSummaryResponse,
    BatchJobStatusResponse,
    BatchScoreRequest,
    CandidateComparisonResponse,
    CandidateProfileInput,
    HumanReviewUpdate,
    ScoreResult,
)
from app.scoring import ScoringError, score_candidate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

_batch_store: dict[str, dict] = {}


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
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _process_batch_job(batch_id: str, profiles: list[CandidateProfileInput]):
    job = _batch_store[batch_id]
    job["status"] = "processing"
    for profile in profiles:
        try:
            res = await score_candidate(profile)
            sid = db.save_score(res)
            res.id = sid
            job["results"].append(
                {
                    "candidate_label": profile.candidate_label,
                    "status": "completed",
                    "score_result": res.model_dump(),
                    "error": None,
                }
            )
            job["completed_items"] += 1
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Batch item failed for candidate '%s': %s", profile.candidate_label, e
            )
            job["results"].append(
                {
                    "candidate_label": profile.candidate_label,
                    "status": "failed",
                    "score_result": None,
                    "error": str(e),
                }
            )
            job["failed_items"] += 1

    job["status"] = "completed" if job["failed_items"] < len(profiles) else "failed"


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
        logger.error(
            "Scoring failed for candidate '%s': %s", profile.candidate_label, e
        )
        raise HTTPException(status_code=502, detail=str(e))

    score_id = db.save_score(result)
    result.id = score_id
    logger.info(
        "Saved score run id=%s for candidate '%s'.", score_id, profile.candidate_label
    )
    return result


@app.get("/api/scores")
def get_scores(
    limit: int = Query(default=DEFAULT_SCORES_LIMIT, ge=1, le=MAX_SCORES_LIMIT),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(
        default=None, description="Search term for candidate label, role, or summary"
    ),
    red_flag_status: str | None = Query(
        default=None, description="Filter by status: pass, review, fail"
    ),
    human_review_status: str | None = Query(
        default=None,
        description="Filter by human review: pending, approved, rejected, overridden",
    ),
    min_score: float | None = Query(default=None, ge=0.0, le=100.0),
    max_score: float | None = Query(default=None, ge=0.0, le=100.0),
    has_excluded_attributes: bool | None = Query(default=None),
    sort_by: str = Query(
        default="id", pattern="^(id|composite_score|created_at|candidate_label)$"
    ),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    results = db.list_scores(
        limit=limit,
        offset=offset,
        search=search,
        red_flag_status=red_flag_status,
        min_score=min_score,
        max_score=max_score,
        has_excluded_attributes=has_excluded_attributes,
        human_review_status=human_review_status,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    total = db.count_scores(
        search=search,
        red_flag_status=red_flag_status,
        min_score=min_score,
        max_score=max_score,
        has_excluded_attributes=has_excluded_attributes,
        human_review_status=human_review_status,
    )
    return {
        "results": results,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "search": search,
            "red_flag_status": red_flag_status,
            "human_review_status": human_review_status,
            "min_score": min_score,
            "max_score": max_score,
            "has_excluded_attributes": has_excluded_attributes,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    }


@app.get("/api/scores/analytics", response_model=AnalyticsSummaryResponse)
def get_analytics():
    """Returns aggregated metrics, red flag counts, and score distribution buckets across all runs."""
    return db.get_analytics_summary()


@app.get("/api/scores/export")
def export_scores(
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    search: str | None = Query(default=None),
    red_flag_status: str | None = Query(default=None),
    human_review_status: str | None = Query(default=None),
    min_score: float | None = Query(default=None),
    max_score: float | None = Query(default=None),
):
    scores = db.list_scores(
        limit=10000,
        offset=0,
        search=search,
        red_flag_status=red_flag_status,
        min_score=min_score,
        max_score=max_score,
        human_review_status=human_review_status,
        sort_by="id",
        sort_order="desc",
    )

    if format == "json":
        json_data = json.dumps(scores, indent=2)
        return Response(
            content=json_data,
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="candidate_scores_export.json"'
            },
        )

    # CSV format
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "candidate_label",
            "job_role",
            "composite_score",
            "red_flag_status",
            "red_flag_rationale",
            "human_review_status",
            "human_review_notes",
            "reviewed_at",
            "excluded_attributes_detected",
            "overall_summary",
            "rubric_version",
            "model_used",
            "created_at",
        ]
    )

    for s in scores:
        writer.writerow(
            [
                s.get("id"),
                s.get("candidate_label"),
                s.get("job_role", ""),
                s.get("composite_score"),
                s.get("red_flag", {}).get("status"),
                s.get("red_flag", {}).get("rationale"),
                s.get("human_review", {}).get("status"),
                s.get("human_review", {}).get("notes"),
                s.get("human_review", {}).get("reviewed_at") or "",
                ", ".join(s.get("excluded_attributes_detected", [])),
                s.get("overall_summary", ""),
                s.get("rubric_version"),
                s.get("model_used"),
                s.get("created_at"),
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="candidate_scores_export.csv"'
        },
    )


@app.get("/api/scores/compare", response_model=CandidateComparisonResponse)
def compare_candidates(
    ids: str = Query(..., description="Comma-separated score IDs, e.g. '1,2,5'"),
):
    try:
        id_list = [int(i.strip()) for i in ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid score ID list format. Expected comma-separated integers.",
        )

    if not id_list:
        raise HTTPException(
            status_code=400, detail="Must provide at least one score ID."
        )

    scores = db.get_scores_by_ids(id_list)
    if not scores:
        raise HTTPException(
            status_code=404, detail="No score runs found for the provided IDs."
        )

    # Calculate dimension averages and red flags summary
    dimension_totals: dict[str, float] = {}
    dimension_counts: dict[str, int] = {}
    red_flags_summary = {"pass": 0, "review": 0, "fail": 0}

    highest_candidate = None
    lowest_candidate = None
    highest_score = -1.0
    lowest_score = 101.0

    for s in scores:
        comp = s["composite_score"]
        label = s["candidate_label"]
        if comp > highest_score:
            highest_score = comp
            highest_candidate = label
        if comp < lowest_score:
            lowest_score = comp
            lowest_candidate = label

        rf_status = s["red_flag"]["status"]
        if rf_status in red_flags_summary:
            red_flags_summary[rf_status] += 1

        for d in s["dimension_scores"]:
            key = d["key"]
            val = d["score"]
            dimension_totals[key] = dimension_totals.get(key, 0.0) + val
            dimension_counts[key] = dimension_counts.get(key, 0) + 1

    dimension_averages = {
        k: round(dimension_totals[k] / dimension_counts[k], 1) for k in dimension_totals
    }

    return {
        "candidates": scores,
        "dimension_averages": dimension_averages,
        "highest_scoring_candidate": highest_candidate,
        "lowest_scoring_candidate": lowest_candidate,
        "red_flags_summary": red_flags_summary,
    }


@app.get("/api/scores/{score_id}")
def get_score_detail(score_id: int):
    result = db.get_score(score_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Score not found")
    return result


@app.patch("/api/scores/{score_id}/review")
def update_human_review(score_id: int, review_update: HumanReviewUpdate):
    """Updates human review status (pending, approved, rejected, overridden) and notes for a score run."""
    updated = db.update_human_review(
        score_id, review_update.status, review_update.notes
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Score run not found")
    return updated


@app.delete("/api/scores/{score_id}")
def delete_score_run(score_id: int):
    """Deletes a single score run by ID."""
    success = db.delete_score(score_id)
    if not success:
        raise HTTPException(status_code=404, detail="Score run not found")
    return {"message": "Score run deleted", "id": score_id}


@app.post("/api/scores/batch", response_model=BatchJobStatusResponse)
async def create_batch_score(req: BatchScoreRequest, background_tasks: BackgroundTasks):
    batch_id = str(uuid.uuid4())[:8]
    job_status = {
        "batch_id": batch_id,
        "status": "processing",
        "total_items": len(req.profiles),
        "completed_items": 0,
        "failed_items": 0,
        "results": [],
    }
    _batch_store[batch_id] = job_status
    background_tasks.add_task(_process_batch_job, batch_id, req.profiles)
    return job_status


@app.get("/api/scores/batch/{batch_id}", response_model=BatchJobStatusResponse)
def get_batch_status(batch_id: str):
    job = _batch_store.get(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return job


# Serve the minimal test UI (static/index.html) at the root path.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
