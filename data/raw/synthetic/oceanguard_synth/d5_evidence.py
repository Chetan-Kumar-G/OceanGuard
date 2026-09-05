"""D5 - evidence consistency dataset (derived).

One row per evidence relationship between two upstream products (F1..F4). Each
row carries the residuals that were compared and a relation label. The label
rule is fixed and configuration-driven:

    SUPPORTS      - every constrained residual is <= its support bound
    CONTRADICTS   - any constrained residual is >= its contradict bound
    UNKNOWN       - anything in between
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .drift import DriftParams, integrate
from .environment import Environment
from .events import Event
from .geo import Frame


def _classify(residuals: dict, sup: dict, con: dict) -> tuple[str, str]:
    hot = [k for k, v in residuals.items() if v >= con[k]]
    if hot:
        return "CONTRADICTS", "exceeds contradict bound: " + ", ".join(
            f"{k}={residuals[k]:.2f}>={con[k]}" for k in hot)
    cool = {k: v for k, v in residuals.items() if v <= sup[k]}
    if len(cool) == len(residuals):
        return "SUPPORTS", "all residuals within support bounds"
    warm = [k for k in residuals if k not in cool]
    return "UNKNOWN", "residuals in the grey band: " + ", ".join(
        f"{k}={residuals[k]:.2f}" for k in warm)


def _forcing_predicted_drift(env: Environment, cfg: Config, start_xy, t0_h, t1_h):
    params = DriftParams(
        wind_drift_factor=float(cfg["environment"]["wind_drift_factor"]),
        diffusion_m2s=0.0,
    )
    g = np.random.default_rng(0)
    dt_h = float(cfg["time"]["step_minutes"]) / 60.0
    _, traj = integrate(env, np.array([start_xy], dtype=float), t0_h, t1_h, dt_h, params, g)
    return traj[-1][0]


def generate_d5(cfg: Config, env: Environment, frame: Frame, events: list[Event],
                d2_states: dict, d3, d4_tracks: pd.DataFrame, candidates: dict):
    sup = cfg["evidence"]["support"]
    con = cfg["evidence"]["contradict"]
    rows: list[dict] = []
    tally: dict[tuple, dict] = {}

    trk_by_ev = {ev: d4_tracks[d4_tracks.event_id == ev] for ev in d4_tracks.event_id.unique()} \
        if not d4_tracks.empty else {}

    for ev in events:
        states = [s for s in d2_states[ev.event_id] if s.state_type == "OBSERVED"]
        hyp = d3.best_hyp.get(ev.event_id)
        if len(states) < 2 or hyp is None:
            continue
        s0, s1 = states[0], states[1]
        sensor_conf = float(np.mean([s.f1_confidence for s in states if s.f1_confidence > 0] or [0.5]))
        obs_count = len(states)
        forcing_quality = "reanalysis-nominal"

        # ---- F1 detection vs F2 reconstructed state ----
        rid = f"{ev.event_id}-EV-F1F2"
        res = {"spatial_residual_km": float(np.hypot(*(s0.centroid - s0.centroid)))}
        rel, why = _classify(res, sup, con)
        if sensor_conf < 0.5:
            rel, why = "UNKNOWN", "low sensor confidence on the seed detection"
        rows.append(_row(cfg, rid, ev, s0.observation_id, "F1_DETECTION",
                         s1.observation_id, "F2_STATE", s0.t_h, s1.t_h,
                         res.get("spatial_residual_km", 0.0), abs(s1.t_h - s0.t_h),
                         np.nan, np.nan, sensor_conf, obs_count, forcing_quality, rel, why,
                         f"F1:{s0.observation_id}|F2:{s1.observation_id}"))

        # ---- F2 observed drift vs F3 forcing ----
        pred_end = _forcing_predicted_drift(env, cfg, s0.centroid, s0.t_h, s1.t_h)
        drift_res = float(np.hypot(*(pred_end - s1.centroid)))
        obs_disp = float(np.hypot(*(s1.centroid - s0.centroid)))
        res = {"drift_residual_km": drift_res}
        rel, why = _classify(res, sup, con)
        rid = f"{ev.event_id}-EV-F2F3"
        rows.append(_row(cfg, rid, ev, s1.observation_id, "F2_DRIFT",
                         hyp["source_hypothesis_id"], "F3_FORCING", s0.t_h, s1.t_h,
                         drift_res, 0.0, drift_res, np.nan, sensor_conf, obs_count,
                         forcing_quality, rel, why + f" (observed disp {obs_disp:.1f} km)",
                         f"F2:{s0.observation_id},{s1.observation_id}|F3:{hyp['source_hypothesis_id']}"))

        # ---- F3 source hypothesis vs each F4 candidate track ----
        trk = d4_tracks[d4_tracks.event_id == ev.event_id] if not d4_tracks.empty else pd.DataFrame()
        for _, tr in trk.iterrows():
            spatial = float(tr["distance_to_source_effective_km"])
            ref_ts = tr["interpolated_closest_timestamp"] or tr["closest_approach_timestamp"]
            temporal = abs(_h(cfg, ref_ts) - hyp["origin_time_mid_sim_h"]) \
                if ref_ts else con["temporal_residual_h"]
            gap_ratio = float(tr["ais_gap_ratio_origin_window"])
            # course/speed disagreement, reported for context only: a vessel does
            # not drift with its slick, so this is weak evidence and never drives
            # the SUPPORTS/CONTRADICTS verdict on its own.
            drift_dis = (1.0 - float(tr["course_compatibility"])) * 20.0 \
                + abs(float(tr["observed_speed_kn"]) - float(tr["slick_drift_speed_kn"])) * 1.0

            # verdict rests on where and when the vessel was relative to the
            # backtracked source. If it went dark over the source the temporal
            # residual is not evaluable and is dropped.
            res = {"spatial_residual_km": spatial}
            if not bool(tr["dark_gap_over_source"]):
                res["temporal_residual_h"] = float(temporal)
            rel, why = _classify(res, sup, con)
            if rel == "SUPPORTS" and gap_ratio > float(sup["ais_gap_ratio"]) \
                    and not bool(tr["dark_gap_over_source"]):
                rel, why = "UNKNOWN", f"support residuals but AIS gap ratio {gap_ratio:.2f} is high"
            rid = f"{ev.event_id}-EV-F3F4-{tr['mmsi']}"
            rows.append(_row(cfg, rid, ev, hyp["source_hypothesis_id"], "F3_SOURCE_HYPOTHESIS",
                             str(tr["track_id"]), "F4_VESSEL_TRACK",
                             hyp["origin_time_mid_sim_h"],
                             _h(cfg, tr["closest_approach_timestamp"]) if tr["closest_approach_timestamp"] else np.nan,
                             spatial, float(temporal), float(drift_dis), gap_ratio,
                             sensor_conf, obs_count, forcing_quality, rel, why,
                             f"F3:{hyp['source_hypothesis_id']}|F4:{tr['track_id']}"))
            key = (ev.event_id, int(tr["mmsi"]))
            t = tally.setdefault(key, {"SUPPORTS": 0, "CONTRADICTS": 0, "UNKNOWN": 0})
            t[rel] += 1

    return pd.DataFrame(rows), tally


def _h(cfg: Config, iso: str) -> float:
    from datetime import datetime, timezone
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (dt - cfg.sim_start).total_seconds() / 3600.0


def _row(cfg, eid, ev, a_id, a_type, b_id, b_type, ta, tb, spatial, temporal,
         drift, gap, sensor_conf, obs_count, fq, rel, reason, provenance):
    return dict(
        evidence_id=eid, event_id=ev.event_id,
        source_a_id=a_id, source_a_type=a_type,
        source_b_id=b_id, source_b_type=b_type,
        timestamp_a=cfg.iso(ta) if ta == ta else "",
        timestamp_b=cfg.iso(tb) if tb == tb else "",
        spatial_residual_km=round(float(spatial), 4) if spatial == spatial else np.nan,
        temporal_residual_h=round(float(temporal), 4) if temporal == temporal else np.nan,
        drift_residual_km=round(float(drift), 4) if drift == drift else np.nan,
        ais_gap_ratio=round(float(gap), 4) if gap == gap else np.nan,
        sensor_confidence=round(float(sensor_conf), 4),
        observation_count=int(obs_count),
        forcing_quality=fq,
        relation=rel, reason=reason, provenance=provenance,
    )
