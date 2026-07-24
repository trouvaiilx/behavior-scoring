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

# ---------------------------------------------------------------------------
# Rubric versioning (bump this whenever rubric.py weights/dimensions change,
# so stored scores can always be traced back to the rubric version that
# produced them.)
# ---------------------------------------------------------------------------
RUBRIC_VERSION = "0.1.0"
