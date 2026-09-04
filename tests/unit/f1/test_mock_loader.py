from backend.shared.mocks.load_mock import load_mock
from backend.shared.schemas.spill_detection import SpillDetectionResult


def test_load_mock_f1_event():
    mocks = load_mock("f1", "EVT0001")
    assert len(mocks) > 0
    for m in mocks:
        # Validate that the mock dict parses back into SpillDetectionResult without error
        res = SpillDetectionResult.model_validate(m)
        assert res.event_id == "EVT0001"
        assert 0.0 <= res.confidence <= 1.0
        assert isinstance(res.oil_present, bool)
        assert "type" in res.polygon_geojson
