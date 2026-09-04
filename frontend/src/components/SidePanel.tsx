import { useState } from "react";
import { ApiError, downloadVesselReportPdf } from "../api/client";
import type { CandidateVessel, EvidenceRelation, EvidenceSummary, RankingResult, TemporalProgressionResult } from "../api/types";

interface Props {
  eventId: string | null;
  temporal: TemporalProgressionResult | null;
  candidates: CandidateVessel[];
  ranking: RankingResult | null;
  evidence: EvidenceRelation[];
  evidenceSummary: EvidenceSummary | null;
  selectedMmsi: string | null;
  onSelectVessel: (mmsi: string | null) => void;
}

function bandClass(band: string) {
  return `band band-${band}`;
}

export default function SidePanel({
  eventId,
  temporal,
  candidates,
  ranking,
  evidence,
  evidenceSummary,
  selectedMmsi,
  onSelectVessel,
}: Props) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function onDownloadReport() {
    if (!eventId) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadVesselReportPdf(eventId);
    } catch (err) {
      setDownloadError(err instanceof ApiError ? `Could not generate the report (HTTP ${err.status}).` : "Could not reach the server.");
    } finally {
      setDownloading(false);
    }
  }

  const latestObserved = temporal?.states.filter((s) => s.state_type === "OBSERVED").at(-1);
  const candidateByMmsi = new Map(candidates.map((c) => [c.mmsi, c]));
  const evidenceForSelected = selectedMmsi
    ? evidence.filter((e) => e.source_b_id.endsWith(`-${selectedMmsi}`) || e.source_a_id.endsWith(`-${selectedMmsi}`))
    : [];

  return (
    <aside className="side-panel">
      <section className="panel-card">
        <h3>Spill summary</h3>
        {temporal ? (
          <dl className="kv">
            <dt>Observations</dt>
            <dd>
              {temporal.observed_count} observed · {temporal.interpolated_count} interpolated ·{" "}
              {temporal.predicted_count} predicted
            </dd>
            <dt>Latest area</dt>
            <dd>{latestObserved ? `${latestObserved.area_km2.toFixed(1)} km²` : "–"}</dd>
            <dt>Detection confidence</dt>
            <dd>{latestObserved?.f1_confidence != null ? `${(latestObserved.f1_confidence * 100).toFixed(0)}%` : "–"}</dd>
            <dt>Data adequacy</dt>
            <dd>
              {temporal.insufficient_temporal_data ? (
                <span className="flag flag-warn">LIMITED — fewer than 2 observed states</span>
              ) : (
                <span className="flag flag-ok">nominal</span>
              )}
            </dd>
          </dl>
        ) : (
          <p className="muted">Select an event to load its spill history.</p>
        )}
      </section>

      <section className="panel-card">
        <div className="panel-card-header">
          <h3>Candidate vessels (F6 ranking)</h3>
          {ranking && ranking.candidates.length > 0 && (
            <button className="link-button" onClick={onDownloadReport} disabled={downloading}>
              {downloading ? "Generating…" : "📄 PDF report"}
            </button>
          )}
        </div>
        {downloadError && <p className="flag flag-warn small">{downloadError}</p>}
        {!ranking && <p className="muted">Not yet computed.</p>}
        {ranking?.event_insufficient_evidence && (
          <p className="flag flag-warn">
            Insufficient evidence — the system correctly declines to name a leading candidate for this event.
          </p>
        )}
        {ranking && ranking.candidates.length > 0 && (
          <table className="ranking-table">
            <thead>
              <tr>
                <th>#</th>
                <th>MMSI</th>
                <th>Score</th>
                <th>Confidence</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {ranking.candidates.map((c) => (
                <tr
                  key={c.candidate_mmsi}
                  className={c.candidate_mmsi === selectedMmsi ? "selected" : ""}
                  onClick={() => onSelectVessel(c.candidate_mmsi === selectedMmsi ? null : c.candidate_mmsi)}
                >
                  <td>{c.rank}</td>
                  <td>{c.candidate_mmsi}</td>
                  <td>{c.final_score.toFixed(2)}</td>
                  <td>
                    <span className={bandClass(c.confidence_band)}>{c.confidence_band}</span>
                  </td>
                  <td>
                    {c.support_count > 0 && <span className="tag tag-support">{c.support_count} support</span>}
                    {c.contradiction_count > 0 && (
                      <span className="tag tag-contradict">{c.contradiction_count} contradict</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {ranking && ranking.candidates.length === 0 && !ranking.event_insufficient_evidence && (
          <p className="muted">No candidate vessels compatible with the source window.</p>
        )}
      </section>

      {selectedMmsi && (
        <section className="panel-card">
          <h3>Vessel {selectedMmsi}</h3>
          {(() => {
            const c = candidateByMmsi.get(selectedMmsi);
            const r = ranking?.candidates.find((x) => x.candidate_mmsi === selectedMmsi);
            return (
              <>
                <dl className="kv">
                  <dt>Type</dt>
                  <dd>{c?.vessel_type ?? "unknown"}</dd>
                  <dt>Distance to source</dt>
                  <dd>{c ? `${c.distance_to_source_effective_km.toFixed(1)} km` : "–"}</dd>
                  <dt>Temporal compatibility</dt>
                  <dd>{c ? `${(c.temporal_compatibility * 100).toFixed(0)}%` : "–"}</dd>
                  <dt>AIS dark gap over source</dt>
                  <dd>{c?.dark_gap_over_source ? "yes ⚠" : "no"}</dd>
                </dl>
                {r && <p className="explanation">{r.explanation}</p>}
                {evidenceForSelected.length > 0 && (
                  <ul className="evidence-list">
                    {evidenceForSelected.map((e) => (
                      <li key={e.evidence_id} className={`evidence-item evidence-${e.relation.toLowerCase()}`}>
                        <strong>{e.relation}</strong> · {e.source_a_type} ↔ {e.source_b_type}
                        <div className="muted small">{e.reason}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            );
          })()}
        </section>
      )}

      <section className="panel-card">
        <h3>Cross-source evidence (F5)</h3>
        {evidenceSummary ? (
          <div className="evidence-summary">
            <span className="tag tag-support">{evidenceSummary.SUPPORTS} supports</span>
            <span className="tag tag-contradict">{evidenceSummary.CONTRADICTS} contradicts</span>
            <span className="tag tag-unknown">{evidenceSummary.UNKNOWN} unknown</span>
          </div>
        ) : (
          <p className="muted">Not yet computed.</p>
        )}
      </section>
    </aside>
  );
}
