"""F8 - Forward Forecasting, Impact Assessment & Historical Replay.

Propagates the latest confirmed spill state forward under a perturbed Lagrangian
ensemble, overlays the result on coastline / sensitive-zone geography, and (for
historical events) replays the forecast against later satellite observations.

The forecast is always a scenario ensemble with an uncertainty envelope - never a
single guaranteed path (see PDF section 11, Technical Boundaries).
"""
