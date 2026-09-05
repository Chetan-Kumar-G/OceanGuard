"""Deterministic named random streams.

A single master seed produces every dataset. Each logical piece of work draws its
own independent stream keyed by a string path (e.g. ``rng.stream("d1", event_id,
scene_idx)``) so that adding events or reordering modules does not disturb the
numbers used elsewhere.
"""
from __future__ import annotations

import hashlib

import numpy as np


class RNG:
    def __init__(self, seed: int):
        self.seed = int(seed)

    def stream(self, *keys) -> np.random.Generator:
        payload = "|".join(str(k) for k in keys).encode("utf-8")
        digest = hashlib.sha256(payload).digest()
        tag = int.from_bytes(digest[:8], "little")
        return np.random.default_rng(np.random.SeedSequence([self.seed, tag]))
