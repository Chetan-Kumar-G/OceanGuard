import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAppeals, reviewAppeal } from "../api/client";
import type { AppealOut, AppealStatus } from "../api/types";
import { useAuth } from "../auth/AuthContext";

const STATUS_OPTIONS: AppealStatus[] = ["open", "reviewing", "upheld", "dismissed"];

export default function AppealsReviewPage() {
  const { user } = useAuth();
  const [appeals, setAppeals] = useState<AppealOut[]>([]);
  const [statusFilter, setStatusFilter] = useState<AppealStatus | "">("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const res = await listAppeals(statusFilter ? { status: statusFilter } : {});
      setAppeals(res);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function decide(appealId: string, status: AppealStatus) {
    await reviewAppeal(appealId, status, notes[appealId]);
    setNotes((n) => ({ ...n, [appealId]: "" }));
    await refresh();
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-icon">🛢️</span>
          <div>
            <h1>OceanGuard AI</h1>
            <p className="tagline">Appeals review queue</p>
          </div>
        </div>
        <nav className="top-nav">
          <Link to="/">← Dashboard</Link>
        </nav>
        <span className="muted small" style={{ marginLeft: "auto" }}>
          {user?.display_name} · {user?.role}
        </span>
      </header>

      <main className="appeals-review">
        <div className="horizon-buttons" style={{ margin: "12px 20px" }}>
          <button className={statusFilter === "" ? "active" : ""} onClick={() => setStatusFilter("")}>
            all
          </button>
          {STATUS_OPTIONS.map((s) => (
            <button key={s} className={statusFilter === s ? "active" : ""} onClick={() => setStatusFilter(s)}>
              {s}
            </button>
          ))}
        </div>

        {loading && <p className="muted" style={{ margin: "0 20px" }}>Loading…</p>}
        {!loading && appeals.length === 0 && <p className="muted" style={{ margin: "0 20px" }}>No appeals.</p>}

        <div className="appeals-list">
          {appeals.map((a) => (
            <div key={a.id} className="panel-card appeal-row">
              <div className="appeal-row-header" onClick={() => setExpanded(expanded === a.id ? null : a.id)}>
                <span className={`flag flag-status-${a.status}`}>{a.status}</span>
                <strong>{a.event_id}</strong>
                <span className="muted small">{a.subject.replace("_", " ")}</span>
                {a.mmsi && <span className="muted small">MMSI {a.mmsi}</span>}
                <span className="muted small" style={{ marginLeft: "auto" }}>
                  {a.contact_name} · {new Date(a.submitted_at).toLocaleString()}
                </span>
              </div>

              {expanded === a.id && (
                <div className="appeal-row-body">
                  <p>{a.statement}</p>
                  <p className="muted small">Contact: {a.contact_email}</p>

                  <h4>History</h4>
                  <ul className="evidence-list">
                    {a.history.map((h, i) => (
                      <li key={i} className={`evidence-item evidence-${h.status === "upheld" ? "supports" : h.status === "dismissed" ? "contradicts" : "unknown"}`}>
                        <strong>{h.status}</strong> — {h.notes ?? "no notes"}
                        <div className="muted small">
                          {h.reviewer_display_name ?? "submitter"} · {new Date(h.timestamp).toLocaleString()}
                        </div>
                      </li>
                    ))}
                  </ul>

                  <div className="appeal-review-form">
                    <textarea
                      placeholder="Review notes…"
                      value={notes[a.id] ?? ""}
                      onChange={(e) => setNotes((n) => ({ ...n, [a.id]: e.target.value }))}
                      rows={2}
                    />
                    <div className="horizon-buttons">
                      {STATUS_OPTIONS.filter((s) => s !== "open").map((s) => (
                        <button key={s} onClick={() => void decide(a.id, s)}>
                          Mark {s}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
