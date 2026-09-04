from datetime import datetime, timezone


def mint_event_id(seq: int) -> str:
    """Format: EVT + 4-digit zero-padded, e.g. EVT0001"""
    return f"EVT{int(seq):04d}"


def mint_scene_id(event_id: str, seq: int) -> str:
    """Format: S1_<event_id>_<2-digit seq>, e.g. S1_EVT0001_00"""
    return f"S1_{event_id}_{int(seq):02d}"


def mint_observation_id(event_id: str, seq: int) -> str:
    """Format: OBS_<event_id>_<3-digit seq>, e.g. OBS_EVT0001_003"""
    return f"OBS_{event_id}_{int(seq):03d}"


def mint_run_id() -> str:
    """Format: RUN_<UTC-ISO-compact>, e.g. RUN_20260904T102000Z"""
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"RUN_{now}"
