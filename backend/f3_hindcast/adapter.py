"""F2 Temporal-State Adapter for F3.

Validates, normalizes, and filters F2 TemporalSpillState sequences.
CRITICAL BRIDGE PRINCIPLE:
ONLY states with is_observed == True and state_type == 'OBSERVED' are permitted
to seed the physical hindcast. INTERPOLATED and PREDICTED states are strictly excluded.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Sequence, Tuple, Union
from shared.schemas.f2_contract import TemporalSpillState


class F2StateAdapter:
    """Adapter for ingesting and validating F2 temporal spill states."""

    @staticmethod
    def parse_states(
        raw_states: Sequence[Union[Dict[str, Any], TemporalSpillState]]
    ) -> List[TemporalSpillState]:
        """Ensures all inputs are parsed and validated as TemporalSpillState models."""
        parsed: List[TemporalSpillState] = []
        for s in raw_states:
            if isinstance(s, TemporalSpillState):
                parsed.append(s)
            else:
                parsed.append(TemporalSpillState.model_validate(s))
        return parsed

    @staticmethod
    def filter_observed_states(
        states: Sequence[TemporalSpillState]
    ) -> List[TemporalSpillState]:
        """Filters states to retain ONLY ground-truth observed detections.

        Rejects INTERPOLATED and PREDICTED states as required by the blueprint.
        """
        observed: List[TemporalSpillState] = []
        for s in states:
            if s.is_observed is True and s.state_type == "OBSERVED":
                observed.append(s)
        return observed

    @staticmethod
    def sort_states_by_time(
        states: Sequence[TemporalSpillState]
    ) -> List[TemporalSpillState]:
        """Sorts states chronologically by timestamp."""
        def parse_ts(s: TemporalSpillState) -> float:
            ts_str = s.timestamp.replace("Z", "+00:00")
            return datetime.fromisoformat(ts_str).timestamp()

        return sorted(states, key=parse_ts)

    @classmethod
    def prepare_seed_sequence(
        cls,
        raw_states: Sequence[Union[Dict[str, Any], TemporalSpillState]]
    ) -> Tuple[List[TemporalSpillState], Dict[str, Any]]:
        """Processes an event's temporal states into valid hindcast seed states and QA metadata.

        Returns:
            Tuple of (observed_seed_states, metadata_dict)
        Raises:
            ValueError: If no states exist at all, or if event_id is inconsistent.
        """
        all_states = cls.parse_states(raw_states)
        if not all_states:
            raise ValueError("Cannot prepare seed sequence: empty states list received.")

        event_ids = {s.event_id for s in all_states}
        if len(event_ids) > 1:
            raise ValueError(f"Mixed event_ids detected in state sequence: {event_ids}")

        observed = cls.filter_observed_states(all_states)
        sorted_observed = cls.sort_states_by_time(observed)

        total_count = len(all_states)
        obs_count = len(sorted_observed)
        interp_count = sum(1 for s in all_states if s.state_type == "INTERPOLATED")
        pred_count = sum(1 for s in all_states if s.state_type == "PREDICTED")

        is_single = obs_count == 1
        dq_flag = "nominal"
        if obs_count == 0:
            dq_flag = "no_observed_states"
        elif is_single:
            dq_flag = "single_observation"

        meta: Dict[str, Any] = {
            "event_id": all_states[0].event_id,
            "total_states": total_count,
            "observed_count": obs_count,
            "interpolated_count": interp_count,
            "predicted_count": pred_count,
            "is_single_observation": is_single,
            "data_quality_flag": dq_flag,
            "earliest_observed_timestamp": sorted_observed[0].timestamp if sorted_observed else None,
            "latest_observed_timestamp": sorted_observed[-1].timestamp if sorted_observed else None,
            "seed_observation_ids": [s.observation_id for s in sorted_observed],
        }

        return sorted_observed, meta
