"""Unit tests for F4 supervisor foundation, empty AIS behavior, and API endpoints.

Covers:
- Test F: Empty AIS does not crash (returns empty candidate list gracefully)
- Test J: FastAPI endpoints and ApiResponse envelope structure
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.schemas.f3_contract import SourceHypothesisWindow
from shared.schemas.f4_contract import CandidateVessel
from backend.f4_ais.repository import get_f4_repository
from backend.f4_ais.router import router
from backend.f4_ais.supervisor import F4AISSupervisor


def _create_test_app() -> FastAPI:
    app = FastAPI(title="F4 Test App")
    app.include_router(router)
    return app


def test_empty_ais_handling_does_not_crash():
    """Test F: Verifies empty raw AIS does not raise exceptions or return HTTP 500."""
    supervisor = F4AISSupervisor()
    hypothesis = SourceHypothesisWindow.model_validate({
        "source_hypothesis_id": "SH_EVT0099_HBEST",
        "event_id": "EVT0099",
        "source_location": {"lat": 36.0, "lon": 20.0},
        "origin_time_start": "2026-01-08T00:00:00Z",
        "origin_time_end": "2026-01-08T04:00:00Z",
        "uncertainty_radius_km": 10.0,
        "source_probability": 1.0,
    })

    # Pass empty raw records
    candidates = supervisor.execute_reconstruction(
        event_id="EVT0099",
        hypothesis=hypothesis,
        raw_records=[],
    )
    assert candidates == []

    # Persistence should reflect empty candidate list
    stored = supervisor.get_candidate_vessels("EVT0099")
    assert stored == []


def test_post_reconstruct_ais_endpoint():
    """Test J1: Verifies POST /api/v1/f4/reconstruct-ais/{event_id} triggers correlation and returns ApiResponse envelope."""
    app = _create_test_app()
    client = TestClient(app)

    resp = client.post("/api/v1/f4/reconstruct-ais/EVT0001")
    assert resp.status_code == 200
    body = resp.json()

    # Check envelope
    assert "data" in body
    assert "meta" in body
    assert "run_id" in body["meta"]
    assert "generated_at" in body["meta"]

    # Check payload
    data = body["data"]
    assert len(data) > 0
    first = data[0]
    assert first["event_id"] == "EVT0001"
    assert first["track_id"].startswith("TRK_EVT0001_")
    assert "distance_to_source_effective_km" in first
    assert "temporal_compatibility" in first
    assert "dark_gap_over_source" in first
    assert "dark_gap_over_source_hours" in first
    assert "speed_compatibility" in first
    assert "course_compatibility" in first
    assert "ais_gap_ratio_origin_window" in first


def test_get_vessel_tracks_endpoint():
    """Test J2: Verifies GET /api/v1/events/{event_id}/vessel-tracks returns candidate list."""
    app = _create_test_app()
    client = TestClient(app)

    resp = client.get("/api/v1/events/EVT0001/vessel-tracks")
    assert resp.status_code == 200
    body = resp.json()

    assert "data" in body
    assert "meta" in body
    data = body["data"]
    assert len(data) > 0
    assert data[0]["event_id"] == "EVT0001"
