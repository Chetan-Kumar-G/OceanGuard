# OilTrace AI — Investigator Dashboard

React + TypeScript + MapLibre GL frontend for the F1–F8 backend (`backend/app.py`).
Implements **F22 — Investigator Geospatial Dashboard** from
[`Features.md`](../Features.md): a map with the spill polygon history, the
backward-hindcast source-hypothesis region, candidate vessels, and forward
forecast/impact overlays, plus a side panel with the F6 candidate ranking,
F5 cross-source evidence, and the F7 forensic evidence chain.

## Run it

```bash
# 1. backend, from the repo root (separate terminal)
python -m uvicorn backend.app:app --reload

# 2. frontend
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`). Dev requests to
`/api`, `/events`, `/f5`, `/f6`, `/health` are proxied to the backend on
`127.0.0.1:8000` (see `vite.config.ts`) — no CORS setup needed locally.

Pick any of `EVT0001`–`EVT0012` (the bundled synthetic dataset). The dashboard
then runs the same pipeline as the spec's demonstration scenario
(Features.md §15): F2 temporal reconstruction → F3 hindcast → F4 AIS
correlation → F5 consistency → F6 ranking → F7 graph → F8 forecast/replay —
each stage shown independently in the header so a failure in one doesn't blank
the page.

## What's real vs. illustrative

- Spill polygons, the source-hypothesis uncertainty circle, and the forecast
  envelope/predicted-slick polygons are the backend's actual GeoJSON output.
- Candidate-vessel markers use `closest_approach_lat/lon` — the position of
  the AIS fix nearest the source hypothesis, added to the F4 contract
  specifically for this map (see `backend/f4_ais/distance.py`). It is
  display-only and was never part of any scoring formula.
- The base map is plain OpenStreetMap raster tiles for coastline context —
  there's no satellite SAR imagery layer (the backend doesn't serve raster
  imagery tiles).

## Build

```bash
npm run build   # tsc -b && vite build -> dist/
npm run preview # serve the production build locally
```
