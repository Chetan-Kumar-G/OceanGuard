"""
Unit tests for F2 geometry.py

Covers:
- Area extraction on a known axis-aligned rectangle
- Perimeter extraction on a known axis-aligned rectangle
- Centroid correctness
- IoU: identical polygons → 1.0, non-overlapping → 0.0, partial
- Interpolation produces a midpoint polygon
- Extrapolation moves beyond the last state
"""
import math
import pytest
from shapely.geometry import Polygon, mapping

from backend.f2_temporal.geometry import (
    extract_geometry_features,
    compute_iou,
    interpolate_polygon,
    extrapolate_polygon,
)

# ─── helpers ──────────────────────────────────────────────────────────────────
def _rect_geojson(min_lon, min_lat, max_lon, max_lat):
    """Axis-aligned rectangle as GeoJSON Polygon."""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


# ─── area tests ───────────────────────────────────────────────────────────────
class TestAreaExtraction:
    """Area of a known ~1° × 1° rectangle near lat 38 should be close to known km²."""

    def test_area_positive(self):
        geojson = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        geo = extract_geometry_features(geojson)
        assert geo["area_km2"] > 0, "Area must be positive for a non-empty polygon"

    def test_area_roughly_correct(self):
        """
        1°×1° rectangle at lat 38.5 (centre).
        km_per_lon ≈ 111.32 * cos(38.5°) ≈ 87.12 km
        km_per_lat ≈ 111.32 km
        expected area ≈ 87.12 * 111.32 ≈ 9699 km²
        """
        geojson = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        geo = extract_geometry_features(geojson)
        # allow 2% tolerance for approximation
        assert 9300 < geo["area_km2"] < 10100, f"Unexpected area: {geo['area_km2']}"

    def test_small_polygon_area(self):
        """A small 0.1° × 0.1° polygon should have area ~77 km² at lat 38."""
        geojson = _rect_geojson(20.0, 38.0, 20.1, 38.1)
        geo = extract_geometry_features(geojson)
        assert 70 < geo["area_km2"] < 100, f"Unexpected area: {geo['area_km2']}"

    def test_empty_polygon_returns_zero_area(self):
        geojson = {"type": "Polygon", "coordinates": []}
        geo = extract_geometry_features(geojson)
        assert geo["area_km2"] == 0.0

    def test_invalid_geojson_returns_zero(self):
        geo = extract_geometry_features({"type": "Polygon", "coordinates": None})
        assert geo["area_km2"] == 0.0


# ─── perimeter tests ──────────────────────────────────────────────────────────
class TestPerimeterExtraction:
    def test_perimeter_positive(self):
        geojson = _rect_geojson(20.0, 38.0, 20.1, 38.1)
        geo = extract_geometry_features(geojson)
        assert geo["perimeter_km"] > 0

    def test_perimeter_larger_than_area_for_thin_shape(self):
        """A thin ~1° wide, 0.01° tall rectangle: perimeter >> area."""
        geojson = _rect_geojson(20.0, 38.0, 21.0, 38.01)
        geo = extract_geometry_features(geojson)
        assert geo["perimeter_km"] > geo["area_km2"]


# ─── centroid tests ───────────────────────────────────────────────────────────
class TestCentroid:
    def test_centroid_at_centre_of_square(self):
        geojson = _rect_geojson(20.0, 38.0, 22.0, 40.0)
        geo = extract_geometry_features(geojson)
        assert abs(geo["centroid_lat"] - 39.0) < 0.001
        assert abs(geo["centroid_lon"] - 21.0) < 0.001

    def test_centroid_inside_polygon(self):
        geojson = _rect_geojson(19.0, 35.0, 21.0, 37.0)
        geo = extract_geometry_features(geojson)
        assert 35.0 <= geo["centroid_lat"] <= 37.0
        assert 19.0 <= geo["centroid_lon"] <= 21.0


# ─── shape descriptor bounds ──────────────────────────────────────────────────
class TestShapeDescriptors:
    def setup_method(self):
        self.geojson = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        self.geo = extract_geometry_features(self.geojson)

    def test_solidity_in_01(self):
        assert 0.0 <= self.geo["solidity"] <= 1.0

    def test_eccentricity_in_01(self):
        assert 0.0 <= self.geo["eccentricity"] <= 1.0

    def test_compactness_positive(self):
        assert self.geo["compactness"] > 0.0

    def test_convexity_in_range(self):
        # convex hull perimeter ≤ perimeter so convexity ≤ 1; but ≥ 0
        assert 0.0 <= self.geo["convexity"] <= 1.01   # slight tolerance

    def test_aspect_ratio_positive(self):
        assert self.geo["aspect_ratio"] >= 1.0   # rectangle is square-ish

    def test_bbox_format(self):
        parts = self.geo["bbox"].split(",")
        assert len(parts) == 4
        floats = [float(p) for p in parts]
        assert floats[0] < floats[2]   # min_lon < max_lon
        assert floats[1] < floats[3]   # min_lat < max_lat


# ─── IoU tests ────────────────────────────────────────────────────────────────
class TestIoU:
    def test_identical_polygons_iou_one(self):
        geo = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        assert compute_iou(geo, geo) == pytest.approx(1.0, abs=1e-5)

    def test_non_overlapping_polygons_iou_zero(self):
        a = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        b = _rect_geojson(25.0, 38.0, 26.0, 39.0)
        assert compute_iou(a, b) == pytest.approx(0.0, abs=1e-5)

    def test_half_overlap_iou(self):
        a = _rect_geojson(20.0, 38.0, 22.0, 40.0)  # 2° × 2°
        b = _rect_geojson(21.0, 38.0, 23.0, 40.0)  # shifted 1° right
        iou = compute_iou(a, b)
        # intersection = 1°×2°, union = 3°×2° → IoU = 2/6 ≈ 0.333
        assert 0.3 < iou < 0.4, f"Expected IoU ~0.333, got {iou}"

    def test_empty_polygon_gives_zero(self):
        a = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        b = {"type": "Polygon", "coordinates": []}
        assert compute_iou(a, b) == 0.0


# ─── interpolation/extrapolation tests ───────────────────────────────────────
class TestInterpolation:
    def test_t0_returns_polygon_a(self):
        a = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        b = _rect_geojson(22.0, 38.0, 23.0, 39.0)
        result = interpolate_polygon(a, b, 0.0)
        # centroid of result should be close to centroid of a
        from shapely.geometry import shape
        result_poly = shape(result)
        a_poly = shape(a)
        assert abs(result_poly.centroid.x - a_poly.centroid.x) < 0.05

    def test_t1_returns_polygon_b(self):
        a = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        b = _rect_geojson(22.0, 38.0, 23.0, 39.0)
        result = interpolate_polygon(a, b, 1.0)
        from shapely.geometry import shape
        result_poly = shape(result)
        b_poly = shape(b)
        assert abs(result_poly.centroid.x - b_poly.centroid.x) < 0.05

    def test_t05_centroid_midpoint(self):
        a = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        b = _rect_geojson(22.0, 38.0, 23.0, 39.0)
        mid = interpolate_polygon(a, b, 0.5)
        from shapely.geometry import shape
        cx = shape(mid).centroid.x
        # should be between centroids of a (20.5) and b (22.5)
        assert 20.0 < cx < 23.0

    def test_extrapolation_moves_beyond_last(self):
        prev = _rect_geojson(20.0, 38.0, 21.0, 39.0)
        last = _rect_geojson(21.0, 38.0, 22.0, 39.0)
        result = extrapolate_polygon(prev, last, dt_extra=12.0, dt_obs=12.0)
        from shapely.geometry import shape
        cx = shape(result).centroid.x
        last_cx = shape(last).centroid.x
        assert cx > last_cx, "Extrapolated centroid should move beyond last observed"
