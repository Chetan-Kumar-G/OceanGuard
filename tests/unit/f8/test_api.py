"""FastAPI surface for F8: envelope shape, happy path, graceful failure."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.f8_forecast.router as f8_router_mod
from backend.f8_forecast.repository import F8Repository
from backend.f8_forecast.router import router
from backend.f8_forecast.supervisor import F8ForecastSupervisor


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(f8_router_mod, "_supervisor", F8ForecastSupervisor(repository=F8Repository()))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_post_forecast_returns_runs(client):
    resp = client.post("/api/v1/f8/forecast/EVT0002", json={"n_ensemble": 6, "n_particles": 100, "horizons_h": [12, 24]})
    assert resp.status_code == 200
    body = resp.json()
    assert "meta" in body and "run_id" in body["meta"]
    assert len(body["data"]) == 2
    assert {r["forecast_horizon_hours"] for r in body["data"]} == {12.0, 24.0}


def test_get_forecast_auto_runs_when_absent(client):
    resp = client.get("/api/v1/events/EVT0002/forecast")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) > 0


def test_get_particles_and_impact(client):
    client.post("/api/v1/f8/forecast/EVT0002", json={"n_ensemble": 6, "n_particles": 100, "horizons_h": [12]})
    particles = client.get("/api/v1/f8/forecast/EVT0002/particles")
    impact = client.get("/api/v1/f8/forecast/EVT0002/impact")
    assert particles.status_code == 200 and len(particles.json()["data"]) > 0
    assert impact.status_code == 200
    assert impact.json()["data"][0]["forecast_id"]


def test_post_replay_returns_evaluations(client):
    resp = client.post("/api/v1/f8/replay/EVT0002", json={"n_ensemble": 6, "n_particles": 100})
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_forecast_for_unknown_event_is_a_400_envelope(client):
    resp = client.post("/api/v1/f8/forecast/EVT9999", json={})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "FORECAST_EXECUTION_FAILED"


def test_get_forecast_for_unknown_event_is_a_404_envelope(client):
    resp = client.get("/api/v1/events/EVT9999/forecast")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "FORECAST_NOT_FOUND"
