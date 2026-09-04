from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class TemporalSpillState(BaseModel):
    event_id: str = Field(..., description="Investigation event identifier, e.g. EVT0001")
    observation_id: str = Field(..., description="Observation state identifier, e.g. EVT0001-OBS000")
    scene_id: Optional[str] = Field(default="", description="Originating S1 scene ID (empty for non-OBSERVED)")
    timestamp: datetime = Field(..., description="UTC ISO-8601 acquisition or state timestamp")
    sim_hours: Optional[float] = Field(default=0.0, description="Hours elapsed since simulation start or T0")
    state_type: str = Field(..., description="State classification: OBSERVED, INTERPOLATED, or PREDICTED")
    polygon_geojson: Dict[str, Any] = Field(..., description="Boundary geometry in EPSG:4326 GeoJSON format")
    polygon_wkt: Optional[str] = Field(default="", description="Boundary geometry in WKT EPSG:4326 format")
    area_km2: float = Field(..., ge=0.0, description="Surface area in square kilometers")
    perimeter_km: float = Field(..., ge=0.0, description="Perimeter length in kilometers")
    centroid_lat: float = Field(..., description="Geographic centroid latitude (degrees)")
    centroid_lon: float = Field(..., description="Geographic centroid longitude (degrees)")
    bbox: str = Field(..., description="Bounding box string: min_lon,min_lat,max_lon,max_lat")
    
    # Shape descriptors
    major_axis_km: float = Field(default=0.0, description="Major axis of minimum rotated bounding rectangle (km)")
    minor_axis_km: float = Field(default=0.0, description="Minor axis of minimum rotated bounding rectangle (km)")
    orientation_deg: float = Field(default=0.0, description="Principal orientation angle [0, 180) degrees")
    solidity: float = Field(default=1.0, ge=0.0, le=1.0, description="Ratio of area to convex hull area")
    eccentricity: float = Field(default=0.0, ge=0.0, le=1.0, description="Eccentricity sqrt(1 - (b/a)^2)")
    compactness: float = Field(default=1.0, ge=0.0, description="Isoperimetric compactness quotient 4*pi*area/perimeter^2")
    convexity: float = Field(default=1.0, ge=0.0, description="Convex hull perimeter / actual perimeter")
    aspect_ratio: float = Field(default=1.0, ge=0.0, description="Major axis / minor axis ratio")

    # Temporal dynamics vs previous state
    previous_observation_id: Optional[str] = Field(default="", description="ID of immediately preceding state")
    polygon_iou: Optional[float] = Field(default=None, description="Spatial IoU with previous state polygon [0.0, 1.0]")
    centroid_displacement_km: Optional[float] = Field(default=None, description="Distance between centroids (km)")
    area_change_pct: Optional[float] = Field(default=None, description="Percentage change in area vs previous state")
    persistence: int = Field(default=1, ge=0, description="Cumulative count of confirmed OBSERVED states so far")
    observation_gap_hours: Optional[float] = Field(default=None, description="Time gap in hours since previous state")
    
    # Provenance and quality
    f1_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence carried through from F1")
    data_quality: str = Field(default="observed", description="Quality description: observed, synthetic, low_contrast, etc.")
    is_observed: bool = Field(..., description="Strict boolean: True ONLY for OBSERVED states")

    @field_validator("is_observed")
    @classmethod
    def validate_is_observed_integrity(cls, v: bool, info) -> bool:
        state_type = info.data.get("state_type")
        if state_type == "OBSERVED" and not v:
            raise ValueError("OBSERVED states must have is_observed=True")
        if state_type in ("INTERPOLATED", "PREDICTED") and v:
            raise ValueError(f"{state_type} states must have is_observed=False")
        return v


class TemporalProgressionResult(BaseModel):
    event_id: str
    total_states: int
    observed_count: int
    interpolated_count: int
    predicted_count: int
    states: List[TemporalSpillState]
    insufficient_temporal_data: bool = Field(
        default=False,
        description="Flagged true if fewer than 2 OBSERVED states exist for the event",
    )
