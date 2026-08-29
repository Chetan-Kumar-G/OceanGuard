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

| Stage | What it does | Status |
|---|---|---|
| 1. Detect | Segment oil spill from Sentinel-1 SAR imagery | ✅ Baseline defined |
| 2. Characterize | Estimate spill geometry (area, shape), age where feasible | ✅ Baseline defined |
| 3. Hindcast | Trace slick backward to likely origin using wind/current data | ⚠️ **Gap — no drift model sourced yet** |
| 4. Forecast | Predict future slick movement | ⚠️ **Gap — depends on stage 3** |
| 5. AIS Reconstruction | Rebuild historical vessel traffic near origin window | ✅ Baseline defined |
| 6. Filter | Remove spatially/temporally irrelevant vessel traffic | ✅ Baseline defined |
| 7. Attribute | Rank candidate vessels with explainable evidence | ✅ Baseline defined |
| 8. Explain | Investigation dashboard tying it all together | 🔜 Planned |

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

- [ ] Source a wind/current drift model for hindcasting & forecasting (INCOIS or equivalent)
- [ ] Confirm Indian-waters AIS access path (NAIS institutional access vs. AISHub substitute)
- [ ] Validate end-to-end attribution against confirmed historical spill incidents (ground truth currently unavailable)
- [ ] Handle AIS blackout / spoofing (dark vessels) — not addressed in current baseline
- [ ] Define system-level (not just per-component) latency budget

---

## 📚 References

- Krestenitis, M. et al. (2019). *Oil Spill Identification from Satellite Images Using Deep Neural Networks.* Remote Sensing, 11(15), 1762.
- Suresh, K. et al. (2025). *Detecting Oil Spills in the Marine Environment Using AIS and Satellite Datasets.* Journal of Computer Science, 18(12).
- Abbas, A. et al. (2025). *Oil Spilling Detection at Marine Environment using AIS and Satellite Datasets.* IJITCE, 13(2s).
