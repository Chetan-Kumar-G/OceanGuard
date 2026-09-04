"""Particle advection + random-walk diffusion, forward and backward in time."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .environment import Environment

_MS_TO_KMH = 3.6


@dataclass
class DriftParams:
    wind_drift_factor: float
    diffusion_m2s: float
    forcing_noise_ms: float = 0.0


def velocity_kmh(env: Environment, pos_km: np.ndarray, t_h: float,
                 params: DriftParams, rng: np.random.Generator | None = None):
    uc, vc = env.current_at(pos_km[:, 0], pos_km[:, 1], t_h)
    uw, vw = env.wind_at(pos_km[:, 0], pos_km[:, 1], t_h)
    uc = np.asarray(uc, dtype=float)
    vc = np.asarray(vc, dtype=float)
    uw = np.asarray(uw, dtype=float)
    vw = np.asarray(vw, dtype=float)
    if params.forcing_noise_ms and rng is not None:
        n = params.forcing_noise_ms
        uc = uc + rng.normal(0.0, n, uc.shape)
        vc = vc + rng.normal(0.0, n, vc.shape)
        uw = uw + rng.normal(0.0, n, uw.shape)
        vw = vw + rng.normal(0.0, n, vw.shape)
    vx = (uc + params.wind_drift_factor * uw) * _MS_TO_KMH
    vy = (vc + params.wind_drift_factor * vw) * _MS_TO_KMH
    return vx, vy


def step(env: Environment, pos_km: np.ndarray, t_h: float, dt_h: float,
         params: DriftParams, rng: np.random.Generator, backward: bool = False):
    vx, vy = velocity_kmh(env, pos_km, t_h, params, rng)
    sign = -1.0 if backward else 1.0
    dt_s = abs(dt_h) * 3600.0
    sigma_km = np.sqrt(2.0 * params.diffusion_m2s * dt_s) / 1000.0
    out = np.empty_like(pos_km)
    out[:, 0] = pos_km[:, 0] + sign * vx * dt_h + rng.normal(0.0, sigma_km, len(pos_km))
    out[:, 1] = pos_km[:, 1] + sign * vy * dt_h + rng.normal(0.0, sigma_km, len(pos_km))
    return out


def integrate(env: Environment, pos0_km: np.ndarray, t0_h: float, t1_h: float,
              dt_h: float, params: DriftParams, rng: np.random.Generator,
              record_times: np.ndarray | None = None):
    """Integrate a cloud from t0 to t1. Returns (times, positions[T, N, 2]).

    Works forward (t1 > t0) or backward (t1 < t0).
    """
    backward = t1_h < t0_h
    step_h = -abs(dt_h) if backward else abs(dt_h)
    n_steps = max(1, int(round(abs(t1_h - t0_h) / abs(dt_h))))
    pos = pos0_km.astype(float).copy()
    t = float(t0_h)
    want = None if record_times is None else list(np.atleast_1d(record_times))
    rec_t, rec_p = [t], [pos.copy()]
    for _ in range(n_steps):
        pos = step(env, pos, t, step_h, params, rng, backward=backward)
        t += step_h
        rec_t.append(t)
        rec_p.append(pos.copy())
    times = np.array(rec_t)
    stack = np.stack(rec_p, axis=0)
    if want is None:
        return times, stack
    idx = [int(np.argmin(np.abs(times - wt))) for wt in want]
    return times[idx], stack[idx]
