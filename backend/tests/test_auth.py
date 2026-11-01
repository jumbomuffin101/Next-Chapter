"""Offline tests for the stub admin token (no database)."""
import time

import pytest
from fastapi import HTTPException

from app.auth.router import make_admin_token, require_admin, verify_admin_token


def test_fresh_token_verifies():
    assert verify_admin_token(make_admin_token())


def test_expired_token_is_rejected():
    token = make_admin_token(now=time.time() - 9 * 3600)  # issued 9h ago, ttl is 8h
    assert not verify_admin_token(token)


def test_tampered_or_garbage_tokens_are_rejected():
    import base64
    role, expires, signature = base64.urlsafe_b64decode(make_admin_token()).decode().split(".")
    forged = base64.urlsafe_b64encode(f"{role}.{int(expires) + 10**6}.{signature}".encode()).decode()
    assert not verify_admin_token(forged)
    assert not verify_admin_token("not-a-token")
    assert not verify_admin_token("")


@pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer nope", "Basic abc", "abc"])
def test_require_admin_rejects_bad_headers(header):
    with pytest.raises(HTTPException) as err:
        require_admin(header)
    assert err.value.status_code == 401


def test_require_admin_accepts_a_valid_bearer_token():
    assert require_admin(f"Bearer {make_admin_token()}") is None
