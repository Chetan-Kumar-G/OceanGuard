"""
backend/f6_ranking/models.py
Pydantic models for F6 hypothesis scoring output.
Schema matches the hypothesis_scores DB table and D6_evidence_ranking.csv.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


ConfidenceBand = Literal["high", "medium", "low"]


class HypothesisScore(BaseModel):
    """One ranked candidate hypothesis per event.  Maps 1-to-1 to a DB row."""

    hypothesis_id: str = Field(..., description="HYP_<event_id>_<mmsi>")
    event_id: str
    candidate_mmsi: str

    rank: int = Field(..., ge=1, description="1 = most likely source for the event")
    final_score: float = Field(..., ge=0.0, le=1.0)
    confidence_band: ConfidenceBand

    event_insufficient_evidence: bool = Field(
        ...,
        description=(
            "True when top score < min_final_score, evidence < min_evidence_items, "
            "or margin_to_next < min_margin."
        ),
    )

    explanation: str = Field(..., description="Component-wise breakdown string")

    # Component scores (kept for transparency / DB storage)
    source_probability: float = 0.0
    spatial_compatibility: float = 0.0
    temporal_compatibility: float = 0.0
    drift_compatibility: float = 0.0
    ais_completeness: float = 0.0
    behavioural_score: float = 0.0
    sensor_confidence: float = 0.0

    # Evidence tally
    support_count: int = 0
    contradiction_count: int = 0
    unknown_count: int = 0
    n_evidence_items: int = 0

    # Quality
    data_quality_weight: float = 0.0
    margin_to_next: float = 0.0

    # Provenance
    is_true_source: Optional[bool] = None          # populated when ground truth available
    vessel_type: Optional[str] = None
    distance_to_source_km: Optional[float] = None
    dark_gap_over_source: Optional[bool] = None
    closest_approach_is_interpolated: Optional[bool] = None
    source_hypothesis_id: Optional[str] = None


class RankingResult(BaseModel):
    """Full ranking for one event."""
    event_id: str
    candidates: list[HypothesisScore]
    event_insufficient_evidence: bool
    n_candidates: int
