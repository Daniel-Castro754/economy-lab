"""Auditable exogenous shock schedules for Economy Zero v1.0.

Shocks are deliberately small contracts, not arbitrary code.  Each shock has a
start month, duration and percentage magnitude.  Overlapping shocks of the same
kind add together and are bounded before they reach agent behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

SHOCK_KINDS = (
    "fiscal_spending",
    "productivity",
    "cost_push",
    "external_demand",
    "import_cost",
)

_BOUNDS = {
    "fiscal_spending": (-80.0, 200.0),
    "productivity": (-50.0, 100.0),
    "cost_push": (-50.0, 200.0),
    "external_demand": (-100.0, 300.0),
    "import_cost": (-80.0, 300.0),
}


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


@dataclass(frozen=True, slots=True)
class EconomicShock:
    kind: str
    start_month: int
    duration_months: int
    magnitude_pct: float
    label: str = ""

    def active(self, month: int) -> bool:
        return self.start_month <= month < self.start_month + self.duration_months


@dataclass(frozen=True, slots=True)
class ShockState:
    month: int
    fiscal_spending_pct: float = 0.0
    productivity_pct: float = 0.0
    cost_push_pct: float = 0.0
    external_demand_pct: float = 0.0
    import_cost_pct: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "fiscal_spending": self.fiscal_spending_pct,
            "productivity": self.productivity_pct,
            "cost_push": self.cost_push_pct,
            "external_demand": self.external_demand_pct,
            "import_cost": self.import_cost_pct,
        }


class ShockRuntime:
    def __init__(self, shocks: Iterable[EconomicShock] = ()):
        self.shocks = tuple(shocks)

    def state_for_month(self, month: int) -> ShockState:
        totals = {kind: 0.0 for kind in SHOCK_KINDS}
        for shock in self.shocks:
            if shock.kind not in totals:
                raise ValueError(f"unsupported shock kind: {shock.kind}")
            if shock.active(month):
                totals[shock.kind] += shock.magnitude_pct
        for kind, (lower, upper) in _BOUNDS.items():
            totals[kind] = _clamp(totals[kind], lower, upper)
        return ShockState(
            month=month,
            fiscal_spending_pct=totals["fiscal_spending"],
            productivity_pct=totals["productivity"],
            cost_push_pct=totals["cost_push"],
            external_demand_pct=totals["external_demand"],
            import_cost_pct=totals["import_cost"],
        )
