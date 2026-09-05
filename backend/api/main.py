"""F1+F2-only FastAPI app, kept for isolated detection/temporal dev and testing.

For the full F1-F8 system, run ``backend.app:app`` instead
(``uvicorn backend.app:app --reload``).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.f1_detection.router import router as f1_router
from backend.f2_temporal.router import router as f2_router
from backend.shared.config.settings import settings

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="OceanGuard AI Backend Service — F1: Detection | F2: Temporal Reconstruction",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount F1 router
app.include_router(f1_router, prefix=settings.api_prefix)
app.include_router(f1_router)

# Mount F2 router
app.include_router(f2_router, prefix=settings.api_prefix)
app.include_router(f2_router)


@app.get("/health")
def healthcheck():
    return {"status": "ok", "service": "oceanguard-f1-f2", "version": settings.api_version}
