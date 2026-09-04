"""Tests for F3.4/F3.5 ID Conventions and Source Inference."""
from backend.f3_hindcast.adapter import F2StateAdapter
from backend.f3_hindcast.ensemble import EnsembleConfig, run_hindcast_ensemble
from backend.f3_hindcast.forcing import (
    MissingForcingFallbackProvider,
    SyntheticForcingProvider,
)
from backend.f3_hindcast.inference import infer_source_hypotheses
from shared.mocks.load_mock import load_mock
from shared.physics.lagrangian import Frame


def test_frozen_id_conventions_and_inference():
    """Verifies that infer_source_hypotheses adheres strictly to the frozen ID scheme."""
    raw_mock = load_mock("f2", "EVT0001")
    seed_states, meta = F2StateAdapter.prepare_seed_sequence(raw_mock)
    assert len(seed_states) > 0

    forcing = SyntheticForcingProvider()
    frame = Frame(ref_lat=forcing.ref_lat, ref_lon=forcing.ref_lon)
    config = EnsembleConfig(n_ensembles=6, n_particles=50)

    run_result = run_hindcast_ensemble(
        seed_states=seed_states,
        forcing_provider=forcing,
        frame=frame,
        config=config,
        base_seed=1234
    )

    hyps = infer_source_hypotheses(
        ensemble_result=run_result,
        seed_states=seed_states,
        frame=frame,
        config=config,
        data_quality_flag="nominal"
    )

    # 6 ensemble members + 1 best = 7 hypotheses
    assert len(hyps) == 7

    # Check ensemble IDs and probabilities
    ens_hyps = [h for h in hyps if h.ensemble_id >= 0]
    assert len(ens_hyps) == 6
    for i, h in enumerate(ens_hyps):
        assert h.source_hypothesis_id == f"SH_EVT0001_{i:02d}"
        assert h.uncertainty_radius_km > 0.0
        assert 0.0 < h.source_probability <= 1.0
        assert "OBS_EVT0001" in h.seed_state_ids[0]

    # Verify probability normalization
    total_prob = sum(h.source_probability for h in ens_hyps)
    assert 0.99 <= total_prob <= 1.01

    # Check pooled best hypothesis
    best_hyp = next(h for h in hyps if h.ensemble_id == -1)
    assert best_hyp.source_hypothesis_id == "SH_EVT0001_HBEST"
    assert best_hyp.source_probability == 1.0
    assert best_hyp.uncertainty_radius_km >= min(h.uncertainty_radius_km for h in ens_hyps)


def test_missing_forcing_widens_uncertainty():
    """Verifies that missing forcing triggers data_quality_flag and wide uncertainty."""
    raw_mock = load_mock("f2", "EVT0001")
    seed_states, meta = F2StateAdapter.prepare_seed_sequence(raw_mock)

    forcing = MissingForcingFallbackProvider()
    frame = Frame(ref_lat=38.0, ref_lon=20.0)
    config = EnsembleConfig(n_ensembles=3, n_particles=20)

    run_result = run_hindcast_ensemble(
        seed_states=seed_states,
        forcing_provider=forcing,
        frame=frame,
        config=config,
        base_seed=999
    )

    hyps = infer_source_hypotheses(
        ensemble_result=run_result,
        seed_states=seed_states,
        frame=frame,
        config=config,
        data_quality_flag="forcing_unavailable"
    )

    for h in hyps:
        assert h.data_quality_flag == "forcing_unavailable"
        assert h.uncertainty_radius_km >= 50.0  # Widened fallback envelope
