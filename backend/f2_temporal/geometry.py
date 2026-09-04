"""
F2 — geometry.py

Deterministic GIS geometry extraction from a Shapely polygon.
All outputs are in km using WGS84 approximations (1 deg lat ≈ 111.32 km).

Functions here are pure (no side-effects) so they are trivially unit-testable.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

import numpy as np
from shapely.geometry import Polygon, MultiPolygon, mapping, shape
from shapely.ops import unary_union

# ─── constants ────────────────────────────────────────────────────────────────
_KM_PER_DEG_LAT = 111.32          # approximate km per degree of latitude
_EARTH_RADIUS_KM = 6371.0          # for haversine displacement


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two (lat, lon) points in km."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _deg_to_km_scale(centroid_lat: float) -> Tuple[float, float]:
    """Return (km_per_deg_lon, km_per_deg_lat) at a given latitude."""
    km_per_lon = _KM_PER_DEG_LAT * math.cos(math.radians(centroid_lat))
    return km_per_lon, _KM_PER_DEG_LAT


def _area_km2(polygon: Polygon, centroid_lat: float) -> float:
    """
    Approximate polygon area in km² by scaling degree² to km².
    shapely.area is in degree² — we scale via local projection.
    For higher accuracy, geopandas .to_crs(epsg=32633).area would be used,
    but for the Mediterranean AOI (lat ~35-40) this approximation is <1% error.
    """
    km_per_lon, km_per_lat = _deg_to_km_scale(centroid_lat)
    return polygon.area * km_per_lon * km_per_lat


def _perimeter_km(polygon: Polygon, centroid_lat: float) -> float:
    """Approximate exterior perimeter in km."""
    km_per_lon, km_per_lat = _deg_to_km_scale(centroid_lat)
    # shapely length is in degree units; use average scale factor
    avg_scale = math.sqrt(km_per_lon * km_per_lat)
    return polygon.length * avg_scale


def _oriented_bbox_axes(polygon: Polygon, centroid_lat: float) -> Tuple[float, float, float]:
    """
    Return (major_axis_km, minor_axis_km, orientation_deg) from the minimum
    rotated bounding rectangle.  orientation_deg in [0, 180).
    """
    km_per_lon, km_per_lat = _deg_to_km_scale(centroid_lat)
    mrr = polygon.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)[:-1]  # 4 corners
    # side lengths
    sides = []
    for i in range(len(coords)):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % len(coords)]
        dx = (x2 - x1) * km_per_lon
        dy = (y2 - y1) * km_per_lat
        sides.append(math.sqrt(dx ** 2 + dy ** 2))
    # major = longer side, minor = shorter
    a = sides[0]
    b = sides[1]
    major_km = max(a, b)
    minor_km = min(a, b)
    # orientation from the long-side vector
    if a >= b:
        dx = (coords[1][0] - coords[0][0]) * km_per_lon
        dy = (coords[1][1] - coords[0][1]) * km_per_lat
    else:
        dx = (coords[2][0] - coords[1][0]) * km_per_lon
        dy = (coords[2][1] - coords[1][1]) * km_per_lat
    angle_deg = math.degrees(math.atan2(dy, dx)) % 180.0
    return major_km, minor_km, angle_deg


def extract_geometry_features(
    polygon_geojson: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Given a GeoJSON Polygon/MultiPolygon dict, return a dict of all F2 geometry
    features (area, perimeter, centroid, bbox, axes, shape descriptors).
    Returns a dict with NaN defaults if the polygon is empty/invalid.
    """
    nan = float("nan")
    empty_result = dict(
        area_km2=0.0,
        perimeter_km=0.0,
        centroid_lat=nan,
        centroid_lon=nan,
        bbox="",
        major_axis_km=0.0,
        minor_axis_km=0.0,
        orientation_deg=0.0,
        solidity=1.0,
        eccentricity=0.0,
        compactness=1.0,
        convexity=1.0,
        aspect_ratio=1.0,
        polygon_wkt="",
    )

    try:
        geom = shape(polygon_geojson)
    except Exception:
        return empty_result

    # Flatten MultiPolygon to the union if possible
    if isinstance(geom, MultiPolygon):
        geom = unary_union(geom)

    if geom is None or geom.is_empty or not isinstance(geom, (Polygon, MultiPolygon)):
        return empty_result

    centroid = geom.centroid
    clat = centroid.y
    clon = centroid.x

    area = _area_km2(geom, clat)
    perim = _perimeter_km(geom, clat)
    major_km, minor_km, orient = _oriented_bbox_axes(geom, clat)

    # Solidity = area / convex hull area
    ch = geom.convex_hull
    ch_area = _area_km2(ch, clat) if not ch.is_empty else area
    solidity = area / ch_area if ch_area > 0 else 1.0
    solidity = min(max(solidity, 0.0), 1.0)

    # Eccentricity = sqrt(1 - (minor/major)^2)
    eccentricity = 0.0
    if major_km > 0:
        eccentricity = math.sqrt(max(0.0, 1.0 - (minor_km / major_km) ** 2))
    eccentricity = min(max(eccentricity, 0.0), 1.0)

    # Compactness = 4*pi*area / perimeter^2 (isoperimetric quotient)
    compactness = (4 * math.pi * area / (perim ** 2)) if perim > 0 else 1.0
    compactness = max(compactness, 0.0)

    # Convexity = convex hull perimeter / polygon perimeter
    ch_perim = _perimeter_km(ch, clat) if isinstance(ch, (Polygon, MultiPolygon)) and not ch.is_empty else perim
    convexity = (ch_perim / perim) if perim > 0 else 1.0
    convexity = max(convexity, 0.0)

    # Aspect ratio
    aspect_ratio = (major_km / minor_km) if minor_km > 0 else 1.0
    aspect_ratio = max(aspect_ratio, 0.0)

    # Bounding box: min_lon,min_lat,max_lon,max_lat
    minx, miny, maxx, maxy = geom.bounds
    bbox_str = f"{minx:.5f},{miny:.5f},{maxx:.5f},{maxy:.5f}"

    return dict(
        area_km2=round(area, 4),
        perimeter_km=round(perim, 4),
        centroid_lat=round(clat, 6),
        centroid_lon=round(clon, 6),
        bbox=bbox_str,
        major_axis_km=round(major_km, 4),
        minor_axis_km=round(minor_km, 4),
        orientation_deg=round(orient, 3),
        solidity=round(solidity, 4),
        eccentricity=round(eccentricity, 4),
        compactness=round(compactness, 4),
        convexity=round(convexity, 4),
        aspect_ratio=round(aspect_ratio, 4),
        polygon_wkt=geom.wkt,
    )


def compute_iou(poly_a_geojson: Dict[str, Any], poly_b_geojson: Dict[str, Any]) -> float:
    """
    Intersection-over-Union between two GeoJSON polygons in geographic coordinates.
    Returns 0.0 if either is empty or invalid.
    """
    try:
        a = shape(poly_a_geojson)
        b = shape(poly_b_geojson)
        if a is None or b is None or a.is_empty or b.is_empty:
            return 0.0
        inter = a.intersection(b).area
        union = a.union(b).area
        return round(inter / union, 6) if union > 0 else 0.0
    except Exception:
        return 0.0


def interpolate_polygon(
    geojson_a: Dict[str, Any],
    geojson_b: Dict[str, Any],
    t: float,
) -> Dict[str, Any]:
    """
    Simple linear interpolation between two GeoJSON polygons using centroid
    scaling approach.  t=0.0 → geojson_a, t=1.0 → geojson_b.
    Uses affine scaling of polygon A's coordinates toward polygon B's centroid.
    Supports both Polygon and MultiPolygon geometries.
    """
    try:
        poly_a = shape(geojson_a)
        poly_b = shape(geojson_b)
        if poly_a.is_empty:
            return geojson_b
        if poly_b.is_empty:
            return geojson_a
        ca = poly_a.centroid
        cb = poly_b.centroid
        # Interpolate centroid
        ic_x = ca.x + t * (cb.x - ca.x)
        ic_y = ca.y + t * (cb.y - ca.y)
        # Interpolate area by scaling
        area_a = poly_a.area
        area_b = poly_b.area
        target_area = area_a + t * (area_b - area_a)
        scale = math.sqrt(target_area / area_a) if area_a > 0 else 1.0

        from shapely import affinity
        dx = ic_x - ca.x
        dy = ic_y - ca.y
        shifted = affinity.translate(poly_a, xoff=dx, yoff=dy)
        scaled = affinity.scale(shifted, xfact=scale, yfact=scale, origin=(ic_x, ic_y))
        return dict(mapping(scaled))
    except Exception:
        return geojson_a


def extrapolate_polygon(
    geojson_prev: Dict[str, Any],
    geojson_last: Dict[str, Any],
    dt_extra: float,
    dt_obs: float,
) -> Dict[str, Any]:
    """
    Simple linear extrapolation beyond geojson_last by dt_extra / dt_obs fraction.
    dt_extra = hours beyond last observation.
    dt_obs   = hours between prev and last observation (denominator).
    """
    if dt_obs <= 0:
        return geojson_last
    t = dt_extra / dt_obs
    return interpolate_polygon(geojson_prev, geojson_last, 1.0 + t)
