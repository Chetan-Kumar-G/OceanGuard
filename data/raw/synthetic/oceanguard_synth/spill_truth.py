"""Forward simulation of the ground-truth slick for one event.

Produces the true particle cloud through time and a helper to read off the true
slick polygon at any requested timestamp. This is the hidden reality the
satellite (D1) samples imperfectly and the hindcast (D3) tries to invert.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon

from .config import Config
from .drift import DriftParams, step as drift_step
from .environment import Environment
from .events import Event
from .geo import points_to_slick
from .rng import RNG


@dataclass
class SpillTruth:
    event: Event
    times_h: np.ndarray            # (T,)
    positions: np.ndarray          # (T, N, 2) km
    buffer_km: float
    poly_particles: int

    def cloud_at(self, t_h: float) -> np.ndarray:
        i = int(np.argmin(np.abs(self.times_h - t_h)))
        return self.positions[i]

    def polygon_at(self, t_h: float, rng: np.random.Generator | None = None) -> Polygon:
        cloud = self.cloud_at(t_h)
        if len(cloud) > self.poly_particles:
            if rng is None:
                idx = np.linspace(0, len(cloud) - 1, self.poly_particles).astype(int)
            else:
                idx = rng.choice(len(cloud), self.poly_particles, replace=False)
            cloud = cloud[idx]
        return points_to_slick(cloud, self.buffer_km)

    def centroid_at(self, t_h: float) -> np.ndarray:
        return self.cloud_at(t_h).mean(axis=0)


def simulate_truth(cfg: Config, rng: RNG, env: Environment, event: Event) -> SpillTruth:
    g = rng.stream("truth", event.event_id)
    n = int(cfg["spill"]["n_particles"])
    dt_h = float(cfg["time"]["step_minutes"]) / 60.0
    r0 = float(cfg["spill"]["initial_radius_km"])

    # seed particles: continuous release smeared over release_hours
    ang = g.uniform(0, 2 * np.pi, n)
    rad = r0 * np.sqrt(g.uniform(0, 1, n))
    p0 = np.column_stack([event.x0_km + rad * np.cos(ang),
                          event.y0_km + rad * np.sin(ang)])
    birth = event.t0_h + g.uniform(0.0, event.release_hours, n)

    params = DriftParams(
        wind_drift_factor=float(cfg["environment"]["wind_drift_factor"]),
        diffusion_m2s=float(cfg["environment"]["diffusion_m2s"]),
    )

    t_end = event.t0_h + float(cfg["satellite"]["observation_span_days"]) * 24.0 + 6.0
    t_end = min(t_end, cfg.sim_hours)
    steps = int(round((t_end - event.t0_h) / dt_h))
    times = event.t0_h + np.arange(steps + 1) * dt_h

    pos = p0.copy()
    out = np.empty((len(times), n, 2), dtype=np.float32)
    for k, t in enumerate(times):
        active = birth <= t
        out[k] = pos
        nxt = pos.copy()
        if active.any():
            moved = drift_step(env, pos[active], float(t), dt_h, params, g)
            nxt[active] = moved
        # unborn particles stay at the source
        pos = nxt
    return SpillTruth(event=event, times_h=times, positions=out,
                      buffer_km=float(cfg["spill"]["slick_buffer_km"]),
                      poly_particles=int(cfg["spill"]["polygon_particles"]))
