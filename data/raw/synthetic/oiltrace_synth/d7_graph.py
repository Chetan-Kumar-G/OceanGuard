"""D7 - evidence graph dataset (derived).

Two tables (nodes, edges) assembled from D2..D8. Node types:
  SPILL_OBSERVATION | SOURCE_HYPOTHESIS | ENVIRONMENTAL_STATE | VESSEL | EVIDENCE | FORECAST
Edge relations:
  DERIVED-FROM | SUPPORTS | CONTRADICTS | TEMPORALLY-COMPATIBLE
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config


def generate_d7(cfg: Config, d2: pd.DataFrame, d3_hyp: pd.DataFrame,
                d4_tracks: pd.DataFrame, d5: pd.DataFrame, d8_runs: pd.DataFrame):
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()

    def add_node(node_id, event_id, ntype, ts="", lat=np.nan, lon=np.nan,
                 confidence=np.nan, uncertainty=np.nan, provenance=""):
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append(dict(node_id=node_id, event_id=event_id, node_type=ntype,
                          timestamp=ts, latitude=lat, longitude=lon,
                          confidence=confidence, uncertainty=uncertainty,
                          provenance=provenance))

    def add_edge(src, tgt, rel, event_id, confidence=np.nan, ts="", provenance=""):
        edges.append(dict(edge_id=f"E{len(edges) + 1:06d}", event_id=event_id,
                          source_node_id=src, target_node_id=tgt, relation_type=rel,
                          confidence=confidence, timestamp=ts, provenance=provenance))

    # SPILL_OBSERVATION nodes (observed states only)
    obs = d2[d2.state_type == "OBSERVED"] if not d2.empty else d2
    for _, r in obs.iterrows():
        add_node(r["observation_id"], r["event_id"], "SPILL_OBSERVATION",
                 ts=r["timestamp"], lat=r["centroid_lat"], lon=r["centroid_lon"],
                 confidence=r["f1_confidence"], provenance=f"scene:{r['scene_id']}")
        if r["scene_id"]:
            add_node(r["scene_id"], r["event_id"], "SPILL_OBSERVATION",
                     ts=r["timestamp"], provenance="D1")
            add_edge(r["observation_id"], r["scene_id"], "DERIVED-FROM", r["event_id"],
                     provenance="F1->F2")
        add_node(f"{r['event_id']}-ENV", r["event_id"], "ENVIRONMENTAL_STATE",
                 provenance="ERA5+CMEMS(synthetic)")

    # chain consecutive observations
    for ev, grp in obs.groupby("event_id"):
        ids = grp.sort_values("sim_hours")["observation_id"].tolist()
        for a, b in zip(ids, ids[1:]):
            add_edge(b, a, "DERIVED-FROM", ev, provenance="temporal-successor")

    # SOURCE_HYPOTHESIS nodes
    for _, r in d3_hyp.iterrows():
        seed_ids = str(r.get("seed_state_ids", "")).split(";") if r.get("seed_state_ids", "") else []
        add_node(r["source_hypothesis_id"], r["event_id"], "SOURCE_HYPOTHESIS",
                 ts=r["origin_time_mid"], lat=r["source_lat"], lon=r["source_lon"],
                 confidence=r.get("source_probability", np.nan),
                 uncertainty=r["uncertainty_radius_km"],
                 provenance="seed:" + ",".join(seed_ids))
        for sid in seed_ids:
            add_edge(r["source_hypothesis_id"], sid, "DERIVED-FROM",
                     r["event_id"], provenance="F3 backtrack")
        add_edge(r["source_hypothesis_id"], f"{r['event_id']}-ENV", "DERIVED-FROM",
                 r["event_id"], provenance="forcing")

    # VESSEL nodes + temporal compatibility edges
    for _, r in d4_tracks.iterrows():
        vid = f"{r['event_id']}-V-{r['mmsi']}"
        add_node(vid, r["event_id"], "VESSEL", ts=r["closest_approach_timestamp"],
                 confidence=r["track_completeness"], provenance=f"AIS mmsi {r['mmsi']}")
        if r["source_hypothesis_id"] and float(r["temporal_compatibility"]) >= 0.5:
            add_edge(vid, r["source_hypothesis_id"], "TEMPORALLY-COMPATIBLE",
                     r["event_id"], confidence=r["temporal_compatibility"],
                     provenance="F4 vs F3")

    # EVIDENCE nodes + SUPPORTS / CONTRADICTS edges
    id_map = {}
    for _, r in d4_tracks.iterrows():
        id_map[str(r["track_id"])] = f"{r['event_id']}-V-{r['mmsi']}"
    for _, r in d5.iterrows():
        add_node(r["evidence_id"], r["event_id"], "EVIDENCE", ts=r["timestamp_b"],
                 confidence=r["sensor_confidence"], provenance=r["provenance"])
        a = id_map.get(str(r["source_a_id"]), r["source_a_id"])
        b = id_map.get(str(r["source_b_id"]), r["source_b_id"])
        add_edge(r["evidence_id"], a, "DERIVED-FROM", r["event_id"], provenance=r["source_a_type"])
        add_edge(r["evidence_id"], b, "DERIVED-FROM", r["event_id"], provenance=r["source_b_type"])
        if r["relation"] in ("SUPPORTS", "CONTRADICTS"):
            add_edge(a, b, r["relation"], r["event_id"],
                     confidence=r["sensor_confidence"], ts=r["timestamp_b"],
                     provenance=r["evidence_id"])

    # FORECAST nodes
    for _, r in d8_runs.iterrows():
        fid = f"{r['forecast_id']}-H{int(r['forecast_horizon_hours'])}"
        add_node(fid, r["event_id"], "FORECAST", ts=r["valid_timestamp"],
                 lat=r["predicted_centroid_lat"], lon=r["predicted_centroid_lon"],
                 confidence=r["forecast_confidence"], uncertainty=r["ensemble_spread_km"],
                 provenance=f"init:{r['initial_observation_id']}")
        add_edge(fid, r["initial_observation_id"], "DERIVED-FROM", r["event_id"],
                 provenance="F8 forward run")
        add_edge(fid, f"{r['event_id']}-ENV", "DERIVED-FROM", r["event_id"],
                 provenance="forecast forcing")

    return pd.DataFrame(nodes), pd.DataFrame(edges)
