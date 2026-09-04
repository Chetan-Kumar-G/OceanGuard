"""Synthetic wind and surface-current fields.

Each field is a small sum of travelling sinusoidal modes, giving something that
is smooth in space and time, divergence-light, and cheap to evaluate anywhere.
The realised RMS speed is rescaled to the configured target. This stands in for
ERA5 wind / CMEMS currents; the derived datasets only need an internally
consistent forcing, not a real reanalysis.
"""
from __future__ import annotations

import numpy as np

from .config import Config
from .rng import RNG


class _VectorField:
    def __init__(self, rng: np.random.Generator, n_modes: int, corr_len_km: float,
                 corr_time_h: float, target_rms: float, mean_dir_rng: np.random.Generator):
        k0 = 2.0 * np.pi / corr_len_km
        w0 = 2.0 * np.pi / corr_time_h
        self.kx = rng.normal(0.0, k0, n_modes)
        self.ky = rng.normal(0.0, k0, n_modes)
        self.w = rng.normal(0.0, w0, n_modes)
        self.phase = rng.uniform(0.0, 2.0 * np.pi, n_modes)
        self.amp = rng.uniform(0.4, 1.0, n_modes)
        # a steady background drift so the field has a mean direction
        ang = mean_dir_rng.uniform(0.0, 2.0 * np.pi)
        self.mean = np.array([np.cos(ang), np.sin(ang)])
        self._scale = 1.0
        self._calibrate(target_rms)

    def _raw(self, x, y, t):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        phases = (np.multiply.outer(x, self.kx) + np.multiply.outer(y, self.ky)
                  - self.w * float(t) + self.phase)
        s = np.sin(phases) * self.amp
        c = np.cos(phases) * self.amp
        u = s.sum(axis=-1)
        v = c.sum(axis=-1)
        return u, v

    def _calibrate(self, target_rms: float):
        g = np.random.default_rng(0)
        xs = g.uniform(0, 400, 4000)
        ys = g.uniform(0, 400, 4000)
        ts = g.uniform(0, 240, 40)
        acc = []
        for t in ts:
            u, v = self._raw(xs, ys, t)
            acc.append(np.sqrt(u * u + v * v))
        rms = float(np.sqrt(np.mean(np.square(acc)))) or 1.0
        self._scale = target_rms / rms

    def __call__(self, x, y, t):
        u, v = self._raw(x, y, t)
        u = u * self._scale + self.mean[0] * self._scale * 0.6
        v = v * self._scale + self.mean[1] * self._scale * 0.6
        return u, v


class Environment:
    """Callable forcing for the whole AOI and simulation window."""

    def __init__(self, cfg: Config, rng: RNG):
        wcfg = cfg["environment"]["wind"]
        ccfg = cfg["environment"]["current"]
        self.wind = _VectorField(
            rng.stream("env", "wind"), int(wcfg["n_modes"]),
            float(wcfg["corr_length_km"]), float(wcfg["corr_time_h"]),
            float(wcfg["mean_speed"]), rng.stream("env", "wind", "dir"))
        self.current = _VectorField(
            rng.stream("env", "current"), int(ccfg["n_modes"]),
            float(ccfg["corr_length_km"]), float(ccfg["corr_time_h"]),
            float(ccfg["mean_speed"]), rng.stream("env", "current", "dir"))
        self._gust_std = float(wcfg["gust_std"])
        self._gust_rng = rng.stream("env", "wind", "gust")
        self._gust_cache: dict[int, float] = {}

    def gust_factor(self, t_h: float) -> float:
        bucket = int(t_h // 3)
        if bucket not in self._gust_cache:
            self._gust_cache[bucket] = float(
                1.0 + self._gust_rng.normal(0.0, self._gust_std) / max(self._gust_std * 4, 1e-6))
        return max(0.4, self._gust_cache[bucket])

    def wind_at(self, x, y, t_h):
        u, v = self.wind(x, y, t_h)
        g = self.gust_factor(t_h)
        return u * g, v * g

    def current_at(self, x, y, t_h):
        return self.current(x, y, t_h)

    def wind_speed(self, x, y, t_h) -> np.ndarray:
        u, v = self.wind_at(x, y, t_h)
        return np.sqrt(np.square(u) + np.square(v))
