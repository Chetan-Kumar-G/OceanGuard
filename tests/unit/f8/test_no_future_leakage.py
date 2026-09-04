"""A forecast must never consume an observation later than its T0 - only the
replay/eval path is allowed to look at the future (PDF section 7 validation
controls; Features.md F20)."""
from __future__ import annotations

import pytest

from shared.mocks.load_mock import load_mock
from shared.schemas.f2_contract import TemporalSpillState
from backend.f8_forecast.geometry import epoch_hours
from backend.f8_forecast.supervisor import F8ForecastSupervisor

from .conftest import FAST


def test_forecast_from_an_early_state_ignores_all_later_states(supervisor):
    raw = load_mock("f2", "EVT0002")
    states = [TemporalSpillState.model_validate(r) for r in raw]
    observed = sorted(
        (s for s in states if s.state_type == "OBSERVED" and s.is_observed),
        key=lambda s: epoch_hours(s.timestamp),
    )
    t0 = observed[0]
    t0_h = epoch_hours(t0.timestamp)

    supervisor.repo.clear()
    runs, _p, _i = supervisor.execute_forecast(
        "EVT0002", t0_observation_index=0, states=states, **{k: v for k, v in FAST.items() if k != "horizons_h"},
        horizons_h=[12.0, 24.0],
    )
    assert runs
    # Every run is launched from t0 and validity never predates it.
    for r in runs:
        assert r.initial_observation_id == t0.observation_id
        assert epoch_hours(r.valid_timestamp) > t0_h


def test_allow_future_flag_is_opt_in_only(supervisor):
    # Default path filters the future out; the private flag is what replay uses.
    import inspect

    sig = inspect.signature(F8ForecastSupervisor.execute_forecast)
    assert sig.parameters["_allow_future_states"].default is False
