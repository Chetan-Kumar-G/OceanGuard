"""
backend/f7_graph/service.py
----------------------------
F7 service layer — orchestrates data loading, graph building,
DB persistence, and API serialization.

Called by the router and by the CLI runner.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.f7_graph.graph_builder import GraphBuilder, GraphResult
from backend.f7_graph.traversal import build_nx_graph, explain_ranking
from backend.f7_graph import db as graph_db
from shared.mocks.load_mock import load_mock_df as load_mock
from shared.schemas.envelope import APIEnvelope, GraphResponse, NodeSchema, EdgeSchema

logger = logging.getLogger(__name__)


def _load_upstream(event_id: Optional[str] = None, data_root: Optional[Path] = None) -> dict:
    """
    Load all upstream tables via mock loader.
    Each call is graceful — returns empty DataFrame on failure.
    """
    kwargs = {"data_root": data_root} if data_root else {}

    def _safe(name: str) -> pd.DataFrame:
        try:
            df = load_mock(name, event_id=event_id, **kwargs)
            logger.debug("Loaded %s: %d rows", name, len(df))
            return df
        except Exception as exc:
            logger.warning("Could not load %s: %s — continuing with empty DF", name, exc)
            return pd.DataFrame()

    return {
        "spill_observations": _safe("spill_observations"),
        "temporal_states":    _safe("temporal_states"),
        "source_hypotheses":  _safe("source_hypotheses"),
        "vessel_tracks":      _safe("vessel_tracks"),
        "evidence_items":     _safe("evidence_items"),
        "hypothesis_scores":  _safe("hypothesis_scores"),
        "forecasts":          _safe("forecasts"),
    }


def build_graph(
    event_id: str,
    engine=None,
    data_root: Optional[Path] = None,
    persist: bool = True,
) -> GraphResult:
    """
    Full pipeline for one event:
      1. Load upstream mocks
      2. Build graph nodes + edges
      3. Persist to DB (if engine provided and persist=True)
      4. Return GraphResult

    A partial upstream pipeline (missing stages) never raises — it
    sets result.is_partial = True.
    """
    tables = _load_upstream(event_id=event_id, data_root=data_root)

    builder = GraphBuilder(**tables)
    result = builder.build_for_event(event_id)

    if persist and engine is not None:
        graph_db.create_tables(engine)
        graph_db.upsert_nodes(engine, result.node_df(), event_id)
        graph_db.upsert_edges(engine, result.edge_df(), event_id)

    return result


def get_graph_response(
    event_id: str,
    engine=None,
    data_root: Optional[Path] = None,
) -> APIEnvelope:
    """
    Used by the GET /events/{event_id}/graph API endpoint.

    Tries DB first, falls back to building from mocks on cache miss.
    """
    # Try DB cache first
    nodes_df = graph_db.read_graph_nodes(engine, event_id) if engine else pd.DataFrame()
    edges_df = graph_db.read_graph_edges(engine, event_id) if engine else pd.DataFrame()

    if nodes_df.empty:
        logger.info("DB cache miss for event=%s — building from mocks", event_id)
        result = build_graph(event_id, engine=engine, data_root=data_root, persist=(engine is not None))
        nodes_df = result.node_df()
        edges_df = result.edge_df()
        is_partial = result.is_partial
    else:
        is_partial = False
        logger.info("Serving event=%s from DB cache (%d nodes)", event_id, len(nodes_df))

    # Serialize
    nodes = [NodeSchema(**row) for row in nodes_df.to_dict(orient="records")] if not nodes_df.empty else []
    edges = [EdgeSchema(**row) for row in edges_df.to_dict(orient="records")] if not edges_df.empty else []

    graph_resp = GraphResponse(
        event_id=event_id,
        nodes=nodes,
        edges=edges,
        node_count=len(nodes),
        edge_count=len(edges),
        is_partial=is_partial,
    )

    return APIEnvelope(success=True, data=graph_resp)


def get_explanation(
    event_id: str,
    hypothesis_id: str,
    engine=None,
    data_root: Optional[Path] = None,
) -> APIEnvelope:
    """
    Returns a clickable evidence chain from a ranked candidate back
    to the originating satellite scene.
    Used for the acceptance-criteria demoable trace.
    """
    result = build_graph(event_id, engine=engine, data_root=data_root, persist=False)
    nx_graph = build_nx_graph(result)
    chain = explain_ranking(nx_graph, event_id, hypothesis_id)
    return APIEnvelope(success=True, data=chain)
