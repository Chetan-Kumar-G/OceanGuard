"""
F2 — reconstruct.py

Core reconstruction engine: converts an ordered list of SpillDetectionResult
records (from F1 or the F1 mock) into a list of TemporalSpillState records,
filling gaps with INTERPOLATED states and extrapolating PREDICTED states.

Rules enforced (see Prompt_2_F2_Temporal.md):
- observation_id format: OBS_<event_id>_<3-digit seq>
- INTERPOLATED  → between two OBSERVED states, is_observed=False
- PREDICTED     → extrapolated beyond the last OBSERVED, is_observed=False
- insufficient_temporal_data flag when < 2 OBSERVED states
- Never mislabels INTERPOLATED/PREDICTED as is_observed=True
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.shared.schemas.spill_detection import SpillDetectionResult
from backend.shared.schemas.temporal import TemporalSpillState, TemporalProgressionResult
from backend.f2_temporal.geometry import (
    extract_geometry_features,
    compute_iou,
    interpolate_polygon,
    extrapolate_polygon,
    _haversine_km,
)

logger = logging.getLogger("oiltrace.f2")

# Default gap-fill config (hours)
_INTERP_INTERVAL_H: float = 24.0   # one synthetic state per 24-h gap
_PRED_STEPS: int = 2                # how many predicted steps to append
_PRED_INTERVAL_H: float = 18.0     # interval between predicted states


def _mint_obs_id(event_id: str, seq: int) -> str:
    """OBS_<event_id>_<3-digit seq>"""
    return f"OBS_{event_id}_{seq:03d}"


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _hours_between(earlier: datetime, later: datetime) -> float:
    diff = _to_utc(later) - _to_utc(earlier)
    return diff.total_seconds() / 3600.0


def _build_state(
    *,
    event_id: str,
    seq: int,
    scene_id: str,
    timestamp: datetime,
    sim_hours: float,
    state_type: str,
    polygon_geojson: Dict[str, Any],
    f1_confidence: float,
    data_quality: str,
    is_observed: bool,
    previous_obs_id: str,
    prev_geojson: Optional[Dict[str, Any]],
    prev_centroid: Optional[Tuple[float, float]],
    prev_area_km2: Optional[float],
    prev_timestamp: Optional[datetime],
    persistence: int,
) -> TemporalSpillState:
    """Construct one TemporalSpillState, computing all delta features."""
    geo = extract_geometry_features(polygon_geojson)
    obs_id = _mint_obs_id(event_id, seq)

    # ── temporal delta features ──────────────────────────────────────────────
    polygon_iou: Optional[float] = None
    centroid_displacement_km: Optional[float] = None
    area_change_pct: Optional[float] = None
    observation_gap_hours: Optional[float] = None

    if prev_geojson is not None:
        polygon_iou = compute_iou(prev_geojson, polygon_geojson)
        if prev_centroid is not None:
            centroid_displacement_km = round(
                _haversine_km(
                    prev_centroid[0], prev_centroid[1],
                    geo["centroid_lat"], geo["centroid_lon"],
                ),
                4,
            )
        if prev_area_km2 is not None and prev_area_km2 > 0:
            area_change_pct = round(
                100.0 * (geo["area_km2"] - prev_area_km2) / prev_area_km2, 4
            )
    if prev_timestamp is not None:
        observation_gap_hours = round(_hours_between(prev_timestamp, timestamp), 4)

    return TemporalSpillState(
        event_id=event_id,
        observation_id=obs_id,
        scene_id=scene_id,
        timestamp=_to_utc(timestamp),
        sim_hours=round(sim_hours, 4),
        state_type=state_type,
        polygon_geojson=polygon_geojson,
        polygon_wkt=geo["polygon_wkt"],
        area_km2=geo["area_km2"],
        perimeter_km=geo["perimeter_km"],
        centroid_lat=geo["centroid_lat"],
        centroid_lon=geo["centroid_lon"],
        bbox=geo["bbox"],
        major_axis_km=geo["major_axis_km"],
        minor_axis_km=geo["minor_axis_km"],
        orientation_deg=geo["orientation_deg"],
        solidity=geo["solidity"],
        eccentricity=geo["eccentricity"],
        compactness=geo["compactness"],
        convexity=geo["convexity"],
        aspect_ratio=geo["aspect_ratio"],
        previous_observation_id=previous_obs_id,
        polygon_iou=polygon_iou,
        centroid_displacement_km=centroid_displacement_km,
        area_change_pct=area_change_pct,
        persistence=persistence,
        observation_gap_hours=observation_gap_hours,
        f1_confidence=f1_confidence,
        data_quality=data_quality,
        is_observed=is_observed,
    )


def reconstruct_event(
    detections: List[Dict[str, Any]],
    interp_interval_h: float = _INTERP_INTERVAL_H,
    pred_steps: int = _PRED_STEPS,
    pred_interval_h: float = _PRED_INTERVAL_H,
) -> TemporalProgressionResult:
    """
    Main F2 reconstruction logic.

    Parameters
    ----------
    detections : list of SpillDetectionResult dicts (from F1 mock or live F1)
    interp_interval_h : hours between synthetic INTERPOLATED gap-fill states
    pred_steps : number of PREDICTED states to append after last OBSERVED
    pred_interval_h : hours between PREDICTED states

    Returns
    -------
    TemporalProgressionResult with all states and event-level flags
    """
    if not detections:
        return TemporalProgressionResult(
            event_id="UNKNOWN",
            total_states=0,
            observed_count=0,
            interpolated_count=0,
            predicted_count=0,
            states=[],
            insufficient_temporal_data=True,
        )

    # Validate and sort by acquisition_timestamp
    parsed: List[SpillDetectionResult] = []
    for d in detections:
        if isinstance(d, SpillDetectionResult):
            parsed.append(d)
        else:
            parsed.append(SpillDetectionResult(**d))

    event_id = parsed[0].event_id

    # Sort by timestamp
    parsed.sort(key=lambda r: _to_utc(r.acquisition_timestamp))

    # Filter to oil_present scenes only (no-oil scenes don't generate states)
    observed_recs = [r for r in parsed if r.oil_present]

    logger.info(
        "F2 reconstruct event=%s total_scenes=%d oil_present=%d",
        event_id, len(parsed), len(observed_recs),
    )

    states: List[TemporalSpillState] = []
    seq = 0
    persistence_counter = 0

    # Reference time (first observed timestamp)
    t0: Optional[datetime] = _to_utc(observed_recs[0].acquisition_timestamp) if observed_recs else None

    # ── Build OBSERVED states + fill INTERPOLATED gaps ─────────────────────
    prev_geojson: Optional[Dict[str, Any]] = None
    prev_centroid: Optional[Tuple[float, float]] = None
    prev_area_km2: Optional[float] = None
    prev_timestamp: Optional[datetime] = None
    prev_obs_id: str = ""
    last_observed_id: str = ""

    for i, rec in enumerate(observed_recs):
        rec_ts = _to_utc(rec.acquisition_timestamp)
        sim_h = _hours_between(t0, rec_ts) if t0 is not None else 0.0

        # ── Gap fill: insert INTERPOLATED states between two OBSERVED ────────
        if prev_timestamp is not None and prev_geojson is not None:
            gap_h = _hours_between(prev_timestamp, rec_ts)
            if gap_h > interp_interval_h:
                n_interp = int(gap_h // interp_interval_h)
                for k in range(1, n_interp + 1):
                    t_val = k / (n_interp + 1)
                    interp_ts_offset = gap_h * t_val
                    from datetime import timedelta
                    interp_ts = prev_timestamp + timedelta(hours=interp_ts_offset)
                    interp_poly = interpolate_polygon(prev_geojson, rec.polygon_geojson, t_val)
                    interp_geo = extract_geometry_features(interp_poly)
                    interp_sim_h = _hours_between(t0, interp_ts) if t0 is not None else 0.0
                    interp_state = _build_state(
                        event_id=event_id,
                        seq=seq,
                        scene_id="",
                        timestamp=interp_ts,
                        sim_hours=interp_sim_h,
                        state_type="INTERPOLATED",
                        polygon_geojson=interp_poly,
                        f1_confidence=0.0,
                        data_quality="interpolated",
                        is_observed=False,
                        previous_obs_id=prev_obs_id,
                        prev_geojson=prev_geojson,
                        prev_centroid=prev_centroid,
                        prev_area_km2=prev_area_km2,
                        prev_timestamp=prev_timestamp,
                        persistence=persistence_counter,
                    )
                    states.append(interp_state)
                    seq += 1
                    # Update previous for next interp step
                    prev_geojson = interp_poly
                    prev_centroid = (interp_geo["centroid_lat"], interp_geo["centroid_lon"])
                    prev_area_km2 = interp_geo["area_km2"]
                    prev_timestamp = interp_ts
                    prev_obs_id = interp_state.observation_id

        # ── Build the OBSERVED state ──────────────────────────────────────
        # Provenance rule (Blueprint #10): previous_observation_id must point
        # to the nearest prior OBSERVED state, never an INTERPOLATED/PREDICTED state.
        persistence_counter += 1
        obs_state = _build_state(
            event_id=event_id,
            seq=seq,
            scene_id=rec.scene_id,
            timestamp=rec_ts,
            sim_hours=sim_h,
            state_type="OBSERVED",
            polygon_geojson=rec.polygon_geojson,
            f1_confidence=rec.confidence,
            data_quality=rec.data_quality_flag,
            is_observed=True,
            previous_obs_id=last_observed_id,
            prev_geojson=prev_geojson,
            prev_centroid=prev_centroid,
            prev_area_km2=prev_area_km2,
            prev_timestamp=prev_timestamp,
            persistence=persistence_counter,
        )
        states.append(obs_state)
        obs_geo = extract_geometry_features(rec.polygon_geojson)
        prev_geojson = rec.polygon_geojson
        prev_centroid = (obs_geo["centroid_lat"], obs_geo["centroid_lon"])
        prev_area_km2 = obs_geo["area_km2"]
        prev_timestamp = rec_ts
        prev_obs_id = obs_state.observation_id
        last_observed_id = obs_state.observation_id
        seq += 1

    # ── Append PREDICTED states (extrapolated beyond last OBSERVED) ──────────
    if len(observed_recs) >= 2 and prev_geojson is not None and pred_steps > 0:
        # Prediction uses the last two OBSERVED polygons for extrapolation direction
        obs_second_last_poly = observed_recs[-2].polygon_geojson
        obs_last_poly = observed_recs[-1].polygon_geojson
        dt_obs = _hours_between(
            _to_utc(observed_recs[-2].acquisition_timestamp),
            _to_utc(observed_recs[-1].acquisition_timestamp),
        )
        if dt_obs <= 0:
            dt_obs = pred_interval_h

        for k in range(1, pred_steps + 1):
            from datetime import timedelta
            pred_ts = prev_timestamp + timedelta(hours=pred_interval_h * k)
            pred_poly = extrapolate_polygon(
                obs_second_last_poly, obs_last_poly,
                dt_extra=pred_interval_h * k,
                dt_obs=dt_obs,
            )
            pred_sim_h = _hours_between(t0, pred_ts) if t0 is not None else 0.0
            pred_state = _build_state(
                event_id=event_id,
                seq=seq,
                scene_id="",
                timestamp=pred_ts,
                sim_hours=pred_sim_h,
                state_type="PREDICTED",
                polygon_geojson=pred_poly,
                f1_confidence=0.0,
                data_quality="predicted",
                is_observed=False,
                previous_obs_id=prev_obs_id,
                prev_geojson=prev_geojson,
                prev_centroid=prev_centroid,
                prev_area_km2=prev_area_km2,
                prev_timestamp=prev_timestamp,
                persistence=persistence_counter,
            )
            states.append(pred_state)
            pred_geo = extract_geometry_features(pred_poly)
            prev_geojson = pred_poly
            prev_centroid = (pred_geo["centroid_lat"], pred_geo["centroid_lon"])
            prev_area_km2 = pred_geo["area_km2"]
            prev_timestamp = pred_ts
            prev_obs_id = pred_state.observation_id
            seq += 1

    observed_count = sum(1 for s in states if s.state_type == "OBSERVED")
    interpolated_count = sum(1 for s in states if s.state_type == "INTERPOLATED")
    predicted_count = sum(1 for s in states if s.state_type == "PREDICTED")

    return TemporalProgressionResult(
        event_id=event_id,
        total_states=len(states),
        observed_count=observed_count,
        interpolated_count=interpolated_count,
        predicted_count=predicted_count,
        states=states,
        insufficient_temporal_data=(observed_count < 2),
    )
