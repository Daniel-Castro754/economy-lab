from dataclasses import dataclass

from economy_lab.core.macro_cycle import (
    derive_dynare_reference_settings,
    extract_quarterly_macro_state,
)


@dataclass
class Metrics:
    month: int
    gdp_index: float
    inflation: float
    unemployment: float
    policy_rate: float
    bank_credit: float
    credit_rationed: float
    undercapitalized_banks: int
    bank_capital_ratio: float


def test_quarterly_state_extracts_growth_credit_and_financial_stress():
    points = [
        Metrics(1, 100.0, 4.0, 7.0, 10.0, 100.0, 0.0, 0, 0.10),
        Metrics(2, 101.0, 4.2, 7.1, 10.2, 110.0, 5.0, 0, 0.095),
        Metrics(3, 102.0, 4.5, 7.4, 10.5, 120.0, 20.0, 1, 0.09),
    ]
    state = extract_quarterly_macro_state(points, quarter=1, bank_count=2)
    assert state.end_month == 3
    assert round(state.quarterly_gdp_growth_pct, 6) == 2.0
    assert round(state.quarterly_credit_growth_pct, 6) == 20.0
    assert 0.0 < state.financial_stress < 1.0
    assert state.bank_capital_ratio_pct == 9.0


def test_reference_settings_are_bounded_and_react_to_state():
    calm = Metrics(3, 100.0, 4.0, 7.0, 10.0, 100.0, 0.0, 0, 0.12)
    stressed = Metrics(3, 95.0, 10.0, 15.0, 12.0, 80.0, 80.0, 2, 0.04)
    calm_state = extract_quarterly_macro_state([calm], quarter=1, bank_count=2)
    stressed_state = extract_quarterly_macro_state([stressed], quarter=1, bank_count=2)
    calm_settings = derive_dynare_reference_settings(
        calm_state,
        initial_monetary_shock_pp=1.0,
        inflation_anchor_pct=4.0,
        unemployment_anchor_pct=7.0,
        adaptation_strength=0.5,
    )
    stressed_settings = derive_dynare_reference_settings(
        stressed_state,
        initial_monetary_shock_pp=1.0,
        inflation_anchor_pct=4.0,
        unemployment_anchor_pct=7.0,
        adaptation_strength=0.5,
    )
    assert 1.1 <= stressed_settings.phi_pi <= 2.5
    assert 0.05 <= stressed_settings.phi_x <= 0.8
    assert 0.55 <= stressed_settings.rho_i <= 0.95
    assert stressed_settings.phi_pi > calm_settings.phi_pi
    assert stressed_settings.phi_x > calm_settings.phi_x
    assert stressed_settings.sigma >= calm_settings.sigma
    assert stressed_settings.base_policy_rate_pct == 12.0
