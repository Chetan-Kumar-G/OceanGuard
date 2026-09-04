from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.repository import AuthRepository, get_auth_repository
from backend.auth.router import router as auth_router


@pytest.fixture()
def repo(tmp_path):
    r = AuthRepository(url=f"sqlite:///{tmp_path / 'auth.sqlite'}")
    yield r
    r.dispose()


@pytest.fixture()
def client(repo):
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_auth_repository] = lambda: repo
    return TestClient(app)
