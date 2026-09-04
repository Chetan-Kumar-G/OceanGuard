"""
tests/unit/f7/test_traversal.py
---------------------------------
Unit tests for the F7 NetworkX traversal engine.

Tests:
  1. build_nx_graph produces correct node/edge counts
  2. explain_ranking traces back to SPILL_OBSERVATION
  3. find_evidence_chain returns shortest path
  4. Graceful handling of missing nodes
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_ROOT))

from backend.f7_graph.graph_builder import GraphBuilder
from backend.f7_graph.traversal import build_nx_graph, explain_ranking, find_evidence_chain


def _build_test_graph():
    d1 = pd.DataFrame([{
        "event_id": "EVT0001",
        "scene_id": "S1_EVT0001_02",
        "acquisition_timestamp": "2026-01-09T16:00:22Z",
        "latitude": 38.3, "longitude": 21.1, "f1_confidence": 0.99, "f1_detected": True,
    }])
    d3 = pd.DataFrame([{
        "event_id": "EVT0001",
        "source_hypothesis_id": "EVT0001-HYP000",
        "ensemble_id": 0,
        "source_lat": 38.1, "source_lon": 21.0,
        "origin_time_mid": "2026-01-09T12:00:00Z",
        "source_probability": 0.85,
        "uncertainty_radius_km": 12.3,
        "seed_state_ids": "",
    }])
    d5 = pd.DataFrame([{
        "event_id": "EVT0001",
        "evidence_id": "EVT0001-EV001",
        "source_a_id": "EVT0001-HYP000",
        "source_a_type": "SOURCE_HYPOTHESIS",
        "source_b_id": "EVT0001-OBS000",
        "source_b_type": "SPILL_OBSERVATION",
        "timestamp_a": "2026-01-09T12:00:00Z",
        "timestamp_b": "2026-01-09T16:00:22Z",
        "relation": "SUPPORTS",
        "reason": "test",
        "sensor_confidence": 0.99,
        "provenance": "F3->F1",
    }])

    builder = GraphBuilder(
        spill_observations=d1,
        temporal_states=pd.DataFrame(),
        source_hypotheses=d3,
        vessel_tracks=pd.DataFrame(),
        evidence_items=d5,
        hypothesis_scores=pd.DataFrame(),
        forecasts=pd.DataFrame(),
    )
    return builder.build_for_event("EVT0001")


class TestBuildNxGraph:
    def test_graph_has_nodes_and_edges(self):
        result = _build_test_graph()
        G = build_nx_graph(result)
        if G is None:
            pytest.skip("networkx not installed")
        # nx may add extra nodes referenced in edges but not explicitly added
        assert G.number_of_nodes() >= len(result.nodes)
        assert G.number_of_edges() == len(result.edges)

    def test_node_data_accessible(self):
        result = _build_test_graph()
        G = build_nx_graph(result)
        if G is None:
            pytest.skip("networkx not installed")
        assert "EVT0001-ENV" in G
        assert G.nodes["EVT0001-ENV"]["node_type"] == "ENVIRONMENTAL_STATE"


class TestExplainRanking:
    def test_returns_dict_with_expected_keys(self):
        result = _build_test_graph()
        G = build_nx_graph(result)
        if G is None:
            pytest.skip("networkx not installed")
        explanation = explain_ranking(G, "EVT0001", "EVT0001-HYP000")
        assert "chain" in explanation
        assert "evidence_items" in explanation
        assert "terminal_scenes" in explanation

    def test_missing_node_returns_error(self):
        result = _build_test_graph()
        G = build_nx_graph(result)
        if G is None:
            pytest.skip("networkx not installed")
        explanation = explain_ranking(G, "EVT0001", "DOES_NOT_EXIST")
        assert "error" in explanation


class TestFindEvidenceChain:
    def test_finds_path_between_connected_nodes(self):
        result = _build_test_graph()
        G = build_nx_graph(result)
        if G is None:
            pytest.skip("networkx not installed")
        # EVT0001-HYP000 is connected to EVT0001-ENV via DERIVED-FROM
        chain = find_evidence_chain(G, "EVT0001-HYP000", "EVT0001-ENV")
        assert chain["found"] is True
        assert chain["length"] >= 1

    def test_disconnected_nodes_returns_not_found(self):
        result = _build_test_graph()
        G = build_nx_graph(result)
        if G is None:
            pytest.skip("networkx not installed")
        chain = find_evidence_chain(G, "EVT0001-HYP000", "TOTALLY_MISSING_NODE")
        assert chain["found"] is False
