import io
import zipfile

from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.abm.agents import Household
from economy_lab.core.schemas import ScenarioSpec
from economy_lab.core.simulation import run_economy_zero
from economy_lab.engines.hark_adapter import update_household_income_state
from economy_lab.reporting import simulation_xlsx_bytes


def test_unemployment_benefits_are_explicit_transfers_and_keep_sfc_balanced():
    model = EconomyZeroModel(
        EconomyZeroConfig(
            households=30,
            firms=3,
            banks=1,
            seed=5,
            initial_employment_rate=0.0,
            unemployment_benefits_enabled=True,
            unemployment_benefit_replacement_rate=0.50,
            unemployment_benefit_waiting_months=0,
            unemployment_benefit_max_months=6,
            unemployment_benefit_cap=2000.0,
            labor_supply_mode="inelastic",
        )
    )
    opening_debt = -model.ledger.balance(model.government.debt_liability)
    metrics = model.step()
    assert metrics.unemployment_benefits > 0
    assert any(h.last_unemployment_benefit > 0 for h in model.households)
    # Transfers are not government final consumption/GDP expenditure.
    assert metrics.unemployment_benefits != metrics.government_spending
    assert -model.ledger.balance(model.government.debt_liability) >= opening_debt
    model.ledger.assert_balanced()


def test_hark_income_state_includes_realized_benefit_and_observed_separation_risk():
    low = Household(
        id=1, bank_id=0, wage=3000.0, propensity_to_consume=0.85,
        employed_by=None, permanent_income_estimate=2400.0,
        last_transfer_income=900.0,
    )
    high = Household(
        id=2, bank_id=0, wage=3000.0, propensity_to_consume=0.85,
        employed_by=None, permanent_income_estimate=2400.0,
        last_transfer_income=900.0,
    )
    common = dict(
        income_tax_rate=0.20,
        aggregate_unemployment_rate=0.08,
        base_unemployment_probability=0.05,
        unemployment_replacement_rate=0.30,
        permanent_income_memory=0.20,
        income_groups=5,
        income_risk_dispersion=0.0,
    )
    low_state = update_household_income_state(low, observed_job_separation_rate=0.01, **common)
    high_state = update_household_income_state(high, observed_job_separation_rate=0.10, **common)
    assert low_state.current_net_income == 900.0
    assert low_state.transitory_income_ratio > 0
    assert high_state.unemployment_probability > low_state.unemployment_probability


def test_labor_supply_search_falls_with_benefits_and_liquid_wealth():
    model = EconomyZeroModel(
        EconomyZeroConfig(
            households=30,
            firms=3,
            banks=1,
            seed=9,
            initial_employment_rate=0.0,
            labor_supply_mode="reservation_wage",
            labor_search_intensity=1.0,
            benefit_search_disincentive=0.50,
            wealth_search_disincentive=0.30,
        )
    )
    household = model.households[0]
    household.last_unemployment_benefit = 0.0
    model._labor_supply_state(household)
    baseline = household.search_intensity
    reservation0 = household.reservation_wage

    household.last_unemployment_benefit = household.permanent_income_estimate * 0.8
    model._labor_supply_state(household)
    assert household.search_intensity < baseline
    assert household.reservation_wage > reservation0


def test_simulation_reports_labor_transitions_and_benefits():
    scenario = ScenarioSpec(
        months=4,
        households=150,
        firms=6,
        banks=2,
        seed=77,
        initial_unemployment=20,
        unemployment_benefits_enabled=True,
        unemployment_benefit_waiting_months=0,
        unemployment_benefit_replacement_rate=50,
        labor_supply_mode="reservation_wage",
    )
    result = run_economy_zero(scenario)
    assert result.labor_market is not None
    assert result.labor_market.benefits_enabled is True
    assert result.summary.cumulative_unemployment_benefits > 0
    assert 0 <= result.summary.final_labor_force_participation <= 100
    assert all(point.job_separation_rate is not None for point in result.series)
    assert all(point.job_finding_rate is not None for point in result.series)
    assert result.summary.ledger_balanced is True
    assert result.summary.godley_stocks_balanced is True
    assert result.summary.godley_flows_balanced is True


def test_labor_report_is_exported_to_excel():
    scenario = ScenarioSpec(months=2, households=120, firms=6, banks=2, initial_unemployment=20)
    result = run_economy_zero(scenario)
    payload = simulation_xlsx_bytes(scenario, result)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        assert "Mercado de trabalho" in workbook
