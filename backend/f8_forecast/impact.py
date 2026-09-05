"""GIS impact overlay for F8.

Distances from the predicted slick to the modelled coast edge and to named
sensitive / protected zones, plus a coarse beaching-risk flag. Geometry comes
from the ``geography`` block of the synthetic ``config.used.yaml`` (ported from
``oceanguard_synth/d8_replay.py``).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from shapely.geometry import Point

from shared.physics.lagrangian import Frame


def coast_distance_km(cfg: Dict[str, Any], cx_km: float, cy_km: float) -> float:
    """Distance from a km-frame point to the single modelled coast edge."""
    geo = cfg.get("geography", {}) or {}
    edge = geo.get("coast_edge", "south")
    w = float(cfg.get("aoi", {}).get("width_km", 400.0))
    h = float(cfg.get("aoi", {}).get("height_km", 400.0))
    return {
        "south": cy_km,
        "north": h - cy_km,
        "west": cx_km,
        "east": w - cx_km,
    }.get(edge, cy_km)


def zone_distance_km(cfg: Dict[str, Any], cx_km: float, cy_km: float) -> Tuple[Optional[float], Optional[str]]:
    """Nearest sensitive-zone boundary distance (>=0) and its name."""
    zones = (cfg.get("geography", {}) or {}).get("sensitive_zones", []) or []
    if not zones:
        return None, None
    best_d, best_name = 9.0e9, None
    for z in zones:
        d = float(np.hypot(cx_km - z["x_km"], cy_km - z["y_km"]) - z["radius_km"])
        if d < best_d:
            best_d, best_name = d, z["name"]
    return max(best_d, 0.0), best_name


def beaching_risk(coast_d_km: float, spread_km: float) -> bool:
    """Coarse flag: the coast is within two ensemble-spread lengths of the forecast centroid."""
    return bool(coast_d_km < max(spread_km, 0.0) * 2.0)


def impact_area_candidates(
    cfg: Dict[str, Any],
    frame: Frame,
    envelope_poly_km,
    coast_d_km: float,
    spread_km: float,
) -> List[str]:
    """Named geography the forecast *envelope* reaches: the coast edge (if beaching
    risk) plus any sensitive zone whose disc intersects the envelope footprint."""
    out: List[str] = []
    if beaching_risk(coast_d_km, spread_km):
        edge = (cfg.get("geography", {}) or {}).get("coast_edge", "south")
        out.append(f"coastline:{edge}")
    if envelope_poly_km is None or getattr(envelope_poly_km, "is_empty", True):
        return out
    for z in (cfg.get("geography", {}) or {}).get("sensitive_zones", []) or []:
        disc = Point(float(z["x_km"]), float(z["y_km"])).buffer(float(z["radius_km"]))
        try:
            if envelope_poly_km.intersects(disc):
                out.append(z["name"])
        except Exception:
            continue
    return out
