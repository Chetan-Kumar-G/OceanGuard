"""The rule/constraint engine. Fixed thresholds, not a learned classifier.

    SUPPORTS     iff every evaluable constrained residual <= its support bound
    CONTRADICTS  iff any  evaluable constrained residual >= its contradict bound
    UNKNOWN      grey band, or no constrained residual was evaluable

Boundary behaviour is inclusive on both sides, matching the reference dataset:
a residual exactly at its support bound SUPPORTS; exactly at its contradict
bound CONTRADICTS. CONTRADICTS is checked first, so it wins ties.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import CONSTRAINED_RESIDUALS, EvidenceThresholds
from .models import Relation


@dataclass
class ResidualSet:
    """Residuals for one candidate relationship.

    ``constrained`` holds only the residuals that were actually evaluable and are
    allowed to drive the verdict (spatial_residual_km, temporal_residual_h).
    ``context`` holds reported-but-not-load-bearing values. ``missing`` names any
    constrained residual that could not be computed (integration rule 8).
    """

    constrained: dict[str, float] = field(default_factory=dict)
    context: dict[str, float] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def set_constrained(self, name: str, value: float | None, *, missing_label: str | None = None) -> None:
        if name not in CONSTRAINED_RESIDUALS:
            raise ValueError(f"{name!r} is not a constrained residual")
        if value is None:
            self.missing.append(missing_label or name)
        else:
            self.constrained[name] = float(value)

    def set_context(self, name: str, value: float | None) -> None:
        if value is not None:
            self.context[name] = float(value)


def classify(residuals: dict[str, float], thr: EvidenceThresholds) -> tuple[Relation, str]:
    """Core three-way rule over the *evaluable constrained* residuals."""
    hot = [k for k, v in residuals.items() if v >= thr.bound("contradict", k)]
    if hot:
        detail = ", ".join(
            f"{k}={residuals[k]:.2f}>={thr.bound('contradict', k):g}" for k in hot
        )
        return "CONTRADICTS", f"exceeds contradict bound: {detail}"

    if not residuals:
        return "UNKNOWN", "no constrained residual was evaluable"

    cool = {k: v for k, v in residuals.items() if v <= thr.bound("support", k)}
    if len(cool) == len(residuals):
        return "SUPPORTS", "all constrained residuals within support bounds"

    warm = [k for k in residuals if k not in cool]
    detail = ", ".join(f"{k}={residuals[k]:.2f}" for k in warm)
    return "UNKNOWN", f"residuals in the grey band: {detail}"


def evaluate(residuals: ResidualSet, thr: EvidenceThresholds) -> tuple[Relation, str]:
    """Classify, then apply the missing-field rule.

    A missing constrained residual forces UNKNOWN *unless* the residuals that
    were evaluable already CONTRADICT — a CONTRADICTS is never discarded to make
    an event look cleaner (integration rule 9).
    """
    relation, reason = classify(residuals.constrained, thr)

    if relation != "CONTRADICTS" and residuals.missing:
        missing = ", ".join(sorted(set(residuals.missing)))
        relation = "UNKNOWN"
        reason = f"missing field(s) needed for a constrained residual: {missing}"

    if residuals.notes:
        reason = f"{reason} ({'; '.join(residuals.notes)})"
    return relation, reason
