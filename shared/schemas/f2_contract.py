"""F2 Temporal Spill State input contract."""
from __future__ import annotations

from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CentroidCoord(BaseModel):
    """Centroid geographic coordinates in EPSG:4326 (WGS84)."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in degrees")


class GeoJSONPolygon(BaseModel):
    """GeoJSON Polygon geometry structure."""
    type: Literal["Polygon"] = Field("Polygon", description="Geometry type must be Polygon")
    coordinates: List[List[List[float]]] = Field(
        ...,
        description="GeoJSON coordinates: outer ring [[[lon, lat], ...]] and optional interior rings"
    )

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: List[List[List[float]]]) -> List[List[List[float]]]:
        if not v or not v[0] or len(v[0]) < 3:
            raise ValueError("Polygon outer ring must contain at least 3 coordinate points")
        for ring in v:
            for pt in ring:
                if len(pt) < 2:
                    raise ValueError(f"Coordinate pair must contain [lon, lat], got {pt}")
        return v


class TemporalSpillState(BaseModel):
    """F2 -> F3 TemporalSpillState data contract.

    Represents a discrete temporal observation or reconstruction of an oil slick.
    NOTE: Only states with state_type == 'OBSERVED' and is_observed == True
    are eligible to seed backward Lagrangian hindcasting.
    """
    observation_id: str = Field(..., description="Unique observation ID, e.g. OBS_EVT0001_000")
    event_id: str = Field(..., description="Spill event ID, e.g. EVT0001")
    timestamp: str = Field(..., description="Observation timestamp in UTC ISO-8601")
    state_type: Literal["OBSERVED", "INTERPOLATED", "PREDICTED"] = Field(
        ..., description="Reconstruction state classification"
    )
    polygon_geojson: GeoJSONPolygon = Field(..., description="Slick boundary in GeoJSON EPSG:4326")
    area_km2: float = Field(..., ge=0.0, description="Surface area of slick in square kilometers")
    centroid: CentroidCoord = Field(..., description="Centroid coordinate of slick")
    is_observed: bool = Field(..., description="True if from direct sensor detection; False if interpolated/predicted")

    @model_validator(mode="before")
    @classmethod
    def assemble_centroid(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "centroid" not in data and "centroid_lat" in data and "centroid_lon" in data:
                data = dict(data)
                data["centroid"] = {"lat": data["centroid_lat"], "lon": data["centroid_lon"]}
        return data

    @property
    def centroid_lat(self) -> float:
        return self.centroid.lat

    @property
    def centroid_lon(self) -> float:
        return self.centroid.lon

    # Optional extended attributes matching D2 dataset / database table
    scene_id: Optional[str] = Field(None, description="Originating satellite scene ID if observed")
    sim_hours: Optional[float] = Field(None, description="Simulation elapsed hours if synthetic")
    perimeter_km: Optional[float] = Field(None, description="Perimeter in kilometers")
    bbox: Optional[str] = Field(None, description="Bounding box string: min_lon,min_lat,max_lon,max_lat")
    major_axis_km: Optional[float] = Field(None, description="Equivalent ellipse major axis in km")
    minor_axis_km: Optional[float] = Field(None, description="Equivalent ellipse minor axis in km")
    orientation_deg: Optional[float] = Field(None, description="Principal orientation in degrees")
    solidity: Optional[float] = Field(None, description="Solidity metric [0, 1]")
    eccentricity: Optional[float] = Field(None, description="Eccentricity metric [0, 1]")
    compactness: Optional[float] = Field(None, description="Compactness metric [0, 1]")
    convexity: Optional[float] = Field(None, description="Convexity metric [0, 1]")
    aspect_ratio: Optional[float] = Field(None, description="Major to minor axis ratio")
    previous_observation_id: Optional[str] = Field(None, description="Preceding observation ID in sequence")
    polygon_iou: Optional[float] = Field(None, description="Intersection over Union with previous state")
    centroid_displacement_km: Optional[float] = Field(None, description="Displacement from previous centroid")
    area_change_pct: Optional[float] = Field(None, description="Percentage change in area vs previous")
    persistence: Optional[int] = Field(None, description="Count of observed states up to this point")
    observation_gap_hours: Optional[float] = Field(None, description="Hours elapsed since previous observation")
    f1_confidence: Optional[float] = Field(None, description="F1 detector confidence score")
    data_quality: Optional[str] = Field(None, description="Quality assessment flag")
