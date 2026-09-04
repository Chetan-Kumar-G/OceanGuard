# F5 — Cross-Source Consistency & Evidence Conflict Detection

F5 sits at the convergence point `F5 ← F1 + F2 + F3 + F4`. For every relevant
pair of already-derived evidence items for an event it computes residuals and
labels the relationship **`SUPPORTS` / `CONTRADICTS` / `UNKNOWN`**, preserving
provenance for every item. It never collapses disagreement into a false
consensus and never discards a `CONTRADICTS` to make an event look cleaner.

## Relationship types (exactly these three, per spec)

| kind | `source_a` | `source_b` | what the residual asks |
|---|---|---|---|
| `F1_DETECTION ↔ F2_STATE` | F1 detection (scene) | F2 OBSERVED state | does the reconstructed state sit where/when F1 actually detected the slick? |
| `F2_DRIFT ↔ F3_FORCING` | F2 drift (obs 0→1) | F3 best hypothesis | is the observed slick displacement explainable by plausible forcing? |
| `F3_SOURCE_HYPOTHESIS ↔ F4_VESSEL_TRACK` | F3 best hypothesis | F4 candidate track | where/when was the vessel relative to the backtracked source? |

One `F1F2` + one `F2F3` + one `F3F4` per candidate vessel, per event.

## The rule / constraint engine (MVP — fixed thresholds, not a learned model)

```
SUPPORTS     iff every evaluable *constrained* residual ≤ its support bound
CONTRADICTS  iff any  evaluable *constrained* residual ≥ its contradict bound
UNKNOWN      grey band, or a constrained residual was not evaluable
```

* **Constrained residuals** (drive the verdict): `spatial_residual_km`,
  `temporal_residual_h`.
* **Context residuals** (reported, never load-bearing): `drift_residual_km`,
  `ais_gap_ratio`. They may only ever *downgrade* a `SUPPORTS` to `UNKNOWN`.
* Boundaries are **inclusive** on both sides (exactly at the support bound →
  `SUPPORTS`; exactly at the contradict bound → `CONTRADICTS`). `CONTRADICTS` is
  tested first, so it wins ties.
* All thresholds live in [`/shared/config/evidence_thresholds.yaml`](../../shared/config/evidence_thresholds.yaml)
  — the single source of truth. Nothing here hardcodes a bound.

### Documented overrides (all one-directional; a `CONTRADICTS` is never softened)

1. **F1F2 — low sensor confidence.** If mean F1 confidence on the seed detection
   `< evidence.overrides.min_sensor_confidence` (0.5), the pair is `UNKNOWN`.
2. **F3F4 — high AIS gap.** If the residuals would `SUPPORT` but the vessel's
   `ais_gap_ratio` in the origin window exceeds its support bound and it did not
   go dark directly over the source, downgrade to `UNKNOWN`.
3. **F3F4 — dark over source.** If `dark_gap_over_source`, the temporal residual
   is not evaluable and is dropped from the constrained set (still reported).
4. **Missing constrained field** (integration rule 8) → `UNKNOWN`, `reason`
   names the missing field — *unless* the evaluable residuals already
   `CONTRADICT` (integration rule 9).

## Residual definitions

### `spatial_residual_km` / `temporal_residual_h` per kind

* **F1F2** — `spatial` = great-circle distance between the F1 scene position and
  the F2 state centroid; `temporal` = \|F1 acquisition time − F2 state time\|.
* **F2F3** — `temporal` is not meaningful (same interval) and is reported as 0.
  `spatial` = the part of the observed displacement that **no** plausible
  `current + wind_drift_factor·wind` could produce, i.e.
  `max(0, observed_speed_kmh − max_plausible_drift_speed_kmh) · Δt`. It is `0`
  for a genuine oil slick and large (→ `CONTRADICTS`) for a vessel-like track.
  The raw observed displacement is reported as `drift_residual_km` (context).
  *Rationale:* a faithful forcing-vs-observed drift residual needs F3's live
  forcing field. Until F3 exposes a forward-drift hook, this envelope check is
  the strongest thing evaluable from tabular mocks alone, and it matches the
  reference dataset's behaviour (a real slick always `SUPPORTS` this pair).
* **F3F4** — `spatial` = `distance_to_source_effective_km` (F4);
  `temporal` = \|closest-approach time − F3 `origin_time_mid`\|. The **observed**
  closest-approach timestamp is preferred; the interpolated fill is used only
  when no observed fix exists.

### Context residuals

* **F2F3** `drift_residual_km` = raw observed slick displacement (km).
* **F3F4** `drift_residual_km` = `(1 − course_compatibility)·20 +
  |observed_speed_kn − slick_drift_speed_kn|` — weak motion disagreement
  (a vessel does not drift with its slick).
* **F3F4** `ais_gap_ratio` = `ais_gap_ratio_origin_window` (F4).

## Reference parity

Running F1–F4 synthetic mocks (`/shared/mocks/data/D1..D4`) through F5 reproduces
`D5_evidence_consistency.csv` **exactly — 77/77 relation labels**
(`SUPPORTS 28 / UNKNOWN 14 / CONTRADICTS 35`). `EVT0001` is skipped by both (only
one OBSERVED state). The integration suite keeps a ±2 tolerance so re-tuned
thresholds do not make it brittle.

## Output — `EvidenceRelation` (frozen consumer contract)

```json
{
  "evidence_id": "EV_EVT0002_002", "event_id": "EVT0002",
  "source_a_id": "EVT0002-HBEST", "source_a_type": "F3_SOURCE_HYPOTHESIS",
  "source_b_id": "EVT0002-480469227", "source_b_type": "F4_VESSEL_TRACK",
  "spatial_residual_km": 0.707, "temporal_residual_h": 14.2631,
  "relation": "SUPPORTS", "reason": "all constrained residuals within support bounds (...)"
}
```

`evidence_id` = `EV_<event_id>_<3-digit seq>` (integration rule 7). The persisted
row (`EvidenceRelationRecord` → `evidence_relations` / `evidence_items`) also
carries `drift_residual_km`, `ais_gap_ratio`, `provenance`, timestamps,
`sensor_confidence`, `observation_count`, `forcing_quality`.

## API

| method | path | purpose |
|---|---|---|
| `POST` | `/f5/evaluate-consistency/{event_id}` | compute + persist evidence relations |
| `GET`  | `/events/{event_id}/evidence` | list stored evidence relations |

Both return the shared `{"data": ..., "meta": {...}}` envelope. `meta` carries
`summary` (label counts), `skipped_reason` (when < 2 OBSERVED states / no
hypothesis), and `thresholds_source`.

## Run independently

```bash
pip install -r requirements.txt
python -m backend.f5_consistency.app          # standalone server on :8005 (needs uvicorn)
pytest tests/unit/f5 -q                        # unit + integration
```

```python
from backend.f5_consistency import evaluate_consistency
relations = evaluate_consistency("EVT0002")    # uses /shared/mocks for any upstream not live
```

## Database contract

* **Reads (read-only):** `spill_observations`, `temporal_states`,
  `source_hypotheses`, `vessel_tracks` — here via `/shared/mocks/load_mock.py`.
* **Writes:** `evidence_relations` (one row per compared pair) and
  `evidence_items` (one row per distinct evidence endpoint, for F7's graph).
  Default store is a local SQLite file (`OILTRACE_DB_URL` to point at shared
  Postgres — F5 has no geometry columns so PostGIS is not required).

## Scope

F5 only. No detection, temporal reconstruction, drift modelling, AIS logic,
graph, or forecasting. **Ranking is F6** — a separate module by the same
developer, not merged with F5.
