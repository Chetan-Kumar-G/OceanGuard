"""Master orchestrator supervisor for Feature F4 (Historical AIS Reconstruction).

Coordinates deterministic specialist agents, executes spatio-temporal correlation,
enforces QA quarantine, and persists results in the F4 repository.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from shared.config.settings import get_settings
from shared.mocks.load_mock import load_mock
from shared.schemas.f3_contract import SourceHypothesisWindow
from shared.schemas.f4_contract import CandidateVessel
from backend.f4_ais.agents import (
    AISIngestionAgent,
    CandidateFilteringAgent,
    CompatibilityAnalysisAgent,
    ProvenanceContractAgent,
    TrackReconstructionAgent,
)
from backend.f4_ais.candidate import CandidateVesselService
from backend.f4_ais.repository import F4Repository, get_f4_repository
from backend.f4_ais.schemas import (
    CorridorFilterResult,
    RawAISRecord,
    ValidatedAISFix,
)


class F4AISSupervisor:
    """Supervisor orchestrating the F4 Historical AIS Reconstruction pipeline."""

    def __init__(self, repository: Optional[F4Repository] = None):
        self.repo = repository or get_f4_repository()
        self.ingestion_agent = AISIngestionAgent()
        self.filtering_agent = CandidateFilteringAgent()
        self.reconstruction_agent = TrackReconstructionAgent()
        self.compatibility_agent = CompatibilityAnalysisAgent()
        self.provenance_agent = ProvenanceContractAgent()
        self.candidate_service = CandidateVesselService()

    def resolve_source_hypothesis(
        self, event_id: str, hypothesis: Optional[SourceHypothesisWindow] = None
    ) -> SourceHypothesisWindow:
        """Resolves the F3 SourceHypothesisWindow for the event.

        If not explicitly supplied, retrieves the HBEST hypothesis from the frozen F3 mock.
        """
        if hypothesis is not None:
            return hypothesis

        # Fallback to shared mock F3
        f3_hypotheses = load_mock("f3", event_id)
        if not f3_hypotheses:
            raise ValueError(f"No F3 source hypotheses available for event {event_id}")

        # Prefer HBEST if present
        hbest_match = next(
            (h for h in f3_hypotheses if h.get("source_hypothesis_id", "").endswith("_HBEST")),
            f3_hypotheses[0]
        )
        return SourceHypothesisWindow.model_validate(hbest_match)

    def filter_corridor(
        self,
        event_id: str,
        hypothesis: Optional[SourceHypothesisWindow] = None,
        raw_records: Optional[Sequence[Union[Dict[str, Any], RawAISRecord]]] = None,
    ) -> CorridorFilterResult:
        """Executes F4.2 corridor filtering for an event and source hypothesis.
        
        Bridges the F3 source hypothesis window and the global AIS stream,
        persists matches in the F4 repository, and returns explicit filter counts.
        """
        src_hyp = self.resolve_source_hypothesis(event_id, hypothesis)
        if raw_records is not None:
            fixes, report = self.ingestion_agent.ingest_records(raw_records)
        else:
            settings = get_settings()
            csv_path = settings.D4_AIS_RAW_CSV_PATH
            if csv_path.exists():
                fixes, report = self.ingestion_agent.ingest_from_csv(csv_path)
            else:
                fixes, report = [], None

        result = self.filtering_agent.filter_corridor(fixes, src_hyp)
        self.repo.save_corridor_matches(event_id, src_hyp.source_hypothesis_id, result.matches)
        return result

    def execute_reconstruction(
        self,
        event_id: str,
        hypothesis: Optional[SourceHypothesisWindow] = None,
        raw_records: Optional[Sequence[Union[Dict[str, Any], RawAISRecord]]] = None,
    ) -> List[CandidateVessel]:
        """Executes the full deterministic F4 historical AIS reconstruction pipeline for an event.

        Flow:
            F3 SourceHypothesisWindow
                     ↓
            F4.1 AIS Ingestion & Validation
                     ↓
            F4.2 Spatio-Temporal Corridor Filtering
                     ↓
            F4.3 Vessel Track Reconstruction & Gap Detection
                     ↓
            F4.4 Closest Approach & Distance Analysis
                     ↓
            F4.5 AIS Dark-Gap Over Source Evaluation
                     ↓
            F4.6 Temporal, Speed, and Course Compatibility
                     ↓
            F4.7 CandidateVessel Contract Assembly
                     ↓
            F4 Persistence
        """
        # 1. Resolve F3 input contract
        src_hyp = self.resolve_source_hypothesis(event_id, hypothesis)

        # 2. Ingest & validate raw AIS
        if raw_records is not None:
            fixes, report = self.ingestion_agent.ingest_records(raw_records)
        else:
            settings = get_settings()
            csv_path = settings.D4_AIS_RAW_CSV_PATH
            if csv_path.exists():
                fixes, report = self.ingestion_agent.ingest_from_csv(csv_path)
            else:
                fixes, report = [], None

        # 3. Handle empty AIS condition gracefully
        if not fixes:
            self.repo.save_candidates(event_id, [])
            return []

        # 4. Spatio-temporal corridor filtering
        corridor_result = self.filtering_agent.filter_corridor(fixes, src_hyp)
        self.repo.save_corridor_matches(event_id, src_hyp.source_hypothesis_id, corridor_result.matches)

        filtered_fixes = self.filtering_agent.filter_fixes(fixes, src_hyp)
        active_fixes = corridor_result.matches if corridor_result.matches else filtered_fixes
        if not active_fixes:
            self.repo.save_candidates(event_id, [])
            return []

        # 5. Track reconstruction (group by MMSI, sort chronologically, detect gaps)
        target_mmsis = set(f.mmsi for f in active_fixes)

        # [UNRESOLVED — TRACK RECONSTRUCTION CONTEXT WINDOW]
        # Upstream specifications do not define the temporal buffer around the F3 origin window
        # for retrieving vessel track context to detect entry/exit gaps.
        # MVP ASSUMPTION: Deterministically bound track context to [origin_start - 24h, origin_end + 24h].
        from datetime import timedelta
        from backend.f4_ais.validation import parse_utc_timestamp
        t_start = parse_utc_timestamp(src_hyp.origin_time_start)
        t_end = parse_utc_timestamp(src_hyp.origin_time_end)
        ctx_buffer = timedelta(hours=24.0)
        t_ctx_start = t_start - ctx_buffer
        t_ctx_end = t_end + ctx_buffer

        relevant_fixes = [
            f for f in fixes
            if f.mmsi in target_mmsis
            and (t_ctx_start <= (f.timestamp_utc if f.timestamp_utc.tzinfo else f.timestamp_utc.replace(tzinfo=timezone.utc)) <= t_ctx_end)
        ]
        tracks = self.reconstruction_agent.build_tracks(
            fixes=relevant_fixes,
            event_id=event_id,
            hypothesis_id=src_hyp.source_hypothesis_id,
        )

        # 6. Candidate vessel generation through deterministic domain services (F4.4 - F4.7)
        candidates = self.candidate_service.generate_candidate_vessels(
            tracks=tracks,
            hypothesis=src_hyp,
        )

        # 7. Persist candidates in repository
        self.repo.save_candidates(event_id, candidates)
        return candidates

    def get_candidate_vessels(self, event_id: str) -> List[CandidateVessel]:
        """Retrieves stored candidate vessels for an event."""
        return self.repo.get_candidates(event_id)

    def has_candidate_vessels(self, event_id: str) -> bool:
        """Checks if candidates are already cached in the repository."""
        return self.repo.has_candidates(event_id)
