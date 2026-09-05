"""D6 - evidence ranking dataset (derived).

One row per candidate hypothesis (event x candidate vessel). Component scores in
[0, 1] are combined with the configured weights, penalised per CONTRADICTS
relation from D5, and scaled by a data-quality weight. Candidates are ranked per
event; the event carries an ``insufficient_evidence`` outcome when the top score
is too low, the margin over rank 2 is too thin, or too little evidence exists.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .events import Event


def _band(score: float, cfg: Config) -> str:
    b = cfg["ranking"]["confidence_bands"]
    if score >= b["high"]:
        return "high"
    if score >= b["medium"]:
        return "medium"
    return "low"


def generate_d6(cfg: Config, events: list[Event], fleet, d1_scenes: pd.DataFrame,
                d3, d4_tracks: pd.DataFrame, d5: pd.DataFrame, d5_tally: dict,
                candidates: dict):
    w = cfg["ranking"]["weights"]
    scale = float(cfg["ranking"]["compat_scale_km"])
    pen = float(cfg["ranking"]["contradiction_penalty"])
    ins = cfg["ranking"]["insufficient_evidence"]
    match_r = float(cfg["hindcast"]["source_match_radius_km"])
    half = float(cfg["hindcast"]["origin_window_half_h"])

    rows: list[dict] = []
    for ev in events:
        hyp = d3.best_hyp.get(ev.event_id)
        trk = d4_tracks[d4_tracks.event_id == ev.event_id] if not d4_tracks.empty else pd.DataFrame()
        if hyp is None or trk.empty:
            continue
        event_evidence_count = int((d5["event_id"] == ev.event_id).sum()) if not d5.empty else 0
        cloud = d3.source_clouds.get(ev.event_id, {}).get(hyp["source_hypothesis_id"])
        unc = float(hyp["uncertainty_radius_km"])
        t_first_obs = float(hyp.get("first_observation_sim_h", hyp["origin_time_mid_sim_h"]))
        win_t = np.arange(t_first_obs - 30.0, t_first_obs + 6.0 + 1e-6, 0.25)
        sensor_conf = float(d1_scenes[(d1_scenes.event_id == ev.event_id) &
                                      (d1_scenes.f1_detected)]["f1_confidence"].mean())
        if not np.isfinite(sensor_conf):
            sensor_conf = 0.5
        dq_weight = float(np.clip(0.5 + 0.5 * sensor_conf, 0.0, 1.0))

        comp_rows = []
        for _, tr in trk.iterrows():
            mmsi = int(tr["mmsi"])
            v = fleet.by_mmsi[mmsi]
            # source probability: best overlap of the vessel's (interpolated) path
            # with the backtracked source cloud anywhere in the window
            if cloud is not None and len(cloud):
                act = (win_t >= v.t_start) & (win_t <= v.t_end)
                best = 0.0
                if act.any():
                    path = v.position(win_t[act])
                    for px, py in path:
                        frac = float((np.hypot(cloud[:, 0] - px, cloud[:, 1] - py) <= match_r).mean())
                        if frac > best:
                            best = frac
                source_prob = best
            else:
                source_prob = 0.0

            dist = float(tr["distance_to_source_effective_km"])
            spatial = float(np.exp(-max(0.0, dist - unc) / scale))
            temporal = float(tr["temporal_compatibility"])
            drift = float(0.5 * tr["course_compatibility"] + 0.5 * tr["speed_compatibility"])
            ais_complete = float(tr["track_completeness"])
            gap_ratio = float(tr["ais_gap_ratio_origin_window"])
            spd = float(tr["observed_speed_kn"])
            dark_hit = float(bool(tr["dark_gap_over_source"]))
            near_src = float(dist <= match_r + unc)
            behavioural = float(np.clip(
                0.55 * dark_hit
                + 0.25 * gap_ratio * near_src
                + 0.20 * (1.0 - min(spd / 8.0, 1.0)) * near_src,
                0.0, 1.0))

            t = d5_tally.get((ev.event_id, mmsi), {"SUPPORTS": 0, "CONTRADICTS": 0, "UNKNOWN": 0})
            contra = int(t["CONTRADICTS"])
            unknown = int(t["UNKNOWN"])
            support = int(t["SUPPORTS"])
            n_evidence = event_evidence_count

            weighted = (w["source_probability"] * source_prob
                        + w["spatial_compatibility"] * spatial
                        + w["temporal_compatibility"] * temporal
                        + w["drift_compatibility"] * drift
                        + w["ais_completeness"] * ais_complete
                        + w["behavioural_score"] * behavioural
                        + w["sensor_confidence"] * sensor_conf)
            final = float(np.clip((weighted - pen * contra) * dq_weight, 0.0, 1.0))

            comp_rows.append(dict(
                event_id=ev.event_id, hypothesis_id=f"{ev.event_id}-C-{mmsi}",
                candidate_mmsi=mmsi, is_true_source=bool(tr["is_true_source"]),
                vessel_type=tr["vessel_type"],
                source_probability=round(source_prob, 4),
                spatial_compatibility=round(spatial, 4),
                temporal_compatibility=round(temporal, 4),
                drift_compatibility=round(drift, 4),
                ais_completeness=round(ais_complete, 4),
                behavioural_score=round(behavioural, 4),
                sensor_confidence=round(sensor_conf, 4),
                contradiction_count=contra, unknown_count=unknown, support_count=support,
                n_evidence_items=n_evidence,
                data_quality_weight=round(dq_weight, 4),
                final_score=round(final, 4),
                distance_to_source_km=round(dist, 3),
                dark_gap_over_source=bool(tr["dark_gap_over_source"]),
                closest_approach_is_interpolated=bool(tr["closest_approach_is_interpolated"]),
                source_hypothesis_id=hyp["source_hypothesis_id"],
            ))

        comp_rows.sort(key=lambda r: r["final_score"], reverse=True)
        top = comp_rows[0]["final_score"]
        second = comp_rows[1]["final_score"] if len(comp_rows) > 1 else 0.0
        margin = top - second
        max_evidence = max(r["n_evidence_items"] for r in comp_rows)
        event_insufficient = bool(
            top < float(ins["min_final_score"])
            or margin < float(ins["min_margin"])
            or max_evidence < int(ins["min_evidence_items"]))

        for rank, r in enumerate(comp_rows, start=1):
            r["rank"] = rank
            r["margin_to_next"] = round(
                r["final_score"] - (comp_rows[rank]["final_score"] if rank < len(comp_rows) else 0.0), 4)
            r["confidence_band"] = _band(r["final_score"], cfg)
            r["event_insufficient_evidence"] = event_insufficient
            r["explanation"] = (
                f"src_prob={r['source_probability']:.2f}, spatial={r['spatial_compatibility']:.2f}, "
                f"temporal={r['temporal_compatibility']:.2f}, drift={r['drift_compatibility']:.2f}, "
                f"behaviour={r['behavioural_score']:.2f}, contradictions={r['contradiction_count']}; "
                f"final={r['final_score']:.2f} (rank {rank}/{len(comp_rows)})")
            rows.append(r)

    cols = ["event_id", "hypothesis_id", "candidate_mmsi", "rank", "final_score",
            "confidence_band", "event_insufficient_evidence", "is_true_source",
            "vessel_type", "source_probability", "spatial_compatibility",
            "temporal_compatibility", "drift_compatibility", "ais_completeness",
            "behavioural_score", "sensor_confidence", "contradiction_count",
            "unknown_count", "support_count", "n_evidence_items", "data_quality_weight",
            "margin_to_next", "distance_to_source_km", "dark_gap_over_source",
            "closest_approach_is_interpolated", "source_hypothesis_id", "explanation"]
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[cols]
    return df
