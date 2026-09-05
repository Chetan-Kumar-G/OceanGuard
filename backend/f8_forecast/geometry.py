"""Geometry helpers for F8: particle clouds <-> polygons, spread, IoU.

Works in the local tangent-plane km frame (``shared.physics.lagrangian.Frame``)
and converts to EPSG:4326 GeoJSON only at the boundary.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from shapely.geometry import MultiPoint, MultiPolygon, Point, Polygon, mapping, shape
from shapely.ops import unary_union

from shared.physics.lagrangian import Frame


def centroid_km(points_km: np.ndarray) -> np.ndarray:
    """Mean (x, y) of an (N, 2) km cloud."""
    return np.asarray(points_km, dtype=float).mean(axis=0)


def ensemble_spread_km(member_centroids_km: Sequence[np.ndarray]) -> float:
    """RMS distance of member centroids about their mean - the ensemble spread."""
    cens = np.asarray(member_centroids_km, dtype=float)
    if len(cens) < 2:
        return 0.0
    mean_cen = cens.mean(axis=0)
    return float(np.sqrt(np.mean(np.sum((cens - mean_cen) ** 2, axis=1))))


def cloud_to_polygon_km(points_km: np.ndarray, buffer_km: float, *, keep_largest: bool = True):
    """Turn an (N, 2) km particle cloud into a slick footprint polygon (km frame).

    Morphological *close* (dilate then partially erode) so nearby particles merge
    into a smooth blob - matching ``oceanguard_synth.geo.points_to_slick``. With
    ``keep_largest`` (the default, used for the predicted slick) diffuse outliers
    fragment off and only the dense core remains; pass ``keep_largest=False`` for
    the forecast *envelope*, where every ensemble patch counts.
    """
    pts = np.asarray(points_km, dtype=float)
    if len(pts) < 3:
        return Polygon()
    b = max(float(buffer_km), 0.1)
    mp = MultiPoint([tuple(p) for p in pts])
    poly = mp.buffer(b, quad_segs=6).buffer(-b * 0.35, quad_segs=6)
    if poly.is_empty:
        poly = mp.convex_hull.buffer(b * 0.5)
    if keep_largest and poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    try:
        poly = poly.simplify(b * 0.15)
    except Exception:
        pass
    return poly


def _ring_to_lonlat(coords, frame: Frame):
    lon, lat = frame.to_lonlat(np.array([c[0] for c in coords]), np.array([c[1] for c in coords]))
    return [[round(float(lo), 6), round(float(la), 6)] for lo, la in zip(lon, lat)]


def polygon_km_to_geojson(poly_km, frame: Frame) -> Dict[str, Any]:
    """Convert a km-frame Polygon/MultiPolygon to an EPSG:4326 GeoJSON geometry dict."""
    if poly_km is None or poly_km.is_empty:
        return {"type": "Polygon", "coordinates": []}
    if poly_km.geom_type == "MultiPolygon":
        polys = [
            [_ring_to_lonlat(g.exterior.coords, frame)] + [_ring_to_lonlat(r.coords, frame) for r in g.interiors]
            for g in poly_km.geoms
        ]
        return {"type": "MultiPolygon", "coordinates": polys}
    rings = [_ring_to_lonlat(poly_km.exterior.coords, frame)]
    rings += [_ring_to_lonlat(r.coords, frame) for r in poly_km.interiors]
    return {"type": "Polygon", "coordinates": rings}


def polygon_area_km2(poly_km) -> float:
    """Area of a km-frame polygon in km^2 (the frame is already metric)."""
    return float(poly_km.area) if (poly_km is not None and not poly_km.is_empty) else 0.0


def geojson_to_polygon_km(geojson: Dict[str, Any], frame: Frame) -> Polygon:
    """Convert an EPSG:4326 GeoJSON Polygon dict to a km-frame shapely Polygon."""
    if not geojson or not geojson.get("coordinates"):
        return Polygon()
    try:
        geom = shape(geojson)
    except Exception:
        return Polygon()
    if geom.is_empty:
        return Polygon()
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    ext = list(geom.exterior.coords)
    x, y = frame.to_km(np.array([c[0] for c in ext]), np.array([c[1] for c in ext]))
    poly = Polygon(np.column_stack([x, y]))
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def safe_iou(a: Polygon, b: Polygon) -> float:
    """Intersection-over-union of two polygons; 0.0 on any degeneracy."""
    try:
        if a.is_empty or b.is_empty:
            return 0.0
        inter = a.intersection(b).area
        union = a.union(b).area
        return float(inter / union) if union > 0 else 0.0
    except Exception:
        return 0.0


def coverage_frac(inner: Polygon, envelope: Polygon) -> float:
    """Fraction of ``inner`` that lies inside ``envelope`` (in [0, 1])."""
    try:
        if inner.is_empty:
            return 0.0
        a = inner.area
        return float(np.clip(inner.intersection(envelope).area / a, 0.0, 1.0)) if a > 0 else 0.0
    except Exception:
        return 0.0


def point_in_polygon(x_km: float, y_km: float, poly_km: Polygon) -> bool:
    try:
        return bool(poly_km.contains(Point(float(x_km), float(y_km))))
    except Exception:
        return False


def epoch_hours(ts_iso: str) -> float:
    """UTC ISO-8601 -> epoch hours (float)."""
    from datetime import datetime

    return datetime.fromisoformat(str(ts_iso).replace("Z", "+00:00")).timestamp() / 3600.0
