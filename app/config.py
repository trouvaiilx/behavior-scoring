"""
Central configuration for the backend.

All values can be overridden via a `.env` file in the project root
(copy `.env.example` to `.env` and edit it) or via real environment
variables. Nothing here should be hardcoded for production use.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present (does nothing if it doesn't exist)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Ollama (local LLM) configuration
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# TODO: Replace with your actual Ollama model name (see .env.example).
# This placeholder intentionally will NOT work until you set it, either by
# editing .env or by setting the OLLAMA_MODEL environment variable.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "REPLACE_WITH_YOUR_MODEL")

OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/scores.db")

# Development-only shared secret for the prototype token endpoint.
API_SECRET_KEY = "dev-secret-key-change-in-prod"

# ---------------------------------------------------------------------------
# Rubric versioning (bump this whenever rubric.py weights/dimensions change,
# so stored scores can always be traced back to the rubric version that
# produced them.)
#
# RUBRIC_VERSION is the human-chosen label. RUBRIC_HASH (computed in
# app/rubric.py from the actual DIMENSIONS/EXCLUDED_ATTRIBUTES content) is a
# deterministic fingerprint that catches the case where someone edits the
# rubric and forgets to bump the version string by hand.
# ---------------------------------------------------------------------------
RUBRIC_VERSION = "0.2.0"

# ---------------------------------------------------------------------------
# Input limits (prototype safeguard against oversized requests hammering a
# local model for a very long time, or blowing past its context window).
# ---------------------------------------------------------------------------
MAX_FIELD_CHARS = int(os.getenv("MAX_FIELD_CHARS", "8000"))

# ---------------------------------------------------------------------------
# CORS
#
# Wide-open CORS is acceptable ONLY because this is meant to run bound to
# 127.0.0.1 for a single local user. If this is ever exposed beyond
# localhost, set CORS_ALLOW_ORIGINS to an explicit comma-separated list.
# ---------------------------------------------------------------------------
_cors_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
CORS_ALLOW_ORIGINS = (
    ["*"]
    if _cors_env == "*"
    else [o.strip() for o in _cors_env.split(",") if o.strip()]
)

# ---------------------------------------------------------------------------
# Pagination defaults for GET /api/scores
# ---------------------------------------------------------------------------
DEFAULT_SCORES_LIMIT = 50
MAX_SCORES_LIMIT = 200
