"""Persistence boundary repository for F4 (Candidate Vessels).

Provides thread-safe in-memory caching and retrieval of reconstructed
candidate vessels and tracks for downstream F5 consumption.
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional

from shared.schemas.f4_contract import CandidateVessel
from backend.f4_ais.schemas import CorridorAISMatch


class F4Repository:
    """Thread-safe in-memory repository for F4 outputs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._candidates: Dict[str, List[CandidateVessel]] = {}
        self._corridor_matches: Dict[str, Dict[str, List[CorridorAISMatch]]] = {}

    def save_candidates(self, event_id: str, candidates: List[CandidateVessel]) -> None:
        """Stores candidate vessels for an event."""
        with self._lock:
            self._candidates[event_id] = list(candidates)

    def get_candidates(self, event_id: str) -> List[CandidateVessel]:
        """Retrieves stored candidate vessels for an event. Returns empty list if none."""
        with self._lock:
            return list(self._candidates.get(event_id, []))

    def has_candidates(self, event_id: str) -> bool:
        """Checks if candidates are already stored for the event."""
        with self._lock:
            return event_id in self._candidates and len(self._candidates[event_id]) > 0

    def save_corridor_matches(
        self, event_id: str, hypothesis_id: str, matches: List[CorridorAISMatch]
    ) -> None:
        """Stores corridor AIS matches for an event and source hypothesis."""
        with self._lock:
            if event_id not in self._corridor_matches:
                self._corridor_matches[event_id] = {}
            self._corridor_matches[event_id][hypothesis_id] = list(matches)

    def get_corridor_matches(
        self, event_id: str, hypothesis_id: Optional[str] = None
    ) -> List[CorridorAISMatch]:
        """Retrieves stored corridor AIS matches.
        
        If hypothesis_id is provided, returns matches for that specific hypothesis.
        If hypothesis_id is None, returns all matches across all hypotheses for the event.
        """
        with self._lock:
            if event_id not in self._corridor_matches:
                return []
            if hypothesis_id is not None:
                return list(self._corridor_matches[event_id].get(hypothesis_id, []))
            all_matches: List[CorridorAISMatch] = []
            for m_list in self._corridor_matches[event_id].values():
                all_matches.extend(m_list)
            return all_matches

    def clear(self, event_id: Optional[str] = None) -> None:
        """Clears stored candidates and corridor matches for a specific event or all events if None."""
        with self._lock:
            if event_id is not None:
                self._candidates.pop(event_id, None)
                self._corridor_matches.pop(event_id, None)
            else:
                self._candidates.clear()
                self._corridor_matches.clear()


_REPO_INSTANCE: Optional[F4Repository] = None
_REPO_LOCK = threading.Lock()


def get_f4_repository() -> F4Repository:
    """Returns the singleton F4Repository instance."""
    global _REPO_INSTANCE
    with _REPO_LOCK:
        if _REPO_INSTANCE is None:
            _REPO_INSTANCE = F4Repository()
        return _REPO_INSTANCE
