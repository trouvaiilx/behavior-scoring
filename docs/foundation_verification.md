# Foundation API Verification

## Status

The twelve Foundation API operations are covered by the automated suite. The
route contract test verifies their `/api/` prefix, path names, HTTP methods,
and request schema references; API tests exercise their observable behavior
against an isolated SQLite database and mocked Ollama client.

Run the verification suite with:

```powershell
pip install -r requirements-dev.txt
pytest
```

## Endpoint Coverage

| Operation | Coverage |
| --- | --- |
| `GET /api/health` | `tests/e2e/test_api_playwright.py::test_get_health_reports_backend_and_ollama_status` |
| `GET /api/rubric` | `tests/e2e/test_api_playwright.py::test_get_rubric_returns_active_rubric` |
| `POST /api/score` | `tests/e2e/test_api_playwright.py::test_post_score_returns_and_persists_score` |
| `GET /api/scores` | `tests/e2e/test_api_playwright.py::test_get_scores_returns_previously_created_score` |
| `GET /api/scores/analytics` | `tests/integration/test_backend_features.py::test_analytics_summary_api` |
| `GET /api/scores/export` | `tests/integration/test_backend_features.py::test_export_scores_api` |
| `GET /api/scores/compare` | `tests/integration/test_backend_features.py::test_candidate_comparison_api` |
| `GET /api/scores/{score_id}` | `tests/integration/test_backend_features.py::test_human_review_workflow_api` |
| `PATCH /api/scores/{score_id}/review` | `tests/integration/test_backend_features.py::test_human_review_workflow_api` |
| `DELETE /api/scores/{score_id}` | `tests/integration/test_backend_features.py::test_delete_score_api` |
| `POST /api/scores/batch` | `tests/e2e/test_api_playwright.py::test_post_scores_batch_creates_a_pollable_job` |
| `GET /api/scores/batch/{batch_id}` | `tests/e2e/test_api_playwright.py::test_post_scores_batch_creates_a_pollable_job` |

## Router And Schema Review

- All Foundation operations are mounted beneath the `/api/` prefix without
  trailing-slash variants.
- Static score subresources (`analytics`, `export`, `compare`) are declared
  before `/api/scores/{score_id}`, preventing those names from being treated as
  score IDs.
- Score creation, batch scoring, and human review use their declared Pydantic
  schemas: `CandidateProfileInput`, `BatchScoreRequest`, and
  `HumanReviewUpdate`.
- The OpenAPI contract is checked by
  `tests/integration/test_route_contracts.py` so route or schema drift fails
  automated verification.
