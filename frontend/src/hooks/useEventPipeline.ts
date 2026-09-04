import { useCallback, useState } from "react";
import {
  ApiError,
  evaluateConsistency,
  getGraph,
  getImpact,
  rankCandidates,
  reconstructAis,
  reconstructTemporal,
  runForecast,
  runHindcast,
  runReplay,
} from "../api/client";
import type {
  CandidateVessel,
  EvidenceRelation,
  EvidenceSummary,
  ForecastEvaluation,
  ForecastRun,
  GraphResponse,
  ImpactAssessment,
  RankingResult,
  SourceHypothesisWindow,
  TemporalProgressionResult,
} from "../api/types";

export type StageKey = "f2" | "f3" | "f4" | "f5" | "f6" | "f7" | "f8";
export type StageStatus = "idle" | "loading" | "done" | "error";

export interface PipelineState {
  eventId: string | null;
  status: Record<StageKey, StageStatus>;
  errors: Partial<Record<StageKey, string>>;
  temporal: TemporalProgressionResult | null;
  hypotheses: SourceHypothesisWindow[];
  candidates: CandidateVessel[];
  evidence: EvidenceRelation[];
  evidenceSummary: EvidenceSummary | null;
  ranking: RankingResult | null;
  graph: GraphResponse | null;
  forecast: ForecastRun[];
  impact: ImpactAssessment[];
  replay: ForecastEvaluation[];
}

const IDLE_STATUS: Record<StageKey, StageStatus> = {
  f2: "idle",
  f3: "idle",
  f4: "idle",
  f5: "idle",
  f6: "idle",
  f7: "idle",
  f8: "idle",
};

const EMPTY: PipelineState = {
  eventId: null,
  status: IDLE_STATUS,
  errors: {},
  temporal: null,
  hypotheses: [],
  candidates: [],
  evidence: [],
  evidenceSummary: null,
  ranking: null,
  graph: null,
  forecast: [],
  impact: [],
  replay: [],
};

function messageFor(err: unknown): string {
  if (err instanceof ApiError) {
    const detail = (err.body as { detail?: unknown })?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message?: unknown }).message);
    }
    return `HTTP ${err.status}`;
  }
  return err instanceof Error ? err.message : String(err);
}

/**
 * Drives the full F2 -> F8 investigation pipeline for one event, mirroring the
 * demonstration scenario in Features.md section 15. Each stage is independently
 * tracked so the dashboard can show partial progress and per-stage failures
 * without one broken feature blanking the whole page.
 */
export function useEventPipeline() {
  const [state, setState] = useState<PipelineState>(EMPTY);

  const setStage = useCallback((key: StageKey, status: StageStatus, error?: string) => {
    setState((s) => ({
      ...s,
      status: { ...s.status, [key]: status },
      errors: error ? { ...s.errors, [key]: error } : s.errors,
    }));
  }, []);

  const load = useCallback(async (eventId: string) => {
    setState({ ...EMPTY, eventId, status: { ...IDLE_STATUS } });

    // F2: temporal reconstruction - everything downstream keys off this.
    setStage("f2", "loading");
    let temporal: TemporalProgressionResult | null = null;
    try {
      const res = await reconstructTemporal(eventId);
      temporal = res.data;
      setState((s) => ({ ...s, temporal }));
      setStage("f2", "done");
    } catch (err) {
      setStage("f2", "error", messageFor(err));
      return;
    }

    // F3, F5, F7 all depend on F3's hypothesis; run F3 first, then F4/F5/F6/F7/F8
    // in a sensible order. Each is independently caught so one failure doesn't
    // stop the rest.
    setStage("f3", "loading");
    try {
      const res = await runHindcast(eventId);
      setState((s) => ({ ...s, hypotheses: res.data }));
      setStage("f3", "done");
    } catch (err) {
      setStage("f3", "error", messageFor(err));
    }

    setStage("f4", "loading");
    try {
      const res = await reconstructAis(eventId);
      setState((s) => ({ ...s, candidates: res.data }));
      setStage("f4", "done");
    } catch (err) {
      setStage("f4", "error", messageFor(err));
    }

    setStage("f5", "loading");
    try {
      const res = await evaluateConsistency(eventId);
      setState((s) => ({
        ...s,
        evidence: res.data,
        evidenceSummary: (res.meta.summary as EvidenceSummary) ?? null,
      }));
      setStage("f5", "done");
    } catch (err) {
      setStage("f5", "error", messageFor(err));
    }

    setStage("f6", "loading");
    try {
      const res = await rankCandidates(eventId);
      setState((s) => ({ ...s, ranking: res.data }));
      setStage("f6", "done");
    } catch (err) {
      setStage("f6", "error", messageFor(err));
    }

    setStage("f7", "loading");
    try {
      const res = await getGraph(eventId);
      setState((s) => ({ ...s, graph: res.data }));
      setStage("f7", "done");
    } catch (err) {
      setStage("f7", "error", messageFor(err));
    }

    setStage("f8", "loading");
    try {
      const [forecastRes, impactRes, replayRes] = await Promise.all([
        runForecast(eventId, { horizons_h: [12, 24, 48, 72], n_ensemble: 16 }),
        getImpact(eventId).catch(() => ({ data: [] as ImpactAssessment[] })),
        runReplay(eventId, { n_ensemble: 16 }).catch(() => ({ data: [] as ForecastEvaluation[] })),
      ]);
      setState((s) => ({
        ...s,
        forecast: forecastRes.data,
        impact: impactRes.data,
        replay: replayRes.data,
      }));
      setStage("f8", "done");
    } catch (err) {
      setStage("f8", "error", messageFor(err));
    }
  }, [setStage]);

  return { state, load };
}
