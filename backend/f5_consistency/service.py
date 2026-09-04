"""F5 orchestration: join the four upstream products for one event, compute
residuals per relationship type, classify, persist, and return
``EvidenceRelation`` rows.

Runs standalone against ``/shared/mocks/load_mock.py`` for any upstream feature
that is not yet live (integration rule 6).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from shared.ids import evidence_id
from shared.mocks import load_mock_rows as _default_load_mock

from . import residuals as _res
from ._geo import parse_iso
from .config import EvidenceThresholds, default_thresholds
from .engine import evaluate
from .models import EvidenceRelation, EvidenceRelationRecord, RelationKind

logger = logging.getLogger("oiltrace.f5")

Loader = Callable[[str, Optional[str]], dict[str, Any]]


@dataclass
class EvaluationResult:
    event_id: str
    records: list[EvidenceRelationRecord] = field(default_factory=list)
    skipped_reason: Optional[str] = None

    @property
    def relations(self) -> list[EvidenceRelation]:
        return [r.to_relation() for r in self.records]

    @property
    def summary(self) -> dict[str, int]:
        out = {"SUPPORTS": 0, "CONTRADICTS": 0, "UNKNOWN": 0, "total": len(self.records)}
        for r in self.records:
            out[r.relation] += 1
        return out


# --------------------------------------------------------------------------- helpers
def _rows(loader: Loader, feature: str, event_id: str) -> list[dict[str, Any]]:
    payload = loader(feature, event_id)
    return list(payload.get("rows", []))


def _observed_states(f2_rows: Iterable[dict]) -> list[dict]:
    observed = [r for r in f2_rows if str(r.get("state_type", "")).upper() == "OBSERVED"]
    observed.sort(key=lambda r: parse_iso(r["timestamp"]) if r.get("timestamp") else 0)
    return observed


def _best_hypothesis(f3_rows: list[dict]) -> Optional[dict]:
    if not f3_rows:
        return None
    pooled = [r for r in f3_rows if r.get("ensemble_id") in (-1, "-1")]
    if pooled:
        return pooled[0]
    with_prob = [r for r in f3_rows if isinstance(r.get("source_probability"), (int, float))]
    if with_prob:
        return max(with_prob, key=lambda r: r["source_probability"])
    deterministic = [r for r in f3_rows if r.get("is_deterministic")]
    return deterministic[0] if deterministic else f3_rows[0]


def _mean_sensor_confidence(observed: list[dict]) -> float:
    vals = [
        float(r["f1_confidence"])
        for r in observed
        if isinstance(r.get("f1_confidence"), (int, float)) and r["f1_confidence"] > 0
    ]
    return sum(vals) / len(vals) if vals else 0.5


def _scene_for_state(f1_rows: list[dict], state: dict) -> dict:
    sid = state.get("scene_id")
    for row in f1_rows:
        if row.get("scene_id") == sid:
            return row
    for row in f1_rows:
        if row.get("f1_detected") or row.get("oil_present"):
            return row
    return f1_rows[0] if f1_rows else {}


# --------------------------------------------------------------------------- core
def evaluate_event(
    event_id: str,
    *,
    loader: Loader = _default_load_mock,
    thresholds: Optional[EvidenceThresholds] = None,
    persist: bool = False,
    repo: Any = None,
) -> EvaluationResult:
    thr = thresholds or default_thresholds()
    result = EvaluationResult(event_id=event_id)

    f1_rows = _rows(loader, "f1", event_id)
    f2_rows = _rows(loader, "f2", event_id)
    f3_rows = _rows(loader, "f3", event_id)
    f4_rows = _rows(loader, "f4", event_id)

    observed = _observed_states(f2_rows)
    best_hyp = _best_hypothesis(f3_rows)

    if len(observed) < 2 or best_hyp is None:
        result.skipped_reason = (
            f"need >=2 OBSERVED F2 states and an F3 hypothesis; "
            f"got {len(observed)} OBSERVED state(s), "
            f"hypothesis={'present' if best_hyp else 'missing'}"
        )
        logger.info("F5 %s: %s", event_id, result.skipped_reason)
        if persist:
            _get_repo(repo).replace_event(event_id, [])
        return result

    s0, s1 = observed[0], observed[1]
    hyp_id = str(best_hyp.get("source_hypothesis_id") or f"{event_id}-HBEST")
    sensor_conf = _mean_sensor_confidence(observed)
    obs_count = len(observed)
    seq = _SeqGen(event_id)

    # ---- F1_DETECTION <-> F2_STATE ------------------------------------------------
    scene = _scene_for_state(f1_rows, s0)
    rs = _res.f1_detection_vs_f2_state(scene, s0, thr)
    relation, reason = evaluate(rs, thr)
    if relation != "CONTRADICTS" and sensor_conf < thr.min_sensor_confidence:
        relation, reason = "UNKNOWN", "low sensor confidence on the seed detection"
    result.records.append(
        EvidenceRelationRecord(
            evidence_id=seq.next(),
            event_id=event_id,
            kind=RelationKind.F1_DETECTION__F2_STATE,
            source_a_id=str(scene.get("scene_id") or s0.get("observation_id")),
            source_a_type="F1_DETECTION",
            source_b_id=str(s0.get("observation_id")),
            source_b_type="F2_STATE",
            spatial_residual_km=rs.constrained.get("spatial_residual_km"),
            temporal_residual_h=rs.constrained.get("temporal_residual_h"),
            relation=relation,
            reason=reason,
            provenance=[f"F1:{scene.get('scene_id')}", f"F2:{s0.get('observation_id')}"],
            timestamp_a=scene.get("acquisition_timestamp"),
            timestamp_b=s0.get("timestamp"),
            sensor_confidence=round(sensor_conf, 4),
            observation_count=obs_count,
        )
    )

    # ---- F2_DRIFT <-> F3_FORCING ------------------------------------------------
    rs = _res.f2_drift_vs_f3_forcing(s0, s1, best_hyp, thr)
    relation, reason = evaluate(rs, thr)
    result.records.append(
        EvidenceRelationRecord(
            evidence_id=seq.next(),
            event_id=event_id,
            kind=RelationKind.F2_DRIFT__F3_FORCING,
            source_a_id=str(s1.get("observation_id")),
            source_a_type="F2_DRIFT",
            source_b_id=hyp_id,
            source_b_type="F3_FORCING",
            spatial_residual_km=rs.constrained.get("spatial_residual_km"),
            temporal_residual_h=0.0,
            drift_residual_km=rs.context.get("drift_residual_km"),
            relation=relation,
            reason=reason,
            provenance=[
                f"F2:{s0.get('observation_id')},{s1.get('observation_id')}",
                f"F3:{hyp_id}",
            ],
            timestamp_a=s0.get("timestamp"),
            timestamp_b=s1.get("timestamp"),
            sensor_confidence=round(sensor_conf, 4),
            observation_count=obs_count,
        )
    )

    # ---- F3_SOURCE_HYPOTHESIS <-> F4_VESSEL_TRACK ------------------------------
    support_gap = thr.bound("support", "ais_gap_ratio")
    for track in f4_rows:
        rs = _res.f3_hypothesis_vs_f4_track(best_hyp, track, thr)
        relation, reason = evaluate(rs, thr)

        gap_ratio = rs.context.get("ais_gap_ratio")
        dark_gap = bool(track.get("dark_gap_over_source"))
        if (
            relation == "SUPPORTS"
            and thr.f3f4_high_gap_downgrade
            and gap_ratio is not None
            and gap_ratio > support_gap
            and not dark_gap
        ):
            relation = "UNKNOWN"
            reason = (
                f"support residuals but AIS gap ratio {gap_ratio:.2f} "
                f"exceeds support bound {support_gap:g}"
            )

        temporal_display = rs.constrained.get("temporal_residual_h")
        if temporal_display is None:
            temporal_display = rs.context.get("_temporal_display_h", 0.0)

        result.records.append(
            EvidenceRelationRecord(
                evidence_id=seq.next(),
                event_id=event_id,
                kind=RelationKind.F3_SOURCE_HYPOTHESIS__F4_VESSEL_TRACK,
                source_a_id=hyp_id,
                source_a_type="F3_SOURCE_HYPOTHESIS",
                source_b_id=str(track.get("track_id") or track.get("mmsi")),
                source_b_type="F4_VESSEL_TRACK",
                spatial_residual_km=rs.constrained.get("spatial_residual_km"),
                temporal_residual_h=temporal_display,
                drift_residual_km=rs.context.get("drift_residual_km"),
                ais_gap_ratio=gap_ratio,
                relation=relation,
                reason=reason,
                provenance=[f"F3:{hyp_id}", f"F4:{track.get('track_id')}"],
                timestamp_a=best_hyp.get("origin_time_mid"),
                timestamp_b=track.get("closest_approach_timestamp"),
                sensor_confidence=round(sensor_conf, 4),
                observation_count=obs_count,
            )
        )

    if persist:
        _get_repo(repo).replace_event(event_id, result.records)

    return result


def evaluate_consistency(
    event_id: str,
    *,
    loader: Loader = _default_load_mock,
    thresholds: Optional[EvidenceThresholds] = None,
    persist: bool = False,
    repo: Any = None,
) -> list[EvidenceRelation]:
    """Public entry point — returns the frozen ``EvidenceRelation`` contract rows."""
    return evaluate_event(
        event_id, loader=loader, thresholds=thresholds, persist=persist, repo=repo
    ).relations


class _SeqGen:
    def __init__(self, event_id: str) -> None:
        self._event_id = event_id
        self._n = 0

    def next(self) -> str:
        eid = evidence_id(self._event_id, self._n)
        self._n += 1
        return eid


def _get_repo(repo: Any) -> Any:
    if repo is not None:
        return repo
    from .repository import EvidenceRepository

    return EvidenceRepository()
