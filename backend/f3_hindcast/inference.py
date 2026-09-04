"""Source Hypothesis Inference and Uncertainty Quantification for F3.

Extracts candidate source centroids, RMS dispersion, origin time windows,
and normalized probabilities from Lagrangian ensemble clouds.
Constructs the pooled best estimate (HBEST).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
import numpy as np

from shared.physics.lagrangian import Frame
from shared.schemas.f2_contract import TemporalSpillState
from shared.schemas.f3_contract import SourceHypothesisWindow, SourceLocationCoord
from backend.f3_hindcast.ensemble import EnsembleConfig, EnsembleRunResult


def epoch_hours_to_iso(epoch_h: float) -> str:
    """Converts epoch hours to UTC ISO-8601 string."""
    dt = datetime.fromtimestamp(epoch_h * 3600.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def infer_source_hypotheses(
    ensemble_result: EnsembleRunResult,
    seed_states: List[TemporalSpillState],
    frame: Frame,
    config: EnsembleConfig,
    data_quality_flag: str = "nominal"
) -> List[SourceHypothesisWindow]:
    """Infers SourceHypothesisWindow instances from Lagrangian ensemble clouds.

    Produces:
    - N ensemble candidate hypotheses (SH_<event_id>_<k:02d>)
    - 1 pooled best hypothesis (SH_<event_id>_HBEST) with ensemble spread uncertainty
    """
    event_id = seed_states[0].event_id
    seed_ids = [s.observation_id for s in seed_states]
    half_h = config.origin_window_half_h

    hypotheses: List[SourceHypothesisWindow] = []
    ens_centroids: List[np.ndarray] = []
    ens_spreads: List[float] = []

    # 1. Evaluate each ensemble member
    for ens_id in sorted(ensemble_result.clouds.keys()):
        cloud = ensemble_result.clouds[ens_id]
        t_rel_h = ensemble_result.release_times_h[ens_id]
        params = ensemble_result.params_used[ens_id]

        cen = np.mean(cloud, axis=0)
        ens_centroids.append(cen)

        # RMS spread: sqrt( mean( ||p - cen||^2 ) )
        spread_km = float(np.sqrt(np.mean(np.sum((cloud - cen) ** 2, axis=1))))

        # If forcing was unavailable, expand uncertainty radius to a safe wide default
        if data_quality_flag == "forcing_unavailable":
            spread_km = max(spread_km, 50.0)

        ens_spreads.append(spread_km)

        lon_c, lat_c = frame.to_lonlat(cen[0], cen[1])
        t_start_iso = epoch_hours_to_iso(t_rel_h - half_h)
        t_end_iso = epoch_hours_to_iso(t_rel_h + half_h)
        t_mid_iso = epoch_hours_to_iso(t_rel_h)

        backtracked_h = max(0.0, ensemble_result.t_obs_first_h - t_rel_h)

        hyp = SourceHypothesisWindow(
            source_hypothesis_id=f"SH_{event_id}_{ens_id:02d}",
            event_id=event_id,
            source_location=SourceLocationCoord(
                lat=round(float(lat_c), 6),
                lon=round(float(lon_c), 6),
            ),
            origin_time_start=t_start_iso,
            origin_time_end=t_end_iso,
            uncertainty_radius_km=round(spread_km, 3),
            source_probability=1.0,  # Will normalize below
            ensemble_id=ens_id,
            seed_state_ids=seed_ids,
            origin_time_mid=t_mid_iso,
            backtracked_hours=round(float(backtracked_h), 3),
            wind_drift_factor=round(float(params.wind_drift_factor), 5),
            diffusion_m2s=round(float(params.diffusion_m2s), 3),
            data_quality_flag=data_quality_flag,
        )
        hypotheses.append(hyp)

    # 2. Normalize probabilities for ensemble members (inversely proportional to uncertainty)
    if hypotheses:
        inv_spreads = np.array([1.0 / max(h.uncertainty_radius_km, 0.01) for h in hypotheses])
        norm_probs = inv_spreads / np.sum(inv_spreads)
        for h, p in zip(hypotheses, norm_probs):
            h.source_probability = round(float(p), 4)

    # 3. Construct pooled best hypothesis (SH_<event_id>_HBEST)
    det_cloud = ensemble_result.clouds[0]
    det_cen = ens_centroids[0]
    det_spread = ens_spreads[0]
    t_rel_best_h = ensemble_result.release_times_h[0]

    # Uncertainty combines deterministic spread and disagreement across ensembles
    centroids_arr = np.array(ens_centroids)
    disagreement_spread = float(np.sqrt(np.mean(np.sum((centroids_arr - np.mean(centroids_arr, axis=0)) ** 2, axis=1))))
    hbest_spread = float(max(det_spread, disagreement_spread))

    if data_quality_flag == "forcing_unavailable":
        hbest_spread = max(hbest_spread, 50.0)

    lon_best, lat_best = frame.to_lonlat(det_cen[0], det_cen[1])
    best_start_iso = epoch_hours_to_iso(t_rel_best_h - half_h)
    best_end_iso = epoch_hours_to_iso(t_rel_best_h + half_h)
    best_mid_iso = epoch_hours_to_iso(t_rel_best_h)
    best_backtracked_h = max(0.0, ensemble_result.t_obs_first_h - t_rel_best_h)

    best_hyp = SourceHypothesisWindow(
        source_hypothesis_id=f"SH_{event_id}_HBEST",
        event_id=event_id,
        source_location=SourceLocationCoord(
            lat=round(float(lat_best), 6),
            lon=round(float(lon_best), 6),
        ),
        origin_time_start=best_start_iso,
        origin_time_end=best_end_iso,
        uncertainty_radius_km=round(hbest_spread, 3),
        source_probability=1.0,
        ensemble_id=-1,
        seed_state_ids=seed_ids,
        origin_time_mid=best_mid_iso,
        backtracked_hours=round(float(best_backtracked_h), 3),
        wind_drift_factor=round(float(config.wind_drift_factor_base), 5),
        diffusion_m2s=round(float(config.diffusion_m2s_base), 3),
        data_quality_flag=data_quality_flag,
    )

    hypotheses.append(best_hyp)
    return hypotheses
