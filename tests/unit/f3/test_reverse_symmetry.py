"""Tests for F3.3 Reverse-Time Symmetry and Conservation."""
import numpy as np
from shared.physics.lagrangian import DriftPhysicsParams, integrate_particles


def _time_varying_forcing(x, y, t_h):
    # Oscillating wind and current
    n = len(np.atleast_1d(x))
    uc = 0.5 + 0.2 * np.sin(0.1 * t_h + x * 0.01)
    vc = 0.3 + 0.1 * np.cos(0.08 * t_h + y * 0.01)
    uw = 5.0 * np.cos(0.05 * t_h)
    vw = 3.0 * np.sin(0.05 * t_h)
    return np.full(n, uc), np.full(n, vc), np.full(n, uw), np.full(n, vw)


def test_reverse_time_symmetry_deterministic():
    """Verifies that forward then backward integration with D=0 perfectly recovers initial position."""
    pos0 = np.array([[25.0, 35.0], [50.0, 70.0], [10.0, 15.0]])
    params = DriftPhysicsParams(wind_drift_factor=0.03, diffusion_m2s=0.0)
    rng = np.random.default_rng(123)

    # 1. Forward 24 hours
    _, traj_fwd = integrate_particles(
        pos0_km=pos0,
        t0_h=0.0,
        t1_h=24.0,
        dt_h=0.25,
        forcing_func=_time_varying_forcing,
        params=params,
        rng=rng
    )
    pos_end = traj_fwd[-1]

    # 2. Backward 24 hours from pos_end to 0.0
    _, traj_bwd = integrate_particles(
        pos0_km=pos_end,
        t0_h=24.0,
        t1_h=0.0,
        dt_h=0.25,
        forcing_func=_time_varying_forcing,
        params=params,
        rng=rng
    )
    recovered_pos0 = traj_bwd[-1]

    # Max difference across all particles should be virtually zero
    max_err = np.max(np.abs(recovered_pos0 - pos0))
    assert max_err < 1e-4, f"Reverse symmetry error too high: {max_err} km"


def test_reverse_time_symmetry_with_diffusion_centroid():
    """Verifies that with diffusion D > 0, the ensemble centroid recovers origin within statistical bound."""
    n_part = 500
    pos0 = np.repeat(np.array([[30.0, 40.0]]), n_part, axis=0)
    params = DriftPhysicsParams(wind_drift_factor=0.03, diffusion_m2s=9.0)
    rng = np.random.default_rng(456)

    # Forward 12h
    _, traj_fwd = integrate_particles(
        pos0_km=pos0,
        t0_h=0.0,
        t1_h=12.0,
        dt_h=0.5,
        forcing_func=_time_varying_forcing,
        params=params,
        rng=rng
    )
    # Backward 12h
    _, traj_bwd = integrate_particles(
        pos0_km=traj_fwd[-1],
        t0_h=12.0,
        t1_h=0.0,
        dt_h=0.5,
        forcing_func=_time_varying_forcing,
        params=params,
        rng=rng
    )
    final_centroid = np.mean(traj_bwd[-1], axis=0)
    centroid_drift = np.linalg.norm(final_centroid - np.array([30.0, 40.0]))

    # Centroid error should be well under 1 km for 500 particles over 24h roundtrip
    assert centroid_drift < 0.5, f"Centroid drift with diffusion too large: {centroid_drift} km"
