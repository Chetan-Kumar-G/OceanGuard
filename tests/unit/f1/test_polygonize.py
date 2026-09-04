from pathlib import Path
import numpy as np
from PIL import Image
import pytest

from backend.shared.config.settings import settings
from backend.shared.geo.polygonize import mask_to_geojson_polygon


def test_polygonize_empty_mask():
    empty = np.zeros((512, 512), dtype=np.uint8)
    poly, area = mask_to_geojson_polygon(empty, (20.0, 37.0, 21.0, 38.0))
    assert poly["type"] == "Polygon"
    assert poly["coordinates"] == []
    assert area == 0.0


def test_polygonize_known_rectangle():
    mask = np.zeros((100, 100), dtype=np.uint8)
    # 20x20 box = 400 pixels
    mask[10:30, 10:30] = 1
    bbox = (20.0, 37.0, 21.0, 38.0)
    poly, area = mask_to_geojson_polygon(
        mask, bbox, min_area_px=10, pixel_spacing_m=40.0, simplify_tolerance=0.0
    )

    assert poly["type"] == "Polygon"
    assert len(poly["coordinates"]) > 0
    # Expected area: 400 * 40 * 40 / 1e6 = 0.64 km2
    assert pytest.approx(area, rel=1e-2) == 0.64

    # Verify all coordinates lie within the bbox
    coords = poly["coordinates"][0]
    for lon, lat in coords:
        assert 20.0 <= lon <= 21.0
        assert 37.0 <= lat <= 38.0


def test_polygonize_real_sih_2048_mask():
    """Verify polygonization on real 2048x2048 SIH satellite mask archive."""
    mask_file = settings.sih_satellite_dir / "masks" / "00642.tif"
    if not mask_file.exists():
        pytest.skip(f"Real mask file not found: {mask_file}")

    img = Image.open(mask_file)
    mask = np.array(img, dtype=np.uint8)
    assert mask.shape == (2048, 2048)

    bbox = (20.5, 37.5, 21.5, 38.5)
    poly, area = mask_to_geojson_polygon(mask, bbox, min_area_px=50, pixel_spacing_m=40.0)

    assert poly["type"] in ("Polygon", "MultiPolygon")
    if np.sum(mask) > 0:
        assert area > 0.0
        assert len(poly["coordinates"]) > 0
