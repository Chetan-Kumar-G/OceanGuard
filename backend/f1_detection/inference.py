from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import cv2
import numpy as np
import pandas as pd
import torch

from backend.f1_detection.dataset import normalize_sar_raster
from backend.f1_detection.model import UNetBaseline
from backend.shared.config.settings import settings
from backend.shared.geo.polygonize import mask_to_geojson_polygon
from backend.shared.schemas.spill_detection import SpillDetectionResult


class F1Detector:
    """
    Inference Engine for Feature F1: AI Oil-Spill Detection & Look-Alike Analysis.
    Converts raw SAR scenes into georeferenced SpillDetectionResult records.
    """

    def __init__(
        self,
        weights_path: Optional[Union[str, Path]] = None,
        confidence_threshold: Optional[float] = None,
        lookalike_threshold: Optional[float] = None,
        min_area_px: Optional[int] = None,
        device: Optional[str] = None,
    ):
        self.device = torch.device(
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.f1_confidence_threshold
        )
        self.lookalike_threshold = (
            lookalike_threshold
            if lookalike_threshold is not None
            else settings.f1_lookalike_threshold
        )
        self.min_area_px = (
            min_area_px if min_area_px is not None else settings.f1_min_area_px
        )

        if weights_path is None:
            weights_path = settings.get_model_weights_path()
        else:
            weights_path = Path(weights_path)

        self.model = UNetBaseline(in_channels=1, num_classes=5, base_features=16)
        if weights_path.exists():
            state_dict = torch.load(weights_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.weights_loaded = True
        else:
            self.weights_loaded = False

        self.model.to(self.device)
        self.model.eval()

        # Cached scenes metadata table for convenience
        self.csv_path = settings.synthetic_data_dir / "outputs" / "D1_satellite_scenes.csv"
        self._scenes_df: Optional[pd.DataFrame] = None

    @property
    def scenes_df(self) -> pd.DataFrame:
        if self._scenes_df is None and self.csv_path.exists():
            self._scenes_df = pd.read_csv(self.csv_path)
        return self._scenes_df if self._scenes_df is not None else pd.DataFrame()

    def detect_scene(
        self,
        scene_id: str,
        image_path: Optional[Union[str, Path]] = None,
        event_id: Optional[str] = None,
        acquisition_timestamp: Optional[Union[str, datetime]] = None,
        sensor: Optional[str] = None,
        polarization: Optional[str] = None,
        bbox: Optional[Union[str, Tuple[float, float, float, float], list]] = None,
        pixel_spacing_m: Optional[float] = None,
    ) -> SpillDetectionResult:
        """
        Runs full detection & segmentation pipeline on a single SAR scene.
        Guaranteed to return a valid SpillDetectionResult (never throws unhandled exceptions).
        """
        # Lookup metadata if scene_id is in D1_satellite_scenes.csv
        row = None
        if len(self.scenes_df) > 0:
            match = self.scenes_df[self.scenes_df["scene_id"] == scene_id]
            if len(match) > 0:
                row = match.iloc[0]

        if row is not None:
            if event_id is None:
                event_id = str(row["event_id"])
            if acquisition_timestamp is None:
                acquisition_timestamp = str(row["acquisition_timestamp"])
            if sensor is None:
                sensor = str(row["sensor"])
            if polarization is None:
                polarization = str(row["polarization"])
            if bbox is None:
                bbox = str(row["bbox"])
            if pixel_spacing_m is None:
                pixel_spacing_m = float(row["pixel_spacing_m"])
            if image_path is None:
                rel = str(row["image_path"]).replace("\\", "/")
                image_path = settings.synthetic_data_dir / "outputs" / rel

        # Defaults for missing metadata
        if event_id is None:
            event_id = "EVT0000"
        if sensor is None:
            sensor = "Sentinel-1"
        if bbox is None:
            bbox = (0.0, 0.0, 1.0, 1.0)
        if pixel_spacing_m is None:
            pixel_spacing_m = 40.0
        if acquisition_timestamp is None:
            acq_dt = datetime.now(timezone.utc)
        elif isinstance(acquisition_timestamp, str):
            acq_dt = datetime.fromisoformat(acquisition_timestamp.replace("Z", "+00:00"))
        else:
            acq_dt = acquisition_timestamp

        # Fallback record generator for errors
        def error_fallback(error_msg: str) -> SpillDetectionResult:
            return SpillDetectionResult(
                scene_id=scene_id,
                event_id=event_id,
                acquisition_timestamp=acq_dt,
                sensor=sensor,
                polarization=polarization,
                polygon_geojson={"type": "Polygon", "coordinates": []},
                confidence=0.0,
                lookalike_present=False,
                data_quality_flag=f"error: {error_msg[:40]}",
                oil_present=False,
                source_dataset="synthetic",
                area_km2=0.0,
            )

        # 1. Load image raster
        try:
            if image_path is None or not Path(image_path).exists():
                return error_fallback("image_not_found")

            path_obj = Path(image_path)
            if path_obj.suffix.lower() == ".npy":
                raw_raster = np.load(path_obj).astype(np.float32)
            else:
                raw_raster = cv2.imread(str(path_obj), cv2.IMREAD_UNCHANGED)
                if raw_raster is None:
                    return error_fallback("invalid_image_format")
                raw_raster = raw_raster.astype(np.float32)
        except Exception as e:
            return error_fallback(str(e))

        # Check raster validity
        if raw_raster.size == 0 or np.isnan(raw_raster).all():
            return error_fallback("empty_or_nan_raster")

        # 2. Preprocess & Normalize
        norm_raster = normalize_sar_raster(raw_raster)

        # Data quality assessment
        std_val = float(np.std(norm_raster))
        if std_val < 0.05:
            data_quality_flag = "low_contrast"
        else:
            data_quality_flag = "nominal"

        # 3. Model Forward Pass
        if norm_raster.ndim == 2:
            tensor_in = (
                torch.from_numpy(norm_raster)
                .unsqueeze(0)
                .unsqueeze(0)
                .float()
                .to(self.device)
            )
        elif norm_raster.ndim == 3:
            tensor_in = (
                torch.from_numpy(norm_raster)
                .permute(2, 0, 1)
                .unsqueeze(0)
                .float()
                .to(self.device)
            )
        else:
            return error_fallback("unsupported_raster_dimension")

        with torch.no_grad():
            logits = self.model(tensor_in)
            probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()

        # probs shape: (5, H, W)
        oil_prob = probs[1]
        lookalike_prob = probs[2]

        # 4. Connected Component Filtering on Oil Mask
        binary_oil = (oil_prob >= self.confidence_threshold).astype(np.uint8)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            binary_oil, connectivity=8
        )

        filtered_oil_mask = np.zeros_like(binary_oil)
        for label_idx in range(1, num_labels):
            area_px = stats[label_idx, cv2.CC_STAT_AREA]
            if area_px >= self.min_area_px:
                filtered_oil_mask[labels == label_idx] = 1

        total_oil_pixels = int(np.sum(filtered_oil_mask))
        oil_present = total_oil_pixels > 0

        # Confidence calculation
        if oil_present:
            mean_conf = float(np.mean(oil_prob[filtered_oil_mask > 0]))
            confidence = round(min(max(mean_conf, 0.0), 1.0), 4)
        else:
            confidence = 0.0

        # Look-alike presence (separate boolean flag)
        lookalike_pixels = int(np.sum(lookalike_prob >= self.lookalike_threshold))
        lookalike_present = lookalike_pixels >= self.min_area_px

        # 5. Georeferenced Polygonization
        polygon_geojson, area_km2 = mask_to_geojson_polygon(
            mask=filtered_oil_mask,
            bbox=bbox,
            min_area_px=self.min_area_px,
            pixel_spacing_m=pixel_spacing_m,
        )

        return SpillDetectionResult(
            scene_id=scene_id,
            event_id=event_id,
            acquisition_timestamp=acq_dt,
            sensor=sensor,
            polarization=polarization,
            polygon_geojson=polygon_geojson,
            confidence=confidence,
            lookalike_present=lookalike_present,
            data_quality_flag=data_quality_flag,
            oil_present=oil_present,
            source_dataset="synthetic",
            area_km2=area_km2,
        )
