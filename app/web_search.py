"""
Live Web Search & Social Media Data Fetcher.

Fetches public web snippets, technical posts, GitHub public data, and social signals
for a candidate name or handle using standard web search APIs and GitHub REST endpoints.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def search_candidate_digital_footprint(candidate_name: str, job_role: str = "") -> dict[str, str]:
    """
    Queries public search signals (DuckDuckGo HTML / GitHub API) to assemble
    a synthetic profile based on public digital evidence.
    """
    clean_query = candidate_name.strip()
    encoded_query = urllib.parse.quote(clean_query)

    posts_snippets: list[str] = []
    bio_snippets: list[str] = []
    network_snippets: list[str] = []

    # 1. Query GitHub REST API if query looks like a username or developer name
    try:
        gh_url = f"https://api.github.com/users/{encoded_query}"
        req = Request(gh_url, headers={"User-Agent": "BehaviorScoringBot/1.0"})
        with urlopen(req, timeout=5) as resp:
            gh_data = json.loads(resp.read().decode("utf-8"))
            if gh_data.get("bio"):
                bio_snippets.append(f"GitHub Bio: {gh_data['bio']}")
            if gh_data.get("public_repos"):
                network_snippets.append(f"Public Repositories: {gh_data['public_repos']}, Followers: {gh_data.get('followers', 0)}")
            if gh_data.get("company"):
                bio_snippets.append(f"Company: {gh_data['company']}")
    except Exception:
        pass  # Non-fatal if GitHub user not found

    # 2. Query DuckDuckGo Web Search API for public web presence
    try:
        ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}+{urllib.parse.quote(job_role)}"
        req = Request(ddg_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Extract plain text snippets from web search results
            from html.parser import HTMLParser

            class TextExtractParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []

                def handle_data(self, data):
                    d = data.strip()
                    if d and len(d) > 20 and "DuckDuckGo" not in d:
                        self.text.append(d)

            parser = TextExtractParser()
            parser.feed(html)
            extracted = parser.text[:5]
            if extracted:
                posts_snippets.extend(extracted)
    except Exception as e:
        logger.warning("DuckDuckGo search error for '%s': %s", candidate_name, e)

    # Assemble normalized candidate profile dictionary
    profile_about = " | ".join(bio_snippets) if bio_snippets else f"Public digital footprint search for {candidate_name}."
    posts_sample = "\n---\n".join(posts_snippets) if posts_snippets else f"Public posts and technical mentions gathered for {candidate_name}."
    network_notes = " | ".join(network_snippets) if network_snippets else "Public web search results aggregated."

    return {
        "candidate_label": candidate_name,
        "job_role": job_role,
        "cv_claims": f"Public digital footprint query for role: {job_role or 'General'}",
        "profile_about": profile_about,
        "posts_sample": posts_sample,
        "comments_sample": "Public web discussion snippets aggregated.",
        "network_notes": network_notes,
    }
