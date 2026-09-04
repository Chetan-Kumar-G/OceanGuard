"""Schemas for F5 output.

``EvidenceRelation`` is the frozen wire/consumer contract (Prompt "REQUIRED
OUTPUTS — exact schema", Blueprint Part 7 ``EvidenceRelation``): exactly ten
fields, ``extra="forbid"``. F6 and F7 consume this shape.

``EvidenceRelationRecord`` is the persisted row (Blueprint Part 4
``evidence_items`` / ``evidence_relations``): it carries the context residuals
(``drift_residual_km``, ``ais_gap_ratio``) and full provenance, and projects
down to ``EvidenceRelation`` for the API / downstream payload.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Relation = Literal["SUPPORTS", "CONTRADICTS", "UNKNOWN"]

# Exact relationship types to compute (Prompt "DATASET FIELDS TO USE").
SOURCE_A_TYPES = ("F1_DETECTION", "F2_DRIFT", "F3_SOURCE_HYPOTHESIS")
SOURCE_B_TYPES = ("F2_STATE", "F3_FORCING", "F4_VESSEL_TRACK")


class RelationKind(str, Enum):
    F1_DETECTION__F2_STATE = "F1_DETECTION<->F2_STATE"
    F2_DRIFT__F3_FORCING = "F2_DRIFT<->F3_FORCING"
    F3_SOURCE_HYPOTHESIS__F4_VESSEL_TRACK = "F3_SOURCE_HYPOTHESIS<->F4_VESSEL_TRACK"

    @property
    def source_a_type(self) -> str:
        return self.value.split("<->")[0]

    @property
    def source_b_type(self) -> str:
        return self.value.split("<->")[1]


class EvidenceRelation(BaseModel):
    """Frozen consumer contract. Do not add fields here — extras live on the record."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    event_id: str
    source_a_id: str
    source_a_type: str
    source_b_id: str
    source_b_type: str
    spatial_residual_km: float
    temporal_residual_h: float
    relation: Relation
    reason: str


class EvidenceRelationRecord(BaseModel):
    """Persisted row + everything needed for explainability and F6 tallies."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    event_id: str
    kind: RelationKind
    source_a_id: str
    source_a_type: str
    source_b_id: str
    source_b_type: str

    spatial_residual_km: Optional[float] = None
    temporal_residual_h: Optional[float] = None
    drift_residual_km: Optional[float] = None
    ais_gap_ratio: Optional[float] = None

    relation: Relation
    reason: str

    # provenance / context (Blueprint Part 4, DATA_DICTIONARY D5)
    provenance: list[str] = Field(default_factory=list)
    timestamp_a: Optional[str] = None
    timestamp_b: Optional[str] = None
    sensor_confidence: Optional[float] = None
    observation_count: Optional[int] = None
    forcing_quality: str = "reanalysis-nominal"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def to_relation(self) -> EvidenceRelation:
        return EvidenceRelation(
            evidence_id=self.evidence_id,
            event_id=self.event_id,
            source_a_id=self.source_a_id,
            source_a_type=self.source_a_type,
            source_b_id=self.source_b_id,
            source_b_type=self.source_b_type,
            spatial_residual_km=round(float(self.spatial_residual_km or 0.0), 4),
            temporal_residual_h=round(float(self.temporal_residual_h or 0.0), 4),
            relation=self.relation,
            reason=self.reason,
        )
