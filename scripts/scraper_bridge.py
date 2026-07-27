#!/usr/bin/env python3
"""Normalize Playwright scraper JSON and submit it to candidate import.

The bridge targets the implemented candidate-import contract:
{"profiles": [CandidateProfileInput, ...]}. It does not scrape data itself
and must only be used with sample, synthetic, or explicitly consented data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_BATCH_SIZE = 100

FIELD_ALIASES = {
    "candidate_label": (
        "candidate_label",
        "label",
        "name",
        "full_name",
        "username",
        "handle",
    ),
    "job_role": ("job_role", "role", "headline", "title"),
    "cv_claims": ("cv_claims", "experience", "experience_summary", "skills"),
    "profile_about": ("profile_about", "about", "bio", "summary"),
    "posts_sample": ("posts_sample", "posts", "articles"),
    "comments_sample": ("comments_sample", "comments", "interactions"),
    "network_notes": ("network_notes", "network", "connections", "endorsements"),
}


class BridgeError(Exception):
    """Raised for malformed scraper output or failed import requests."""


def _as_text(value: Any) -> str:
    """Convert values commonly emitted by a scraper into request text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(part for item in value if (part := _as_text(item)))
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _first_available(record: Mapping[str, Any], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        value = _as_text(record.get(alias))
        if value:
            return value
    return ""


def _normalize_candidate(record: Any, position: int) -> dict[str, str]:
    if not isinstance(record, Mapping):
        raise BridgeError(f"Candidate {position} must be a JSON object.")

    candidate = {
        field: _first_available(record, aliases)
        for field, aliases in FIELD_ALIASES.items()
    }
    if not candidate["candidate_label"]:
        aliases = ", ".join(FIELD_ALIASES["candidate_label"])
        raise BridgeError(
            f"Candidate {position} needs a non-blank candidate_label or one of: {aliases}."
        )
    return candidate


def _extract_records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, Mapping):
        raise BridgeError("Scraper JSON must be an array or an object.")

    for key in ("candidates", "profiles"):
        if key in payload:
            records = payload[key]
            if not isinstance(records, list):
                raise BridgeError(f"Scraper JSON field '{key}' must be an array.")
            return records
    return [payload]


def _batches(records: list[dict[str, str]], size: int) -> Iterable[list[dict[str, str]]]:
    for start in range(0, len(records), size):
        yield records[start:start + size]


def _import_url(api_base_url: str) -> str:
    parsed = urlparse(api_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise BridgeError("--api-base-url must be an absolute HTTP(S) URL.")
    return f"{api_base_url.rstrip('/')}/api/candidates/import"


def _decode_response(body: bytes) -> Any:
    text = body.decode("utf-8", errors="replace")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _post_import(endpoint: str, profiles: list[dict[str, str]], timeout: float) -> tuple[int, Any]:
    body = json.dumps({"profiles": profiles}, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    request = Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, _decode_response(response.read())
    except HTTPError as error:
        detail = _decode_response(error.read())
        raise BridgeError(f"Import request failed with HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise BridgeError(f"Could not reach candidate-import API: {error.reason}") from error


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize Playwright scraper JSON and post it to /api/candidates/import."
    )
    parser.add_argument("input", type=Path, help="Path to scraper JSON output.")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL),
        help="API base URL (default: API_BASE_URL or http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Profiles per import request; must be 1-100 (default: 100).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print import payloads without making HTTP requests.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not 1 <= args.batch_size <= DEFAULT_BATCH_SIZE:
        print("error: --batch-size must be between 1 and 100.", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("error: --timeout must be greater than zero.", file=sys.stderr)
        return 2

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        records = _extract_records(payload)
        if not records:
            raise BridgeError("Scraper JSON does not contain any candidates.")
        profiles = [_normalize_candidate(record, index) for index, record in enumerate(records, start=1)]
        endpoint = _import_url(args.api_base_url)

        results = []
        for index, batch in enumerate(_batches(profiles, args.batch_size), start=1):
            if args.dry_run:
                results.append({"batch": index, "request": {"profiles": batch}})
                continue

            status, response = _post_import(endpoint, batch, args.timeout)
            results.append({"batch": index, "status": status, "response": response})
    except (BridgeError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "endpoint": endpoint,
                "submitted_profiles": len(profiles),
                "dry_run": args.dry_run,
                "batches": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
