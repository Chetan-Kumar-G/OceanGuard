"""Reusable Lagrangian Particle Tracking Physics Engine.

Designed for backward hindcasting (F3) and forward forecasting (F8).
Supports:
- Surface ocean current advection
- Wind leeway advection (wind_drift_factor)
- Brownian random-walk diffusion
- Forward and backward numerical time integration
- Coordinate transformations (WGS84 EPSG:4326 <-> local tangent-plane metric frame)
- Pure Python/NumPy polygon seeding without external C-library dependencies
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union
import numpy as np

_MS_TO_KMH = 3.6
_KM_PER_DEG_LAT = 111.32


@dataclass(frozen=True)
class Frame:
    """Local tangent-plane metric coordinate frame referenced to an AOI origin."""
    ref_lat: float
    ref_lon: float

    @property
    def km_per_deg_lon(self) -> float:
        return _KM_PER_DEG_LAT * math.cos(math.radians(self.ref_lat))

    def to_lonlat(self, x_km: Union[float, np.ndarray], y_km: Union[float, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """Converts local metric coordinates (x_km, y_km) to WGS84 (lon, lat)."""
        lon = self.ref_lon + np.asarray(x_km, dtype=float) / self.km_per_deg_lon
        lat = self.ref_lat + np.asarray(y_km, dtype=float) / _KM_PER_DEG_LAT
        return lon, lat

    def to_km(self, lon: Union[float, np.ndarray], lat: Union[float, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """Converts WGS84 (lon, lat) to local metric coordinates (x_km, y_km)."""
        x = (np.asarray(lon, dtype=float) - self.ref_lon) * self.km_per_deg_lon
        y = (np.asarray(lat, dtype=float) - self.ref_lat) * _KM_PER_DEG_LAT
        return x, y


@dataclass
class DriftPhysicsParams:
    """Parameters governing Lagrangian drift and diffusion."""
    wind_drift_factor: float = 0.032    # 3.2% standard leeway factor
    diffusion_m2s: float = 9.0          # Horizontal eddy diffusivity (m²/s)
    forcing_noise_ms: float = 0.0       # Perturbation standard deviation on forcing (m/s)


def point_in_polygon(x: float, y: float, poly_ring: Sequence[Sequence[float]]) -> bool:
    """Ray-casting algorithm to test if (x, y) is inside a closed polygon ring.

    poly_ring: sequence of [x, y] or [lon, lat] coordinates.
    """
    n = len(poly_ring)
    if n < 3:
        return False
    inside = False
    p1x, p1y = poly_ring[0]
    for i in range(1, n + 1):
        p2x, p2y = poly_ring[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def seed_particles_in_polygon(
    poly_coords: Sequence[Sequence[float]],
    n_particles: int,
    rng: np.random.Generator
) -> np.ndarray:
    """Rejection-samples n_particles strictly inside the given 2D polygon coordinates.

    poly_coords: [[x, y], ...] or [[lon, lat], ...]
    Returns:
        (N, 2) numpy array of particle positions.
    """
    pts = np.asarray(poly_coords, dtype=float)
    minx, miny = np.min(pts, axis=0)
    maxx, maxy = np.max(pts, axis=0)
    centroid = np.mean(pts, axis=0)

    sampled: List[Tuple[float, float]] = []
    batch_size = max(n_particles * 2, 50)
    max_trials = n_particles * 200
    trials = 0

    while len(sampled) < n_particles and trials < max_trials:
        xs = rng.uniform(minx, maxx, batch_size)
        ys = rng.uniform(miny, maxy, batch_size)
        for x, y in zip(xs, ys):
            if point_in_polygon(x, y, pts):
                sampled.append((float(x), float(y)))
                if len(sampled) >= n_particles:
                    break
        trials += batch_size

    # Fallback to centroid if polygon is too thin or rejection budget reached
    if len(sampled) < n_particles:
        needed = n_particles - len(sampled)
        for _ in range(needed):
            sampled.append((float(centroid[0]), float(centroid[1])))

    return np.array(sampled[:n_particles], dtype=float)


def compute_advection_velocity_kmh(
    pos_km: np.ndarray,
    t_h: float,
    forcing_func: Callable[[np.ndarray, np.ndarray, float], Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    params: DriftPhysicsParams,
    rng: Optional[np.random.Generator] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """Computes instantaneous slick advection velocity in km/h for particle positions pos_km.

    forcing_func(x_km, y_km, t_h) -> (u_current_ms, v_current_ms, u_wind_ms, v_wind_ms)
    """
    uc, vc, uw, vw = forcing_func(pos_km[:, 0], pos_km[:, 1], t_h)
    uc = np.asarray(uc, dtype=float)
    vc = np.asarray(vc, dtype=float)
    uw = np.asarray(uw, dtype=float)
    vw = np.asarray(vw, dtype=float)

    if params.forcing_noise_ms > 0.0 and rng is not None:
        noise = params.forcing_noise_ms
        uc = uc + rng.normal(0.0, noise, uc.shape)
        vc = vc + rng.normal(0.0, noise, vc.shape)
        uw = uw + rng.normal(0.0, noise, uw.shape)
        vw = vw + rng.normal(0.0, noise, vw.shape)

    vx_kmh = (uc + params.wind_drift_factor * uw) * _MS_TO_KMH
    vy_kmh = (vc + params.wind_drift_factor * vw) * _MS_TO_KMH
    return vx_kmh, vy_kmh


def lagrangian_step(
    pos_km: np.ndarray,
    t_h: float,
    dt_h: float,
    forcing_func: Callable[[np.ndarray, np.ndarray, float], Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    params: DriftPhysicsParams,
    rng: np.random.Generator,
    backward: bool = False
) -> np.ndarray:
    """Advances particle positions by time step dt_h (hours) using 2nd-order midpoint integration.

    Advection velocity is evaluated at the interval midpoint t_h + 0.5 * step_h for
    time-reversible numerical symmetry.
    Brownian diffusion is added based on horizontal diffusion coefficient:
        sigma_km = sqrt(2 * D * dt_sec) / 1000.0
    """
    sign = -1.0 if backward else 1.0
    abs_dt = abs(dt_h)
    step_h = -abs_dt if backward else abs_dt
    t_mid = t_h + 0.5 * step_h

    # 1. Predictor step to midpoint position
    v_pred_x, v_pred_y = compute_advection_velocity_kmh(pos_km, t_h, forcing_func, params, rng=None)
    pos_mid = np.empty_like(pos_km)
    pos_mid[:, 0] = pos_km[:, 0] + sign * v_pred_x * (0.5 * abs_dt)
    pos_mid[:, 1] = pos_km[:, 1] + sign * v_pred_y * (0.5 * abs_dt)

    # 2. Corrector step evaluated at midpoint in time and space
    vx_kmh, vy_kmh = compute_advection_velocity_kmh(pos_mid, t_mid, forcing_func, params, rng)

    dt_sec = abs_dt * 3600.0
    out = np.empty_like(pos_km)
    if params.diffusion_m2s > 0.0:
        sigma_km = np.sqrt(2.0 * params.diffusion_m2s * dt_sec) / 1000.0
        diff_x = rng.normal(0.0, sigma_km, len(pos_km))
        diff_y = rng.normal(0.0, sigma_km, len(pos_km))
    else:
        diff_x = 0.0
        diff_y = 0.0

    out[:, 0] = pos_km[:, 0] + sign * vx_kmh * abs_dt + diff_x
    out[:, 1] = pos_km[:, 1] + sign * vy_kmh * abs_dt + diff_y
    return out


def integrate_particles(
    pos0_km: np.ndarray,
    t0_h: float,
    t1_h: float,
    dt_h: float,
    forcing_func: Callable[[np.ndarray, np.ndarray, float], Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    params: DriftPhysicsParams,
    rng: np.random.Generator,
    record_times: Optional[Sequence[float]] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """Integrates particle trajectory from t0_h to t1_h.

    Works forward (t1_h > t0_h) or backward (t1_h < t0_h).
    Returns:
        times: 1D numpy array of timestamps (hours)
        positions: 3D numpy array of shape [T, N, 2] in local km
    """
    backward = t1_h < t0_h
    abs_dt = abs(dt_h)
    step_h = -abs_dt if backward else abs_dt
    n_steps = max(1, int(round(abs(t1_h - t0_h) / abs_dt)))

    pos = pos0_km.astype(float).copy()
    t = float(t0_h)

    want_times = None if record_times is None else list(np.atleast_1d(record_times))
    rec_t = [t]
    rec_p = [pos.copy()]

    for _ in range(n_steps):
        pos = lagrangian_step(pos, t, abs_dt, forcing_func, params, rng, backward=backward)
        t += step_h
        rec_t.append(t)
        rec_p.append(pos.copy())

    times_arr = np.array(rec_t)
    stack_arr = np.stack(rec_p, axis=0)

    if want_times is None:
        return times_arr, stack_arr

    indices = [int(np.argmin(np.abs(times_arr - wt))) for wt in want_times]
    return times_arr[indices], stack_arr[indices]
