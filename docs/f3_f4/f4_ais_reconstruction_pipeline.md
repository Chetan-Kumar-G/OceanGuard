# Feature F4 — Historical AIS Vessel Reconstruction & Correlation Pipeline

## 1. Executive Summary & Core Principle

Feature F4 reconstructs and correlates historical AIS vessel traffic against the environmental drift hindcast source hypotheses produced by Feature F3.

### Core Principle
**F4 is an evidence-generation and vessel-association pipeline. It DOES NOT determine legal responsibility or guilt.**

- F4 does NOT use supervised machine learning or black-box attribution classifiers.
- F4 does NOT output "probabilities of guilt", "culpability scores", or "culprit classifications".
- F4 produces transparent, auditable, and deterministic physical and navigational evidence features.
- Downstream features (F5 Evidence & Attribution, F6 Multi-criteria Decision Analysis, F7 Reporting) combine these signals into legal forensic packages.

---

## 2. End-to-End Pipeline Architecture

```
                 Feature F3 (Environmental Drift & Hindcasting)
                                       │
                                       ▼
                       [SourceHypothesisWindow] (EPSG:4326, UTC)
                                       │
                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ FEATURE F4: Historical AIS Reconstruction & Spatio-Temporal Correlation     │
 │                                                                             │
 │  Raw AIS Stream (D4_ais_raw.csv)                                            │
 │          │                                                                  │
 │          ▼                                                                  │
 │  [F4.1 AIS Ingestion & Validation] ────────────────► [ValidatedAISFix]      │
 │                                                              │              │
 │                                                              ▼              │
 │  [F4.2 Spatio-Temporal Corridor Filter] ───────────► [CorridorAISMatch]     │
 │                                                              │              │
 │                                                              ▼              │
 │  [F4.3 Track Context & Reconstruction] ────────────► [VesselTrack]          │
 │                                                              │              │
 │          ┌───────────────────────┬───────────────────────────┤              │
 │          ▼                       ▼                           ▼              │
 │  [F4.4 Closest Approach]  [F4.5 Dark Gap Engine]  [F4.6 Compatibility]      │
 │  (Observed/Interpolated)  (Over-source gaps)      (Temporal, Speed, Course) │
 │          │                       │                           │              │
 │          └───────────────────────┼───────────────────────────┘              │
 │                                  ▼                                          │
 │  [F4.7 Candidate Generation] ──────────────────────► [CandidateVessel[]]    │
 │                                                              │              │
 │                                                              ▼              │
 │  [F4.8 Master Supervisor & Storage] ───────────────► [F4Repository]         │
 └──────────────────────────────────────────────────────────────┬──────────────┘
                                                                │
                                                                ▼
                         Feature F5 (Evidence & Attribution)
```

---

## 3. Explicit Status Categorization

To maintain total transparency, all algorithms, parameters, and behaviors are categorized into one of four explicit classifications:

### A. SPECIFIED BY BLUEPRINT
1. **Corridor Spatial & Temporal Predicates (F4.2):**
   - Geodesic distance: $d \le \text{uncertainty\_radius\_km}$ using spherical Haversine ($R = 6371.0\text{ km}$).
   - Strict adherence without radius expansion, tolerance buffers, or multipliers.
   - Temporal window: $\text{origin\_window\_start} \le t \le \text{origin\_window\_end}$ (endpoints inclusive, UTC).
2. **Deterministic Track Grouping & Ordering (F4.3):**
   - Grouping by MMSI and hypothesis context.
   - Deterministic sorting by `timestamp_utc`.
   - Track ID convention: `TRK_<event_id>_<mmsi>`.
3. **Observed vs. Non-Observed Provenance (F4.3, F4.4):**
   - Exact preservation of `is_observed` flag.
   - Interpolated positions are never mislabeled as observed AIS transmissions.
   - Effective distance: $\min(\text{observed}, \text{interpolated})$.
   - `closest_approach_is_interpolated = True` if and only if the minimum distance originated from an unobserved/interpolated fix.
4. **Circular Angular Compass Difference (F4.6):**
   - Shortest angular difference: $\Delta \theta = \min(|\theta_1 - \theta_2|, 360^\circ - |\theta_1 - \theta_2|)$ handling $0^\circ/360^\circ$ wrap-around.
5. **Frozen CandidateVessel Output Contract (F4.7):**
   - Strict conformance to `shared/schemas/f4_contract.py`.
   - Zero ML attribution classifiers, zero culpability scores.

### B. MVP ASSUMPTION
1. **F4.2 → F4.3 Track Context Retrieval Buffer:**
   - *Assumption:* When reconstructing tracks for candidate vessels identified in F4.2, AIS transmissions are deterministically retrieved within a temporal context buffer of $[t_{\text{start}} - 24.0\text{h}, t_{\text{end}} + 24.0\text{h}]$.
   - *Rationale:* Prevents unbounded global archive scanning while retaining sufficient trajectory history to observe entry, transit, exit, and dropouts.
2. **Configurable Reporting Gap Threshold (`1.0 Hour`):**
   - *Assumption:* A transmission interval $\Delta t > 1.0\text{ h}$ constitutes a reporting gap for generic AIS streams.
   - *Rationale:* In raw operational AIS, expected reporting interval metadata per vessel (ranging from 2s to 3min underway, up to 1h moored) is unavailable.
3. **Missing Kinematic Compatibility Values Semantics:**
   - *Assumption:* When SOG or COG is unavailable (`None`), the frozen `CandidateVessel` schema (which mandates numeric floats in $[0, 1]$) receives neutral compatibility $0.5$.
   - *Distinction:* Provenance fields `observed_speed_kn` and `observed_course_deg` remain `None`, enabling downstream F5/F6 to clearly distinguish *missing evidence* from *measured stationary/North values* (`SOG=0.0`, `COG=0.0`).
4. **Gap-Based Track Completeness Proxy:**
   - *Assumption:* Evaluates $1.0 - (\text{total\_gap\_hours} / \text{track\_duration\_h})$.
   - *Rationale:* This represents an active coverage proxy, NOT the percentage of expected pings (as broadcast cadence is unknown).
5. **Linear Temporal Compatibility Decay:**
   - *Assumption:* $1.0$ if active or dark-gap inside origin window; linear decay to $0.0$ over 24 hours outside the window boundaries.

### C. [UNRESOLVED] ARCHITECTURAL DECISIONS
1. **[UNRESOLVED — TRACK RECONSTRUCTION CONTEXT WINDOW]:**
   - Upstream specifications do not define the exact temporal context window for historical track retrieval around an F3 origin window. Flagged for upstream formalization.
2. **[UNRESOLVED — DYNAMIC AIS CADENCE PROFILING]:**
   - Dynamic thresholding based on vessel static Class A/B metadata and navigation status is deferred to F5/F6 evidence fusion.
3. **[UNRESOLVED — TRACK COMPLETENESS FORMULATION]:**
   - Definitive completeness calculation requires ITU-R M.1371 cadence modeling against static voyage parameters.

### D. OFFLINE QA ONLY
1. **Ground Truth Labels & Datasets:**
   - `data/evaluation/synthetic/ground_truth_events.csv`, `data/raw/synthetic/D4_vessel_tracks.csv`, `is_true_source`, and `qa_source_error_km` are quarantined exclusively to test fixtures.
   - Runtime code has ZERO dependencies on these tokens.
2. **EVT0001 F3 Hypothesis Error Limitation:**
   - Offline QA demonstrates that for `EVT0001`, the F3 hindcast centroid error is $62.25\text{ km}$, while the uncertainty radius is $7.66\text{ km}$.
   - True source MMSI `329813634` is $52.5\text{ km}$ from the hypothesis centroid and is honestly excluded by F4.2.
   - F4 does NOT artificially widen its corridor or add tolerances to force candidate inclusion. This limitation is reported as an upstream F3 data quality property.

---

## 4. Ground-Truth Isolation & Forensic Firewall Audit

Static search across all `.py` files in `backend/f4_ais/`:
- `banned_tokens = ["ground_truth_events", "is_true_source", "qa_source_error_km", "D4_vessel_tracks", "tolerance_km", "culprit", "guilty", "responsible_vessel", "guilt_probability"]`

**Audit Result: ZERO occurrences (0 violations).**

---

## 5. Protected Dataset Verification

SHA-256 Checksums:
- `data/raw/synthetic/D4_ais_raw.csv`: `dd6eb9d443033135dcda76f647ab837ed50ea4e1f8c178cdf9b29142daa66eec` (VERIFIED UNCHANGED)
- `data/raw/synthetic/D4_vessel_tracks.csv`: `8bd8270035294826689524378909123b053bb48eb650c86c2582bf6ce5c6ad4b` (VERIFIED UNCHANGED)
- `data/evaluation/synthetic/ground_truth_events.csv`: `c7ef887b395ab5762c4ab097ab462d993074373076b5531fb090ad84d452490f` (VERIFIED UNCHANGED)

---

## 6. Acceptance & Freeze Verdict

- F4.0: 🔒 COMPLETE + FROZEN
- F4.1: 🔒 COMPLETE + FROZEN
- F4.2: 🔒 COMPLETE + FROZEN
- F4.3: 🔒 COMPLETE + FROZEN
- F4.4: 🔒 COMPLETE + FROZEN
- F4.5: 🔒 COMPLETE + FROZEN
- F4.6: 🔒 COMPLETE + FROZEN
- F4.7: 🔒 COMPLETE + FROZEN
- F4.8: 🔒 COMPLETE + FROZEN

**ALL GATES PASSED. F4 IS FINALLY FROZEN. READY FOR FEATURE F5.**
