"""
backend/f6_ranking/service.py
F6 — Evidence Fusion & Dynamic Hypothesis Ranking

Core scoring logic:
    final_score = clip(raw_score * data_quality_weight, 0, 1)
    raw_score   = sum(w_k * component_k) - penalty * contradiction_count
    data_quality_weight = 0.5 + 0.5 * sensor_confidence

Weights and thresholds are loaded from shared/config/ranking_weights.yaml.
Never hardcoded here.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from backend.f6_ranking.models import ConfidenceBand, HypothesisScore, RankingResult
from shared.mocks.load_mock import load_mock_df as load_mock

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_WEIGHTS_PATH = _HERE.parent.parent / "shared" / "config" / "ranking_weights.yaml"


def _load_cfg() -> dict:
    with open(_WEIGHTS_PATH, "r") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Component helpers
# ---------------------------------------------------------------------------

def _spatial_compat(distance_km: float, uncertainty_km: float, scale_km: float) -> float:
    """exp(-max(0, d_eff - uncertainty) / scale_km), clipped to [0,1]."""
    excess = max(0.0, distance_km - uncertainty_km)
    return math.exp(-excess / scale_km)


def _drift_compat(speed_compat: float, course_compat: float) -> float:
    """0.5 * speed_compatibility + 0.5 * course_compatibility."""
    return 0.5 * float(speed_compat) + 0.5 * float(course_compat)


def _behavioural_score(dark_gap_over_source: bool, ais_gap_ratio_origin_window: float) -> float:
    """
    Combines dark-gap-over-source flag with the AIS gap ratio.
    When a vessel went dark while passing the source, score is elevated.
    Formula: dark_gap_over_source * (0.5 + 0.5 * ais_gap_ratio)
    This matches the reference D6 output closely.
    """
    if not dark_gap_over_source:
        return 0.0
    return 0.5 + 0.5 * float(ais_gap_ratio_origin_window)


def _confidence_band(score: float, cfg: dict) -> ConfidenceBand:
    bands = cfg["confidence_bands"]
    if score >= bands["high"]:
        return "high"
    if score >= bands["medium"]:
        return "medium"
    return "low"


def _build_explanation(
    src_prob: float,
    spatial: float,
    temporal: float,
    drift: float,
    behaviour: float,
    contradiction_count: int,
    final_score: float,
    rank: int,
    n_candidates: int,
) -> str:
    return (
        f"src_prob={src_prob:.2f}, spatial={spatial:.2f}, temporal={temporal:.2f}, "
        f"drift={drift:.2f}, behaviour={behaviour:.2f}, "
        f"contradictions={contradiction_count}; "
        f"final={final_score:.2f} (rank {rank}/{n_candidates})"
    )


# ---------------------------------------------------------------------------
# Evidence aggregation from D5
# ---------------------------------------------------------------------------

def _aggregate_evidence(
    d5: pd.DataFrame,
    mmsi: str,
    event_id: str,
) -> tuple[int, int, int, int, float]:
    """
    Return (support_count, contradiction_count, unknown_count, n_evidence_items, sensor_confidence)
    for a specific candidate (mmsi) within an event.

    D5 structure:
    - Rows with source_b_type = F3_SOURCE_HYPOTHESIS <-> F4_VESSEL_TRACK are per-candidate.
      The source_b_id is like "EVT0002-480469227" (event_id + "-" + mmsi).
    - Rows with source_a_type = F1_DETECTION or F2_DRIFT are event-level (not candidate-specific).

    n_evidence_items counts all rows for the event (event-level count).
    contradiction/support/unknown count per-candidate F3<->F4 rows.
    """
    if d5.empty:
        return 0, 0, 0, 0, 0.5

    n_evidence_items = len(d5)

    # Per-candidate rows: source_b_id ends with the mmsi
    candidate_key = f"{event_id}-{mmsi}"
    cand_rows = d5[d5["source_b_id"] == candidate_key]

    support_count = int((cand_rows["relation"] == "SUPPORTS").sum())
    contradiction_count = int((cand_rows["relation"] == "CONTRADICTS").sum())
    unknown_count = int((cand_rows["relation"] == "UNKNOWN").sum())

    # sensor_confidence is event-level (same for all rows in the event)
    sensor_confidence = float(d5["sensor_confidence"].iloc[0]) if "sensor_confidence" in d5.columns else 0.5

    return support_count, contradiction_count, unknown_count, n_evidence_items, sensor_confidence


# ---------------------------------------------------------------------------
# Main ranking function
# ---------------------------------------------------------------------------

def rank_event(
    event_id: str,
    f3_data: Optional[pd.DataFrame] = None,
    f4_data: Optional[pd.DataFrame] = None,
    f5_data: Optional[pd.DataFrame] = None,
) -> RankingResult:
    """
    Compute ranked hypotheses for a single event.

    Loads F3/F4/F5 from mocks if not provided (for live integration, pass DataFrames).
    Writes result to DB is NOT done in this prototype — handled by router.

    Args:
        event_id:  e.g. "EVT0002"
        f3_data:   D3_source_hypotheses rows (HBEST only). None -> load mock.
        f4_data:   D4_vessel_tracks rows for the event. None -> load mock.
        f5_data:   D5_evidence_consistency rows for the event. None -> load mock.

    Returns:
        RankingResult with ranked HypothesisScore list.
    """
    cfg = _load_cfg()
    w = cfg["weights"]
    penalty = cfg["contradiction_penalty"]
    scale_km = cfg["compat_scale_km"]
    ie_cfg = cfg["insufficient_evidence"]

    # ------------------------------------------------------------------
    # Load upstream data
    # ------------------------------------------------------------------
    if f3_data is None:
        f3_data = load_mock("f3", event_id)   # HBEST row already filtered
    if f4_data is None:
        f4_data = load_mock("f4", event_id)
    if f5_data is None:
        f5_data = load_mock("f5", event_id)

    if f4_data.empty:
        # No candidates -> insufficient evidence immediately
        return RankingResult(
            event_id=event_id,
            candidates=[],
            event_insufficient_evidence=True,
            n_candidates=0,
        )

    # HBEST row from F3
    if f3_data.empty:
        hbest_row = None
    else:
        hbest_row = f3_data.iloc[0]

    uncertainty_km = float(hbest_row["uncertainty_radius_km"]) if hbest_row is not None else 0.0
    source_hypothesis_id = str(hbest_row["source_hypothesis_id"]) if hbest_row is not None else f"{event_id}-HBEST"

    # ------------------------------------------------------------------
    # Score each candidate
    # ------------------------------------------------------------------
    scored: list[dict] = []

    for _, track in f4_data.iterrows():
        mmsi = str(int(track["mmsi"]))

        # --- F3-derived: source_probability
        src_prob_val = hbest_row["source_probability"] if hbest_row is not None else 0.0
        # source_probability in D3 HBEST is 1.0 always (normalised).
        # Per-candidate source_probability comes from matching ensemble source_probability.
        # In the reference dataset, source_probability in D6 matches what D4 provides indirectly:
        # we read it from the F3 hypothesis that was linked to this track.
        # Since D4 references source_hypothesis_id and D3 HBEST has source_probability=1.0,
        # we use the candidate-specific best source_probability from all D3 ensembles.
        # Strategy: the true culprit track will have distance_to_source ~= 0.
        # We load full F3 (all ensembles) and compute overlap weight.
        full_f3 = load_mock("f3", event_id) if f3_data is not None else pd.DataFrame()
        non_hbest = full_f3[full_f3["ensemble_id"] != -1] if not full_f3.empty else pd.DataFrame()

        # The reference D6 source_probability corresponds to the fraction of ensemble members
        # that are close to the vessel's closest approach point. Approximation:
        # Use the HBEST source_probability directly if track is_true_source else 0.
        # But the reference shows non-zero values for some non-source tracks too.
        # Best approach: use distance_to_source_effective_km and uncertainty_radius_km
        # to compute a probability proxy: exp(-d/uncertainty) if d < 2*uncertainty else 0.
        d_eff = float(track.get("distance_to_source_effective_km", 999.0))
        if uncertainty_km > 0:
            src_prob = math.exp(-d_eff / max(uncertainty_km, 1.0))
        else:
            src_prob = 1.0 if d_eff < 5.0 else 0.0
        # Clamp to [0,1]
        src_prob = min(max(src_prob, 0.0), 1.0)

        # --- F4-derived components
        spatial = _spatial_compat(d_eff, uncertainty_km, scale_km)
        temporal = float(track.get("temporal_compatibility", 0.0))
        drift = _drift_compat(
            track.get("speed_compatibility", 0.5),
            track.get("course_compatibility", 0.5),
        )
        ais_completeness = float(track.get("track_completeness", 0.0))
        dark_gap = bool(track.get("dark_gap_over_source", False))
        ais_gap_ratio = float(track.get("ais_gap_ratio_origin_window", 0.0))
        behaviour = _behavioural_score(dark_gap, ais_gap_ratio)

        # --- F5-derived evidence tallies
        support_count, contradiction_count, unknown_count, n_evidence_items, sensor_confidence = (
            _aggregate_evidence(f5_data, mmsi, event_id)
        )

        # --- Scoring formula
        data_quality_weight = 0.5 + 0.5 * sensor_confidence

        raw_score = (
            w["source_probability"] * src_prob
            + w["spatial_compatibility"] * spatial
            + w["temporal_compatibility"] * temporal
            + w["drift_compatibility"] * drift
            + w["ais_completeness"] * ais_completeness
            + w["behavioural_score"] * behaviour
            + w["sensor_confidence"] * sensor_confidence
            - penalty * contradiction_count
        )
        final_score = float(min(max(raw_score * data_quality_weight, 0.0), 1.0))

        scored.append({
            "mmsi": mmsi,
            "final_score": round(final_score, 4),
            "src_prob": round(src_prob, 4),
            "spatial": round(spatial, 4),
            "temporal": round(temporal, 4),
            "drift": round(drift, 4),
            "ais_completeness": round(ais_completeness, 4),
            "behaviour": round(behaviour, 4),
            "sensor_confidence": round(sensor_confidence, 4),
            "data_quality_weight": round(data_quality_weight, 4),
            "support_count": support_count,
            "contradiction_count": contradiction_count,
            "unknown_count": unknown_count,
            "n_evidence_items": n_evidence_items,
            "vessel_type": track.get("vessel_type"),
            "is_true_source": bool(track.get("is_true_source", False)),
            "distance_to_source_km": round(d_eff, 3),
            "dark_gap_over_source": dark_gap,
            "closest_approach_is_interpolated": bool(track.get("closest_approach_is_interpolated", False)),
            "source_hypothesis_id": source_hypothesis_id,
        })

    # Sort descending by final_score; tie-break: lower contradiction_count first,
    # then higher ais_completeness (deterministic)
    scored.sort(
        key=lambda x: (
            -x["final_score"],
            x["contradiction_count"],
            -x["ais_completeness"],
        )
    )

    n_candidates = len(scored)

    # ------------------------------------------------------------------
    # Compute margins and build output models
    # ------------------------------------------------------------------
    results: list[HypothesisScore] = []
    for i, s in enumerate(scored):
        rank = i + 1
        margin = round(s["final_score"] - scored[i + 1]["final_score"], 4) if i + 1 < n_candidates else s["final_score"]

        explanation = _build_explanation(
            s["src_prob"], s["spatial"], s["temporal"],
            s["drift"], s["behaviour"],
            s["contradiction_count"], s["final_score"],
            rank, n_candidates,
        )

        results.append(
            HypothesisScore(
                hypothesis_id=f"HYP_{event_id}_{s['mmsi']}",
                event_id=event_id,
                candidate_mmsi=s["mmsi"],
                rank=rank,
                final_score=s["final_score"],
                confidence_band=_confidence_band(s["final_score"], cfg),
                event_insufficient_evidence=False,   # will be set below
                explanation=explanation,
                source_probability=s["src_prob"],
                spatial_compatibility=s["spatial"],
                temporal_compatibility=s["temporal"],
                drift_compatibility=s["drift"],
                ais_completeness=s["ais_completeness"],
                behavioural_score=s["behaviour"],
                sensor_confidence=s["sensor_confidence"],
                support_count=s["support_count"],
                contradiction_count=s["contradiction_count"],
                unknown_count=s["unknown_count"],
                n_evidence_items=s["n_evidence_items"],
                data_quality_weight=s["data_quality_weight"],
                margin_to_next=margin,
                is_true_source=s["is_true_source"],
                vessel_type=s["vessel_type"],
                distance_to_source_km=s["distance_to_source_km"],
                dark_gap_over_source=s["dark_gap_over_source"],
                closest_approach_is_interpolated=s["closest_approach_is_interpolated"],
                source_hypothesis_id=s["source_hypothesis_id"],
            )
        )

    # ------------------------------------------------------------------
    # Insufficient evidence check (event-level)
    # ------------------------------------------------------------------
    top = results[0] if results else None
    n_ev = results[0].n_evidence_items if results else 0
    top_score = results[0].final_score if results else 0.0
    top_margin = results[0].margin_to_next if results else 0.0

    insufficient = (
        n_candidates == 0
        or top_score < ie_cfg["min_final_score"]
        or n_ev < ie_cfg["min_evidence_items"]
        or top_margin < ie_cfg["min_margin"]
    )

    for h in results:
        h.event_insufficient_evidence = insufficient

    return RankingResult(
        event_id=event_id,
        candidates=results,
        event_insufficient_evidence=insufficient,
        n_candidates=n_candidates,
    )
