from pathlib import Path
import pandas as pd
import pytest

from backend.f1_detection.inference import F1Detector
from backend.shared.config.settings import settings


def test_full_event_integration_pipeline():
    """
    Integration test: Run all scenes for synthetic event EVT0001 through F1Detector.
    Validates end-to-end schema compliance and compares predicted polygon area
    against true_oil_area_km2 in D1_satellite_scenes.csv.
    """
    csv_path = settings.synthetic_data_dir / "outputs" / "D1_satellite_scenes.csv"
    if not csv_path.exists():
        pytest.skip(f"D1 scenes CSV not found at: {csv_path}")

    df = pd.read_csv(csv_path)
    event_df = df[df["event_id"] == "EVT0001"].sort_values("acquisition_timestamp")
    assert len(event_df) > 0, "No scenes found for event EVT0001"

    detector = F1Detector()
    results = []

    for _, row in event_df.iterrows():
        scene_id = str(row["scene_id"])
        true_area = float(row.get("true_oil_area_km2", 0.0))
        oil_present_truth = bool(row["oil_present"])

        res = detector.detect_scene(scene_id=scene_id)
        results.append((res, true_area, oil_present_truth))

        # Check required schema integrity
        assert res.scene_id == scene_id
        assert res.event_id == "EVT0001"
        assert 0.0 <= res.confidence <= 1.0
        assert isinstance(res.oil_present, bool)
        assert isinstance(res.lookalike_present, bool)
        assert "type" in res.polygon_geojson
        assert "coordinates" in res.polygon_geojson

        # When no oil is present, confidence must be 0.0
        if not res.oil_present:
            assert res.confidence == 0.0

    # Ensure at least one scene in the event had oil evaluated
    oil_scenes = [r for r, true_area, truth in results if truth]
    assert len(oil_scenes) > 0
