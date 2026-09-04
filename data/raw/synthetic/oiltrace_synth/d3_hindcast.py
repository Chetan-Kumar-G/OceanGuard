"""D3 - backward hindcasting dataset.

For each event the earliest OBSERVED D2 state is seeded with particles and
integrated backward through the (perturbed) forcing. The release time is
*estimated from D2* by back-extrapolating the observed area growth to the initial
slick size - no ground-truth leak - and each ensemble backtracks to its own
noisy copy of that estimate.

Outputs:
  * D3_particles          - sampled backtracked particle positions (trajectories)
  * D3_source_hypotheses  - one row per (event, ensemble): source region + window
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Config
from .drift import DriftParams, integrate
from .environment import Environment
from .events import Event
from .geo import Frame
from .rng import RNG
from .spill_truth import SpillTruth


@dataclass
class D3Result:
    particles: pd.DataFrame
    hypotheses: pd.DataFrame
    source_clouds: dict = field(default_factory=dict)   # event_id -> {hyp_id: (N,2) km}
    best_hyp: dict = field(default_factory=dict)         # event_id -> row dict


_AGE_MIN_H = 3.0
_AGE_MAX_H = 18.0
_AGE_FALLBACK_H = 8.0


def _estimate_release_time(states) -> tuple[float, float]:
    """Return (t_release_est_h, t_first_obs_h) by back-extrapolating D2 area growth.

    Robust to noisy / non-monotone early detections: a least-squares slope on the
    first few observations, a positive-slope guard, a physical prior fallback and
    a hard clip keep the estimated slick age in a sane band.
    """
    obs = [s for s in states if s.state_type == "OBSERVED"]
    t0_obs = obs[0].t_h
    head = obs[: min(5, len(obs))]
    if len(head) >= 2:
        t = np.array([s.t_h for s in head]) - t0_obs
        a = np.array([s.area_km2 for s in head])
        slope, intercept = np.polyfit(t, a, 1)
        if slope <= 0.05:
            diffs = np.diff(a) / np.clip(np.diff(t), 1e-3, None)
            pos = diffs[diffs > 0]
            slope = float(np.median(pos)) if len(pos) else 0.0
        a0 = max(a[0], 0.1)
        age = a0 / slope if slope > 0.05 else _AGE_FALLBACK_H
    else:
        age = _AGE_FALLBACK_H
    return t0_obs - float(np.clip(age, _AGE_MIN_H, _AGE_MAX_H)), t0_obs


def _seed_in_polygon(poly, n, g: np.random.Generator):
    minx, miny, maxx, maxy = poly.bounds
    pts = []
    from shapely.geometry import Point
    trials = 0
    while len(pts) < n and trials < n * 60:
        xs = g.uniform(minx, maxx, n)
        ys = g.uniform(miny, maxy, n)
        for x, y in zip(xs, ys):
            if poly.contains(Point(x, y)):
                pts.append((x, y))
                if len(pts) >= n:
                    break
        trials += n
    if not pts:
        c = poly.centroid
        pts = [(c.x, c.y)] * n
    return np.array(pts[:n], dtype=float)


def generate_d3(cfg: Config, rng: RNG, env: Environment, frame: Frame,
                events: list[Event], d2_states: dict, truths: dict[str, SpillTruth]):
    hc = cfg["hindcast"]
    dt_h = float(cfg["time"]["step_minutes"]) / 60.0
    n_part = int(hc["n_particles"])
    rec_every = float(hc["record_every_h"])
    half = float(hc["origin_window_half_h"])
    base_wdf = float(cfg["environment"]["wind_drift_factor"])
    base_diff = float(cfg["environment"]["diffusion_m2s"])

    prow: list[dict] = []
    hrow: list[dict] = []
    clouds: dict = {}
    best: dict = {}

    true_wdf = float(cfg["environment"]["wind_drift_factor"])

    for ev in events:
        states = d2_states[ev.event_id]
        observed = [s for s in states if s.state_type == "OBSERVED"]
        if not observed:
            continue
        first = observed[0]
        t_rel_est, t_obs = _estimate_release_time(states)
        g = rng.stream("d3", ev.event_id)

        # seed from the earliest observation only: the shorter the backtrack, the
        # less advection-model error accumulates
        seed_states = [first]
        seeds = [(first.t_h, _seed_in_polygon(first.polygon_km, n_part, g))]

        clouds[ev.event_id] = {}
        pooled_release: list[np.ndarray] = []
        for ens in range(int(hc["n_ensembles"])):
            hyp_id = f"{ev.event_id}-H{ens:02d}"
            eg = rng.stream("d3", ev.event_id, ens)
            deterministic = ens == 0
            params = DriftParams(
                wind_drift_factor=true_wdf if deterministic else
                float(base_wdf + eg.normal(0, hc["perturb"]["wind_drift_factor_std"])),
                diffusion_m2s=base_diff if deterministic else
                float(max(0.5, base_diff * (1.0 + eg.normal(0, hc["perturb"]["diffusion_rel_std"])))),
                forcing_noise_ms=0.0 if deterministic else float(hc["perturb"]["forcing_noise_ms"]),
            )
            t_rel = float(min(t_rel_est + (0.0 if deterministic else eg.normal(0.0, half * 0.5)),
                              t_obs - 1.0))

            ens_release = []
            for s_t, s_pts in seeds:
                span = max(s_t - t_rel, dt_h * 2)
                n_rec = max(2, int(span / rec_every) + 1)
                rec_times = s_t - np.linspace(0.0, span, n_rec)
                times, traj = integrate(env, s_pts, s_t, t_rel, dt_h, params, eg,
                                        record_times=rec_times)
                ens_release.append(traj[-1])
                if s_t == seeds[0][0]:
                    keep = eg.choice(traj.shape[1], min(80, traj.shape[1]), replace=False)
                    for ti, tt in enumerate(times):
                        sub = traj[ti][keep]
                        lon, lat = frame.to_lonlat(sub[:, 0], sub[:, 1])
                        for pj in range(len(sub)):
                            prow.append(dict(
                                event_id=ev.event_id, source_hypothesis_id=hyp_id,
                                ensemble_id=ens, particle_id=int(keep[pj]),
                                timestamp=cfg.iso(float(tt)), sim_hours=round(float(tt), 3),
                                backtracked_hours=round(float(s_t - tt), 3),
                                latitude=round(float(lat[pj]), 6), longitude=round(float(lon[pj]), 6),
                                wind_drift_factor=round(params.wind_drift_factor, 5),
                                diffusion_m2s=round(params.diffusion_m2s, 3),
                            ))
            source_cloud = np.vstack(ens_release)
            clouds[ev.event_id][hyp_id] = source_cloud
            pooled_release.append(source_cloud)
            if deterministic:
                det_cloud = source_cloud
                det_cen = source_cloud.mean(axis=0)
            cen = source_cloud.mean(axis=0)
            spread = float(np.sqrt(np.mean(np.sum((source_cloud - cen) ** 2, axis=1))))
            lon_c, lat_c = frame.to_lonlat(cen[0], cen[1])
            true_src = np.array([ev.x0_km, ev.y0_km])
            hrow.append(dict(
                event_id=ev.event_id, source_hypothesis_id=hyp_id, ensemble_id=ens,
                is_deterministic=deterministic,
                source_lat=round(float(lat_c), 6), source_lon=round(float(lon_c), 6),
                source_x_km=round(float(cen[0]), 4), source_y_km=round(float(cen[1]), 4),
                origin_time_start=cfg.iso(t_rel - half), origin_time_end=cfg.iso(t_rel + half),
                origin_time_mid=cfg.iso(t_rel), origin_time_mid_sim_h=round(t_rel, 3),
                first_observation_sim_h=round(float(t_obs), 3),
                backtracked_hours=round(float(t_obs - t_rel), 3),
                uncertainty_radius_km=round(spread, 3),
                wind_drift_factor=round(params.wind_drift_factor, 5),
                diffusion_m2s=round(params.diffusion_m2s, 3),
                seed_state_ids=";".join(s.observation_id for s in seed_states),
                qa_source_error_km=round(float(np.hypot(*(cen - true_src))), 3),
            ))

        # the working "best" hypothesis: the deterministic run's point estimate,
        # with uncertainty taken from the full ensemble's disagreement
        pooled = np.vstack(pooled_release)
        ens_cens = np.array([c.mean(axis=0) for c in pooled_release])
        pcen = det_cen
        pspread = float(max(
            np.sqrt(np.mean(np.sum((det_cloud - det_cen) ** 2, axis=1))),
            np.sqrt(np.mean(np.sum((ens_cens - ens_cens.mean(axis=0)) ** 2, axis=1)))))
        plon, plat = frame.to_lonlat(pcen[0], pcen[1])
        t_rel_best = float(min(t_rel_est, t_obs - 1.0))
        best_id = f"{ev.event_id}-HBEST"
        clouds[ev.event_id][best_id] = det_cloud
        best_row = dict(
            event_id=ev.event_id, source_hypothesis_id=best_id, ensemble_id=-1,
            is_deterministic=False, source_lat=round(float(plat), 6),
            source_lon=round(float(plon), 6), source_x_km=round(float(pcen[0]), 4),
            source_y_km=round(float(pcen[1]), 4),
            origin_time_start=cfg.iso(t_rel_best - half), origin_time_end=cfg.iso(t_rel_best + half),
            origin_time_mid=cfg.iso(t_rel_best), origin_time_mid_sim_h=round(t_rel_best, 3),
            first_observation_sim_h=round(float(t_obs), 3),
            backtracked_hours=round(float(t_obs - t_rel_best), 3),
            uncertainty_radius_km=round(pspread, 3),
            wind_drift_factor=round(true_wdf, 5), diffusion_m2s=round(base_diff, 3),
            seed_state_ids=";".join(s.observation_id for s in seed_states),
            qa_source_error_km=round(float(np.hypot(*(pcen - np.array([ev.x0_km, ev.y0_km])))), 3),
        )
        hrow.append(best_row)

        ev_hyps = [h for h in hrow if h["event_id"] == ev.event_id and h["ensemble_id"] >= 0]
        inv = np.array([1.0 / max(h["uncertainty_radius_km"], 1e-3) for h in ev_hyps])
        probs = inv / inv.sum()
        for h, p in zip(ev_hyps, probs):
            h["source_probability"] = round(float(p), 4)
        best_row["source_probability"] = 1.0
        best[ev.event_id] = best_row

    return D3Result(particles=pd.DataFrame(prow), hypotheses=pd.DataFrame(hrow),
                    source_clouds=clouds, best_hyp=best)
