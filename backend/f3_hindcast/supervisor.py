"""Supervisor orchestrator for F3 Environmental Drift & Backward Hindcasting."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from shared.config.settings import get_settings
from shared.mocks.load_mock import load_mock
from shared.physics.lagrangian import Frame
from shared.schemas.f2_contract import TemporalSpillState
from shared.schemas.f3_contract import (
    EnvironmentalStateSnapshot,
    SourceHypothesisWindow,
)
from backend.f3_hindcast.agents import (
    ForcingAgent,
    HindcastPhysicsAgent,
    ProvenanceContractAgent,
    SourceInferenceAgent,
    StateValidationAgent,
)
from backend.f3_hindcast.ensemble import EnsembleConfig
from backend.f3_hindcast.forcing import (
    ForcingProvider,
    MissingForcingFallbackProvider,
    SyntheticForcingProvider,
)
from backend.f3_hindcast.repository import F3Repository, get_f3_repository


class F3HindcastSupervisor:
    """Orchestrator coordinating deterministic specialist agents for F3."""

    def __init__(self, repository: Optional[F3Repository] = None):
        self.repo = repository or get_f3_repository()
        self.validation_agent = StateValidationAgent()
        self.forcing_agent = ForcingAgent()
        self.physics_agent = HindcastPhysicsAgent()
        self.inference_agent = SourceInferenceAgent()
        self.provenance_agent = ProvenanceContractAgent()

    def execute_hindcast(
        self,
        event_id: str,
        states: Optional[Sequence[Union[Dict[str, Any], TemporalSpillState]]] = None,
        forcing_provider: Optional[ForcingProvider] = None,
        config: Optional[EnsembleConfig] = None,
        base_seed: int = 42
    ) -> Tuple[List[SourceHypothesisWindow], List[EnvironmentalStateSnapshot]]:
        """Executes the complete F3 hindcast pipeline for an event.

        Args:
            event_id: The spill event identifier (e.g. 'EVT0001')
            states: Optional live F2 states. If None, loaded via load_mock('f2', event_id)
            forcing_provider: Optional environmental forcing provider. If None, SyntheticForcingProvider is used
            config: Optional ensemble configuration
            base_seed: Master seed for reproducibility

        Returns:
            Tuple of (source_hypotheses, environmental_state_snapshots)
        """
        # 1. Acquire temporal states
        if states is None:
            states = load_mock("f2", event_id)

        seed_states, validation_meta = self.validation_agent.process(states)
        if not seed_states:
            raise ValueError(f"No valid OBSERVED states available to seed hindcast for {event_id}")

        # 2. Acquire forcing provider
        if forcing_provider is None:
            try:
                forcing_provider = SyntheticForcingProvider()
            except Exception:
                forcing_provider = MissingForcingFallbackProvider()

        # Determine reference frame
        settings = get_settings()
        cfg_dict = settings.load_config_yaml()
        aoi = cfg_dict.get("aoi", {})
        ref_lat = float(aoi.get("ref_lat", seed_states[0].centroid.lat))
        ref_lon = float(aoi.get("ref_lon", seed_states[0].centroid.lon))
        frame = Frame(ref_lat=ref_lat, ref_lon=ref_lon)

        if config is None:
            config = EnsembleConfig.from_dict(cfg_dict)

        # 3. Capture environmental state snapshot for provenance
        first_state = seed_states[0]
        env_snapshot = self.forcing_agent.capture_snapshot(
            forcing_provider=forcing_provider,
            event_id=event_id,
            lat=first_state.centroid.lat,
            lon=first_state.centroid.lon,
            timestamp=first_state.timestamp
        )

        dq_flag = "nominal"
        if not forcing_provider.is_available():
            dq_flag = "forcing_unavailable"
        elif validation_meta.get("is_single_observation"):
            dq_flag = "single_observation"

        # 4. Execute physical Lagrangian ensemble integration
        ensemble_result = self.physics_agent.run_ensemble(
            seed_states=seed_states,
            forcing_provider=forcing_provider,
            frame=frame,
            config=config,
            base_seed=base_seed
        )

        # 5. Infer candidate source hypotheses and pooled best estimate
        hypotheses = self.inference_agent.infer(
            ensemble_result=ensemble_result,
            seed_states=seed_states,
            frame=frame,
            config=config,
            data_quality_flag=dq_flag
        )

        # 6. Audit and seal provenance contracts
        self.provenance_agent.verify_and_seal(hypotheses, event_id)

        # 7. Persist to repository
        self.repo.save_hypotheses(event_id, hypotheses)
        self.repo.save_environmental_states(event_id, [env_snapshot])
        self.repo.save_trajectories(event_id, ensemble_result.trajectories)

        return hypotheses, [env_snapshot]

    def get_hypotheses(self, event_id: str) -> List[SourceHypothesisWindow]:
        """Retrieves stored hypotheses for an event."""
        return self.repo.get_hypotheses(event_id)

    def get_best_hypothesis(self, event_id: str) -> SourceHypothesisWindow:
        """Retrieves the pooled best estimate (HBEST) for an event."""
        hyps = self.get_hypotheses(event_id)
        if not hyps:
            # Auto-run if not yet generated
            hyps, _ = self.execute_hindcast(event_id)
        for h in hyps:
            if h.ensemble_id == -1:
                return h
        raise KeyError(f"No HBEST hypothesis found for event {event_id}")
