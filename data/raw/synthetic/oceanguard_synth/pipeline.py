"""Orchestrate the full D1..D8 generation and write everything to disk."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pandas as pd

from .config import Config, load_config
from .d1_satellite import generate_d1
from .d2_temporal import generate_d2
from .d3_hindcast import generate_d3
from .d4_ais import generate_d4
from .d5_evidence import generate_d5
from .d6_ranking import generate_d6
from .d7_graph import generate_d7
from .d8_replay import generate_d8
from .environment import Environment
from .events import sample_events
from .geo import Frame
from .rng import RNG
from .spill_truth import simulate_truth
from .vessels import build_fleet


def _write(df: pd.DataFrame, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return {"file": str(path.name), "rows": int(len(df)), "columns": list(df.columns)}


def run(config_path: str | Path, out_dir: str | Path | None = None,
        overrides: dict | None = None) -> dict:
    cfg: Config = load_config(config_path)
    if overrides:
        for k, v in overrides.items():
            cfg[k] = v

    out = Path(out_dir) if out_dir else Path(cfg["output"]["dir"])
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    rng = RNG(int(cfg["seed"]))
    frame = Frame(float(cfg["aoi"]["ref_lat"]), float(cfg["aoi"]["ref_lon"]))
    env = Environment(cfg, rng)

    t0 = time.time()
    fleet = build_fleet(cfg, rng)
    events = sample_events(cfg, rng, fleet)
    truths = {ev.event_id: simulate_truth(cfg, rng, env, ev) for ev in events}

    manifest: dict = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "seed": int(cfg["seed"]), "n_events": len(events), "datasets": {}}

    # ground-truth events (the hidden answer key)
    gt = pd.DataFrame([dict(
        event_id=ev.event_id, split=ev.split, true_source_mmsi=ev.source_mmsi,
        true_origin_lat=round(frame.to_lonlat(ev.x0_km, ev.y0_km)[1].item(), 6),
        true_origin_lon=round(frame.to_lonlat(ev.x0_km, ev.y0_km)[0].item(), 6),
        true_origin_x_km=round(ev.x0_km, 4), true_origin_y_km=round(ev.y0_km, 4),
        true_release_timestamp=cfg.iso(ev.t0_h), true_release_sim_hours=round(ev.t0_h, 3),
        release_duration_h=round(ev.release_hours, 3),
    ) for ev in events])
    manifest["datasets"]["ground_truth_events"] = _write(gt, out / "ground_truth_events.csv")

    # D1
    d1 = generate_d1(cfg, rng, env, frame, events, truths, fleet, out)
    manifest["datasets"]["D1_satellite_scenes"] = _write(d1.scenes, out / "D1_satellite_scenes.csv")

    # D2
    d2_df, d2_states = generate_d2(cfg, frame, events, d1.detections)
    manifest["datasets"]["D2_temporal_states"] = _write(d2_df, out / "D2_temporal_states.csv")

    # D3
    d3 = generate_d3(cfg, rng, env, frame, events, d2_states, truths)
    manifest["datasets"]["D3_particles"] = _write(d3.particles, out / "D3_hindcast_particles.csv")
    manifest["datasets"]["D3_source_hypotheses"] = _write(d3.hypotheses, out / "D3_source_hypotheses.csv")

    # D4
    d4_raw, d4_tracks, candidates = generate_d4(cfg, rng, env, frame, events, fleet, d3, d2_states)
    manifest["datasets"]["D4_ais_raw"] = _write(d4_raw, out / "D4_ais_raw.csv")
    manifest["datasets"]["D4_tracks"] = _write(d4_tracks, out / "D4_vessel_tracks.csv")

    # D5
    d5_df, d5_tally = generate_d5(cfg, env, frame, events, d2_states, d3, d4_tracks, candidates)
    manifest["datasets"]["D5_evidence"] = _write(d5_df, out / "D5_evidence_consistency.csv")

    # D6
    d6_df = generate_d6(cfg, events, fleet, d1.scenes, d3, d4_tracks, d5_df, d5_tally, candidates)
    manifest["datasets"]["D6_ranking"] = _write(d6_df, out / "D6_evidence_ranking.csv")

    # D8 (before D7 so forecast nodes can be linked)
    d8_runs, d8_parts, d8_eval = generate_d8(cfg, rng, env, frame, events, d2_states)
    manifest["datasets"]["D8_forecast_runs"] = _write(d8_runs, out / "D8_forecast_runs.csv")
    manifest["datasets"]["D8_forecast_particles"] = _write(d8_parts, out / "D8_forecast_particles.csv")
    eval_dir = out / "evaluation_only"
    manifest["datasets"]["D8_evaluation"] = _write(d8_eval, eval_dir / "D8_evaluation.csv")
    manifest["datasets"]["D8_evaluation"]["note"] = "eval-only: contains future truth, never use for training"

    # D7
    d7_nodes, d7_edges = generate_d7(cfg, d2_df, d3.hypotheses, d4_tracks, d5_df, d8_runs)
    manifest["datasets"]["D7_graph_nodes"] = _write(d7_nodes, out / "D7_graph_nodes.csv")
    manifest["datasets"]["D7_graph_edges"] = _write(d7_edges, out / "D7_graph_edges.csv")

    # provenance / reproducibility
    shutil.copy(config_path, out / "config.used.yaml")
    manifest["elapsed_seconds"] = round(time.time() - t0, 1)
    manifest["scoring_hints"] = _scoring_hints(gt, d3, d6_df, d8_eval)
    with (out / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    _write_readme(out)
    return manifest


def _scoring_hints(gt: pd.DataFrame, d3, d6_df: pd.DataFrame,
                   d8_eval: pd.DataFrame) -> dict:
    hints: dict = {}
    if d3.hypotheses is not None and not d3.hypotheses.empty:
        best = d3.hypotheses[d3.hypotheses["ensemble_id"] == -1]
        hints["D3_median_source_error_km"] = round(
            float(best["qa_source_error_km"].median()), 3)
    if not d6_df.empty:
        top1 = d6_df[d6_df["rank"] == 1]
        hints["D6_top1_accuracy"] = round(float(top1["is_true_source"].mean()), 3)
        hints["D6_events_insufficient_evidence"] = int(
            top1["event_insufficient_evidence"].sum())
        hints["D6_events_scored"] = int(len(top1))
    if d8_eval is not None and not d8_eval.empty:
        hints["D8_median_trajectory_error_km"] = round(
            float(d8_eval["trajectory_error_km"].median()), 3)
        hints["D8_envelope_capture_rate"] = round(
            float(d8_eval["observed_centroid_in_envelope"].mean()), 3)
    return hints


def _write_readme(out: Path) -> None:
    (out / "OUTPUTS.md").write_text(
        "# Generated outputs\n\n"
        "See `manifest.json` for row counts and column lists, and the top-level\n"
        "`DATA_DICTIONARY.md` for field-by-field descriptions.\n\n"
        "Integrity rules enforced by the generator:\n\n"
        "1. `ground_truth_events.csv` is the answer key - do not join it into training features.\n"
        "2. Train/val/test in every dataset is assigned at **event** level (`split` column\n"
        "   on D1; propagate via `event_id`).\n"
        "3. D2 rows with `state_type` in {INTERPOLATED, PREDICTED} and D4 `is_observed=False`\n"
        "   rows are synthetic fill - never treat them as observations.\n"
        "4. `evaluation_only/D8_evaluation.csv` is the only place future observations appear;\n"
        "   it is for scoring forecasts, not for training them.\n"
        "5. D5 relation labels come from the fixed residual thresholds in `config.used.yaml`\n"
        "   (`evidence.support` / `evidence.contradict`).\n",
        encoding="utf-8")
