# Project Implementation Report

## Current Status

The core local R&D workflow is implemented: a user can submit consented or
synthetic profile text, score it with a locally hosted Ollama model, review the
result, and inspect or export the stored audit trail. The current application
version is `0.2.0` and uses rubric version `0.2.0`.

This remains a research prototype, not a production hiring-decision system.
Human review is required before any result influences a real-world decision.

## Delivered Functionality

| Area | Implementation status | Current capability |
| --- | --- | --- |
| Local application | Complete for prototype use | FastAPI backend serves the API and a minimal static browser UI from one local process. |
| LLM integration | Complete for prototype use | Calls a locally running Ollama model, requests JSON output, and surfaces connection/model failures to callers. |
| Input safeguards | Complete for prototype use | Candidate labels are validated; text fields are trimmed and bounded by configurable size limits. |
| Rubric scoring | Complete | Four weighted dimensions generate a 0-100 composite score. Weights total 1.0 and are covered by a regression test. |
| Red-flag workflow | Complete | A separate pass/review/fail gate is returned independently of the composite score. Invalid model statuses default safely to `review`. |
| Excluded-attribute safeguards | Complete for prototype use | Prompt instructions and a deterministic keyword backstop keep specified protected attributes out of scoring and escalate detected references to review. |
| Persistence and traceability | Complete | SQLite stores score inputs-derived results, rubric version/hash, model name, raw model output, timestamp, and human-review state. |
| Score management | Complete | Listing, filter/search/sort, detail retrieval, deletion, review updates, analytics, export, and candidate comparison are implemented. |
| Batch scoring | Complete for prototype use | Up to 20 profiles can be queued as an in-memory FastAPI background job and polled for item results. |
| Automated tests | Present | Tests cover rubric math, model-output handling, safety defaults, persistence, review workflow, filtering, analytics, export, comparison, and batch endpoint structure. |
| Project documentation | Complete | The API contract is maintained in `docs/api_reference.md`; this report records the current implementation state. |

## Implemented Architecture

| Component | Responsibility |
| --- | --- |
| `app/main.py` | FastAPI application setup and HTTP route handlers. |
| `app/schemas.py` | Pydantic request/response schemas and validation constraints. |
| `app/scoring.py` | Prompt construction, Ollama-result parsing, scoring validation, red-flag handling, and excluded-attribute backstop. |
| `app/rubric.py` | Single source of truth for scoring dimensions, weights, exclusions, version fingerprinting, and weighted-composite calculation. |
| `app/ollama_client.py` | Local Ollama health check and JSON-generation client. |
| `app/db.py` | SQLite schema initialization, persistence, filtering, analytics, review updates, and export-ready records. |
| `static/` | Minimal browser interface for submitting and inspecting prototype scoring runs. |
| `tests/` | Unit and API integration coverage using a temporary SQLite database and mocked model calls. |

## API Progress

Twelve application API routes are implemented and documented. They cover
health/rubric discovery, single and batch scoring, score-run lifecycle
management, analytics, export, and comparison.

| Capability | Routes |
| --- | --- |
| Service discovery | `GET /api/health`, `GET /api/rubric` |
| Scoring | `POST /api/score`, `POST /api/scores/batch`, `GET /api/scores/batch/{batch_id}` |
| Stored score runs | `GET /api/scores`, `GET /api/scores/{score_id}`, `DELETE /api/scores/{score_id}` |
| Human oversight | `PATCH /api/scores/{score_id}/review` |
| Analysis and portability | `GET /api/scores/analytics`, `GET /api/scores/export`, `GET /api/scores/compare` |

Full request fields, validation limits, error outcomes, content types, and
response contracts are in [API Reference](api_reference.md).

## Traceability and Safeguards

- Every saved score includes the configured model name, rubric version, rubric
  content hash, raw model output, and a UTC creation timestamp.
- The rubric hash complements the human-managed version number, so rubric
  edits are observable even if a manual version bump is missed.
- Red-flag screening is intentionally not averaged into the numerical score;
  it acts as a pass/review/fail escalation signal.
- Excluded attributes are defined centrally in the rubric and must not affect
  a dimension score. Detected references are reported and can escalate a run
  to `review`.
- Human reviewers can set an explicit review status and notes. The system
  stores the review timestamp with the score run.

## Operational Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL. |
| `OLLAMA_MODEL` | `REPLACE_WITH_YOUR_MODEL` | Model used for scoring; must be replaced with a pulled local model. |
| `OLLAMA_TIMEOUT` | `120` | Model request timeout in seconds. |
| `DATABASE_PATH` | `data/scores.db` | SQLite persistence location relative to the project root. |
| `MAX_FIELD_CHARS` | `8000` | Maximum length for each free-text profile field. |
| `CORS_ALLOW_ORIGINS` | `*` | CORS configuration intended only for local prototype operation. |

Use `GET /api/health` to confirm that the configured model is available before
submitting a scoring request.

## Documentation and Reporting

- `docs/api_reference.md` is the route-level API contract derived from
  `app/main.py` and the request/response schemas.
- `docs/project_report.md` is the current implementation-progress report.
- `scripts/generate_pdf_report.py` combines these Markdown files into a
  portable PDF using only the Python standard library.

Generate the default report with:

```powershell
python scripts/generate_pdf_report.py
```

The command writes `docs/project_report.pdf`. Provide one or more `--input`
arguments to compile a different documentation set, and `--output` to choose
another PDF path.

## Remaining Prototype Boundaries

The following items are intentionally outside the current implementation and
must be addressed before any broader or production deployment:

- Authentication, authorization, and tenant/data access controls are absent.
- Default CORS is permissive and is appropriate only for local use.
- There is no rate limiting, quota enforcement, audit-log access control, or
  formal data-retention/deletion policy.
- Batch-job state is stored only in process memory. It is lost on restart and
  has no durable queue, retry policy, cancellation, or worker isolation.
- SQLite is sufficient for a single-user prototype but not a multi-user,
  highly available deployment strategy.
- LLM scoring and keyword detection need formal fairness, legal, security,
  privacy, and domain validation before use with real candidate data.
- External Ollama availability and model quality remain operational
  dependencies; automated tests mock model calls rather than validate a
  specific locally installed model.

## Recommended Next Priorities

1. Establish governance and approval criteria for permitted data, reviewer
   workflows, retention, and model/rubric changes.
2. Add authentication, least-privilege authorization, restrictive CORS, rate
   limiting, and secure operational logging before network exposure.
3. Replace in-memory batch tracking with durable job storage and worker-based
   execution if asynchronous processing must survive restarts.
4. Expand integration tests to a controlled local Ollama environment and add
   security, fairness, and failure-mode evaluation before handling non-sample
   data.
