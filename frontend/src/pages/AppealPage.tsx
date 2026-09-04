import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, submitAppeal, type AppealSubmissionBody } from "../api/client";
import type { AppealOut, AppealSubject } from "../api/types";

const EVENTS = Array.from({ length: 12 }, (_, i) => `EVT${String(i + 1).padStart(4, "0")}`);

const SUBJECT_LABEL: Record<AppealSubject, string> = {
  detection: "The satellite spill detection itself",
  source_hypothesis: "The estimated source region",
  candidate_vessel: "A vessel named as a candidate",
  other: "Something else",
};

export default function AppealPage() {
  const [form, setForm] = useState<AppealSubmissionBody>({
    event_id: "",
    subject: "candidate_vessel",
    mmsi: "",
    contact_name: "",
    contact_email: "",
    statement: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AppealOut | null>(null);

  function set<K extends keyof AppealSubmissionBody>(key: K, value: AppealSubmissionBody[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body = { ...form, mmsi: form.mmsi || undefined };
      const res = await submitAppeal(body);
      setResult(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) setError("Please check the form — an event ID, valid email, and a longer statement (10+ characters) are required.");
      else setError("Could not submit the appeal. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>Dispute received</h1>
          <p>
            Reference ID: <code>{result.id}</code>
          </p>
          <p className="muted">
            An investigator will review this and may contact you at <strong>{result.contact_email}</strong>. Submitting a
            dispute does not itself change any status — it starts a human review.
          </p>
          <Link to="/">Back to OilTrace AI</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <form className="auth-card appeal-card" onSubmit={onSubmit}>
        <h1>Dispute a false positive</h1>
        <p className="muted">
          No account needed. Use this if you believe OilTrace AI incorrectly detected a spill, estimated a source
          region, or named a vessel as a candidate. Candidate vessels are evidence-based associations for
          investigation, not confirmed legal responsibility — this form starts a human review.
        </p>

        <label>
          Event ID
          <select value={form.event_id} onChange={(e) => set("event_id", e.target.value)} required>
            <option value="" disabled>
              Select the event…
            </option>
            {EVENTS.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </label>

        <label>
          What are you disputing?
          <select value={form.subject} onChange={(e) => set("subject", e.target.value as AppealSubject)}>
            {(Object.keys(SUBJECT_LABEL) as AppealSubject[]).map((s) => (
              <option key={s} value={s}>
                {SUBJECT_LABEL[s]}
              </option>
            ))}
          </select>
        </label>

        {form.subject === "candidate_vessel" && (
          <label>
            Vessel MMSI (if known)
            <input value={form.mmsi} onChange={(e) => set("mmsi", e.target.value)} placeholder="e.g. 480469227" />
          </label>
        )}

        <label>
          Your name
          <input value={form.contact_name} onChange={(e) => set("contact_name", e.target.value)} required />
        </label>
        <label>
          Your email
          <input type="email" value={form.contact_email} onChange={(e) => set("contact_email", e.target.value)} required />
        </label>
        <label>
          Statement
          <textarea
            value={form.statement}
            onChange={(e) => set("statement", e.target.value)}
            required
            minLength={10}
            rows={5}
            placeholder="Explain why this is a false positive — dates, times, supporting evidence, etc."
          />
        </label>

        {error && <p className="flag flag-warn">{error}</p>}

        <button type="submit" disabled={busy}>
          {busy ? "Submitting…" : "Submit dispute"}
        </button>
        <p className="muted small">
          <Link to="/login">Investigator sign-in</Link>
        </p>
      </form>
    </div>
  );
}
