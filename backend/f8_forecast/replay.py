"""Historical replay scoring for F8.

For a completed forward run, each horizon is matched to the nearest *later*
OBSERVED satellite state and scored: trajectory error, observed-region coverage
(IoU), envelope capture, and ensemble calibration.

This is the ONLY F8 code path that reads observations later than T0. The forecast
itself (``ensemble.py`` / ``supervisor.execute_forecast``) never sees them.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from shared.physics.lagrangian import Frame
from shared.schemas.f2_contract import TemporalSpillState
from shared.schemas.f8_contract import ForecastEvaluation, ForecastRun, LonLat
from backend.f8_forecast.geometry import (
    coverage_frac,
    epoch_hours,
    geojson_to_polygon_km,
    point_in_polygon,
    safe_iou,
)


def _state_polygon_km(state: TemporalSpillState, frame: Frame):
    return geojson_to_polygon_km(state.polygon_geojson.model_dump(), frame)


def _state_centroid_km(state: TemporalSpillState, frame: Frame) -> np.ndarray:
    x, y = frame.to_km(state.centroid.lon, state.centroid.lat)
    return np.array([float(x), float(y)], dtype=float)


def _sim_h(state: TemporalSpillState) -> float:
    sh = getattr(state, "sim_hours", None)
    return float(sh) if sh is not None else epoch_hours(state.timestamp)


def score_forecast(
    *,
    runs: List[ForecastRun],
    envelope_polys_km: dict,          # horizon_h -> shapely Polygon (km frame)
    predicted_polys_km: dict,         # horizon_h -> shapely Polygon (km frame)
    predicted_centroids_km: dict,     # horizon_h -> np.ndarray (2,)
    spreads_km: dict,                 # horizon_h -> float
    t0_sim_h: float,
    later_observed: List[TemporalSpillState],
    frame: Frame,
    match_tolerance_h: float = 12.0,
) -> List[ForecastEvaluation]:
    """Match each forecast horizon to the nearest later OBSERVED state and score it.

    Times are in simulation-hours (the forcing-field clock) so the match window
    lines up with how the ensemble was integrated.
    """
    later = [s for s in later_observed if _sim_h(s) > t0_sim_h + 1.0]
    evals: List[ForecastEvaluation] = []
    if not later:
        return evals

    for run in runs:
        h = float(run.forecast_horizon_hours)
        target_h = t0_sim_h + h
        match = min(later, key=lambda s: abs(_sim_h(s) - target_h))
        offset = _sim_h(match) - target_h
        if abs(offset) > match_tolerance_h:
            continue

        pred_cen = predicted_centroids_km[h]
        obs_cen = _state_centroid_km(match, frame)
        obs_poly = _state_polygon_km(match, frame)
        pred_poly = predicted_polys_km[h]
        env_poly = envelope_polys_km[h]
        spread = float(spreads_km[h])

        traj_err = float(np.hypot(*(pred_cen - obs_cen)))
        iou = safe_iou(pred_poly, obs_poly)
        in_env = coverage_frac(obs_poly, env_poly)
        centroid_in_env = point_in_polygon(float(obs_cen[0]), float(obs_cen[1]), env_poly)
        calib = float(traj_err / max(spread, 1e-6))

        evals.append(ForecastEvaluation(
            event_id=run.event_id,
            forecast_id=run.forecast_id,
            forecast_horizon_hours=h,
            valid_timestamp=run.valid_timestamp,
            matched_observation_id=match.observation_id,
            matched_timestamp=match.timestamp,
            match_offset_hours=round(float(offset), 3),
            predicted_centroid=run.predicted_centroid,
            observed_centroid=LonLat(lat=match.centroid.lat, lon=match.centroid.lon),
            trajectory_error_km=round(traj_err, 4),
            observed_region_coverage_iou=round(float(np.clip(iou, 0.0, 1.0)), 4),
            observed_in_forecast_envelope_frac=round(float(np.clip(in_env, 0.0, 1.0)), 4),
            observed_centroid_in_envelope=bool(centroid_in_env),
            calibration_ratio=round(calib, 4),
            well_calibrated=bool(0.5 <= calib <= 2.0),
        ))
    return evals
