"""Integration and Benchmark Validation Test for Canonical Event EVT0001."""
import numpy as np
from backend.f3_hindcast.supervisor import F3HindcastSupervisor
from shared.mocks.load_mock import load_mock
from shared.schemas.f3_contract import SourceHypothesisWindow


def test_evt0001_full_hindcast_pipeline():
    """Executes F3 end-to-end on canonical event EVT0001 and checks contracts and baseline numbers."""
    supervisor = F3HindcastSupervisor()

    # 1. Run hindcast on EVT0001
    hypotheses, env_snapshots = supervisor.execute_hindcast("EVT0001", base_seed=20260902)

    # 2. Verify hypothesis count (6 ensemble + 1 best)
    assert len(hypotheses) == 7
    assert len(env_snapshots) == 1

    # 3. Verify HBEST hypothesis
    hbest = next(h for h in hypotheses if h.source_hypothesis_id == "SH_EVT0001_HBEST")
    assert hbest.event_id == "EVT0001"
    assert hbest.ensemble_id == -1
    assert hbest.source_probability == 1.0
    assert hbest.uncertainty_radius_km > 0.0

    # Ensure source_location is within realistic AOI bounds (Mediterranean latitude ~35-40, lon ~18-23)
    assert 34.0 <= hbest.source_location.lat <= 41.0
    assert 17.0 <= hbest.source_location.lon <= 24.0

    # 4. Compare with reference D3_source_hypotheses mock
    ref_hyps = load_mock("f3", "EVT0001")
    ref_hbest = next(h for h in ref_hyps if h["source_hypothesis_id"] == "SH_EVT0001_HBEST")

    # The reconstructed position should be within consistent physical range of reference HBEST
    lat_diff = abs(hbest.source_location.lat - ref_hbest["source_location"]["lat"])
    lon_diff = abs(hbest.source_location.lon - ref_hbest["source_location"]["lon"])
    # Within 0.5 degrees (~50 km) of reference synthetic run
    assert lat_diff < 0.5, f"Latitude diff too large: {lat_diff}"
    assert lon_diff < 0.5, f"Longitude diff too large: {lon_diff}"

    # 5. Check persistence
    stored = supervisor.get_hypotheses("EVT0001")
    assert len(stored) == 7
    stored_best = supervisor.get_best_hypothesis("EVT0001")
    assert stored_best.source_hypothesis_id == "SH_EVT0001_HBEST"
