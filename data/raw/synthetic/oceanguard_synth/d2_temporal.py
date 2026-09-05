"""D2 - temporal reconstruction dataset.

One row per timestamped spill state for an event. OBSERVED rows come straight
from F1 detections. INTERPOLATED rows are inserted inside long gaps and PREDICTED
rows extrapolate past the last observation - both are synthesised ellipse
polygons and are explicitly flagged via ``state_type`` so a consumer never
mistakes them for real detections.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from .config import Config
from .d1_satellite import Detection
from .events import Event
from .geo import Frame, ellipse_polygon, oriented_extent, safe_iou, shape_descriptors


@dataclass
class D2State:
    event_id: str
    observation_id: str
    t_h: float
    polygon_km: Polygon
    centroid: np.ndarray
    area_km2: float
    state_type: str
    f1_confidence: float


def _state_from_polygon(poly: Polygon):
    major, minor, orient = oriented_extent(poly)
    desc = shape_descriptors(poly)
    c = poly.centroid
    return dict(
        area_km2=float(poly.area), perimeter_km=float(poly.length),
        centroid=np.array([c.x, c.y]), major_axis_km=major, minor_axis_km=minor,
        orientation_deg=orient, **desc,
    )


def generate_d2(cfg: Config, frame: Frame, events: list[Event],
                detections: dict[str, list[Detection]]):
    gap_hi = float(cfg["satellite"]["revisit_hours"]) * 1.5
    rows: list[dict] = []
    states: dict[str, list[D2State]] = {}

    for ev in events:
        dets = sorted(detections[ev.event_id], key=lambda d: d.t_h)
        observed = [d for d in dets if d.detected and d.polygon_km is not None
                    and not d.polygon_km.is_empty]
        ev_states: list[D2State] = []

        seq: list[tuple[str, float, Polygon, float]] = []
        for i, d in enumerate(observed):
            seq.append(("OBSERVED", d.t_h, d.polygon_km, d.f1_confidence))

        # interpolate inside gaps
        interp: list[tuple[str, float, Polygon, float]] = []
        for a, b in zip(observed, observed[1:]):
            gap = b.t_h - a.t_h
            if gap <= gap_hi:
                continue
            n_mid = int(min(2, gap // gap_hi))
            sa, sb = _state_from_polygon(a.polygon_km), _state_from_polygon(b.polygon_km)
            for m in range(1, n_mid + 1):
                f = m / (n_mid + 1)
                tc = a.t_h + f * gap
                cen = sa["centroid"] * (1 - f) + sb["centroid"] * f
                area = sa["area_km2"] * (1 - f) + sb["area_km2"] * f
                major = sa["major_axis_km"] * (1 - f) + sb["major_axis_km"] * f
                minor = sa["minor_axis_km"] * (1 - f) + sb["minor_axis_km"] * f
                orient = sa["orientation_deg"] * (1 - f) + sb["orientation_deg"] * f
                poly = ellipse_polygon(cen[0], cen[1], major or np.sqrt(area), minor or np.sqrt(area), orient)
                interp.append(("INTERPOLATED", tc, poly, 0.0))

        # predict past the last observation
        pred: list[tuple[str, float, Polygon, float]] = []
        if len(observed) >= 2:
            a, b = observed[-2], observed[-1]
            sa, sb = _state_from_polygon(a.polygon_km), _state_from_polygon(b.polygon_km)
            dt = max(b.t_h - a.t_h, 1e-3)
            vel = (sb["centroid"] - sa["centroid"]) / dt
            area_rate = (sb["area_km2"] - sa["area_km2"]) / dt
            step = float(cfg["satellite"]["revisit_hours"])
            for m in (1, 2):
                tc = b.t_h + m * step
                cen = sb["centroid"] + vel * (m * step)
                area = max(sb["area_km2"] + area_rate * (m * step), 0.5)
                major = sb["major_axis_km"] + (sb["major_axis_km"] - sa["major_axis_km"]) / dt * m * step
                minor = sb["minor_axis_km"] + (sb["minor_axis_km"] - sa["minor_axis_km"]) / dt * m * step
                poly = ellipse_polygon(cen[0], cen[1], max(major, np.sqrt(area)),
                                       max(minor, np.sqrt(area) * 0.5), sb["orientation_deg"])
                pred.append(("PREDICTED", tc, poly, 0.0))

        merged = sorted(seq + interp + pred, key=lambda r: r[1])
        prev_obs_state: dict | None = None
        prev_obs_id: str | None = None
        persistence = 0

        for j, (stype, t_h, poly, conf) in enumerate(merged):
            obs_id = f"{ev.event_id}-OBS{j:03d}"
            st = _state_from_polygon(poly)
            c = st["centroid"]
            lon, lat = frame.to_lonlat(c[0], c[1])

            if stype == "OBSERVED":
                persistence += 1
            iou = disp = area_chg = np.nan
            gap_h = np.nan
            if prev_obs_state is not None:
                iou = safe_iou(poly, prev_obs_state["poly"])
                disp = float(np.hypot(*(c - prev_obs_state["centroid"])))
                area_chg = 100.0 * (st["area_km2"] - prev_obs_state["area_km2"]) / max(prev_obs_state["area_km2"], 1e-6)
                gap_h = t_h - prev_obs_state["t_h"]

            minx, miny, maxx, maxy = poly.bounds if not poly.is_empty else (0, 0, 0, 0)
            blon0, blat0 = frame.to_lonlat(minx, miny)
            blon1, blat1 = frame.to_lonlat(maxx, maxy)

            rows.append(dict(
                event_id=ev.event_id,
                observation_id=obs_id,
                scene_id=(observed[[o.t_h for o in observed].index(t_h)].scene_id
                          if stype == "OBSERVED" else ""),
                timestamp=cfg.iso(t_h),
                sim_hours=round(t_h, 3),
                state_type=stype,
                polygon_wkt=frame.polygon_to_wkt(poly),
                area_km2=round(st["area_km2"], 4),
                perimeter_km=round(st["perimeter_km"], 4),
                centroid_lat=round(float(lat), 6),
                centroid_lon=round(float(lon), 6),
                bbox=f"{blon0:.5f},{blat0:.5f},{blon1:.5f},{blat1:.5f}",
                major_axis_km=round(st["major_axis_km"], 4),
                minor_axis_km=round(st["minor_axis_km"], 4),
                orientation_deg=round(st["orientation_deg"], 3),
                solidity=st["solidity"], eccentricity=st["eccentricity"],
                compactness=st["compactness"], convexity=st["convexity"],
                aspect_ratio=st["aspect_ratio"],
                previous_observation_id=prev_obs_id or "",
                polygon_iou=round(iou, 4) if iou == iou else np.nan,
                centroid_displacement_km=round(disp, 4) if disp == disp else np.nan,
                area_change_pct=round(area_chg, 3) if area_chg == area_chg else np.nan,
                persistence=persistence,
                observation_gap_hours=round(gap_h, 3) if gap_h == gap_h else np.nan,
                f1_confidence=round(conf, 3),
                data_quality="observed" if stype == "OBSERVED" else "synthetic",
                is_observed=bool(stype == "OBSERVED"),
            ))

            ev_states.append(D2State(ev.event_id, obs_id, t_h, poly, c,
                                     st["area_km2"], stype, conf))
            prev_obs_id = obs_id
            prev_obs_state = dict(poly=poly, centroid=c, area_km2=st["area_km2"], t_h=t_h)

        states[ev.event_id] = ev_states

    return pd.DataFrame(rows), states
