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
    rubric_version TEXT NOT NULL,
    rubric_hash TEXT NOT NULL DEFAULT '',
    model_used TEXT NOT NULL,
    overall_summary TEXT NOT NULL DEFAULT '',
    dimension_scores_json TEXT NOT NULL,
    composite_score REAL NOT NULL,
    red_flag_status TEXT NOT NULL,
    red_flag_rationale TEXT NOT NULL,
    excluded_attributes_json TEXT NOT NULL,
    raw_model_output TEXT NOT NULL,
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
        # Migrations for DBs created before these columns existed.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(scores)")}
        if "overall_summary" not in existing_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN overall_summary TEXT NOT NULL DEFAULT ''")
        if "rubric_hash" not in existing_cols:
            conn.execute("ALTER TABLE scores ADD COLUMN rubric_hash TEXT NOT NULL DEFAULT ''")


def save_score(result: ScoreResult) -> int:
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO scores (
                candidate_label, rubric_version, rubric_hash, model_used, overall_summary,
                dimension_scores_json, composite_score,
                red_flag_status, red_flag_rationale,
                excluded_attributes_json, raw_model_output, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.candidate_label,
                result.rubric_version,
                result.rubric_hash,
                result.model_used,
                result.overall_summary,
                json.dumps([d.model_dump() for d in result.dimension_scores]),
                result.composite_score,
                result.red_flag.status,
                result.red_flag.rationale,
                json.dumps(result.excluded_attributes_detected),
                result.raw_model_output,
                created_at,
            ),
        )
        return cur.lastrowid


def list_scores(limit: int = 50, offset: int = 0) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM scores ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def count_scores() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM scores").fetchone()
        return row["n"]


def get_score(score_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM scores WHERE id = ?", (score_id,)).fetchone()
        return _row_to_dict(row) if row else None


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["dimension_scores"] = json.loads(d.pop("dimension_scores_json"))
    d["excluded_attributes_detected"] = json.loads(d.pop("excluded_attributes_json"))
    d["red_flag"] = {
        "status": d.pop("red_flag_status"),
        "rationale": d.pop("red_flag_rationale"),
    }
    return d
