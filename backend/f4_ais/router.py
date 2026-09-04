"""FastAPI router for Feature F4 (Historical AIS Reconstruction) endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status

from shared.schemas.envelope import ApiMeta, ApiResponse
from shared.schemas.f4_contract import CandidateVessel
from backend.f4_ais.schemas import CorridorFilterResult, ReconstructionRequest
from backend.f4_ais.supervisor import F4AISSupervisor

router = APIRouter(tags=["F4 - Historical AIS"])
_supervisor = F4AISSupervisor()


def _make_meta() -> ApiMeta:
    now_utc = datetime.now(timezone.utc)
    run_id = f"RUN_{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
    return ApiMeta(run_id=run_id, generated_at=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))


@router.post(
    "/api/v1/f4/corridor-filter/{event_id}",
    response_model=ApiResponse[CorridorFilterResult],
    status_code=status.HTTP_200_OK,
    summary="Filter historical AIS fixes through F3 source hypothesis corridor",
)
def filter_ais_corridor(event_id: str, payload: Optional[ReconstructionRequest] = None):
    """Executes F4.2 spatio-temporal corridor filtering for an event."""
    try:
        hyp = payload.source_hypothesis if payload else None
        result = _supervisor.filter_corridor(event_id=event_id, hypothesis=hyp)
        return ApiResponse[CorridorFilterResult](
            data=result,
            meta=_make_meta()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "AIS_CORRIDOR_FILTER_FAILED", "message": str(e)}
        )


@router.post(
    "/api/v1/f4/reconstruct-ais/{event_id}",
    response_model=ApiResponse[List[CandidateVessel]],
    status_code=status.HTTP_200_OK,
    summary="Trigger historical AIS vessel reconstruction and correlation for an event",
)
def reconstruct_ais(event_id: str, payload: Optional[ReconstructionRequest] = None):
    """Executes the F4 historical AIS reconstruction and spatio-temporal correlation."""
    try:
        hyp = payload.source_hypothesis if payload else None
        candidates = _supervisor.execute_reconstruction(event_id=event_id, hypothesis=hyp)
        return ApiResponse[List[CandidateVessel]](
            data=candidates,
            meta=_make_meta()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "AIS_RECONSTRUCTION_FAILED", "message": str(e)}
        )


@router.get(
    "/api/v1/events/{event_id}/vessel-tracks",
    response_model=ApiResponse[List[CandidateVessel]],
    status_code=status.HTTP_200_OK,
    summary="Retrieve reconstructed candidate vessel tracks for an event",
)
def get_vessel_tracks(event_id: str):
    """Retrieves candidate vessel tracks for the specified event."""
    candidates = _supervisor.get_candidate_vessels(event_id)
    if not candidates:
        try:
            candidates = _supervisor.execute_reconstruction(event_id=event_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "EVENT_VESSELS_NOT_FOUND", "message": str(e)}
            )

    return ApiResponse[List[CandidateVessel]](
        data=candidates,
        meta=_make_meta()
    )
