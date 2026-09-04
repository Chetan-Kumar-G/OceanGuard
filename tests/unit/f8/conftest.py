"""Shared fixtures for F8 forward-forecast tests."""
from __future__ import annotations

import pytest

from backend.f8_forecast.repository import F8Repository
from backend.f8_forecast.supervisor import F8ForecastSupervisor

# EVT0002..EVT0012 all have >= 2 OBSERVED states; EVT0001 has only one.
REPLAY_EVENTS = [f"EVT{n:04d}" for n in range(2, 13)]
FAST = dict(n_ensemble=8, n_particles=120, horizons_h=[12.0, 24.0, 48.0])


@pytest.fixture()
def supervisor() -> F8ForecastSupervisor:
    return F8ForecastSupervisor(repository=F8Repository())
