from __future__ import annotations

import pytest

from backend.f5_consistency.config import load_thresholds
from backend.f5_consistency.repository import EvidenceRepository


@pytest.fixture()
def thr():
    """Thresholds from the real /shared config (the single source of truth)."""
    return load_thresholds()


@pytest.fixture()
def repo(tmp_path):
    """Isolated SQLite repo per test."""
    r = EvidenceRepository(url=f"sqlite:///{tmp_path / 'f5.sqlite'}")
    yield r
    r.dispose()


REFERENCE_EVENTS = [f"EVT{n:04d}" for n in range(2, 13)]  # EVT0002..EVT0012 (EVT0001 has 1 OBSERVED state)
