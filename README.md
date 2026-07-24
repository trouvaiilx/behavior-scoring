# Behavior Scoring — Backend Prototype

Internal R&D prototype for the "Social Media Behavior Scoring for Candidate
Screening" project. Scores candidate text (from safe/consented/synthetic
sources only) against a rubric using a **local** LLM via **Ollama** — no
data leaves your machine.

**This is a research prototype, not a hiring decision system.** Every score
must be reviewed by a human before it influences anything.

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
ollama pull llama3.1
```
(Other options: `mistral`, `qwen2.5`, `gemma2` — bigger models score better
but need more RAM/VRAM. Run `ollama list` anytime to see what you have.)

**Remember the exact model name you pulled** — you'll set it as
`OLLAMA_MODEL` in step 3 below. This project ships with a placeholder
(`REPLACE_WITH_YOUR_MODEL`) that will intentionally fail until you set it.

---

## 2. Where to put these files

Extract/copy all the files from this project into:
```
C:\Users\Yuuji\behavior-scoring
```

You should end up with this structure:
```
C:\Users\Yuuji\behavior-scoring\
  app\
    __init__.py
    config.py
    db.py
    main.py
    ollama_client.py
    rubric.py
    schemas.py
    scoring.py
  static\
    app.js
    index.html
    style.css
  data\                (created automatically on first run)
  .env.example
  README.md
  requirements.txt
```

---

## 3. Set up the Python environment

Open **Command Prompt** (or PowerShell) and run:

```bat
cd C:\Users\Yuuji\behavior-scoring

:: create a virtual environment
python -m venv venv

:: activate it (Command Prompt)
venv\Scripts\activate.bat

:: (if using PowerShell instead, use this activation command instead)
:: venv\Scripts\Activate.ps1

:: install dependencies
pip install -r requirements.txt
```

You'll know the venv is active because your prompt will show `(venv)` at
the start of the line. Run every command below from inside this activated
venv.

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
OLLAMA_MODEL=llama3.1
```
Save the file.

---

## 5. Run the backend

Make sure Ollama is running in the background (it usually auto-starts; if
unsure, just run `ollama serve` in a separate terminal window and leave it
open).

Then, with your venv activated:
```bat
uvicorn app.main:app --reload
```

You should see output ending with something like:
```
Uvicorn running on http://127.0.0.1:8000
```

---

## 6. Try it out

- Open **http://127.0.0.1:8000** in your browser — a simple test page to
  submit sample candidate text and see the rubric-based score.
- Open **http://127.0.0.1:8000/docs** for interactive Swagger API docs, if
  you'd rather call the API directly (useful for testing from Postman,
  curl, or another script).
- The banner at the top of the test page tells you immediately if Ollama
  isn't reachable or if the model isn't pulled yet.

Every scoring run is saved to a local SQLite database at
`data\scores.db`, with the rubric version, model used, and raw model
output — visible in the "Past Runs" table on the test page, or via
`GET /api/scores`.

---

## 7. API summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Check backend + Ollama + model availability |
| GET | `/api/rubric` | Return the active scoring rubric (dimensions, weights, exclusions) |
| POST | `/api/score` | Score a candidate profile (see `CandidateProfileInput` in `app/schemas.py`) |
| GET | `/api/scores` | List past scoring runs (audit trail) |
| GET | `/api/scores/{id}` | Get one past run in full detail, including raw model output |

---

## 8. Important reminders

- Only use **sample, synthetic, or explicitly consented** text as input
  while this is a prototype.
- The composite score **excludes** the Red Flag Screen — that's a
  pass/review/fail gate, not something averaged into the number.
- The rubric (`app/rubric.py`) is the single source of truth for
  dimensions/weights. Change it there — the prompt and the composite-score
  math both read from it automatically, so they can't drift out of sync.
- This prototype does **not** implement authentication, rate limiting, or
  production-grade error handling — it is for local, single-user R&D use
  only.

---

## 9. Common issues

**"Cannot reach Ollama at the configured URL"**
Ollama isn't running. Open a terminal and run `ollama serve`, then refresh
the test page.

**"model 'X' was not found locally"**
Run `ollama pull <model-name>` for whichever model you set in `.env`, then
restart the backend.

**Scoring is very slow / times out**
Larger models are slower on CPU-only machines. Try a smaller model (e.g.
`llama3.1:8b` or similar) or increase `OLLAMA_TIMEOUT` in `.env`.

**Model output fails to parse as JSON**
Some smaller/older models don't reliably follow the `format: json`
instruction. If this happens often, try a different model — this is
exactly the kind of consistency issue Track A (rubric validation) is meant
to surface, so it's useful information, not just a bug.
