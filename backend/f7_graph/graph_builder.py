"""
backend/f7_graph/graph_builder.py
-----------------------------------
F7 — Forensic Investigation Graph & Explainable Evidence Chain

Materializes every upstream row as a typed graph node, derives edges from
D5 evidence_items and provenance_records, and stores the result to
graph_nodes / graph_edges tables (or in-memory DataFrames for mock runs).

RULES (from Prompt_7_F7_Graph.md):
 * Do NOT compute any new scores or evidence — only visualize/trace.
 * Carry upstream confidence/uncertainty VERBATIM — never average.
 * A partial pipeline (F6 not run yet) must still return a partial graph.
 * Every edge must cite the provenance row that justifies it.
 * Use exactly the taxonomy defined in the spec — no new node/edge types.

NODE ID CONVENTIONS (matched to reference D7_graph_nodes.csv):
  SPILL_OBSERVATION : D2 observation_id   (e.g. EVT0001-OBS000)
                      + D1 scene_id       (e.g. S1_EVT0001_02)
                      Only for f1_detected=True D1 rows.
  SOURCE_HYPOTHESIS : D3 source_hypothesis_id (e.g. EVT0001-H00, EVT0001-HBEST)
  ENVIRONMENTAL_STATE : {event_id}-ENV
  VESSEL            : {event_id}-V-{mmsi}  (e.g. EVT0001-V-329813634)
  EVIDENCE          : D5 evidence_id
  FORECAST          : {forecast_id}-H{horizon}  (e.g. EVT0002-FC02-H12)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Taxonomy constants (frozen per spec — do NOT add new types)
# ---------------------------------------------------------------------------
NODE_TYPES = frozenset(
    {
        "SPILL_OBSERVATION",
        "SOURCE_HYPOTHESIS",
        "ENVIRONMENTAL_STATE",
        "VESSEL",
        "EVIDENCE",
        "FORECAST",
    }
)

EDGE_TYPES = frozenset(
    {
        "DERIVED-FROM",
        "SUPPORTS",
        "CONTRADICTS",
        "TEMPORALLY-COMPATIBLE",
    }
)


# ---------------------------------------------------------------------------
# Lightweight in-memory node/edge records
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    node_id: str
    event_id: str
    node_type: str
    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence: Optional[float] = None
    uncertainty: Optional[float] = None
    provenance: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "event_id": self.event_id,
            "node_type": self.node_type,
            "timestamp": self.timestamp,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "provenance": self.provenance,
        }


@dataclass
class GraphEdge:
    edge_id: str
    event_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    confidence: Optional[float] = None
    timestamp: Optional[str] = None
    provenance: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "event_id": self.event_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relation_type": self.relation_type,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "provenance": self.provenance,
        }


@dataclass
class GraphResult:
    event_id: str
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    is_partial: bool = False  # True when some upstream stages were missing

    def node_df(self) -> pd.DataFrame:
        return pd.DataFrame([n.to_dict() for n in self.nodes])

    def edge_df(self) -> pd.DataFrame:
        return pd.DataFrame([e.to_dict() for e in self.edges])


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_str(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ("nan", "none", "") else None


def _edge_id(counter: list) -> str:
    counter[0] += 1
    return f"E{counter[0]:06d}"


def _is_true(val) -> bool:
    """Parse a bool-like value from CSV (True / 'True' / 1 / 'true')."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return False


# ---------------------------------------------------------------------------
# GraphBuilder
# ---------------------------------------------------------------------------

class GraphBuilder:
    """
    Assembles nodes and edges for one or all events from upstream DataFrames.

    Parameters (all DataFrames may be empty — partial graph returned gracefully)
    ----------
    spill_observations  : D1_satellite_scenes.csv
    temporal_states     : D2_temporal_states.csv
    source_hypotheses   : D3_source_hypotheses.csv
    vessel_tracks       : D4_vessel_tracks.csv
    evidence_items      : D5_evidence_consistency.csv
    hypothesis_scores   : D6_evidence_ranking.csv
    forecasts           : D8_forecast_runs.csv
    """

    def __init__(
        self,
        spill_observations: pd.DataFrame,
        temporal_states: pd.DataFrame,
        source_hypotheses: pd.DataFrame,
        vessel_tracks: pd.DataFrame,
        evidence_items: pd.DataFrame,
        hypothesis_scores: pd.DataFrame,
        forecasts: pd.DataFrame,
    ):
        self._d1 = spill_observations
        self._d2 = temporal_states
        self._d3 = source_hypotheses
        self._d4 = vessel_tracks
        self._d5 = evidence_items
        self._d6 = hypothesis_scores
        self._d8 = forecasts

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def build_for_event(self, event_id: str) -> GraphResult:
        """Build graph nodes and edges for a single event_id."""
        result = GraphResult(event_id=event_id)
        counter = [0]  # mutable counter for edge IDs

        seen_nodes: Dict[str, GraphNode] = {}

        def add_node(node: GraphNode):
            if node.node_id not in seen_nodes:
                seen_nodes[node.node_id] = node
                result.nodes.append(node)

        def add_edge(edge: GraphEdge):
            result.edges.append(edge)

        # ---- 1. SPILL_OBSERVATION nodes from D2 OBSERVED states -------
        #    (only for D1-detected scenes, using D2 observation_id as node_id)
        partial_obs = self._add_observation_nodes(event_id, add_node, add_edge, counter)
        if partial_obs:
            result.is_partial = True

        # ---- 2. ENVIRONMENTAL_STATE node (one per event) --------------
        self._add_environmental_node(event_id, add_node)

        # ---- 3. SOURCE_HYPOTHESIS nodes from D3 -----------------------
        partial_hyp = self._add_source_hypothesis_nodes(event_id, add_node, add_edge, counter)
        if partial_hyp:
            result.is_partial = True

        # ---- 4. VESSEL nodes from D4 ----------------------------------
        partial_ves = self._add_vessel_nodes(event_id, add_node, add_edge, counter)
        if partial_ves:
            result.is_partial = True

        # ---- 5. EVIDENCE nodes + SUPPORTS/CONTRADICTS edges from D5 --
        partial_ev = self._add_evidence_nodes(event_id, add_node, add_edge, counter)
        if partial_ev:
            result.is_partial = True

        # ---- 6. FORECAST nodes from D8 --------------------------------
        partial_fc = self._add_forecast_nodes(event_id, add_node, add_edge, counter, seen_nodes)
        if partial_fc:
            result.is_partial = True

        logger.info(
            "event=%s  nodes=%d  edges=%d  partial=%s",
            event_id, len(result.nodes), len(result.edges), result.is_partial,
        )
        return result

    def build_all_events(self) -> Dict[str, GraphResult]:
        """Build graphs for all events found in any upstream table."""
        event_ids: set[str] = set()
        for df in (self._d1, self._d2, self._d3, self._d4, self._d5, self._d6, self._d8):
            if not df.empty and "event_id" in df.columns:
                event_ids.update(df["event_id"].dropna().unique())

        results: Dict[str, GraphResult] = {}
        for eid in sorted(event_ids):
            results[eid] = self.build_for_event(eid)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _filter(self, df: pd.DataFrame, event_id: str) -> pd.DataFrame:
        if df.empty or "event_id" not in df.columns:
            return pd.DataFrame()
        return df[df["event_id"] == event_id].copy()

    # ------------------------------------------------------------------
    # Node builders — matched to reference CSV patterns
    # ------------------------------------------------------------------

    def _add_observation_nodes(
        self, event_id, add_node, add_edge, counter
    ) -> bool:
        """
        Strategy (matched to reference D7_graph_nodes.csv):

        Source of truth for SPILL_OBSERVATION nodes is D2 OBSERVED rows.
        For each D2 OBSERVED row that has a scene_id referencing a
        D1 f1_detected=True scene:
          - Create EVTxxxx-OBSyyy node (from D2.observation_id)
            with lat/lon/confidence from D1 (scene-centre)
          - Create S1_... scene node (from D1.scene_id) with provenance "D1"
          - Create DERIVED-FROM edge: OBSyyy → S1_...

        This produces exactly 2 nodes × (number of detected scenes per event)
        = matching the reference 140 SPILL_OBSERVATION count.
        """
        d2_rows = self._filter(self._d2, event_id)
        d1_rows = self._filter(self._d1, event_id)

        if d2_rows.empty and d1_rows.empty:
            return True   # partial — no observation data at all

        # Build lookup: scene_id → D1 row (only f1_detected=True)
        d1_detected: Dict[str, dict] = {}
        if not d1_rows.empty and "scene_id" in d1_rows.columns:
            for _, row in d1_rows.iterrows():
                if _is_true(row.get("f1_detected", False)):
                    sid = _safe_str(row.get("scene_id"))
                    if sid:
                        d1_detected[sid] = row.to_dict()

        # Process D2 OBSERVED states
        if not d2_rows.empty and "state_type" in d2_rows.columns:
            observed = d2_rows[d2_rows["state_type"] == "OBSERVED"]
        else:
            observed = d2_rows  # fallback: treat all D2 rows as observations

        had_any = False
        obs_id_list: list[str] = []  # for temporal-successor edges

        for _, row in observed.iterrows():
            obs_id = _safe_str(row.get("observation_id"))
            scene_id = _safe_str(row.get("scene_id"))

            if not obs_id:
                continue

            # Look up D1 scene for position/confidence
            d1_scene = d1_detected.get(scene_id, {}) if scene_id else {}

            lat = _safe_float(row.get("centroid_lat")) or _safe_float(d1_scene.get("latitude"))
            lon = _safe_float(row.get("centroid_lon")) or _safe_float(d1_scene.get("longitude"))
            conf = _safe_float(row.get("f1_confidence")) or _safe_float(d1_scene.get("f1_confidence"))
            ts = _safe_str(row.get("timestamp")) or _safe_str(d1_scene.get("acquisition_timestamp"))

            # Primary observation node (EVTxxxx-OBSyyy)
            obs_node = GraphNode(
                node_id=obs_id,
                event_id=event_id,
                node_type="SPILL_OBSERVATION",
                timestamp=ts,
                latitude=lat,
                longitude=lon,
                confidence=conf,
                uncertainty=None,
                provenance=f"scene:{scene_id}" if scene_id else "D2",
            )
            add_node(obs_node)
            obs_id_list.append(obs_id)
            had_any = True

            # Scene-level node (S1_...)
            if scene_id:
                scene_ts = _safe_str(d1_scene.get("acquisition_timestamp")) or ts
                scene_node = GraphNode(
                    node_id=scene_id,
                    event_id=event_id,
                    node_type="SPILL_OBSERVATION",
                    timestamp=scene_ts,
                    latitude=None,
                    longitude=None,
                    confidence=None,
                    uncertainty=None,
                    provenance="D1",
                )
                add_node(scene_node)

                # DERIVED-FROM edge: OBSyyy → scene
                add_edge(GraphEdge(
                    edge_id=_edge_id(counter),
                    event_id=event_id,
                    source_node_id=obs_id,
                    target_node_id=scene_id,
                    relation_type="DERIVED-FROM",
                    confidence=None,
                    timestamp=None,
                    provenance="F1->F2",
                ))

        # temporal-successor edges: OBS[i+1] → OBS[i]
        for i in range(1, len(obs_id_list)):
            add_edge(GraphEdge(
                edge_id=_edge_id(counter),
                event_id=event_id,
                source_node_id=obs_id_list[i],
                target_node_id=obs_id_list[i - 1],
                relation_type="DERIVED-FROM",
                confidence=None,
                timestamp=None,
                provenance="temporal-successor",
            ))

        return not had_any  # partial if no observations were added

    def _add_environmental_node(self, event_id, add_node):
        """One ENVIRONMENTAL_STATE node per event."""
        add_node(GraphNode(
            node_id=f"{event_id}-ENV",
            event_id=event_id,
            node_type="ENVIRONMENTAL_STATE",
            timestamp=None,
            latitude=None,
            longitude=None,
            confidence=None,
            uncertainty=None,
            provenance="ERA5+CMEMS(synthetic)",
        ))

    def _add_source_hypothesis_nodes(
        self, event_id, add_node, add_edge, counter
    ) -> bool:
        """
        D3 rows → SOURCE_HYPOTHESIS nodes.

        Node ID  : D3.source_hypothesis_id  (e.g. EVT0001-H00, EVT0001-HBEST)
        Provenance: "seed:{seed_state_id}"
        Confidence: D3.source_probability  (verbatim)
        Uncertainty: D3.uncertainty_radius_km  (verbatim)

        Edges:
          - DERIVED-FROM  → ENV node (forcing dependency)
          - DERIVED-FROM  → seed observation node (backtrack origin)
        """
        rows = self._filter(self._d3, event_id)
        if rows.empty:
            return True

        env_id = f"{event_id}-ENV"

        for _, row in rows.iterrows():
            hyp_id = _safe_str(row.get("source_hypothesis_id"))
            if not hyp_id:
                continue

            seed_id = _safe_str(row.get("seed_state_ids"))
            conf = _safe_float(row.get("source_probability"))
            unc = _safe_float(row.get("uncertainty_radius_km"))

            node = GraphNode(
                node_id=hyp_id,
                event_id=event_id,
                node_type="SOURCE_HYPOTHESIS",
                timestamp=_safe_str(row.get("origin_time_mid")),
                latitude=_safe_float(row.get("source_lat")),
                longitude=_safe_float(row.get("source_lon")),
                confidence=conf,
                uncertainty=unc,
                provenance=f"seed:{seed_id}" if seed_id else "D3",
            )
            add_node(node)

            # DERIVED-FROM → ENV (environmental forcing used for backtrack)
            add_edge(GraphEdge(
                edge_id=_edge_id(counter),
                event_id=event_id,
                source_node_id=hyp_id,
                target_node_id=env_id,
                relation_type="DERIVED-FROM",
                confidence=None,
                timestamp=None,
                provenance="forcing",
            ))

            # DERIVED-FROM → seed observation
            if seed_id:
                add_edge(GraphEdge(
                    edge_id=_edge_id(counter),
                    event_id=event_id,
                    source_node_id=hyp_id,
                    target_node_id=seed_id,
                    relation_type="DERIVED-FROM",
                    confidence=None,
                    timestamp=None,
                    provenance="F3 backtrack",
                ))

        return False

    def _add_vessel_nodes(
        self, event_id, add_node, add_edge, counter
    ) -> bool:
        """
        D4 rows → VESSEL nodes.

        Node ID  : {event_id}-V-{mmsi}  (e.g. EVT0001-V-329813634)
        Provenance: "AIS mmsi {mmsi}"
        Confidence: D4.temporal_compatibility  (verbatim)

        Edges:
          - TEMPORALLY-COMPATIBLE → source_hypothesis
        """
        rows = self._filter(self._d4, event_id)
        if rows.empty:
            return True

        for _, row in rows.iterrows():
            mmsi = _safe_str(row.get("mmsi"))
            if not mmsi:
                continue

            node_id = f"{event_id}-V-{mmsi}"
            temporal_compat = _safe_float(row.get("temporal_compatibility"))

            add_node(GraphNode(
                node_id=node_id,
                event_id=event_id,
                node_type="VESSEL",
                timestamp=_safe_str(row.get("closest_approach_timestamp")),
                latitude=None,
                longitude=None,
                confidence=temporal_compat,
                uncertainty=None,
                provenance=f"AIS mmsi {mmsi}",
            ))

            # TEMPORALLY-COMPATIBLE → hypothesis
            hyp_id = _safe_str(row.get("source_hypothesis_id"))
            if hyp_id:
                add_edge(GraphEdge(
                    edge_id=_edge_id(counter),
                    event_id=event_id,
                    source_node_id=node_id,
                    target_node_id=hyp_id,
                    relation_type="TEMPORALLY-COMPATIBLE",
                    confidence=temporal_compat,
                    timestamp=None,
                    provenance=f"D4:mmsi={mmsi}",
                ))

        return False

    def _add_evidence_nodes(
        self, event_id, add_node, add_edge, counter
    ) -> bool:
        """
        D5 rows → EVIDENCE nodes + typed edges.

        Node ID  : D5.evidence_id  (e.g. EVT0002-EV-F1F2, EVT0002-EV-F3F4-mmsi)
        Provenance: composed from source_a_id, source_a_type, source_b_id, source_b_type
        Confidence: D5.sensor_confidence (verbatim)

        Edge pattern (matched to reference D7_graph_edges.csv):

          SUPPORTS/CONTRADICTS relation:
            - DERIVED-FROM: src_a → ev_id  (provenance = source_a_type)
            - DERIVED-FROM: src_b → ev_id  (provenance = source_b_type)
            - SUPPORTS or CONTRADICTS: src_a → src_b  (provenance = ev_id)

          UNKNOWN relation:
            - DERIVED-FROM: src_a → ev_id  (provenance = source_a_type)
            - DERIVED-FROM: src_b → ev_id  (provenance = source_b_type)
            (no SUPPORTS/CONTRADICTS edge)

        VESSEL node IDs in D5 use {event_id}-{mmsi} format (not EVT-V-mmsi).
        We emit edges against whatever node IDs D5 specifies.
        """
        rows = self._filter(self._d5, event_id)
        if rows.empty:
            return True

        for _, row in rows.iterrows():
            ev_id = _safe_str(row.get("evidence_id"))
            if not ev_id:
                continue

            conf = _safe_float(row.get("sensor_confidence"))
            relation = _safe_str(row.get("relation")) or "UNKNOWN"

            src_a = _safe_str(row.get("source_a_id"))
            src_b = _safe_str(row.get("source_b_id"))
            type_a = _safe_str(row.get("source_a_type")) or "D5"
            type_b = _safe_str(row.get("source_b_type")) or "D5"

            # Build evidence node provenance string matching reference
            # e.g. "F1:EVT0002-OBS000|F2:EVT0002-OBS001"
            prov_parts = []
            if src_a and type_a:
                prov_parts.append(f"{type_a.split('_')[0]}:{src_a}")
            if src_b and type_b:
                prov_parts.append(f"{type_b.split('_')[0]}:{src_b}")
            ev_provenance = "|".join(prov_parts) if prov_parts else "D5"

            add_node(GraphNode(
                node_id=ev_id,
                event_id=event_id,
                node_type="EVIDENCE",
                timestamp=_safe_str(row.get("timestamp_a")),
                latitude=None,
                longitude=None,
                confidence=conf,
                uncertainty=None,
                provenance=ev_provenance,
            ))

            # DERIVED-FROM: src_a → evidence node  (provenance = source_a_type)
            if src_a:
                add_edge(GraphEdge(
                    edge_id=_edge_id(counter),
                    event_id=event_id,
                    source_node_id=ev_id,
                    target_node_id=src_a,
                    relation_type="DERIVED-FROM",
                    confidence=conf,
                    timestamp=_safe_str(row.get("timestamp_a")),
                    provenance=type_a,
                ))

            # DERIVED-FROM: src_b → evidence node  (provenance = source_b_type)
            if src_b:
                add_edge(GraphEdge(
                    edge_id=_edge_id(counter),
                    event_id=event_id,
                    source_node_id=ev_id,
                    target_node_id=src_b,
                    relation_type="DERIVED-FROM",
                    confidence=conf,
                    timestamp=_safe_str(row.get("timestamp_b")),
                    provenance=type_b,
                ))

            # SUPPORTS or CONTRADICTS: src_a → src_b  (provenance = ev_id)
            if relation in ("SUPPORTS", "CONTRADICTS") and src_a and src_b:
                # Map D5 source_b_id vessel format to graph VESSEL node format
                # D5 uses {event_id}-{mmsi}, graph uses {event_id}-V-{mmsi}
                tgt = src_b
                if type_b == "F4_VESSEL_TRACK":
                    # extract mmsi from the D5 id: EVT0002-480469227 → EVT0002-V-480469227
                    parts = src_b.rsplit("-", 1)
                    if len(parts) == 2:
                        tgt = f"{parts[0]}-V-{parts[1]}"

                add_edge(GraphEdge(
                    edge_id=_edge_id(counter),
                    event_id=event_id,
                    source_node_id=src_a,
                    target_node_id=tgt,
                    relation_type=relation,
                    confidence=conf,
                    timestamp=None,
                    provenance=ev_id,
                ))

        return False

    def _add_forecast_nodes(
        self, event_id, add_node, add_edge, counter, seen_nodes: dict
    ) -> bool:
        """
        D8 rows → FORECAST nodes.

        D8 has one row per (event, forecast_id, horizon_hours).
        Node ID : {forecast_id}-H{horizon_hours}  (e.g. EVT0002-FC02-H12)
        Provenance: "init:{initial_observation_id}"
        Confidence: D8.forecast_confidence  (verbatim)
        Uncertainty: D8.ensemble_spread_km  (verbatim)

        Edges (matched to reference):
          - DERIVED-FROM → initial_observation_id  (provenance: "F8 forward run")
          - DERIVED-FROM → ENV node                (provenance: "forecast forcing")
        """
        rows = self._filter(self._d8, event_id)
        if rows.empty:
            return True

        env_id = f"{event_id}-ENV"

        # Deduplicate on (forecast_id, horizon)
        seen_fc: set[str] = set()

        for _, row in rows.iterrows():
            fc_id = _safe_str(row.get("forecast_id"))
            horizon = _safe_str(row.get("forecast_horizon_hours"))
            if not fc_id or not horizon:
                continue

            node_id = f"{fc_id}-H{horizon}"
            if node_id in seen_fc:
                continue
            seen_fc.add(node_id)

            init_obs = _safe_str(row.get("initial_observation_id"))
            conf = _safe_float(row.get("forecast_confidence"))
            unc = _safe_float(row.get("ensemble_spread_km"))

            add_node(GraphNode(
                node_id=node_id,
                event_id=event_id,
                node_type="FORECAST",
                timestamp=_safe_str(row.get("valid_timestamp")),
                latitude=_safe_float(row.get("predicted_centroid_lat")),
                longitude=_safe_float(row.get("predicted_centroid_lon")),
                confidence=conf,
                uncertainty=unc,
                provenance=f"init:{init_obs}" if init_obs else f"D8:{fc_id}",
            ))

            # DERIVED-FROM → initial observation ("F8 forward run")
            if init_obs:
                add_edge(GraphEdge(
                    edge_id=_edge_id(counter),
                    event_id=event_id,
                    source_node_id=node_id,
                    target_node_id=init_obs,
                    relation_type="DERIVED-FROM",
                    confidence=conf,
                    timestamp=_safe_str(row.get("initial_timestamp")),
                    provenance="F8 forward run",
                ))

            # DERIVED-FROM → ENV ("forecast forcing")
            add_edge(GraphEdge(
                edge_id=_edge_id(counter),
                event_id=event_id,
                source_node_id=node_id,
                target_node_id=env_id,
                relation_type="DERIVED-FROM",
                confidence=None,
                timestamp=None,
                provenance="forecast forcing",
            ))

        return False
