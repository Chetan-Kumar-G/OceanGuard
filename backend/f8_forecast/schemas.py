"""Internal request models for the F8 router / supervisor."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    """Optional overrides for a forward-forecast run.

    All fields default to the reference synthetic ``config.used.yaml`` ``replay``
    block, so ``POST /api/v1/f8/forecast/{event_id}`` with an empty body just
    works against the bundled dataset.
    """
    t0_observation_index: Optional[int] = Field(
        None,
        description="Index into the event's chronological OBSERVED states to launch from. "
                    "Default: the latest confirmed OBSERVED state.",
    )
    horizons_h: Optional[List[float]] = Field(None, description="Forecast lead times in hours")
    n_ensemble: Optional[int] = Field(None, ge=1, le=200, description="Ensemble members")
    n_particles: Optional[int] = Field(None, ge=20, le=5000, description="Particles seeded in the slick")
    base_seed: int = Field(42, description="Master RNG seed for reproducibility")
    states: Optional[List[Dict[str, Any]]] = Field(
        None, description="Live F2 TemporalSpillState rows; if omitted they are loaded from the mock dataset",
    )
