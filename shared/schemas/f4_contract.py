"""F4 Candidate Vessel contract reference."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class CandidateVessel(BaseModel):
    """F4 -> F5 CandidateVessel contract reference.

    Downstream representation produced by F4 from evaluating historical AIS
    tracks against F3's SourceHypothesisWindow.
    NEVER present this candidate as proven vessel attribution or legal culpability.
    """
    track_id: str = Field(..., description="Unique track ID: TRK_<event_id>_<mmsi>")
    event_id: str = Field(..., description="Spill event ID")
    mmsi: str = Field(..., description="Vessel MMSI as string")
    source_hypothesis_id: str = Field(..., description="F3 hypothesis ID evaluated against")
    distance_to_source_effective_km: float = Field(
        ..., ge=0.0, description="Effective minimum distance to source location in km"
    )
    temporal_compatibility: float = Field(
        ..., ge=0.0, le=1.0, description="Temporal alignment score [0, 1]"
    )
    track_overlap: float = Field(
        ..., ge=0.0, le=1.0, description="Spatial-temporal track overlap [0, 1]"
    )
    track_completeness: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of expected reports present [0, 1]"
    )
    dark_gap_over_source: bool = Field(
        ..., description="True if vessel went dark (AIS gap) while traversing the source window"
    )
    dark_gap_over_source_hours: float = Field(
        ..., ge=0.0, description="Duration in hours of dark gap overlapping the source window"
    )
    closest_approach_is_interpolated: bool = Field(
        ..., description="True if closest approach point came from interpolated rather than observed fix"
    )
    speed_compatibility: float = Field(
        ..., ge=0.0, le=1.0, description="Speed consistency with estimated slick drift [0, 1]"
    )
    course_compatibility: float = Field(
        ..., ge=0.0, le=1.0, description="Course consistency with estimated slick drift [0, 1]"
    )
    ais_gap_ratio_origin_window: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of origin window spent in an AIS gap [0, 1]"
    )

    # Optional provenance / audit fields
    vessel_type: Optional[str] = Field(None, description="Reported vessel category (Tanker, Cargo, etc.)")
    vessel_length: Optional[float] = Field(None, ge=0.0, description="Vessel length in meters")
    vessel_width: Optional[float] = Field(None, ge=0.0, description="Vessel beam/width in meters")
    draught: Optional[float] = Field(None, ge=0.0, description="Vessel draught in meters")
    first_timestamp: Optional[str] = Field(None, description="First observed transmission timestamp (UTC ISO-8601)")
    last_timestamp: Optional[str] = Field(None, description="Last observed transmission timestamp (UTC ISO-8601)")
    track_duration_h: Optional[float] = Field(None, ge=0.0, description="Total observed track duration in hours")
    number_of_observations: Optional[int] = Field(None, ge=0, description="Count of observed AIS transmissions")
    gap_count: Optional[int] = Field(None, ge=0, description="Number of transmission dropouts/gaps detected")
    max_gap_hours: Optional[float] = Field(None, ge=0.0, description="Maximum single gap duration in hours")
    distance_to_source_km: Optional[float] = Field(None, ge=0.0, description="Observed closest approach distance in km")
    distance_to_source_interpolated_km: Optional[float] = Field(
        None, ge=0.0, description="Interpolated closest approach distance in km"
    )
    closest_approach_timestamp: Optional[str] = Field(None, description="Timestamp of observed closest approach (UTC)")
    interpolated_closest_timestamp: Optional[str] = Field(None, description="Timestamp of interpolated closest approach (UTC)")
    observed_speed_kn: Optional[float] = Field(None, ge=0.0, description="Observed SOG at closest approach in knots")
    observed_course_deg: Optional[float] = Field(None, ge=0.0, le=360.0, description="Observed COG at closest approach in degrees")
    slick_drift_speed_kn: Optional[float] = Field(None, ge=0.0, description="Slick drift speed in knots used for comparison")
    slick_drift_course_deg: Optional[float] = Field(None, ge=0.0, le=360.0, description="Slick drift course in degrees used for comparison")
    closest_approach_lat: Optional[float] = Field(
        None, ge=-90.0, le=90.0, description="Latitude of the closest-approach AIS fix (map display only, never used in scoring)"
    )
    closest_approach_lon: Optional[float] = Field(
        None, ge=-180.0, le=180.0, description="Longitude of the closest-approach AIS fix (map display only, never used in scoring)"
    )
