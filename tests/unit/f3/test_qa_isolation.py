"""Regression test ensuring zero QA-only or ground-truth data leakage into F3 outputs."""
from typing import Any, Dict, List, Set
from backend.f3_hindcast.supervisor import F3HindcastSupervisor
from shared.mocks.load_mock import load_mock


FORBIDDEN_QA_KEYS: Set[str] = {
    "qa_source_error_km",
    "is_true_source",
    "true_origin_lat",
    "true_origin_lon",
    "true_source_mmsi",
    "true_release_timestamp",
    "true_release_sim_hours",
}


def _assert_no_forbidden_keys(obj: Any, path: str = "") -> None:
    """Recursively checks that no forbidden QA or ground-truth keys exist in obj."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            current_path = f"{path}.{k}" if path else str(k)
            assert k not in FORBIDDEN_QA_KEYS, (
                f"QA Data Leakage Detected! Forbidden key '{k}' found at path '{current_path}'"
            )
            _assert_no_forbidden_keys(v, current_path)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _assert_no_forbidden_keys(item, f"{path}[{idx}]")


def test_f3_mock_zero_qa_leakage_all_events():
    """Verifies that load_mock('f3', event_id) contains no QA-only or ground-truth fields."""
    events = [f"EVT{i:04d}" for i in range(1, 13)]
    for event_id in events:
        mock_data = load_mock("f3", event_id)
        assert len(mock_data) > 0, f"No mock data returned for {event_id}"
        _assert_no_forbidden_keys(mock_data, path=f"mock_f3_{event_id}")


def test_f3_live_output_zero_qa_leakage():
    """Verifies that live F3 pipeline output contains no QA-only or ground-truth fields."""
    supervisor = F3HindcastSupervisor()
    hypotheses, _ = supervisor.execute_hindcast("EVT0001", base_seed=42)
    assert len(hypotheses) > 0

    dumped_hypotheses = [h.model_dump() for h in hypotheses]
    _assert_no_forbidden_keys(dumped_hypotheses, path="live_f3_EVT0001")
