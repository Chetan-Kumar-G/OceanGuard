"""D4 - historical AIS dataset.

Two tables:
  * D4_ais_raw     - every AIS transmission for the whole fleet. Observed rows
                     (is_observed=True) and regular-cadence interpolated rows
                     (is_observed=False) are both present and clearly flagged.
  * D4_tracks      - per (event, candidate vessel) reconstructed track summary
                     with spatio-temporal compatibility against the D3 source
                     hypothesis. Candidates = true culprit + nearest decoys.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .environment import Environment
from .events import Event
from .geo import Frame
from .rng import RNG
from .vessels import Fleet, interpolated_track, transmissions


def _raw_ais(cfg: Config, rng: RNG, frame: Frame, fleet: Fleet) -> pd.DataFrame:
    rows: list[dict] = []
    for v in fleet:
        g = rng.stream("d4", "raw", v.mmsi)
        for tr in transmissions(v, cfg, g):
            lon, lat = frame.to_lonlat(tr["x_km"], tr["y_km"])
            rows.append(dict(
                mmsi=tr["mmsi"], timestamp=cfg.iso(tr["t_h"]), sim_hours=round(tr["t_h"], 4),
                latitude=round(float(lat), 6), longitude=round(float(lon), 6),
                sog_kn=tr["sog_kn"], cog_deg=tr["cog_deg"], heading_deg=tr["heading_deg"],
                nav_status=tr["nav_status"], vessel_type=tr["vessel_type"],
                vessel_length=tr["length"], vessel_width=tr["width"], draught=tr["draught"],
                source="AIS-terrestrial", is_observed=True,
            ))
        for ir in interpolated_track(v, cfg):
            lon, lat = frame.to_lonlat(ir["x_km"], ir["y_km"])
            rows.append(dict(
                mmsi=ir["mmsi"], timestamp=cfg.iso(ir["t_h"]), sim_hours=round(ir["t_h"], 4),
                latitude=round(float(lat), 6), longitude=round(float(lon), 6),
                sog_kn=ir["sog_kn"], cog_deg=ir["cog_deg"], heading_deg=ir["heading_deg"],
                nav_status=ir["nav_status"], vessel_type=ir["vessel_type"],
                vessel_length=ir["length"], vessel_width=ir["width"], draught=ir["draught"],
                source="interpolation", is_observed=False,
            ))
    df = pd.DataFrame(rows).sort_values(["mmsi", "sim_hours"]).reset_index(drop=True)
    return df


def _obs_positions(vessel, t_lo, t_hi, cfg, g):
    """Observed transmissions of one vessel inside a time window (km frame)."""
    out = []
    for tr in transmissions(vessel, cfg, g):
        if t_lo <= tr["t_h"] <= t_hi:
            out.append((tr["t_h"], tr["x_km"], tr["y_km"], tr["sog_kn"], tr["cog_deg"]))
    return out


def generate_d4(cfg: Config, rng: RNG, env: Environment, frame: Frame,
                events: list[Event], fleet: Fleet, d3, d2_states: dict):
    raw_df = _raw_ais(cfg, rng, frame, fleet)

    n_decoy = int(cfg["ais"]["candidate_decoys"])
    half = float(cfg["hindcast"]["origin_window_half_h"])
    match_r = float(cfg["hindcast"]["source_match_radius_km"])
    trk_rows: list[dict] = []
    candidates: dict[str, list[int]] = {}

    for ev in events:
        hyp = d3.best_hyp.get(ev.event_id)
        if hyp is None:
            continue
        src = np.array([hyp["source_x_km"], hyp["source_y_km"]])
        t_mid = float(hyp["origin_time_mid_sim_h"])
        t_first_obs = float(hyp.get("first_observation_sim_h", t_mid))
        t_lo, t_hi = t_mid - half, t_mid + half
        # the observation window is anchored on the *first detection time* (a hard
        # fact), not on the fragile release-time estimate
        win_lo, win_hi = t_first_obs - 30.0, t_first_obs + 6.0

        # slick drift vector from the first two observed D2 states
        obs = [s for s in d2_states[ev.event_id] if s.state_type == "OBSERVED"]
        if len(obs) >= 2:
            dvec = obs[1].centroid - obs[0].centroid
            dt = max(obs[1].t_h - obs[0].t_h, 1e-3)
            drift_speed_kn = float(np.hypot(*dvec) / dt / 1.852)
            drift_course = float(np.degrees(np.arctan2(dvec[0], dvec[1])) % 360.0)
        else:
            drift_speed_kn, drift_course = 0.0, 0.0

        # rank vessels by closest approach to the source during the window
        scored = []
        for v in fleet:
            g = rng.stream("d4", "obs", ev.event_id, v.mmsi)
            pos = _obs_positions(v, win_lo, win_hi, cfg, g)
            if not pos:
                d_min = 9e9
            else:
                d_min = min(float(np.hypot(x - src[0], y - src[1])) for _, x, y, _, _ in pos)
            scored.append((d_min, v.mmsi))
        scored.sort()
        picked = [ev.source_mmsi] + [m for _, m in scored if m != ev.source_mmsi][:n_decoy]
        candidates[ev.event_id] = picked

        for mmsi in picked:
            v = fleet.by_mmsi[mmsi]
            g = rng.stream("d4", "obs", ev.event_id, mmsi)
            pos = _obs_positions(v, win_lo, win_hi, cfg, g)
            is_culprit = (mmsi == ev.source_mmsi)
            if not pos:
                trk_rows.append(_empty_track_row(cfg, ev, v, is_culprit))
                continue
            ts = np.array([p[0] for p in pos])
            xy = np.array([[p[1], p[2]] for p in pos])
            sog = np.array([p[3] for p in pos])
            cog = np.array([p[4] for p in pos])

            gaps = np.diff(ts)
            gap_thr = float(v.report_interval_min) / 60.0 * 3.0
            gap_count = int((gaps > gap_thr).sum())
            max_gap = float(gaps.max()) if len(gaps) else 0.0
            duration = float(ts[-1] - ts[0])
            expected = max(1.0, (win_hi - win_lo) / (float(v.report_interval_min) / 60.0))
            completeness = float(np.clip(len(ts) / expected, 0.0, 1.0))

            d_src = np.hypot(xy[:, 0] - src[0], xy[:, 1] - src[1])
            dist_to_source = float(d_src.min())
            near = ts[(ts >= t_lo) & (ts <= t_hi) & (d_src <= match_r)]
            in_window_pts = ts[(ts >= t_lo) & (ts <= t_hi)]
            track_overlap = float(len(in_window_pts) / max(1.0, (t_hi - t_lo) / (float(v.report_interval_min) / 60.0)))
            track_overlap = float(np.clip(track_overlap, 0.0, 1.0))

            # temporal compatibility: was it near the source during the origin window?
            if len(near):
                temporal_compat = 1.0
            else:
                gap_to_window = float(np.min(np.abs(ts - t_mid)))
                temporal_compat = float(np.exp(-gap_to_window / 12.0))
                if dist_to_source > match_r:
                    temporal_compat *= float(np.exp(-(dist_to_source - match_r) / 20.0))

            # speed / course compatibility vs slick drift
            near_idx = np.argmin(d_src)
            v_sog = float(sog[near_idx])
            v_cog = float(cog[near_idx])
            speed_compat = float(np.exp(-abs(v_sog - drift_speed_kn) / 6.0)) if drift_speed_kn else 0.5
            dcos = np.cos(np.radians(v_cog - drift_course))
            course_compat = float((dcos + 1.0) / 2.0)

            # AIS gap ratio inside the origin window (dark-time fraction)
            win_pts = sorted(in_window_pts.tolist())
            if len(win_pts) >= 2:
                covered = sum(min(b - a, gap_thr) for a, b in zip(win_pts, win_pts[1:]))
                gap_ratio = float(np.clip(1.0 - covered / (t_hi - t_lo), 0.0, 1.0))
            else:
                gap_ratio = 1.0

            # ---- interpolation-reconstructed closest approach (spans dark gaps) ----
            # This is what an investigator does: draw a straight line across the
            # AIS gap. Flagged as interpolation-derived so a consumer knows it is
            # not an observed fix.
            unc = float(hyp["uncertainty_radius_km"])
            dense_t = np.arange(win_lo, win_hi + 1e-6, 0.1)
            act = (dense_t >= v.t_start) & (dense_t <= v.t_end)
            if act.any():
                dp = v.position(dense_t[act])
                dd = np.hypot(dp[:, 0] - src[0], dp[:, 1] - src[1])
                interp_min = float(dd.min())
                interp_min_t = float(dense_t[act][int(np.argmin(dd))])
            else:
                interp_min, interp_min_t = 9999.0, float("nan")

            # did the vessel go dark *while passing near the backtracked source*?
            dark_over_source = False
            dark_gap_hours = 0.0
            for ga, gb in v.dark_gaps:
                oa, ob = max(ga, win_lo), min(gb, win_hi)
                if ob <= oa:
                    continue
                seg_t = np.arange(oa, ob + 1e-6, 0.1)
                seg = v.position(seg_t)
                seg_d = np.hypot(seg[:, 0] - src[0], seg[:, 1] - src[1])
                if float(seg_d.min()) <= match_r + unc:
                    dark_over_source = True
                    dark_gap_hours = max(dark_gap_hours, float(ob - oa))

            d_eff = min(dist_to_source, interp_min)
            closest_is_interp = bool(interp_min < dist_to_source - 0.5)
            if dark_over_source or interp_min <= match_r + unc:
                temporal_compat = max(temporal_compat, 0.85)

            trk_rows.append(dict(
                event_id=ev.event_id, mmsi=mmsi,
                track_id=f"{ev.event_id}-{mmsi}",
                is_true_source=is_culprit,
                vessel_type=v.vessel_type, vessel_length=v.length, vessel_width=v.width,
                draught=v.draught,
                first_timestamp=cfg.iso(float(ts[0])), last_timestamp=cfg.iso(float(ts[-1])),
                track_duration_h=round(duration, 3),
                number_of_observations=int(len(ts)),
                gap_count=gap_count, max_gap_hours=round(max_gap, 3),
                track_completeness=round(completeness, 4),
                distance_to_source_km=round(dist_to_source, 3),
                distance_to_source_interpolated_km=round(min(interp_min, 9999.0), 3),
                distance_to_source_effective_km=round(min(d_eff, 9999.0), 3),
                closest_approach_is_interpolated=closest_is_interp,
                dark_gap_over_source=bool(dark_over_source),
                dark_gap_over_source_hours=round(dark_gap_hours, 3),
                closest_approach_timestamp=cfg.iso(float(ts[near_idx])),
                interpolated_closest_timestamp=cfg.iso(interp_min_t) if interp_min_t == interp_min_t else "",
                temporal_compatibility=round(temporal_compat, 4),
                track_overlap=round(track_overlap, 4),
                speed_compatibility=round(speed_compat, 4),
                course_compatibility=round(course_compat, 4),
                ais_gap_ratio_origin_window=round(gap_ratio, 4),
                observed_speed_kn=round(v_sog, 2), observed_course_deg=round(v_cog, 1),
                slick_drift_speed_kn=round(drift_speed_kn, 2),
                slick_drift_course_deg=round(drift_course, 1),
                source_hypothesis_id=hyp["source_hypothesis_id"],
            ))

    return raw_df, pd.DataFrame(trk_rows), candidates


def _empty_track_row(cfg, ev, v, is_culprit):
    return dict(
        event_id=ev.event_id, mmsi=v.mmsi, track_id=f"{ev.event_id}-{v.mmsi}",
        is_true_source=is_culprit, vessel_type=v.vessel_type, vessel_length=v.length,
        vessel_width=v.width, draught=v.draught, first_timestamp="", last_timestamp="",
        track_duration_h=0.0, number_of_observations=0, gap_count=0, max_gap_hours=0.0,
        track_completeness=0.0, distance_to_source_km=9999.0,
        distance_to_source_interpolated_km=9999.0, distance_to_source_effective_km=9999.0,
        closest_approach_is_interpolated=False, dark_gap_over_source=False,
        dark_gap_over_source_hours=0.0, closest_approach_timestamp="",
        interpolated_closest_timestamp="",
        temporal_compatibility=0.0, track_overlap=0.0, speed_compatibility=0.0,
        course_compatibility=0.0, ais_gap_ratio_origin_window=1.0, observed_speed_kn=0.0,
        observed_course_deg=0.0, slick_drift_speed_kn=0.0, slick_drift_course_deg=0.0,
        source_hypothesis_id="",
    )
