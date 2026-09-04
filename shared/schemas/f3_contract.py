"""F3 Source Hypothesis Window and Environmental State contracts."""
from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class SourceLocationCoord(BaseModel):
    """Geographic point coordinates in EPSG:4326 (WGS84)."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in degrees")


class SourceHypothesisWindow(BaseModel):
    """F3 -> F4 SourceHypothesisWindow public data contract.

    Defines the estimated origin region, origin-time window, and uncertainty envelope
    used by F4 to construct its historical AIS vessel search corridor.
    NEVER present this hypothesis as proven vessel attribution or legal culpability.
    """
    source_hypothesis_id: str = Field(
        ...,
        description="Hypothesis ID following frozen convention: SH_<event_id>_<ensemble_id> or SH_<event_id>_HBEST"
    )
    event_id: str = Field(..., description="Spill event ID, e.g. EVT0001")
    source_location: SourceLocationCoord = Field(
        ..., description="Estimated release location centroid in EPSG:4326"
    )
    origin_time_start: str = Field(
        ..., description="Start of release-time search window in UTC ISO-8601"
    )
    origin_time_end: str = Field(
        ..., description="End of release-time search window in UTC ISO-8601"
    )
    uncertainty_radius_km: float = Field(
        ..., ge=0.0, description="RMS spread / uncertainty radius in kilometers. Mandatory, never omitted."
    )
    source_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized hypothesis weight/probability (1.0 for pooled best HBEST)"
    )

    # Optional internal/provenance fields
    ensemble_id: Optional[int] = Field(
        None, description="Ensemble member index (0..N) or -1 for pooled best estimate"
    )
    seed_state_ids: Optional[List[str]] = Field(
        None, description="List of F2 observation IDs used to seed the backward trajectory"
    )
    origin_time_mid: Optional[str] = Field(
        None, description="Midpoint release time estimate in UTC ISO-8601"
    )
    backtracked_hours: Optional[float] = Field(
        None, description="Elapsed hours backtracked from earliest seed observation"
    )
    wind_drift_factor: Optional[float] = Field(
        None, description="Wind drift factor (leeway) used in integration"
    )
    diffusion_m2s: Optional[float] = Field(
        None, description="Horizontal diffusion coefficient in m²/s"
    )
    data_quality_flag: Optional[str] = Field(
        None, description="Data quality or warning status, e.g. 'nominal', 'forcing_unavailable', 'single_observation'"
    )


class EnvironmentalStateSnapshot(BaseModel):
    """Snapshot of environmental forcing at a specific point in space and time.

    Recorded for provenance and audit in the environmental_states table.
    """
    env_state_id: str = Field(..., description="Unique environmental state ID, e.g. ENV_EVT0001_00")
    event_id: str = Field(..., description="Spill event ID, e.g. EVT0001")
    timestamp: str = Field(..., description="Forcing timestamp in UTC ISO-8601")
    location: SourceLocationCoord = Field(..., description="Geographic location of forcing evaluation")
    wind_speed_ms: Optional[float] = Field(None, ge=0.0, description="10m wind speed in m/s")
    current_speed_ms: Optional[float] = Field(None, ge=0.0, description="Surface current speed in m/s")
    wind_dir_deg: Optional[float] = Field(None, ge=0.0, le=360.0, description="Wind direction in degrees from north")
    current_dir_deg: Optional[float] = Field(None, ge=0.0, le=360.0, description="Current direction in degrees")
    source: str = Field("synthetic", description="Forcing source: 'synthetic', 'ERA5', 'Copernicus'")
