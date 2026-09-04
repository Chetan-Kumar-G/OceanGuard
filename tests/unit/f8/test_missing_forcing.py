"""When environmental forcing is unavailable, F8 falls back to the zero-velocity
provider, flags ``data_quality_flag='forcing_unavailable'``, and still returns a
run (never crashes) - mirroring F3's fallback contract."""
from __future__ import annotations

import pytest

import backend.f8_forecast.supervisor as supervisor_mod
from backend.f8_forecast.forcing import MissingForcingFallbackProvider

from .conftest import FAST


def test_missing_forcing_flags_data_quality_and_still_forecasts(monkeypatch, supervisor):
    def _boom(*a, **kw):
        raise RuntimeError("forcing field unavailable")

    monkeypatch.setattr(supervisor_mod, "SyntheticForcingProvider", _boom)

    runs, particles, impacts = supervisor.execute_forecast("EVT0002", **FAST)
    assert runs
    assert all(r.data_quality_flag == "forcing_unavailable" for r in runs)
    # Zero-velocity fallback: only noise/diffusion move the cloud, so it must stay
    # close to the launch point (no systematic advection to drag it far away).
    for r in runs:
        assert abs(r.predicted_centroid.lat - r.initial_centroid.lat) < 0.3
        assert abs(r.predicted_centroid.lon - r.initial_centroid.lon) < 0.3


def test_fallback_provider_reports_unavailable():
    p = MissingForcingFallbackProvider()
    assert p.is_available() is False
    uc, vc, uw, vw = p.get_forcing([1.0, 2.0], [1.0, 2.0], 10.0)
    assert list(uc) == [0.0, 0.0]
    assert list(vw) == [0.0, 0.0]
