# OceanGuard AI — Investigator Dashboard

React + TypeScript + MapLibre GL frontend for the F1–F8 backend (`backend/app.py`).
Implements **F22 — Investigator Geospatial Dashboard** from
[`Features.md`](../Features.md): a map with the spill polygon history, the
backward-hindcast source-hypothesis region, candidate vessels, and forward
forecast/impact overlays, plus a side panel with the F6 candidate ranking,
F5 cross-source evidence, and the F7 forensic evidence chain.

Also includes:
- **Investigator login** (`/login`, `/register`) — the whole dashboard is
  behind auth (`backend/auth/`); the first account ever registered becomes
  `admin`, everyone after is `investigator`. Admins can promote/demote via
  `PATCH /admin/users/{id}/role`.
- **Public false-positive appeals** (`/appeal`) — no account needed. Submissions
  land in the investigator-only review queue at `/review` (`backend/appeals/`),
  which appends a status history rather than overwriting it.
- **Satellite quicklooks** — F1 scene thumbnails per observation, served from
  `/media/quicklook/...` (a static mount over the dataset directory).
- **Layer toggles** — show/hide the spill polygons, source region, candidate
  vessels, and forecast overlay independently on the map.
- **Run forecaster** — the F8 forecast panel lets you pick horizons, ensemble
  size, particle count, and seed, then re-run the forward ensemble (with or
  without replay validation) on demand, instead of only the pipeline's
  auto-run defaults.

> Note: the frontend route is `/review`, not `/appeals` — `/appeals` is
> proxied straight to the backend's `GET /appeals` API (see `vite.config.ts`),
> so a full-page navigation to that path would hit the JSON API instead of
> the React app.

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
