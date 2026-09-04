"""The shared Lagrangian engine must move particles forward under forcing and be
deterministic for a fixed seed (F8 relies on both)."""
from __future__ import annotations

import numpy as np

from shared.physics.lagrangian import DriftPhysicsParams, integrate_particles


def _steady_forcing(u_c=0.3, v_c=0.1):
    def f(x_km, y_km, t_h):
        n = len(np.atleast_1d(x_km))
        return (np.full(n, u_c), np.full(n, v_c), np.zeros(n), np.zeros(n))
    return f


def test_forward_step_advects_downstream():
    pos0 = np.zeros((50, 2))
    rng = np.random.default_rng(0)
    params = DriftPhysicsParams(wind_drift_factor=0.0, diffusion_m2s=0.0, forcing_noise_ms=0.0)
    _t, traj = integrate_particles(pos0, 0.0, 12.0, 0.5, _steady_forcing(0.3, 0.1), params, rng)
    end = traj[-1].mean(axis=0)
    # 0.3 m/s over 12 h ~= 12.96 km east; 0.1 m/s ~= 4.32 km north
    assert 11.0 < end[0] < 15.0
    assert 3.0 < end[1] < 6.0


def test_forward_integration_is_deterministic_for_a_fixed_seed():
    pos0 = np.random.default_rng(1).uniform(-1, 1, (40, 2))
    params = DriftPhysicsParams(diffusion_m2s=9.0, forcing_noise_ms=0.5)
    a = integrate_particles(pos0.copy(), 0.0, 24.0, 0.5, _steady_forcing(), params, np.random.default_rng(7))[1]
    b = integrate_particles(pos0.copy(), 0.0, 24.0, 0.5, _steady_forcing(), params, np.random.default_rng(7))[1]
    assert np.allclose(a, b)


def test_diffusion_spreads_the_cloud():
    pos0 = np.zeros((200, 2))
    no_diff = integrate_particles(pos0.copy(), 0.0, 24.0, 0.5, _steady_forcing(0, 0),
                                  DriftPhysicsParams(diffusion_m2s=0.0), np.random.default_rng(3))[1][-1]
    with_diff = integrate_particles(pos0.copy(), 0.0, 24.0, 0.5, _steady_forcing(0, 0),
                                    DriftPhysicsParams(diffusion_m2s=12.0), np.random.default_rng(3))[1][-1]
    assert with_diff.std(axis=0).mean() > no_diff.std(axis=0).mean() + 1.0
