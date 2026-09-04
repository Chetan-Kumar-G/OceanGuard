"""Tests for F3.2 Environmental Forcing Providers and Missing-Forcing Handling."""
import numpy as np
from backend.f3_hindcast.forcing import (
    MissingForcingFallbackProvider,
    SyntheticForcingProvider,
)


def test_synthetic_forcing_provider_evaluation():
    """Verifies that SyntheticForcingProvider yields valid wind and current vectors."""
    provider = SyntheticForcingProvider()
    assert provider.is_available() is True
    assert provider.source_name == "synthetic"

    lons = np.array([21.0, 21.2, 21.4])
    lats = np.array([38.0, 38.2, 38.4])
    t_h = 100.0

    uc, vc, uw, vw = provider.get_forcing(lons, lats, t_h)

    assert uc.shape == (3,)
    assert vc.shape == (3,)
    assert uw.shape == (3,)
    assert vw.shape == (3,)

    # Verify physical sanity (current speeds typically < 2 m/s, winds < 30 m/s)
    current_speed = np.hypot(uc, vc)
    wind_speed = np.hypot(uw, vw)

    assert np.all(current_speed > 0.0)
    assert np.all(current_speed < 3.0)  # m/s
    assert np.all(wind_speed > 0.0)
    assert np.all(wind_speed < 40.0)   # m/s


def test_missing_forcing_fallback_provider():
    """Verifies that MissingForcingFallbackProvider produces zero vectors without crashing."""
    fallback = MissingForcingFallbackProvider()
    assert fallback.is_available() is False
    assert fallback.source_name == "unavailable"

    lons = np.array([21.0, 21.5])
    lats = np.array([38.0, 38.5])
    t_h = 50.0

    uc, vc, uw, vw = fallback.get_forcing(lons, lats, t_h)
    assert np.all(uc == 0.0)
    assert np.all(vc == 0.0)
    assert np.all(uw == 0.0)
    assert np.all(vw == 0.0)
