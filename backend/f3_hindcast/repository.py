"""Repository for persisting F3 Source Hypotheses and Environmental States."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from shared.config.settings import get_settings
from shared.schemas.f3_contract import EnvironmentalStateSnapshot, SourceHypothesisWindow


class F3Repository:
    """In-memory and file-backed repository for F3 artifacts.

    Persists source_hypotheses and environmental_states while avoiding database
    table bloat by keeping detailed particle trajectories in audit storage.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self._hypotheses_store: Dict[str, List[SourceHypothesisWindow]] = {}
        self._env_states_store: Dict[str, List[EnvironmentalStateSnapshot]] = {}
        self._trajectories_store: Dict[str, List[Dict[str, Any]]] = {}

        if storage_dir is None:
            settings = get_settings()
            self.storage_dir = settings.DATA_DIR / "f3_audit"
        else:
            self.storage_dir = storage_dir

    def save_hypotheses(self, event_id: str, hypotheses: List[SourceHypothesisWindow]) -> None:
        """Stores source hypotheses for an event."""
        self._hypotheses_store[event_id] = list(hypotheses)

    def get_hypotheses(self, event_id: str) -> List[SourceHypothesisWindow]:
        """Retrieves source hypotheses for an event."""
        return list(self._hypotheses_store.get(event_id, []))

    def save_environmental_states(self, event_id: str, states: List[EnvironmentalStateSnapshot]) -> None:
        """Stores environmental state provenance snapshots for an event."""
        self._env_states_store[event_id] = list(states)

    def get_environmental_states(self, event_id: str) -> List[EnvironmentalStateSnapshot]:
        """Retrieves environmental state provenance snapshots for an event."""
        return list(self._env_states_store.get(event_id, []))

    def save_trajectories(self, event_id: str, trajectories: List[Dict[str, Any]]) -> None:
        """Stores particle trajectory audit points."""
        self._trajectories_store[event_id] = list(trajectories)
        # File-backed audit export
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            out_file = self.storage_dir / f"{event_id}_particles.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(trajectories, f)
        except Exception:
            pass  # In-memory storage remains available

    def get_trajectories(self, event_id: str) -> List[Dict[str, Any]]:
        """Retrieves particle trajectory audit points."""
        return list(self._trajectories_store.get(event_id, []))

    def clear(self) -> None:
        """Clears in-memory stores (useful for testing)."""
        self._hypotheses_store.clear()
        self._env_states_store.clear()
        self._trajectories_store.clear()


_default_repo = F3Repository()


def get_f3_repository() -> F3Repository:
    """Returns singleton repository instance."""
    return _default_repo
