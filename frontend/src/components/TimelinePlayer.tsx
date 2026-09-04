import { useEffect, useRef, useState } from "react";
import { maskUrl, quicklookUrl } from "../api/client";
import type { TemporalSpillState } from "../api/types";
import { playAlertSound } from "../lib/alertSound";
import type { LayerVisibility } from "./LayerToggles";

interface Props {
  eventId: string;
  states: TemporalSpillState[]; // full set (OBSERVED + INTERPOLATED + PREDICTED)
  stepIndex: number;
  onStepChange: (i: number) => void;
  layers: LayerVisibility;
  onLayersChange: (next: LayerVisibility) => void;
  hasForecast: boolean;
  onEnableForecast: () => void;
}

const PLAY_INTERVAL_MS = 2600;

function fmtSigned(n: number, digits = 1) {
  return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}`;
}

export default function TimelinePlayer({
  eventId,
  states,
  stepIndex,
  onStepChange,
  layers,
  onLayersChange,
  hasForecast,
  onEnableForecast,
}: Props) {
  const observed = states.filter((s) => s.state_type === "OBSERVED").sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  const [playing, setPlaying] = useState(false);
  const [showMask, setShowMask] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const alertedForRef = useRef<string | null>(null);

  const current = observed[stepIndex];
  const previous = stepIndex > 0 ? observed[stepIndex - 1] : null;

  // Play the alert the moment step 0 is reached for this event (on load, or
  // if the user scrubs back to the first detection).
  useEffect(() => {
    if (!current || stepIndex !== 0) return;
    const key = `${eventId}:${current.observation_id}`;
    if (alertedForRef.current === key) return;
    alertedForRef.current = key;
    playAlertSound();
  }, [eventId, current, stepIndex]);

  // Auto-advance while playing.
  useEffect(() => {
    if (!playing) return;
    timerRef.current = setInterval(() => {
      onStepChange(Math.min(stepIndex + 1, observed.length - 1));
    }, PLAY_INTERVAL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, stepIndex, observed.length]);

  useEffect(() => {
    if (stepIndex >= observed.length - 1) setPlaying(false);
  }, [stepIndex, observed.length]);

  if (observed.length === 0) {
    return (
      <div className="timeline-player panel-card">
        <h3>Investigation playback</h3>
        <p className="muted small">No observed satellite passes for this event.</p>
      </div>
    );
  }

  const areaDelta = previous ? current.area_km2 - previous.area_km2 : null;
  const areaPct =
    current.area_change_pct != null
      ? current.area_change_pct
      : previous && previous.area_km2 > 0
        ? ((current.area_km2 - previous.area_km2) / previous.area_km2) * 100
        : null;
  const shiftKm = current.centroid_displacement_km ?? null;

  function toggle(key: keyof LayerVisibility) {
    if (key === "forecast" && !layers.forecast && !hasForecast) onEnableForecast();
    onLayersChange({ ...layers, [key]: !layers[key] });
  }

  return (
    <div className="timeline-player panel-card">
      <div className="tp-header">
        <h3>Investigation playback</h3>
        <span className="muted small">
          Pass {stepIndex + 1} / {observed.length} · {new Date(current.timestamp).toLocaleString()}
        </span>
      </div>

      {stepIndex === 0 && (
        <div className="alert-banner" role="alert">
          🚨 <strong>Spill detected</strong> — {current.area_km2.toFixed(1)} km² · confidence{" "}
          {current.f1_confidence != null ? `${(current.f1_confidence * 100).toFixed(0)}%` : "n/a"}
        </div>
      )}

      {stepIndex > 0 && (
        <div className={`delta-banner ${areaDelta != null && areaDelta >= 0 ? "delta-up" : "delta-down"}`}>
          {areaDelta != null && (
            <span>
              {areaDelta >= 0 ? "▲" : "▼"} area {fmtSigned(areaDelta)} km²
              {areaPct != null ? ` (${fmtSigned(areaPct, 0)}%)` : ""}
            </span>
          )}
          {shiftKm != null && <span> · moved {shiftKm.toFixed(1)} km</span>}
        </div>
      )}

      {current.scene_id && (
        <div className="tp-image-frame">
          <img src={quicklookUrl(current.scene_id)} alt={current.scene_id} className="tp-base-image" />
          {showMask && <img src={maskUrl(current.scene_id)} alt="" className="tp-mask-overlay" />}
          <button className="tp-mask-toggle" onClick={() => setShowMask((v) => !v)}>
            {showMask ? "Hide AI marking" : "Show AI marking"}
          </button>
        </div>
      )}

      <div className="tp-controls">
        <button onClick={() => onStepChange(0)} disabled={stepIndex === 0} title="First pass">
          ⏮
        </button>
        <button onClick={() => onStepChange(Math.max(0, stepIndex - 1))} disabled={stepIndex === 0}>
          ◀ Prev
        </button>
        <button className="primary" onClick={() => setPlaying((p) => !p)}>
          {playing ? "⏸ Pause" : "▶ Play"}
        </button>
        <button
          onClick={() => onStepChange(Math.min(observed.length - 1, stepIndex + 1))}
          disabled={stepIndex >= observed.length - 1}
        >
          Next ▶
        </button>
        <button
          onClick={() => onStepChange(observed.length - 1)}
          disabled={stepIndex >= observed.length - 1}
          title="Latest pass"
        >
          ⏭
        </button>
      </div>

      <input
        type="range"
        min={0}
        max={observed.length - 1}
        value={stepIndex}
        onChange={(e) => onStepChange(Number(e.target.value))}
        className="tp-scrubber"
      />

      <div className="tp-toggles">
        <button className={`chip ${layers.vessels ? "chip-on" : ""}`} onClick={() => toggle("vessels")}>
          🚢 Vessels
        </button>
        <button className={`chip ${layers.source ? "chip-on" : ""}`} onClick={() => toggle("source")}>
          🎯 Source
        </button>
        <button className={`chip ${layers.forecast ? "chip-on" : ""}`} onClick={() => toggle("forecast")}>
          🔮 Future
        </button>
      </div>
    </div>
  );
}
