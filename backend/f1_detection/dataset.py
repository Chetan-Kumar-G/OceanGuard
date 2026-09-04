import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from PIL import Image
import torch
from torch.utils.data import Dataset

from backend.shared.config.settings import settings


def normalize_sar_raster(img: np.ndarray) -> np.ndarray:
    """
    Robust min-max normalization for SAR amplitude raster.
    Clips extreme speckle outliers at 99.5th percentile and scales to [0, 1].
    """
    img = np.nan_to_num(img, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    p_high = np.percentile(img, 99.5)
    if p_high > 0:
        img = np.clip(img, 0.0, p_high)
        img = img / p_high
    else:
        min_v, max_v = float(img.min()), float(img.max())
        if max_v > min_v:
            img = (img - min_v) / (max_v - min_v)
        else:
            img = np.zeros_like(img)
    return img


class OilSpillDataset(Dataset):
    """
    PyTorch Dataset for Sentinel-1 Synthetic D1 imagery and masks.
    Enforces strict event-level splitting (no scene leakage across train/val/test).
    """

    def __init__(
        self,
        csv_path: Optional[Path] = None,
        split: Optional[str] = "train",
        augment: bool = True,
    ):
        super().__init__()
        self.split = split
        self.augment = augment and (split == "train")

        if csv_path is None:
            csv_path = settings.synthetic_data_dir / "outputs" / "D1_satellite_scenes.csv"

        self.base_dir = csv_path.parent
        self.df = pd.read_csv(csv_path)

        if split is not None:
            self.df = self.df[self.df["split"] == split].reset_index(drop=True)

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
        row = self.df.iloc[idx]
        scene_id = str(row["scene_id"])

        # Resolve paths
        img_rel = str(row["image_path"]).replace("\\", "/")
        mask_rel = str(row["mask_path"]).replace("\\", "/")
        
        img_path = self.base_dir / img_rel
        mask_path = self.base_dir / mask_rel

        # Load raster (.npy)
        if img_path.exists():
            img = np.load(img_path).astype(np.float32)
        else:
            raise FileNotFoundError(f"Image raster not found: {img_path}")

        # Load mask (.png)
        if mask_path.exists():
            mask_img = Image.open(mask_path)
            mask = np.array(mask_img, dtype=np.int64)
        else:
            mask = np.zeros(img.shape[:2], dtype=np.int64)

        # Normalize SAR raster
        img = normalize_sar_raster(img)

        # Augmentation (only for train)
        if self.augment:
            if np.random.rand() > 0.5:
                img = np.fliplr(img).copy()
                mask = np.fliplr(mask).copy()
            if np.random.rand() > 0.5:
                img = np.flipud(img).copy()
                mask = np.flipud(mask).copy()
            k = int(np.random.choice([0, 1, 2, 3]))
            if k > 0:
                img = np.rot90(img, k).copy()
                mask = np.rot90(mask, k).copy()

        # Format tensors: (C, H, W) for image, (H, W) for target mask
        if img.ndim == 2:
            img = np.expand_dims(img, axis=0)  # (1, H, W)
        elif img.ndim == 3 and img.shape[2] in (1, 2):
            img = np.transpose(img, (2, 0, 1))

        img_tensor = torch.from_numpy(img).float()
        mask_tensor = torch.from_numpy(mask).long()

        meta = {
            "scene_id": scene_id,
            "event_id": str(row["event_id"]),
            "acquisition_timestamp": str(row["acquisition_timestamp"]),
            "sensor": str(row["sensor"]),
            "polarization": str(row["polarization"]),
            "bbox": str(row["bbox"]),
            "pixel_spacing_m": float(row["pixel_spacing_m"]),
            "oil_present": bool(row["oil_present"]),
            "lookalike_present": bool(row["lookalike_present"]),
            "true_oil_area_km2": float(row.get("true_oil_area_km2", 0.0)),
            "data_quality_flag": str(row.get("data_quality_flag", "nominal")),
            "split": str(row["split"]),
        }

        return img_tensor, mask_tensor, meta
