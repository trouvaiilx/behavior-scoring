# API Security Audit

Audit date: 2026-07-27

## Scope

Reviewed `app/main.py`, `app/schemas.py`, `app/config.py`, `app/auth.py`,
`app/db.py`, and API tests for these Phase 2 endpoints:

- `POST /api/auth/token`
- `POST /api/candidates/import`

## Auth and Candidate Import Audit

| Control | `POST /api/auth/token` | `POST /api/candidates/import` |
| --- | --- | --- |
| Content type | Requires exactly one `Content-Type: application/json`; missing, duplicate, or unsupported values return `415`. | Requires exactly one `Content-Type: application/json`; missing, duplicate, or unsupported values return `415`. |
| Authorization header | Rejects an `Authorization` header because this is an explicit JSON client-credentials grant. | Requires exactly one `Authorization: Bearer <token>` header. Missing, malformed, expired, revoked, and unknown tokens return the same `401` detail with `WWW-Authenticate: Bearer`. |
| Credentials and tokens | Compares configured client credentials with constant-time comparison, generates opaque high-entropy tokens, persists only keyed SHA-256 token digests, and returns `Cache-Control: no-store`. | Authorizes only active tokens with the `candidates:import` scope; a valid token with another scope returns `403`. |
| Body size | `MAX_AUTH_REQUEST_BYTES` defaults to 4 KiB. An ASGI middleware enforces both declared and streamed byte counts before JSON parsing. | `MAX_IMPORT_REQUEST_BYTES` defaults to 6 MiB. The same middleware enforces streamed byte counts even if `Content-Length` is absent or inaccurate. |
| Input validation | Strict request schema rejects unknown fields. Validation failures intentionally use the generic `401` credential response. | Strict import and profile schemas reject unknown fields; profiles are limited to `MAX_IMPORT_PROFILES` (20 by default) and preserve existing field-length constraints. Validation details omit supplied candidate text. |
| Persistence | Expiry, scope, client ID, timestamps, and nullable revocation state are stored in SQLite. | A complete validated batch is inserted in one SQLite transaction. The endpoint returns `201 Created` with only count and generated candidate IDs. |

### Residual Security Considerations

- `AUTH_CLIENT_SECRET` has no default. The token and import endpoints return
  `503` until a high-entropy local secret is configured in `.env` or the
  environment.
- Only the import route is protected. Existing score, export, review, delete,
  and webhook routes remain unauthenticated and must not be exposed publicly.
- SQLite stores imported candidate text locally in plaintext, consistent with
  the prototype's existing score storage. Protect the local filesystem and bind
  the server to loopback unless a fuller security model is implemented.
- Tokens expire but there is no operator-facing revocation endpoint yet.

## Webhook Registration Audit

### `POST /api/webhooks`

| Control | Finding | Resolution |
| --- | --- | --- |
| HTTP status | The route declares `status_code=201`. | Verified by an API test that a valid registration returns `201 Created`. |
| URL scheme and host | The original validator limited schemes to `http` and `https`, but accepted any non-empty `netloc`, including a missing hostname or embedded credentials. | The schema now requires an HTTP(S) scheme, valid hostname and port, and rejects embedded user credentials. |
| Input shape | The request allowed unknown properties and had no per-event string bound. | Unknown properties are rejected; subscriptions remain limited to 20 events and each event is limited to 100 characters. |
| Registration cap | Registrations were unbounded. | Added configurable `MAX_WEBHOOK_REGISTRATIONS` (default: 100). The route serializes its count-and-insert check within one application process and returns `409 Conflict` when full. |
| Rate limiting | No temporal rate limiter exists. | Not implemented in-process because this unauthenticated prototype has no stable client identity and process-local limits would not protect multi-worker deployments. Enforce a client-aware distributed rate limit at the reverse proxy or API gateway before exposing the endpoint externally. |

### Residual Security Considerations

- URL validation confirms syntax and protocol only. If a future dispatcher sends requests to registered URLs, it must resolve and block loopback, link-local, private, and other restricted network addresses to prevent server-side request forgery (SSRF), including DNS rebinding defenses.
- The registration cap is process-local. A multi-process deployment requires a database-enforced or shared-store limit for a global guarantee.
- This route has no authentication. Any deployment beyond the local prototype must require authorization before allowing webhook registration.

## Verification

- Unit/API tests cover content-type and authorization rejection, generic
  credential failures, token issue/cache headers, expiry and scope rejection,
  body limits, profile/batch validation redaction, and successful imports.
- Playwright tests cover the token-to-import flow against a live Uvicorn server
  with an isolated SQLite database.
