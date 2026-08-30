"""Quarterly ABM/SFC -> Dynare state-conditioning bridge.

v0.9 deliberately stops short of claiming online DSGE estimation.  At each
completed ABM quarter we extract a small, auditable macro state vector and map
it to *bounded reference-model settings*.  Dynare is then re-run and only the
future IRF guidance is replaced.

The mapping is an experimental controller, not an econometric estimator.  Its
purpose is architectural: prove that the macro engine can be re-solved from
realized micro/SFC state without rewriting history or violating ledger
ownership.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


@dataclass(frozen=True, slots=True)
class QuarterlyMacroState:
    quarter: int
    end_month: int
    gdp_index: float
    quarterly_gdp_growth_pct: float
    inflation_pct: float
    unemployment_pct: float
    policy_rate_pct: float
    bank_credit: float
    quarterly_credit_growth_pct: float
    bank_capital_ratio_pct: float
    financial_stress: float


@dataclass(frozen=True, slots=True)
class DynareReferenceSettings:
    quarter: int
    start_month: int
    base_policy_rate_pct: float
    monetary_shock_pp: float
    beta: float
    sigma: float
    kappa: float
    rho_i: float
    phi_pi: float
    phi_x: float
    state: QuarterlyMacroState


def extract_quarterly_macro_state(
    metrics: Sequence[object],
    *,
    quarter: int,
    bank_count: int,
    previous_endpoint: object | None = None,
) -> QuarterlyMacroState:
    if not metrics:
        raise ValueError("metrics cannot be empty")
    end = metrics[-1]
    reference = previous_endpoint if previous_endpoint is not None else metrics[0]

    end_gdp = max(1e-9, float(getattr(end, "gdp_index")))
    reference_gdp = max(1e-9, float(getattr(reference, "gdp_index")))
    gdp_growth = 100.0 * (end_gdp / reference_gdp - 1.0)

    end_credit = max(0.0, float(getattr(end, "bank_credit", 0.0)))
    reference_credit = max(0.0, float(getattr(reference, "bank_credit", 0.0)))
    if reference_credit <= 1e-9:
        credit_growth = 0.0 if end_credit <= 1e-9 else 100.0
    else:
        credit_growth = 100.0 * (end_credit / reference_credit - 1.0)

    rationed = max(0.0, float(getattr(end, "credit_rationed", 0.0)))
    undercapitalized = max(0.0, float(getattr(end, "undercapitalized_banks", 0.0)))
    rationing_ratio = rationed / max(end_credit + rationed, 1.0)
    bank_stress = min(1.0, undercapitalized / float(max(1, bank_count)))
    financial_stress = _clamp(0.70 * rationing_ratio + 0.30 * bank_stress, 0.0, 1.0)

    return QuarterlyMacroState(
        quarter=max(1, int(quarter)),
        end_month=int(getattr(end, "month")),
        gdp_index=end_gdp,
        quarterly_gdp_growth_pct=_clamp(gdp_growth, -50.0, 50.0),
        inflation_pct=_clamp(float(getattr(end, "inflation")), -50.0, 150.0),
        unemployment_pct=_clamp(float(getattr(end, "unemployment")), 0.0, 100.0),
        policy_rate_pct=_clamp(float(getattr(end, "policy_rate")), -5.0, 100.0),
        bank_credit=end_credit,
        quarterly_credit_growth_pct=_clamp(credit_growth, -100.0, 300.0),
        bank_capital_ratio_pct=_clamp(
            100.0 * float(getattr(end, "bank_capital_ratio", 0.0)), -100.0, 100.0
        ),
        financial_stress=financial_stress,
    )


def derive_dynare_reference_settings(
    state: QuarterlyMacroState,
    *,
    initial_monetary_shock_pp: float,
    inflation_anchor_pct: float,
    unemployment_anchor_pct: float,
    adaptation_strength: float = 0.25,
    base_beta: float = 0.99,
    base_sigma: float = 1.0,
    base_kappa: float = 0.10,
    base_rho_i: float = 0.80,
    base_phi_pi: float = 1.50,
    base_phi_x: float = 0.25,
) -> DynareReferenceSettings:
    """Map realized state to bounded reference-model settings.

    These are *not* estimated deep parameters.  The mapping is intentionally
    weak, bounded and fully reportable so it can later be replaced by formal
    calibration/estimation without changing the orchestration contract.
    """
    a = _clamp(adaptation_strength, 0.0, 1.0)
    inflation_gap = _clamp(state.inflation_pct - inflation_anchor_pct, -20.0, 20.0)
    unemployment_gap = _clamp(state.unemployment_pct - unemployment_anchor_pct, -20.0, 40.0)
    weak_growth = _clamp(-state.quarterly_gdp_growth_pct, -20.0, 20.0)
    stress = state.financial_stress

    phi_pi = _clamp(base_phi_pi + a * 0.07 * inflation_gap, 0.50, 4.00)
    phi_x = _clamp(base_phi_x + a * (0.018 * unemployment_gap + 0.012 * weak_growth), -1.0, 2.0)
    rho_i = _clamp(base_rho_i + a * 0.10 * stress, 0.05, 0.98)
    sigma = _clamp(base_sigma + a * (0.35 * stress + 0.012 * max(unemployment_gap, 0.0)), 0.10, 5.0)
    kappa = _clamp(base_kappa * (1.0 + a * 0.035 * abs(inflation_gap)), 0.005, 1.0)

    # The initial exogenous impulse decays as the simulation moves away from the
    # original shock date.  State stress can modestly preserve its effective
    # magnitude, but never reverse its sign or let it explode.
    persistence = 0.65 ** max(1, state.quarter)
    stress_multiplier = 1.0 + a * (0.25 * stress + 0.02 * abs(inflation_gap))
    shock = _clamp(initial_monetary_shock_pp * persistence * stress_multiplier, 0.02, 20.0)

    # The re-solved IRF is anchored at the *realized* policy rate at quarter end.
    # This affects the ABM bridge baseline; Dynare variables remain deviations.
    base_policy_rate = _clamp(state.policy_rate_pct, -5.0, 100.0)

    return DynareReferenceSettings(
        quarter=state.quarter,
        start_month=state.end_month + 1,
        base_policy_rate_pct=base_policy_rate,
        monetary_shock_pp=shock,
        beta=_clamp(base_beta, 0.81, 0.999),
        sigma=sigma,
        kappa=kappa,
        rho_i=rho_i,
        phi_pi=phi_pi,
        phi_x=phi_x,
        state=state,
    )

