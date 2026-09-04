"""In-memory store for F8 forecast artifacts (mirrors F3's repository shape)."""
from __future__ import annotations

from typing import Dict, List, Optional

from shared.schemas.f8_contract import (
    ForecastEvaluation,
    ForecastParticle,
    ForecastRun,
    ImpactAssessment,
)


class F8Repository:
    def __init__(self) -> None:
        self._runs: Dict[str, List[ForecastRun]] = {}
        self._particles: Dict[str, List[ForecastParticle]] = {}
        self._impact: Dict[str, List[ImpactAssessment]] = {}
        self._evals: Dict[str, List[ForecastEvaluation]] = {}

    def save_runs(self, event_id: str, runs: List[ForecastRun]) -> None:
        self._runs[event_id] = list(runs)

    def save_particles(self, event_id: str, parts: List[ForecastParticle]) -> None:
        self._particles[event_id] = list(parts)

    def save_impact(self, event_id: str, impact: List[ImpactAssessment]) -> None:
        self._impact[event_id] = list(impact)

    def save_evaluations(self, event_id: str, evals: List[ForecastEvaluation]) -> None:
        self._evals[event_id] = list(evals)

    def get_runs(self, event_id: str) -> List[ForecastRun]:
        return list(self._runs.get(event_id, []))

    def get_particles(self, event_id: str) -> List[ForecastParticle]:
        return list(self._particles.get(event_id, []))

    def get_impact(self, event_id: str) -> List[ImpactAssessment]:
        return list(self._impact.get(event_id, []))

    def get_evaluations(self, event_id: str) -> List[ForecastEvaluation]:
        return list(self._evals.get(event_id, []))

    def clear(self) -> None:
        self._runs.clear()
        self._particles.clear()
        self._impact.clear()
        self._evals.clear()


_default_repo = F8Repository()


def get_f8_repository() -> F8Repository:
    return _default_repo
