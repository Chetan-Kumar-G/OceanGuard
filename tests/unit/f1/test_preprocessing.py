import numpy as np
import pytest
import torch

from backend.f1_detection.dataset import OilSpillDataset, normalize_sar_raster
from backend.shared.config.settings import settings


def test_normalize_sar_raster_nominal():
    raw = np.array([[0.0, 2.0], [5.0, 10.0]], dtype=np.float32)
    norm = normalize_sar_raster(raw)
    assert norm.min() >= 0.0
    assert norm.max() <= 1.0
    assert norm.shape == (2, 2)


def test_normalize_sar_raster_handles_nans_and_constants():
    # NaN and inf handling
    corrupt = np.array([[np.nan, np.inf], [-np.inf, 1.0]], dtype=np.float32)
    norm = normalize_sar_raster(corrupt)
    assert not np.isnan(norm).any()
    assert not np.isinf(norm).any()
    assert norm.min() >= 0.0
    assert norm.max() <= 1.0

    # Constant raster
    const = np.ones((10, 10), dtype=np.float32) * 5.0
    norm_const = normalize_sar_raster(const)
    assert not np.isnan(norm_const).any()


def test_dataset_item_shapes_and_types():
    ds = OilSpillDataset(split="train", augment=False)
    if len(ds) > 0:
        img, mask, meta = ds[0]
        assert isinstance(img, torch.Tensor)
        assert isinstance(mask, torch.Tensor)
        assert img.ndim == 3  # (C, H, W)
        assert img.shape[0] in (1, 2)
        assert img.shape[1] == 512
        assert img.shape[2] == 512
        assert mask.ndim == 2  # (H, W)
        assert mask.dtype == torch.int64
        assert "scene_id" in meta
        assert "event_id" in meta


def test_event_level_split_isolation():
    """Ensure no events or scenes straddle the train/val/test boundary (leakage prevention)."""
    csv_path = settings.synthetic_data_dir / "outputs" / "D1_satellite_scenes.csv"
    if not csv_path.exists():
        pytest.skip("Synthetic D1 CSV not present")

    train_ds = OilSpillDataset(split="train", augment=False)
    val_ds = OilSpillDataset(split="val", augment=False)
    test_ds = OilSpillDataset(split="test", augment=False)

    train_events = set(train_ds.df["event_id"].unique())
    val_events = set(val_ds.df["event_id"].unique())
    test_events = set(test_ds.df["event_id"].unique())

    # Assert mutual exclusivity between splits
    assert len(train_events.intersection(val_events)) == 0, "Train and Val share events!"
    assert len(train_events.intersection(test_events)) == 0, "Train and Test share events!"
    assert len(val_events.intersection(test_events)) == 0, "Val and Test share events!"
