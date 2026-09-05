"""Forward Lagrangian ensemble for F8.

Seeds particles inside the latest confirmed slick polygon and integrates them
*forward* under a perturbed ensemble. Per-member perturbations (wind-drift
factor, diffusion, forcing noise) and forcing noise that grows with lead time
give a spreading cloud whose footprint is the forecast envelope.

Ported in spirit from ``data/raw/synthetic/oceanguard_synth/d8_replay.py`` but
running in epoch-hours on the shared physics engine + F3 forcing field.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from shared.physics.lagrangian import (
    DriftPhysicsParams,
    Frame,
    integrate_particles,
    seed_particles_in_polygon,
)
from backend.f8_forecast.forcing import ForcingProvider
from backend.f8_forecast.geometry import centroid_km, ensemble_spread_km


@dataclass
class ForwardEnsembleConfig:
    """Forward-forecast ensemble configuration (defaults mirror the reference ``replay`` block)."""
    horizons_h: List[float] = field(default_factory=lambda: [12.0, 24.0, 48.0, 72.0])
    n_ensemble: int = 40
    n_particles: int = 300
    dt_minutes: float = 30.0
    wind_drift_factor_base: float = 0.032
    diffusion_m2s_base: float = 9.0
    wind_drift_factor_std: float = 0.011
    diffusion_rel_std: float = 0.4
    forcing_noise_growth_ms_per_h: float = 0.03
    slick_buffer_km: float = 0.45

    @classmethod
    def from_dict(cls, cfg: Dict[str, Any], *, overrides: Optional[Dict[str, Any]] = None) -> "ForwardEnsembleConfig":
        rp = cfg.get("replay", {}) or {}
        env = cfg.get("environment", {}) or {}
        tm = cfg.get("time", {}) or {}
        spill = cfg.get("spill", {}) or {}
        out = cls(
            horizons_h=[float(x) for x in rp.get("horizons_h", [12, 24, 48, 72])],
            n_ensemble=int(rp.get("n_ensemble", 40)),
            n_particles=300,
            dt_minutes=float(tm.get("step_minutes", 30.0)),
            wind_drift_factor_base=float(env.get("wind_drift_factor", 0.032)),
            diffusion_m2s_base=float(env.get("diffusion_m2s", 9.0)),
            forcing_noise_growth_ms_per_h=float(rp.get("forcing_noise_growth_ms_per_h", 0.03)),
            slick_buffer_km=float(spill.get("slick_buffer_km", 0.45)),
        )
        for k, v in (overrides or {}).items():
            if v is not None and hasattr(out, k):
                setattr(out, k, v)
        return out


@dataclass
class HorizonResult:
    horizon_h: float
    pooled_cloud_km: np.ndarray            # (M*N, 2) all member particles at this horizon
    member_centroids_km: List[np.ndarray]  # per-member centroid (2,)
    mean_centroid_km: np.ndarray           # (2,)
    spread_km: float


@dataclass
class ForwardEnsembleResult:
    event_id: str
    forecast_id: str
    t0_sim_h: float
    t0_iso: str
    horizons: List[HorizonResult]
    sampled_particles: List[Dict[str, Any]]   # audit sample: forecast particle rows (lon/lat)
    n_ensemble: int


def run_forward_ensemble(
    *,
    event_id: str,
    forecast_id: str,
    seed_polygon_lonlat: List[List[float]],
    t0_iso: str,
    t0_sim_h: float,
    frame: Frame,
    forcing_provider: ForcingProvider,
    config: ForwardEnsembleConfig,
    base_seed: int = 42,
    audit_members: int = 8,
    audit_particles_per_member: int = 40,
) -> ForwardEnsembleResult:
    """Run the perturbed forward ensemble and return per-horizon particle clouds.

    ``t0_sim_h`` is the simulation-hours clock the synthetic forcing field is
    defined on (F2 ``sim_hours``); integration and forcing sampling both use it.
    """
    horizons = sorted(float(h) for h in config.horizons_h)
    if not horizons:
        raise ValueError("run_forward_ensemble: no forecast horizons requested")
    hmax = horizons[-1]
    dt_h = config.dt_minutes / 60.0
    t0_epoch_h = float(t0_sim_h)

    # Seed particles inside the confirmed slick polygon (converted to km frame).
    lons = [pt[0] for pt in seed_polygon_lonlat]
    lats = [pt[1] for pt in seed_polygon_lonlat]
    px, py = frame.to_km(lons, lats)
    poly_km = np.column_stack([px, py])
    master_rng = np.random.default_rng(base_seed)
    seed_km = seed_particles_in_polygon(poly_km, config.n_particles, master_rng)

    def forcing_wrapper(x_km, y_km, t_h):
        lo, la = frame.to_lonlat(x_km, y_km)
        return forcing_provider.get_forcing(lo, la, t_h)

    rec_times = t0_epoch_h + np.array(horizons)
    member_clouds: Dict[float, List[np.ndarray]] = {h: [] for h in horizons}
    member_centroids: Dict[float, List[np.ndarray]] = {h: [] for h in horizons}
    sampled: List[Dict[str, Any]] = []

    for m in range(config.n_ensemble):
        mrng = np.random.default_rng(base_seed + 1000 + m)
        params = DriftPhysicsParams(
            wind_drift_factor=float(config.wind_drift_factor_base + mrng.normal(0.0, config.wind_drift_factor_std)),
            diffusion_m2s=float(max(0.5, config.diffusion_m2s_base * (1.0 + mrng.normal(0.0, config.diffusion_rel_std)))),
            forcing_noise_ms=float(config.forcing_noise_growth_ms_per_h * hmax),
        )
        _times, traj = integrate_particles(
            pos0_km=seed_km,
            t0_h=t0_epoch_h,
            t1_h=t0_epoch_h + hmax,
            dt_h=dt_h,
            forcing_func=forcing_wrapper,
            params=params,
            rng=mrng,
            record_times=rec_times,
        )
        for hi, h in enumerate(horizons):
            cloud = traj[hi]
            member_clouds[h].append(cloud)
            member_centroids[h].append(centroid_km(cloud))
            if m < audit_members:
                k = min(audit_particles_per_member, len(cloud))
                sub = cloud[mrng.choice(len(cloud), k, replace=False)]
                lo, la = frame.to_lonlat(sub[:, 0], sub[:, 1])
                for j in range(len(sub)):
                    sampled.append({
                        "event_id": event_id,
                        "forecast_id": forecast_id,
                        "forecast_horizon_hours": h,
                        "ensemble_member": m,
                        "timestamp": _iso_add_hours(t0_iso, h),
                        "particle": {"lat": round(float(la[j]), 6), "lon": round(float(lo[j]), 6)},
                    })

    horizon_results: List[HorizonResult] = []
    poly_rng = np.random.default_rng(base_seed + 7)
    for h in horizons:
        pooled = np.vstack(member_clouds[h])
        # Cap the cloud used for polygonisation - GEOS buffer cost is superlinear
        # and 600 points already resolve the footprint (matches the reference generator).
        if len(pooled) > 600:
            pooled = pooled[poly_rng.choice(len(pooled), 600, replace=False)]
        cens = member_centroids[h]
        mean_cen = np.asarray(cens, dtype=float).mean(axis=0)
        horizon_results.append(HorizonResult(
            horizon_h=h,
            pooled_cloud_km=pooled,
            member_centroids_km=cens,
            mean_centroid_km=mean_cen,
            spread_km=ensemble_spread_km(cens),
        ))

    return ForwardEnsembleResult(
        event_id=event_id,
        forecast_id=forecast_id,
        t0_sim_h=t0_epoch_h,
        t0_iso=t0_iso,
        horizons=horizon_results,
        sampled_particles=sampled,
        n_ensemble=config.n_ensemble,
    )


def _iso_add_hours(ts_iso: str, hours: float) -> str:
    from datetime import datetime, timedelta, timezone

    dt = datetime.fromisoformat(str(ts_iso).replace("Z", "+00:00"))
    dt = (dt + timedelta(hours=float(hours))).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
