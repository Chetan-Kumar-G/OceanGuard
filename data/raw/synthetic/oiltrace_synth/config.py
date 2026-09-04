"""Load and lightly validate the master configuration."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class Config(dict):
    """Dict with attribute access and a couple of derived helpers."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc

    @property
    def sim_start(self) -> datetime:
        raw = self["sim_start_utc"].replace("Z", "+00:00")
        return datetime.fromisoformat(raw).astimezone(timezone.utc)

    @property
    def sim_hours(self) -> float:
        return float(self["time"]["sim_days"]) * 24.0

    def ts(self, hours: float) -> datetime:
        """Simulation hour -> absolute UTC timestamp."""
        from datetime import timedelta

        return self.sim_start + timedelta(hours=float(hours))

    def iso(self, hours: float) -> str:
        return self.ts(hours).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wrap(obj: Any) -> Any:
    if isinstance(obj, dict):
        return Config({k: _wrap(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_wrap(v) for v in obj]
    return obj


def load_config(path: str | Path) -> Config:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    cfg = _wrap(raw)

    assert cfg["n_events"] >= 1, "n_events must be >= 1"
    frac = cfg["output"]["train_val_test"]
    assert abs(sum(frac) - 1.0) < 1e-6, "train_val_test must sum to 1.0"
    assert cfg["time"]["step_minutes"] > 0
    return cfg
