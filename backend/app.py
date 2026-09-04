"""OilTrace AI — unified FastAPI application.

Mounts all eight pipeline features behind one app:

    F1 AI Oil-Spill Detection & Look-Alike Analysis
    F2 Multi-Temporal Spill Reconstruction & Characterization
    F3 Environmental Drift & Backward Hindcasting -> Source Hypotheses
    F4 Historical AIS Vessel Reconstruction & Correlation
    F5 Cross-Source Consistency & Evidence Conflict Detection
    F6 Evidence Fusion & Dynamic Hypothesis Ranking
    F7 Forensic Investigation Graph & Explainable Evidence Chain
    F8 Forward Forecasting, Impact Assessment & Historical Replay

Run with: ``uvicorn backend.app:app --reload``
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.f1_detection.router import router as f1_router
from backend.f2_temporal.router import router as f2_router
from backend.f3_hindcast.router import router as f3_router
from backend.f4_ais.router import router as f4_router
from backend.f5_consistency.router import router as f5_router
from backend.f6_ranking.router import router as f6_router
from backend.f7_graph.router import router as f7_router
from backend.f8_forecast.router import router as f8_router
from backend.shared.config.settings import settings as f1f2_settings

app = FastAPI(
    title="OilTrace AI — Unified Investigation API",
    version="1.0.0",
    description=(
        "AI-assisted satellite oil-spill investigation and decision-support system: "
        "detection, temporal reconstruction, backward/forward drift modelling, "
        "historical AIS correlation, cross-source consistency, evidence-fusion "
        "ranking, a forensic evidence graph, and forecast/impact/replay - behind "
        "one API. Reports probable/possible source hypotheses and candidate-vessel "
        "associations, never legal responsibility (see PDF section 11)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# F1/F2 historically dual-mount at both the bare path and an /api/v1 prefix.
app.include_router(f1_router, prefix=f1f2_settings.api_prefix)
app.include_router(f1_router)
app.include_router(f2_router, prefix=f1f2_settings.api_prefix)
app.include_router(f2_router)

app.include_router(f3_router)
app.include_router(f4_router)
app.include_router(f5_router)
app.include_router(f6_router)
app.include_router(f7_router)
app.include_router(f8_router)


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "service": "oiltrace-ai",
        "features": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"],
    }


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "OilTrace AI — Unified Investigation API",
        "docs": "/docs",
        "health": "/health",
        "pipeline": [
            "POST /api/v1/f1/detect",
            "POST /api/v1/f2/reconstruct/{event_id}",
            "POST /api/v1/f3/hindcast/{event_id}",
            "POST /api/v1/f4/reconstruct-ais/{event_id}",
            "POST /f5/evaluate-consistency/{event_id}",
            "POST /f6/rank/{event_id}",
            "GET  /events/{event_id}/graph",
            "POST /api/v1/f8/forecast/{event_id}",
            "POST /api/v1/f8/replay/{event_id}",
        ],
    }
