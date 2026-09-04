from __future__ import annotations

import time

from backend.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    new_reset_token,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", h) is True
    assert verify_password("wrong-password", h) is False


def test_password_hash_is_salted_differently_each_time():
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    assert verify_password("same-password", h1)
    assert verify_password("same-password", h2)


def test_verify_password_rejects_malformed_hash():
    assert verify_password("anything", "not-a-real-hash") is False


def test_access_token_roundtrip():
    token = create_access_token(subject="user-123", role="admin")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"


def test_access_token_rejects_tampering():
    token = create_access_token(subject="user-123", role="investigator")
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    assert decode_access_token(tampered) is None


def test_access_token_expiry_is_enforced():
    token = create_access_token(subject="user-123", role="investigator", expires_minutes=0)
    time.sleep(1.1)
    assert decode_access_token(token) is None


def test_reset_tokens_are_unique():
    assert new_reset_token() != new_reset_token()
