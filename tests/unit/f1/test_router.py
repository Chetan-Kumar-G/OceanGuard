from fastapi.testclient import TestClient
import pytest

from backend.api.main import app

client = TestClient(app)


def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_detect_scene_nominal():
    payload = {
        "scene_id": "S1_EVT0001_01",
    }
    response = client.post("/api/v1/f1/detect", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert "run_id" in body["meta"]

    data = body["data"]
    assert data["scene_id"] == "S1_EVT0001_01"
    assert data["event_id"] == "EVT0001"
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["oil_present"], bool)
    assert isinstance(data["lookalike_present"], bool)
    assert "polygon_geojson" in data


def test_api_list_event_observations():
    response = client.get("/api/v1/events/EVT0001/observations")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0
    first_obs = body["data"][0]
    assert first_obs["event_id"] == "EVT0001"
