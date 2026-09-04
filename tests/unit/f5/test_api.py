"""API contract smoke tests (Blueprint Part 8 + shared envelope)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.f5_consistency.app import create_app
from backend.f5_consistency.repository import EvidenceRepository
from backend.f5_consistency.router import set_repo


@pytest.fixture()
def client(tmp_path):
    repo = EvidenceRepository(url=f"sqlite:///{tmp_path / 'api.sqlite'}")
    set_repo(repo)
    with TestClient(create_app()) as test_client:
        yield test_client
    repo.dispose()


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_evaluate_then_list(client):
    post = client.post("/f5/evaluate-consistency/EVT0002")
    assert post.status_code == 200
    body = post.json()
    assert set(body) == {"data", "meta"}
    assert body["meta"]["run_id"].startswith("RUN_")
    assert body["meta"]["summary"]["total"] == len(body["data"]) > 0
    first = body["data"][0]
    assert set(first) == {
        "evidence_id",
        "event_id",
        "source_a_id",
        "source_a_type",
        "source_b_id",
        "source_b_type",
        "spatial_residual_km",
        "temporal_residual_h",
        "relation",
        "reason",
    }

    got = client.get("/events/EVT0002/evidence")
    assert got.status_code == 200
    assert got.json()["data"] == body["data"]


def test_invalid_event_id_returns_400_envelope(client):
    resp = client.post("/f5/evaluate-consistency/not-an-event")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_event_id"


def test_single_observation_event_returns_empty_with_reason(client):
    resp = client.post("/f5/evaluate-consistency/EVT0001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["meta"]["skipped_reason"]


def test_list_before_evaluate_is_empty(client):
    resp = client.get("/events/EVT0009/evidence")
    assert resp.status_code == 200
    assert resp.json()["data"] == []
