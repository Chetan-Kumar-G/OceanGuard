from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.appeals.repository import AppealsRepository, get_appeals_repository
from backend.appeals.router import router as appeals_router
from backend.auth.repository import AuthRepository, get_auth_repository
from backend.auth.router import router as auth_router


@pytest.fixture()
def auth_repo(tmp_path):
    r = AuthRepository(url=f"sqlite:///{tmp_path / 'auth.sqlite'}")
    yield r
    r.dispose()


@pytest.fixture()
def appeals_repo(tmp_path):
    r = AppealsRepository(url=f"sqlite:///{tmp_path / 'appeals.sqlite'}")
    yield r
    r.dispose()


@pytest.fixture()
def client(auth_repo, appeals_repo):
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(appeals_router)
    app.dependency_overrides[get_auth_repository] = lambda: auth_repo
    app.dependency_overrides[get_appeals_repository] = lambda: appeals_repo
    return TestClient(app)


@pytest.fixture()
def investigator_token(client):
    r = client.post("/auth/register", json={"email": "investigator@oceanguard.example", "password": "supersecret1", "display_name": "Inv"})
    return r.json()["access_token"]
