"""
backend/f7_graph/router.py
---------------------------
FastAPI router for F7 — Forensic Investigation Graph.

Endpoints
---------
GET /events/{event_id}/graph
    Returns full node+edge set for an event.

GET /events/{event_id}/graph/explain/{hypothesis_id}
    Returns clickable evidence chain from hypothesis back to raw scene.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.f7_graph import db as graph_db
from backend.f7_graph.service import get_explanation, get_graph_response
from shared.schemas.envelope import APIEnvelope, GraphResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["F7 - Forensic Graph"])

# Lazy engine — created on first use
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = graph_db.get_engine()
    return _engine


def _data_root() -> Path | None:
    env = os.environ.get("OCEANGUARD_DATA_DIR")
    return Path(env) if env else None


@router.get(
    "/{event_id}/graph",
    response_model=APIEnvelope,
    summary="Full forensic graph for an event",
    description=(
        "Returns all graph nodes (SPILL_OBSERVATION, SOURCE_HYPOTHESIS, "
        "ENVIRONMENTAL_STATE, VESSEL, EVIDENCE, FORECAST) and typed edges "
        "(DERIVED-FROM, SUPPORTS, CONTRADICTS, TEMPORALLY-COMPATIBLE) "
        "for the specified event. "
        "If upstream stages have not run, a partial graph is returned with "
        "is_partial=true — this endpoint never errors on a missing stage."
    ),
)
async def get_event_graph(
    event_id: str,
    rebuild: bool = Query(
        default=False,
        description="If true, bypass DB cache and rebuild from upstream mocks.",
    ),
):
    try:
        engine = None if rebuild else _get_engine()
        envelope = get_graph_response(
            event_id=event_id,
            engine=engine,
            data_root=_data_root(),
        )
        if not envelope.data or (envelope.data.node_count == 0):
            raise HTTPException(status_code=404, detail=f"No graph data found for event {event_id!r}")
        return envelope
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error building graph for event=%s", event_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/{event_id}/graph/explain/{hypothesis_id}",
    response_model=APIEnvelope,
    summary="Evidence chain explanation for a ranked candidate",
    description=(
        "Traces a ranked source hypothesis back to the originating "
        "satellite scene, returning the full evidence chain with "
        "provenance at each hop."
    ),
)
async def explain_hypothesis(event_id: str, hypothesis_id: str):
    try:
        envelope = get_explanation(
            event_id=event_id,
            hypothesis_id=hypothesis_id,
            engine=_get_engine(),
            data_root=_data_root(),
        )
        return envelope
    except Exception as exc:
        logger.exception(
            "Unexpected error explaining event=%s hypothesis=%s", event_id, hypothesis_id
        )
        raise HTTPException(status_code=500, detail=str(exc))
