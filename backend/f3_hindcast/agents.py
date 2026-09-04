"""Specialist deterministic agents for F3 Hindcast orchestration."""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple, Union
import numpy as np

from shared.physics.lagrangian import Frame
from shared.schemas.f2_contract import TemporalSpillState
from shared.schemas.f3_contract import (
    EnvironmentalStateSnapshot,
    SourceHypothesisWindow,
    SourceLocationCoord,
)
from backend.f3_hindcast.adapter import F2StateAdapter
from backend.f3_hindcast.ensemble import (
    EnsembleConfig,
    EnsembleRunResult,
    run_hindcast_ensemble,
)
from backend.f3_hindcast.forcing import ForcingProvider
from backend.f3_hindcast.inference import infer_source_hypotheses


class StateValidationAgent:
    """Agent responsible for validating F2 temporal states and enforcing observed-only seeding."""

    def process(
        self,
        raw_states: Sequence[Union[Dict[str, Any], TemporalSpillState]]
    ) -> Tuple[List[TemporalSpillState], Dict[str, Any]]:
        """Parses, validates, and filters temporal states."""
        return F2StateAdapter.prepare_seed_sequence(raw_states)


class ForcingAgent:
    """Agent responsible for obtaining and checking environmental forcing."""

    def capture_snapshot(
        self,
        forcing_provider: ForcingProvider,
        event_id: str,
        lat: float,
        lon: float,
        timestamp: str
    ) -> EnvironmentalStateSnapshot:
        """Captures an environmental state snapshot for audit provenance."""
        lons = np.array([lon])
        lats = np.array([lat])
        t_h = 0.0  # Epoch offset or nominal
        uc, vc, uw, vw = forcing_provider.get_forcing(lons, lats, t_h)

        wind_speed = float(np.hypot(uw[0], vw[0]))
        curr_speed = float(np.hypot(uc[0], vc[0]))

        return EnvironmentalStateSnapshot(
            env_state_id=f"ENV_{event_id}_00",
            event_id=event_id,
            timestamp=timestamp,
            location=SourceLocationCoord(lat=lat, lon=lon),
            wind_speed_ms=round(wind_speed, 2),
            current_speed_ms=round(curr_speed, 3),
            source=forcing_provider.source_name,
        )


class HindcastPhysicsAgent:
    """Agent executing numerical Lagrangian particle tracking."""

    def run_ensemble(
        self,
        seed_states: List[TemporalSpillState],
        forcing_provider: ForcingProvider,
        frame: Frame,
        config: EnsembleConfig,
        base_seed: int = 42
    ) -> EnsembleRunResult:
        """Runs backward Lagrangian ensemble."""
        return run_hindcast_ensemble(
            seed_states=seed_states,
            forcing_provider=forcing_provider,
            frame=frame,
            config=config,
            base_seed=base_seed
        )


class SourceInferenceAgent:
    """Agent calculating source regions, centroids, and uncertainty bounds."""

    def infer(
        self,
        ensemble_result: EnsembleRunResult,
        seed_states: List[TemporalSpillState],
        frame: Frame,
        config: EnsembleConfig,
        data_quality_flag: str = "nominal"
    ) -> List[SourceHypothesisWindow]:
        """Clusters particles and derives candidate hypotheses."""
        return infer_source_hypotheses(
            ensemble_result=ensemble_result,
            seed_states=seed_states,
            frame=frame,
            config=config,
            data_quality_flag=data_quality_flag
        )


class ProvenanceContractAgent:
    """Agent verifying that all hypotheses strictly conform to public contracts and provenance standards."""

    def verify_and_seal(
        self,
        hypotheses: List[SourceHypothesisWindow],
        event_id: str
    ) -> None:
        """Validates that hypotheses follow frozen standards."""
        if not hypotheses:
            raise ValueError(f"Provenance verification failed: empty hypotheses list for {event_id}")

        has_hbest = False
        for h in hypotheses:
            if h.event_id != event_id:
                raise ValueError(f"Hypothesis {h.source_hypothesis_id} event_id mismatch: {h.event_id} != {event_id}")
            if h.uncertainty_radius_km < 0.0:
                raise ValueError(f"Negative uncertainty radius on {h.source_hypothesis_id}")
            if h.source_hypothesis_id.endswith("_HBEST"):
                has_hbest = True
                if h.ensemble_id != -1:
                    raise ValueError(f"HBEST hypothesis must have ensemble_id == -1, got {h.ensemble_id}")
                if h.source_probability != 1.0:
                    raise ValueError(f"HBEST hypothesis must have source_probability == 1.0, got {h.source_probability}")

        if not has_hbest:
            raise ValueError(f"Missing mandatory pooled best hypothesis (SH_{event_id}_HBEST)")
