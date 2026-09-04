"""FastAPI router for F3 Hindcast endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from shared.schemas.envelope import ApiError, ApiMeta, ApiResponse, ErrorDetail
from shared.schemas.f2_contract import TemporalSpillState
from shared.schemas.f3_contract import SourceHypothesisWindow
from backend.f3_hindcast.supervisor import F3HindcastSupervisor


router = APIRouter(tags=["F3 - Hindcast"])
_supervisor = F3HindcastSupervisor()


class HindcastTriggerRequest(BaseModel):
    """Optional request body allowing caller to supply live states or custom seed."""
    states: Optional[List[TemporalSpillState]] = None
    base_seed: Optional[int] = 42


def _make_meta() -> ApiMeta:
    now_utc = datetime.now(timezone.utc)
    run_id = f"RUN_{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
    return ApiMeta(run_id=run_id, generated_at=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))


@router.post(
    "/api/v1/f3/hindcast/{event_id}",
    response_model=ApiResponse[List[SourceHypothesisWindow]],
    status_code=status.HTTP_200_OK,
    summary="Execute backward Lagrangian hindcast to derive candidate source hypotheses",
)
def run_hindcast(event_id: str, payload: Optional[HindcastTriggerRequest] = None):
    """Executes the F3 backward hindcasting pipeline for the specified event."""
    try:
        states = payload.states if payload else None
        seed = payload.base_seed if (payload and payload.base_seed is not None) else 42

        hypotheses, _ = _supervisor.execute_hindcast(
            event_id=event_id,
            states=states,
            base_seed=seed
        )
        return ApiResponse[List[SourceHypothesisWindow]](
            data=hypotheses,
            meta=_make_meta()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "HINDCAST_EXECUTION_FAILED", "message": str(e)}
        )


@router.get(
    "/api/v1/events/{event_id}/source-hypotheses",
    response_model=ApiResponse[List[SourceHypothesisWindow]],
    status_code=status.HTTP_200_OK,
    summary="List candidate source hypotheses for an event",
)
def get_source_hypotheses(event_id: str):
    """Retrieves all candidate source hypotheses for the given event."""
    hypotheses = _supervisor.get_hypotheses(event_id)
    if not hypotheses:
        # Run hindcast if not yet generated
        try:
            hypotheses, _ = _supervisor.execute_hindcast(event_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "EVENT_NOT_FOUND", "message": f"No hypotheses for {event_id}: {e}"}
            )

    return ApiResponse[List[SourceHypothesisWindow]](
        data=hypotheses,
        meta=_make_meta()
    )


@router.get(
    "/api/v1/f3/hindcast/{event_id}/best",
    response_model=ApiResponse[SourceHypothesisWindow],
    status_code=status.HTTP_200_OK,
    summary="Retrieve the pooled best estimate (HBEST) source hypothesis window for F4 AIS filtering",
)
def get_best_source_hypothesis(event_id: str):
    """Retrieves specifically the SH_<event_id>_HBEST hypothesis window for F4 integration."""
    try:
        best_hyp = _supervisor.get_best_hypothesis(event_id)
        return ApiResponse[SourceHypothesisWindow](
            data=best_hyp,
            meta=_make_meta()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HBEST_NOT_FOUND", "message": str(e)}
        )
