"""HTTP-level tests for the vessel report endpoint."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.repository import AuthRepository, get_auth_repository
from backend.auth.router import router as auth_router
from backend.reports.router import router as reports_router


@pytest.fixture()
def client(tmp_path):
    repo = AuthRepository(url=f"sqlite:///{tmp_path / 'auth.sqlite'}")
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(reports_router)
    app.dependency_overrides[get_auth_repository] = lambda: repo
    c = TestClient(app)
    yield c
    repo.dispose()


@pytest.fixture()
def token(client):
    r = client.post(
        "/auth/register",
        json={"email": "investigator@oiltrace.example", "password": "supersecret1", "display_name": "Inv"},
    )
    return r.json()["access_token"]


def test_report_requires_authentication(client):
    assert client.get("/api/v1/reports/EVT0002/vessels.pdf").status_code == 401


def test_report_returns_a_pdf(client, token):
    r = client.get("/api/v1/reports/EVT0002/vessels.pdf", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "oiltrace-EVT0002-vessel-report.pdf" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF-")
