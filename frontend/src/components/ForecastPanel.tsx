import { useState } from "react";
import type { ForecastEvaluation, ForecastRun, ImpactAssessment } from "../api/types";
import type { ForecastRequestBody } from "../api/client";

interface Props {
  forecast: ForecastRun[];
  impact: ImpactAssessment[];
  replay: ForecastEvaluation[];
  selectedHorizon: number | null;
  onSelectHorizon: (h: number | null) => void;
  onRun: (params: ForecastRequestBody, options: { replay?: boolean }) => void;
  busy: boolean;
}

const HORIZON_CHOICES = [6, 12, 24, 48, 72, 96];

export default function ForecastPanel({ forecast, impact, replay, selectedHorizon, onSelectHorizon, onRun, busy }: Props) {
  const [horizons, setHorizons] = useState<number[]>([12, 24, 48, 72]);
  const [nEnsemble, setNEnsemble] = useState(16);
  const [nParticles, setNParticles] = useState(200);
  const [seed, setSeed] = useState(42);

  const activeHorizons = [...new Set(forecast.map((r) => r.forecast_horizon_hours))].sort((a, b) => a - b);
  const impactByHorizon = new Map(impact.map((i) => [i.forecast_horizon_hours, i]));
  const selected = forecast.find((r) => r.forecast_horizon_hours === selectedHorizon);
  const selectedImpact = selectedHorizon != null ? impactByHorizon.get(selectedHorizon) : undefined;

  function toggleHorizon(h: number) {
    setHorizons((hs) => (hs.includes(h) ? hs.filter((x) => x !== h) : [...hs, h].sort((a, b) => a - b)));
  }

  function run(withReplay: boolean) {
    onRun({ horizons_h: horizons, n_ensemble: nEnsemble, n_particles: nParticles, base_seed: seed }, { replay: withReplay });
  }

  return (
    <section className="panel-card">
      <h3>F8 forward forecast</h3>

      <div className="forecaster-controls">
        <div className="forecaster-row">
          <span className="muted small">Horizons (h)</span>
          <div className="chip-row">
            {HORIZON_CHOICES.map((h) => (
              <label key={h} className={`chip ${horizons.includes(h) ? "chip-on" : ""}`}>
                <input type="checkbox" checked={horizons.includes(h)} onChange={() => toggleHorizon(h)} />
                {h}
              </label>
            ))}
          </div>
        </div>
        <div className="forecaster-row">
          <label className="inline-field">
            Ensemble
            <input type="number" min={4} max={80} value={nEnsemble} onChange={(e) => setNEnsemble(Number(e.target.value))} />
          </label>
          <label className="inline-field">
            Particles
            <input type="number" min={20} max={2000} step={20} value={nParticles} onChange={(e) => setNParticles(Number(e.target.value))} />
          </label>
          <label className="inline-field">
            Seed
            <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
          </label>
        </div>
        <div className="horizon-buttons">
          <button onClick={() => run(false)} disabled={busy || horizons.length === 0}>
            {busy ? "Running…" : "Run forecaster"}
          </button>
          <button onClick={() => run(true)} disabled={busy || horizons.length === 0}>
            Run + replay validation
          </button>
        </div>
      </div>

      {activeHorizons.length === 0 ? (
        <p className="muted">Not yet computed.</p>
      ) : (
        <>
          <div className="horizon-buttons">
            <button className={selectedHorizon == null ? "active" : ""} onClick={() => onSelectHorizon(null)}>
              off
            </button>
            {activeHorizons.map((h) => (
              <button key={h} className={h === selectedHorizon ? "active" : ""} onClick={() => onSelectHorizon(h)}>
                +{h}h
              </button>
            ))}
          </div>
          {selected && (
            <dl className="kv">
              <dt>Ensemble spread</dt>
              <dd>{selected.ensemble_spread_km.toFixed(1)} km</dd>
              <dt>Forecast confidence</dt>
              <dd>{(selected.forecast_confidence * 100).toFixed(0)}%</dd>
              <dt>Coastline distance</dt>
              <dd>{selected.coastline_distance_km.toFixed(0)} km</dd>
              <dt>Beaching risk</dt>
              <dd>
                {selected.beaching_risk ? (
                  <span className="flag flag-warn">yes ⚠</span>
                ) : (
                  <span className="flag flag-ok">low</span>
                )}
              </dd>
              {selectedImpact && selectedImpact.impact_area_candidates.length > 0 && (
                <>
                  <dt>Impact candidates</dt>
                  <dd>{selectedImpact.impact_area_candidates.join(", ")}</dd>
                </>
              )}
            </dl>
          )}
        </>
      )}

      {replay.length > 0 && (
        <>
          <h4>Historical replay validation</h4>
          <table className="ranking-table">
            <thead>
              <tr>
                <th>Horizon</th>
                <th>Traj. error</th>
                <th>Envelope hit</th>
                <th>Calibrated</th>
              </tr>
            </thead>
            <tbody>
              {replay.map((e) => (
                <tr key={`${e.forecast_id}-${e.forecast_horizon_hours}`}>
                  <td>+{e.forecast_horizon_hours}h</td>
                  <td>{e.trajectory_error_km.toFixed(1)} km</td>
                  <td>{e.observed_centroid_in_envelope ? "✓" : "✕"}</td>
                  <td>{e.well_calibrated ? "✓" : "✕"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            Replay scores this event's forecast against later real satellite observations. A forecast is a scenario
            envelope, never a guaranteed path.
          </p>
        </>
      )}
    </section>
  );
}
