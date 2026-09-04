"""Tests for F3.3 Polygon Seeding and Coordinate Frames."""
import numpy as np
from shared.physics.lagrangian import (
    Frame,
    point_in_polygon,
    seed_particles_in_polygon,
)


def test_frame_coordinate_roundtrip():
    """Verifies that Frame transforms between (lon, lat) and (x_km, y_km) with sub-meter precision."""
    frame = Frame(ref_lat=38.0, ref_lon=20.0)
    lon0, lat0 = 21.25, 38.50

    x_km, y_km = frame.to_km(lon0, lat0)
    lon_rec, lat_rec = frame.to_lonlat(x_km, y_km)

    assert np.isclose(lon0, lon_rec, atol=1e-7)
    assert np.isclose(lat0, lat_rec, atol=1e-7)


def test_point_in_polygon_ray_casting():
    """Verifies ray-casting point-in-polygon logic on convex and non-convex geometries."""
    # L-shaped polygon
    l_poly = [
        [0.0, 0.0],
        [4.0, 0.0],
        [4.0, 2.0],
        [2.0, 2.0],
        [2.0, 4.0],
        [0.0, 4.0],
        [0.0, 0.0],
    ]

    assert point_in_polygon(1.0, 1.0, l_poly) is True   # Bottom-left block (inside)
    assert point_in_polygon(1.0, 3.0, l_poly) is True   # Top-left block (inside)
    assert point_in_polygon(3.0, 1.0, l_poly) is True   # Bottom-right block (inside)
    assert point_in_polygon(3.0, 3.0, l_poly) is False  # Empty corner (outside)
    assert point_in_polygon(-1.0, 1.0, l_poly) is False # Far outside
    assert point_in_polygon(5.0, 5.0, l_poly) is False  # Far outside


def test_seed_particles_strictly_inside_polygon():
    """Verifies that 100% of particles seeded inside a polygon fall within its boundary."""
    # Triangle polygon
    triangle = [
        [10.0, 10.0],
        [20.0, 10.0],
        [15.0, 20.0],
        [10.0, 10.0],
    ]
    rng = np.random.default_rng(999)
    n_part = 200

    seeds = seed_particles_in_polygon(triangle, n_part, rng)
    assert len(seeds) == n_part

    # Every single seed must be inside the triangle
    for x, y in seeds:
        assert point_in_polygon(x, y, triangle) is True, f"Seed ({x}, {y}) was outside polygon!"
