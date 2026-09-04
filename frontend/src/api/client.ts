import type {
  AppealOut,
  AppealSubject,
  AppealStatus,
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
  TokenResponse,
  UserOut,
} from "./types";

let _authToken: string | null = null;
export function setAuthToken(token: string | null) {
  _authToken = token;
}

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
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (_authToken) headers.Authorization = `Bearer ${_authToken}`;
  const res = await fetch(`${BASE}${path}`, { headers: { ...headers, ...(init?.headers as Record<string, string>) }, ...init });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, path, body);
  return body as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const patch = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined });
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

// ---------------------------------------------------------------- auth
export const register = (email: string, password: string, displayName: string) =>
  post<TokenResponse>(`/auth/register`, { email, password, display_name: displayName });

export async function login(email: string, password: string): Promise<TokenResponse> {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, "/auth/login", body);
  return body as TokenResponse;
}

export const getMe = () => get<UserOut>(`/auth/me`);

export const requestPasswordReset = (email: string) =>
  post<{ message: string; dev_reset_token: string | null }>(`/auth/password-reset/request`, { email });

export const confirmPasswordReset = (token: string, newPassword: string) =>
  post<UserOut>(`/auth/password-reset/confirm`, { token, new_password: newPassword });

// ---------------------------------------------------------------- appeals
export interface AppealSubmissionBody {
  event_id: string;
  subject: AppealSubject;
  mmsi?: string;
  contact_name: string;
  contact_email: string;
  statement: string;
}

export const submitAppeal = (body: AppealSubmissionBody) => post<AppealOut>(`/appeals`, body);

export const listAppeals = (filters: { event_id?: string; status?: AppealStatus } = {}) => {
  const qs = new URLSearchParams(filters as Record<string, string>).toString();
  return get<AppealOut[]>(`/appeals${qs ? `?${qs}` : ""}`);
};

export const reviewAppeal = (appealId: string, status: AppealStatus, notes?: string) =>
  patch<AppealOut>(`/appeals/${appealId}/review`, { status, notes });

// ---------------------------------------------------------------- media
export const quicklookUrl = (sceneId: string) => `${BASE}/media/quicklook/${sceneId}.png`;
