"""
F2 — router.py

FastAPI router for Feature F2: Multi-Temporal Spill Reconstruction.

Endpoints:
  POST /f2/reconstruct/{event_id}  — (re)build all temporal states for an event
  GET  /events/{event_id}/states   — list temporal states for an event

Uses /shared/schemas/envelope.py response models.
Uses /shared/mocks/load_mock.py to load F1 data (no live F1 required).
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Query

from backend.shared.ids import mint_run_id
from backend.shared.mocks.load_mock import load_mock
from backend.shared.schemas.envelope import ApiResponse, ApiError, ResponseMeta
from backend.shared.schemas.temporal import TemporalSpillState, TemporalProgressionResult
from backend.f2_temporal.reconstruct import reconstruct_event

logger = logging.getLogger("oiltrace.f2")

router = APIRouter(tags=["F2 — Temporal Reconstruction"])

# In-memory store for the demo / tests (replace with DB writes for production)
_temporal_store: dict[str, TemporalProgressionResult] = {}


@router.post(
    "/f2/reconstruct/{event_id}",
    response_model=ApiResponse[TemporalProgressionResult],
    summary="(Re)build temporal states for a spill event",
    responses={404: {"model": ApiError}, 422: {"model": ApiError}},
)
def reconstruct(event_id: str):
    """
    Load F1 mock detections for the given event_id, run the F2 geometry
    extraction + temporal reconstruction pipeline, cache and return the result.
    """
    run_id = mint_run_id()
    logger.info("F2 reconstruct start event=%s run=%s", event_id, run_id)

    try:
        detections = load_mock("f1", event_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not detections:
        raise HTTPException(
            status_code=404,
            detail=f"No F1 detections found for event_id={event_id!r}. "
                   "Check that the event exists in D1_satellite_scenes.csv.",
        )

    result = reconstruct_event(detections)
    _temporal_store[event_id] = result

    logger.info(
        "F2 reconstruct done event=%s total=%d observed=%d interp=%d pred=%d insufficient=%s",
        event_id,
        result.total_states,
        result.observed_count,
        result.interpolated_count,
        result.predicted_count,
        result.insufficient_temporal_data,
    )

    return ApiResponse(
        data=result,
        meta=ResponseMeta(run_id=run_id),
    )


@router.get(
    "/events/{event_id}/states",
    response_model=ApiResponse[List[TemporalSpillState]],
    summary="List temporal states for a spill event",
    responses={404: {"model": ApiError}},
)
def list_states(
    event_id: str,
    state_type: str | None = Query(
        default=None,
        description="Filter by state_type: OBSERVED, INTERPOLATED, or PREDICTED",
    ),
    observed_only: bool = Query(
        default=False,
        description="If true, return only is_observed=True states (shortcut for F3)",
    ),
):
    """
    Return the cached temporal states for an event.
    Call POST /f2/reconstruct/{event_id} first if no states are cached.
    """
    run_id = mint_run_id()

    if event_id not in _temporal_store:
        # Auto-reconstruct on first GET
        try:
            detections = load_mock("f1", event_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if not detections:
            raise HTTPException(
                status_code=404,
                detail=f"No states available for event_id={event_id!r}. "
                       "Run POST /f2/reconstruct/{event_id} first.",
            )
        result = reconstruct_event(detections)
        _temporal_store[event_id] = result

    progression = _temporal_store[event_id]
    states = progression.states

    if observed_only:
        states = [s for s in states if s.is_observed]
    elif state_type:
        upper = state_type.upper()
        if upper not in ("OBSERVED", "INTERPOLATED", "PREDICTED"):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid state_type={state_type!r}. "
                       "Must be OBSERVED, INTERPOLATED, or PREDICTED.",
            )
        states = [s for s in states if s.state_type == upper]

    return ApiResponse(
        data=states,
        meta=ResponseMeta(run_id=run_id),
    )
