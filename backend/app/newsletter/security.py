"""Purpose-bound newsletter tokens. No fallback signing secret."""
import hashlib
import hmac
import os
import re
import secrets
import time
from uuid import UUID


def signing_key() -> bytes:
    value = os.getenv("NEWSLETTER_TOKEN_SECRET", "")
    if len(value) < 32:
        raise ValueError("Newsletter signing configuration is unavailable")
    return value.encode()


def nonce() -> str:
    return secrets.token_urlsafe(32)


def sign(kind: str, subject: str, *, lifetime: int, now: int | None = None) -> str:
    payload = f"{kind}.{subject}.{(int(time.time()) if now is None else now) + lifetime}"
    signature = hmac.new(signing_key(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify(token: str, kind: str, *, now: int | None = None) -> str:
    try:
        purpose, subject, expires, signature = token.split(".")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", subject) or purpose != kind:
            raise ValueError
        expected = hmac.new(signing_key(), f"{purpose}.{subject}.{expires}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature) or int(expires) <= (int(time.time()) if now is None else now):
            raise ValueError
        return subject
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid or expired newsletter token") from None


def demo_session(profile_id) -> str | None:
    """Only call after checking is_demo in PostgreSQL; missing config never breaks login."""
    try:
        return sign("demo", UUID(str(profile_id)).hex, lifetime=8 * 3600)
    except ValueError:
        return None


def unsubscribe_token(value: str) -> str:
    return sign("unsubscribe", value, lifetime=90 * 86400)
