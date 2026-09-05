"""Persistence for F5 output.

Writes ``evidence_relations`` (one row per compared pair) and ``evidence_items``
(one row per distinct evidence endpoint, for F7's graph). Reads the four
upstream tables only through the mock loader / live services — never here.

Default store is a local SQLite file so ``DB write works`` is demoable without
Postgres/PostGIS (F5 has no geometry columns). Point ``OCEANGUARD_DB_URL`` at the
shared Postgres instance in integration.
"""
from __future__ import annotations

import json
import os
from typing import Iterable, Optional

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    select,
)
from sqlalchemy.engine import Engine

from .models import EvidenceRelation, EvidenceRelationRecord, RelationKind

_DEFAULT_URL = "sqlite:///" + os.path.abspath("oceanguard_f5.sqlite")

_metadata = MetaData()

evidence_relations = Table(
    "evidence_relations",
    _metadata,
    Column("evidence_id", String(64), primary_key=True),
    Column("event_id", String(16), index=True, nullable=False),
    Column("kind", String(64), nullable=False),
    Column("source_a_id", String(96), nullable=False),
    Column("source_a_type", String(32), nullable=False),
    Column("source_b_id", String(96), nullable=False),
    Column("source_b_type", String(32), nullable=False),
    Column("spatial_residual_km", Float),
    Column("temporal_residual_h", Float),
    Column("drift_residual_km", Float),
    Column("ais_gap_ratio", Float),
    Column("relation", String(16), nullable=False),
    Column("reason", Text, nullable=False),
    Column("provenance", Text, nullable=False),
    Column("timestamp_a", String(32)),
    Column("timestamp_b", String(32)),
    Column("sensor_confidence", Float),
    Column("observation_count", Integer),
    Column("forcing_quality", String(32)),
    Column("created_at", String(32)),
)

evidence_items = Table(
    "evidence_items",
    _metadata,
    Column("item_key", String(128), primary_key=True),  # f"{event_id}:{source_id}"
    Column("event_id", String(16), index=True, nullable=False),
    Column("source_id", String(96), nullable=False),
    Column("source_type", String(32), nullable=False),
)


class EvidenceRepository:
    def __init__(self, url: Optional[str] = None, *, engine: Optional[Engine] = None) -> None:
        self.engine = engine or create_engine(
            url or os.environ.get("OCEANGUARD_DB_URL") or _DEFAULT_URL,
            future=True,
        )
        _metadata.create_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()

    # ----------------------------------------------------------------- writes
    def replace_event(self, event_id: str, records: Iterable[EvidenceRelationRecord]) -> int:
        records = list(records)
        with self.engine.begin() as conn:
            conn.execute(delete(evidence_relations).where(evidence_relations.c.event_id == event_id))
            conn.execute(delete(evidence_items).where(evidence_items.c.event_id == event_id))
            if not records:
                return 0
            conn.execute(
                evidence_relations.insert(),
                [self._relation_row(r) for r in records],
            )
            items = {}
            for r in records:
                for sid, stype in ((r.source_a_id, r.source_a_type), (r.source_b_id, r.source_b_type)):
                    items[f"{event_id}:{sid}"] = {
                        "item_key": f"{event_id}:{sid}",
                        "event_id": event_id,
                        "source_id": sid,
                        "source_type": stype,
                    }
            conn.execute(evidence_items.insert(), list(items.values()))
        return len(records)

    # ----------------------------------------------------------------- reads
    def list_relations(self, event_id: str) -> list[EvidenceRelation]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(evidence_relations)
                .where(evidence_relations.c.event_id == event_id)
                .order_by(evidence_relations.c.evidence_id)
            ).mappings().all()
        return [
            EvidenceRelation(
                evidence_id=row["evidence_id"],
                event_id=row["event_id"],
                source_a_id=row["source_a_id"],
                source_a_type=row["source_a_type"],
                source_b_id=row["source_b_id"],
                source_b_type=row["source_b_type"],
                spatial_residual_km=round(float(row["spatial_residual_km"] or 0.0), 4),
                temporal_residual_h=round(float(row["temporal_residual_h"] or 0.0), 4),
                relation=row["relation"],
                reason=row["reason"],
            )
            for row in rows
        ]

    def list_records(self, event_id: str) -> list[EvidenceRelationRecord]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(evidence_relations)
                .where(evidence_relations.c.event_id == event_id)
                .order_by(evidence_relations.c.evidence_id)
            ).mappings().all()
        out = []
        for row in rows:
            out.append(
                EvidenceRelationRecord(
                    evidence_id=row["evidence_id"],
                    event_id=row["event_id"],
                    kind=RelationKind(row["kind"]),
                    source_a_id=row["source_a_id"],
                    source_a_type=row["source_a_type"],
                    source_b_id=row["source_b_id"],
                    source_b_type=row["source_b_type"],
                    spatial_residual_km=row["spatial_residual_km"],
                    temporal_residual_h=row["temporal_residual_h"],
                    drift_residual_km=row["drift_residual_km"],
                    ais_gap_ratio=row["ais_gap_ratio"],
                    relation=row["relation"],
                    reason=row["reason"],
                    provenance=json.loads(row["provenance"]) if row["provenance"] else [],
                    timestamp_a=row["timestamp_a"],
                    timestamp_b=row["timestamp_b"],
                    sensor_confidence=row["sensor_confidence"],
                    observation_count=row["observation_count"],
                    forcing_quality=row["forcing_quality"] or "reanalysis-nominal",
                    created_at=row["created_at"],
                )
            )
        return out

    # ----------------------------------------------------------------- internal
    @staticmethod
    def _relation_row(r: EvidenceRelationRecord) -> dict:
        return {
            "evidence_id": r.evidence_id,
            "event_id": r.event_id,
            "kind": r.kind.value,
            "source_a_id": r.source_a_id,
            "source_a_type": r.source_a_type,
            "source_b_id": r.source_b_id,
            "source_b_type": r.source_b_type,
            "spatial_residual_km": r.spatial_residual_km,
            "temporal_residual_h": r.temporal_residual_h,
            "drift_residual_km": r.drift_residual_km,
            "ais_gap_ratio": r.ais_gap_ratio,
            "relation": r.relation,
            "reason": r.reason,
            "provenance": json.dumps(r.provenance),
            "timestamp_a": r.timestamp_a,
            "timestamp_b": r.timestamp_b,
            "sensor_confidence": r.sensor_confidence,
            "observation_count": r.observation_count,
            "forcing_quality": r.forcing_quality,
            "created_at": r.created_at,
        }
