"""
Automated Pipeline: Connects Playwright profile data -> Candidate Import -> Ollama Scoring.

Usage:
    python scripts/scrape_and_score.py path/to/scraped_profiles.json
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_API = "http://127.0.0.1:8000"


def main():
    parser = argparse.ArgumentParser(description="Automated Scrape -> Import -> Score Pipeline")
    parser.add_argument("input", type=Path, help="Path to scraped profiles JSON")
    parser.add_argument("--api-url", default=DEFAULT_API, help="Backend API URL")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: File {args.input} does not exist.", file=sys.stderr)
        return 1

    print(f"1. Reading scraped profiles from: {args.input}")
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error reading JSON: {e}", file=sys.stderr)
        return 1

    # Extract profiles list
    profiles = data.get("profiles", data) if isinstance(data, dict) else data
    if not isinstance(profiles, list):
        profiles = [profiles]

    print(f"2. Importing {len(profiles)} candidate profiles into backend API...")
    import_url = f"{args.api_url.rstrip('/')}/api/candidates/import"
    req_data = json.dumps({"profiles": profiles}).encode("utf-8")
    req = Request(import_url, data=req_data, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with urlopen(req) as resp:
            import_res = json.loads(resp.read().decode("utf-8"))
            print(f"   -> Import Success: {import_res.get('imported_count')} candidates saved to DB.")
    except Exception as e:
        print(f"   -> Import Error: {e}", file=sys.stderr)
        return 1

    print("3. Pipeline complete! You can view the imported candidates on the dashboard at http://127.0.0.1:8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
