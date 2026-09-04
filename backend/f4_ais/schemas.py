"""Internal schemas and data transfer models for Feature F4 (AIS Reconstruction)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from shared.schemas.f3_contract import SourceHypothesisWindow
from shared.schemas.f4_contract import CandidateVessel


class RawAISRecord(BaseModel):
    """Direct representation of an unparsed AIS transmission record."""
    mmsi: Any
    timestamp: str
    latitude: Any
    longitude: Any
    sog_kn: Optional[Any] = None
    cog_deg: Optional[Any] = None
    heading_deg: Optional[Any] = None
    nav_status: Optional[str] = None
    vessel_type: Optional[str] = None
    vessel_length: Optional[Any] = None
    vessel_width: Optional[Any] = None
    draught: Optional[Any] = None
    source: Optional[str] = "AIS-terrestrial"
    is_observed: Optional[Any] = True
    sim_hours: Optional[Any] = None


class ValidatedAISFix(BaseModel):
    """Normalized, validated AIS fix adhering to UTC and EPSG:4326 standards."""
    mmsi: str = Field(..., description="9-digit normalized MMSI string")
    timestamp_utc: datetime = Field(..., description="Parsed UTC ISO-8601 timestamp")
    timestamp_iso: str = Field(..., description="Canonical UTC ISO-8601 string ending in Z")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    sog_kn: Optional[float] = Field(None, ge=0.0, le=102.2, description="Speed over ground in knots or None if unavailable")
    cog_deg: Optional[float] = Field(None, ge=0.0, le=360.0, description="Course over ground in degrees [0, 360] or None if unavailable")
    heading_deg: Optional[float] = Field(None, description="True heading in degrees [0, 360] or 511 if unavailable")
    nav_status: Optional[str] = Field("UnderWayUsingEngine", description="Navigational status")
    vessel_type: Optional[str] = Field(None, description="Vessel category (Tanker, Cargo, etc.)")
    vessel_length: Optional[float] = Field(None, ge=0.0, description="Vessel length in meters")
    vessel_width: Optional[float] = Field(None, ge=0.0, description="Vessel beam/width in meters")
    draught: Optional[float] = Field(None, ge=0.0, description="Vessel draught in meters")
    source: str = Field("AIS-terrestrial", description="Transmission source as reported in raw AIS record")
    is_observed: bool = Field(True, description="Observation status: True for observed records, False for non-observed records")
    sim_hours: Optional[float] = Field(None, description="Simulation hours offset if present")


class AISValidationIssue(BaseModel):
    """Audit log entry for an invalid or flagged raw AIS record."""
    row_index: int
    mmsi: Optional[str] = None
    field_name: str
    raw_value: Any
    reason: str


class AISValidationReport(BaseModel):
    """Aggregated report of raw AIS validation."""
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    issues: List[AISValidationIssue] = Field(default_factory=list)


class VesselTrack(BaseModel):
    """Chronologically ordered collection of fixes for a single vessel (MMSI)."""
    mmsi: str
    track_id: Optional[str] = None
    event_id: Optional[str] = None
    source_hypothesis_id: Optional[str] = None
    fixes: List[Union[CorridorAISMatch, ValidatedAISFix]] = Field(default_factory=list)
    vessel_type: Optional[str] = None
    vessel_length: Optional[float] = None
    vessel_width: Optional[float] = None
    draught: Optional[float] = None
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    duration_hours: float = 0.0
    observation_count: int = 0
    non_observation_count: int = 0
    gap_count: int = 0
    max_gap_hours: float = 0.0
    track_completeness: float = 0.0


class ReconstructionRequest(BaseModel):
    """Request payload for triggering F4 historical AIS reconstruction."""
    source_hypothesis: Optional[SourceHypothesisWindow] = Field(
        None, description="Optional explicit F3 SourceHypothesisWindow. If omitted, loaded from F3 supervisor/mock."
    )
    search_buffer_km: Optional[float] = Field(
        None, ge=0.0, description="Optional spatial search buffer beyond uncertainty radius in km"
    )


class CorridorAISMatch(BaseModel):
    """An AIS fix associated with a specific F3 SourceHypothesisWindow via spatio-temporal corridor matching."""
    event_id: str = Field(..., description="Spill event ID from the SourceHypothesisWindow")
    source_hypothesis_id: str = Field(..., description="F3 hypothesis ID matched against")
    mmsi: str = Field(..., description="Vessel MMSI as 9-digit string")
    timestamp_utc: datetime = Field(..., description="Parsed UTC timestamp")
    timestamp_iso: str = Field(..., description="Canonical UTC ISO-8601 string ending in Z")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    distance_to_source_km: float = Field(..., ge=0.0, description="Geodesic distance to hypothesis source location in km")
    sog_kn: Optional[float] = Field(None, ge=0.0, le=102.2, description="Speed over ground in knots or None if unavailable")
    cog_deg: Optional[float] = Field(None, ge=0.0, le=360.0, description="Course over ground in degrees [0, 360] or None if unavailable")
    heading_deg: Optional[float] = Field(None, description="True heading in degrees [0, 360] or 511 if unavailable")
    nav_status: Optional[str] = Field("UnderWayUsingEngine", description="Navigational status")
    vessel_type: Optional[str] = Field(None, description="Vessel category (Tanker, Cargo, etc.)")
    vessel_length: Optional[float] = Field(None, ge=0.0, description="Vessel length in meters")
    vessel_width: Optional[float] = Field(None, ge=0.0, description="Vessel beam/width in meters")
    draught: Optional[float] = Field(None, ge=0.0, description="Vessel draught in meters")
    source: str = Field("AIS-terrestrial", description="Transmission source as reported in raw AIS record")
    is_observed: bool = Field(True, description="Observation status: True for observed records, False for non-observed records")
    sim_hours: Optional[float] = Field(None, description="Simulation hours offset if present")


class CorridorFilterResult(BaseModel):
    """Result summary of filtering AIS records against a SourceHypothesisWindow."""
    event_id: str = Field(..., description="Spill event ID")
    source_hypothesis_id: str = Field(..., description="F3 hypothesis ID evaluated against")
    total_ais_input: int = Field(..., ge=0, description="Total count of input AIS records evaluated")
    spatial_matches: int = Field(..., ge=0, description="Number of AIS fixes within uncertainty radius")
    temporal_matches: int = Field(..., ge=0, description="Number of AIS fixes within origin time window")
    corridor_matches: int = Field(..., ge=0, description="Number of AIS fixes satisfying both spatial and temporal criteria")
    matches: List[CorridorAISMatch] = Field(default_factory=list, description="Retained corridor-matching AIS fixes")


class ClosestApproachResult(BaseModel):
    """F4.4 Closest Approach / Distance Analysis result for a vessel track against a source hypothesis."""
    mmsi: str
    track_id: Optional[str] = None
    event_id: Optional[str] = None
    source_hypothesis_id: Optional[str] = None
    distance_to_source_observed_km: Optional[float] = None
    distance_to_source_interpolated_km: Optional[float] = None
    distance_to_source_effective_km: float = 9999.0
    closest_approach_is_interpolated: bool = False
    closest_approach_timestamp: Optional[str] = None
    interpolated_closest_timestamp: Optional[str] = None
    closest_observed_sog_kn: Optional[float] = None
    closest_observed_cog_deg: Optional[float] = None
    # Position of the closest-approach fix (the one distance_to_source_effective_km
    # is measured from) - additive, for map display only. Never used in scoring.
    closest_approach_lat: Optional[float] = None
    closest_approach_lon: Optional[float] = None


class AISGapInterval(BaseModel):
    """Explicit audit record of an identified AIS reporting gap between consecutive observed fixes."""
    start_timestamp: str = Field(..., description="UTC ISO timestamp of transmission immediately preceding the gap")
    end_timestamp: str = Field(..., description="UTC ISO timestamp of transmission immediately succeeding the gap")
    duration_hours: float = Field(..., ge=0.0, description="Duration of reporting gap in hours")
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    overlaps_origin_window: bool = Field(False, description="True if gap interval intersects F3 origin time window")
    is_over_source: bool = Field(False, description="True if gap trajectory passes within source uncertainty region")
    overlap_hours: float = Field(0.0, ge=0.0, description="Hours of gap intersecting the origin window")


class DarkGapResult(BaseModel):
    """F4.5 AIS Gap / Dark-Gap evidence evaluation for a vessel track."""
    mmsi: str
    track_id: Optional[str] = None
    event_id: Optional[str] = None
    source_hypothesis_id: Optional[str] = None
    dark_gap_over_source: bool = Field(False, description="True if vessel had an AIS gap over source during origin window")
    dark_gap_over_source_hours: float = Field(0.0, ge=0.0, description="Duration in hours of dark gap overlapping source")
    total_gaps: int = Field(0, ge=0, description="Total number of reporting gaps detected along track")
    max_gap_hours: float = Field(0.0, ge=0.0, description="Maximum single gap duration in hours")
    gap_intervals: List[AISGapInterval] = Field(default_factory=list, description="Auditable list of detected reporting gaps")


class CompatibilityResult(BaseModel):
    """F4.6 Temporal, Speed, Course, and Gap compatibility evidence features."""
    mmsi: str
    track_id: Optional[str] = None
    event_id: Optional[str] = None
    source_hypothesis_id: Optional[str] = None
    temporal_compatibility: float = Field(..., ge=0.0, le=1.0, description="Temporal overlap score [0, 1]")
    speed_compatibility: float = Field(..., ge=0.0, le=1.0, description="Speed consistency with estimated slick drift [0, 1]")
    course_compatibility: float = Field(..., ge=0.0, le=1.0, description="Course consistency with estimated slick drift [0, 1]")
    track_overlap: float = Field(..., ge=0.0, le=1.0, description="Spatio-temporal track overlap fraction [0, 1]")
    ais_gap_ratio_origin_window: float = Field(..., ge=0.0, le=1.0, description="Fraction of origin window spent in an AIS gap [0, 1]")
    observed_speed_kn: Optional[float] = None
    observed_course_deg: Optional[float] = None
    slick_drift_speed_kn: Optional[float] = None
    slick_drift_course_deg: Optional[float] = None




