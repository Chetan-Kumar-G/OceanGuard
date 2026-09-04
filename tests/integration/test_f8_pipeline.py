"""F8 end-to-end: F2 mock states -> forward forecast -> impact overlay -> replay,
for the reference EVT0002 event."""
from __future__ import annotations

from backend.f8_forecast.repository import F8Repository
from backend.f8_forecast.supervisor import F8ForecastSupervisor

_FAST = dict(n_ensemble=10, n_particles=150, horizons_h=[12.0, 24.0, 48.0])


def test_f8_pipeline_end_to_end():
    supervisor = F8ForecastSupervisor(repository=F8Repository())

    runs, particles, impacts = supervisor.execute_forecast("EVT0002", **_FAST)
    assert len(runs) == 3
    assert len(particles) > 0
    assert len(impacts) == 3

    for r in runs:
        assert r.n_ensemble == 10
        assert r.ensemble_spread_km >= 0.0
        assert r.forecast_envelope_area_km2 >= r.predicted_area_km2
        assert r.predicted_polygon_geojson["type"] in ("Polygon", "MultiPolygon")

    # Impact rows line up 1:1 with forecast horizons and carry the same geometry facts.
    by_horizon = {i.forecast_horizon_hours: i for i in impacts}
    for r in runs:
        i = by_horizon[r.forecast_horizon_hours]
        assert i.coastline_distance_km == r.coastline_distance_km
        assert i.beaching_risk == r.beaching_risk

    # Replay: EVT0002 has later OBSERVED states, so scoring must produce rows.
    replay_runs, evals = supervisor.execute_replay("EVT0002", **_FAST)
    assert replay_runs and evals
    for e in evals:
        assert e.event_id == "EVT0002"
        assert e.trajectory_error_km >= 0.0
        assert 0.0 <= e.observed_in_forecast_envelope_frac <= 1.0

    # Repository round-trip via the getters (cache hit, no re-run).
    cached = supervisor.get_runs("EVT0002")
    assert len(cached) == len(replay_runs)
