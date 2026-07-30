import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import APIRequestContext, sync_playwright

from app import db, main
from app.rubric import DIMENSIONS
from app.schemas import DimensionScore, RedFlagResult, ScoreResult


def _unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def api_base_url(tmp_path, monkeypatch) -> Iterator[str]:
    """Run the FastAPI app against an isolated database for one API test."""
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "scores.db")

    async def fake_check_connection() -> dict:
        return {
            "reachable": True,
            "configured_model": "test-model",
            "model_available_locally": True,
            "installed_models": ["test-model"],
        }

    async def fake_score_candidate(profile) -> ScoreResult:
        return ScoreResult(
            candidate_label=profile.candidate_label,
            job_role=profile.job_role,
            rubric_version="test-rubric",
            rubric_hash="test-rubric-hash",
            model_used="test-model",
            overall_summary="Deterministic score generated for API testing.",
            dimension_scores=[
                DimensionScore(
                    key=dimension["key"],
                    label=dimension["label"],
                    score=80.0,
                    rationale="Deterministic test rationale.",
                )
                for dimension in DIMENSIONS
            ],
            composite_score=80.0,
            red_flag=RedFlagResult(status="pass", rationale="No test red flags."),
            raw_model_output="{}",
        )

    monkeypatch.setattr(main.ollama_client, "check_connection", fake_check_connection)
    monkeypatch.setattr(main, "score_candidate", fake_score_candidate)

    port = _unused_local_port()
    server = uvicorn.Server(
        uvicorn.Config(
            main.app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        deadline = time.monotonic() + 5
        while not server.started:
            if not thread.is_alive():
                raise RuntimeError("FastAPI test server stopped before becoming ready.")
            if time.monotonic() >= deadline:
                raise RuntimeError("FastAPI test server did not become ready within five seconds.")
            time.sleep(0.01)

        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("FastAPI test server did not stop cleanly.")


@pytest.fixture
def api_request(api_base_url: str) -> Iterator[APIRequestContext]:
    """Provide a Playwright API request context scoped to a single test."""
    with sync_playwright() as playwright:
        request_context = playwright.request.new_context(base_url=api_base_url)
        try:
            yield request_context
        finally:
            request_context.dispose()
