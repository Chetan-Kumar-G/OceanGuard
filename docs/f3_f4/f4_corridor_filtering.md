# Feature F4.2 — AIS Spatio-Temporal Corridor Filtering

## 1. Overview
Feature F4.2 serves as the spatio-temporal bridge between F3's backward Lagrangian drift hindcast (`SourceHypothesisWindow`) and the global/historical AIS observation stream (`ValidatedAISFix`).

Its sole responsibility is to identify AIS transmissions that fall within the spatial and temporal uncertainty boundaries defined by an F3 source hypothesis window and associate them with the corresponding `event_id` and `source_hypothesis_id`.

```
           F3 Hindcast
      [SourceHypothesisWindow]
                 │
                 ▼
    ┌───────────────────────────┐
    │     F4.2 AIS Corridor     │ ◄─── Global/Historical AIS
    │         Filtering         │      [ValidatedAISFix]
    └─────────────┬─────────────┘
                  │
                  ▼
        [CorridorAISMatch]
                  │
                  ▼
        Downstream F4.3 Track
            Reconstruction
```

## 2. Interface Contracts

### Inputs
1. **F3 SourceHypothesisWindow** (Frozen F3 Contract):
   - `event_id`: Unique spill event identifier (e.g. `EVT0001`)
   - `source_hypothesis_id`: Hypothesis identifier (e.g. `SH_EVT0001_HBEST` or `SH_EVT0001_00`)
   - `source_location`: Centroid coordinates (`lat`, `lon`) in EPSG:4326
   - `origin_time_start`: Earliest estimated release time in UTC ISO-8601
   - `origin_time_end`: Latest estimated release time in UTC ISO-8601
   - `uncertainty_radius_km`: RMS spread / search radius boundary in kilometers

2. **F4.1 ValidatedAISFix** (Frozen F4.1 Contract):
   - `mmsi`: 9-digit maritime mobile service identity
   - `timestamp_utc`: Timezone-aware UTC timestamp
   - `timestamp_iso`: Canonical UTC ISO-8601 string
   - `latitude`, `longitude`: Validated coordinates in EPSG:4326
   - `sog_kn`, `cog_deg`, `heading_deg`: Validated kinematic metrics (or `None`)
   - `nav_status`, `vessel_type`, dimensions: Provenance metadata
   - `source`: AIS receiver source (e.g., `TERRESTRIAL_AIS`, `SATELLITE_AIS`)
   - `is_observed`: Observation fidelity flag (`True` = real transmission, `False` = unobserved/dead-reckoned)

### Output
- **CorridorAISMatch**: Preserves all validated fix fields, and attaches:
  - `event_id`: Conferred by matching hypothesis
  - `source_hypothesis_id`: Originating hypothesis ID
  - `distance_to_source_km`: Geodesic distance (Haversine) from fix to source centroid

- **CorridorFilterResult**: Diagnostic envelope containing:
  - `event_id`, `source_hypothesis_id`
  - `total_ais_input`: Total input fixes evaluated
  - `spatial_matches`: Count of fixes satisfying distance <= `uncertainty_radius_km`
  - `temporal_matches`: Count of fixes satisfying `t_start <= timestamp <= t_end`
  - `corridor_matches`: Count of joint spatio-temporal matches
  - `matches`: List of `CorridorAISMatch` records, sorted deterministically by `(event_id, source_hypothesis_id, mmsi, timestamp_iso)`.

## 3. Filtering Logic & Boundaries

### Spatial Filtering
- Calculates great-circle distance using the **Haversine formula** with mean Earth radius $R = 6371.0\text{ km}$:
  $$a = \sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)$$
  $$d = 2R \arcsin(\min(1.0, \sqrt{a}))$$
- Floating-point clamping is applied to eliminate domain errors in $\arcsin$.
- Explicit boundary condition:
  $$\text{distance} \le \text{uncertainty\_radius\_km} \implies \text{INCLUDED}$$
- Naive Euclidean degree approximations are strictly prohibited.

### Temporal Filtering
- Evaluates fix timestamps against origin boundaries:
  $$\text{origin\_time\_start} \le \text{timestamp\_utc} \le \text{origin\_time\_end} \implies \text{INCLUDED}$$
- Both start and end boundary timestamps are inclusive.
- All timestamps are normalized to timezone-aware UTC prior to comparison.

## 4. Multi-Hypothesis & Overlap Handling
F3 may generate multiple competing ensemble hypotheses (`SH_..._00`, `SH_..._01`, etc.) plus a pooled best estimate (`SH_..._HBEST`).
- Each hypothesis defines an independent search corridor.
- If a fix falls within two overlapping corridors, it produces **two separate `CorridorAISMatch` instances**, each tagged with its originating `source_hypothesis_id`.
- Hypotheses are never collapsed or deduplicated in a way that destroys provenance.

## 5. Explicit Non-Goals & Scope Boundaries

> [!IMPORTANT]
> **F4.2 DOES NOT DETERMINE VESSEL RESPONSIBILITY.**
> F4.2 performs spatio-temporal corridor filtering and association ONLY.

Explicit non-goals for F4.2:
1. **NO Vessel Ranking / Attribution**: F4.2 never assigns culpability or generates `CandidateVessel` scores.
2. **NO Track Reconstruction**: F4.2 does not group fixes into tracks or assign `track_id` (belongs to F4.3).
3. **NO Gap Detection / Interpolation**: F4.2 does not synthesize missing positions or calculate dark gap durations (belongs to F4.3/F4.4).
4. **NO Closest Approach Calculation**: F4.2 does not compute minimum distance across tracks (belongs to F4.4).
5. **NO Speed / Course Compatibility Scoring**: Belongs to F4.5.
6. **NO Ground-Truth Leakage**: Does not use `ground_truth_events.csv`, `is_true_source`, or `qa_source_error_km`.

## 6. Interpretation of Corridor Results
When an evaluation returns zero corridor matches, the authoritative deterministic explanation is:
> *"No AIS transmission in the tested input simultaneously satisfied the spatial and temporal corridor predicates for this source hypothesis."*

F4.2 does NOT attribute absence of fixes to a "culprit" or "true source" vessel, nor does it compute dark gaps or evaluate vessel behavior. Provenance remains strictly isolated.
