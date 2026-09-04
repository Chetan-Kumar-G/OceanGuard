"""
backend/f7_graph/traversal.py
------------------------------
NetworkX-based in-process traversal and explanation engine for F7.

Provides:
  - build_nx_graph(result)       : convert GraphResult → nx.DiGraph
  - explain_ranking(graph, event_id, hypothesis_id)
                                  : "why is this candidate ranked N?"
                                    trace back to originating satellite scene
  - find_evidence_chain(graph, source_node_id, target_node_id)
                                  : shortest path + edge annotations

These functions are used to construct the API response for the
clickable evidence chain required by the acceptance criteria.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False
    logger.warning("networkx not installed — traversal features disabled. pip install networkx")

from backend.f7_graph.graph_builder import GraphResult


def build_nx_graph(result: GraphResult):
    """
    Convert a GraphResult into a NetworkX DiGraph.

    Nodes carry all GraphNode attributes as node data.
    Edges carry all GraphEdge attributes as edge data.

    Returns None if networkx is not installed.
    """
    if not _NX_AVAILABLE:
        return None

    G = nx.DiGraph()

    for node in result.nodes:
        G.add_node(node.node_id, **node.to_dict())

    for edge in result.edges:
        G.add_edge(
            edge.source_node_id,
            edge.target_node_id,
            **edge.to_dict(),
        )

    logger.debug(
        "Built nx graph for event=%s: %d nodes, %d edges",
        result.event_id, G.number_of_nodes(), G.number_of_edges(),
    )
    return G


def explain_ranking(
    graph,
    event_id: str,
    hypothesis_id: str,
    max_depth: int = 10,
) -> Dict[str, Any]:
    """
    Answer: "Why is this candidate ranked N?"

    Performs a backwards BFS from the hypothesis node, following
    DERIVED-FROM / SUPPORTS edges upstream, until it reaches
    SPILL_OBSERVATION nodes (the raw satellite scene roots).

    Parameters
    ----------
    graph          : nx.DiGraph from build_nx_graph()
    event_id       : the event being investigated
    hypothesis_id  : node_id of the SOURCE_HYPOTHESIS to explain
    max_depth      : BFS depth limit

    Returns
    -------
    dict with keys:
        hypothesis_id, event_id,
        chain          : ordered list of node dicts (from hypothesis → scene),
        evidence_items : list of edge dicts on the chain,
        terminal_scenes: list of SPILL_OBSERVATION node_ids at the chain root
    """
    if not _NX_AVAILABLE or graph is None:
        return {"error": "networkx unavailable", "hypothesis_id": hypothesis_id}

    if hypothesis_id not in graph:
        return {"error": f"Node {hypothesis_id} not in graph", "hypothesis_id": hypothesis_id}

    # Reverse the graph so we can BFS "backwards" from hypothesis
    rev = graph.reverse(copy=False)

    chain_nodes = []
    chain_edges = []
    terminal_scenes = []

    visited = set()
    queue = [(hypothesis_id, 0)]

    while queue:
        current_id, depth = queue.pop(0)
        if current_id in visited or depth > max_depth:
            continue
        visited.add(current_id)

        node_data = graph.nodes.get(current_id, {})
        chain_nodes.append(node_data)

        node_type = node_data.get("node_type", "")
        if node_type == "SPILL_OBSERVATION":
            terminal_scenes.append(current_id)
            continue  # don't go further back from raw observations

        for neighbor in rev.successors(current_id):
            edge_data = graph.edges.get((neighbor, current_id), {})
            rel = edge_data.get("relation_type", "")
            if rel in ("DERIVED-FROM", "SUPPORTS"):
                chain_edges.append(edge_data)
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))

    return {
        "hypothesis_id": hypothesis_id,
        "event_id": event_id,
        "chain": chain_nodes,
        "evidence_items": chain_edges,
        "terminal_scenes": terminal_scenes,
    }


def find_evidence_chain(
    graph,
    source_node_id: str,
    target_node_id: str,
) -> Dict[str, Any]:
    """
    Find the shortest path between two nodes in the graph.

    Returns
    -------
    dict with keys:
        found        : bool
        path_nodes   : list of node dicts along the path
        path_edges   : list of edge dicts along the path
        length       : path length in hops
    """
    if not _NX_AVAILABLE or graph is None:
        return {"found": False, "error": "networkx unavailable"}

    try:
        # Use undirected view for reachability
        undirected = graph.to_undirected()
        path = nx.shortest_path(undirected, source=source_node_id, target=target_node_id)
    except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
        return {"found": False, "error": str(e), "path_nodes": [], "path_edges": []}

    path_nodes = [graph.nodes.get(n, {"node_id": n}) for n in path]
    path_edges = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        edge = graph.edges.get((a, b)) or graph.edges.get((b, a)) or {}
        path_edges.append(edge)

    return {
        "found": True,
        "path_nodes": path_nodes,
        "path_edges": path_edges,
        "length": len(path) - 1,
    }
