"""Sample the ground-truth spill events.

Each event is anchored to a real fleet vessel: the release point and time are
taken from a point along that vessel's route, so there is always a genuine
culprit whose AIS track is consistent with the spill. The vessel is then given a
dark gap covering the release.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import Config
from .rng import RNG
from .vessels import Fleet, Vessel


@dataclass
class Event:
    event_id: str
    idx: int
    source_mmsi: int
    x0_km: float
    y0_km: float
    t0_h: float                 # release start (sim hours)
    release_hours: float
    split: str                  # train / val / test (event-level)

    @property
    def origin_xy(self) -> np.ndarray:
        return np.array([self.x0_km, self.y0_km])


def _assign_splits(n: int, fracs, g: np.random.Generator) -> list[str]:
    labels = np.array(["train"] * n, dtype=object)
    order = g.permutation(n)
    n_train = int(round(fracs[0] * n))
    n_val = int(round(fracs[1] * n))
    for j, i in enumerate(order):
        if j < n_train:
            labels[i] = "train"
        elif j < n_train + n_val:
            labels[i] = "val"
        else:
            labels[i] = "test"
    return list(labels)


def sample_events(cfg: Config, rng: RNG, fleet: Fleet) -> list[Event]:
    g = rng.stream("events")
    n = int(cfg["n_events"])
    obs_span = float(cfg["satellite"]["observation_span_days"]) * 24.0
    sim_h = cfg.sim_hours
    w = float(cfg["aoi"]["width_km"])
    h = float(cfg["aoi"]["height_km"])

    # a vessel is eligible if it is mid-route for long enough to host a release
    # that leaves room for a hindcast before and the observation span after
    earliest = 30.0
    latest = sim_h - obs_span - 6.0
    eligible: list[Vessel] = [
        v for v in fleet
        if v.t_start + 3.0 < latest and v.t_end - 3.0 > earliest
        and (v.t_end - v.t_start) > 12.0
    ]
    if not eligible:
        eligible = list(fleet)

    splits = _assign_splits(n, cfg["output"]["train_val_test"], rng.stream("events", "split"))
    chosen = g.choice(len(eligible), size=n, replace=len(eligible) < n)
    events: list[Event] = []
    for i, ci in enumerate(chosen):
        v = eligible[int(ci)]
        lo = max(v.t_start + 2.0, earliest)
        hi = min(v.t_end - 2.0, latest)
        if hi <= lo:
            lo, hi = v.t_start + 1.0, v.t_end - 1.0
        t0 = float(g.uniform(lo, hi))
        p = v.position(t0)
        # small offset: the slick is dumped just off the vessel
        off = g.normal(0.0, 0.4, 2)
        x0 = float(np.clip(p[0] + off[0], 8.0, w - 8.0))
        y0 = float(np.clip(p[1] + off[1], 8.0, h - 8.0))
        rel = float(np.clip(g.normal(cfg["spill"]["release_hours"], 1.0), 0.5, 8.0))

        gap_lo, gap_hi = cfg["ais"]["culprit_dark_gap_h"]
        gap_len = float(g.uniform(gap_lo, gap_hi))
        gap_start = t0 - gap_len * float(g.uniform(0.2, 0.6))
        v.dark_gaps.append((gap_start, gap_start + gap_len))

        events.append(Event(
            event_id=f"EVT{i + 1:04d}", idx=i, source_mmsi=v.mmsi,
            x0_km=x0, y0_km=y0, t0_h=t0, release_hours=rel, split=splits[i],
        ))

    # optional extra dark gaps on non-culprit vessels (decoy noise)
    dg = rng.stream("events", "decoy_gaps")
    prob = float(cfg["ais"]["decoy_dark_gap_prob"])
    culprits = {e.source_mmsi for e in events}
    for v in fleet:
        if v.mmsi in culprits or dg.random() > prob:
            continue
        span = v.t_end - v.t_start
        s = v.t_start + dg.uniform(0.2, 0.7) * span
        v.dark_gaps.append((s, s + dg.uniform(1.0, 4.0)))
    return events
