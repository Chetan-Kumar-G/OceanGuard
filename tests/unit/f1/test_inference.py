from pathlib import Path
import pytest

from backend.f1_detection.inference import F1Detector
from backend.shared.schemas.spill_detection import SpillDetectionResult


def test_detector_nominal_scene():
    detector = F1Detector()
    # Test on known synthetic scene S1_EVT0001_01
    res = detector.detect_scene(scene_id="S1_EVT0001_01")
    assert isinstance(res, SpillDetectionResult)
    assert res.scene_id == "S1_EVT0001_01"
    assert res.event_id == "EVT0001"
    assert 0.0 <= res.confidence <= 1.0
    assert isinstance(res.oil_present, bool)
    assert isinstance(res.lookalike_present, bool)
    assert res.source_dataset == "synthetic"
    assert "type" in res.polygon_geojson


def test_detector_handles_missing_file_gracefully():
    detector = F1Detector()
    # Provide non-existent image path
    res = detector.detect_scene(
        scene_id="S1_NON_EXISTENT",
        image_path="path/to/missing/file.npy",
    )
    assert isinstance(res, SpillDetectionResult)
    assert res.scene_id == "S1_NON_EXISTENT"
    assert res.confidence == 0.0
    assert res.oil_present is False
    assert "error" in res.data_quality_flag
    assert res.polygon_geojson["coordinates"] == []


def test_confidence_zero_when_no_oil():
    detector = F1Detector()
    # Pre-release scene S1_EVT0001_00 has no oil
    res = detector.detect_scene(scene_id="S1_EVT0001_00")
    assert isinstance(res, SpillDetectionResult)
    if not res.oil_present:
        assert res.confidence == 0.0
