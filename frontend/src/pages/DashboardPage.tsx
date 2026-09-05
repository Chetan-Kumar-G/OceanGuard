import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import EventSelector from "../components/EventSelector";
import PipelineStatus from "../components/PipelineStatus";
import MapView from "../components/MapView";
import SidePanel from "../components/SidePanel";
import ForecastPanel from "../components/ForecastPanel";
import GraphExplorer from "../components/GraphExplorer";
import TimelinePlayer from "../components/TimelinePlayer";
import DockableWindow from "../components/DockableWindow";
import { DEFAULT_LAYERS, type LayerVisibility } from "../components/LayerToggles";
import { useEventPipeline } from "../hooks/useEventPipeline";
import { usePdfReportDownload } from "../hooks/usePdfReportDownload";
import { useAuth } from "../auth/AuthContext";

// AOI centre from the bundled synthetic dataset's config.used.yaml (aoi.ref_lat/ref_lon).
const DEFAULT_CENTER: [number, number] = [18.0, 35.0];

type SidePanelId = "evidence" | "forecast" | "graph";
const SIDE_PANELS: { id: SidePanelId; label: string }[] = [
  { id: "evidence", label: "Evidence" },
  { id: "forecast", label: "Forecast" },
  { id: "graph", label: "Graph" },
];

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const { state, load, rerunForecast } = useEventPipeline();
  const [selectedMmsi, setSelectedMmsi] = useState<string | null>(null);
  const [selectedHorizon, setSelectedHorizon] = useState<number | null>(null);
  const [layers, setLayers] = useState<LayerVisibility>(DEFAULT_LAYERS);
  const [stepIndex, setStepIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<SidePanelId>("evidence");
  const [detachedPanels, setDetachedPanels] = useState<Set<SidePanelId>>(new Set());
  const isLoading = Object.values(state.status).some((s) => s === "loading");
  const report = usePdfReportDownload(state.eventId);

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
    setDetachedPanels(new Set());
    void load(eventId);
  }

  function enableForecast() {
    const horizons = [...new Set(state.forecast.map((r) => r.forecast_horizon_hours))].sort((a, b) => a - b);
    if (horizons.length > 0) setSelectedHorizon(horizons[0]);
  }

  function setPanelDetached(id: SidePanelId, next: boolean) {
    setDetachedPanels((prev) => {
      const copy = new Set(prev);
      if (next) copy.add(id);
      else copy.delete(id);
      return copy;
    });
    if (next && activeTab === id) {
      const remaining = SIDE_PANELS.map((p) => p.id).filter((p) => p !== id && !detachedPanels.has(p));
      if (remaining.length > 0) setActiveTab(remaining[0]);
    }
  }

  function panelContent(id: SidePanelId) {
    switch (id) {
      case "evidence":
        return (
          <SidePanel
            eventId={state.eventId}
            temporal={state.temporal}
            candidates={state.candidates}
            ranking={state.ranking}
            evidence={state.evidence}
            evidenceSummary={state.evidenceSummary}
            selectedMmsi={selectedMmsi}
            onSelectVessel={setSelectedMmsi}
          />
        );
      case "forecast":
        return (
          <ForecastPanel
            forecast={state.forecast}
            impact={state.impact}
            replay={state.replay}
            selectedHorizon={selectedHorizon}
            onSelectHorizon={setSelectedHorizon}
            onRun={(params, options) => void rerunForecast(params, options)}
            busy={state.status.f8 === "loading"}
          />
        );
      case "graph":
        return <GraphExplorer graph={state.graph} eventId={state.eventId} selectedMmsi={selectedMmsi} />;
    }
  }

  const attachedTabs = SIDE_PANELS.filter((p) => !detachedPanels.has(p.id));

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-icon">🛢️</span>
          <div>
            <h1>OceanGuard AI</h1>
            <p className="tagline">Investigator dashboard — F1–F8</p>
          </div>
        </div>
        <EventSelector value={state.eventId} onChange={handleSelectEvent} disabled={isLoading} />
        {state.eventId && <PipelineStatus status={state.status} errors={state.errors} />}
        {state.eventId && state.ranking && state.ranking.candidates.length > 0 && (
          <button className="link-button header-pdf-button" onClick={() => void report.download()} disabled={report.downloading}>
            {report.downloading ? "Generating…" : "📄 PDF report"}
          </button>
        )}
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
      {report.error && <p className="flag flag-warn header-pdf-error">{report.error}</p>}

      <p className="disclaimer" title="Candidate vessels are evidence-based associations for investigation, not confirmed legal responsibility. See Technical Boundaries in the project specification.">
        Candidates are evidence-based associations, not confirmed responsibility. <Link to="/appeal">Dispute a flag</Link> — no account needed.
      </p>

      {state.eventId && observedStates.length > 0 && (
        <div className="player-row">
          <DockableWindow title="Investigation playback" floatingSize={{ width: 520, height: 560 }}>
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
          </DockableWindow>
        </div>
      )}

      <main className="layout">
        <div className="map-pane">
          {state.eventId ? (
            <DockableWindow title="Map" className="map-dock" floatingSize={{ width: 640, height: 520 }}>
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
            </DockableWindow>
          ) : (
            <div className="map-placeholder">
              <p>Select an event above to load its investigation.</p>
            </div>
          )}
        </div>

        <div className="side-col">
          {attachedTabs.length > 1 && (
            <div className="side-tabs">
              {attachedTabs.map((p) => (
                <button key={p.id} className={activeTab === p.id ? "active" : ""} onClick={() => setActiveTab(p.id)}>
                  {p.label}
                </button>
              ))}
            </div>
          )}

          {SIDE_PANELS.map((p) => {
            const isDetached = detachedPanels.has(p.id);
            if (!isDetached && p.id !== activeTab) return null; // attached but not the visible tab
            return (
              <DockableWindow
                key={p.id}
                title={p.label}
                floatingSize={{ width: 420, height: 480 }}
                detached={isDetached}
                onToggleDetached={(next) => setPanelDetached(p.id, next)}
              >
                {panelContent(p.id)}
              </DockableWindow>
            );
          })}
        </div>
      </main>
    </div>
  );
}
