"""
backend/f7_graph/db.py
-----------------------
PostgreSQL/PostGIS database layer for F7.

Owns tables: graph_nodes, graph_edges

Rules:
 * READ ONLY from all upstream tables — never modify them.
 * WRITE only to graph_nodes and graph_edges.
 * Coordinate with team on refresh strategy before enabling
   materialized-view mode (storage tradeoff flagged below).

STORAGE TRADEOFF NOTE (per spec requirement):
  Two strategies are available:
  1. DEDICATED TABLES (default for MVP):
     INSERT graph_nodes / graph_edges rows on each pipeline run.
     Pro: simple, queryable, indexed.
     Con: storage duplication of upstream data (subset of fields).
  2. MATERIALIZED VIEWS:
     Define views over upstream tables instead of dedicated tables.
     Pro: zero duplication.
     Con: refresh cost, no independent indexing without manual work.
  Current choice: DEDICATED TABLES for MVP.
  Flag for team review before switching to materialized views.

When no live DB is available (mock mode), these functions are no-ops
and the graph is returned from in-memory DataFrames only.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Optional SQLAlchemy import — not required for mock/test runs
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    _SA_AVAILABLE = True
except ImportError:
    _SA_AVAILABLE = False
    logger.info("sqlalchemy not installed — DB layer running in no-op mock mode")


# ---------------------------------------------------------------------------
# DDL — graph_nodes and graph_edges tables
# ---------------------------------------------------------------------------

_DDL_NODES = """
CREATE TABLE IF NOT EXISTS graph_nodes (
    node_id         TEXT        NOT NULL,
    event_id        TEXT        NOT NULL,
    node_type       TEXT        NOT NULL
                    CHECK (node_type IN (
                        'SPILL_OBSERVATION', 'SOURCE_HYPOTHESIS',
                        'ENVIRONMENTAL_STATE', 'VESSEL', 'EVIDENCE', 'FORECAST'
                    )),
    timestamp       TIMESTAMPTZ,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    confidence      DOUBLE PRECISION,
    uncertainty     DOUBLE PRECISION,
    provenance      TEXT,
    inserted_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (node_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_event ON graph_nodes (event_id);
"""

_DDL_EDGES = """
CREATE TABLE IF NOT EXISTS graph_edges (
    edge_id         TEXT        NOT NULL PRIMARY KEY,
    event_id        TEXT        NOT NULL,
    source_node_id  TEXT        NOT NULL,
    target_node_id  TEXT        NOT NULL,
    relation_type   TEXT        NOT NULL
                    CHECK (relation_type IN (
                        'DERIVED-FROM', 'SUPPORTS', 'CONTRADICTS', 'TEMPORALLY-COMPATIBLE'
                    )),
    confidence      DOUBLE PRECISION,
    timestamp       TIMESTAMPTZ,
    provenance      TEXT,
    inserted_at     TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (source_node_id, event_id) REFERENCES graph_nodes(node_id, event_id) ON DELETE CASCADE,
    FOREIGN KEY (target_node_id, event_id) REFERENCES graph_nodes(node_id, event_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_graph_edges_event ON graph_edges (event_id);
"""


# ---------------------------------------------------------------------------
# Engine management
# ---------------------------------------------------------------------------

def get_engine(dsn: Optional[str] = None):
    """
    Return a SQLAlchemy engine.
    DSN resolution order:
      1. dsn argument
      2. OILTRACE_DB_DSN environment variable
      3. None → mock mode
    """
    if not _SA_AVAILABLE:
        return None

    resolved = dsn or os.environ.get("OILTRACE_DB_DSN")
    if not resolved:
        logger.info("No DB DSN configured — running in mock/no-op mode")
        return None

    try:
        engine = create_engine(resolved, pool_pre_ping=True)
        return engine
    except Exception as exc:
        logger.error("Failed to create DB engine: %s", exc)
        return None


def create_tables(engine) -> None:
    """Create graph_nodes and graph_edges tables if they don't exist."""
    if engine is None:
        logger.debug("create_tables: no engine (mock mode)")
        return
    with engine.begin() as conn:
        conn.execute(text(_DDL_NODES))
        conn.execute(text(_DDL_EDGES))
    logger.info("graph_nodes and graph_edges tables ensured")


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def upsert_nodes(engine, nodes_df: pd.DataFrame, event_id: str) -> int:
    """
    Insert/replace graph nodes for an event.
    Deletes existing nodes for event_id first (full refresh per event).
    Returns row count written.
    """
    if engine is None or nodes_df.empty:
        return 0
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM graph_nodes WHERE event_id = :eid"), {"eid": event_id})
    # NaN (e.g. a column that's None for every node so far) isn't a valid value
    # for the nullable TEXT/TIMESTAMPTZ columns below - use real NULL instead.
    rows = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in nodes_df.to_dict(orient="records")]
    written = 0
    with engine.begin() as conn:
        for row in rows:
            conn.execute(
                text("""
                    INSERT INTO graph_nodes
                        (node_id, event_id, node_type, timestamp, latitude, longitude,
                         confidence, uncertainty, provenance)
                    VALUES
                        (:node_id, :event_id, :node_type, :timestamp, :latitude, :longitude,
                         :confidence, :uncertainty, :provenance)
                    ON CONFLICT (node_id, event_id) DO UPDATE SET
                        node_type   = EXCLUDED.node_type,
                        timestamp   = EXCLUDED.timestamp,
                        latitude    = EXCLUDED.latitude,
                        longitude   = EXCLUDED.longitude,
                        confidence  = EXCLUDED.confidence,
                        uncertainty = EXCLUDED.uncertainty,
                        provenance  = EXCLUDED.provenance,
                        inserted_at = NOW()
                """),
                row,
            )
            written += 1
    logger.info("upsert_nodes: wrote %d nodes for event=%s", written, event_id)
    return written


def upsert_edges(engine, edges_df: pd.DataFrame, event_id: str) -> int:
    """
    Insert/replace graph edges for an event.
    Returns row count written.
    """
    if engine is None or edges_df.empty:
        return 0
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM graph_edges WHERE event_id = :eid"), {"eid": event_id})
    rows = [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in edges_df.to_dict(orient="records")]
    written = 0
    with engine.begin() as conn:
        for row in rows:
            conn.execute(
                text("""
                    INSERT INTO graph_edges
                        (edge_id, event_id, source_node_id, target_node_id, relation_type,
                         confidence, timestamp, provenance)
                    VALUES
                        (:edge_id, :event_id, :source_node_id, :target_node_id, :relation_type,
                         :confidence, :timestamp, :provenance)
                    ON CONFLICT (edge_id) DO UPDATE SET
                        relation_type  = EXCLUDED.relation_type,
                        confidence     = EXCLUDED.confidence,
                        timestamp      = EXCLUDED.timestamp,
                        provenance     = EXCLUDED.provenance,
                        inserted_at    = NOW()
                """),
                row,
            )
            written += 1
    logger.info("upsert_edges: wrote %d edges for event=%s", written, event_id)
    return written


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_graph_nodes(engine, event_id: str) -> pd.DataFrame:
    """Load graph_nodes for an event from DB. Returns empty DF if unavailable."""
    if engine is None:
        return pd.DataFrame()
    sql = "SELECT * FROM graph_nodes WHERE event_id = :eid ORDER BY node_id"
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params={"eid": event_id})
    except Exception as exc:
        logger.error("read_graph_nodes: %s", exc)
        return pd.DataFrame()


def read_graph_edges(engine, event_id: str) -> pd.DataFrame:
    """Load graph_edges for an event from DB. Returns empty DF if unavailable."""
    if engine is None:
        return pd.DataFrame()
    sql = "SELECT * FROM graph_edges WHERE event_id = :eid ORDER BY edge_id"
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params={"eid": event_id})
    except Exception as exc:
        logger.error("read_graph_edges: %s", exc)
        return pd.DataFrame()
