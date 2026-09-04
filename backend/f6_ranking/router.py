"""
backend/f6_ranking/router.py
F6 API endpoints — Evidence Fusion & Dynamic Hypothesis Ranking

Routes:
    POST /f6/rank/{event_id}         — compute + store ranked hypotheses
    GET  /events/{event_id}/ranking  — retrieve ranked candidates
"""
from fastapi import APIRouter, HTTPException

from backend.f6_ranking.models import RankingResult
from backend.f6_ranking.service import rank_event
from shared.schemas.envelope import APIResponse

router = APIRouter(tags=["F6 Ranking"])

# In-memory store for prototype (replace with DB writes in production).
_ranking_cache: dict[str, RankingResult] = {}


@router.post("/f6/rank/{event_id}", response_model=APIResponse, summary="Rank candidates for an event")
def post_rank(event_id: str) -> APIResponse:
    """
    Compute and cache ranked candidate source vessels for a given event.

    - Loads F3/F4/F5 data from mocks if not yet live.
    - Returns a ranked list with component-wise breakdown.
    - Returns HTTP 200 with event_insufficient_evidence=true when evidence is thin;
      never raises an error for zero candidates.
    """
    try:
        result = rank_event(event_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ranking failed: {exc}")

    _ranking_cache[event_id] = result
    return APIResponse.ok(
        data=result.model_dump(),
        meta={
            "event_id": event_id,
            "n_candidates": result.n_candidates,
            "event_insufficient_evidence": result.event_insufficient_evidence,
        },
    )


@router.get("/events/{event_id}/ranking", response_model=APIResponse, summary="Get ranked candidates for an event")
def get_ranking(event_id: str) -> APIResponse:
    """
    Retrieve cached ranking for an event.
    Call POST /f6/rank/{event_id} first to populate the cache.
    """
    if event_id not in _ranking_cache:
        raise HTTPException(
            status_code=404,
            detail=f"No ranking found for {event_id}. Call POST /f6/rank/{event_id} first.",
        )
    result = _ranking_cache[event_id]
    return APIResponse.ok(
        data=result.model_dump(),
        meta={
            "event_id": event_id,
            "n_candidates": result.n_candidates,
            "event_insufficient_evidence": result.event_insufficient_evidence,
        },
    )
