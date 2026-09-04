"""Forward ensemble behaviour: spread grows with lead time, member count is
honoured, and a fixed seed reproduces the run."""
from __future__ import annotations

import pytest

from .conftest import FAST


def _runs(supervisor, **kw):
    supervisor.repo.clear()
    runs, _p, _i = supervisor.execute_forecast("EVT0002", **{**FAST, **kw})
    return runs


def test_ensemble_spread_grows_with_horizon(supervisor):
    runs = _runs(supervisor, horizons_h=[12.0, 24.0, 48.0, 72.0])
    spreads = [r.ensemble_spread_km for r in sorted(runs, key=lambda r: r.forecast_horizon_hours)]
    assert spreads == sorted(spreads), f"spread not monotonic in horizon: {spreads}"
    assert spreads[-1] > spreads[0]


def test_forecast_confidence_decays_with_horizon(supervisor):
    runs = sorted(_runs(supervisor), key=lambda r: r.forecast_horizon_hours)
    confs = [r.forecast_confidence for r in runs]
    assert confs == sorted(confs, reverse=True)
    assert all(0.0 <= c <= 1.0 for c in confs)


def test_n_ensemble_is_recorded_and_respected(supervisor):
    runs = _runs(supervisor, n_ensemble=11)
    assert all(r.n_ensemble == 11 for r in runs)


def test_run_is_reproducible_for_a_fixed_seed(supervisor):
    a = _runs(supervisor, base_seed=123)
    b = _runs(supervisor, base_seed=123)
    assert [r.ensemble_spread_km for r in a] == [r.ensemble_spread_km for r in b]
    assert [r.predicted_area_km2 for r in a] == [r.predicted_area_km2 for r in b]


def test_envelope_is_larger_than_the_predicted_slick(supervisor):
    for r in _runs(supervisor):
        assert r.forecast_envelope_area_km2 >= r.predicted_area_km2
        assert r.predicted_polygon_geojson["coordinates"]
        assert r.forecast_envelope_geojson["coordinates"]


def test_horizons_override_is_applied(supervisor):
    runs = _runs(supervisor, horizons_h=[6.0, 18.0])
    assert sorted(r.forecast_horizon_hours for r in runs) == [6.0, 18.0]
