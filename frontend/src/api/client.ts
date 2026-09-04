import type {
  ApiResponse,
  CandidateVessel,
  EvidenceRelation,
  EvidenceSummary,
  FlatEnvelope,
  ForecastEvaluation,
  ForecastRun,
  GraphResponse,
  ImpactAssessment,
  RankingResult,
  SourceHypothesisWindow,
  TemporalProgressionResult,
} from "./types";

/**
 * Every request is relative (``/f5/...``) so Vite's dev proxy (see
 * vite.config.ts) forwards it to the backend - the browser never needs to know
 * the API's host/port, and CORS is a non-issue. In production, point
 * VITE_API_BASE_URL at the deployed backend origin.
 */
const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

class ApiError extends Error {
  constructor(
    public status: number,
    public url: string,
    public body: unknown,
  ) {
    super(`${status} ${url}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, path, body);
  return body as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const get = <T>(path: string) => request<T>(path);

export { ApiError };

// ---------------------------------------------------------------- F2
export const reconstructTemporal = (eventId: string) =>
  post<ApiResponse<TemporalProgressionResult>>(`/f2/reconstruct/${eventId}`);

// ---------------------------------------------------------------- F3
export const runHindcast = (eventId: string) =>
  post<ApiResponse<SourceHypothesisWindow[]>>(`/api/v1/f3/hindcast/${eventId}`);

// ---------------------------------------------------------------- F4
export const reconstructAis = (eventId: string) =>
  post<ApiResponse<CandidateVessel[]>>(`/api/v1/f4/reconstruct-ais/${eventId}`);

// ---------------------------------------------------------------- F5
export const evaluateConsistency = (eventId: string) =>
  post<ApiResponse<EvidenceRelation[]> & { meta: { summary?: EvidenceSummary } }>(
    `/f5/evaluate-consistency/${eventId}`,
  );

// ---------------------------------------------------------------- F6
export const rankCandidates = (eventId: string) =>
  post<FlatEnvelope<RankingResult>>(`/f6/rank/${eventId}`);

// ---------------------------------------------------------------- F7
export const getGraph = (eventId: string) =>
  get<FlatEnvelope<GraphResponse>>(`/events/${eventId}/graph`);

// ---------------------------------------------------------------- F8
export interface ForecastRequestBody {
  horizons_h?: number[];
  n_ensemble?: number;
  n_particles?: number;
  base_seed?: number;
}

export const runForecast = (eventId: string, body: ForecastRequestBody = {}) =>
  post<ApiResponse<ForecastRun[]>>(`/api/v1/f8/forecast/${eventId}`, body);

export const getImpact = (eventId: string) =>
  get<ApiResponse<ImpactAssessment[]>>(`/api/v1/f8/forecast/${eventId}/impact`);

export const runReplay = (eventId: string, body: ForecastRequestBody = {}) =>
  post<ApiResponse<ForecastEvaluation[]>>(`/api/v1/f8/replay/${eventId}`, body);

// ---------------------------------------------------------------- health
export const getHealth = () => get<{ status: string; features: string[] }>(`/health`);
