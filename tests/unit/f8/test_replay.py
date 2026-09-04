"""Historical replay: horizons matched to the nearest later OBSERVED state and
scored. Metrics must be well-formed and physically bounded.

NOTE: F8 drives the ensemble with F3's forcing *abstraction*, not the synthetic
generator's internal field, so exact agreement with ``D8_evaluation.csv`` is not
expected (the same reason F7's D7 check uses a tolerance band). These tests assert
structure and bounds, not reference values.
"""
from __future__ import annotations

import statistics

import pytest

from .conftest import FAST, REPLAY_EVENTS


def test_replay_matches_a_later_observation_within_tolerance(supervisor):
    supervisor.repo.clear()
    runs, evals = supervisor.execute_replay("EVT0002", **FAST)
    assert evals, "EVT0002 has later OBSERVED states -> at least one horizon must score"
    for e in evals:
        assert abs(e.match_offset_hours) <= 12.0 + 1e-6
        assert e.matched_observation_id
        assert 0.0 <= e.observed_region_coverage_iou <= 1.0
        assert 0.0 <= e.observed_in_forecast_envelope_frac <= 1.0
        assert e.trajectory_error_km >= 0.0
        assert e.calibration_ratio >= 0.0
        assert e.well_calibrated == (0.5 <= e.calibration_ratio <= 2.0)


def test_replay_returns_nothing_for_a_single_observation_event(supervisor):
    supervisor.repo.clear()
    runs, evals = supervisor.execute_replay("EVT0001", **FAST)  # only 1 OBSERVED state
    assert runs == [] and evals == []


def test_replay_trajectory_error_is_physically_bounded(supervisor):
    errs = []
    for ev in REPLAY_EVENTS:
        supervisor.repo.clear()
        _runs, evals = supervisor.execute_replay(ev, **FAST)
        errs.extend(e.trajectory_error_km for e in evals)
    assert errs, "expected replay scores across the reference events"
    # A drift forecast over <=48 h cannot plausibly be off by hundreds of km.
    assert max(errs) < 200.0
    assert statistics.median(errs) < 120.0


def test_replay_is_reproducible(supervisor):
    supervisor.repo.clear()
    _r1, e1 = supervisor.execute_replay("EVT0005", **FAST, base_seed=99)
    supervisor.repo.clear()
    _r2, e2 = supervisor.execute_replay("EVT0005", **FAST, base_seed=99)
    assert [e.trajectory_error_km for e in e1] == [e.trajectory_error_km for e in e2]
