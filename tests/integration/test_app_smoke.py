"""End-to-end smoke test: every feature (F1-F8) responds through the one
unified FastAPI app (``backend.app``) for the reference EVT0002 event, plus
auth gating, appeals, and the media mount.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.appeals.repository import AppealsRepository, get_appeals_repository
from backend.auth.repository import AuthRepository, get_auth_repository

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_dbs(tmp_path):
    """Every test in this module gets its own auth/appeals SQLite file, so a
    'first user becomes admin' assumption never collides across test runs."""
    auth_repo = AuthRepository(url=f"sqlite:///{tmp_path / 'auth.sqlite'}")
    appeals_repo = AppealsRepository(url=f"sqlite:///{tmp_path / 'appeals.sqlite'}")
    app.dependency_overrides[get_auth_repository] = lambda: auth_repo
    app.dependency_overrides[get_appeals_repository] = lambda: appeals_repo
    yield
    app.dependency_overrides.clear()
    auth_repo.dispose()
    appeals_repo.dispose()


def _auth_headers() -> dict[str, str]:
    r = client.post(
        "/auth/register",
        json={"email": "smoke@investigators.example", "password": "supersecret1", "display_name": "Smoke Tester"},
    )
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health_and_root():
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["features"] == ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"]
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200


def test_investigation_endpoints_require_authentication():
    assert client.post("/api/v1/f3/hindcast/EVT0002").status_code == 401
    assert client.get("/events/EVT0002/graph").status_code == 401


def test_all_eight_features_respond_for_evt0002():
    headers = _auth_headers()

    assert client.post("/api/v1/f2/reconstruct/EVT0002", headers=headers).status_code == 200
    assert client.post("/api/v1/f3/hindcast/EVT0002", headers=headers).status_code == 200
    assert client.post("/api/v1/f4/reconstruct-ais/EVT0002", headers=headers).status_code == 200
    assert client.post("/f5/evaluate-consistency/EVT0002", headers=headers).status_code == 200
    assert client.post("/f6/rank/EVT0002", headers=headers).status_code == 200
    assert client.get("/events/EVT0002/graph", headers=headers).status_code == 200

    f8 = client.post(
        "/api/v1/f8/forecast/EVT0002",
        json={"n_ensemble": 6, "n_particles": 100, "horizons_h": [12, 24]},
        headers=headers,
    )
    assert f8.status_code == 200
    assert len(f8.json()["data"]) == 2

    replay = client.post(
        "/api/v1/f8/replay/EVT0002",
        json={"n_ensemble": 6, "n_particles": 100},
        headers=headers,
    )
    assert replay.status_code == 200


def test_appeal_lifecycle_through_the_unified_app():
    headers = _auth_headers()

    submitted = client.post(
        "/appeals",
        json={
            "event_id": "EVT0002",
            "subject": "candidate_vessel",
            "mmsi": "480469227",
            "contact_name": "Capt. Smith",
            "contact_email": "capt@ship.example",
            "statement": "We were docked the entire time; AIS logs attached separately.",
        },
    )
    assert submitted.status_code == 201
    appeal_id = submitted.json()["id"]

    assert client.get("/appeals").status_code == 401  # review queue is investigator-only
    listed = client.get("/appeals", headers=headers)
    assert listed.status_code == 200
    assert any(a["id"] == appeal_id for a in listed.json())

    reviewed = client.patch(
        f"/appeals/{appeal_id}/review",
        json={"status": "dismissed", "notes": "AIS confirms vessel in port."},
        headers=headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "dismissed"


def test_media_mount_serves_satellite_quicklooks():
    r = client.get("/media/quicklook/S1_EVT0002_00.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
