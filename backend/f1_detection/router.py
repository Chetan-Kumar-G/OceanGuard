from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.f1_detection.inference import F1Detector
from backend.shared.ids import mint_run_id
from backend.shared.schemas.envelope import ApiResponse, ResponseMeta
from backend.shared.schemas.spill_detection import SpillDetectionResult

router = APIRouter(tags=["F1 Detection"])
_detector: Optional[F1Detector] = None


def get_detector() -> F1Detector:
    global _detector
    if _detector is None:
        _detector = F1Detector()
    return _detector


class DetectSceneRequest(BaseModel):
    scene_id: str = Field(..., description="Unique scene identifier, e.g. S1_EVT0001_01")
    image_path: Optional[str] = Field(None, description="Path to raster image file (.npy or image)")
    event_id: Optional[str] = Field(None, description="Associated investigation event ID")
    acquisition_timestamp: Optional[str] = Field(None, description="ISO-8601 acquisition timestamp")
    sensor: Optional[str] = Field("Sentinel-1", description="Sensor name")
    polarization: Optional[str] = Field(None, description="Polarization channels, e.g. VV+VH")
    bbox: Optional[Union[str, List[float]]] = Field(None, description="Scene bounding box [min_lon, min_lat, max_lon, max_lat]")
    pixel_spacing_m: Optional[float] = Field(40.0, description="Pixel spacing in meters")


@router.post("/f1/detect", response_model=ApiResponse[SpillDetectionResult])
def detect_spill(req: DetectSceneRequest) -> ApiResponse[SpillDetectionResult]:
    """
    Run F1 AI Oil-Spill Detection and Look-Alike Analysis on a given SAR scene.
    Returns georeferenced SpillDetectionResult enclosed in standard ApiResponse envelope.
    """
    detector = get_detector()
    result = detector.detect_scene(
        scene_id=req.scene_id,
        image_path=req.image_path,
        event_id=req.event_id,
        acquisition_timestamp=req.acquisition_timestamp,
        sensor=req.sensor,
        polarization=req.polarization,
        bbox=req.bbox,
        pixel_spacing_m=req.pixel_spacing_m,
    )

    return ApiResponse(
        data=result,
        meta=ResponseMeta(
            run_id=mint_run_id(),
            generated_at=datetime.now(timezone.utc),
        ),
    )


@router.get("/events/{event_id}/observations", response_model=ApiResponse[List[SpillDetectionResult]])
def list_event_observations(event_id: str) -> ApiResponse[List[SpillDetectionResult]]:
    """
    List all detection observations for a given event ID.
    Processes or retrieves observations for all scenes associated with this event.
    """
    detector = get_detector()
    df = detector.scenes_df

    if len(df) == 0 or "event_id" not in df.columns:
        raise HTTPException(status_code=404, detail="Scenes database not available")

    event_scenes = df[df["event_id"] == event_id]
    if len(event_scenes) == 0:
        raise HTTPException(status_code=404, detail=f"No observations found for event: {event_id}")

    observations: List[SpillDetectionResult] = []
    for _, row in event_scenes.iterrows():
        obs = detector.detect_scene(scene_id=str(row["scene_id"]))
        observations.append(obs)

    return ApiResponse(
        data=observations,
        meta=ResponseMeta(
            run_id=mint_run_id(),
            generated_at=datetime.now(timezone.utc),
        ),
    )
