/**
 * TypeScript mirrors of the backend's pydantic contracts (F1-F8).
 * Keep these in sync with shared/schemas/*.py and backend/shared/schemas/*.py
 * when the API changes shape.
 */

export interface ApiMeta {
  run_id: string;
  generated_at: string;
  [key: string]: unknown;
}

export interface ApiResponse<T> {
  data: T;
  meta: ApiMeta;
}

/** F6 / F7 use a `{success, data, error, meta}` envelope instead. */
export interface FlatEnvelope<T> {
  success: boolean;
  data: T;
  error?: string | null;
  meta?: Record<string, unknown>;
}

export interface GeoJSONPolygon {
  type: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
}

// ---------------------------------------------------------------- F2
export type StateType = "OBSERVED" | "INTERPOLATED" | "PREDICTED";

export interface TemporalSpillState {
  event_id: string;
  observation_id: string;
  scene_id?: string;
  timestamp: string;
  sim_hours?: number;
  state_type: StateType;
  polygon_geojson: GeoJSONPolygon;
  area_km2: number;
  perimeter_km: number;
  centroid_lat: number;
  centroid_lon: number;
  is_observed: boolean;
  f1_confidence?: number;
  data_quality?: string;
  area_change_pct?: number | null;
  centroid_displacement_km?: number | null;
}

export interface TemporalProgressionResult {
  event_id: string;
  total_states: number;
  observed_count: number;
  interpolated_count: number;
  predicted_count: number;
  states: TemporalSpillState[];
  insufficient_temporal_data: boolean;
}

// ---------------------------------------------------------------- F3
export interface SourceHypothesisWindow {
  source_hypothesis_id: string;
  event_id: string;
  source_location: { lat: number; lon: number };
  origin_time_start: string;
  origin_time_end: string;
  uncertainty_radius_km: number;
  source_probability: number;
  ensemble_id?: number;
  data_quality_flag?: string;
}

// ---------------------------------------------------------------- F4
export interface CandidateVessel {
  track_id: string;
  event_id: string;
  mmsi: string;
  source_hypothesis_id: string;
  distance_to_source_effective_km: number;
  temporal_compatibility: number;
  track_overlap: number;
  track_completeness: number;
  dark_gap_over_source: boolean;
  speed_compatibility: number;
  course_compatibility: number;
  ais_gap_ratio_origin_window: number;
  vessel_type?: string | null;
  closest_approach_timestamp?: string | null;
  closest_approach_is_interpolated: boolean;
  closest_approach_lat?: number | null;
  closest_approach_lon?: number | null;
}

// ---------------------------------------------------------------- F5
export type EvidenceRelationType = "SUPPORTS" | "CONTRADICTS" | "UNKNOWN";

export interface EvidenceRelation {
  evidence_id: string;
  event_id: string;
  source_a_id: string;
  source_a_type: string;
  source_b_id: string;
  source_b_type: string;
  spatial_residual_km: number;
  temporal_residual_h: number;
  relation: EvidenceRelationType;
  reason: string;
}

export interface EvidenceSummary {
  SUPPORTS: number;
  CONTRADICTS: number;
  UNKNOWN: number;
  total: number;
}

// ---------------------------------------------------------------- F6
export type ConfidenceBand = "high" | "medium" | "low";

export interface HypothesisScore {
  hypothesis_id: string;
  event_id: string;
  candidate_mmsi: string;
  rank: number;
  final_score: number;
  confidence_band: ConfidenceBand;
  event_insufficient_evidence: boolean;
  explanation: string;
  source_probability: number;
  spatial_compatibility: number;
  temporal_compatibility: number;
  drift_compatibility: number;
  ais_completeness: number;
  behavioural_score: number;
  sensor_confidence: number;
  support_count: number;
  contradiction_count: number;
  unknown_count: number;
  n_evidence_items: number;
  margin_to_next: number;
  is_true_source?: boolean | null;
  vessel_type?: string | null;
}

export interface RankingResult {
  event_id: string;
  candidates: HypothesisScore[];
  event_insufficient_evidence: boolean;
  n_candidates: number;
}

// ---------------------------------------------------------------- F7
export type NodeType =
  | "SPILL_OBSERVATION"
  | "SOURCE_HYPOTHESIS"
  | "ENVIRONMENTAL_STATE"
  | "VESSEL"
  | "EVIDENCE"
  | "FORECAST";

export type EdgeType = "DERIVED-FROM" | "SUPPORTS" | "CONTRADICTS" | "TEMPORALLY-COMPATIBLE";

export interface GraphNode {
  node_id: string;
  event_id: string;
  node_type: NodeType;
  timestamp?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  confidence?: number | null;
  uncertainty?: number | null;
  provenance?: string | null;
}

export interface GraphEdge {
  edge_id: string;
  event_id: string;
  source_node_id: string;
  target_node_id: string;
  relation_type: EdgeType;
  confidence?: number | null;
  provenance?: string | null;
}

export interface GraphResponse {
  event_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  edge_count: number;
  is_partial: boolean;
}

// ---------------------------------------------------------------- F8
export interface LonLat {
  lat: number;
  lon: number;
}

export interface ForecastRun {
  event_id: string;
  forecast_id: string;
  initial_observation_id: string;
  initial_timestamp: string;
  initial_centroid: LonLat;
  initial_area_km2: number;
  forecast_horizon_hours: number;
  valid_timestamp: string;
  n_ensemble: number;
  predicted_centroid: LonLat;
  predicted_polygon_geojson: GeoJSONPolygon;
  predicted_area_km2: number;
  forecast_envelope_geojson: GeoJSONPolygon;
  forecast_envelope_area_km2: number;
  ensemble_spread_km: number;
  forecast_confidence: number;
  coastline_distance_km: number;
  nearest_sensitive_zone?: string | null;
  sensitive_zone_distance_km?: number | null;
  beaching_risk: boolean;
  data_quality_flag: string;
}

export interface ImpactAssessment {
  event_id: string;
  forecast_id: string;
  forecast_horizon_hours: number;
  valid_timestamp: string;
  predicted_centroid: LonLat;
  coastline_distance_km: number;
  beaching_risk: boolean;
  nearest_sensitive_zone?: string | null;
  sensitive_zone_distance_km?: number | null;
  impact_area_candidates: string[];
}

// ---------------------------------------------------------------- Auth
export type Role = "investigator" | "admin";

export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserOut;
}

// ---------------------------------------------------------------- Appeals
export type AppealSubject = "detection" | "source_hypothesis" | "candidate_vessel" | "other";
export type AppealStatus = "open" | "reviewing" | "upheld" | "dismissed";

export interface AppealHistoryEntry {
  status: AppealStatus;
  notes?: string | null;
  reviewer_display_name?: string | null;
  timestamp: string;
}

export interface AppealOut {
  id: string;
  event_id: string;
  subject: AppealSubject;
  mmsi?: string | null;
  contact_name: string;
  contact_email: string;
  statement: string;
  status: AppealStatus;
  submitted_at: string;
  history: AppealHistoryEntry[];
}

export interface ForecastEvaluation {
  event_id: string;
  forecast_id: string;
  forecast_horizon_hours: number;
  matched_observation_id: string;
  match_offset_hours: number;
  trajectory_error_km: number;
  observed_region_coverage_iou: number;
  observed_in_forecast_envelope_frac: number;
  observed_centroid_in_envelope: boolean;
  calibration_ratio: number;
  well_calibrated: boolean;
}
