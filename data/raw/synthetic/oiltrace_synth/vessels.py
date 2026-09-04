"""Synthetic AIS fleet.

Each vessel follows a piecewise-linear great-ish-circle route across the AOI at a
roughly constant speed, and reports its position at irregular intervals with
occasional dropouts. The true source vessel of each spill is additionally given a
"dark" gap around the release time.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import Config
from .rng import RNG

_VESSEL_TYPES = [
    ("Cargo", 90, 260, 14, 40, 5, 16),
    ("Tanker", 110, 330, 16, 60, 6, 15),
    ("Fishing", 15, 45, 4, 9, 2, 11),
    ("Passenger", 60, 200, 10, 30, 12, 22),
    ("Tug", 20, 40, 6, 12, 4, 12),
]
_NAV_UNDERWAY = "UnderWayUsingEngine"
_NAV_RESTRICTED = "RestrictedManoeuvrability"


@dataclass
class Vessel:
    mmsi: int
    vessel_type: str
    length: float
    width: float
    draught: float
    waypoints: np.ndarray          # (K, 2) km
    wp_times: np.ndarray           # (K,) sim hours
    base_speed_kn: float
    report_interval_min: float
    dark_gaps: list = field(default_factory=list)   # list of (start_h, end_h)

    @property
    def t_start(self) -> float:
        return float(self.wp_times[0])

    @property
    def t_end(self) -> float:
        return float(self.wp_times[-1])

    def active(self, t_h: float) -> bool:
        return self.t_start <= t_h <= self.t_end

    def position(self, t_h):
        """Piecewise-linear position; clamps to the endpoints outside the window."""
        t_h = np.asarray(t_h, dtype=float)
        x = np.interp(t_h, self.wp_times, self.waypoints[:, 0])
        y = np.interp(t_h, self.wp_times, self.waypoints[:, 1])
        return np.stack([x, y], axis=-1)

    def course_speed(self, t_h: float):
        p0 = self.position(t_h - 0.05)
        p1 = self.position(t_h + 0.05)
        d = p1 - p0
        cog = (np.degrees(np.arctan2(d[0], d[1]))) % 360.0   # 0 = north
        dist_km = float(np.hypot(*d))
        sog_kn = dist_km / 0.1 / 1.852
        return cog, sog_kn

    def in_dark_gap(self, t_h: float) -> bool:
        return any(a <= t_h <= b for a, b in self.dark_gaps)


class Fleet:
    def __init__(self, vessels: list[Vessel]):
        self.vessels = vessels
        self.by_mmsi = {v.mmsi: v for v in vessels}

    def __iter__(self):
        return iter(self.vessels)

    def __len__(self):
        return len(self.vessels)


def _random_route(rng: np.random.Generator, cfg: Config, speed_kn: float):
    w = float(cfg["aoi"]["width_km"])
    h = float(cfg["aoi"]["height_km"])
    sim_h = cfg.sim_hours

    def edge_point():
        side = rng.integers(0, 4)
        if side == 0:
            return np.array([rng.uniform(0, w), 0.0])
        if side == 1:
            return np.array([rng.uniform(0, w), h])
        if side == 2:
            return np.array([0.0, rng.uniform(0, h)])
        return np.array([w, rng.uniform(0, h)])

    k = int(rng.integers(2, 5))
    pts = [edge_point()]
    for _ in range(k - 2):
        pts.append(np.array([rng.uniform(0.1 * w, 0.9 * w), rng.uniform(0.1 * h, 0.9 * h)]))
    pts.append(edge_point())
    pts = np.array(pts)

    seg_km = np.hypot(*np.diff(pts, axis=0).T)
    speed_kmh = speed_kn * 1.852
    seg_h = seg_km / max(speed_kmh, 1e-3)
    total = seg_h.sum()
    # start so the whole route fits inside the sim window with margin
    latest_start = max(1.0, sim_h - total - 2.0)
    t0 = rng.uniform(0.0, latest_start)
    times = np.concatenate([[t0], t0 + np.cumsum(seg_h)])
    return pts, times


def build_fleet(cfg: Config, rng: RNG) -> Fleet:
    g = rng.stream("fleet")
    n = int(cfg["ais"]["n_vessels"])
    lo, hi = cfg["ais"]["report_interval_min"]
    vessels: list[Vessel] = []
    used = set()
    for i in range(n):
        while True:
            mmsi = int(g.integers(200_000_000, 775_000_000))
            if mmsi not in used:
                used.add(mmsi)
                break
        vt, lmin, lmax, wmin, wmax, smin, smax = _VESSEL_TYPES[int(g.integers(0, len(_VESSEL_TYPES)))]
        length = float(g.uniform(lmin, lmax))
        width = float(g.uniform(wmin, wmax))
        draught = float(np.clip(g.normal(length / 22.0, 1.2), 2.0, 22.0))
        speed = float(g.uniform(smin, smax))
        pts, times = _random_route(g, cfg, speed)
        vessels.append(Vessel(
            mmsi=mmsi, vessel_type=vt, length=round(length, 1), width=round(width, 1),
            draught=round(draught, 1), waypoints=pts, wp_times=times,
            base_speed_kn=round(speed, 1),
            report_interval_min=float(g.uniform(lo, hi)),
        ))
    return Fleet(vessels)


def transmissions(vessel: Vessel, cfg: Config, rng: np.random.Generator):
    """Yield observed AIS rows (dicts, without event context)."""
    dropout = float(cfg["ais"]["dropout_rate"])
    t = vessel.t_start
    while t <= vessel.t_end:
        if not vessel.in_dark_gap(t) and rng.random() > dropout:
            pos = vessel.position(t)
            cog, sog = vessel.course_speed(t)
            nav = _NAV_UNDERWAY if sog > 1.0 else "AtAnchor"
            yield dict(
                mmsi=vessel.mmsi, t_h=float(t), x_km=float(pos[0]), y_km=float(pos[1]),
                sog_kn=round(float(sog), 2), cog_deg=round(float(cog), 1),
                heading_deg=round(float(cog + rng.normal(0, 3)) % 360.0, 1),
                nav_status=nav, vessel_type=vessel.vessel_type,
                length=vessel.length, width=vessel.width, draught=vessel.draught,
            )
        step_min = max(0.5, rng.normal(vessel.report_interval_min, vessel.report_interval_min * 0.3))
        t += step_min / 60.0


def interpolated_track(vessel: Vessel, cfg: Config):
    """Regular-cadence interpolated positions, explicitly flagged is_observed=False."""
    step_h = float(cfg["ais"]["interp_interval_min"]) / 60.0
    ts = np.arange(vessel.t_start, vessel.t_end + 1e-6, step_h)
    pos = vessel.position(ts)
    rows = []
    for t, p in zip(ts, pos):
        cog, sog = vessel.course_speed(float(t))
        rows.append(dict(
            mmsi=vessel.mmsi, t_h=float(t), x_km=float(p[0]), y_km=float(p[1]),
            sog_kn=round(float(sog), 2), cog_deg=round(float(cog), 1),
            heading_deg=round(float(cog), 1),
            nav_status="Interpolated", vessel_type=vessel.vessel_type,
            length=vessel.length, width=vessel.width, draught=vessel.draught,
        ))
    return rows
