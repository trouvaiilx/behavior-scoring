"""
Bulk-runs every profile in sample_data/sample_profiles.json through the
running backend (POST /api/score) and prints a summary table.

Usage (with the backend already running via `uvicorn app.main:app --reload`):
    python sample_data/run_samples.py

Requires the `requests` package: pip install requests
"""
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("This script needs the 'requests' package. Install it with:")
    print("    pip install requests")
    sys.exit(1)

API_URL = "http://127.0.0.1:8000/api/score"
SAMPLES_PATH = Path(__file__).parent / "sample_profiles.json"


def main():
    profiles = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))

    print(f"Running {len(profiles)} sample profiles through {API_URL}\n")
    print(f"{'Label':<32} {'Composite':>9}  {'Red Flag':<8}  Note")
    print("-" * 80)

    for profile in profiles:
        try:
            resp = requests.post(API_URL, json=profile, timeout=180)
        except requests.exceptions.ConnectionError:
            print(f"{profile['candidate_label']:<32} Could not connect. Is the backend running?")
            continue

        if resp.status_code != 200:
            detail = resp.json().get("detail", resp.text)
            print(f"{profile['candidate_label']:<32} ERROR: {detail[:60]}")
            continue

        result = resp.json()
        note = "excluded attrs noticed" if result["excluded_attributes_detected"] else ""
        print(
            f"{result['candidate_label']:<32} "
            f"{result['composite_score']:>9} "
            f"{result['red_flag']['status']:<8}  {note}"
        )

    print("\nDone. Full detail (including rationale) is visible in the web UI's")
    print("'Past Runs' table, or via GET /api/scores/{id}.")


if __name__ == "__main__":
    main()
