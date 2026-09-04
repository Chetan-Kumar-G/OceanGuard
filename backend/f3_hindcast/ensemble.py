"""Lagrangian Ensemble Runner and Perturbation Engine for F3."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from shared.physics.lagrangian import (
    DriftPhysicsParams,
    Frame,
    integrate_particles,
    seed_particles_in_polygon,
)
from shared.schemas.f2_contract import TemporalSpillState
from backend.f3_hindcast.forcing import ForcingProvider


_AGE_MIN_H = 3.0
_AGE_MAX_H = 18.0
_AGE_FALLBACK_H = 8.0


@dataclass
class EnsembleConfig:
    """Hindcast ensemble and perturbation configuration."""
    n_ensembles: int = 6
    backtrack_hours: float = 72.0
    n_particles: int = 250
    record_every_h: float = 6.0
    dt_minutes: float = 10.0
    origin_window_half_h: float = 6.0
    wind_drift_factor_base: float = 0.032
    diffusion_m2s_base: float = 9.0
    # Perturbations
    wind_drift_factor_std: float = 0.01
    diffusion_rel_std: float = 0.4
    forcing_noise_ms: float = 0.6

    @classmethod
    def from_dict(cls, cfg: Dict[str, Any]) -> EnsembleConfig:
        hc = cfg.get("hindcast", {})
        env = cfg.get("environment", {})
        perturb = hc.get("perturb", {})
        time_cfg = cfg.get("time", {})

        return cls(
            n_ensembles=int(hc.get("n_ensembles", 6)),
            backtrack_hours=float(hc.get("backtrack_hours", 72.0)),
            n_particles=int(hc.get("n_particles", 250)),
            record_every_h=float(hc.get("record_every_h", 6.0)),
            dt_minutes=float(time_cfg.get("step_minutes", 10.0)),
            origin_window_half_h=float(hc.get("origin_window_half_h", 6.0)),
            wind_drift_factor_base=float(env.get("wind_drift_factor", 0.032)),
            diffusion_m2s_base=float(env.get("diffusion_m2s", 9.0)),
            wind_drift_factor_std=float(perturb.get("wind_drift_factor_std", 0.01)),
            diffusion_rel_std=float(perturb.get("diffusion_rel_std", 0.4)),
            forcing_noise_ms=float(perturb.get("forcing_noise_ms", 0.6)),
        )


@dataclass
class EnsembleRunResult:
    """Outputs of the Lagrangian ensemble hindcast."""
    clouds: Dict[int, np.ndarray]                     # ensemble_id -> backtracked (N, 2) positions in km
    release_times_h: Dict[int, float]                 # ensemble_id -> estimated release time (sim hours)
    t_obs_first_h: float                              # observation time of earliest seed (sim hours)
    t_obs_first_iso: str                              # observation ISO timestamp
    params_used: Dict[int, DriftPhysicsParams]        # ensemble_id -> parameters
    trajectories: List[Dict[str, Any]]                # Sampled particle trajectories for audit


def estimate_release_time(
    observed_states: List[TemporalSpillState],
    ref_sim_start_iso: Optional[str] = None
) -> Tuple[float, float]:
    """Estimates (t_release_est_h, t_obs_first_h) by back-extrapolating slick area growth.

    Uses a least-squares slope on earliest observed states to avoid ground-truth leakage.
    Falls back gracefully for single-observation events.
    """
    first_obs = observed_states[0]

    def to_epoch_hours(ts_str: str) -> float:
        clean = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean).timestamp() / 3600.0

    t0_epoch_h = to_epoch_hours(first_obs.timestamp)

    if len(observed_states) >= 2:
        head = observed_states[: min(5, len(observed_states))]
        t_offsets = np.array([to_epoch_hours(s.timestamp) - t0_epoch_h for s in head])
        areas = np.array([s.area_km2 for s in head])

        if len(t_offsets) >= 2 and np.max(t_offsets) > 0.0:
            slope, _ = np.polyfit(t_offsets, areas, 1)
            if slope <= 0.05:
                dt = np.diff(t_offsets)
                da = np.diff(areas)
                valid = dt > 1e-4
                rates = da[valid] / dt[valid]
                pos_rates = rates[rates > 0]
                slope = float(np.median(pos_rates)) if len(pos_rates) > 0 else 0.0
            a0 = max(areas[0], 0.1)
            age = a0 / slope if slope > 0.05 else _AGE_FALLBACK_H
        else:
            age = _AGE_FALLBACK_H
    else:
        age = _AGE_FALLBACK_H

    age_clipped = float(np.clip(age, _AGE_MIN_H, _AGE_MAX_H))
    return t0_epoch_h - age_clipped, t0_epoch_h


def run_hindcast_ensemble(
    seed_states: List[TemporalSpillState],
    forcing_provider: ForcingProvider,
    frame: Frame,
    config: EnsembleConfig,
    base_seed: int = 42
) -> EnsembleRunResult:
    """Executes multi-ensemble backward Lagrangian particle tracking.

    Seeds particles in earliest observed state, perturbs physical parameters,
    and runs reverse-time integration to candidate origin times.
    """
    if not seed_states:
        raise ValueError("Cannot run hindcast: seed_states list is empty.")

    first_state = seed_states[0]
    t_rel_epoch_h, t_obs_epoch_h = estimate_release_time(seed_states)
    dt_h = config.dt_minutes / 60.0

    # Seed particles inside the first observed polygon
    rng_master = np.random.default_rng(base_seed)
    seed_polygon = first_state.polygon_geojson.coordinates[0]
    # Convert polygon coords (lon, lat) to local km frame
    poly_lons = [pt[0] for pt in seed_polygon]
    poly_lats = [pt[1] for pt in seed_polygon]
    poly_x_km, poly_y_km = frame.to_km(poly_lons, poly_lats)
    poly_km_coords = np.column_stack([poly_x_km, poly_y_km])

    initial_particles_km = seed_particles_in_polygon(
        poly_coords=poly_km_coords,
        n_particles=config.n_particles,
        rng=rng_master
    )

    def forcing_wrapper(x_km, y_km, t_h):
        lons, lats = frame.to_lonlat(x_km, y_km)
        return forcing_provider.get_forcing(lons, lats, t_h)

    clouds: Dict[int, np.ndarray] = {}
    release_times: Dict[int, float] = {}
    params_dict: Dict[int, DriftPhysicsParams] = {}
    trajectories: List[Dict[str, Any]] = []

    for ens_id in range(config.n_ensembles):
        ens_rng = np.random.default_rng(base_seed + 1000 + ens_id)
        deterministic = (ens_id == 0)

        if deterministic:
            wdf = config.wind_drift_factor_base
            diff = config.diffusion_m2s_base
            noise = 0.0
            t_rel_h = t_rel_epoch_h
        else:
            wdf = float(config.wind_drift_factor_base + ens_rng.normal(0, config.wind_drift_factor_std))
            diff = float(max(0.5, config.diffusion_m2s_base * (1.0 + ens_rng.normal(0, config.diffusion_rel_std))))
            noise = float(config.forcing_noise_ms)
            jitter_h = float(ens_rng.normal(0.0, config.origin_window_half_h * 0.5))
            t_rel_h = min(t_rel_epoch_h + jitter_h, t_obs_epoch_h - 1.0)

        params = DriftPhysicsParams(
            wind_drift_factor=wdf,
            diffusion_m2s=diff,
            forcing_noise_ms=noise
        )
        params_dict[ens_id] = params
        release_times[ens_id] = t_rel_h

        # Setup recording times
        span_h = max(t_obs_epoch_h - t_rel_h, dt_h * 2)
        n_rec = max(2, int(span_h / config.record_every_h) + 1)
        rec_times = t_obs_epoch_h - np.linspace(0.0, span_h, n_rec)

        times_rec, traj = integrate_particles(
            pos0_km=initial_particles_km,
            t0_h=t_obs_epoch_h,
            t1_h=t_rel_h,
            dt_h=dt_h,
            forcing_func=forcing_wrapper,
            params=params,
            rng=ens_rng,
            record_times=rec_times
        )

        final_cloud = traj[-1]
        clouds[ens_id] = final_cloud

        # Audit sample of particles (up to 50 particles)
        sample_indices = ens_rng.choice(traj.shape[1], min(50, traj.shape[1]), replace=False)
        for ti, tt in enumerate(times_rec):
            sub_pos = traj[ti][sample_indices]
            sub_lons, sub_lats = frame.to_lonlat(sub_pos[:, 0], sub_pos[:, 1])
            for pj in range(len(sub_pos)):
                trajectories.append({
                    "event_id": first_state.event_id,
                    "ensemble_id": ens_id,
                    "particle_id": int(sample_indices[pj]),
                    "sim_hours": round(float(tt), 3),
                    "backtracked_hours": round(float(t_obs_epoch_h - tt), 3),
                    "latitude": round(float(sub_lats[pj]), 6),
                    "longitude": round(float(sub_lons[pj]), 6),
                    "wind_drift_factor": round(wdf, 5),
                    "diffusion_m2s": round(diff, 3),
                })

    return EnsembleRunResult(
        clouds=clouds,
        release_times_h=release_times,
        t_obs_first_h=t_obs_epoch_h,
        t_obs_first_iso=first_state.timestamp,
        params_used=params_dict,
        trajectories=trajectories
    )
