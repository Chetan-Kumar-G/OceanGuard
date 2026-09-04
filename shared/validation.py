"""Lightweight, dependency-free field validators shared across features.

Deliberately does NOT use pydantic's ``EmailStr`` — it (via ``email-validator``)
performs a live DNS MX-record lookup by default, which is wrong for a backend:
it breaks offline/CI test runs and needlessly makes registration/appeal
submission depend on network reachability of the *sender's* domain.
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_plausible_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value.strip()))


def validate_email_format(value: str) -> str:
    """Pydantic ``field_validator`` body: syntax-only check, no network calls."""
    v = value.strip()
    if not is_plausible_email(v):
        raise ValueError(f"{value!r} is not a plausible email address")
    return v
