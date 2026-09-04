"""F8 Forward Forecasting, Impact Assessment & Historical Replay contracts.

These models mirror the columns of the reference ``D8_forecast_runs.csv`` /
``D8_forecast_particles.csv`` / ``evaluation_only/D8_evaluation.csv`` so the F8
backend output is interchangeable with the generated dataset.

A forecast is a *scenario ensemble*, never a single deterministic path: every
``ForecastRun`` carries an ``ensemble_spread_km`` and a ``forecast_envelope``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LonLat(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class ForecastRun(BaseModel):
    """One forecast horizon of one forward ensemble run (F8 -> F7 / dashboard)."""
    event_id: str = Field(..., description="Spill event ID, e.g. EVT0002")
    forecast_id: str = Field(..., description="<event_id>-FC<t0_index> forward-run ID")
    initial_observation_id: str = Field(..., description="F2 OBSERVED state the run was launched from")
    initial_timestamp: str = Field(..., description="T0 timestamp (UTC ISO-8601)")
    initial_centroid: LonLat = Field(..., description="T0 slick centroid")
    initial_area_km2: float = Field(..., ge=0.0)

    forecast_horizon_hours: float = Field(..., gt=0.0, description="Lead time from T0 in hours")
    valid_timestamp: str = Field(..., description="T0 + horizon (UTC ISO-8601)")
    n_ensemble: int = Field(..., ge=1)

    predicted_centroid: LonLat = Field(..., description="Ensemble-mean predicted slick centroid")
    predicted_polygon_geojson: Dict[str, Any] = Field(..., description="Predicted slick outline (GeoJSON Polygon, EPSG:4326)")
    predicted_area_km2: float = Field(..., ge=0.0)
    forecast_envelope_geojson: Dict[str, Any] = Field(..., description="Generously-buffered ensemble footprint (GeoJSON Polygon)")
    forecast_envelope_area_km2: float = Field(..., ge=0.0)

    ensemble_spread_km: float = Field(..., ge=0.0, description="RMS spread of member centroids about the mean")
    forecast_confidence: float = Field(..., ge=0.0, le=1.0, description="exp(-spread/15) * exp(-h/96); decays with spread and lead time")

    coastline_distance_km: float = Field(..., description="Predicted centroid distance to the modelled coast edge")
    nearest_sensitive_zone: Optional[str] = Field(None, description="Name of nearest sensitive/protected zone")
    sensitive_zone_distance_km: Optional[float] = Field(None, description="Distance from predicted centroid to that zone boundary (>=0)")
    beaching_risk: bool = Field(..., description="True when coast distance < 2 * ensemble spread")

    data_quality_flag: str = Field("nominal", description="'nominal', 'forcing_unavailable', 'single_observation'")


class ForecastParticle(BaseModel):
    """A sampled predicted particle position (audit / map animation)."""
    event_id: str
    forecast_id: str
    forecast_horizon_hours: float
    ensemble_member: int
    timestamp: str
    particle: LonLat


class ImpactAssessment(BaseModel):
    """GIS impact overlay for one forecast horizon."""
    event_id: str
    forecast_id: str
    forecast_horizon_hours: float
    valid_timestamp: str
    predicted_centroid: LonLat
    coastline_distance_km: float
    beaching_risk: bool
    nearest_sensitive_zone: Optional[str] = None
    sensitive_zone_distance_km: Optional[float] = None
    impact_area_candidates: List[str] = Field(
        default_factory=list,
        description="Named coast edge / sensitive zones the forecast envelope reaches",
    )


class ForecastEvaluation(BaseModel):
    """Historical-replay score for one forecast horizon (eval-only: reads a later observation)."""
    event_id: str
    forecast_id: str
    forecast_horizon_hours: float
    valid_timestamp: str
    matched_observation_id: str
    matched_timestamp: str
    match_offset_hours: float
    predicted_centroid: LonLat
    observed_centroid: LonLat
    trajectory_error_km: float = Field(..., ge=0.0)
    observed_region_coverage_iou: float = Field(..., ge=0.0, le=1.0)
    observed_in_forecast_envelope_frac: float = Field(..., ge=0.0, le=1.0)
    observed_centroid_in_envelope: bool
    calibration_ratio: float = Field(..., ge=0.0, description="trajectory_error / ensemble_spread; ~1 well calibrated")
    well_calibrated: bool = Field(..., description="0.5 <= calibration_ratio <= 2.0")
