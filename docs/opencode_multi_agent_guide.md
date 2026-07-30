# Behavior Scoring — Single Workspace Development & API Workflow Guide

> **Branch**: `API`  
> **Workspace**: `behavior-scoring`  
> **Updated**: July 27, 2026

This guide provides the official, streamlined development workflow for the **Candidate Social Media Behavior Scoring** backend. 

All development happens **directly in this workspace on the `API` branch**. There are no extra Git worktrees or feature branches — keeping Source Control clean and straightforward.

---

## 1. Single Workspace Architecture

Everything is consolidated into a single working directory on the **`API`** branch:

```
behavior-scoring/                (Branch: API)
├── app/                         # FastAPI backend, schemas, database, scoring logic
├── docs/                        # Project documentation, security audit, API reference
├── scripts/                     # Utility scripts (scraper bridge, report PDF generator)
├── static/                      # Minimal browser UI
├── tests/                       # Unit, integration, and Playwright E2E test suites
└── task.md                      # Milestone task tracking
```

---

## 2. Standard Development Workflow

Whenever you or an AI assistant add features, fix bugs, or write tests:

1. **Work directly in the `behavior-scoring` folder on the `API` branch.**
2. **Run test verification**:
   ```powershell
   # Run the full 88+ test suite
   venv\Scripts\python.exe -m pytest
   ```
3. **Commit & Push directly to `API`**:
   ```powershell
   git add .
   git commit -m "feat(api): description of your change"
   git push origin API
   ```

---

## 3. Implemented API Summary (15+ Endpoints)

| Category | Method | Endpoint | Purpose |
|----------|--------|----------|---------|
| **System** | `GET` | `/api/health` | Backend + Ollama + model reachability check |
| | `GET` | `/api/rubric` | Returns active rubric dimensions, weights, hash |
| **Auth** | `POST` | `/api/auth/token` | Issues Bearer access token for client credentials |
| **Scoring** | `POST` | `/api/score` | Evaluates single candidate text via Ollama |
| | `GET` | `/api/scores` | Paginated list with search, filter, and sort |
| | `GET` | `/api/scores/{id}` | Full score detail and rationale breakdown |
| | `DELETE` | `/api/scores/{id}` | Deletes a score run record |
| **Batch** | `POST` | `/api/scores/batch` | Submits candidate profile batch job |
| | `GET` | `/api/scores/batch/{batch_id}` | Polls batch job processing status |
| **Import** | `POST` | `/api/candidates/import` | Bulk-imports scraped candidate profiles to SQLite |
| **Webhooks** | `POST` | `/api/webhooks` | Registers webhook URLs for event notifications |
| **Review** | `PATCH` | `/api/scores/{id}/review` | Updates human audit review status and notes |
| **Analytics** | `GET` | `/api/scores/analytics` | Aggregated score distributions and metrics |
| | `GET` | `/api/scores/export` | CSV/JSON export download |
| | `GET` | `/api/scores/compare` | Side-by-side candidate score comparison |

---

## 4. Playwright Scraper Bridge Usage

To import data scraped by your Playwright scraper (`iSpy` project):

```powershell
# Run scraper bridge to import scraped candidate JSON into the API:
venv\Scripts\python.exe scripts/scraper_bridge.py path/to/scraped_profiles.json
```

---

## 5. Summary

- **Source Control**: Clean, single branch (`API`).
- **Zero Worktrees**: All code lives in this directory.
- **Full Quality Enforcement**: 88 automated unit, contract, and Playwright E2E tests passing.
