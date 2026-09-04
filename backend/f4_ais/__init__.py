"""Feature F4 - Historical AIS Vessel Reconstruction & Correlation.

Reconstructs vessel tracks from historical AIS transmissions and evaluates
spatio-temporal compatibility with F3 Lagrangian source hypotheses.
"""
from backend.f4_ais.agents import (
    AISIngestionAgent,
    CandidateFilteringAgent,
    CompatibilityAnalysisAgent,
    CorridorFilteringAgent,
    ProvenanceContractAgent,
    TrackReconstructionAgent,
)
from backend.f4_ais.corridor import (
    CorridorFilteringService,
    haversine_distance_km,
    is_spatially_compatible,
    is_temporally_compatible,
)
from backend.f4_ais.candidate import CandidateVesselService
from backend.f4_ais.compatibility import (
    CompatibilityAnalysisService,
    compute_circular_bearing_difference,
)
from backend.f4_ais.distance import DistanceAnalysisService
from backend.f4_ais.gap import DarkGapAnalysisService
from backend.f4_ais.ingestion import AISIngestionService
from backend.f4_ais.repository import F4Repository, get_f4_repository
from backend.f4_ais.router import router
from backend.f4_ais.schemas import (
    AISGapInterval,
    AISValidationIssue,
    AISValidationReport,
    ClosestApproachResult,
    CompatibilityResult,
    CorridorAISMatch,
    CorridorFilterResult,
    DarkGapResult,
    RawAISRecord,
    ReconstructionRequest,
    ValidatedAISFix,
    VesselTrack,
)
from backend.f4_ais.supervisor import F4AISSupervisor
from backend.f4_ais.track import TrackReconstructionService
from backend.f4_ais.validation import (
    AISValidationService,
    parse_utc_timestamp,
    validate_ais_record,
    validate_ais_stream,
)

__all__ = [
    "AISGapInterval",
    "AISIngestionAgent",
    "AISIngestionService",
    "AISValidationIssue",
    "AISValidationReport",
    "AISValidationService",
    "CandidateFilteringAgent",
    "CandidateVesselService",
    "ClosestApproachResult",
    "CompatibilityAnalysisAgent",
    "CompatibilityAnalysisService",
    "CompatibilityResult",
    "CorridorAISMatch",
    "CorridorFilterResult",
    "CorridorFilteringAgent",
    "CorridorFilteringService",
    "DarkGapAnalysisService",
    "DarkGapResult",
    "DistanceAnalysisService",
    "F4AISSupervisor",
    "F4Repository",
    "ProvenanceContractAgent",
    "RawAISRecord",
    "ReconstructionRequest",
    "TrackReconstructionAgent",
    "TrackReconstructionService",
    "ValidatedAISFix",
    "VesselTrack",
    "get_f4_repository",
    "haversine_distance_km",
    "is_spatially_compatible",
    "is_temporally_compatible",
    "parse_utc_timestamp",
    "router",
    "validate_ais_record",
    "validate_ais_stream",
]
