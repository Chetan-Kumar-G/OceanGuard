"""D8 - historical replay / forecast dataset (derived).

At a chosen T0 (the k-th observation of an event) the slick is propagated forward
with an ensemble under forecast-quality forcing (true forcing plus an error that
grows with lead time). The forecast tables contain **no future information**.

A separate evaluation table (``D8_evaluation.csv``) matches each forecast horizon
to the nearest *later* real observation and is the only place the future truth
appears - it is for scoring, never for training a forecaster.

Outputs:
  * D8_forecast_runs      - one row per (event, horizon): predicted slick + risk
  * D8_forecast_particles - sampled predicted particle positions
  * D8_evaluation         - eval-only: predicted vs observed future
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from shapely.geometry import Point

from .config import Config
from .drift import DriftParams, integrate
from .environment import Environment
from .events import Event
from .geo import Frame, points_to_slick, safe_iou
from .rng import RNG


def _coast_distance(cfg: Config, cx: float, cy: float) -> float:
    edge = cfg["geography"]["coast_edge"]
    w = float(cfg["aoi"]["width_km"])
    h = float(cfg["aoi"]["height_km"])
    return {"south": cy, "north": h - cy, "west": cx, "east": w - cx}.get(edge, cy)


def _zone_distance(cfg: Config, cx: float, cy: float):
    best_d, best_name = 9e9, ""
    for z in cfg["geography"]["sensitive_zones"]:
        d = float(np.hypot(cx - z["x_km"], cy - z["y_km"]) - z["radius_km"])
        if d < best_d:
            best_d, best_name = d, z["name"]
    return max(best_d, 0.0), best_name


def generate_d8(cfg: Config, rng: RNG, env: Environment, frame: Frame,
                events: list[Event], d2_states: dict):
    rp = cfg["replay"]
    dt_h = float(cfg["time"]["step_minutes"]) / 60.0
    horizons = [float(x) for x in rp["horizons_h"]]
    hmax = max(horizons)
    n_ens = int(rp["n_ensemble"])
    base_wdf = float(cfg["environment"]["wind_drift_factor"])
    base_diff = float(cfg["environment"]["diffusion_m2s"])
    noise_growth = float(rp["forcing_noise_growth_ms_per_h"])
    tol = float(rp["match_tolerance_h"])

    runs: list[dict] = []
    parts: list[dict] = []
    evals: list[dict] = []

    for ev in events:
        observed = [s for s in d2_states[ev.event_id] if s.state_type == "OBSERVED"]
        if len(observed) < int(rp["min_observations"]):
            continue
        k = min(int(rp["t0_observation_index"]), len(observed) - 2)
        t0 = observed[k]
        forecast_id = f"{ev.event_id}-FC{k:02d}"
        g = rng.stream("d8", ev.event_id)

        n_seed = 300
        minx, miny, maxx, maxy = t0.polygon_km.bounds
        seed = []
        while len(seed) < n_seed:
            xs = g.uniform(minx, maxx, n_seed)
            ys = g.uniform(miny, maxy, n_seed)
            for x, y in zip(xs, ys):
                if t0.polygon_km.contains(Point(x, y)):
                    seed.append((x, y))
        seed = np.array(seed[:n_seed])

        member_final = {h: [] for h in horizons}     # per-horizon list of member centroids
        pooled = {h: [] for h in horizons}
        for m in range(n_ens):
            mg = rng.stream("d8", ev.event_id, m)
            params = DriftParams(
                wind_drift_factor=float(base_wdf + mg.normal(0, 0.011)),
                diffusion_m2s=float(max(0.5, base_diff * (1 + mg.normal(0, 0.4)))),
                forcing_noise_ms=float(noise_growth * hmax),
            )
            rec_times = t0.t_h + np.array(horizons)
            times, traj = integrate(env, seed, t0.t_h, t0.t_h + hmax, dt_h, params, mg,
                                    record_times=rec_times)
            for hi, h in enumerate(horizons):
                cloud = traj[hi]
                member_final[h].append(cloud.mean(axis=0))
                pooled[h].append(cloud)
                if m < 8:
                    sub = cloud[mg.choice(len(cloud), 40, replace=False)]
                    lon, lat = frame.to_lonlat(sub[:, 0], sub[:, 1])
                    for pj in range(len(sub)):
                        parts.append(dict(
                            event_id=ev.event_id, forecast_id=forecast_id,
                            forecast_horizon_hours=h, ensemble_member=m,
                            timestamp=cfg.iso(float(t0.t_h + h)),
                            particle_lat=round(float(lat[pj]), 6),
                            particle_lon=round(float(lon[pj]), 6),
                        ))

        for h in horizons:
            allp = np.vstack(pooled[h])
            cens = np.array(member_final[h])
            mean_cen = cens.mean(axis=0)
            spread = float(np.sqrt(np.mean(np.sum((cens - mean_cen) ** 2, axis=1))))
            samp = allp[g.choice(len(allp), min(800, len(allp)), replace=False)]
            pred_poly = points_to_slick(samp, cfg["spill"]["slick_buffer_km"])
            # forecast envelope: the whole ensemble footprint, generously buffered.
            # Used for envelope-style verification (does the later obs fall inside?).
            env_buf = float(max(2.0, spread))
            envelope_poly = points_to_slick(samp, env_buf)
            if envelope_poly.is_empty:
                envelope_poly = pred_poly.buffer(env_buf)
            cx, cy = float(mean_cen[0]), float(mean_cen[1])
            lon_c, lat_c = frame.to_lonlat(cx, cy)
            coast_d = _coast_distance(cfg, cx, cy)
            zone_d, zone_name = _zone_distance(cfg, cx, cy)
            conf = float(np.exp(-spread / 15.0) * np.exp(-h / 96.0))

            runs.append(dict(
                event_id=ev.event_id, forecast_id=forecast_id,
                initial_observation_id=t0.observation_id,
                initial_timestamp=cfg.iso(t0.t_h), initial_sim_hours=round(t0.t_h, 3),
                initial_centroid_lat=round(float(frame.to_lonlat(t0.centroid[0], t0.centroid[1])[1]), 6),
                initial_centroid_lon=round(float(frame.to_lonlat(t0.centroid[0], t0.centroid[1])[0]), 6),
                initial_area_km2=round(float(t0.area_km2), 4),
                forecast_horizon_hours=h,
                valid_timestamp=cfg.iso(t0.t_h + h),
                n_ensemble=n_ens,
                predicted_centroid_lat=round(float(lat_c), 6),
                predicted_centroid_lon=round(float(lon_c), 6),
                predicted_polygon_wkt=frame.polygon_to_wkt(pred_poly),
                predicted_area_km2=round(float(pred_poly.area), 4),
                forecast_envelope_wkt=frame.polygon_to_wkt(envelope_poly),
                forecast_envelope_area_km2=round(float(envelope_poly.area), 4),
                ensemble_spread_km=round(spread, 4),
                forecast_confidence=round(conf, 4),
                coastline_distance_km=round(float(coast_d), 3),
                nearest_sensitive_zone=zone_name,
                sensitive_zone_distance_km=round(float(zone_d), 3),
                beaching_risk=bool(coast_d < spread * 2.0),
            ))

            # ---- eval-only: compare against the nearest real later observation ----
            target_t = t0.t_h + h
            later = [s for s in observed if s.t_h > t0.t_h + 1.0]
            match = min(later, key=lambda s: abs(s.t_h - target_t), default=None)
            if match is not None and abs(match.t_h - target_t) <= tol:
                traj_err = float(np.hypot(*(mean_cen - match.centroid)))
                cover = safe_iou(pred_poly, match.polygon_km)
                obs_area = float(match.polygon_km.area)
                in_env = (float(match.polygon_km.intersection(envelope_poly).area) / obs_area
                          if obs_area > 0 else 0.0)
                centroid_in_env = bool(envelope_poly.contains(
                    Point(float(match.centroid[0]), float(match.centroid[1]))))
                # calibration: forecast error relative to the ensemble's own stated
                # spread. ~1 = well calibrated, >>1 = over-confident, <<1 = over-dispersed.
                calib_ratio = float(traj_err / max(spread, 1e-6))
                well_calibrated = bool(0.5 <= calib_ratio <= 2.0)
                evals.append(dict(
                    event_id=ev.event_id, forecast_id=forecast_id,
                    forecast_horizon_hours=h,
                    valid_timestamp=cfg.iso(target_t),
                    matched_observation_id=match.observation_id,
                    matched_timestamp=cfg.iso(match.t_h),
                    match_offset_hours=round(float(match.t_h - target_t), 3),
                    predicted_centroid_lat=round(float(lat_c), 6),
                    predicted_centroid_lon=round(float(lon_c), 6),
                    observed_future_polygon_wkt=frame.polygon_to_wkt(match.polygon_km),
                    observed_centroid_lat=round(float(frame.to_lonlat(match.centroid[0], match.centroid[1])[1]), 6),
                    observed_centroid_lon=round(float(frame.to_lonlat(match.centroid[0], match.centroid[1])[0]), 6),
                    trajectory_error_km=round(traj_err, 4),
                    observed_region_coverage_iou=round(float(cover), 4),
                    observed_in_forecast_envelope_frac=round(float(np.clip(in_env, 0, 1)), 4),
                    observed_centroid_in_envelope=centroid_in_env,
                    calibration_ratio=round(calib_ratio, 4),
                    well_calibrated=well_calibrated,
                ))

    return (pd.DataFrame(runs), pd.DataFrame(parts), pd.DataFrame(evals))
