"""F8 orchestrator: forward forecasting, impact assessment and historical replay."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from shared.config.settings import get_settings
from shared.mocks.load_mock import load_mock
from shared.physics.lagrangian import Frame
from shared.schemas.f2_contract import TemporalSpillState
from shared.schemas.f8_contract import (
    ForecastEvaluation,
    ForecastParticle,
    ForecastRun,
    ImpactAssessment,
    LonLat,
)
from backend.f8_forecast.ensemble import (
    ForwardEnsembleConfig,
    ForwardEnsembleResult,
    run_forward_ensemble,
)
from backend.f8_forecast.forcing import (
    MissingForcingFallbackProvider,
    SyntheticForcingProvider,
)
from backend.f8_forecast.geometry import (
    cloud_to_polygon_km,
    epoch_hours,
    polygon_area_km2,
    polygon_km_to_geojson,
)
from backend.f8_forecast.impact import (
    beaching_risk,
    coast_distance_km,
    impact_area_candidates,
    zone_distance_km,
)
from backend.f8_forecast.replay import score_forecast
from backend.f8_forecast.repository import F8Repository, get_f8_repository


class F8ForecastSupervisor:
    """Coordinates the deterministic F8 pipeline stages."""

    def __init__(self, repository: Optional[F8Repository] = None):
        self.repo = repository or get_f8_repository()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _parse_states(raw: Sequence[Union[Dict[str, Any], TemporalSpillState]]) -> List[TemporalSpillState]:
        out: List[TemporalSpillState] = []
        for s in raw:
            out.append(s if isinstance(s, TemporalSpillState) else TemporalSpillState.model_validate(s))
        return out

    @staticmethod
    def _sim_h(state: TemporalSpillState) -> float:
        """Simulation-hours clock the synthetic forcing field is defined on.

        Falls back to epoch-hours for live states that carry no ``sim_hours``.
        """
        sh = getattr(state, "sim_hours", None)
        return float(sh) if sh is not None else epoch_hours(state.timestamp)

    @classmethod
    def _observed_sorted(cls, states: List[TemporalSpillState]) -> List[TemporalSpillState]:
        obs = [s for s in states if s.state_type == "OBSERVED" and s.is_observed]
        return sorted(obs, key=lambda s: epoch_hours(s.timestamp))

    def _load_states(self, event_id: str, states: Optional[Sequence[Any]]) -> List[TemporalSpillState]:
        raw = states if states is not None else load_mock("f2", event_id)
        parsed = self._parse_states(raw)
        if not parsed:
            raise ValueError(f"F8: no F2 temporal states available for {event_id}")
        return parsed

    @staticmethod
    def _frame_and_config(overrides: Optional[Dict[str, Any]] = None) -> Tuple[Frame, Dict[str, Any], ForwardEnsembleConfig]:
        cfg = get_settings().load_config_yaml()
        aoi = cfg.get("aoi", {})
        frame = Frame(ref_lat=float(aoi.get("ref_lat", 0.0)), ref_lon=float(aoi.get("ref_lon", 0.0)))
        fcfg = ForwardEnsembleConfig.from_dict(cfg, overrides=overrides)
        return frame, cfg, fcfg

    def _forcing(self, cfg: Dict[str, Any]) -> Tuple[Any, str]:
        try:
            return SyntheticForcingProvider(cfg), "nominal"
        except Exception:
            return MissingForcingFallbackProvider(), "forcing_unavailable"

    # ------------------------------------------------------------------ forecast
    def execute_forecast(
        self,
        event_id: str,
        *,
        t0_observation_index: Optional[int] = None,
        horizons_h: Optional[List[float]] = None,
        n_ensemble: Optional[int] = None,
        n_particles: Optional[int] = None,
        base_seed: int = 42,
        states: Optional[Sequence[Any]] = None,
        _allow_future_states: bool = False,
    ) -> Tuple[List[ForecastRun], List[ForecastParticle], List[ImpactAssessment]]:
        """Run the forward ensemble from a confirmed OBSERVED state.

        Only observations at or before T0 are used. ``execute_replay`` is the only
        method that inspects later observations.
        """
        parsed = self._load_states(event_id, states)
        observed = self._observed_sorted(parsed)
        if not observed:
            raise ValueError(f"F8: event {event_id} has no OBSERVED states to launch a forecast from")

        idx = t0_observation_index if t0_observation_index is not None else len(observed) - 1
        idx = max(0, min(idx, len(observed) - 1))
        t0 = observed[idx]
        t0_h = epoch_hours(t0.timestamp)

        # Guardrail: the forecast must not see the future.
        if not _allow_future_states:
            observed = [s for s in observed if epoch_hours(s.timestamp) <= t0_h + 1e-6]

        overrides = {
            "horizons_h": horizons_h,
            "n_ensemble": n_ensemble,
            "n_particles": n_particles,
        }
        frame, cfg, fcfg = self._frame_and_config(overrides)
        forcing_provider, dq_flag = self._forcing(cfg)
        if len([s for s in parsed if s.state_type == "OBSERVED" and s.is_observed]) == 1 and dq_flag == "nominal":
            dq_flag = "single_observation"

        forecast_id = f"{event_id}-FC{idx:02d}"
        seed_ring = t0.polygon_geojson.coordinates[0]

        ens: ForwardEnsembleResult = run_forward_ensemble(
            event_id=event_id,
            forecast_id=forecast_id,
            seed_polygon_lonlat=[[float(p[0]), float(p[1])] for p in seed_ring],
            t0_iso=t0.timestamp,
            t0_sim_h=self._sim_h(t0),
            frame=frame,
            forcing_provider=forcing_provider,
            config=fcfg,
            base_seed=base_seed,
        )

        runs, impacts = self._assemble_runs(event_id, forecast_id, t0, ens, frame, cfg, fcfg, dq_flag)
        particles = [ForecastParticle(**p) for p in ens.sampled_particles]

        self.repo.save_runs(event_id, runs)
        self.repo.save_particles(event_id, particles)
        self.repo.save_impact(event_id, impacts)
        # stash geometry for a subsequent replay call
        self._last_geometry = {
            "event_id": event_id, "forecast_id": forecast_id, "t0_iso": t0.timestamp,
            "frame": frame, "ens": ens, "cfg": cfg, "fcfg": fcfg,
        }
        return runs, particles, impacts

    def _assemble_runs(
        self, event_id, forecast_id, t0, ens: ForwardEnsembleResult, frame, cfg, fcfg, dq_flag,
    ) -> Tuple[List[ForecastRun], List[ImpactAssessment]]:
        runs: List[ForecastRun] = []
        impacts: List[ImpactAssessment] = []
        init_lonlat = frame.to_lonlat(*frame.to_km(t0.centroid.lon, t0.centroid.lat))
        for hr in ens.horizons:
            h = hr.horizon_h
            pred_poly = cloud_to_polygon_km(hr.pooled_cloud_km, fcfg.slick_buffer_km)
            env_buf = max(2.0, hr.spread_km)
            env_poly = cloud_to_polygon_km(hr.pooled_cloud_km, env_buf, keep_largest=False)
            cx, cy = float(hr.mean_centroid_km[0]), float(hr.mean_centroid_km[1])
            lon_c, lat_c = frame.to_lonlat(cx, cy)
            coast_d = coast_distance_km(cfg, cx, cy)
            zone_d, zone_name = zone_distance_km(cfg, cx, cy)
            risk = beaching_risk(coast_d, hr.spread_km)
            conf = float(math.exp(-hr.spread_km / 15.0) * math.exp(-h / 96.0))
            valid_ts = _iso_add_hours(t0.timestamp, h)

            runs.append(ForecastRun(
                event_id=event_id,
                forecast_id=forecast_id,
                initial_observation_id=t0.observation_id,
                initial_timestamp=t0.timestamp,
                initial_centroid=LonLat(lat=float(t0.centroid.lat), lon=float(t0.centroid.lon)),
                initial_area_km2=round(float(t0.area_km2), 4),
                forecast_horizon_hours=h,
                valid_timestamp=valid_ts,
                n_ensemble=ens.n_ensemble,
                predicted_centroid=LonLat(lat=round(float(lat_c), 6), lon=round(float(lon_c), 6)),
                predicted_polygon_geojson=polygon_km_to_geojson(pred_poly, frame),
                predicted_area_km2=round(polygon_area_km2(pred_poly), 4),
                forecast_envelope_geojson=polygon_km_to_geojson(env_poly, frame),
                forecast_envelope_area_km2=round(polygon_area_km2(env_poly), 4),
                ensemble_spread_km=round(float(hr.spread_km), 4),
                forecast_confidence=round(min(max(conf, 0.0), 1.0), 4),
                coastline_distance_km=round(float(coast_d), 3),
                nearest_sensitive_zone=zone_name,
                sensitive_zone_distance_km=None if zone_d is None else round(float(zone_d), 3),
                beaching_risk=risk,
                data_quality_flag=dq_flag,
            ))

            impacts.append(ImpactAssessment(
                event_id=event_id,
                forecast_id=forecast_id,
                forecast_horizon_hours=h,
                valid_timestamp=valid_ts,
                predicted_centroid=LonLat(lat=round(float(lat_c), 6), lon=round(float(lon_c), 6)),
                coastline_distance_km=round(float(coast_d), 3),
                beaching_risk=risk,
                nearest_sensitive_zone=zone_name,
                sensitive_zone_distance_km=None if zone_d is None else round(float(zone_d), 3),
                impact_area_candidates=impact_area_candidates(cfg, frame, env_poly, coast_d, hr.spread_km),
            ))
        return runs, impacts

    # ------------------------------------------------------------------ replay
    def execute_replay(
        self,
        event_id: str,
        *,
        t0_observation_index: Optional[int] = None,
        horizons_h: Optional[List[float]] = None,
        n_ensemble: Optional[int] = None,
        n_particles: Optional[int] = None,
        base_seed: int = 42,
        states: Optional[Sequence[Any]] = None,
    ) -> Tuple[List[ForecastRun], List[ForecastEvaluation]]:
        """Forward-forecast from an *early* confirmed state, then score every horizon
        against the nearest later OBSERVED state (eval-only)."""
        parsed = self._load_states(event_id, states)
        observed = self._observed_sorted(parsed)
        cfg_all = get_settings().load_config_yaml()
        rp = cfg_all.get("replay", {}) or {}
        if len(observed) < int(rp.get("min_observations", 2)):
            return [], []

        if t0_observation_index is None:
            t0_observation_index = min(int(rp.get("t0_observation_index", 2)), len(observed) - 2)
            t0_observation_index = max(0, t0_observation_index)

        runs, _particles, _impacts = self.execute_forecast(
            event_id,
            t0_observation_index=t0_observation_index,
            horizons_h=horizons_h,
            n_ensemble=n_ensemble,
            n_particles=n_particles,
            base_seed=base_seed,
            states=parsed,
        )

        g = self._last_geometry
        frame = g["frame"]
        ens: ForwardEnsembleResult = g["ens"]
        fcfg = g["fcfg"]
        env_polys, pred_polys, pred_cens, spreads = {}, {}, {}, {}
        for hr in ens.horizons:
            env_polys[hr.horizon_h] = cloud_to_polygon_km(
                hr.pooled_cloud_km, max(2.0, hr.spread_km), keep_largest=False
            )
            pred_polys[hr.horizon_h] = cloud_to_polygon_km(hr.pooled_cloud_km, fcfg.slick_buffer_km)
            pred_cens[hr.horizon_h] = hr.mean_centroid_km
            spreads[hr.horizon_h] = hr.spread_km

        evals = score_forecast(
            runs=runs,
            envelope_polys_km=env_polys,
            predicted_polys_km=pred_polys,
            predicted_centroids_km=pred_cens,
            spreads_km=spreads,
            t0_sim_h=ens.t0_sim_h,
            later_observed=observed,
            frame=frame,
            match_tolerance_h=float(rp.get("match_tolerance_h", 12.0)),
        )
        self.repo.save_evaluations(event_id, evals)
        return runs, evals

    # ------------------------------------------------------------------ getters
    def get_runs(self, event_id: str) -> List[ForecastRun]:
        runs = self.repo.get_runs(event_id)
        if not runs:
            runs, _, _ = self.execute_forecast(event_id)
        return runs

    def get_particles(self, event_id: str) -> List[ForecastParticle]:
        if not self.repo.get_particles(event_id):
            self.execute_forecast(event_id)
        return self.repo.get_particles(event_id)

    def get_impact(self, event_id: str) -> List[ImpactAssessment]:
        if not self.repo.get_impact(event_id):
            self.execute_forecast(event_id)
        return self.repo.get_impact(event_id)


def _iso_add_hours(ts_iso: str, hours: float) -> str:
    from datetime import datetime, timedelta, timezone

    dt = datetime.fromisoformat(str(ts_iso).replace("Z", "+00:00"))
    return (dt + timedelta(hours=float(hours))).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
