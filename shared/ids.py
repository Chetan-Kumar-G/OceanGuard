"""Frozen ID scheme (Blueprint Part 5). The ONLY place these strings are minted.

No feature invents an alternate scheme. Every downstream id embeds ``event_id``
so any feature can filter its working set without a join.
"""
from __future__ import annotations

import re

_EVENT_RE = re.compile(r"^EVT\d{4}$")


def is_event_id(value: str) -> bool:
    return bool(_EVENT_RE.match(value or ""))


def event_scoped_id(prefix: str, event_id: str, seq: int, *, width: int = 3) -> str:
    """``<prefix>_<event_id>_<zero-padded seq>`` e.g. ``EV_EVT0001_012``."""
    if seq < 0:
        raise ValueError(f"sequence must be non-negative, got {seq}")
    return f"{prefix}_{event_id}_{seq:0{width}d}"


def evidence_id(event_id: str, seq: int) -> str:
    """F5 evidence relation id — ``EV_<event_id>_<3-digit seq>`` (integration rule 7)."""
    return event_scoped_id("EV", event_id, seq, width=3)


def parse_evidence_seq(evidence_id_str: str) -> int:
    return int(evidence_id_str.rsplit("_", 1)[1])
