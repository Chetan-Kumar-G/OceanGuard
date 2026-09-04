"""F8 environmental forcing.

F8 reuses F3's proven synthetic wind/current field so forward forecasting and
backward hindcasting are driven by the *same* environment. The only F8-specific
behaviour is that per-ensemble forcing noise grows with the forecast lead time
(handled in ``ensemble.py`` via ``DriftPhysicsParams.forcing_noise_ms``).
"""
from __future__ import annotations

from backend.f3_hindcast.forcing import (
    ForcingProvider,
    ForcingVector,
    MissingForcingFallbackProvider,
    SyntheticForcingProvider,
)

__all__ = [
    "ForcingProvider",
    "ForcingVector",
    "SyntheticForcingProvider",
    "MissingForcingFallbackProvider",
    "build_forcing_provider",
]


def build_forcing_provider(cfg_dict: dict | None = None) -> ForcingProvider:
    """Synthetic forcing when the field can be built, otherwise the zero-velocity fallback."""
    try:
        return SyntheticForcingProvider(cfg_dict)
    except Exception:
        return MissingForcingFallbackProvider()
