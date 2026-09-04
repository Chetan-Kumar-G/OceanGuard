"""F5 — Cross-Source Consistency & Evidence Conflict Detection.

Compares already-derived evidence (F1/F2 observations, F3 hypotheses, F4 tracks)
for one event and labels every relevant pair SUPPORTS / CONTRADICTS / UNKNOWN,
preserving provenance. Never collapses disagreement into a false consensus.
"""
from .models import EvidenceRelation, EvidenceRelationRecord, RelationKind
from .service import evaluate_consistency

__all__ = [
    "EvidenceRelation",
    "EvidenceRelationRecord",
    "RelationKind",
    "evaluate_consistency",
]
