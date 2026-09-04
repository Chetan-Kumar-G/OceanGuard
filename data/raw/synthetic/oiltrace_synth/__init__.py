"""OilTrace synthetic data generator.

Simulates marine oil-spill events end to end (source vessel -> drift -> satellite
observation) and emits the eight logical datasets D1..D8 described in the OilTrace
design. Every derived dataset (D2..D8) is produced from the simulated evidence
pipeline, so the ground-truth source is always known and the attribution
datasets can be scored.
"""

__version__ = "0.1.0"
