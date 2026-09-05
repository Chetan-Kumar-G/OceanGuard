# Feature F1: AI Oil-Spill Detection & Look-Alike Analysis

## Overview
Feature F1 is the foundation of the OceanGuard AI maritime pipeline. It turns raw Synthetic Aperture Radar (SAR, optionally +optical) scenes into georeferenced, confidence-scored oil-spill polygons alongside look-alike risk flags and data quality flags.

- **Developer**: Developer 1 (F1 Lead)
- **Model**: Standard U-Net Baseline (1-channel input, 5-class segmentation: sea, oil, look-alike, ship, land)
- **Loss**: Combined Weighted CrossEntropy + Soft Multi-class Dice Loss
- **Outputs**: Strict conformance to `SpillDetectionResult` schema wrapped in `ApiResponse[T]` envelope

---

## Architecture & Pipeline Flow
1. **Scene Ingestion**: Reads SAR raster amplitude (.npy float32 or standard raster format) and acquisition metadata (bbox, sensor, timestamp).
2. **Preprocessing & Normalization**: Dynamic percentile-clipped (99.5%) min-max scaling to normalize radar backscatter intensity.
3. **U-Net Inference**: Forward pass producing class probability maps.
4. **Morphological Post-processing**: Connected-component analysis filtering out speckle noise under `f1_min_area_px`.
5. **Georeferenced Polygonization**: Vectorizes slick contours into EPSG:4326 GeoJSON polygons using pixel-to-geographic affine mapping.
6. **Confidence & QA**: Computes mean detector confidence over positive oil pixels; assigns data quality flags (`nominal`, `low_contrast`, `error`).

---

## Dataset Strategy
- **Real SIH Labels**: 1,200 `.tif` binary masks located at `data/raw/sih_satellite/masks/`. **Note**: These currently lack paired raw SAR imagery in the archive; they are utilized for polygonization and post-processing verification.
- **Interim / Synthetic Dataset**: Full, self-consistent synthetic dataset located at `data/raw/synthetic/` with 121 scenes and 12 events. All model checkpoints and outputs derived here are explicitly labelled `source_dataset: "synthetic"`.

---

## How to Run Standalone

### 1. Training the U-Net Baseline
Train the baseline model on the event-level synthetic dataset split:
```bash
python -m backend.f1_detection.train --epochs 5 --batch-size 4 --lr 0.001
```
Weights will be saved to `models/f1_detection/unet_baseline/v1/model.pt` along with versioned `metadata.json`.

### 2. Standalone Inference (Python)
```python
from backend.f1_detection.inference import F1Detector

detector = F1Detector()
result = detector.detect_scene(scene_id="S1_EVT0001_01")
print("Oil detected:", result.oil_present)
print("Confidence:", result.confidence)
print("GeoJSON Polygon:", result.polygon_geojson)
```

### 3. Running the API Server
Start the FastAPI server using Uvicorn:
```bash
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints:
- `POST /api/v1/f1/detect` (or `POST /f1/detect`):
  ```json
  {
    "scene_id": "S1_EVT0001_01"
  }
  ```
  Returns `ApiResponse[SpillDetectionResult]`.
- `GET /api/v1/events/{event_id}/observations` (or `GET /events/{event_id}/observations`):
  Lists all observations for an event.

---

## Testing
Run unit and integration tests:
```bash
# Unit tests
python -m pytest tests/unit/f1/ -v

# Integration tests
python -m pytest tests/integration/test_f1_pipeline.py -v
```

---

## Downstream Consumption by Developer 2 (F2)
Dev 2 consumes F1's `SpillDetectionResult` payload.
The output format is frozen and validated against Pydantic schema `backend.shared.schemas.spill_detection.SpillDetectionResult`.
Dev 2 can either call `POST /f1/detect` directly or load mock results via the synthetic dataset.
