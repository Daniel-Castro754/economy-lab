from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FinancialGuidance:
    """Canonical monthly banking controls used by Economy Zero.

    Ratios and spreads are stored as decimals inside the kernel. Profiles and
    API contracts use percentage points for human-facing values and are
    converted before model construction.
    """

    month: int
    minimum_capital_ratio: float
    target_reserve_ratio: float
    credit_supply_factor: float
    default_writeoff_ratio: float
    interbank_spread: float
    central_bank_penalty_spread: float


@dataclass(slots=True)
class FinancialControls:
    minimum_capital_ratio: float
    target_reserve_ratio: float
    credit_supply_factor: float
    default_writeoff_ratio: float
    interbank_spread: float
    central_bank_penalty_spread: float

    @classmethod
    def from_guidance(cls, item: FinancialGuidance) -> "FinancialControls":
        return cls(
            minimum_capital_ratio=item.minimum_capital_ratio,
            target_reserve_ratio=item.target_reserve_ratio,
            credit_supply_factor=item.credit_supply_factor,
            default_writeoff_ratio=item.default_writeoff_ratio,
            interbank_spread=item.interbank_spread,
            central_bank_penalty_spread=item.central_bank_penalty_spread,
        )


def guidance_for_month(
    path: tuple[FinancialGuidance, ...],
    month: int,
    fallback: FinancialControls,
) -> FinancialControls:
    """Return the most recent guidance point at or before *month*.

    The path is a deterministic snapshot embedded in ScenarioSpec. No live
    Minsky call happens during simulation, preserving reproducibility.
    """

    selected: FinancialGuidance | None = None
    for item in path:
        if item.month <= month:
            selected = item
        else:
            break
    return FinancialControls.from_guidance(selected) if selected is not None else FinancialControls(
        minimum_capital_ratio=fallback.minimum_capital_ratio,
        target_reserve_ratio=fallback.target_reserve_ratio,
        credit_supply_factor=fallback.credit_supply_factor,
        default_writeoff_ratio=fallback.default_writeoff_ratio,
        interbank_spread=fallback.interbank_spread,
        central_bank_penalty_spread=fallback.central_bank_penalty_spread,
    )
