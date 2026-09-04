import type { TemporalSpillState } from "../api/types";

const DOT_COLOR: Record<string, string> = {
  OBSERVED: "#ff7a45",
  INTERPOLATED: "#ffb066",
  PREDICTED: "#5b6270",
};

interface Props {
  states: TemporalSpillState[];
}

/** Area-vs-time sparkline across F2's observed/interpolated/predicted states. */
export default function Timeline({ states }: Props) {
  if (states.length === 0) {
    return (
      <div className="timeline panel-card">
        <h3>Temporal reconstruction</h3>
        <p className="muted">No temporal states loaded yet.</p>
      </div>
    );
  }

  const sorted = [...states].sort((a, b) => (a.sim_hours ?? 0) - (b.sim_hours ?? 0));
  const maxArea = Math.max(...sorted.map((s) => s.area_km2), 1);
  const w = 100 / Math.max(sorted.length - 1, 1);

  const points = sorted
    .map((s, i) => {
      const x = i * w;
      const y = 100 - (s.area_km2 / maxArea) * 90;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="timeline panel-card">
      <h3>Slick evolution</h3>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="timeline-svg">
        <polyline points={points} fill="none" stroke="#4f8dff" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        {sorted.map((s, i) => (
          <circle
            key={s.observation_id}
            cx={i * w}
            cy={100 - (s.area_km2 / maxArea) * 90}
            r={1.6}
            fill={DOT_COLOR[s.state_type] ?? "#888"}
          />
        ))}
      </svg>
      <div className="timeline-labels">
        {sorted.map((s) => (
          <div key={s.observation_id} className="timeline-label" title={`${s.timestamp} · ${s.state_type}`}>
            <span className="dot" style={{ background: DOT_COLOR[s.state_type] ?? "#888" }} />
            {s.area_km2.toFixed(1)} km²
          </div>
        ))}
      </div>
    </div>
  );
}
