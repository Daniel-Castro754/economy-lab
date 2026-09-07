from economy_lab.abm.agents import Household
from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.engines.hark_adapter import (
    income_group_risk_multiplier,
    update_household_income_state,
)
from economy_lab.profiles.service import build_lab_profile, apply_profile_to_scenario
from economy_lab.core.schemas import ScenarioSpec


def _household(*, employed: bool = True, group: int = 0) -> Household:
    return Household(
        id=1,
        bank_id=0,
        wage=3000.0,
        propensity_to_consume=0.85,
        employed_by=0 if employed else None,
        last_income=3000.0 if employed else 0.0,
        income_group=group,
        permanent_income_estimate=2400.0,
    )


def test_income_group_risk_multiplier_declines_across_groups():
    low = income_group_risk_multiplier(group=0, groups=5, dispersion=0.35)
    middle = income_group_risk_multiplier(group=2, groups=5, dispersion=0.35)
    high = income_group_risk_multiplier(group=4, groups=5, dispersion=0.35)
    assert low > middle > high
    assert middle == 1.0


def test_employed_household_syncs_current_and_permanent_income():
    household = _household(employed=True, group=2)
    state = update_household_income_state(
        household,
        income_tax_rate=0.20,
        aggregate_unemployment_rate=0.07,
        base_unemployment_probability=0.05,
        unemployment_replacement_rate=0.30,
        permanent_income_memory=0.20,
        income_groups=5,
        income_risk_dispersion=0.35,
    )
    assert state.employed is True
    assert state.current_net_income == 2400.0
    assert state.permanent_income == 2400.0
    assert state.transitory_income_ratio == 1.0
    assert household.months_employed == 1


def test_unemployed_household_keeps_slow_moving_permanent_income_but_zero_current_income():
    household = _household(employed=False, group=0)
    household.permanent_income_estimate = 2400.0
    state = update_household_income_state(
        household,
        income_tax_rate=0.20,
        aggregate_unemployment_rate=0.12,
        base_unemployment_probability=0.05,
        unemployment_replacement_rate=0.30,
        permanent_income_memory=0.20,
        income_groups=5,
        income_risk_dispersion=0.35,
    )
    assert state.current_net_income == 0.0
    assert 720.0 < state.permanent_income < 2400.0
    assert state.transitory_income_ratio == 0.0
    assert state.unemployment_probability > 0.05
    assert household.months_unemployed == 1


def test_wage_payment_resets_stale_income_for_unemployed_households():
    model = EconomyZeroModel(EconomyZeroConfig(households=120, firms=6, banks=2, seed=91, initial_employment_rate=0.50))
    unemployed = [item for item in model.households if item.employed_by is None]
    assert unemployed
    for household in unemployed:
        household.last_income = 9999.0
    model.tick = 1
    model._pay_wages_and_taxes()
    assert all(item.last_income == 0.0 for item in unemployed if item.employed_by is None)
    model.ledger.assert_balanced()


def test_hark_profile_carries_state_and_income_process_parameters():
    built = build_lab_profile(module_id="hark", inputs={
        "annual_interest_rate": 0.11,
        "crra": 3.0,
        "annual_discount_factor": 0.97,
        "unemployment_probability": 0.07,
        "unemployment_replacement_rate": 0.42,
        "permanent_shock_std": 0.06,
        "transitory_shock_std": 0.18,
        "permanent_income_memory": 0.25,
        "income_groups": 4,
        "income_risk_dispersion": 0.20,
        "max_market_resources": 10.0,
        "points": 20,
    })
    built["id"] = "hark-state-test"
    scenario, _ = apply_profile_to_scenario(ScenarioSpec(), built)
    assert scenario.household_behavior == "hark"
    assert scenario.hark_state_mode == "employment_income"
    assert scenario.hark_unemployment_probability == 0.07
    assert scenario.hark_unemployment_replacement_rate == 0.42
    assert scenario.hark_permanent_shock_std == 0.06
    assert scenario.hark_transitory_shock_std == 0.18
    assert scenario.hark_permanent_income_memory == 0.25
    assert scenario.hark_income_groups == 4
    assert scenario.hark_income_risk_dispersion == 0.20


def test_stateful_hark_flow_builds_household_report_without_touching_accounting(monkeypatch):
    import economy_lab.engines.hark_adapter as hark_adapter
    from economy_lab.core.simulation import run_economy_zero

    monkeypatch.setattr(hark_adapter, "hark_available", lambda: True)
    monkeypatch.setattr(
        hark_adapter.HarkConsumptionPolicy,
        "_policy_function",
        lambda self, **kwargs: (lambda market_resources: min(float(market_resources), 0.55 * float(market_resources))),
    )

    result = run_economy_zero(
        ScenarioSpec(
            months=3,
            households=150,
            firms=6,
            banks=2,
            seed=123,
            household_behavior="hark",
            hark_state_mode="employment_income",
            hark_income_groups=5,
            hark_unemployment_probability=0.06,
            hark_unemployment_replacement_rate=0.35,
        )
    )
    assert result.household_engine is not None
    assert result.household_engine.engine == "hark-indshock-stateful"
    assert result.household_engine.state_mode == "employment_income"
    assert len(result.household_engine.groups) == 5
    assert result.household_engine.average_permanent_income > 0
    assert result.household_engine.average_unemployment_probability > 0
    assert result.summary.ledger_balanced is True
    assert result.summary.godley_stocks_balanced is True
    assert result.summary.godley_flows_balanced is True


def test_hark_household_report_is_exported_to_xlsx(monkeypatch):
    import io
    import zipfile
    import economy_lab.engines.hark_adapter as hark_adapter
    from economy_lab.core.simulation import run_economy_zero
    from economy_lab.reporting import simulation_xlsx_bytes

    monkeypatch.setattr(hark_adapter, "hark_available", lambda: True)
    monkeypatch.setattr(
        hark_adapter.HarkConsumptionPolicy,
        "_policy_function",
        lambda self, **kwargs: (lambda market_resources: 0.50 * float(market_resources)),
    )
    scenario = ScenarioSpec(months=2, households=120, firms=6, banks=2, household_behavior="hark")
    result = run_economy_zero(scenario)
    payload = simulation_xlsx_bytes(scenario, result)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        assert "Famílias HARK" in workbook
        assert "Grupos HARK" in workbook
