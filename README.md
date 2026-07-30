# Behavior Scoring — Prototype

Internal R&D prototype for the "Social Media Behavior Scoring for Candidate
Screening" project. Scores candidate profiles (from safe/consented/synthetic
sources only) against a rubric using a **local** LLM via **Ollama** — no
data leaves your machine.

**This is a research prototype, not a hiring decision system.** Every score
must be reviewed by a human before it influences anything.

---

## Table of Contents

- [1. What you need to install first](#1-what-you-need-to-install-first)
  - [1.1 Python](#11-python)
  - [1.2 Ollama (local LLM runtime)](#12-ollama-local-llm-runtime)
  - [1.3 Pull a model](#13-pull-a-model)
- [2. Project structure](#2-project-structure)
- [3. Set up the Python environment](#3-set-up-the-python-environment)
- [4. Configure your model](#4-configure-your-model)
- [5. Run the backend](#5-run-the-backend)
- [6. Try it out](#6-try-it-out)
- [7. API summary (all 17 endpoints)](#7-api-summary-all-17-endpoints)
- [7a. Running the tests](#7a-running-the-tests)
- [7b. Scraper Bridge & Automated Pipeline](#7b-scraper-bridge--automated-pipeline)
- [8. Important reminders](#8-important-reminders)
- [9. Common issues](#9-common-issues)

---

## 1. What you need to install first

### 1.1 Python

Install Python 3.11 or newer: https://www.python.org/downloads/
During install on Windows, check **"Add python.exe to PATH"**.

Verify in Command Prompt / PowerShell:

```
python --version
```

### 1.2 Ollama (local LLM runtime)

Download and install for Windows: https://ollama.com/download

After installing, Ollama runs a local server at `http://localhost:11434`
automatically (it also starts on login). Verify it's running:

```
ollama --version
```

### 1.3 Pull a model

Pick a model to use locally. For a first try on a normal laptop, a smaller
model is easiest, e.g.:

```
ollama pull qwen2.5
```

(Other options: `mistral`, `llama3.1`, `gemma2`, `qwen3` — bigger models score
better but need more RAM/VRAM. Run `ollama list` anytime to see what you have.)

**Remember the exact model name you pulled** — you'll set it as
`OLLAMA_MODEL` in step 4 below. This project ships with a placeholder
(`REPLACE_WITH_YOUR_MODEL`) that will intentionally fail until you set it.

---

## 2. Project structure

```
behavior-scoring/
  app/
    __init__.py
    config.py
    db.py              ← SQLite layer (4 tables, WAL mode)
    main.py            ← FastAPI app — all 17 endpoints
    ollama_client.py
    rubric.py
    schemas.py         ← Pydantic v2 request/response models
    scoring.py         ← LLM rubric evaluation engine
    web_search.py      ← Live GitHub + DuckDuckGo footprint search
  scripts/
    scraper_bridge.py      ← CLI: import Playwright-scraped JSON → DB
    scrape_and_score.py    ← Automated scrape → import → LLM score pipeline
    generate_pdf_report.py ← PDF report generator (coming soon)
  static/
    app.js
    index.html         ← 6-tab interactive dashboard
    style.css
  tests/
    e2e/
      test_api_playwright.py
      test_auth_import_playwright.py
      test_auth_playwright.py
      test_webhooks_playwright.py
    integration/
      test_backend_features.py
      test_route_contracts.py
    unit/
      test_rubric.py
      test_scoring.py
    test_rubric.py
    test_samples.py
    test_scoring.py
  sample_data/           ← sample JSON profiles for testing
  docs/                  ← project documentation
  data/                  ← created automatically on first run (scores.db)
  .env.example
  pytest.ini
  README.md
  requirements.txt
```

---

## 3. Set up the Python environment

Open **Command Prompt** (or PowerShell) and run:

```bat
cd path\to\behavior-scoring

:: create a virtual environment
python -m venv venv

:: activate it (Command Prompt)
venv\Scripts\activate.bat

:: (if using PowerShell instead)
:: venv\Scripts\Activate.ps1

:: install dependencies
pip install -r requirements.txt
```

You'll know the venv is active because your prompt will show `(venv)` at
the start of the line. Run every command below from inside this activated venv.

---

## 4. Configure your model

```bat
copy .env.example .env
```

Open the new `.env` file in Notepad (or any editor) and replace:

```
OLLAMA_MODEL=REPLACE_WITH_YOUR_MODEL
```

with the model you pulled in step 1.3, e.g.:

```
OLLAMA_MODEL=qwen2.5
```

Save the file.

---

## 5. Run the backend

Make sure Ollama is running in the background (it usually auto-starts; if
unsure, run `ollama serve` in a separate terminal and leave it open).

Then, with your venv activated:

```bat
uvicorn app.main:app --reload
```

You should see:

```
Uvicorn running on http://127.0.0.1:8000
```

---

## 6. Try it out

- **http://127.0.0.1:8000** — Interactive 6-tab dashboard:
  - **Analyze** — Submit candidate text for LLM scoring
  - **History** — Browse and review past scoring runs
  - **Analytics** — Aggregate stats and score distribution charts
  - **Compare** — Side-by-side comparison of multiple candidates
  - **Batch** — Submit up to 20 profiles for background scoring
  - **Social & Scrape** — Upload Playwright-scraped JSON or run a live internet/GitHub footprint search
- **http://127.0.0.1:8000/docs** — Interactive Swagger API docs (useful for Postman, curl, or scripting)

Every scoring run is saved to `data/scores.db` (SQLite, WAL mode) with the
rubric version, model used, and raw model output.

---

## 7. API summary (all 17 endpoints)

### System & Health

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/api/health` | Check backend + Ollama + model availability |
| GET | `/api/rubric` | Return active rubric (dimensions, weights, exclusions, version, hash) |
| GET | `/api/samples` | Return built-in sample preset profiles |

### Core Scoring & Human Review

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/score` | Score a candidate profile using the local LLM |
| GET | `/api/scores?limit=&offset=` | List past scoring runs, paginated |
| GET | `/api/scores/{id}` | Get one past run in full detail (including raw model output) |
| PATCH | `/api/scores/{id}/review` | Update human review status (`pending`/`approved`/`rejected`/`overridden`) and notes |
| DELETE | `/api/scores/{id}` | Delete a single past run |

### Batch Scoring

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/scores/batch` | Submit up to 20 profiles to score in the background; returns `batch_id` immediately |
| GET | `/api/scores/batch/{batch_id}` | Poll a batch job's status and results |

### Analytics, Export & Comparison

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/api/scores/analytics` | Aggregate stats (score distribution, red-flag and review breakdowns) |
| GET | `/api/scores/export` | Export past runs as CSV or JSON (`?format=csv\|json`) |
| GET | `/api/scores/compare?ids=` | Compare multiple past runs by ID (comma-separated) with per-dimension averages |

### Integration & Security

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/auth/token` | Issue a Bearer token (OAuth2 client credentials) |
| POST | `/api/candidates/import` | Bulk import Playwright-scraped candidate profiles (JSON) into the database |
| POST | `/api/webhooks` | Register a webhook URL to receive scoring event notifications |

### Advanced Internet & Digital Footprint

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/candidates/live-search` | Real-time GitHub API + DuckDuckGo web search to score a candidate's digital footprint |
| POST | `/api/rubric/versions` | Register a custom rubric version with dynamic dimensions and weight distribution |
| GET | `/api/usage/stats` | Return operational metrics (total scores run, configured model, uptime) |

> **Pagination note:** `GET /api/scores` returns `{"results": [...], "total": 42, "limit": 50, "offset": 0}` — not a bare array — so pagination metadata is always available.

> **Rubric hash:** every score result includes `rubric_hash`, a short fingerprint of `app/rubric.py` at scoring time. This catches rubric dimension/weight changes that weren't reflected by bumping `RUBRIC_VERSION`.

> **Batch persistence:** batch job state is stored in SQLite (not in memory), so `GET /api/scores/batch/{id}` still returns results even if the server restarted mid-job. Rows older than 24 hours are cleaned up automatically on the next batch submission.

---

## 7a. Running the tests

96 tests cover unit logic, integration contracts, and full E2E API flows
via Playwright. The unit/integration tests do **not** require Ollama to be
running — the LLM call is mocked. The E2E tests do require the server to be
running (`uvicorn app.main:app`).

```bat
:: Run all tests
pytest

:: Run only unit + integration (no server needed)
pytest tests/unit tests/integration tests/test_rubric.py tests/test_scoring.py tests/test_samples.py

:: Run only E2E tests (server must be running)
pytest tests/e2e
```

Test layers:

| Layer | Files | Count |
| ----- | ----- | ----- |
| E2E API (Playwright) | `test_api_playwright.py` | 7 |
| E2E Auth & Import | `test_auth_import_playwright.py` | 2 |
| E2E Auth | `test_auth_playwright.py` | 6 |
| E2E Webhooks | `test_webhooks_playwright.py` | 2 |
| Integration | `test_backend_features.py` + `test_route_contracts.py` | 10 |
| Unit | `test_rubric.py` + `test_scoring.py` + `test_samples.py` + others | 69 |
| **Total** | | **96** |

---

## 7b. Scraper Bridge & Automated Pipeline

### Import a Playwright-scraped JSON file

```bat
venv\Scripts\python.exe scripts/scraper_bridge.py sample_data/sample_profiles.json
```

The JSON file must be an array of objects. Each object must include at minimum
`candidate_label`. Optional fields: `platform`, `bio`, `posts_sample`,
`comments_sample`, `network_notes`.

### Automated scrape → import → score pipeline

```bat
venv\Scripts\python.exe scripts/scrape_and_score.py
```

This runs the full pipeline: reads scraped output, imports profiles to the
database, then triggers LLM scoring for each candidate.

### Live internet footprint search (from the dashboard)

Open the **Social & Scrape** tab at `http://127.0.0.1:8000`, enter a
candidate name (e.g. a GitHub username), and click **Search & Score**. The
system queries GitHub's public API and DuckDuckGo web search in real time
and returns a composite behavioral score.

Or call the endpoint directly:

```bash
curl -X POST http://127.0.0.1:8000/api/candidates/live-search \
  -H "Content-Type: application/json" \
  -d '{"candidate_name": "torvalds", "job_role": "Engineer"}'
```

---

## 8. Important reminders

- Only use **sample, synthetic, or explicitly consented** text as input
  while this is a prototype.
- The composite score **excludes** the Red Flag Screen — that's a
  pass/review/fail gate, not something averaged into the number.
- The rubric (`app/rubric.py`) is the single source of truth for
  dimensions/weights. Change it there — the prompt and composite-score
  math both read from it automatically, so they can't drift out of sync.
- The excluded-attributes rule (`app/rubric.py` → `EXCLUDED_ATTRIBUTES`) is
  enforced via the prompt, plus a deterministic keyword backstop in
  `app/scoring.py`. The backstop scans the model's summary/rationale for
  excluded-attribute language it didn't self-report, and forces `"review"`
  status if found. Expect occasional false positives — that's the safer
  failure mode.
- **v0.2.0 rubric note:** earlier versions had dimension weights summing to
  0.75 instead of 1.0, silently under-scaling every composite score by 25%.
  Fixed in v0.2.0 (weights renormalized) and covered by
  `tests/test_rubric.py::test_total_weight_sums_to_one`.
- **Batch persistence:** batch job state used to live only in memory. It's
  now stored in SQLite (`batch_jobs` table) so results survive server
  restarts.
- **WAL mode:** `data/scores.db` runs in WAL mode. You may see sidecar files
  (`scores.db-wal`, `scores.db-shm`) while the app is running — these are
  normal and fold back into the main file on clean shutdown.

---

## 9. Common issues

**"Cannot reach Ollama at the configured URL"**
Ollama isn't running. Open a terminal and run `ollama serve`, then refresh
the page.

**"model 'X' was not found locally"**
Run `ollama pull <model-name>` for whichever model you set in `.env`, then
restart the backend.

**Scoring is very slow / times out**
Larger models are slower on CPU-only machines. Try a smaller model (e.g.
`qwen2.5` or `llama3.1:8b`) or increase `OLLAMA_TIMEOUT` in `.env`.

**Model output fails to parse as JSON**
Some smaller/older models don't reliably follow the `format: json` instruction.
Try a different model — this surfaces exactly the kind of consistency issues
this prototype is designed to measure.

**Import request failed with HTTP 405**
The server is not running or was restarted before the endpoint loaded. Make
sure `uvicorn app.main:app --reload` is running, then retry.

**Live search returns low scores / empty results**
GitHub API allows 60 unauthenticated requests/hour. If you hit the rate limit,
results will be partial. Add a `GITHUB_TOKEN` to `.env` to raise the limit to
5,000/hour.
