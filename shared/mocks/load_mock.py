"""Shared mock data loader.

Three entry points over the one canonical synthetic dataset
(``data/raw/synthetic/outputs/``):

* ``load_mock(feature, event_id)``      -> list of pydantic-validated dicts for
  ``f2`` / ``f3`` / ``f4`` (F3, F4 consumers). Unchanged historical behaviour.
* ``load_mock_rows(feature, event_id)`` -> ``{"feature", "event_id", "rows": [...]}``
  of lightly type-coerced raw CSV rows (F5 consumer + generic use).
* ``load_mock_df(key, event_id)``       -> ``pandas.DataFrame`` of the raw CSV
  (F6, F7 consumers). Accepts feature codes *and* F7 table-name aliases.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from shared.config.settings import get_settings
from shared.schemas.f2_contract import CentroidCoord, GeoJSONPolygon, TemporalSpillState
from shared.schemas.f3_contract import SourceHypothesisWindow, SourceLocationCoord
from shared.schemas.f4_contract import CandidateVessel


def wkt_polygon_to_geojson(wkt: str) -> Dict[str, Any]:
    """Converts a WKT POLYGON string to a GeoJSON Polygon coordinates structure."""
    raw_rings = re.findall(r"\(([^()]+)\)", wkt)
    coordinates: List[List[List[float]]] = []
    for ring_str in raw_rings:
        ring_pts: List[List[float]] = []
        for pair in ring_str.strip().split(","):
            parts = pair.strip().split()
            if len(parts) >= 2:
                ring_pts.append([float(parts[0]), float(parts[1])])
        if len(ring_pts) >= 3:
            # Ensure closed ring
            if ring_pts[0] != ring_pts[-1]:
                ring_pts.append(ring_pts[0])
            coordinates.append(ring_pts)
    if not coordinates:
        raise ValueError(f"Could not parse valid polygon coordinates from WKT: {wkt[:50]}")
    return {"type": "Polygon", "coordinates": coordinates}


def _load_f2_mock(event_id: str) -> List[Dict[str, Any]]:
    """Loads F2 temporal states for the given event_id, validated as TemporalSpillState."""
    settings = get_settings()
    csv_path = settings.D2_CSV_PATH
    if not csv_path.exists():
        raise FileNotFoundError(f"D2 temporal states CSV not found at {csv_path}")

    results: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["event_id"] != event_id:
                continue

            raw_obs = row["observation_id"]
            if "-OBS" in raw_obs:
                parts = raw_obs.split("-OBS")
                norm_obs = f"OBS_{parts[0]}_{parts[1]}"
            else:
                norm_obs = raw_obs

            geo = wkt_polygon_to_geojson(row["polygon_wkt"])
            centroid = {
                "lat": float(row["centroid_lat"]),
                "lon": float(row["centroid_lon"]),
            }
            state_data: Dict[str, Any] = {
                "observation_id": norm_obs,
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "state_type": row["state_type"],
                "polygon_geojson": geo,
                "area_km2": float(row["area_km2"]),
                "centroid": centroid,
                "is_observed": row["is_observed"].strip().lower() == "true",
            }
            # Optional attributes
            for k in [
                "scene_id", "bbox", "data_quality", "previous_observation_id"
            ]:
                if row.get(k):
                    state_data[k] = row[k]
            for fk in [
                "sim_hours", "perimeter_km", "major_axis_km", "minor_axis_km",
                "orientation_deg", "solidity", "eccentricity", "compactness",
                "convexity", "aspect_ratio", "polygon_iou", "centroid_displacement_km",
                "area_change_pct", "observation_gap_hours", "f1_confidence"
            ]:
                if row.get(fk) is not None and row[fk] != "":
                    state_data[fk] = float(row[fk])
            if row.get("persistence") is not None and row["persistence"] != "":
                state_data["persistence"] = int(row["persistence"])

            # Validate against Pydantic contract
            validated = TemporalSpillState.model_validate(state_data)
            results.append(validated.model_dump())

    return results


def _load_f3_mock(event_id: str) -> List[Dict[str, Any]]:
    """Loads F3 source hypotheses for the given event_id, validated as SourceHypothesisWindow."""
    settings = get_settings()
    csv_path = settings.D3_SOURCE_HYPOTHESES_CSV_PATH
    if not csv_path.exists():
        raise FileNotFoundError(f"D3 source hypotheses CSV not found at {csv_path}")

    results: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["event_id"] != event_id:
                continue

            # Normalize historical ID to frozen contract format:
            # e.g. EVT0001-H00 -> SH_EVT0001_00, EVT0001-HBEST -> SH_EVT0001_HBEST
            raw_hid = row["source_hypothesis_id"]
            if "-HBEST" in raw_hid:
                norm_hid = f"SH_{event_id}_HBEST"
                ens_id = -1
            else:
                ens_id_str = row["ensemble_id"]
                ens_id = int(ens_id_str)
                norm_hid = f"SH_{event_id}_{ens_id:02d}"

            source_loc = {
                "lat": float(row["source_lat"]),
                "lon": float(row["source_lon"]),
            }
            seed_ids = [s.strip() for s in row.get("seed_state_ids", "").split(";") if s.strip()]

            hyp_data: Dict[str, Any] = {
                "source_hypothesis_id": norm_hid,
                "event_id": row["event_id"],
                "source_location": source_loc,
                "origin_time_start": row["origin_time_start"],
                "origin_time_end": row["origin_time_end"],
                "uncertainty_radius_km": float(row["uncertainty_radius_km"]),
                "source_probability": float(row.get("source_probability", 1.0)),
                "ensemble_id": ens_id,
                "seed_state_ids": seed_ids,
                "origin_time_mid": row.get("origin_time_mid"),
                "backtracked_hours": float(row["backtracked_hours"]) if row.get("backtracked_hours") else None,
                "wind_drift_factor": float(row["wind_drift_factor"]) if row.get("wind_drift_factor") else None,
                "diffusion_m2s": float(row["diffusion_m2s"]) if row.get("diffusion_m2s") else None,
                "data_quality_flag": "nominal",
            }

            validated = SourceHypothesisWindow.model_validate(hyp_data)
            results.append(validated.model_dump())

    return results


def _load_f4_mock(event_id: str) -> List[Dict[str, Any]]:
    """Loads F4 candidate vessels for the given event_id, validated as CandidateVessel.

    Strictly quarantines QA fields (such as is_true_source).
    """
    settings = get_settings()
    csv_path = settings.D4_VESSEL_TRACKS_CSV_PATH
    if not csv_path.exists():
        raise FileNotFoundError(f"D4 vessel tracks CSV not found at {csv_path}")

    results: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["event_id"] != event_id:
                continue

            track_data: Dict[str, Any] = {
                "track_id": f"TRK_{event_id}_{row['mmsi']}",
                "event_id": row["event_id"],
                "mmsi": row["mmsi"],
                "source_hypothesis_id": f"SH_{event_id}_HBEST",
                "distance_to_source_effective_km": float(row["distance_to_source_effective_km"]),
                "temporal_compatibility": float(row["temporal_compatibility"]),
                "track_overlap": float(row["track_overlap"]),
                "track_completeness": float(row["track_completeness"]),
                "dark_gap_over_source": row["dark_gap_over_source"].strip().lower() == "true",
                "dark_gap_over_source_hours": float(row.get("dark_gap_over_source_hours", 0.0)),
                "closest_approach_is_interpolated": row["closest_approach_is_interpolated"].strip().lower() == "true",
                "speed_compatibility": float(row.get("speed_compatibility", 0.5)),
                "course_compatibility": float(row.get("course_compatibility", 0.5)),
                "ais_gap_ratio_origin_window": float(row.get("ais_gap_ratio_origin_window", 1.0)),
                # Provenance / audit fields
                "vessel_type": row.get("vessel_type"),
                "vessel_length": float(row["vessel_length"]) if row.get("vessel_length") else None,
                "vessel_width": float(row["vessel_width"]) if row.get("vessel_width") else None,
                "draught": float(row["draught"]) if row.get("draught") else None,
                "first_timestamp": row.get("first_timestamp") or None,
                "last_timestamp": row.get("last_timestamp") or None,
                "track_duration_h": float(row["track_duration_h"]) if row.get("track_duration_h") else None,
                "number_of_observations": int(row["number_of_observations"]) if row.get("number_of_observations") else None,
                "gap_count": int(row["gap_count"]) if row.get("gap_count") else None,
                "max_gap_hours": float(row["max_gap_hours"]) if row.get("max_gap_hours") else None,
                "distance_to_source_km": float(row["distance_to_source_km"]) if row.get("distance_to_source_km") else None,
                "distance_to_source_interpolated_km": float(row["distance_to_source_interpolated_km"]) if row.get("distance_to_source_interpolated_km") else None,
                "closest_approach_timestamp": row.get("closest_approach_timestamp") or None,
                "interpolated_closest_timestamp": row.get("interpolated_closest_timestamp") or None,
                "observed_speed_kn": float(row["observed_speed_kn"]) if row.get("observed_speed_kn") else None,
                "observed_course_deg": float(row["observed_course_deg"]) if row.get("observed_course_deg") else None,
                "slick_drift_speed_kn": float(row["slick_drift_speed_kn"]) if row.get("slick_drift_speed_kn") else None,
                "slick_drift_course_deg": float(row["slick_drift_course_deg"]) if row.get("slick_drift_course_deg") else None,
            }
            validated = CandidateVessel.model_validate(track_data)
            results.append(validated.model_dump())

    return results


def load_mock(feature: str, event_id: str) -> List[Dict[str, Any]]:
    """Generic shared mock loader.

    Args:
        feature: 'f2', 'f3', or 'f4'
        event_id: Event ID string, e.g. 'EVT0001'

    Returns:
        List of dictionaries validated against the appropriate feature contract.
    """
    key = feature.lower().strip()
    if key == "f2":
        return _load_f2_mock(event_id)
    elif key == "f3":
        return _load_f3_mock(event_id)
    elif key == "f4":
        return _load_f4_mock(event_id)
    else:
        raise ValueError(f"Unknown mock feature '{feature}'. Supported: 'f2', 'f3', 'f4'")


# --------------------------------------------------------------------------- #
# Raw-row / DataFrame loaders (F5 / F6 / F7)
# --------------------------------------------------------------------------- #

# Feature code + F7 table-name alias -> CSV file (relative to RAW_SYNTHETIC_DIR).
_MOCK_FILES: Dict[str, str] = {
    "f1": "D1_satellite_scenes.csv",
    "f2": "D2_temporal_states.csv",
    "f3": "D3_source_hypotheses.csv",
    "f4": "D4_vessel_tracks.csv",
    "f5": "D5_evidence_consistency.csv",
    "f6": "D6_evidence_ranking.csv",
    "f7_nodes": "D7_graph_nodes.csv",
    "f7_edges": "D7_graph_edges.csv",
    "f8": "D8_forecast_runs.csv",
    "f8_particles": "D8_forecast_particles.csv",
    "f8_eval": "evaluation_only/D8_evaluation.csv",
    # F7 GraphBuilder / db.py logical table names
    "spill_observations": "D1_satellite_scenes.csv",
    "temporal_states": "D2_temporal_states.csv",
    "source_hypotheses": "D3_source_hypotheses.csv",
    "hindcast_particles": "D3_hindcast_particles.csv",
    "vessel_tracks": "D4_vessel_tracks.csv",
    "ais_raw": "D4_ais_raw.csv",
    "evidence_items": "D5_evidence_consistency.csv",
    "hypothesis_scores": "D6_evidence_ranking.csv",
    "graph_nodes": "D7_graph_nodes.csv",
    "graph_edges": "D7_graph_edges.csv",
    "forecasts": "D8_forecast_runs.csv",
    "forecast_particles": "D8_forecast_particles.csv",
    "forecast_evaluation": "evaluation_only/D8_evaluation.csv",
    "ground_truth": "ground_truth_events.csv",
}

_TRUE = {"true", "t", "yes", "1"}
_FALSE = {"false", "f", "no", "0"}


def _coerce(value: Any) -> Any:
    """Best-effort scalar typing: '' -> None, bool-ish -> bool, numeric -> int/float."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    low = s.lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def _resolve_mock_file(key: str) -> Path:
    k = key.strip().lower()
    if k not in _MOCK_FILES:
        # allow bare "f7" -> nodes for convenience
        if k == "f7":
            k = "f7_nodes"
        else:
            raise KeyError(
                f"unknown mock key {key!r}; expected one of {sorted(_MOCK_FILES)}"
            )
    return get_settings().RAW_SYNTHETIC_DIR / _MOCK_FILES[k]


def load_mock_rows(feature: str, event_id: Optional[str] = None) -> Dict[str, Any]:
    """Return ``{"feature", "event_id", "rows": [dict, ...]}`` of coerced raw CSV rows."""
    path = _resolve_mock_file(feature)
    if not path.exists():
        raise FileNotFoundError(f"mock data file missing: {path}")

    rows: List[Dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            row = {k: _coerce(v) for k, v in raw.items()}
            if event_id is not None and row.get("event_id") != event_id:
                continue
            rows.append(row)
    return {"feature": feature.strip().lower(), "event_id": event_id, "rows": rows}


def _find_data_root() -> Path:
    """Canonical synthetic dataset directory (``data/raw/synthetic/outputs``)."""
    return get_settings().RAW_SYNTHETIC_DIR


def load_mock_df(key: str, event_id: Optional[str] = None, data_root: Optional[Path] = None):
    """Return a ``pandas.DataFrame`` of the mapped CSV, optionally filtered to one event.

    ``data_root`` overrides the canonical dataset directory (used by F7 tests).
    Missing file -> empty DataFrame (graceful degradation, matching F7's contract).
    """
    import pandas as pd

    rel = _MOCK_FILES.get(key.strip().lower())
    if rel is None and key.strip().lower() == "f7":
        rel = _MOCK_FILES["f7_nodes"]
    if rel is None:
        raise KeyError(f"unknown mock key {key!r}; expected one of {sorted(_MOCK_FILES)}")

    path = (Path(data_root) / rel) if data_root is not None else _resolve_mock_file(key)
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path, low_memory=False)
    if event_id is not None and "event_id" in df.columns:
        df = df[df["event_id"] == event_id].reset_index(drop=True)

    # ``f3`` is the *F3 result* (pooled best estimate). The raw D3 table is still
    # reachable via the ``source_hypotheses`` alias, which F7 uses to build a node
    # per ensemble member.
    if key.strip().lower() == "f3" and event_id is not None and "ensemble_id" in df.columns:
        hbest = df[df["ensemble_id"] == -1]
        if not hbest.empty:
            df = hbest.reset_index(drop=True)
    return df


def list_events(feature: str = "f4") -> List[str]:
    """Sorted unique ``event_id`` values available for a feature/table."""
    df = load_mock_df(feature)
    if "event_id" not in getattr(df, "columns", []):
        return []
    return sorted(df["event_id"].dropna().unique().tolist())
