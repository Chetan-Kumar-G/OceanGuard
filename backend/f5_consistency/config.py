"""Threshold loading. `/shared/config/evidence_thresholds.yaml` is the single
source of truth — nothing in this package hardcodes a bound.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_PATH = (
    Path(__file__).resolve().parents[2] / "shared" / "config" / "evidence_thresholds.yaml"
)

# The only residuals that can move a verdict. drift_residual_km / ais_gap_ratio
# are context: reported, and allowed to downgrade SUPPORTS -> UNKNOWN, never more.
CONSTRAINED_RESIDUALS: tuple[str, ...] = ("spatial_residual_km", "temporal_residual_h")


@dataclass(frozen=True)
class DriftModelParams:
    default_wind_drift_factor: float = 0.032
    max_current_speed_ms: float = 1.125
    max_wind_speed_ms: float = 15.0

    @property
    def max_plausible_drift_speed_kmh(self) -> float:
        return (self.max_current_speed_ms + self.default_wind_drift_factor * self.max_wind_speed_ms) * 3.6


@dataclass(frozen=True)
class EvidenceThresholds:
    support: dict[str, float]
    contradict: dict[str, float]
    min_sensor_confidence: float = 0.5
    f3f4_high_gap_downgrade: bool = True
    drift_model: DriftModelParams = field(default_factory=DriftModelParams)
    source_path: str = str(_DEFAULT_PATH)

    def bound(self, kind: str, residual: str) -> float:
        table = self.support if kind == "support" else self.contradict
        try:
            return float(table[residual])
        except KeyError as exc:  # pragma: no cover - config guard
            raise KeyError(
                f"no {kind} bound for residual {residual!r} in {self.source_path}"
            ) from exc


def _load_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"evidence thresholds config not found: {path}")
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    ev = doc.get("evidence")
    if not isinstance(ev, dict) or "support" not in ev or "contradict" not in ev:
        raise ValueError(f"{path} must define evidence.support and evidence.contradict")
    return ev


def load_thresholds(path: str | os.PathLike[str] | None = None) -> EvidenceThresholds:
    """Load thresholds from YAML. ``OILTRACE_EVIDENCE_THRESHOLDS`` env var overrides
    the default path; an explicit ``path`` argument overrides both."""
    resolved = Path(
        path
        or os.environ.get("OILTRACE_EVIDENCE_THRESHOLDS")
        or _DEFAULT_PATH
    )
    ev = _load_raw(resolved)
    overrides = ev.get("overrides", {}) or {}
    dm = ev.get("drift_model", {}) or {}
    return EvidenceThresholds(
        support={k: float(v) for k, v in ev["support"].items()},
        contradict={k: float(v) for k, v in ev["contradict"].items()},
        min_sensor_confidence=float(overrides.get("min_sensor_confidence", 0.5)),
        f3f4_high_gap_downgrade=bool(overrides.get("f3f4_high_gap_downgrade", True)),
        drift_model=DriftModelParams(
            default_wind_drift_factor=float(dm.get("default_wind_drift_factor", 0.032)),
            max_current_speed_ms=float(dm.get("max_current_speed_ms", 1.125)),
            max_wind_speed_ms=float(dm.get("max_wind_speed_ms", 15.0)),
        ),
        source_path=str(resolved),
    )


@lru_cache(maxsize=1)
def default_thresholds() -> EvidenceThresholds:
    return load_thresholds()
