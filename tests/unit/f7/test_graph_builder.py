"""
tests/unit/f7/test_graph_builder.py
-------------------------------------
Unit tests for F7 GraphBuilder.

Tests:
  1. Node construction from each upstream type (fixture rows)
  2. Edge construction from evidence_items
  3. Partial pipeline tolerance (empty DataFrames don't error)
  4. Confidence/uncertainty verbatim pass-through (never averaged)
  5. Node type taxonomy enforcement
  6. Edge provenance citation
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure project root on path
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_ROOT))

from backend.f7_graph.graph_builder import (
    EDGE_TYPES,
    NODE_TYPES,
    GraphBuilder,
    GraphResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _empty_tables() -> dict:
    return {
        "spill_observations": pd.DataFrame(),
        "temporal_states": pd.DataFrame(),
        "source_hypotheses": pd.DataFrame(),
        "vessel_tracks": pd.DataFrame(),
        "evidence_items": pd.DataFrame(),
        "hypothesis_scores": pd.DataFrame(),
        "forecasts": pd.DataFrame(),
    }


def _d1_fixture() -> pd.DataFrame:
    """Minimal D1 spill_observations row for EVT0001 (f1_detected=True)."""
    return pd.DataFrame([{
        "event_id": "EVT0001",
        "scene_id": "S1_EVT0001_02",
        "acquisition_timestamp": "2026-01-09T16:00:22Z",
        "latitude": 38.363357,
        "longitude": 21.147173,
        "f1_confidence": 0.99,
        "f1_detected": True,
    }])


def _d2_fixture() -> pd.DataFrame:
    """Minimal D2 temporal_states OBSERVED row for EVT0001."""
    return pd.DataFrame([{
        "event_id": "EVT0001",
        "observation_id": "EVT0001-OBS000",
        "scene_id": "S1_EVT0001_02",
        "timestamp": "2026-01-09T16:00:22Z",
        "state_type": "OBSERVED",
        "centroid_lat": 38.363357,
        "centroid_lon": 21.147173,
        "f1_confidence": 0.99,
    }])


def _d3_fixture() -> pd.DataFrame:
    """Minimal D3 source_hypotheses row for EVT0001."""
    return pd.DataFrame([
        {
            "event_id": "EVT0001",
            "source_hypothesis_id": "EVT0001-HYP000",
            "ensemble_id": 0,
            "source_lat": 38.1,
            "source_lon": 21.0,
            "origin_time_mid": "2026-01-09T12:00:00Z",
            "source_probability": 0.85,
            "uncertainty_radius_km": 12.3,
            "seed_state_ids": "OBS0",
        }
    ])


def _d4_fixture() -> pd.DataFrame:
    """Minimal D4 vessel_tracks row for EVT0001."""
    return pd.DataFrame([
        {
            "event_id": "EVT0001",
            "mmsi": "123456789",
            "track_id": "EVT0001-TRACK-123456789",
            "temporal_compatibility": 0.72,
            "source_hypothesis_id": "EVT0001-HYP000",
            "closest_approach_timestamp": "2026-01-09T11:30:00Z",
        }
    ])


def _d5_fixture() -> pd.DataFrame:
    """Minimal D5 evidence_items row for EVT0001."""
    return pd.DataFrame([
        {
            "event_id": "EVT0001",
            "evidence_id": "EVT0001-EV001",
            "source_a_id": "EVT0001-HYP000",
            "source_a_type": "SOURCE_HYPOTHESIS",
            "source_b_id": "EVT0001-TRACK-123456789",
            "source_b_type": "VESSEL",
            "timestamp_a": "2026-01-09T12:00:00Z",
            "timestamp_b": "2026-01-09T11:30:00Z",
            "relation": "SUPPORTS",
            "reason": "Close spatial and temporal match",
            "sensor_confidence": 0.99,
            "provenance": "F3->F4",
        }
    ])


def _d8_fixture() -> pd.DataFrame:
    """Minimal D8 forecast_runs row for EVT0001."""
    return pd.DataFrame([
        {
            "event_id": "EVT0001",
            "forecast_id": "EVT0001-FC001",
            "initial_observation_id": "OBS0",
            "initial_timestamp": "2026-01-09T16:00:22Z",
            "valid_timestamp": "2026-01-10T04:00:22Z",
            "forecast_horizon_hours": 12,
            "predicted_centroid_lat": 38.5,
            "predicted_centroid_lon": 21.3,
            "forecast_confidence": 0.78,
            "ensemble_spread_km": 8.5,
        }
    ])


# ---------------------------------------------------------------------------
# Tests — node construction
# ---------------------------------------------------------------------------

class TestSpillObservationNodes:
    def test_creates_observation_and_scene_nodes(self):
        tables = {
            **_empty_tables(),
            "spill_observations": _d1_fixture(),
            "temporal_states": _d2_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        node_types = {n.node_type for n in result.nodes}
        assert "SPILL_OBSERVATION" in node_types

        node_ids = {n.node_id for n in result.nodes}
        assert "S1_EVT0001_02" in node_ids   # scene node from D1
        assert "EVT0001-OBS000" in node_ids  # observation node from D2

    def test_confidence_verbatim(self):
        """Confidence must be passed through exactly — never averaged."""
        tables = {
            **_empty_tables(),
            "spill_observations": _d1_fixture(),
            "temporal_states": _d2_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        obs_nodes = [n for n in result.nodes if n.node_id == "EVT0001-OBS000"]
        assert len(obs_nodes) > 0
        assert obs_nodes[0].confidence == pytest.approx(0.99)

    def test_derived_from_edge_created(self):
        tables = {
            **_empty_tables(),
            "spill_observations": _d1_fixture(),
            "temporal_states": _d2_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        df_edges = [e for e in result.edges if e.relation_type == "DERIVED-FROM"]
        assert len(df_edges) > 0

    def test_edge_has_provenance(self):
        tables = {
            **_empty_tables(),
            "spill_observations": _d1_fixture(),
            "temporal_states": _d2_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        for edge in result.edges:
            assert edge.provenance is not None and edge.provenance != ""


class TestEnvironmentalStateNode:
    def test_env_node_always_created(self):
        """ENVIRONMENTAL_STATE node is created even with all empty tables."""
        builder = GraphBuilder(**_empty_tables())
        result = builder.build_for_event("EVT0001")

        env_nodes = [n for n in result.nodes if n.node_type == "ENVIRONMENTAL_STATE"]
        assert len(env_nodes) == 1
        assert env_nodes[0].node_id == "EVT0001-ENV"

    def test_env_node_provenance(self):
        builder = GraphBuilder(**_empty_tables())
        result = builder.build_for_event("EVT0001")
        env_node = next(n for n in result.nodes if n.node_type == "ENVIRONMENTAL_STATE")
        assert "ERA5" in env_node.provenance


class TestSourceHypothesisNodes:
    def test_creates_hypothesis_node(self):
        tables = {**_empty_tables(), "source_hypotheses": _d3_fixture()}
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        hyp_nodes = [n for n in result.nodes if n.node_type == "SOURCE_HYPOTHESIS"]
        assert len(hyp_nodes) == 1
        assert hyp_nodes[0].node_id == "EVT0001-HYP000"

    def test_hypothesis_confidence_verbatim(self):
        tables = {**_empty_tables(), "source_hypotheses": _d3_fixture()}
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        hyp = next(n for n in result.nodes if n.node_type == "SOURCE_HYPOTHESIS")
        assert hyp.confidence == pytest.approx(0.85)
        assert hyp.uncertainty == pytest.approx(12.3)

    def test_hypothesis_derived_from_env(self):
        tables = {**_empty_tables(), "source_hypotheses": _d3_fixture()}
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        env_edges = [
            e for e in result.edges
            if e.target_node_id == "EVT0001-ENV" and e.relation_type == "DERIVED-FROM"
        ]
        assert len(env_edges) >= 1


class TestVesselNodes:
    def test_creates_vessel_node(self):
        tables = {
            **_empty_tables(),
            "source_hypotheses": _d3_fixture(),
            "vessel_tracks": _d4_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        vessel_nodes = [n for n in result.nodes if n.node_type == "VESSEL"]
        assert len(vessel_nodes) == 1

    def test_temporal_compatible_edge(self):
        tables = {
            **_empty_tables(),
            "source_hypotheses": _d3_fixture(),
            "vessel_tracks": _d4_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        tc_edges = [e for e in result.edges if e.relation_type == "TEMPORALLY-COMPATIBLE"]
        assert len(tc_edges) >= 1
        assert tc_edges[0].confidence == pytest.approx(0.72)


class TestEvidenceNodes:
    def test_creates_evidence_node(self):
        tables = {
            **_empty_tables(),
            "source_hypotheses": _d3_fixture(),
            "vessel_tracks": _d4_fixture(),
            "evidence_items": _d5_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        ev_nodes = [n for n in result.nodes if n.node_type == "EVIDENCE"]
        assert len(ev_nodes) >= 1

    def test_supports_edge_created(self):
        tables = {
            **_empty_tables(),
            "source_hypotheses": _d3_fixture(),
            "vessel_tracks": _d4_fixture(),
            "evidence_items": _d5_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        sup_edges = [e for e in result.edges if e.relation_type == "SUPPORTS"]
        assert len(sup_edges) >= 1


class TestForecastNodes:
    def test_creates_forecast_node(self):
        tables = {**_empty_tables(), "forecasts": _d8_fixture()}
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        fc_nodes = [n for n in result.nodes if n.node_type == "FORECAST"]
        assert len(fc_nodes) == 1
        assert fc_nodes[0].confidence == pytest.approx(0.78)
        assert fc_nodes[0].uncertainty == pytest.approx(8.5)


# ---------------------------------------------------------------------------
# Tests — taxonomy enforcement
# ---------------------------------------------------------------------------

class TestTaxonomy:
    def test_all_node_types_are_valid(self):
        tables = {
            **_empty_tables(),
            "spill_observations": _d1_fixture(),
            "source_hypotheses": _d3_fixture(),
            "vessel_tracks": _d4_fixture(),
            "evidence_items": _d5_fixture(),
            "forecasts": _d8_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        for node in result.nodes:
            assert node.node_type in NODE_TYPES, (
                f"Invalid node_type {node.node_type!r} on node {node.node_id!r}"
            )

    def test_all_edge_types_are_valid(self):
        tables = {
            **_empty_tables(),
            "spill_observations": _d1_fixture(),
            "source_hypotheses": _d3_fixture(),
            "vessel_tracks": _d4_fixture(),
            "evidence_items": _d5_fixture(),
            "forecasts": _d8_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        for edge in result.edges:
            assert edge.relation_type in EDGE_TYPES, (
                f"Invalid relation_type {edge.relation_type!r} on edge {edge.edge_id!r}"
            )


# ---------------------------------------------------------------------------
# Tests — partial pipeline tolerance
# ---------------------------------------------------------------------------

class TestPartialPipeline:
    def test_empty_all_tables_returns_partial(self):
        """A totally empty upstream state must return a partial graph, not error."""
        builder = GraphBuilder(**_empty_tables())
        result = builder.build_for_event("EVT9999")

        assert isinstance(result, GraphResult)
        assert result.is_partial is True
        # ENV node still created
        env = [n for n in result.nodes if n.node_type == "ENVIRONMENTAL_STATE"]
        assert len(env) == 1

    def test_only_d1_available(self):
        # D1 alone now requires D2 to produce OBS nodes; result is partial
        # but ENV node is still created
        tables = {**_empty_tables(), "spill_observations": _d1_fixture()}
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        assert result.is_partial is True
        env = [n for n in result.nodes if n.node_type == "ENVIRONMENTAL_STATE"]
        assert len(env) == 1

    def test_d1_and_d2_produce_obs_nodes(self):
        """With both D1 and D2, SPILL_OBSERVATION nodes are produced."""
        tables = {
            **_empty_tables(),
            "spill_observations": _d1_fixture(),
            "temporal_states": _d2_fixture(),
        }
        builder = GraphBuilder(**tables)
        result = builder.build_for_event("EVT0001")

        obs = [n for n in result.nodes if n.node_type == "SPILL_OBSERVATION"]
        assert len(obs) > 0

    def test_no_error_on_unknown_event(self):
        builder = GraphBuilder(**_empty_tables())
        result = builder.build_for_event("EVT_DOES_NOT_EXIST")
        assert isinstance(result, GraphResult)


# ---------------------------------------------------------------------------
# Integration test — synthetic pipeline node/edge counts within tolerance
# ---------------------------------------------------------------------------

class TestIntegrationSyntheticPipeline:
    """
    Loads all synthetic CSVs, builds the full graph, and checks that
    node/edge counts are within 20% of the reference D7 outputs.
    """

    @pytest.fixture(scope="class")
    def synthetic_result(self):
        from shared.mocks.load_mock import load_mock_df as load_mock

        def _load(name):
            try:
                return load_mock(name)
            except Exception:
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
        builder = GraphBuilder(**tables)
        results = builder.build_all_events()
        all_nodes = []
        all_edges = []
        for r in results.values():
            all_nodes.extend(r.nodes)
            all_edges.extend(r.edges)
        return all_nodes, all_edges

    @pytest.fixture(scope="class")
    def ref_counts(self):
        from shared.mocks.load_mock import load_mock_df as load_mock
        try:
            ref_n = len(load_mock("graph_nodes"))
            ref_e = len(load_mock("graph_edges"))
        except Exception:
            ref_n, ref_e = 417, 613
        return ref_n, ref_e

    def test_node_count_within_tolerance(self, synthetic_result, ref_counts):
        nodes, _ = synthetic_result
        ref_n, _ = ref_counts
        our_n = len(nodes)
        pct = abs(our_n - ref_n) / max(ref_n, 1)
        assert pct <= 0.20, (
            f"Node count {our_n} differs from reference {ref_n} by {pct:.1%} (>20% tolerance)"
        )

    def test_edge_count_within_tolerance(self, synthetic_result, ref_counts):
        _, edges = synthetic_result
        _, ref_e = ref_counts
        our_e = len(edges)
        pct = abs(our_e - ref_e) / max(ref_e, 1)
        assert pct <= 0.20, (
            f"Edge count {our_e} differs from reference {ref_e} by {pct:.1%} (>20% tolerance)"
        )

    def test_output_validates_against_schema(self, synthetic_result):
        from shared.schemas.envelope import NodeSchema, EdgeSchema
        nodes, edges = synthetic_result
        for node in nodes:
            NodeSchema(**node.to_dict())  # raises ValidationError if wrong
        for edge in edges:
            EdgeSchema(**edge.to_dict())
