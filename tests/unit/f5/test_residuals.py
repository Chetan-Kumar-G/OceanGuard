"""Per-relationship residual computation."""
from __future__ import annotations

from backend.f5_consistency import residuals as res
from backend.f5_consistency.engine import evaluate


def test_f1f2_identical_position_and_time_supports(thr):
    scene = {
        "scene_id": "S1_EVT9999_00",
        "latitude": 37.0,
        "longitude": 20.0,
        "acquisition_timestamp": "2026-01-10T00:00:00Z",
    }
    state = {
        "observation_id": "EVT9999-OBS000",
        "centroid_lat": 37.0,
        "centroid_lon": 20.0,
        "timestamp": "2026-01-10T00:00:00Z",
    }
    rs = res.f1_detection_vs_f2_state(scene, state, thr)
    assert rs.constrained["spatial_residual_km"] == 0.0
    assert rs.constrained["temporal_residual_h"] == 0.0
    assert evaluate(rs, thr)[0] == "SUPPORTS"


def test_f1f2_missing_centroid_marks_missing(thr):
    scene = {"latitude": 37.0, "longitude": 20.0, "acquisition_timestamp": "2026-01-10T00:00:00Z"}
    state = {"timestamp": "2026-01-10T00:00:00Z"}  # no centroid
    rs = res.f1_detection_vs_f2_state(scene, state, thr)
    assert "spatial_residual_km" not in rs.constrained
    assert rs.missing
    assert evaluate(rs, thr)[0] == "UNKNOWN"


def test_f2f3_slick_speed_drift_within_forcing_envelope_supports(thr):
    # ~20 km over ~14 h ≈ 1.4 km/h — an oil slick, well under the forcing cap
    s0 = {"centroid_lat": 38.0, "centroid_lon": 18.3, "timestamp": "2026-01-13T13:49:27Z"}
    s1 = {"centroid_lat": 38.15, "centroid_lon": 18.32, "timestamp": "2026-01-14T03:24:19Z"}
    rs = res.f2_drift_vs_f3_forcing(s0, s1, {"wind_drift_factor": 0.032}, thr)
    assert rs.constrained["spatial_residual_km"] == 0.0
    assert rs.context["drift_residual_km"] > 0  # raw displacement still reported
    assert evaluate(rs, thr)[0] == "SUPPORTS"


def test_f2f3_vessel_like_speed_contradicts(thr):
    # ~60 km in 3 h = 20 km/h — no plausible current + wind-drift explains this
    s0 = {"centroid_lat": 37.0, "centroid_lon": 20.0, "timestamp": "2026-01-10T00:00:00Z"}
    s1 = {"centroid_lat": 37.54, "centroid_lon": 20.0, "timestamp": "2026-01-10T03:00:00Z"}
    rs = res.f2_drift_vs_f3_forcing(s0, s1, {}, thr)
    assert rs.constrained["spatial_residual_km"] >= thr.bound("contradict", "spatial_residual_km")
    assert evaluate(rs, thr)[0] == "CONTRADICTS"


def test_f3f4_close_and_timely_supports(thr):
    hyp = {"source_hypothesis_id": "EVT9999-HBEST", "origin_time_mid": "2026-01-13T08:00:00Z"}
    track = {
        "track_id": "EVT9999-111",
        "distance_to_source_effective_km": 2.0,
        "closest_approach_timestamp": "2026-01-13T10:00:00Z",
        "interpolated_closest_timestamp": "2026-01-13T10:00:00Z",
        "dark_gap_over_source": False,
        "course_compatibility": 0.9,
        "observed_speed_kn": 1.0,
        "slick_drift_speed_kn": 0.0,
        "ais_gap_ratio_origin_window": 0.05,
    }
    rs = res.f3_hypothesis_vs_f4_track(hyp, track, thr)
    assert rs.constrained["spatial_residual_km"] == 2.0
    assert rs.constrained["temporal_residual_h"] == 2.0
    assert rs.context["ais_gap_ratio"] == 0.05
    assert evaluate(rs, thr)[0] == "SUPPORTS"


def test_f3f4_far_source_contradicts(thr):
    hyp = {"source_hypothesis_id": "EVT9999-HBEST", "origin_time_mid": "2026-01-13T08:00:00Z"}
    track = {
        "track_id": "EVT9999-222",
        "distance_to_source_effective_km": 130.0,
        "closest_approach_timestamp": "2026-01-13T10:00:00Z",
        "dark_gap_over_source": False,
        "ais_gap_ratio_origin_window": 1.0,
    }
    rs = res.f3_hypothesis_vs_f4_track(hyp, track, thr)
    assert evaluate(rs, thr)[0] == "CONTRADICTS"


def test_f3f4_dark_gap_drops_temporal_from_verdict(thr):
    hyp = {"source_hypothesis_id": "EVT9999-HBEST", "origin_time_mid": "2026-01-13T08:00:00Z"}
    track = {
        "track_id": "EVT9999-333",
        "distance_to_source_effective_km": 1.0,
        "closest_approach_timestamp": "2026-01-12T18:00:00Z",  # 14h off — would be grey
        "dark_gap_over_source": True,
        "ais_gap_ratio_origin_window": 0.01,
    }
    rs = res.f3_hypothesis_vs_f4_track(hyp, track, thr)
    assert "temporal_residual_h" not in rs.constrained
    assert evaluate(rs, thr)[0] == "SUPPORTS"
    assert "dark over source" in evaluate(rs, thr)[1]
