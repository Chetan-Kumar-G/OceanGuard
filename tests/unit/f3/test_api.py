"""Tests for F3 FastAPI Router Endpoints."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.f3_hindcast.router import router


def _create_test_app() -> FastAPI:
    app = FastAPI(title="Test App")
    app.include_router(router)
    return app


def test_post_run_hindcast_endpoint():
    """Verifies POST /api/v1/f3/hindcast/{event_id} triggers execution and returns ApiResponse envelope."""
    app = _create_test_app()
    client = TestClient(app)

    resp = client.post("/api/v1/f3/hindcast/EVT0001", json={"base_seed": 42})
    assert resp.status_code == 200
    body = resp.json()

    # Check envelope
    assert "data" in body
    assert "meta" in body
    assert "run_id" in body["meta"]
    assert "generated_at" in body["meta"]

    # Check payload
    data = body["data"]
    assert len(data) == 7
    hbest = next(h for h in data if h["source_hypothesis_id"] == "SH_EVT0001_HBEST")
    assert hbest["uncertainty_radius_km"] > 0.0
    assert hbest["source_probability"] == 1.0


def test_get_source_hypotheses_endpoint():
    """Verifies GET /api/v1/events/{event_id}/source-hypotheses returns candidate list."""
    app = _create_test_app()
    client = TestClient(app)

    resp = client.get("/api/v1/events/EVT0001/source-hypotheses")
    assert resp.status_code == 200
    body = resp.json()

    assert "data" in body
    assert "meta" in body
    data = body["data"]
    assert len(data) == 7


def test_get_best_hypothesis_endpoint():
    """Verifies GET /api/v1/f3/hindcast/{event_id}/best returns specifically the HBEST window."""
    app = _create_test_app()
    client = TestClient(app)

    resp = client.get("/api/v1/f3/hindcast/EVT0001/best")
    assert resp.status_code == 200
    body = resp.json()

    assert "data" in body
    assert "meta" in body
    best_data = body["data"]
    assert best_data["source_hypothesis_id"] == "SH_EVT0001_HBEST"
    assert best_data["event_id"] == "EVT0001"
    assert best_data["uncertainty_radius_km"] > 0.0
    assert "lat" in best_data["source_location"]
    assert "lon" in best_data["source_location"]


def test_nonexistent_event_returns_404():
    """Verifies that non-existent event triggers appropriate HTTP 404 error."""
    app = _create_test_app()
    client = TestClient(app)

    resp = client.get("/api/v1/f3/hindcast/EVT_NONEXISTENT_9999/best")
    assert resp.status_code == 404
