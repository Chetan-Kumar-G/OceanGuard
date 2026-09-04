"""End-to-end smoke test: every feature (F1-F8) responds through the one
unified FastAPI app (``backend.app``) for the reference EVT0002 event."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_health_and_root():
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["features"] == ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"]
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200


def test_all_eight_features_respond_for_evt0002():
    assert client.post("/api/v1/f2/reconstruct/EVT0002").status_code == 200
    assert client.post("/api/v1/f3/hindcast/EVT0002").status_code == 200
    assert client.post("/api/v1/f4/reconstruct-ais/EVT0002").status_code == 200
    assert client.post("/f5/evaluate-consistency/EVT0002").status_code == 200
    assert client.post("/f6/rank/EVT0002").status_code == 200
    assert client.get("/events/EVT0002/graph").status_code == 200

    f8 = client.post(
        "/api/v1/f8/forecast/EVT0002",
        json={"n_ensemble": 6, "n_particles": 100, "horizons_h": [12, 24]},
    )
    assert f8.status_code == 200
    assert len(f8.json()["data"]) == 2

    replay = client.post(
        "/api/v1/f8/replay/EVT0002",
        json={"n_ensemble": 6, "n_particles": 100},
    )
    assert replay.status_code == 200
