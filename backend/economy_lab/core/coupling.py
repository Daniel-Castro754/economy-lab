"""Explicit macro ↔ micro coupling contract for Economy Lab.

The coupling layer never edits ledger balances. It translates Dynare IRFs into
bounded monthly *signals* that the ABM can react to, then observes realized ABM
metrics and computes a bounded feedback adjustment for the following month.

Authority remains explicit:
- ABM/SFC owns realized GDP, prices, employment, credit and balance sheets.
- Dynare owns the structural marginal IRF used as guidance.
- The coupler owns only the translation/feedback signals between them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from economy_lab.engines.dynare_adapter import DynareIRFPoint, irf_to_monthly_guidance


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


@dataclass(frozen=True, slots=True)
class MacroSignal:
    month: int
    output_gap_guidance_pp: float
    inflation_guidance_pp: float
    dynare_policy_gap_pp: float
    feedback_policy_gap_pp: float
    applied_policy_rate_pct: float
    demand_signal_pp: float
    price_signal_pp: float


@dataclass(frozen=True, slots=True)
class CouplingObservation:
    month: int
    output_gap_guidance_pp: float
    inflation_guidance_pp: float
    dynare_policy_gap_pp: float
    feedback_policy_gap_pp: float
    applied_policy_rate_pct: float
    demand_signal_pp: float
    price_signal_pp: float
    realized_gdp_index: float
    realized_output_gap_proxy_pp: float
    realized_inflation_pct: float
    realized_unemployment_pct: float
    financial_stress: float
    output_residual_pp: float
    inflation_residual_pp: float


class HybridMacroCoupler:
    """Bounded bridge between a quarterly Dynare IRF and the monthly ABM.

    This is intentionally not an estimator or a mathematically exact mixed-
    frequency solution. The v0.9 bridge is a transparent control contract that
    lets the two engines exchange signals without creating dual authority.
    """

    def __init__(
        self,
        *,
        points: Iterable[DynareIRFPoint],
        base_policy_rate_pct: float,
        inflation_anchor_pct: float,
        coupling_strength: float = 0.35,
        feedback_strength: float = 0.15,
        bank_count: int = 3,
    ) -> None:
        self.base_policy_rate_pct = float(base_policy_rate_pct)
        self.inflation_anchor_pct = float(inflation_anchor_pct)
        self.coupling_strength = _clamp(coupling_strength, 0.0, 1.0)
        self.feedback_strength = _clamp(feedback_strength, 0.0, 1.0)
        self.bank_count = max(1, int(bank_count))
        self._guidance: dict[int, dict[str, float]] = {}
        self.replace_guidance(points=points, start_month=1)
        self._policy_feedback_pp = 0.0
        self._demand_feedback_pp = 0.0
        self._trend_gdp: float | None = None
        self.observations: list[CouplingObservation] = []


    def replace_guidance(
        self,
        *,
        points: Iterable[DynareIRFPoint],
        start_month: int,
        base_policy_rate_pct: float | None = None,
    ) -> None:
        """Replace only future monthly guidance with a newly solved Dynare IRF.

        Historical observations are never rewritten.  A quarterly re-solve can
        therefore update month ``start_month`` onward while the ledger/ABM
        history remains immutable.
        """
        if start_month < 1:
            raise ValueError("start_month must be >= 1")
        monthly = irf_to_monthly_guidance(points)
        # Remove stale future guidance but preserve all months already realized.
        for month in tuple(self._guidance):
            if month >= start_month:
                del self._guidance[month]
        for offset, raw in enumerate(monthly):
            self._guidance[start_month + offset] = {
                "output_gap": float(raw["output_gap"]),
                "inflation_gap": float(raw["inflation_gap"]),
                "policy_rate_gap": float(raw["policy_rate_gap"]),
            }
        if base_policy_rate_pct is not None:
            self.base_policy_rate_pct = float(base_policy_rate_pct)

    def signal_for_month(self, month: int) -> MacroSignal:
        if month < 1:
            raise ValueError("month must be >= 1")
        raw = self._guidance.get(month)
        if raw is not None:
            output_gap = float(raw["output_gap"])
            inflation_gap = float(raw["inflation_gap"])
            policy_gap = float(raw["policy_rate_gap"])
        else:
            output_gap = inflation_gap = policy_gap = 0.0

        dynare_policy = policy_gap * self.coupling_strength
        demand = output_gap * self.coupling_strength + self._demand_feedback_pp
        price = inflation_gap * self.coupling_strength
        applied = self.base_policy_rate_pct + dynare_policy + self._policy_feedback_pp
        return MacroSignal(
            month=month,
            output_gap_guidance_pp=output_gap,
            inflation_guidance_pp=inflation_gap,
            dynare_policy_gap_pp=policy_gap,
            feedback_policy_gap_pp=self._policy_feedback_pp,
            applied_policy_rate_pct=_clamp(applied, -5.0, 100.0),
            demand_signal_pp=_clamp(demand, -5.0, 5.0),
            price_signal_pp=_clamp(price, -5.0, 5.0),
        )

    def observe(self, *, signal: MacroSignal, metrics: object) -> CouplingObservation:
        gdp = float(getattr(metrics, "gdp_index"))
        inflation = float(getattr(metrics, "inflation"))
        unemployment = float(getattr(metrics, "unemployment"))
        credit = max(0.0, float(getattr(metrics, "bank_credit", 0.0)))
        rationed = max(0.0, float(getattr(metrics, "credit_rationed", 0.0)))
        undercapitalized = max(0.0, float(getattr(metrics, "undercapitalized_banks", 0.0)))

        if self._trend_gdp is None:
            self._trend_gdp = max(gdp, 1e-9)
        else:
            self._trend_gdp = 0.85 * self._trend_gdp + 0.15 * max(gdp, 1e-9)
        output_gap_proxy = 100.0 * (gdp / max(self._trend_gdp, 1e-9) - 1.0)
        output_gap_proxy = _clamp(output_gap_proxy, -10.0, 10.0)
        inflation_gap = _clamp(inflation - self.inflation_anchor_pct, -20.0, 20.0)

        rationing_ratio = rationed / max(credit + rationed, 1.0)
        bank_stress = min(1.0, undercapitalized / float(self.bank_count))
        financial_stress = _clamp(0.70 * rationing_ratio + 0.30 * bank_stress, 0.0, 1.0)

        output_residual = output_gap_proxy - signal.output_gap_guidance_pp
        inflation_residual = inflation_gap - signal.inflation_guidance_pp

        # A deliberately small, bounded feedback controller. Higher realized
        # inflation/output than the macro guide nudges rates up; financial stress
        # pushes the adjustment down. This is a bridge rule, not a central-bank
        # policy estimate and is therefore exposed in the report.
        raw_policy_feedback = self.feedback_strength * (
            0.30 * inflation_residual + 0.10 * output_residual - 1.50 * financial_stress
        )
        self._policy_feedback_pp = _clamp(raw_policy_feedback, -3.0, 3.0)

        # Micro weakness/financial stress carries into the next demand signal.
        raw_demand_feedback = self.feedback_strength * (
            -0.08 * output_residual - 1.25 * financial_stress
        )
        self._demand_feedback_pp = _clamp(raw_demand_feedback, -2.0, 2.0)

        observation = CouplingObservation(
            month=signal.month,
            output_gap_guidance_pp=signal.output_gap_guidance_pp,
            inflation_guidance_pp=signal.inflation_guidance_pp,
            dynare_policy_gap_pp=signal.dynare_policy_gap_pp,
            feedback_policy_gap_pp=signal.feedback_policy_gap_pp,
            applied_policy_rate_pct=signal.applied_policy_rate_pct,
            demand_signal_pp=signal.demand_signal_pp,
            price_signal_pp=signal.price_signal_pp,
            realized_gdp_index=gdp,
            realized_output_gap_proxy_pp=output_gap_proxy,
            realized_inflation_pct=inflation,
            realized_unemployment_pct=unemployment,
            financial_stress=financial_stress,
            output_residual_pp=output_residual,
            inflation_residual_pp=inflation_residual,
        )
        self.observations.append(observation)
        return observation
