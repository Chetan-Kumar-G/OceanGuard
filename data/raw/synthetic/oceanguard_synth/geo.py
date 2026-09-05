"""Geometry helpers.

Internally everything is done in a local tangent-plane frame measured in
kilometres from the AOI origin (``ref_lat`` / ``ref_lon``). Output geometry is
converted to lon/lat WKT so the datasets are geo-referenced.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import transform as shp_transform

_KM_PER_DEG_LAT = 111.32


@dataclass(frozen=True)
class Frame:
    ref_lat: float
    ref_lon: float

    @property
    def km_per_deg_lon(self) -> float:
        return _KM_PER_DEG_LAT * math.cos(math.radians(self.ref_lat))

    def to_lonlat(self, x_km, y_km):
        lon = self.ref_lon + np.asarray(x_km) / self.km_per_deg_lon
        lat = self.ref_lat + np.asarray(y_km) / _KM_PER_DEG_LAT
        return lon, lat

    def to_km(self, lon, lat):
        x = (np.asarray(lon) - self.ref_lon) * self.km_per_deg_lon
        y = (np.asarray(lat) - self.ref_lat) * _KM_PER_DEG_LAT
        return x, y

    def polygon_to_wkt(self, poly_km: Polygon, precision: int = 6) -> str:
        def _fn(xs, ys):
            lon, lat = self.to_lonlat(np.asarray(xs), np.asarray(ys))
            return (lon, lat)

        geo = shp_transform(_fn, poly_km)
        return _round_wkt(geo, precision)


def _round_wkt(geom, precision: int) -> str:
    from shapely.wkt import loads as wkt_loads

    return wkt_loads(geom.wkt).wkt if geom.is_empty else _fmt(geom, precision)


def _fmt(geom, precision: int) -> str:
    from shapely import set_precision

    try:
        return set_precision(geom, 10 ** (-precision)).wkt
    except Exception:  # pragma: no cover
        return geom.wkt


def points_to_slick(points_km: np.ndarray, buffer_km: float) -> Polygon:
    """Turn a particle cloud into a single smooth slick polygon."""
    if len(points_km) < 3:
        return Polygon()
    mp = MultiPoint([tuple(p) for p in points_km])
    poly = mp.buffer(buffer_km, quad_segs=6).buffer(-buffer_km * 0.35, quad_segs=6)
    if poly.is_empty:
        poly = mp.convex_hull.buffer(buffer_km * 0.5)
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return poly.simplify(buffer_km * 0.15)


def ellipse_polygon(cx: float, cy: float, major_km: float, minor_km: float,
                    orient_deg: float, n: int = 48) -> Polygon:
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    a, b = max(major_km, 1e-3) / 2.0, max(minor_km, 1e-3) / 2.0
    x = a * np.cos(t)
    y = b * np.sin(t)
    ang = math.radians(orient_deg)
    xr = cx + x * math.cos(ang) - y * math.sin(ang)
    yr = cy + x * math.sin(ang) + y * math.cos(ang)
    return Polygon(np.column_stack([xr, yr]))


def oriented_extent(poly: Polygon):
    """(major_km, minor_km, orientation_deg) from the minimum rotated rectangle."""
    if poly.is_empty or poly.area <= 0:
        return 0.0, 0.0, 0.0
    rect = poly.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    edges = []
    for i in range(4):
        dx = xs[i + 1] - xs[i]
        dy = ys[i + 1] - ys[i]
        edges.append((math.hypot(dx, dy), math.degrees(math.atan2(dy, dx))))
    edges.sort()
    minor = edges[0][0]
    major = edges[-1][0]
    orient = edges[-1][1] % 180.0
    return major, minor, orient


def shape_descriptors(poly: Polygon) -> dict:
    if poly.is_empty or poly.area <= 0:
        return dict(solidity=0.0, eccentricity=0.0, compactness=0.0,
                    convexity=0.0, aspect_ratio=0.0)
    major, minor, _ = oriented_extent(poly)
    hull = poly.convex_hull
    solidity = poly.area / hull.area if hull.area > 0 else 0.0
    convexity = hull.length / poly.length if poly.length > 0 else 0.0
    compactness = 4.0 * math.pi * poly.area / (poly.length ** 2) if poly.length else 0.0
    ecc = math.sqrt(max(0.0, 1.0 - (minor / major) ** 2)) if major > 0 else 0.0
    aspect = major / minor if minor > 0 else 0.0
    return dict(solidity=round(solidity, 4), eccentricity=round(ecc, 4),
                compactness=round(compactness, 4), convexity=round(convexity, 4),
                aspect_ratio=round(aspect, 4))


def safe_iou(a: Polygon, b: Polygon) -> float:
    if a.is_empty or b.is_empty:
        return 0.0
    try:
        inter = a.intersection(b).area
        union = a.union(b).area
    except Exception:  # pragma: no cover - topology noise
        a, b = a.buffer(0), b.buffer(0)
        inter = a.intersection(b).area
        union = a.union(b).area
    return float(inter / union) if union > 0 else 0.0


def jitter_polygon(poly: Polygon, rng, rel_noise: float, buffer_km: float) -> Polygon:
    """Perturb a polygon boundary the way an imperfect detector would."""
    if poly.is_empty:
        return poly
    grow = rng.normal(0.0, rel_noise) * buffer_km
    out = poly.buffer(grow).buffer(-grow * 0.5)
    if out.is_empty:
        return poly
    if out.geom_type == "MultiPolygon":
        out = max(out.geoms, key=lambda g: g.area)
    return out.simplify(buffer_km * 0.2)
