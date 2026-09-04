"""Password hashing (stdlib PBKDF2-HMAC, no extra native dependency) and JWT
access tokens (PyJWT, HS256).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

_PBKDF2_ITERATIONS = 260_000
_ALGORITHM = "HS256"

# Insecure but functional default so the app runs out of the box; ALWAYS
# override with a real secret (env var) before any non-local deployment.
_DEFAULT_SECRET = "oiltrace-dev-secret-change-me-before-any-real-deployment"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


def _secret_key() -> str:
    return os.environ.get("OILTRACE_JWT_SECRET", _DEFAULT_SECRET)


def hash_password(password: str) -> str:
    """Returns ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations_s, salt_hex, hash_hex = stored_hash.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_s))
    return hmac.compare_digest(digest, expected)


def create_access_token(*, subject: str, role: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, _secret_key(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    try:
        return jwt.decode(token, _secret_key(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None


def new_reset_token() -> str:
    return secrets.token_urlsafe(32)
