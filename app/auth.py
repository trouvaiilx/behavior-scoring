"""Small local client-credentials helpers for the protected import API."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from app import config

IMPORT_SCOPE = "candidates:import"


def auth_is_configured() -> bool:
    return bool(config.AUTH_CLIENT_ID and config.AUTH_CLIENT_SECRET)


def client_credentials_are_valid(client_id: str, client_secret: str) -> bool:
    client_id_valid = hmac.compare_digest(client_id, config.AUTH_CLIENT_ID)
    client_secret_valid = hmac.compare_digest(client_secret, config.AUTH_CLIENT_SECRET)
    return client_id_valid & client_secret_valid


def issue_access_token() -> tuple[str, str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=config.AUTH_TOKEN_TTL_SECONDS)
    return token, token_digest(token), expires_at


def token_digest(token: str) -> str:
    return hmac.new(
        config.AUTH_CLIENT_SECRET.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def token_is_active(token_record: dict) -> bool:
    if token_record.get("revoked_at"):
        return False

    try:
        expires_at = datetime.fromisoformat(token_record["expires_at"])
    except (KeyError, TypeError, ValueError):
        return False

    if expires_at.tzinfo is None:
        return False
    return expires_at > datetime.now(timezone.utc)
