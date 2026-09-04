from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class GeoJSONGeometry(BaseModel):
    type: str = Field(..., description="Geometry type: Polygon or MultiPolygon")
    coordinates: List[Any] = Field(..., description="Coordinates array conforming to GeoJSON spec")


class SpillDetectionResult(BaseModel):
    scene_id: str = Field(..., description="Unique scene identifier, e.g. S1_EVT0001_01")
    event_id: str = Field(..., description="Investigation event identifier, e.g. EVT0001")
    acquisition_timestamp: datetime = Field(..., description="UTC timestamp of satellite acquisition")
    sensor: str = Field(..., description="Sensor name, e.g. Sentinel-1")
    polarization: Optional[str] = Field(None, description="Polarization channel, e.g. VV, VH, VV+VH")
    polygon_geojson: Dict[str, Any] = Field(
        ...,
        description="Georeferenced slick boundary in EPSG:4326 GeoJSON format",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Detector confidence score between 0.0 and 1.0 (0.0 when oil_present=false)",
    )
    lookalike_present: bool = Field(
        ...,
        description="Flag indicating whether look-alikes (biogenic slicks/low-wind areas) are detected",
    )
    data_quality_flag: str = Field(
        default="nominal",
        description="Quality assessment flag: nominal, low_contrast, error, etc.",
    )
    oil_present: bool = Field(
        ...,
        description="Boolean indicating whether oil spill is detected in the scene",
    )
    source_dataset: str = Field(
        default="synthetic",
        description="Origin of imagery: synthetic, real_s1, etc.",
    )
    area_km2: Optional[float] = Field(
        default=0.0,
        description="Estimated slick area in square kilometers",
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be in range [0.0, 1.0], got {v}")
        return round(float(v), 4)
