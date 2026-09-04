import type { GraphResponse } from "../api/types";

interface Props {
  graph: GraphResponse | null;
  eventId: string | null;
  selectedMmsi: string | null;
}

const NODE_TYPE_LABEL: Record<string, string> = {
  SPILL_OBSERVATION: "spill observation",
  SOURCE_HYPOTHESIS: "source hypothesis",
  ENVIRONMENTAL_STATE: "environmental state",
  VESSEL: "vessel",
  EVIDENCE: "evidence",
  FORECAST: "forecast",
};

export default function GraphExplorer({ graph, eventId, selectedMmsi }: Props) {
  if (!graph) {
    return (
      <section className="panel-card">
        <h3>F7 forensic evidence chain</h3>
        <p className="muted">Not yet computed.</p>
      </section>
    );
  }

  const counts: Record<string, number> = {};
  for (const n of graph.nodes) counts[n.node_type] = (counts[n.node_type] ?? 0) + 1;

  const vesselNodeId = selectedMmsi && eventId ? `${eventId}-V-${selectedMmsi}` : null;
  const relatedEdges = vesselNodeId
    ? graph.edges.filter((e) => e.source_node_id === vesselNodeId || e.target_node_id === vesselNodeId)
    : [];

  return (
    <section className="panel-card">
      <h3>F7 forensic evidence chain</h3>
      <p className="muted small">
        {graph.node_count} nodes · {graph.edge_count} edges{graph.is_partial ? " · partial (upstream stage missing)" : ""}
      </p>
      <div className="node-type-counts">
        {Object.entries(counts).map(([type, n]) => (
          <span key={type} className="tag tag-neutral">
            {n} {NODE_TYPE_LABEL[type] ?? type}
          </span>
        ))}
      </div>

      {vesselNodeId && (
        <>
          <h4>Why vessel {selectedMmsi}?</h4>
          {relatedEdges.length === 0 ? (
            <p className="muted small">No graph edges reference this vessel yet.</p>
          ) : (
            <ul className="evidence-list">
              {relatedEdges.map((e) => (
                <li key={e.edge_id} className={`evidence-item edge-${e.relation_type.toLowerCase()}`}>
                  <strong>{e.relation_type}</strong>{" "}
                  <span className="muted small">
                    {e.source_node_id} → {e.target_node_id}
                  </span>
                  {e.provenance && <div className="muted small">via {e.provenance}</div>}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
