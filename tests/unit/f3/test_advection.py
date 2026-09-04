"""Tests for F3.3 Analytic Constant-Current Lagrangian Advection."""
import numpy as np
from shared.physics.lagrangian import (
    DriftPhysicsParams,
    compute_advection_velocity_kmh,
    integrate_particles,
    lagrangian_step,
)


def _constant_current_forcing(x, y, t_h):
    # u_current = 1.0 m/s, v_current = 0.5 m/s, zero wind
    n = len(np.atleast_1d(x))
    uc = np.full(n, 1.0)
    vc = np.full(n, 0.5)
    uw = np.zeros(n)
    vw = np.zeros(n)
    return uc, vc, uw, vw


def test_analytic_constant_advection_forward():
    """Verifies that particle moves exactly: x = x0 + u * 3.6 * dt."""
    pos0 = np.array([[10.0, 20.0]])
    params = DriftPhysicsParams(wind_drift_factor=0.0, diffusion_m2s=0.0)
    rng = np.random.default_rng(42)

    # 10 hours of advection:
    # dx = 1.0 m/s * 3.6 km/h / (m/s) * 10 h = 36.0 km
    # dy = 0.5 m/s * 3.6 * 10 = 18.0 km
    times, traj = integrate_particles(
        pos0_km=pos0,
        t0_h=0.0,
        t1_h=10.0,
        dt_h=0.5,
        forcing_func=_constant_current_forcing,
        params=params,
        rng=rng
    )

    final_pos = traj[-1][0]
    expected_x = 10.0 + 36.0
    expected_y = 20.0 + 18.0

    assert np.isclose(final_pos[0], expected_x, atol=1e-6)
    assert np.isclose(final_pos[1], expected_y, atol=1e-6)


def test_analytic_constant_advection_backward():
    """Verifies that reverse-time integration reverses the trajectory exactly."""
    pos0 = np.array([[46.0, 38.0]])
    params = DriftPhysicsParams(wind_drift_factor=0.0, diffusion_m2s=0.0)
    rng = np.random.default_rng(42)

    # Backward from t=10h to t=0h
    times, traj = integrate_particles(
        pos0_km=pos0,
        t0_h=10.0,
        t1_h=0.0,
        dt_h=0.5,
        forcing_func=_constant_current_forcing,
        params=params,
        rng=rng
    )

    final_pos = traj[-1][0]
    expected_x = 10.0
    expected_y = 20.0

    assert np.isclose(final_pos[0], expected_x, atol=1e-6)
    assert np.isclose(final_pos[1], expected_y, atol=1e-6)
