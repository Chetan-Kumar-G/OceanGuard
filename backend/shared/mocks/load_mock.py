from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union
import pandas as pd

from backend.shared.config.settings import settings
from backend.shared.schemas.spill_detection import SpillDetectionResult


def load_mock(feature: str, event_id: str) -> List[Dict[str, Any]]:
    """
    Standard mock loader utility for downstream developers (e.g. Dev2, Dev5).
    Loads reference data mapped directly to validated shared Pydantic payloads.
    """
    feature = feature.lower().strip()
    if feature in ("f1", "d1"):
        csv_path = settings.synthetic_data_dir / "outputs" / "D1_satellite_scenes.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Synthetic D1 CSV not found at: {csv_path}")

        df = pd.read_csv(csv_path)
        filtered = df[df["event_id"] == event_id]
        results = []

        import math
        from PIL import Image
        import cv2
        import numpy as np
        from shapely.geometry import shape, mapping, Polygon, MultiPolygon
        from shapely.ops import unary_union
        from backend.shared.geo.polygonize import mask_to_geojson_polygon

        for _, row in filtered.iterrows():
            bbox_str = str(row["bbox"])

            # Use f1_detected (not just oil_present) to match D2 reference behaviour:
            # f1_detected=True means the F1 model actually fired for this scene.
            # oil_present=True but f1_detected=False means the oil was too low-contrast
            # or otherwise missed — those scenes still exist but produce confidence=0.
            f1_detected = bool(row.get("f1_detected", row.get("oil_present", False)))

            if f1_detected:
                mask_rel = str(row.get("mask_path", "")).replace("\\", "/")
                mask_file = settings.synthetic_data_dir / "outputs" / mask_rel
                if not mask_file.exists():
                    mask_file = settings.synthetic_data_dir / "outputs" / "masks" / f"{row['scene_id']}.png"

                if mask_file.exists():
                    mask_arr = np.array(Image.open(mask_file))
                    oil_mask = (mask_arr == 1).astype(np.uint8)
                    n_oil = int(np.sum(oil_mask))
                    pix_spacing = float(row.get("pixel_spacing_m", 40.0))

                    # 1. Morphological cleanup of Gaussian feathering artifact
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                    iters = 2 if n_oil < 2500 else 1
                    cleaned_oil_mask = cv2.erode(oil_mask, kernel, iterations=iters)

                    raw_geojson, _ = mask_to_geojson_polygon(
                        mask=cleaned_oil_mask,
                        bbox=bbox_str,
                        min_area_px=10,
                        pixel_spacing_m=pix_spacing,
                    )
                    poly = shape(raw_geojson)

                    if not poly.is_empty:
                        clat = poly.centroid.y
                        km_per_lat = 111.32
                        km_per_lon = 111.32 * math.cos(math.radians(clat))
                        deg_per_km = 1.0 / km_per_lat

                        # 2. Replicate F1 look-alike merge if flagged in detector simulation
                        if bool(row.get("f1_lookalike_merged", False)):
                            la_mask = (mask_arr == 2).astype(np.uint8)
                            if np.any(la_mask):
                                la_geo, _ = mask_to_geojson_polygon(
                                    mask=la_mask,
                                    bbox=bbox_str,
                                    min_area_px=10,
                                    pixel_spacing_m=pix_spacing,
                                )
                                la_shape = shape(la_geo)
                                if not la_shape.is_empty:
                                    la_geoms = (
                                        list(la_shape.geoms)
                                        if la_shape.geom_type == "MultiPolygon"
                                        else [la_shape]
                                    )
                                    nearest = min(la_geoms, key=lambda g: g.distance(poly))
                                    poly = unary_union([poly, nearest]).convex_hull

                        # 3. Replicate F1 partial filament erosion if flagged in detector simulation
                        if bool(row.get("f1_partial", False)):
                            buf_deg = 0.45 * deg_per_km
                            eroded = poly.buffer(-buf_deg * 0.7).buffer(buf_deg * 0.35)
                            if not eroded.is_empty and eroded.area > 0:
                                if eroded.geom_type == "MultiPolygon":
                                    eroded = max(eroded.geoms, key=lambda g: g.area)
                                poly = eroded

                        polygon_geojson = dict(mapping(poly))
                        det_area_km2 = poly.area * km_per_lon * km_per_lat
                    else:
                        polygon_geojson = {"type": "Polygon", "coordinates": []}
                        det_area_km2 = 0.0
                else:
                    polygon_geojson = {"type": "Polygon", "coordinates": []}
                    det_area_km2 = 0.0
            else:
                polygon_geojson = {"type": "Polygon", "coordinates": []}
                det_area_km2 = 0.0

            result = SpillDetectionResult(
                scene_id=str(row["scene_id"]),
                event_id=str(row["event_id"]),
                acquisition_timestamp=datetime.fromisoformat(
                    str(row["acquisition_timestamp"]).replace("Z", "+00:00")
                ),
                sensor=str(row["sensor"]),
                polarization=str(row["polarization"]),
                polygon_geojson=polygon_geojson,
                confidence=float(row.get("f1_confidence", 0.85 if f1_detected else 0.0)),
                lookalike_present=bool(row.get("lookalike_present", False)),
                data_quality_flag=str(row.get("data_quality_flag", "nominal")),
                oil_present=f1_detected,   # only treat f1_detected scenes as oil present
                source_dataset="synthetic",
                area_km2=round(float(det_area_km2), 4),
            )
            results.append(result.model_dump())

        return results

    if feature in ("f2", "d2"):
        from backend.shared.schemas.temporal import TemporalSpillState
        from shapely import wkt as shapely_wkt
        from shapely.geometry import mapping

        csv_path = settings.synthetic_data_dir / "outputs" / "D2_temporal_states.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Synthetic D2 CSV not found at: {csv_path}")

        df = pd.read_csv(csv_path)
        filtered = df[df["event_id"] == event_id]
        results = []

        for _, row in filtered.iterrows():
            # Reconstruct GeoJSON from WKT
            try:
                geom = shapely_wkt.loads(str(row["polygon_wkt"]))
                polygon_geojson = mapping(geom)
            except Exception:
                polygon_geojson = {"type": "Polygon", "coordinates": []}

            def _float_or_none(val):
                import math
                try:
                    v = float(val)
                    return None if math.isnan(v) else v
                except (TypeError, ValueError):
                    return None

            state = TemporalSpillState(
                event_id=str(row["event_id"]),
                observation_id=str(row["observation_id"]),
                scene_id=str(row.get("scene_id", "")),
                timestamp=datetime.fromisoformat(
                    str(row["timestamp"]).replace("Z", "+00:00")
                ),
                sim_hours=float(row.get("sim_hours", 0.0)),
                state_type=str(row["state_type"]),
                polygon_geojson=polygon_geojson,
                polygon_wkt=str(row.get("polygon_wkt", "")),
                area_km2=float(row.get("area_km2", 0.0)),
                perimeter_km=float(row.get("perimeter_km", 0.0)),
                centroid_lat=float(row.get("centroid_lat", 0.0)),
                centroid_lon=float(row.get("centroid_lon", 0.0)),
                bbox=str(row.get("bbox", "")),
                major_axis_km=float(row.get("major_axis_km", 0.0)),
                minor_axis_km=float(row.get("minor_axis_km", 0.0)),
                orientation_deg=float(row.get("orientation_deg", 0.0)),
                solidity=float(row.get("solidity", 1.0)),
                eccentricity=float(row.get("eccentricity", 0.0)),
                compactness=float(row.get("compactness", 1.0)),
                convexity=float(row.get("convexity", 1.0)),
                aspect_ratio=float(row.get("aspect_ratio", 1.0)),
                previous_observation_id=str(row.get("previous_observation_id", "")),
                polygon_iou=_float_or_none(row.get("polygon_iou")),
                centroid_displacement_km=_float_or_none(row.get("centroid_displacement_km")),
                area_change_pct=_float_or_none(row.get("area_change_pct")),
                persistence=int(row.get("persistence", 1)),
                observation_gap_hours=_float_or_none(row.get("observation_gap_hours")),
                f1_confidence=float(row.get("f1_confidence", 0.0)),
                data_quality=str(row.get("data_quality", "observed")),
                is_observed=bool(row["is_observed"]),
            )
            results.append(state.model_dump())

        return results

    raise NotImplementedError(f"Mock loader for feature '{feature}' not implemented yet.")
