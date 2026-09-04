"""
backend/f7_graph/run_pipeline.py
---------------------------------
CLI runner: builds the F7 graph for all events using mock data
and writes output CSVs to data/raw/synthetic/outputs/.

Usage:
    python -m backend.f7_graph.run_pipeline
    python -m backend.f7_graph.run_pipeline --event EVT0001
    python -m backend.f7_graph.run_pipeline --output-dir ./my_outputs
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Make sure project root is on path when running as script
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.f7_graph.graph_builder import GraphBuilder
from shared.mocks.load_mock import load_mock_df as load_mock

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run(event_id: str | None = None, output_dir: Path | None = None):
    logger.info("=== F7 Pipeline starting ===")

    # ------------------------------------------------------------------
    # Load all upstream mocks
    # ------------------------------------------------------------------
    def _load(name: str) -> pd.DataFrame:
        try:
            df = load_mock(name, event_id=event_id)
            logger.info("  %-25s %d rows", name, len(df))
            return df
        except Exception as exc:
            logger.warning("  %-25s FAILED: %s", name, exc)
            return pd.DataFrame()

    tables = {
        "spill_observations": _load("spill_observations"),
        "temporal_states":    _load("temporal_states"),
        "source_hypotheses":  _load("source_hypotheses"),
        "vessel_tracks":      _load("vessel_tracks"),
        "evidence_items":     _load("evidence_items"),
        "hypothesis_scores":  _load("hypothesis_scores"),
        "forecasts":          _load("forecasts"),
    }

    # ------------------------------------------------------------------
    # Build graphs
    # ------------------------------------------------------------------
    builder = GraphBuilder(**tables)

    if event_id:
        results = {event_id: builder.build_for_event(event_id)}
    else:
        results = builder.build_all_events()

    all_nodes = []
    all_edges = []
    for eid, result in results.items():
        all_nodes.extend([n.to_dict() for n in result.nodes])
        all_edges.extend([e.to_dict() for e in result.edges])
        logger.info(
            "  event=%-10s  nodes=%3d  edges=%3d  partial=%s",
            eid, len(result.nodes), len(result.edges), result.is_partial,
        )

    nodes_df = pd.DataFrame(all_nodes)
    edges_df = pd.DataFrame(all_edges)

    logger.info("Total: %d nodes, %d edges across %d events", len(nodes_df), len(edges_df), len(results))

    # ------------------------------------------------------------------
    # Validation against reference CSVs
    # ------------------------------------------------------------------
    ref_nodes = load_mock("graph_nodes")
    ref_edges = load_mock("graph_edges")

    if not ref_nodes.empty:
        tol = 0.20  # ±20% tolerance as per spec ("within tolerance")
        ref_n = len(ref_nodes)
        our_n = len(nodes_df)
        pct_n = abs(our_n - ref_n) / max(ref_n, 1)
        status_n = "✓ PASS" if pct_n <= tol else "✗ WARN"
        logger.info("Node count  — reference: %d, generated: %d  [%s %.1f%%]", ref_n, our_n, status_n, pct_n * 100)

    if not ref_edges.empty:
        ref_e = len(ref_edges)
        our_e = len(edges_df)
        pct_e = abs(our_e - ref_e) / max(ref_e, 1)
        status_e = "✓ PASS" if pct_e <= tol else "✗ WARN"
        logger.info("Edge count  — reference: %d, generated: %d  [%s %.1f%%]", ref_e, our_e, status_e, pct_e * 100)

    # ------------------------------------------------------------------
    # Write outputs
    # ------------------------------------------------------------------
    if output_dir is None:
        # Try to auto-discover next to the reference CSVs
        try:
            from shared.mocks.load_mock import _find_data_root
            output_dir = _find_data_root()
        except Exception:
            output_dir = Path("data/raw/synthetic/outputs")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes_out = output_dir / "F7_graph_nodes_generated.csv"
    edges_out = output_dir / "F7_graph_edges_generated.csv"

    nodes_df.to_csv(nodes_out, index=False)
    edges_df.to_csv(edges_out, index=False)
    logger.info("Wrote %s", nodes_out)
    logger.info("Wrote %s", edges_out)
    logger.info("=== F7 Pipeline complete ===")

    return nodes_df, edges_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="F7 Graph Pipeline Runner")
    parser.add_argument("--event", default=None, help="Run for a single event_id only")
    parser.add_argument("--output-dir", default=None, help="Directory for output CSVs")
    args = parser.parse_args()
    run(event_id=args.event, output_dir=args.output_dir)
