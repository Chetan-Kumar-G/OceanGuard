"""D1 - satellite dataset.

One row per SAR scene. Rasters and ground-truth masks are written to disk; the
metadata table carries acquisition geometry, environmental QA, label taxonomy
flags, provenance and the event-level train/val/test split. The module also
returns, per event, the simulated F1 detector output (a possibly-imperfect or
missing polygon plus a confidence) which feeds D2 and D3.

Mask taxonomy:  0 sea | 1 oil spill | 2 look-alike | 3 ship | 4 land
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, box

from .config import Config
from .environment import Environment
from .events import Event
from .geo import Frame, jitter_polygon, oriented_extent, safe_iou
from .rng import RNG
from .spill_truth import SpillTruth

MASK_PALETTE = {
    0: (12, 28, 60),      # sea
    1: (230, 90, 40),     # oil
    2: (240, 210, 90),    # look-alike
    3: (250, 250, 250),   # ship
    4: (110, 90, 70),     # land
}


@dataclass
class Detection:
    event_id: str
    scene_id: str
    t_h: float
    detected: bool
    polygon_km: Polygon | None
    f1_confidence: float
    lookalike_merged: bool = False
    partial: bool = False


@dataclass
class D1Result:
    scenes: pd.DataFrame
    detections: dict[str, list[Detection]] = field(default_factory=dict)


def _contrast_factor(wind: float, det_cfg: Config) -> float:
    lo = float(det_cfg["low_wind_speed"])
    hi = float(det_cfg["high_wind_speed"])
    left = np.clip((wind - lo * 0.5) / max(lo * 0.5, 1e-6), 0.0, 1.0)
    right = np.clip((hi + 3.0 - wind) / 3.0, 0.0, 1.0)
    return float(0.15 + 0.85 * min(left, right))


class _SceneGrid:
    def __init__(self, cx_km, cy_km, size_px, pix_m):
        self.size = int(size_px)
        self.pix_km = pix_m / 1000.0
        half = self.size * self.pix_km / 2.0
        self.x_min = cx_km - half
        self.x_max = cx_km + half
        self.y_min = cy_km - half
        self.y_max = cy_km + half

    @property
    def bbox_poly(self) -> Polygon:
        return box(self.x_min, self.y_min, self.x_max, self.y_max)

    def to_px(self, xs, ys):
        col = (np.asarray(xs) - self.x_min) / self.pix_km
        row = (self.y_max - np.asarray(ys)) / self.pix_km
        return col, row

    def poly_to_px(self, poly: Polygon):
        rings = []
        geoms = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
        for g in geoms:
            if g.is_empty:
                continue
            xs, ys = g.exterior.coords.xy
            col, row = self.to_px(np.asarray(xs), np.asarray(ys))
            rings.append(list(zip(col.tolist(), row.tolist())))
        return rings


def _render_scene(grid: _SceneGrid, g: np.random.Generator, truth_poly: Polygon,
                  contrast: float, lookalikes: list[Polygon], ships_px: list,
                  land_poly: Polygon | None):
    size = grid.size
    # SAR-like background: Rayleigh-ish sea clutter
    img = g.gamma(shape=4.0, scale=0.12, size=(size, size)).astype(np.float32)
    img += g.normal(0.0, 0.02, (size, size)).astype(np.float32)
    mask = np.zeros((size, size), dtype=np.uint8)

    def _fill(poly, value_img=None, value_mask=None, feather=0):
        rings = grid.poly_to_px(poly)
        if not rings:
            return None
        layer = Image.new("L", (size, size), 0)
        d = ImageDraw.Draw(layer)
        for r in rings:
            if len(r) >= 3:
                d.polygon(r, fill=255)
        arr = np.asarray(layer, dtype=np.float32) / 255.0
        if feather:
            from PIL import ImageFilter
            arr = np.asarray(layer.filter(ImageFilter.GaussianBlur(feather)),
                             dtype=np.float32) / 255.0
        sel = arr > 0.01
        if value_mask is not None:
            mask[sel] = value_mask
        if value_img is not None:
            nonlocal img
            img = img * (1.0 - arr) + value_img * arr
        return sel

    if land_poly is not None and not land_poly.is_empty:
        texture = 1.1 + g.gamma(3.0, 0.14, (size, size)).astype(np.float32)
        _fill(land_poly, value_img=texture, value_mask=4)

    for la in lookalikes:
        depth = float(g.uniform(0.35, 0.6))
        _fill(la, value_img=img * depth, value_mask=2, feather=1.5)

    if truth_poly is not None and not truth_poly.is_empty:
        # darker with higher contrast; feather the edge
        depth = float(np.clip(0.12 + (1.0 - contrast) * 0.5, 0.1, 0.75))
        _fill(truth_poly, value_img=img * depth, value_mask=1, feather=1.2)

    for (cx, cy, bright) in ships_px:
        r = 1
        x0, x1 = int(cx - r), int(cx + r + 1)
        y0, y1 = int(cy - r), int(cy + r + 1)
        if 0 <= x0 and x1 <= size and 0 <= y0 and y1 <= size:
            img[y0:y1, x0:x1] = bright
            mask[y0:y1, x0:x1] = 3

    np.clip(img, 0.0, 12.0, out=img)
    return img, mask


def _save_raster(path: Path, img: np.ndarray, fmt: str):
    if fmt == "none":
        return
    np.save(path.with_suffix(".npy"), img.astype(np.float32))


def _save_mask(path: Path, mask: np.ndarray):
    im = Image.fromarray(mask, mode="P")
    pal = [0, 0, 0] * 256
    for k, (r, gg, b) in MASK_PALETTE.items():
        pal[k * 3: k * 3 + 3] = [r, gg, b]
    im.putpalette(pal)
    im.save(path.with_suffix(".png"))


def _save_quicklook(path: Path, img: np.ndarray):
    v = np.clip(img / np.percentile(img, 99.0), 0, 1)
    Image.fromarray((v * 255).astype(np.uint8)).save(path.with_suffix(".png"))


def generate_d1(cfg: Config, rng: RNG, env: Environment, frame: Frame,
                events: list[Event], truths: dict[str, SpillTruth],
                fleet, out_dir: Path) -> D1Result:
    sat = cfg["satellite"]
    det_cfg = sat["detection"]
    fmt = cfg["output"]["raster_format"]
    img_dir = out_dir / "images"
    mask_dir = out_dir / "masks"
    ql_dir = out_dir / "quicklook"
    for d in (img_dir, mask_dir, ql_dir):
        d.mkdir(parents=True, exist_ok=True)

    w = float(cfg["aoi"]["width_km"])
    h = float(cfg["aoi"]["height_km"])
    size_px = int(sat["scene_size_px"])
    pix_m = float(sat["pixel_spacing_m"])
    scene_km = size_px * pix_m / 1000.0

    rows: list[dict] = []
    detections: dict[str, list[Detection]] = {}
    scene_counter = 0

    for ev in events:
        g = rng.stream("d1", ev.event_id)
        truth = truths[ev.event_id]
        det_list: list[Detection] = []

        overpass_times: list[float] = []
        if g.random() < float(sat["pre_release_scene_prob"]):
            overpass_times.append(ev.t0_h - float(g.uniform(4.0, 16.0)))
        t = ev.t0_h + float(g.uniform(1.0, sat["revisit_hours"] * 0.5))
        t_stop = ev.t0_h + float(sat["observation_span_days"]) * 24.0
        while t <= t_stop:
            overpass_times.append(t)
            t += float(sat["revisit_hours"]) + float(g.uniform(-1, 1) * sat["revisit_jitter_h"])

        for k, ot in enumerate(overpass_times):
            scene_counter += 1
            scene_id = f"S1_{ev.event_id}_{k:02d}"
            tile_id = f"T{scene_counter:05d}"

            pre_release = ot < truth.times_h[0]
            truth_poly_full = Polygon() if pre_release else truth.polygon_at(ot, g)

            if not truth_poly_full.is_empty:
                c = truth_poly_full.centroid
                cx = float(np.clip(c.x + g.normal(0, scene_km * 0.12), scene_km / 2, w - scene_km / 2))
                cy = float(np.clip(c.y + g.normal(0, scene_km * 0.12), scene_km / 2, h - scene_km / 2))
            else:
                cx = float(g.uniform(scene_km / 2, w - scene_km / 2))
                cy = float(g.uniform(scene_km / 2, h - scene_km / 2))
            grid = _SceneGrid(cx, cy, size_px, pix_m)
            scene_box = grid.bbox_poly

            truth_poly = truth_poly_full.intersection(scene_box) if not truth_poly_full.is_empty else Polygon()
            oil_in_scene = (not truth_poly.is_empty) and truth_poly.area > 0.05

            wind = float(np.ravel(env.wind_speed(np.array([cx]), np.array([cy]), ot))[0])
            cur_u, cur_v = env.current_at(np.array([cx]), np.array([cy]), ot)
            cur_speed = float(np.hypot(np.ravel(cur_u)[0], np.ravel(cur_v)[0]))
            contrast = _contrast_factor(wind, det_cfg)

            # look-alikes: dark patches unrelated to oil
            n_la = int(g.integers(sat["lookalikes_per_scene"][0], sat["lookalikes_per_scene"][1] + 1))
            lookalikes = []
            for _ in range(n_la):
                lx = g.uniform(grid.x_min, grid.x_max)
                ly = g.uniform(grid.y_min, grid.y_max)
                rr = g.uniform(0.6, 3.0)
                lookalikes.append(Polygon(_blob(lx, ly, rr, g)))

            # ships: some near the culprit position, some random
            n_ship = int(g.integers(sat["ships_per_scene"][0], sat["ships_per_scene"][1] + 1))
            ships_px = []
            ship_present = False
            culprit = fleet.by_mmsi.get(ev.source_mmsi)
            for si in range(n_ship):
                if si == 0 and culprit is not None and culprit.active(ot) and g.random() < 0.5:
                    sp = culprit.position(ot)
                    sx, sy = float(sp[0]), float(sp[1])
                else:
                    sx = g.uniform(grid.x_min, grid.x_max)
                    sy = g.uniform(grid.y_min, grid.y_max)
                col, row = grid.to_px(sx, sy)
                if 1 <= col < size_px - 1 and 1 <= row < size_px - 1:
                    ships_px.append((float(col), float(row), float(g.uniform(4.0, 9.0))))
                    ship_present = True

            land_poly = None
            land_present = False
            if g.random() < float(sat["land_scene_prob"]):
                corner = g.integers(0, 4)
                cxl = grid.x_min if corner in (0, 2) else grid.x_max
                cyl = grid.y_min if corner in (0, 1) else grid.y_max
                land_poly = Polygon(_blob(cxl, cyl, g.uniform(4.0, 9.0), g))
                land_poly = land_poly.intersection(scene_box)
                land_present = not land_poly.is_empty

            img, mask = _render_scene(grid, g, truth_poly if oil_in_scene else Polygon(),
                                      contrast, lookalikes, ships_px, land_poly)

            _save_raster(img_dir / scene_id, img, fmt)
            _save_mask(mask_dir / scene_id, mask)
            if cfg["output"]["write_quicklook"]:
                _save_quicklook(ql_dir / scene_id, img)

            # ---- simulate the F1 detector ----
            detected = False
            det_poly = None
            merged = False
            partial = False
            conf = 0.0
            if oil_in_scene:
                area = truth_poly.area
                pod = float(det_cfg["base_pod"]) * (0.35 + 0.65 * contrast)
                pod *= np.clip(area / 8.0, 0.3, 1.0)
                if g.random() < pod:
                    detected = True
                    det_poly = jitter_polygon(truth_poly, g, float(det_cfg["boundary_iou_noise"]),
                                              truth.buffer_km)
                    if g.random() < float(det_cfg["filament_drop_prob"]):
                        det_poly = det_poly.buffer(-truth.buffer_km * 0.6).buffer(truth.buffer_km * 0.3)
                        partial = True
                        if det_poly.geom_type == "MultiPolygon":
                            det_poly = max(det_poly.geoms, key=lambda gg: gg.area)
                    if lookalikes and g.random() < float(det_cfg["lookalike_merge_prob"]):
                        nearest = min(lookalikes, key=lambda p: p.distance(det_poly))
                        if nearest.distance(det_poly) < 4.0:
                            det_poly = det_poly.union(nearest).convex_hull
                            merged = True
                    if det_poly.is_empty or det_poly.area <= 0:
                        detected = False
                        det_poly = None
            if detected and det_poly is not None:
                iou = safe_iou(det_poly, truth_poly)
                conf = float(np.clip(0.45 + 0.4 * contrast + 0.25 * iou
                                     - (0.15 if merged else 0) - (0.1 if partial else 0)
                                     + g.normal(0, 0.05), float(det_cfg["min_confidence"]), 0.99))

            det = Detection(event_id=ev.event_id, scene_id=scene_id, t_h=float(ot),
                            detected=detected, polygon_km=det_poly, f1_confidence=round(conf, 3),
                            lookalike_merged=merged, partial=partial)
            det_list.append(det)

            lon_c, lat_c = frame.to_lonlat(cx, cy)
            minlon, minlat = frame.to_lonlat(grid.x_min, grid.y_min)
            maxlon, maxlat = frame.to_lonlat(grid.x_max, grid.y_max)
            gt_major, gt_minor, gt_orient = oriented_extent(truth_poly) if oil_in_scene else (0, 0, 0)

            rows.append(dict(
                scene_id=scene_id,
                event_id=ev.event_id,
                tile_id=tile_id,
                acquisition_timestamp=cfg.iso(ot),
                sim_hours=round(float(ot), 3),
                latitude=round(float(lat_c), 6),
                longitude=round(float(lon_c), 6),
                bbox=f"{minlon:.5f},{minlat:.5f},{maxlon:.5f},{maxlat:.5f}",
                sensor=sat["sensor"],
                product_type=sat["product_type"],
                polarization="+".join(sat["polarizations"]),
                acquisition_mode=sat["acquisition_mode"],
                pixel_spacing_m=pix_m,
                scene_size_px=size_px,
                incidence_angle_deg=round(float(g.uniform(30.0, 45.0)), 2),
                image_path=str((img_dir / scene_id).with_suffix(".npy").relative_to(out_dir)) if fmt != "none" else "",
                mask_path=str((mask_dir / scene_id).with_suffix(".png").relative_to(out_dir)),
                quicklook_path=str((ql_dir / scene_id).with_suffix(".png").relative_to(out_dir)) if cfg["output"]["write_quicklook"] else "",
                mask_available=True,
                oil_present=bool(oil_in_scene),
                lookalike_present=bool(n_la > 0),
                ship_present=bool(ship_present),
                land_present=bool(land_present),
                pre_release_scene=bool(pre_release),
                true_oil_area_km2=round(float(truth_poly.area), 4) if oil_in_scene else 0.0,
                true_oil_major_km=round(float(gt_major), 3),
                true_oil_minor_km=round(float(gt_minor), 3),
                true_oil_orientation_deg=round(float(gt_orient), 2),
                f1_detected=bool(detected),
                f1_confidence=round(conf, 3),
                f1_lookalike_merged=bool(merged),
                f1_partial=bool(partial),
                wind_speed_ms=round(wind, 3),
                current_speed_ms=round(cur_speed, 4),
                contrast_factor=round(contrast, 3),
                ground_truth_source="simulation",
                label_confidence=round(float(np.clip(0.75 + 0.2 * contrast + g.normal(0, 0.04), 0.5, 0.99)), 3),
                data_quality_flag="nominal" if 2.5 <= wind <= 12.5 else "low_contrast",
                source_dataset="OceanGuard-Synth",
                license="CC-BY-4.0 (synthetic)",
                split=ev.split,
            ))

        detections[ev.event_id] = det_list

    return D1Result(scenes=pd.DataFrame(rows), detections=detections)


def _blob(cx, cy, r, g: np.random.Generator, n=14):
    ang = np.sort(g.uniform(0, 2 * np.pi, n))
    rad = r * (0.6 + 0.4 * g.uniform(0, 1, n))
    return np.column_stack([cx + rad * np.cos(ang), cy + rad * np.sin(ang)])
