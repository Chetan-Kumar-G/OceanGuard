"""Persistence for users and password-reset tokens.

Default store is a local SQLite file (no Postgres required for the demo).
Point ``OILTRACE_AUTH_DB_URL`` at a shared database for a real deployment.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    create_engine,
    select,
    update,
)
from sqlalchemy.engine import Engine

_DEFAULT_URL = "sqlite:///" + os.path.abspath("oiltrace_auth.sqlite")
_RESET_TOKEN_TTL_MINUTES = 30

_metadata = MetaData()

users = Table(
    "users",
    _metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(255), unique=True, nullable=False),
    Column("password_hash", String(200), nullable=False),
    Column("display_name", String(120), nullable=False),
    Column("role", String(20), nullable=False, default="investigator"),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("created_at", String(32), nullable=False),
)

password_reset_tokens = Table(
    "password_reset_tokens",
    _metadata,
    Column("token", String(64), primary_key=True),
    Column("user_id", String(36), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("used", Boolean, nullable=False, default=False),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class UserRecord:
    __slots__ = ("id", "email", "password_hash", "display_name", "role", "is_active", "created_at")

    def __init__(self, id, email, password_hash, display_name, role, is_active, created_at):  # noqa: A002
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.display_name = display_name
        self.role = role
        self.is_active = is_active
        self.created_at = created_at


class AuthRepository:
    def __init__(self, url: Optional[str] = None, *, engine: Optional[Engine] = None) -> None:
        self.engine = engine or create_engine(url or os.environ.get("OILTRACE_AUTH_DB_URL") or _DEFAULT_URL, future=True)
        _metadata.create_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()

    # ------------------------------------------------------------- users
    def user_count(self) -> int:
        with self.engine.connect() as conn:
            return len(conn.execute(select(users.c.id)).fetchall())

    def create_user(self, *, email: str, password_hash: str, display_name: str, role: str) -> UserRecord:
        row = dict(
            id=str(uuid.uuid4()),
            email=email.lower(),
            password_hash=password_hash,
            display_name=display_name,
            role=role,
            is_active=True,
            created_at=_now_iso(),
        )
        with self.engine.begin() as conn:
            conn.execute(users.insert(), row)
        return UserRecord(**row)

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        with self.engine.connect() as conn:
            row = conn.execute(select(users).where(users.c.email == email.lower())).mappings().first()
        return UserRecord(**dict(row)) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[UserRecord]:
        with self.engine.connect() as conn:
            row = conn.execute(select(users).where(users.c.id == user_id)).mappings().first()
        return UserRecord(**dict(row)) if row else None

    def list_users(self) -> list[UserRecord]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(users).order_by(users.c.created_at)).mappings().all()
        return [UserRecord(**dict(r)) for r in rows]

    def set_role(self, user_id: str, role: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(users).where(users.c.id == user_id).values(role=role))

    def set_password(self, user_id: str, password_hash: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(users).where(users.c.id == user_id).values(password_hash=password_hash))

    # ------------------------------------------------------- reset tokens
    def create_reset_token(self, user_id: str, token: str) -> str:
        expires = (datetime.now(timezone.utc) + timedelta(minutes=_RESET_TOKEN_TTL_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.engine.begin() as conn:
            conn.execute(password_reset_tokens.insert(), {"token": token, "user_id": user_id, "expires_at": expires, "used": False})
        return token

    def consume_reset_token(self, token: str) -> Optional[str]:
        """Marks the token used and returns the user_id, or None if invalid/expired/used."""
        with self.engine.begin() as conn:
            row = conn.execute(select(password_reset_tokens).where(password_reset_tokens.c.token == token)).mappings().first()
            if row is None or row["used"]:
                return None
            expires_at = datetime.strptime(row["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return None
            conn.execute(update(password_reset_tokens).where(password_reset_tokens.c.token == token).values(used=True))
            return row["user_id"]


_default_repo: Optional[AuthRepository] = None


def get_auth_repository() -> AuthRepository:
    global _default_repo
    if _default_repo is None:
        _default_repo = AuthRepository()
    return _default_repo
