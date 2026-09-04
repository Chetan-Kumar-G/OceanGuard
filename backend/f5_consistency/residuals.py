"""Residual computation, one function per relationship type.

Only ``spatial_residual_km`` and ``temporal_residual_h`` feed the verdict
(see README ADR). ``drift_residual_km`` and ``ais_gap_ratio`` are filled for
context and downstream tallies but never classify on their own.
"""
from __future__ import annotations

from typing import Any

from . import _geo
from .config import EvidenceThresholds
from .engine import ResidualSet


def _num(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        v = row.get(key)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _flag(row: dict[str, Any], key: str) -> bool:
    return bool(row.get(key))


# --------------------------------------------------------------------------- F1<->F2
def f1_detection_vs_f2_state(scene: dict, state: dict, thr: EvidenceThresholds) -> ResidualSet:
    """Does F1's detection agree, in place and time, with the F2 state derived
    from it? For a faithful pipeline the residuals are near zero; a large gap
    means the reconstructed state drifted from what was actually detected."""
    rs = ResidualSet()

    s_lat, s_lon = _num(scene, "latitude"), _num(scene, "longitude")
    o_lat, o_lon = _num(state, "centroid_lat"), _num(state, "centroid_lon")
    if None in (s_lat, s_lon, o_lat, o_lon):
        rs.set_constrained("spatial_residual_km", None, missing_label="f1/f2 centroid coordinates")
    else:
        rs.set_constrained(
            "spatial_residual_km",
            _geo.haversine_km((s_lat, s_lon), (o_lat, o_lon)),
        )

    t_scene = _text(scene, "acquisition_timestamp")
    t_state = _text(state, "timestamp")
    if not t_scene or not t_state:
        rs.set_constrained("temporal_residual_h", None, missing_label="acquisition/state timestamp")
    else:
        rs.set_constrained("temporal_residual_h", _geo.hours_between(t_scene, t_state))
    return rs


# --------------------------------------------------------------------------- F2<->F3
def f2_drift_vs_f3_forcing(
    state0: dict, state1: dict, hyp: dict, thr: EvidenceThresholds
) -> ResidualSet:
    """Is the observed slick displacement between the first two OBSERVED states
    consistent with the environmental forcing F3 used?

    Standalone/mock mode (no live F3 forcing field): the constrained spatial
    residual is the part of the observed displacement that *no* plausible
    current + wind-drift could produce — 0 for a genuine oil slick advecting
    with the sea, large and CONTRADICTS-worthy for a vessel-like track. The raw
    observed displacement is reported as ``drift_residual_km`` for context.
    """
    rs = ResidualSet()

    c0 = (_num(state0, "centroid_lat"), _num(state0, "centroid_lon"))
    c1 = (_num(state1, "centroid_lat"), _num(state1, "centroid_lon"))
    t0 = _text(state0, "timestamp")
    t1 = _text(state1, "timestamp")
    if None in c0 or None in c1 or not t0 or not t1:
        rs.set_constrained("spatial_residual_km", None, missing_label="f2 state geometry/timestamps")
        return rs

    dt_h = _geo.signed_hours(t1, t0)
    if dt_h <= 0:
        rs.set_constrained(
            "spatial_residual_km", None, missing_label="two time-ordered OBSERVED states"
        )
        return rs

    obs_disp_km = _geo.haversine_km(c0, c1)
    obs_speed_kmh = obs_disp_km / dt_h

    wdf = _num(hyp or {}, "wind_drift_factor") or thr.drift_model.default_wind_drift_factor
    max_kmh = (
        thr.drift_model.max_current_speed_ms + wdf * thr.drift_model.max_wind_speed_ms
    ) * 3.6
    unexplained_km = max(0.0, obs_speed_kmh - max_kmh) * dt_h

    rs.set_constrained("spatial_residual_km", unexplained_km)
    rs.set_context("drift_residual_km", obs_disp_km)
    rs.notes.append(
        f"observed drift {obs_disp_km:.1f} km / {dt_h:.1f} h = {obs_speed_kmh:.2f} km/h "
        f"vs forcing-plausible {max_kmh:.2f} km/h"
    )
    return rs


# --------------------------------------------------------------------------- F3<->F4
def f3_hypothesis_vs_f4_track(hyp: dict, track: dict, thr: EvidenceThresholds) -> ResidualSet:
    """Where and when was the vessel relative to the backtracked source?

    Spatial: the vessel's effective closest approach to the F3 source.
    Temporal: gap between that closest approach and the F3 origin-time midpoint.
    If the vessel went dark directly over the source the temporal residual is
    not evaluable and is dropped from the verdict (still reported).
    """
    rs = ResidualSet()

    rs.set_constrained(
        "spatial_residual_km",
        _num(track, "distance_to_source_effective_km"),
        missing_label="distance_to_source_effective_km",
    )

    origin_mid = _text(hyp or {}, "origin_time_mid")
    # Prefer the real closest-approach fix; fall back to the interpolated fill
    # only when there is no observed timestamp (blueprint: never let an
    # interpolated position stand in for an observed one where a real one exists).
    ref_ts = _text(track, "closest_approach_timestamp") or _text(
        track, "interpolated_closest_timestamp"
    )
    dark_gap = _flag(track, "dark_gap_over_source")
    temporal = _geo.hours_between(ref_ts, origin_mid) if (ref_ts and origin_mid) else None

    if dark_gap:
        rs.notes.append("vessel dark over source — temporal residual not evaluable")
    elif temporal is None:
        rs.set_constrained(
            "temporal_residual_h", None, missing_label="closest-approach timestamp / origin_time_mid"
        )
    else:
        rs.set_constrained("temporal_residual_h", temporal)

    # weak, context-only motion disagreement (a vessel does not drift with its slick)
    course_compat = _num(track, "course_compatibility")
    obs_kn = _num(track, "observed_speed_kn")
    slick_kn = _num(track, "slick_drift_speed_kn")
    if course_compat is not None and obs_kn is not None and slick_kn is not None:
        rs.set_context(
            "drift_residual_km", (1.0 - course_compat) * 20.0 + abs(obs_kn - slick_kn)
        )
    rs.set_context("ais_gap_ratio", _num(track, "ais_gap_ratio_origin_window"))

    # stash the display-only temporal value even when it was dropped from the verdict
    if dark_gap and temporal is not None:
        rs.context["_temporal_display_h"] = temporal
    return rs
