"""
Bulk-runs every profile in sample_data/sample_profiles.json through the
running backend (POST /api/score or POST /api/scores/batch) and prints a summary table.

Usage (with the backend already running via `uvicorn app.main:app --reload`):
    python sample_data/run_samples.py
    python sample_data/run_samples.py --batch

Requires the `requests` package: pip install requests
"""

import argparse
import json
from pathlib import Path
import sys
import time

try:
    import requests
except ImportError:
    print("This script needs the 'requests' package. Install it with:")
    print("    pip install requests")
    sys.exit(1)

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
SAMPLES_PATH = Path(__file__).parent / "sample_profiles.json"


def run_sequential(base_url: str, profiles: list[dict]):
    score_url = f"{base_url.rstrip('/')}/api/score"
    print(f"Running {len(profiles)} sample profiles sequentially through {score_url}\n")
    print(f"{'Label':<40} {'Job Role':<24} {'Composite':>9}  {'Red Flag':<8}  Note")
    print("-" * 96)

    for profile in profiles:
        label = profile.get("candidate_label", "unknown")
        role = profile.get("job_role", "") or "(none)"

        try:
            resp = requests.post(score_url, json=profile, timeout=180)
        except requests.exceptions.ConnectionError:
            print(
                f"{label:<40} {role[:23]:<24} Could not connect. Is the backend running?"
            )
            continue

        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except (json.JSONDecodeError, ValueError):
                detail = resp.text
            print(f"{label:<40} {role[:23]:<24} ERROR: {detail[:40]}")
            continue

        result = resp.json()
        note = (
            "excluded attrs noticed"
            if result.get("excluded_attributes_detected")
            else ""
        )
        composite = result.get("composite_score", 0.0)
        red_flag_status = result.get("red_flag", {}).get("status", "unknown")

        print(
            f"{label:<40} "
            f"{role[:23]:<24} "
            f"{composite:>9.1f} "
            f"{red_flag_status:<8}  {note}"
        )


def run_batch(base_url: str, profiles: list[dict]):
    batch_url = f"{base_url.rstrip('/')}/api/scores/batch"
    print(
        f"Submitting {len(profiles)} sample profiles as a batch job to {batch_url}..."
    )

    try:
        resp = requests.post(batch_url, json={"profiles": profiles}, timeout=30)
    except requests.exceptions.ConnectionError:
        print("Could not connect to backend. Is uvicorn running?")
        return

    if resp.status_code != 200:
        print(f"Batch submission failed ({resp.status_code}): {resp.text}")
        return

    data = resp.json()
    batch_id = data["batch_id"]
    print(f"Batch job created with ID: {batch_id}. Polling progress...")

    poll_url = f"{base_url.rstrip('/')}/api/scores/batch/{batch_id}"
    while True:
        r = requests.get(poll_url, timeout=10)
        if r.status_code != 200:
            print(f"Error polling batch job status: {r.text}")
            break
        job = r.json()
        status = job["status"]
        completed = job["completed_items"]
        total = job["total_items"]
        print(f"Progress: {completed}/{total} completed (status: {status})")

        if status in ("completed", "failed"):
            print("\nBatch execution finished!")
            print(f"{'Label':<40} {'Status':<10} {'Composite':>9}  {'Red Flag':<8}")
            print("-" * 75)
            for res in job.get("results", []):
                lbl = res["candidate_label"]
                st = res["status"]
                sr = res.get("score_result")
                comp_str = f"{sr['composite_score']:>9.1f}" if sr else "     N/A"
                rf_str = (
                    sr["red_flag"]["status"] if sr else (res.get("error") or "err")[:8]
                )
                print(f"{lbl:<40} {st:<10} {comp_str}  {rf_str}")
            break
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(
        description="Run sample candidate profiles through the Behavior Scoring API."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help="Base URL of the backend API (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Submit as a background batch job via POST /api/scores/batch",
    )
    args = parser.parse_args()

    if not SAMPLES_PATH.exists():
        print(f"Error: Sample data file not found at {SAMPLES_PATH}")
        sys.exit(1)

    profiles = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))

    if args.batch:
        run_batch(args.url, profiles)
    else:
        run_sequential(args.url, profiles)

    print("\nDone. Full detail (including rationale) is visible in the web UI's")
    print("'Past Runs' table, or via GET /api/scores/{id}.")


if __name__ == "__main__":
    main()
