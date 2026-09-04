# OilTrace AI 🛢️🛰️

**Maritime Spill Intelligence Platform** — SIH26143 (NTRO)

OilTrace AI turns a satellite-detected oil spill into a maritime forensic investigation by reconstructing where and when it likely originated, tracing its movement, analysing historical vessel traffic, and ranking potential source vessels using explainable spatio-temporal evidence.

---

## 📌 Problem Statement

Satellite imagery can confirm an oil spill *exists* — it can't say who caused it or where it's heading next. Oceanographic drift data, historical AIS vessel traffic, and spill imagery currently live in separate systems, costing authorities critical response time during manual reconciliation.

**OilTrace AI** connects these sources end-to-end:

> Satellite → detect spill → trace backward → estimate origin → reconstruct ships → score candidate vessels → predict future movement → visualize evidence

## 👥 Users

| User | Need |
|---|---|
| Coast guard / maritime enforcement | Fast spill confirmation + ranked vessel candidates to investigate |
| Environmental agencies | Origin/drift reconstruction to direct containment and cleanup |
| Marine authorities / regulators | Evidence trail to support enforcement action |

## 🎯 Objective

Given a satellite SAR image showing a possible oil spill, detect and localize it, reconstruct its likely origin and future drift path, and produce an **explainable, evidence-backed ranking** of vessels that may be responsible — fast enough to give authorities a head start on containment and enforcement.

---

## 🏗️ Pipeline

The system implements all eight features of the
[OilTrace AI Technical Research Specification](OilTrace_Technical_Research_Specification_CleanLayout.pdf)
behind **one unified FastAPI app** (`backend/app.py`):

| # | Feature | Module | Status |
|---|---|---|---|
| F1 | AI Oil-Spill Detection & Look-Alike Analysis | `backend/f1_detection/` | ✅ Implemented |
| F2 | Multi-Temporal Spill Reconstruction & Characterization | `backend/f2_temporal/` | ✅ Implemented |
| F3 | Environmental Drift & Backward Hindcasting → Source Hypotheses | `backend/f3_hindcast/` | ✅ Implemented |
| F4 | Historical AIS Vessel Reconstruction & Correlation | `backend/f4_ais/` | ✅ Implemented |
| F5 | Cross-Source Consistency & Evidence Conflict Detection | `backend/f5_consistency/` | ✅ Implemented |
| F6 | Evidence Fusion & Dynamic Hypothesis Ranking | `backend/f6_ranking/` | ✅ Implemented |
| F7 | Forensic Investigation Graph & Explainable Evidence Chain | `backend/f7_graph/` | ✅ Implemented |
| F8 | Forward Forecasting, Impact Assessment & Historical Replay | `backend/f8_forecast/` | ✅ Implemented |

F3 and F8 share one Lagrangian particle-tracking engine (`shared/physics/lagrangian.py`) run
**backward** (hindcast) and **forward** (forecast) respectively.

> **F8 honesty note:** F8 drives its forward ensemble with F3's synthetic forcing
> *abstraction*, not the internal field used by the `oiltrace_synth` dataset generator
> (a separately-seeded implementation of the same kind of field). It reproduces the
> D8 data **contract** exactly and behaves correctly (spread grows with lead time,
> confidence decays, the envelope is scenario-based, replay never sees the future) —
> it does not bit-reproduce the reference `D8_forecast_runs.csv` values, for the same
> reason F7's graph-count check against `D7_graph_*.csv` uses a tolerance band rather
> than an exact match.

---

## ▶️ Running the unified API

```bash
pip install -r requirements.txt
uvicorn backend.app:app --reload
# then open http://127.0.0.1:8000/docs
```

Every feature is mounted on one app — `GET /health` lists them, `GET /docs` gives the
full interactive OpenAPI surface. Example calls against the bundled synthetic dataset
(event `EVT0002`):

```bash
curl -X POST localhost:8000/api/v1/f3/hindcast/EVT0002
curl -X POST localhost:8000/api/v1/f4/reconstruct-ais/EVT0002
curl -X POST localhost:8000/f5/evaluate-consistency/EVT0002
curl -X POST localhost:8000/f6/rank/EVT0002
curl      localhost:8000/events/EVT0002/graph
curl -X POST localhost:8000/api/v1/f8/forecast/EVT0002
curl -X POST localhost:8000/api/v1/f8/replay/EVT0002
```

## 🗺️ Investigator dashboard

**F22 — Investigator Geospatial Dashboard** (Features.md) is implemented at
[`frontend/`](frontend/) — React + TypeScript + MapLibre GL, driving the same
F2 → F8 pipeline as the demonstration scenario in Features.md §15: spill
polygon history, source-hypothesis region, candidate vessels, F6 ranking, F5
evidence, F7 evidence chain, and F8 forecast/impact/replay, all against the
live backend.

```bash
# backend (terminal 1)
python -m uvicorn backend.app:app --reload

# dashboard (terminal 2)
cd frontend && npm install && npm run dev
```

Open the printed `localhost:5173` URL and pick an event. See
[frontend/README.md](frontend/README.md) for details.

## ✅ Running the tests

```bash
python -m pytest
```

One suite covers all eight features end-to-end (`tests/unit/f1` … `tests/unit/f8`,
plus `tests/integration/`), running against the single synthetic dataset in
`data/raw/synthetic/outputs/`.

---

## 🧠 Model Baseline

### Spill Detection & Segmentation
- **Sensor:** Sentinel-1 SAR (Sigma0, VV/VH) — chosen for all-weather, day/night operation
- **Dataset:** [Krestenitis et al. / MKLab Oil Spill Detection Dataset](https://mklab.iti.gr/results/oil-spill-detection-dataset/) — 1,112 images, 5 semantic classes (oil spill, look-alike, ship, land, sea surface)
- **Model:** **DeepLabv3+** (MobileNetV2 backbone)
  - Highest mIoU (65.06%) among benchmarked architectures
  - Fastest practical inference (117ms/image) — chosen deliberately for response-time-sensitive deployment
  - U-Net kept as documented runner-up (marginally higher oil-spill-class IoU, slower inference)

| Model | Oil Spill IoU | mIoU | Inference |
|---|---|---|---|
| U-Net | 53.79% | 64.97% | 195ms |
| **DeepLabv3+** | 53.38% | **65.06%** | **117ms** |
| LinkNet | 51.53% | 64.79% | 171ms |
| PSPNet | 40.10% | 55.60% | 89ms |

### AIS Vessel Analysis
- **Anomaly detection:** Isolation Forest (unsupervised — no labeled distress data required)
- **Fusion scoring:** proximity + behavioral anomaly combined into a ranked, evidence-backed vessel list

---

## 📊 Datasets Explored

| Dataset | Type | Status |
|---|---|---|
| Krestenitis / MKLab OSD | SAR, 5-class segmentation | Primary baseline — access is request-gated |
| Zenodo Sentinel-1 SAR Oil Spill (Part I) | SAR, binary masks | Fallback — open access |
| Deep-SAR "SOS" | SAR/PALSAR, binary | Reference only |
| MarineTraffic AIS | Commercial AIS | Reference only |
| AccessAIS / MarineCadastre.gov | U.S. AIS, "clip and ship" | Explored — **U.S. waters only**, geography mismatch for India-facing deployment |
| NAIS (DGLL, India) | National AIS network, full Indian coastline | Correct production source — **access is institutional/authorized, not public** |
| AISHub | Global AIS, free tier | Candidate for demo/dev feed |
| INCOIS (ocean currents, India) | Oceanographic data | **Unverified — not yet confirmed** |

> ⚠️ **Known gap:** No sourced wind/current dataset yet for the hindcast/forecast stages. This blocks stages 3–4 of the pipeline until resolved.

---

## ✨ Key Features

- **Oil-Spill Time Machine** — timeline slider showing hindcast origin → observed spill → forecast drift
- **Explainable Suspect Graph** — vessel scores shown with supporting evidence (proximity, timing, trajectory, behavior), not a bare number
- **Confidence-calibrated alerts** — surfaces uncertainty (e.g. "likely look-alike, 62% confidence") rather than forcing binary decisions
- **Impact Predictor** — overlays forecast drift against coastline/protected-area layers
- **Geography-aware AIS adapter** — swappable AIS source (production: NAIS: demo: AISHub / synthetic feed)

---

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Data processing | Python, NumPy, Pandas, OpenCV |
| Remote sensing | SAR/EO preprocessing, DCNN segmentation |
| Geospatial | GeoPandas, Rasterio, Shapely, GeoJSON |
| Database / GIS | PostgreSQL + PostGIS |
| ML | TensorFlow / Keras, scikit-learn (Isolation Forest) |
| Backend | Flask |
| Frontend | React / Next.js + Mapbox or Leaflet |

---

## ⚠️ Important Positioning

Vessel results are presented as **evidence-based association / attribution scores**, not confirmed legal responsibility. This reflects both the genuine ambiguity in the underlying detection task (oil spill vs. look-alike classes are known to be difficult to separate, even in benchmark models) and responsible deployment practice for a system that could trigger real-world enforcement action.

---

## 🚧 Open Issues / Roadmap

- [x] Backward hindcast (F3) and forward forecast (F8) drift models — implemented on a
      shared synthetic Lagrangian engine; swap in ERA5/Copernicus/INCOIS forcing behind
      the same `ForcingProvider` interface for production
- [ ] Source a real wind/current dataset for hindcasting & forecasting (INCOIS or equivalent)
- [ ] Confirm Indian-waters AIS access path (NAIS institutional access vs. AISHub substitute)
- [x] Validate end-to-end attribution against synthetic historical events (`tests/integration/`);
      confirmed historical-incident ground truth is still unavailable
- [ ] Handle AIS blackout / spoofing (dark vessels) — F4 records AIS gaps as evidence but does
      not yet model spoofing
- [ ] Define system-level (not just per-component) latency budget
- [ ] Reconcile F1/F2's `backend/shared/` support package (detection/temporal schemas,
      mask polygonize, ID minting) into the cross-feature `shared/` used by F3–F8

---

## 📚 References

- Krestenitis, M. et al. (2019). *Oil Spill Identification from Satellite Images Using Deep Neural Networks.* Remote Sensing, 11(15), 1762.
- Suresh, K. et al. (2025). *Detecting Oil Spills in the Marine Environment Using AIS and Satellite Datasets.* Journal of Computer Science, 18(12).
- Abbas, A. et al. (2025). *Oil Spilling Detection at Marine Environment using AIS and Satellite Datasets.* IJITCE, 13(2s).
