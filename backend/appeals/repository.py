"""Persistence for appeals and their append-only review history."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, MetaData, String, Table, Text, create_engine, insert, select, update
from sqlalchemy.engine import Engine

_DEFAULT_URL = "sqlite:///" + os.path.abspath("oceanguard_appeals.sqlite")
_metadata = MetaData()

appeals = Table(
    "appeals",
    _metadata,
    Column("id", String(36), primary_key=True),
    Column("event_id", String(16), nullable=False, index=True),
    Column("subject", String(32), nullable=False),
    Column("mmsi", String(16)),
    Column("contact_name", String(200), nullable=False),
    Column("contact_email", String(255), nullable=False),
    Column("statement", Text, nullable=False),
    Column("status", String(16), nullable=False, default="open"),
    Column("submitted_at", String(32), nullable=False),
)

appeal_history = Table(
    "appeal_history",
    _metadata,
    Column("id", String(36), primary_key=True),
    Column("appeal_id", String(36), nullable=False, index=True),
    Column("status", String(16), nullable=False),
    Column("notes", Text),
    Column("reviewer_display_name", String(120)),
    Column("timestamp", String(32), nullable=False),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AppealsRepository:
    def __init__(self, url: Optional[str] = None, *, engine: Optional[Engine] = None) -> None:
        self.engine = engine or create_engine(url or os.environ.get("OCEANGUARD_APPEALS_DB_URL") or _DEFAULT_URL, future=True)
        _metadata.create_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()

    def submit(self, *, event_id: str, subject: str, mmsi: Optional[str], contact_name: str, contact_email: str, statement: str) -> str:
        appeal_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            conn.execute(insert(appeals), {
                "id": appeal_id, "event_id": event_id, "subject": subject, "mmsi": mmsi,
                "contact_name": contact_name, "contact_email": contact_email, "statement": statement,
                "status": "open", "submitted_at": _now_iso(),
            })
            conn.execute(insert(appeal_history), {
                "id": str(uuid.uuid4()), "appeal_id": appeal_id, "status": "open",
                "notes": "Appeal submitted.", "reviewer_display_name": None, "timestamp": _now_iso(),
            })
        return appeal_id

    def get(self, appeal_id: str) -> Optional[dict]:
        with self.engine.connect() as conn:
            row = conn.execute(select(appeals).where(appeals.c.id == appeal_id)).mappings().first()
            if row is None:
                return None
            hist = conn.execute(
                select(appeal_history).where(appeal_history.c.appeal_id == appeal_id).order_by(appeal_history.c.timestamp)
            ).mappings().all()
        return {**dict(row), "history": [dict(h) for h in hist]}

    def list(self, *, event_id: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
        query = select(appeals).order_by(appeals.c.submitted_at.desc())
        if event_id:
            query = query.where(appeals.c.event_id == event_id)
        if status:
            query = query.where(appeals.c.status == status)
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
            out = []
            for row in rows:
                hist = conn.execute(
                    select(appeal_history).where(appeal_history.c.appeal_id == row["id"]).order_by(appeal_history.c.timestamp)
                ).mappings().all()
                out.append({**dict(row), "history": [dict(h) for h in hist]})
        return out

    def review(self, appeal_id: str, *, status: str, notes: Optional[str], reviewer_display_name: str) -> Optional[dict]:
        with self.engine.begin() as conn:
            existing = conn.execute(select(appeals.c.id).where(appeals.c.id == appeal_id)).first()
            if existing is None:
                return None
            conn.execute(update(appeals).where(appeals.c.id == appeal_id).values(status=status))
            conn.execute(insert(appeal_history), {
                "id": str(uuid.uuid4()), "appeal_id": appeal_id, "status": status,
                "notes": notes, "reviewer_display_name": reviewer_display_name, "timestamp": _now_iso(),
            })
        return self.get(appeal_id)


_default_repo: Optional[AppealsRepository] = None


def get_appeals_repository() -> AppealsRepository:
    global _default_repo
    if _default_repo is None:
        _default_repo = AppealsRepository()
    return _default_repo
