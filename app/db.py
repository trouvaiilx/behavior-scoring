"""
Lightweight SQLite persistence layer.

Every scoring run is stored with its rubric version, model used, raw model
output, and timestamp — this is the minimal audit trail: enough to trace 
back any score to exactly what produced it.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATABASE_PATH
from app.schemas import ScoreResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_label TEXT NOT NULL,
    job_role TEXT NOT NULL DEFAULT '',
    rubric_version TEXT NOT NULL,
    rubric_hash TEXT NOT NULL DEFAULT '',
    model_used TEXT NOT NULL,
    overall_summary TEXT NOT NULL DEFAULT '',
    dimension_scores_json TEXT NOT NULL,
    composite_score REAL NOT NULL,
    red_flag_status TEXT NOT NULL,
    red_flag_rationale TEXT NOT NULL,
    excluded_attributes_json TEXT NOT NULL,
    human_review_status TEXT NOT NULL DEFAULT 'pending',
    human_review_notes TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL DEFAULT '',
    raw_model_output TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

WEBHOOKS_SCHEMA = """
CREATE TABLE IF NOT EXISTS webhooks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    events_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(SCHEMA)
        conn.execute(WEBHOOKS_SCHEMA)
        # Migrations for DBs created before these columns existed.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(scores)")}
        if "overall_summary" not in existing_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN overall_summary TEXT NOT NULL DEFAULT ''")
        if "rubric_hash" not in existing_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN rubric_hash TEXT NOT NULL DEFAULT ''")
        if "job_role" not in existing_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN job_role TEXT NOT NULL DEFAULT ''")
        if "human_review_status" not in existing_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN human_review_status TEXT NOT NULL DEFAULT 'pending'")
        if "human_review_notes" not in existing_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN human_review_notes TEXT NOT NULL DEFAULT ''")
        if "reviewed_at" not in existing_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN reviewed_at TEXT NOT NULL DEFAULT ''")


def insert_webhook(url: str, events: list[str]) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO webhooks (url, events_json, created_at) VALUES (?, ?, ?)",
            (url, json.dumps(events), created_at),
        )
        return {
            "id": cur.lastrowid,
            "url": url,
            "events": events,
            "created_at": created_at,
        }


def list_webhooks() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM webhooks ORDER BY id DESC").fetchall()
        return [
            {
                "id": row["id"],
                "url": row["url"],
                "events": json.loads(row["events_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def save_score(result: ScoreResult) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    hr_status = result.human_review.status if result.human_review else "pending"
    hr_notes = result.human_review.notes if result.human_review else ""
    hr_reviewed_at = result.human_review.reviewed_at if result.human_review and result.human_review.reviewed_at else ""

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO scores (
                candidate_label, job_role, rubric_version, rubric_hash, model_used, overall_summary,
                dimension_scores_json, composite_score,
                red_flag_status, red_flag_rationale,
                excluded_attributes_json, human_review_status, human_review_notes, reviewed_at,
                raw_model_output, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.candidate_label,
                getattr(result, "job_role", "") or "",
                result.rubric_version,
                result.rubric_hash,
                result.model_used,
                result.overall_summary,
                json.dumps([d.model_dump() for d in result.dimension_scores]),
                result.composite_score,
                result.red_flag.status,
                result.red_flag.rationale,
                json.dumps(result.excluded_attributes_detected),
                hr_status,
                hr_notes,
                hr_reviewed_at,
                result.raw_model_output,
                created_at,
            ),
        )
        return cur.lastrowid


def _build_where_clause(
    search: str | None = None,
    red_flag_status: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    has_excluded_attributes: bool | None = None,
    human_review_status: str | None = None,
) -> tuple[str, list]:
    conditions = []
    params = []

    if search and search.strip():
        conditions.append("(candidate_label LIKE ? OR job_role LIKE ? OR overall_summary LIKE ?)")
        term = f"%{search.strip()}%"
        params.extend([term, term, term])

    if red_flag_status and red_flag_status.strip():
        conditions.append("red_flag_status = ?")
        params.append(red_flag_status.strip().lower())

    if human_review_status and human_review_status.strip():
        conditions.append("human_review_status = ?")
        params.append(human_review_status.strip().lower())

    if min_score is not None:
        conditions.append("composite_score >= ?")
        params.append(min_score)

    if max_score is not None:
        conditions.append("composite_score <= ?")
        params.append(max_score)

    if has_excluded_attributes is not None:
        if has_excluded_attributes:
            conditions.append("excluded_attributes_json != '[]'")
        else:
            conditions.append("excluded_attributes_json = '[]'")

    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    return where_sql, params


def list_scores(
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    red_flag_status: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    has_excluded_attributes: bool | None = None,
    human_review_status: str | None = None,
    sort_by: str = "id",
    sort_order: str = "desc",
) -> list[dict]:
    allowed_sort_cols = {"id": "id", "composite_score": "composite_score", "created_at": "created_at", "candidate_label": "candidate_label"}
    sort_col = allowed_sort_cols.get(sort_by, "id")
    order = "ASC" if sort_order.lower() == "asc" else "DESC"

    where_sql, params = _build_where_clause(
        search=search,
        red_flag_status=red_flag_status,
        min_score=min_score,
        max_score=max_score,
        has_excluded_attributes=has_excluded_attributes,
        human_review_status=human_review_status,
    )

    query = f"SELECT * FROM scores{where_sql} ORDER BY {sort_col} {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]


def count_scores(
    search: str | None = None,
    red_flag_status: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    has_excluded_attributes: bool | None = None,
    human_review_status: str | None = None,
) -> int:
    where_sql, params = _build_where_clause(
        search=search,
        red_flag_status=red_flag_status,
        min_score=min_score,
        max_score=max_score,
        has_excluded_attributes=has_excluded_attributes,
        human_review_status=human_review_status,
    )
    query = f"SELECT COUNT(*) AS n FROM scores{where_sql}"
    with _connect() as conn:
        row = conn.execute(query, params).fetchone()
        return row["n"]


def get_score(score_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM scores WHERE id = ?", (score_id,)).fetchone()
        return _row_to_dict(row) if row else None


def get_scores_by_ids(score_ids: list[int]) -> list[dict]:
    if not score_ids:
        return []
    placeholders = ",".join("?" for _ in score_ids)
    query = f"SELECT * FROM scores WHERE id IN ({placeholders})"
    with _connect() as conn:
        rows = conn.execute(query, score_ids).fetchall()
        # Maintain request order if possible
        id_map = {r["id"]: _row_to_dict(r) for r in rows}
        return [id_map[sid] for sid in score_ids if sid in id_map]


def update_human_review(score_id: int, status: str, notes: str) -> dict | None:
    reviewed_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE scores
            SET human_review_status = ?, human_review_notes = ?, reviewed_at = ?
            WHERE id = ?
            """,
            (status.lower(), notes.strip(), reviewed_at, score_id),
        )
        if cur.rowcount == 0:
            return None
    return get_score(score_id)


def delete_score(score_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM scores WHERE id = ?", (score_id,))
        return cur.rowcount > 0


def get_analytics_summary() -> dict:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM scores").fetchall()

    if not rows:
        return {
            "total_candidates": 0,
            "composite_score_stats": {"avg": 0.0, "median": 0.0, "min": 0.0, "max": 0.0},
            "red_flag_breakdown": {"pass": 0, "review": 0, "fail": 0},
            "human_review_breakdown": {"pending": 0, "approved": 0, "rejected": 0, "overridden": 0},
            "excluded_attributes_counts": {},
            "score_buckets": {"0_to_20": 0, "21_to_40": 0, "41_to_60": 0, "61_to_80": 0, "81_to_100": 0},
        }

    scores_list = [r["composite_score"] for r in rows]
    scores_list.sort()
    total = len(scores_list)

    avg_score = round(sum(scores_list) / total, 1)
    min_score = min(scores_list)
    max_score = max(scores_list)
    if total % 2 == 1:
        median_score = scores_list[total // 2]
    else:
        median_score = round((scores_list[total // 2 - 1] + scores_list[total // 2]) / 2.0, 1)

    red_flag_counts = {"pass": 0, "review": 0, "fail": 0}
    human_review_counts = {"pending": 0, "approved": 0, "rejected": 0, "overridden": 0}
    excluded_counts: dict[str, int] = {}
    buckets = {"0_to_20": 0, "21_to_40": 0, "41_to_60": 0, "61_to_80": 0, "81_to_100": 0}

    for r in rows:
        rf_status = r["red_flag_status"]
        if rf_status in red_flag_counts:
            red_flag_counts[rf_status] += 1

        hr_status = r["human_review_status"] or "pending"
        if hr_status in human_review_counts:
            human_review_counts[hr_status] += 1
        else:
            human_review_counts[hr_status] = 1

        # excluded attrs
        try:
            attrs = json.loads(r["excluded_attributes_json"])
            for attr in attrs:
                excluded_counts[attr] = excluded_counts.get(attr, 0) + 1
        except Exception:
            pass

        # buckets
        val = r["composite_score"]
        if val <= 20:
            buckets["0_to_20"] += 1
        elif val <= 40:
            buckets["21_to_40"] += 1
        elif val <= 60:
            buckets["41_to_60"] += 1
        elif val <= 80:
            buckets["61_to_80"] += 1
        else:
            buckets["81_to_100"] += 1

    return {
        "total_candidates": total,
        "composite_score_stats": {
            "avg": avg_score,
            "median": median_score,
            "min": min_score,
            "max": max_score,
        },
        "red_flag_breakdown": red_flag_counts,
        "human_review_breakdown": human_review_counts,
        "excluded_attributes_counts": excluded_counts,
        "score_buckets": buckets,
    }


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["dimension_scores"] = json.loads(d.pop("dimension_scores_json"))
    d["excluded_attributes_detected"] = json.loads(d.pop("excluded_attributes_json"))
    d["red_flag"] = {
        "status": d.pop("red_flag_status"),
        "rationale": d.pop("red_flag_rationale"),
    }
    d["human_review"] = {
        "status": d.pop("human_review_status", "pending") or "pending",
        "notes": d.pop("human_review_notes", "") or "",
        "reviewed_at": d.pop("reviewed_at", None) or None,
    }
    d["job_role"] = d.get("job_role", "") or ""
    return d

