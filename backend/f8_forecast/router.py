"""FastAPI router for F8 - Forward Forecasting, Impact Assessment & Historical Replay."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from shared.schemas.envelope import ApiMeta, ApiResponse
from shared.schemas.f8_contract import (
    ForecastEvaluation,
    ForecastParticle,
    ForecastRun,
    ImpactAssessment,
)
from backend.f8_forecast.schemas import ForecastRequest
from backend.f8_forecast.supervisor import F8ForecastSupervisor

router = APIRouter(tags=["F8 - Forecast & Replay"])
_supervisor = F8ForecastSupervisor()


def _make_meta() -> ApiMeta:
    now = datetime.now(timezone.utc)
    return ApiMeta(run_id=f"RUN_{now.strftime('%Y%m%dT%H%M%SZ')}",
                   generated_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"))


@router.post(
    "/api/v1/f8/forecast/{event_id}",
    response_model=ApiResponse[List[ForecastRun]],
    status_code=status.HTTP_200_OK,
    summary="Run a forward Lagrangian ensemble forecast from the latest confirmed spill state",
)
def run_forecast(event_id: str, payload: Optional[ForecastRequest] = None):
    p = payload or ForecastRequest()
    try:
        runs, _particles, _impact = _supervisor.execute_forecast(
            event_id,
            t0_observation_index=p.t0_observation_index,
            horizons_h=p.horizons_h,
            n_ensemble=p.n_ensemble,
            n_particles=p.n_particles,
            base_seed=p.base_seed,
            states=p.states,
        )
        return ApiResponse[List[ForecastRun]](data=runs, meta=_make_meta())
    except Exception as e:  # noqa: BLE001 - surfaced as a 400 envelope
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "FORECAST_EXECUTION_FAILED", "message": str(e)},
        )


@router.get(
    "/api/v1/events/{event_id}/forecast",
    response_model=ApiResponse[List[ForecastRun]],
    status_code=status.HTTP_200_OK,
    summary="Retrieve the latest forecast runs for an event (auto-runs if absent)",
)
def get_forecast(event_id: str):
    try:
        return ApiResponse[List[ForecastRun]](data=_supervisor.get_runs(event_id), meta=_make_meta())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FORECAST_NOT_FOUND", "message": str(e)},
        )


@router.get(
    "/api/v1/f8/forecast/{event_id}/particles",
    response_model=ApiResponse[List[ForecastParticle]],
    status_code=status.HTTP_200_OK,
    summary="Sampled predicted particle positions for map animation / audit",
)
def get_forecast_particles(event_id: str):
    try:
        return ApiResponse[List[ForecastParticle]](data=_supervisor.get_particles(event_id), meta=_make_meta())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FORECAST_NOT_FOUND", "message": str(e)},
        )


@router.get(
    "/api/v1/f8/forecast/{event_id}/impact",
    response_model=ApiResponse[List[ImpactAssessment]],
    status_code=status.HTTP_200_OK,
    summary="GIS impact overlay (coastline / sensitive-zone distances, beaching risk) per horizon",
)
def get_forecast_impact(event_id: str):
    try:
        return ApiResponse[List[ImpactAssessment]](data=_supervisor.get_impact(event_id), meta=_make_meta())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "IMPACT_NOT_FOUND", "message": str(e)},
        )


@router.post(
    "/api/v1/f8/replay/{event_id}",
    response_model=ApiResponse[List[ForecastEvaluation]],
    status_code=status.HTTP_200_OK,
    summary="Historical replay: score each forecast horizon against the nearest later observation",
)
def run_replay(event_id: str, payload: Optional[ForecastRequest] = None):
    p = payload or ForecastRequest()
    try:
        _runs, evals = _supervisor.execute_replay(
            event_id,
            t0_observation_index=p.t0_observation_index,
            horizons_h=p.horizons_h,
            n_ensemble=p.n_ensemble,
            n_particles=p.n_particles,
            base_seed=p.base_seed,
            states=p.states,
        )
        return ApiResponse[List[ForecastEvaluation]](data=evals, meta=_make_meta())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REPLAY_EXECUTION_FAILED", "message": str(e)},
        )
