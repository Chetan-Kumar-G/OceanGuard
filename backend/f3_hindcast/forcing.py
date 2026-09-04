"""Environmental Forcing Provider abstraction and implementations.

Provides spatial-temporal wind and surface-current vectors at arbitrary coordinates.
Supports synthetic vector fields and graceful fallback when forcing is unavailable.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np

from shared.config.settings import get_settings


_KM_PER_DEG_LAT = 111.32


@dataclass(frozen=True)
class ForcingVector:
    """Wind and current components at a specific point in time and space."""
    u_wind_ms: float       # Eastward wind component (m/s)
    v_wind_ms: float       # Northward wind component (m/s)
    u_current_ms: float    # Eastward current component (m/s)
    v_current_ms: float    # Northward current component (m/s)
    source: str            # 'synthetic', 'ERA5', 'Copernicus', 'unavailable'
    data_quality_flag: str # 'nominal', 'forcing_unavailable', etc.

    @property
    def wind_speed_ms(self) -> float:
        return float(math.hypot(self.u_wind_ms, self.v_wind_ms))

    @property
    def current_speed_ms(self) -> float:
        return float(math.hypot(self.u_current_ms, self.v_current_ms))

    @property
    def wind_dir_deg(self) -> float:
        """Meteorological direction (direction wind is coming from) in degrees [0, 360)."""
        angle = math.degrees(math.atan2(-self.u_wind_ms, -self.v_wind_ms))
        return (angle + 360.0) % 360.0

    @property
    def current_dir_deg(self) -> float:
        """Oceanographic direction (direction current is flowing towards) in degrees [0, 360)."""
        angle = math.degrees(math.atan2(self.u_current_ms, self.v_current_ms))
        return (angle + 360.0) % 360.0


class ForcingProvider(ABC):
    """Abstract interface for environmental forcing queries."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the forcing source, e.g. 'synthetic', 'ERA5', 'Copernicus'."""
        pass

    @abstractmethod
    def get_forcing(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        t_h: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Evaluates wind and current vectors at array of coordinates (lons, lats) and sim_hours t_h.

        Returns:
            Tuple of (u_current_ms, v_current_ms, u_wind_ms, v_wind_ms) as numpy arrays.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if forcing data is loaded and valid."""
        pass


class SyntheticForcingProvider(ForcingProvider):
    """Forcing provider using synthetic spectral multi-mode vector fields."""

    def __init__(self, cfg_dict: Optional[Dict[str, Any]] = None):
        if cfg_dict is None:
            settings = get_settings()
            cfg_dict = settings.load_config_yaml()

        self._cfg = cfg_dict
        self._aoi = cfg_dict["aoi"]
        self.ref_lat = float(self._aoi["ref_lat"])
        self.ref_lon = float(self._aoi["ref_lon"])
        self.km_per_deg_lon = _KM_PER_DEG_LAT * math.cos(math.radians(self.ref_lat))

        # Build synthetic vector fields matching oiltrace_synth reference
        seed = int(cfg_dict.get("seed", 20260902))
        wcfg = cfg_dict["environment"]["wind"]
        ccfg = cfg_dict["environment"]["current"]

        # Deterministic RNG streams for reproducibility
        self._rng_wind = np.random.default_rng(seed + 101)
        self._rng_wind_dir = np.random.default_rng(seed + 102)
        self._rng_curr = np.random.default_rng(seed + 201)
        self._rng_curr_dir = np.random.default_rng(seed + 202)
        self._gust_rng = np.random.default_rng(seed + 301)

        self._wind_field = self._init_vector_field(
            rng=self._rng_wind,
            n_modes=int(wcfg["n_modes"]),
            corr_len_km=float(wcfg["corr_length_km"]),
            corr_time_h=float(wcfg["corr_time_h"]),
            target_rms=float(wcfg["mean_speed"]),
            mean_dir_rng=self._rng_wind_dir
        )

        self._current_field = self._init_vector_field(
            rng=self._rng_curr,
            n_modes=int(ccfg["n_modes"]),
            corr_len_km=float(ccfg["corr_length_km"]),
            corr_time_h=float(ccfg["corr_time_h"]),
            target_rms=float(ccfg["mean_speed"]),
            mean_dir_rng=self._rng_curr_dir
        )

        self._gust_std = float(wcfg.get("gust_std", 2.0))
        self._gust_cache: Dict[int, float] = {}

    def _init_vector_field(
        self,
        rng: np.random.Generator,
        n_modes: int,
        corr_len_km: float,
        corr_time_h: float,
        target_rms: float,
        mean_dir_rng: np.random.Generator
    ) -> Dict[str, Any]:
        k0 = 2.0 * np.pi / corr_len_km
        w0 = 2.0 * np.pi / corr_time_h
        kx = rng.normal(0.0, k0, n_modes)
        ky = rng.normal(0.0, k0, n_modes)
        w = rng.normal(0.0, w0, n_modes)
        phase = rng.uniform(0.0, 2.0 * np.pi, n_modes)
        amp = rng.uniform(0.4, 1.0, n_modes)
        ang = mean_dir_rng.uniform(0.0, 2.0 * np.pi)
        mean_dir = np.array([np.cos(ang), np.sin(ang)])

        # Calibrate scale
        g = np.random.default_rng(0)
        xs = g.uniform(0, 400, 2000)
        ys = g.uniform(0, 400, 2000)
        ts = g.uniform(0, 240, 20)
        acc = []
        for t in ts:
            phases = (np.multiply.outer(xs, kx) + np.multiply.outer(ys, ky)
                      - w * float(t) + phase)
            u = (np.sin(phases) * amp).sum(axis=-1)
            v = (np.cos(phases) * amp).sum(axis=-1)
            acc.append(np.sqrt(u * u + v * v))
        rms = float(np.sqrt(np.mean(np.square(acc)))) or 1.0
        scale = target_rms / rms

        return {
            "kx": kx, "ky": ky, "w": w, "phase": phase, "amp": amp,
            "mean_dir": mean_dir, "scale": scale
        }

    def _eval_field(self, field: Dict[str, Any], x_km: np.ndarray, y_km: np.ndarray, t_h: float):
        x = np.asarray(x_km, dtype=float)
        y = np.asarray(y_km, dtype=float)
        phases = (np.multiply.outer(x, field["kx"]) + np.multiply.outer(y, field["ky"])
                  - field["w"] * float(t_h) + field["phase"])
        u = (np.sin(phases) * field["amp"]).sum(axis=-1)
        v = (np.cos(phases) * field["amp"]).sum(axis=-1)
        u = u * field["scale"] + field["mean_dir"][0] * field["scale"] * 0.6
        v = v * field["scale"] + field["mean_dir"][1] * field["scale"] * 0.6
        return u, v

    def _gust_factor(self, t_h: float) -> float:
        bucket = int(t_h // 3)
        if bucket not in self._gust_cache:
            self._gust_cache[bucket] = float(
                1.0 + self._gust_rng.normal(0.0, self._gust_std) / max(self._gust_std * 4, 1e-6)
            )
        return max(0.4, self._gust_cache[bucket])

    @property
    def source_name(self) -> str:
        return "synthetic"

    def is_available(self) -> bool:
        return True

    def to_km(self, lon: Union[float, np.ndarray], lat: Union[float, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        x = (np.asarray(lon) - self.ref_lon) * self.km_per_deg_lon
        y = (np.asarray(lat) - self.ref_lat) * _KM_PER_DEG_LAT
        return x, y

    def get_forcing(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        t_h: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        x_km, y_km = self.to_km(lons, lats)
        uc, vc = self._eval_field(self._current_field, x_km, y_km, t_h)
        uw, vw = self._eval_field(self._wind_field, x_km, y_km, t_h)
        gust = self._gust_factor(t_h)
        return uc, vc, uw * gust, vw * gust


class MissingForcingFallbackProvider(ForcingProvider):
    """Fallback provider when environmental forcing is unavailable.

    Returns zero velocities and flags the state as 'forcing_unavailable'
    allowing downstream F4 to run with an expanded uncertainty corridor.
    """

    @property
    def source_name(self) -> str:
        return "unavailable"

    def is_available(self) -> bool:
        return False

    def get_forcing(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        t_h: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        n = len(np.atleast_1d(lons))
        zeros = np.zeros(n, dtype=float)
        return zeros.copy(), zeros.copy(), zeros.copy(), zeros.copy()
