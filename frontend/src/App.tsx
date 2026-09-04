import { useMemo, useState } from "react";
import EventSelector from "./components/EventSelector";
import PipelineStatus from "./components/PipelineStatus";
import MapView from "./components/MapView";
import SidePanel from "./components/SidePanel";
import Timeline from "./components/Timeline";
import ForecastPanel from "./components/ForecastPanel";
import GraphExplorer from "./components/GraphExplorer";
import { useEventPipeline } from "./hooks/useEventPipeline";

// AOI centre from the bundled synthetic dataset's config.used.yaml (aoi.ref_lat/ref_lon).
const DEFAULT_CENTER: [number, number] = [18.0, 35.0];

export default function App() {
  const { state, load } = useEventPipeline();
  const [selectedMmsi, setSelectedMmsi] = useState<string | null>(null);
  const [selectedHorizon, setSelectedHorizon] = useState<number | null>(null);
  const isLoading = Object.values(state.status).some((s) => s === "loading");

  const center = useMemo<[number, number]>(() => {
    const latest = state.temporal?.states.filter((s) => s.state_type === "OBSERVED").at(-1);
    return latest ? [latest.centroid_lon, latest.centroid_lat] : DEFAULT_CENTER;
  }, [state.temporal]);

  const forecastRun = useMemo(
    () => state.forecast.find((r) => r.forecast_horizon_hours === selectedHorizon) ?? null,
    [state.forecast, selectedHorizon],
  );

  function handleSelectEvent(eventId: string) {
    setSelectedMmsi(null);
    setSelectedHorizon(null);
    void load(eventId);
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
      </header>

      <p className="disclaimer">
        Candidate vessels are evidence-based associations for investigation, not confirmed legal responsibility. See{" "}
        <em>Technical Boundaries</em> in the project specification.
      </p>

      <main className="layout">
        <div className="map-pane">
          {state.eventId ? (
            <MapView
              center={center}
              states={state.temporal?.states ?? []}
              hypotheses={state.hypotheses}
              candidates={state.candidates}
              ranking={state.ranking}
              forecastRun={forecastRun}
              selectedMmsi={selectedMmsi}
              onSelectVessel={setSelectedMmsi}
            />
          ) : (
            <div className="map-placeholder">
              <p>Select an event above to load its investigation.</p>
            </div>
          )}
        </div>

        <div className="side-col">
          <Timeline states={state.temporal?.states ?? []} />
          <SidePanel
            temporal={state.temporal}
            candidates={state.candidates}
            ranking={state.ranking}
            evidence={state.evidence}
            evidenceSummary={state.evidenceSummary}
            selectedMmsi={selectedMmsi}
            onSelectVessel={setSelectedMmsi}
          />
          <ForecastPanel
            forecast={state.forecast}
            impact={state.impact}
            replay={state.replay}
            selectedHorizon={selectedHorizon}
            onSelectHorizon={setSelectedHorizon}
          />
          <GraphExplorer graph={state.graph} eventId={state.eventId} selectedMmsi={selectedMmsi} />
        </div>
      </main>
    </div>
  );
}
