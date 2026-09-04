from typing import Any, Dict, List, Optional, Tuple, Union
import cv2
import numpy as np
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.ops import unary_union


def mask_to_geojson_polygon(
    mask: np.ndarray,
    bbox: Union[str, Tuple[float, float, float, float], List[float]],
    min_area_px: int = 15,
    pixel_spacing_m: float = 40.0,
    simplify_tolerance: float = 0.0001,
) -> Tuple[Dict[str, Any], float]:
    """
    Convert a 2D binary segmentation mask into a georeferenced GeoJSON polygon in EPSG:4326.
    
    Args:
        mask: 2D numpy array (uint8 or bool) where positive values represent oil.
        bbox: (min_lon, min_lat, max_lon, max_lat) either as tuple/list or comma-separated string.
        min_area_px: Minimum contour area in pixels to filter speckle noise.
        pixel_spacing_m: Spatial resolution in meters per pixel.
        simplify_tolerance: Shapely simplification tolerance in degrees (~10m).
        
    Returns:
        Tuple of (geojson_dict, area_km2).
    """
    if isinstance(bbox, str):
        parts = [float(x.strip()) for x in bbox.split(",")]
        min_lon, min_lat, max_lon, max_lat = parts[0], parts[1], parts[2], parts[3]
    else:
        min_lon, min_lat, max_lon, max_lat = bbox[0], bbox[1], bbox[2], bbox[3]

    h, w = mask.shape[:2]
    binary = (mask > 0).astype(np.uint8)
    total_oil_pixels = int(np.sum(binary))

    if total_oil_pixels == 0:
        return {"type": "Polygon", "coordinates": []}, 0.0

    # Calculate true area in km2 based on pixel spacing
    area_km2 = float(total_oil_pixels * (pixel_spacing_m**2) / 1e6)

    # Find external contours
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    polygons: List[Polygon] = []
    lon_scale = (max_lon - min_lon) / w
    lat_scale = (max_lat - min_lat) / h

    for cnt in contours:
        if cv2.contourArea(cnt) < min_area_px:
            continue

        # Flatten points (N, 1, 2) -> (N, 2)
        pts = cnt.squeeze(axis=1)
        if len(pts) < 3:
            continue

        # Transform pixel (x, y) to (lon, lat)
        # x increases from min_lon to max_lon; y increases downwards from max_lat to min_lat
        coords = []
        for px, py in pts:
            lon = min_lon + px * lon_scale
            lat = max_lat - py * lat_scale
            coords.append((round(lon, 6), round(lat, 6)))

        # Close the ring if not closed
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        if len(coords) >= 4:
            try:
                poly = Polygon(coords)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if not poly.is_empty and poly.geom_type in ("Polygon", "MultiPolygon"):
                    polygons.append(poly)
            except Exception:
                continue

    if not polygons:
        return {"type": "Polygon", "coordinates": []}, area_km2

    # Combine into single unified geometry
    if len(polygons) == 1:
        merged = polygons[0]
    else:
        merged = unary_union(polygons)

    if simplify_tolerance > 0:
        merged = merged.simplify(simplify_tolerance, preserve_topology=True)

    geom_dict = mapping(merged)
    # Ensure coordinates format conforms to GeoJSON
    return dict(geom_dict), round(area_km2, 4)
