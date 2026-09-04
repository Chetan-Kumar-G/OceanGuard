# Feature F3: Environmental Drift & Backward Hindcasting — Implementation & Integration Notes

## 1. Feature Mission & Scope
Feature F3 estimates the probable origin region and time-window of a detected marine oil slick by integrating Lagrangian particles backward in time through environmental forcing fields.

- **Primary Mission:** Answers *"Where and when could the oil have originated?"* with rigorous uncertainty quantification.
- **Out of Scope:** Does **not** determine vessel guilt, vessel attribution, or candidate scoring. F3 outputs are strictly candidate source hypotheses.

---

## 2. Architecture & Components

```
F2 (Temporal States)
       │ [TemporalSpillState[]]
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    F3HindcastSupervisor                     │
│                                                             │
│  1. StateValidationAgent   -> Filter is_observed==True only │
│  2. ForcingAgent           -> Acquire & snapshot forcing    │
│  3. HindcastPhysicsAgent   -> Multi-ensemble backward drift │
│  4. SourceInferenceAgent   -> RMS uncertainty & window      │
│  5. ProvenanceContractAgent-> Validate & seal SH_* IDs      │
└──────────────────────────────┬──────────────────────────────┘
                               │
       ┌───────────────────────┴───────────────────────┐
       ▼                                               ▼
source_hypotheses (DB/Repo)                 environmental_states (DB/Repo)
       │
       │ [SourceHypothesisWindow]
       ▼
F4 (Historical AIS Filtering)
```

### Module Breakdown
- `shared/schemas/envelope.py`: Standard API response and error envelopes (`ApiResponse`, `ApiMeta`, `ApiError`).
- `shared/schemas/f2_contract.py`: F2 input contract (`TemporalSpillState`).
- `shared/schemas/f3_contract.py`: F3 public interface (`SourceHypothesisWindow`) and provenance snapshot (`EnvironmentalStateSnapshot`).
- `shared/schemas/f4_contract.py`: Downstream candidate vessel contract reference (`CandidateVessel`).
- `shared/config/settings.py`: Application settings with transparent dataset discovery (`config.yaml` with automatic fallback to `config.used.yaml`).
- `shared/mocks/load_mock.py`: Shared mock loading infrastructure for `load_mock("f2", event_id)` and `load_mock("f3", event_id)`.
- `shared/physics/lagrangian.py`: Reusable, 2nd-order time-reversible Lagrangian advection-diffusion physics engine and local tangent-plane metric frame.
- `backend/f3_hindcast/adapter.py`: Ingestion, chronological sorting, and observed-only filtering of temporal states.
- `backend/f3_hindcast/forcing.py`: Environmental forcing providers (`SyntheticForcingProvider`, `MissingForcingFallbackProvider`).
- `backend/f3_hindcast/ensemble.py`: Lagrangian ensemble runner with parameter perturbations.
- `backend/f3_hindcast/inference.py`: Centroid calculation, RMS uncertainty radius, and origin-time window inference.
- `backend/f3_hindcast/repository.py`: In-memory and file-backed repository for hypotheses, forcing snapshots, and particle trajectories.
- `backend/f3_hindcast/agents.py`: Specialist deterministic agents coordinating each stage.
- `backend/f3_hindcast/supervisor.py`: Top-level pipeline orchestrator.
- `backend/f3_hindcast/router.py`: FastAPI endpoints.

---

## 3. Frozen Public Contract: `SourceHypothesisWindow`

F4 directly consumes this contract to construct its historical AIS spatio-temporal filter:

| Field | Type | Description |
|---|---|---|
| `source_hypothesis_id` | `str` | `SH_<event_id>_<ensemble_id:02d>` or `SH_<event_id>_HBEST` |
| `event_id` | `str` | Root spill case identifier (e.g. `EVT0001`) |
| `source_location` | `{"lat": float, "lon": float}` | Estimated release centroid in WGS84 EPSG:4326 |
| `origin_time_start` | `str` | Search window start in UTC ISO-8601 |
| `origin_time_end` | `str` | Search window end in UTC ISO-8601 |
| `uncertainty_radius_km` | `float` | RMS uncertainty radius (km). Mandatory. |
| `source_probability` | `float` | Probability weight in $[0.0, 1.0]$ (1.0 for HBEST) |

---

## 4. API Endpoints

All endpoints wrap payloads in the shared `ApiResponse` envelope:

1. `POST /api/v1/f3/hindcast/{event_id}`
   - Triggers full backward hindcast for `event_id`.
   - Optional request body: `{"states": [...], "base_seed": 42}`.
   - Returns: `ApiResponse[List[SourceHypothesisWindow]]`.
2. `GET /api/v1/events/{event_id}/source-hypotheses`
   - Returns all candidate hypotheses for `event_id`.
3. `GET /api/v1/f3/hindcast/{event_id}/best`
   - Returns specifically the pooled best estimate (`SH_<event_id>_HBEST`) for direct F4 integration.

---

## 5. Verification & Test Suite

The test suite contains 31 automated tests under `tests/unit/f3/`:
- `test_contracts.py`: Validates Pydantic schemas, envelope models, and mock loader.
- `test_advection.py`: Analytic constant-current verification ($x = x_0 + v \cdot t$).
- `test_reverse_symmetry.py`: 2nd-order midpoint time-reversibility check ($< 10^{-4}$ km).
- `test_seeding.py`: 100% boundary verification for particle seeding via ray casting.
- `test_observed_filtering.py`: Strict exclusion of `INTERPOLATED` and `PREDICTED` states.
- `test_single_observation.py`: Graceful handling of 1-observation events (`data_quality_flag = "single_observation"`).
- `test_missing_forcing.py`: Graceful fallback with widened uncertainty envelope (`data_quality_flag = "forcing_unavailable"`).
- `test_id_conventions.py`: Enforcement of `SH_<event_id>_00` and `SH_<event_id>_HBEST` standards.
- `test_evt0001_synthetic.py`: Canonical synthetic event execution and benchmark comparison.
- `test_api.py`: FastAPI endpoint responses, envelope validation, and HTTP status codes.
