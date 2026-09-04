import { quicklookUrl } from "../api/client";
import type { TemporalSpillState } from "../api/types";

interface Props {
  states: TemporalSpillState[];
  onSelect?: (sceneId: string) => void;
}

/** F1 satellite quicklooks for every OBSERVED state that has a scene_id. */
export default function SatelliteThumbnails({ states, onSelect }: Props) {
  const scenes = states.filter((s) => s.state_type === "OBSERVED" && s.scene_id);

  if (scenes.length === 0) {
    return (
      <section className="panel-card">
        <h3>Satellite imagery</h3>
        <p className="muted small">No observed scenes for this event.</p>
      </section>
    );
  }

  return (
    <section className="panel-card">
      <h3>Satellite imagery (F1)</h3>
      <div className="thumb-strip">
        {scenes.map((s) => (
          <button key={s.scene_id} className="thumb" onClick={() => onSelect?.(s.scene_id!)} title={`${s.scene_id} · ${s.timestamp}`}>
            <img
              src={quicklookUrl(s.scene_id!)}
              alt={s.scene_id}
              loading="lazy"
              onError={(e) => {
                (e.target as HTMLImageElement).style.visibility = "hidden";
              }}
            />
            <span className="thumb-label">{s.area_km2.toFixed(1)} km²</span>
          </button>
        ))}
      </div>
    </section>
  );
}
