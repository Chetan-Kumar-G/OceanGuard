"""Standalone FastAPI app for running F5 on its own (integration rule: "HOW TO
RUN INDEPENDENTLY"). The shared `/backend/api` assembly can instead just
``from backend.f5_consistency.router import router`` and mount it.

    python -m backend.f5_consistency.app        # needs `uvicorn`
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from .router import http_exception_handler, router


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(
        title="OilTrace F5 — Cross-Source Consistency & Evidence Conflict Detection",
        version="0.1.0",
    )
    app.include_router(router)
    app.add_exception_handler(HTTPException, http_exception_handler)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "feature": "f5_consistency"}

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    try:
        import uvicorn
    except ModuleNotFoundError:
        raise SystemExit("install uvicorn to run the standalone server: pip install uvicorn")
    uvicorn.run(app, host="127.0.0.1", port=8005)
