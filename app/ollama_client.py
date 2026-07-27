"""
Minimal client for the local Ollama API.

Ollama must be installed and running locally (default: http://localhost:11434)
with the model set in OLLAMA_MODEL already pulled, e.g.:

    ollama pull llama3.1
    ollama serve   (usually starts automatically after install)

Docs: https://github.com/ollama/ollama/blob/main/docs/api.md
"""
import json
import httpx

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT


class OllamaError(Exception):
    pass


async def check_connection() -> dict:
    """Ping Ollama and report whether it's reachable and whether the
    configured model is available locally."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            model_found = any(
                OLLAMA_MODEL == m or m.startswith(OLLAMA_MODEL + ":") for m in models
            )
            return {
                "reachable": True,
                "configured_model": OLLAMA_MODEL,
                "model_available_locally": model_found,
                "installed_models": models,
            }
    except Exception as e:  # noqa: BLE001 - surfaced to the health endpoint
        return {
            "reachable": False,
            "configured_model": OLLAMA_MODEL,
            "error": str(e),
        }


async def generate_json(system_prompt: str, user_prompt: str) -> str:
    """
    Calls Ollama's /api/chat endpoint asking for a JSON-formatted response.
    Returns the raw text content from the model (expected to be JSON).
    Raises OllamaError on connection/HTTP failures.
    """
    if OLLAMA_MODEL == "REPLACE_WITH_YOUR_MODEL":
        raise OllamaError(
            "OLLAMA_MODEL is still the placeholder value. Set it in your .env "
            "file (copy .env.example to .env) to a model you have pulled, "
            "e.g. OLLAMA_MODEL=llama3.1"
        )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.2},
    }

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError as e:
        raise OllamaError(
            f"Could not connect to Ollama at {OLLAMA_BASE_URL}. "
            f"Is Ollama installed and running? (ollama serve)"
        ) from e
    except httpx.HTTPStatusError as e:
        raise OllamaError(
            f"Ollama returned an error: {e.response.status_code} {e.response.text}"
        ) from e

    content = data.get("message", {}).get("content")
    if not content:
        raise OllamaError(f"Unexpected Ollama response shape: {json.dumps(data)[:500]}")
    return content
