"""FastAPI routes for F5 (Blueprint Part 8).

    POST /f5/evaluate-consistency/{event_id}   compute evidence relations
    GET  /events/{event_id}/evidence           list evidence relations

Responses use the shared envelope models — never a raw dict.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from shared.ids import is_event_id
from shared.schemas.envelope import ApiMeta, ApiResponse, error_response

from .repository import EvidenceRepository
from .service import evaluate_event

logger = logging.getLogger("oiltrace.f5")

router = APIRouter(tags=["f5-consistency"])

_repo: EvidenceRepository | None = None


def get_repo() -> EvidenceRepository:
    """Lazily created so importing the router has no filesystem/DB side effect."""
    global _repo
    if _repo is None:
        _repo = EvidenceRepository()
    return _repo


def set_repo(repo: EvidenceRepository) -> None:
    global _repo
    _repo = repo


def _guard_event_id(event_id: str) -> None:
    if not is_event_id(event_id):
        raise HTTPException(
            status_code=400,
            detail=error_response(
                "invalid_event_id",
                "event_id must match EVT#### (Blueprint Part 5)",
                {"event_id": event_id},
            ),
        )


@router.post("/f5/evaluate-consistency/{event_id}")
def evaluate_consistency_endpoint(event_id: str) -> ApiResponse:
    _guard_event_id(event_id)
    try:
        result = evaluate_event(event_id, persist=True, repo=get_repo())
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=error_response("upstream_data_missing", str(exc)),
        ) from exc
    except Exception as exc:  # pragma: no cover - surfaced as 500 envelope
        logger.exception("F5 evaluate failed for %s", event_id)
        raise HTTPException(
            status_code=500, detail=error_response("f5_internal_error", str(exc))
        ) from exc

    return ApiResponse(
        data=[r.model_dump() for r in result.relations],
        meta=ApiMeta(
            event_id=event_id,
            summary=result.summary,
            skipped_reason=result.skipped_reason,
            thresholds_source=_thresholds_source(),
        ),
    )


@router.get("/events/{event_id}/evidence")
def list_evidence_endpoint(event_id: str) -> ApiResponse:
    _guard_event_id(event_id)
    relations = get_repo().list_relations(event_id)
    summary = {"SUPPORTS": 0, "CONTRADICTS": 0, "UNKNOWN": 0, "total": len(relations)}
    for r in relations:
        summary[r.relation] += 1
    return ApiResponse(
        data=[r.model_dump() for r in relations],
        meta=ApiMeta(event_id=event_id, summary=summary),
    )


def _thresholds_source() -> str:
    from .config import default_thresholds

    return default_thresholds().source_path


# Uniform error envelope for guard failures raised as HTTPException(detail=<envelope>)
async def http_exception_handler(_request, exc: HTTPException):  # pragma: no cover
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response("http_error", str(exc.detail)),
    )
