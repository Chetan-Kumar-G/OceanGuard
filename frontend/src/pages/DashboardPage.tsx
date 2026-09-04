import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import EventSelector from "../components/EventSelector";
import PipelineStatus from "../components/PipelineStatus";
import MapView from "../components/MapView";
import SidePanel from "../components/SidePanel";
import ForecastPanel from "../components/ForecastPanel";
import GraphExplorer from "../components/GraphExplorer";
import TimelinePlayer from "../components/TimelinePlayer";
import { DEFAULT_LAYERS, type LayerVisibility } from "../components/LayerToggles";
import { useEventPipeline } from "../hooks/useEventPipeline";
import { useAuth } from "../auth/AuthContext";

// AOI centre from the bundled synthetic dataset's config.used.yaml (aoi.ref_lat/ref_lon).
const DEFAULT_CENTER: [number, number] = [18.0, 35.0];

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const { state, load, rerunForecast } = useEventPipeline();
  const [selectedMmsi, setSelectedMmsi] = useState<string | null>(null);
  const [selectedHorizon, setSelectedHorizon] = useState<number | null>(null);
  const [layers, setLayers] = useState<LayerVisibility>(DEFAULT_LAYERS);
  const [stepIndex, setStepIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<"evidence" | "forecast" | "graph">("evidence");
  const isLoading = Object.values(state.status).some((s) => s === "loading");

  // Reset the playback position whenever a new event finishes loading.
  useEffect(() => {
    setStepIndex(0);
  }, [state.eventId, state.temporal]);

  const observedStates = useMemo(
    () =>
      (state.temporal?.states ?? [])
        .filter((s) => s.state_type === "OBSERVED")
        .sort((a, b) => a.timestamp.localeCompare(b.timestamp)),
    [state.temporal],
  );

  // The map shows the story "as of" the current playback step - only the
  // satellite passes revealed so far, so the polygon visibly grows/shifts
  // as you step or play through.
  const revealedStates = useMemo(() => observedStates.slice(0, stepIndex + 1), [observedStates, stepIndex]);

  const center = useMemo<[number, number]>(() => {
    const latest = revealedStates.at(-1);
    return latest ? [latest.centroid_lon, latest.centroid_lat] : DEFAULT_CENTER;
  }, [revealedStates]);

  const forecastRun = useMemo(
    () => state.forecast.find((r) => r.forecast_horizon_hours === selectedHorizon) ?? null,
    [state.forecast, selectedHorizon],
  );

  function handleSelectEvent(eventId: string) {
    setSelectedMmsi(null);
    setSelectedHorizon(null);
    setStepIndex(0);
    setActiveTab("evidence");
    void load(eventId);
  }

  function enableForecast() {
    const horizons = [...new Set(state.forecast.map((r) => r.forecast_horizon_hours))].sort((a, b) => a - b);
    if (horizons.length > 0) setSelectedHorizon(horizons[0]);
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-icon">🛢️</span>
          <div>
            <h1>OilTrace AI</h1>
            <p className="tagline">Investigator dashboard — F1–F8</p>
          </div>
        </div>
        <EventSelector value={state.eventId} onChange={handleSelectEvent} disabled={isLoading} />
        {state.eventId && <PipelineStatus status={state.status} errors={state.errors} />}
        <nav className="top-nav">
          <Link to="/review">Appeals</Link>
        </nav>
        <span className="user-badge">
          {user?.display_name} <span className="muted small">({user?.role})</span>
          <button className="link-button" onClick={logout}>
            Sign out
          </button>
        </span>
      </header>

      <p className="disclaimer" title="Candidate vessels are evidence-based associations for investigation, not confirmed legal responsibility. See Technical Boundaries in the project specification.">
        Candidates are evidence-based associations, not confirmed responsibility. <Link to="/appeal">Dispute a flag</Link> — no account needed.
      </p>

      {state.eventId && observedStates.length > 0 && (
        <div className="player-row">
          <TimelinePlayer
            eventId={state.eventId}
            states={state.temporal?.states ?? []}
            stepIndex={stepIndex}
            onStepChange={setStepIndex}
            layers={layers}
            onLayersChange={setLayers}
            hasForecast={state.forecast.length > 0}
            onEnableForecast={enableForecast}
          />
        </div>
      )}

      <main className="layout">
        <div className="map-pane">
          {state.eventId ? (
            <MapView
              center={center}
              states={revealedStates}
              hypotheses={state.hypotheses}
              candidates={state.candidates}
              ranking={state.ranking}
              forecastRun={forecastRun}
              selectedMmsi={selectedMmsi}
              onSelectVessel={setSelectedMmsi}
              layers={layers}
            />
          ) : (
            <div className="map-placeholder">
              <p>Select an event above to load its investigation.</p>
            </div>
          )}
        </div>

        <div className="side-col">
          <div className="side-tabs">
            <button className={activeTab === "evidence" ? "active" : ""} onClick={() => setActiveTab("evidence")}>
              Evidence
            </button>
            <button className={activeTab === "forecast" ? "active" : ""} onClick={() => setActiveTab("forecast")}>
              Forecast
            </button>
            <button className={activeTab === "graph" ? "active" : ""} onClick={() => setActiveTab("graph")}>
              Graph
            </button>
          </div>

          {activeTab === "evidence" && (
            <SidePanel
              temporal={state.temporal}
              candidates={state.candidates}
              ranking={state.ranking}
              evidence={state.evidence}
              evidenceSummary={state.evidenceSummary}
              selectedMmsi={selectedMmsi}
              onSelectVessel={setSelectedMmsi}
            />
          )}
          {activeTab === "forecast" && (
            <ForecastPanel
              forecast={state.forecast}
              impact={state.impact}
              replay={state.replay}
              selectedHorizon={selectedHorizon}
              onSelectHorizon={setSelectedHorizon}
              onRun={(params, options) => void rerunForecast(params, options)}
              busy={state.status.f8 === "loading"}
            />
          )}
          {activeTab === "graph" && <GraphExplorer graph={state.graph} eventId={state.eventId} selectedMmsi={selectedMmsi} />}
        </div>
      </main>
    </div>
  );
}
