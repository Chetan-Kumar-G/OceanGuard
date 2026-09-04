export interface LayerVisibility {
  spill: boolean;
  source: boolean;
  vessels: boolean;
  forecast: boolean;
}

export const DEFAULT_LAYERS: LayerVisibility = { spill: true, source: true, vessels: true, forecast: true };

const LABELS: Record<keyof LayerVisibility, string> = {
  spill: "Spill polygons",
  source: "Source region",
  vessels: "Candidate vessels",
  forecast: "Forecast overlay",
};

interface Props {
  value: LayerVisibility;
  onChange: (next: LayerVisibility) => void;
}

export default function LayerToggles({ value, onChange }: Props) {
  return (
    <div className="layer-toggles">
      {(Object.keys(LABELS) as (keyof LayerVisibility)[]).map((key) => (
        <label key={key} className="layer-toggle">
          <input
            type="checkbox"
            checked={value[key]}
            onChange={(e) => onChange({ ...value, [key]: e.target.checked })}
          />
          {LABELS[key]}
        </label>
      ))}
    </div>
  );
}
