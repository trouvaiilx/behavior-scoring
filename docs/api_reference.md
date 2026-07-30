# API Reference

## Overview

This reference describes the HTTP API implemented in `app/main.py` for the
Behavior Scoring prototype, version `0.2.0`. It is intended for local R&D use
with synthetic, sample, or explicitly consented text only. It is not a
production hiring-decision API.

Default base URL: `http://127.0.0.1:8000`

The currently mounted routes do not enforce authentication or authorization.
`POST /api/auth/token` issues a development bearer token, but no route yet
validates that token. Requests and JSON responses use `application/json` unless
an endpoint explicitly returns a download.

## Endpoint Index

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Check backend and local Ollama availability. |
| GET | `/api/rubric` | Return the active scoring rubric and exclusions. |
| POST | `/api/score` | Score and persist one candidate profile. |
| POST | `/api/webhooks` | Register an event webhook. |
| POST | `/api/auth/token` | Exchange client credentials for a development bearer token. |
| POST | `/api/candidates/import` | Persist up to 100 imported candidate profiles. |
| GET | `/api/scores` | List persisted score runs with filters and pagination. |
| GET | `/api/scores/analytics` | Return aggregate score and review metrics. |
| GET | `/api/scores/export` | Download filtered score runs as CSV or JSON. |
| GET | `/api/scores/compare` | Compare selected persisted score runs. |
| GET | `/api/scores/{score_id}` | Return one persisted score run. |
| PATCH | `/api/scores/{score_id}/review` | Record a human-review outcome. |
| DELETE | `/api/scores/{score_id}` | Delete one persisted score run. |
| POST | `/api/scores/batch` | Start asynchronous scoring for up to 20 profiles. |
| GET | `/api/scores/batch/{batch_id}` | Poll an in-memory batch job. |

The server also exposes the static test UI at `/` and FastAPI-generated
documentation at `/docs`, `/redoc`, and `/openapi.json`.

## Common Behavior

- A validation failure returns `422 Unprocessable Entity` using FastAPI's
  standard `detail` error array. This applies to malformed JSON, missing
  required fields, invalid path/query types, and declared field constraints.
- Endpoint-specific failures return an object shaped as
  `{ "detail": "message" }`.
- Timestamps use ISO 8601 UTC strings when present.
- Scores are persisted in the local SQLite database configured by
  `DATABASE_PATH` (default: `data/scores.db`).
- `red_flag.status` is one of `pass`, `review`, or `fail`. It is a separate
  screening gate and is not included in the composite-score calculation.
- Human-review statuses are `pending`, `approved`, `rejected`, and
  `overridden`.
- Candidate imports are stored in the separate `candidates` table. Importing a
  profile does not create a score run or queue scoring.

## Shared Schemas

### CandidateProfileInput

Used by `POST /api/score`, `POST /api/scores/batch`, and each `profiles` item
in `POST /api/candidates/import`.

| Field | Type | Required | Constraints and meaning |
| --- | --- | --- | --- |
| `candidate_label` | string | Yes | Trimmed non-blank label; 1-200 characters. Use a non-identifying label such as `sample_001`. |
| `job_role` | string | No | Defaults to `""`; maximum 200 characters. Target role used as scoring context. |
| `cv_claims` | string | No | Defaults to `""`; maximum `MAX_FIELD_CHARS` characters (8,000 by default). Resume/CV claims used for consistency checks. |
| `profile_about` | string | No | Defaults to `""`; maximum `MAX_FIELD_CHARS` characters. Public bio/about text. |
| `posts_sample` | string | No | Defaults to `""`; maximum `MAX_FIELD_CHARS` characters. Plain-text sample of posts or articles. |
| `comments_sample` | string | No | Defaults to `""`; maximum `MAX_FIELD_CHARS` characters. Plain-text sample of comments or interactions. |
| `network_notes` | string | No | Defaults to `""`; maximum `MAX_FIELD_CHARS` characters. Notes about endorsements or professional connections. |

`MAX_FIELD_CHARS` can be overridden with an environment variable. Text fields
are trimmed before scoring.

Example:

```json
{
  "candidate_label": "sample_001",
  "job_role": "Backend Engineer",
  "cv_claims": "Software Engineer, 2022-2024. Python and SQL.",
  "profile_about": "Backend engineer interested in distributed systems.",
  "posts_sample": "Wrote about database indexing strategies.",
  "comments_sample": "Helpful technical comments on engineering posts.",
  "network_notes": "Several relevant endorsements."
}
```

### WebhookRegisterRequest and WebhookResponse

Used by `POST /api/webhooks`.

| Request field | Type | Required | Constraints and meaning |
| --- | --- | --- | --- |
| `url` | string | Yes | Trimmed HTTP or HTTPS URL with a host; 1-2,048 characters. |
| `events` | string array | No | Defaults to `[]`; maximum 20 items. Values are trimmed and cannot be blank. |

`WebhookResponse` returns the persisted `id` (integer), `url` (string),
`events` (string array), and `created_at` (ISO 8601 UTC string).

### TokenRequest and TokenResponse

Used by `POST /api/auth/token`.

| Request field | Type | Required | Constraints and behavior |
| --- | --- | --- | --- |
| `client_id` | string | Yes | Required identifier; 1-200 characters. The current prototype validates its presence and length but does not look it up. |
| `client_secret` | string | Yes | Required shared secret; 1-512 characters. It must match the configured `API_SECRET_KEY`. |

`TokenResponse` contains `access_token` (string) and `token_type` (always
`"bearer"`). The current prototype returns the configured shared secret itself
as `access_token`; it does not issue unique tokens, expiry times, or refresh
tokens. Treat this endpoint as local development-only functionality and do not
log either credential or token.

### CandidateImportRequest and CandidateImportResponse

Used by `POST /api/candidates/import`. The bridge posts its normalized scraper
output in the `profiles` field.

| Request field | Type | Required | Constraints and behavior |
| --- | --- | --- | --- |
| `profiles` | array of `CandidateProfileInput` | Conditionally | Provide a non-empty list of up to 100 profiles. Each item follows `CandidateProfileInput` validation. Do not supply this field with `json_file`. |
| `json_file` | string | Conditionally | Provide JSON text containing either a non-empty profile array or `{ "profiles": [...] }`. Maximum length is `MAX_FIELD_CHARS * 100` (800,000 by default). Do not supply this field with `profiles`. |

`CandidateImportResponse` contains `imported_count` (integer), `candidate_ids`
(integer array), and `status` (always `"success"`). IDs identify records in the
local `candidates` table, not score-run IDs.

### ScoreResult

Returned by successful scoring, score detail, review update, comparison, and
completed batch items.

| Field | Type | Description |
| --- | --- | --- |
| `id` | integer or null | SQLite score-run identifier. It is populated after persistence. |
| `candidate_label` | string | Label supplied in the request. |
| `job_role` | string | Target role context; empty when not supplied. |
| `rubric_version` | string | Human-managed rubric version used for the run. |
| `rubric_hash` | string | Twelve-character fingerprint of rubric content at scoring time. |
| `model_used` | string | Configured Ollama model name. |
| `overall_summary` | string | Model-generated plain-language profile summary. |
| `dimension_scores` | array of `DimensionScore` | One result for each active rubric dimension. |
| `composite_score` | number | Weighted 0-100 score, rounded to one decimal. |
| `red_flag` | `RedFlagResult` | Separate pass/review/fail screening result. |
| `human_review` | `HumanReviewInfo` | Human-review state; initially `pending`. |
| `excluded_attributes_detected` | string array | Protected attributes detected but explicitly excluded from scoring. |
| `raw_model_output` | string | Unprocessed JSON text returned by the local model. |
| `created_at` | string or null | UTC persistence timestamp. |

`DimensionScore` contains `key` (string), `label` (string), `score` (number),
and `rationale` (string). `RedFlagResult` contains `status` and `rationale`.
`HumanReviewInfo` contains `status`, `notes`, and `reviewed_at` (an ISO 8601
string or `null`).

Example abbreviated response:

```json
{
  "id": 42,
  "candidate_label": "sample_001",
  "job_role": "Backend Engineer",
  "rubric_version": "0.2.0",
  "rubric_hash": "abc123def456",
  "model_used": "llama3.1",
  "overall_summary": "Consistent technical profile with clear communication.",
  "dimension_scores": [
    {
      "key": "professional_consistency",
      "label": "Professional Consistency",
      "score": 82.0,
      "rationale": "Claims align with supplied profile text."
    }
  ],
  "composite_score": 80.5,
  "red_flag": { "status": "pass", "rationale": "No concerns found." },
  "human_review": { "status": "pending", "notes": "", "reviewed_at": null },
  "excluded_attributes_detected": [],
  "raw_model_output": "{...}",
  "created_at": "2026-07-27T12:34:56.789012+00:00"
}
```

## Endpoints

### `GET /api/health`

Reports application health and whether Ollama is reachable. The endpoint
returns `200 OK` even when Ollama is unavailable; inspect `ollama.reachable`.

Parameters: none.

Success response (`200 OK`):

```json
{
  "backend": "ok",
  "ollama": {
    "reachable": true,
    "configured_model": "llama3.1",
    "model_available_locally": true,
    "installed_models": ["llama3.1:latest"]
  }
}
```

When the Ollama check fails, `ollama` instead contains `reachable: false`,
`configured_model`, and an `error` string.

### `GET /api/rubric`

Returns the rubric currently used by scoring. It lets clients display the
dimensions, weights, exclusion policy, and version that govern new runs.

Parameters: none.

Success response (`200 OK`):

| Field | Type | Description |
| --- | --- | --- |
| `dimensions` | array | Objects with `key`, `label`, `weight`, and `description`. Current weights are 0.33, 0.27, 0.27, and 0.13. |
| `red_flag_note` | string | Explains that red-flag screening is a separate escalation gate. |
| `excluded_attributes` | string array | Attributes that must not influence scores. |
| `rubric_version` | string | Current configured version, `0.2.0`. |
| `rubric_hash` | string | Current twelve-character rubric-content fingerprint. |

### `POST /api/score`

Scores one profile through the configured local Ollama model and persists the
result in SQLite.

Request body: a [`CandidateProfileInput`](#candidateprofileinput) object.

Success response (`200 OK`): a persisted
[`ScoreResult`](#scoreresult), including `id` and `created_at`.

Error responses:

| Status | When returned |
| --- | --- |
| `422` | The input body does not satisfy `CandidateProfileInput`. |
| `502` | The scoring pipeline cannot call or parse the configured Ollama model. The response `detail` contains the scoring error. |

### `POST /api/webhooks`

Registers a webhook destination and the event names it is interested in. The
route persists the registration locally; event delivery is not implemented by
the current prototype.

Request body: a
[`WebhookRegisterRequest`](#webhookregisterrequest-and-webhookresponse)
object.

Example:

```json
{
  "url": "https://example.test/hooks/behavior-score",
  "events": ["score.completed", "score.review_required"]
}
```

Success response (`201 Created`):

```json
{
  "id": 7,
  "url": "https://example.test/hooks/behavior-score",
  "events": ["score.completed", "score.review_required"],
  "created_at": "2026-07-27T12:34:56.789012+00:00"
}
```

Error response: `422 Unprocessable Entity` when `url` is blank, is not an
HTTP(S) URL with a host, `events` has more than 20 values, or an event value is
blank.

### `POST /api/auth/token`

Exchanges client credentials for a development bearer token. The server
compares `client_secret` with `API_SECRET_KEY` using a constant-time comparison.
The required `client_id` is currently not used for identity lookup.

Request body: an
[`TokenRequest`](#tokenrequest-and-tokenresponse) object.

Example:

```json
{
  "client_id": "local-scraper-bridge",
  "client_secret": "configured-api-secret"
}
```

Success response (`200 OK`): an
[`TokenResponse`](#tokenrequest-and-tokenresponse) object.

Error responses:

| Status | When returned |
| --- | --- |
| `401` | `client_secret` does not match the configured shared secret. The response includes `WWW-Authenticate: Bearer`. |
| `422` | The body is malformed, a credential is missing, or `client_id`/`client_secret` violates its length constraint. |

The returned token is not currently required by any route, has no expiry, and
is not an authentication boundary. Do not expose this prototype endpoint
beyond a trusted local development environment.

### `POST /api/candidates/import`

Persists normalized profiles from an approved scraper bridge into the local
`candidates` table. It does not score the profiles or create a batch job.
Submit only sample, synthetic, or explicitly consented data with a valid legal
basis; this route must not be used to ingest scraped candidate data
indiscriminately.

Request body: a [`CandidateImportRequest`](#candidateimportrequest) object.

Example:

```json
{
  "profiles": [
    {
      "candidate_label": "consented_sample_001",
      "job_role": "Backend Engineer",
      "cv_claims": "Software Engineer, 2022-2024. Python and SQL.",
      "profile_about": "Backend engineer interested in distributed systems.",
      "posts_sample": "Wrote about database indexing strategies.",
      "comments_sample": "Helpful technical comments on engineering posts.",
      "network_notes": "Several relevant endorsements."
    }
  ]
}
```

Success response (`200 OK`):

```json
{
  "imported_count": 1,
  "candidate_ids": [17],
  "status": "success"
}
```

`candidate_ids` contains the newly persisted local candidate-record IDs. They
cannot be passed to score-detail or batch-status routes, and no scoring is
started by this endpoint.

The same import can be submitted from JSON-file contents:

```json
{
  "json_file": "{\"profiles\":[{\"candidate_label\":\"consented_sample_001\"}]}"
}
```

Error responses:

| Status | When returned |
| --- | --- |
| `422` | Neither or both import sources are provided, the supplied list is empty or has more than 100 entries, an individual profile fails `CandidateProfileInput` validation, or `json_file` is invalid or exceeds its size limit. |

`scripts/scraper_bridge.py` accepts a JSON array, a single candidate object,
or an envelope using `candidates` or `profiles`. It normalizes common scraper
field names into the `profiles` request contract and submits no more than 100
profiles per import request.

### `GET /api/scores`

Lists persisted score runs. Filters are combined with logical AND. The
`search` filter matches `candidate_label`, `job_role`, and `overall_summary`.

| Query parameter | Type | Default | Constraints and behavior |
| --- | --- | --- | --- |
| `limit` | integer | `50` | Minimum 1; maximum 200. |
| `offset` | integer | `0` | Minimum 0. |
| `search` | string | null | Case handling is delegated to SQLite `LIKE`; surrounding whitespace is ignored. |
| `red_flag_status` | string | null | Stored red-flag status to match, normally `pass`, `review`, or `fail`. |
| `human_review_status` | string | null | Stored review status to match: `pending`, `approved`, `rejected`, or `overridden`. |
| `min_score` | number | null | Inclusive minimum composite score; 0-100. |
| `max_score` | number | null | Inclusive maximum composite score; 0-100. |
| `has_excluded_attributes` | boolean | null | `true` returns runs with detected excluded attributes; `false` returns runs without any. |
| `sort_by` | string | `id` | One of `id`, `composite_score`, `created_at`, or `candidate_label`. |
| `sort_order` | string | `desc` | `asc` or `desc`. |

Success response (`200 OK`):

```json
{
  "results": ["ScoreResult objects"],
  "total": 42,
  "limit": 50,
  "offset": 0,
  "filters": {
    "search": null,
    "red_flag_status": null,
    "human_review_status": null,
    "min_score": null,
    "max_score": null,
    "has_excluded_attributes": null,
    "sort_by": "id",
    "sort_order": "desc"
  }
}
```

`total` is the count before pagination but after all filters. The `results`
items use the same shape as [`ScoreResult`](#scoreresult).

### `GET /api/scores/analytics`

Returns aggregate metrics for every persisted score run. It accepts no query
parameters.

Success response (`200 OK`):

| Field | Type | Description |
| --- | --- | --- |
| `total_candidates` | integer | Total number of persisted runs. |
| `composite_score_stats` | object | `avg`, `median`, `min`, and `max` numeric composite scores. All are `0.0` when no runs exist. |
| `red_flag_breakdown` | object | Counts keyed by `pass`, `review`, and `fail`. |
| `human_review_breakdown` | object | Counts keyed by review status. |
| `excluded_attributes_counts` | object | Count of each detected excluded-attribute label. |
| `score_buckets` | object | Counts in `0_to_20`, `21_to_40`, `41_to_60`, `61_to_80`, and `81_to_100`. |

### `GET /api/scores/export`

Downloads up to 10,000 filtered score runs. Export results are always ordered
by score ID descending. The `has_excluded_attributes` list filter is not
available on this route.

| Query parameter | Type | Default | Constraints and behavior |
| --- | --- | --- | --- |
| `format` | string | `csv` | `csv` or `json`. |
| `search` | string | null | Same matching behavior as `GET /api/scores`. |
| `red_flag_status` | string | null | Same filtering behavior as `GET /api/scores`. |
| `human_review_status` | string | null | Same filtering behavior as `GET /api/scores`. |
| `min_score` | number | null | Inclusive composite-score lower bound. |
| `max_score` | number | null | Inclusive composite-score upper bound. |

Success responses (`200 OK`):

| `format` | Content type | Download name | Body |
| --- | --- | --- | --- |
| `csv` | `text/csv` | `candidate_scores_export.csv` | Header row followed by one row per score. Includes review fields and flattened red-flag data. |
| `json` | `application/json` | `candidate_scores_export.json` | JSON array of [`ScoreResult`](#scoreresult)-shaped score runs. |

The download filename is supplied through the `Content-Disposition` response
header.

### `GET /api/scores/compare`

Compares the selected persisted score runs. Candidate results follow the order
of the requested IDs when those IDs exist.

| Query parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `ids` | string | Yes | Comma-separated integer score IDs, for example `1,2,5`. |

Success response (`200 OK`):

| Field | Type | Description |
| --- | --- | --- |
| `candidates` | array of `ScoreResult` | Score runs found for the supplied IDs. |
| `dimension_averages` | object | Average score by dimension key, rounded to one decimal. |
| `highest_scoring_candidate` | string or null | Candidate label with the highest composite score. |
| `lowest_scoring_candidate` | string or null | Candidate label with the lowest composite score. |
| `red_flags_summary` | object | Counts keyed by `pass`, `review`, and `fail`. |

Error responses:

| Status | When returned |
| --- | --- |
| `400` | `ids` is not a comma-separated integer list or contains no IDs. |
| `404` | None of the requested IDs exist. |

### `GET /api/scores/{score_id}`

Returns one persisted scoring run in full detail.

| Path parameter | Type | Description |
| --- | --- | --- |
| `score_id` | integer | SQLite score-run ID. |

Success response (`200 OK`): a [`ScoreResult`](#scoreresult) object.

Error response: `404 Not Found` with `{ "detail": "Score not found" }` when
the ID is absent.

### `PATCH /api/scores/{score_id}/review`

Records a human-review outcome and notes for an existing score run. The server
sets `human_review.reviewed_at` to the update time.

| Path parameter | Type | Description |
| --- | --- | --- |
| `score_id` | integer | SQLite score-run ID. |

Request body:

| Field | Type | Required | Constraints |
| --- | --- | --- | --- |
| `status` | string | Yes | One of `pending`, `approved`, `rejected`, or `overridden`. |
| `notes` | string | No | Defaults to `""`; maximum 1,000 characters. |

Example:

```json
{
  "status": "approved",
  "notes": "Reviewer confirmed the evidence is appropriate for this prototype run."
}
```

Success response (`200 OK`): the updated [`ScoreResult`](#scoreresult).

Error responses:

| Status | When returned |
| --- | --- |
| `404` | The score-run ID does not exist. |
| `422` | The body has an invalid review status or notes exceed 1,000 characters. |

### `DELETE /api/scores/{score_id}`

Deletes one persisted score run permanently.

| Path parameter | Type | Description |
| --- | --- | --- |
| `score_id` | integer | SQLite score-run ID. |

Success response (`200 OK`):

```json
{
  "message": "Score run deleted",
  "id": 42
}
```

Error response: `404 Not Found` with
`{ "detail": "Score run not found" }` when the ID is absent.

### `POST /api/scores/batch`

Creates an in-memory batch job and queues profile scoring as a FastAPI
background task. Each successful item is persisted as an individual score run.

Request body:

| Field | Type | Required | Constraints |
| --- | --- | --- | --- |
| `profiles` | array of `CandidateProfileInput` | Yes | At least 1 and at most 20 profile objects. |

Example:

```json
{
  "profiles": [
    { "candidate_label": "sample_001", "cv_claims": "Developer" },
    { "candidate_label": "sample_002", "cv_claims": "Analyst" }
  ]
}
```

Success response (`200 OK`): a [`BatchJobStatus`](#batchjobstatus) object. A
new response starts with `status: "processing"` and empty `results`; poll the
batch-status endpoint for completion.

Errors: `422 Unprocessable Entity` when `profiles` is outside the allowed size
or an item does not satisfy `CandidateProfileInput`.

### `GET /api/scores/batch/{batch_id}`

Returns the latest state of an in-memory batch job.

| Path parameter | Type | Description |
| --- | --- | --- |
| `batch_id` | string | Eight-character ID returned when the batch was created. |

#### BatchJobStatus

| Field | Type | Description |
| --- | --- | --- |
| `batch_id` | string | Batch identifier. |
| `status` | string | `processing`, `completed`, or `failed`. |
| `total_items` | integer | Number of profiles accepted in the request. |
| `completed_items` | integer | Number of successfully scored profiles. |
| `failed_items` | integer | Number of profiles that failed scoring. |
| `results` | array | Completed/failed item records accumulated as processing proceeds. |

Each item record has `candidate_label`, `status` (`completed` or `failed`),
`score_result` (a `ScoreResult` or `null`), and `error` (a string or `null`).
A batch is marked `completed` if at least one item succeeds; it is marked
`failed` only when every item fails.

Success response (`200 OK`): a [`BatchJobStatus`](#batchjobstatus) object.

Error response: `404 Not Found` with
`{ "detail": "Batch job not found" }` when the ID is unknown. Batch state is
not durable and is lost when the application process restarts.

## Non-API Routes

| Path | Response | Purpose |
| --- | --- | --- |
| `/` | Static HTML application | Minimal browser test interface served from `static/`. |
| `/docs` | Swagger UI | Interactive FastAPI documentation. |
| `/redoc` | ReDoc | Alternative generated documentation interface. |
| `/openapi.json` | OpenAPI JSON | Machine-readable API schema. |

## Operational Notes

- Configure the local model with `OLLAMA_MODEL`; the placeholder value
  `REPLACE_WITH_YOUR_MODEL` intentionally prevents scoring.
- `GET /api/health` is the recommended readiness check before calling score
  endpoints.
- The API is configured for local prototype use. It does not implement
  authentication, rate limiting, durable background-job storage, or
  production-grade error handling.
