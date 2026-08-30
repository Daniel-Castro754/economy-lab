import pytest
from pydantic import ValidationError

from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.core.schemas import EconomicShockSpec, ScenarioSpec
from economy_lab.core.shocks import EconomicShock, ShockRuntime
from economy_lab.core.simulation import run_economy_zero
from economy_lab.finance import flow_matrix, stock_matrix


def test_shock_runtime_adds_overlapping_shocks_and_bounds_values():
    runtime = ShockRuntime(
        [
            EconomicShock("productivity", 1, 3, 80.0),
            EconomicShock("productivity", 2, 2, 80.0),
            EconomicShock("external_demand", 2, 1, -40.0),
        ]
    )
    assert runtime.state_for_month(1).productivity_pct == 80.0
    assert runtime.state_for_month(2).productivity_pct == 100.0
    assert runtime.state_for_month(2).external_demand_pct == -40.0
    assert runtime.state_for_month(4).productivity_pct == 0.0


def test_shock_schedule_must_fit_simulation_horizon():
    with pytest.raises(ValidationError):
        ScenarioSpec(
            months=6,
            shocks=[EconomicShockSpec(kind="productivity", start_month=5, duration_months=3, magnitude_pct=10)],
        )


def test_trade_sector_is_explicit_and_godley_balances():
    model = EconomyZeroModel(EconomyZeroConfig(households=160, firms=8, banks=2, seed=44))
    metrics = model.run(3)
    assert sum(item.exports for item in metrics) > 0
    assert sum(item.imports for item in metrics) > 0
    stocks = stock_matrix(model.ledger, tick=model.tick)
    flows = flow_matrix(model.ledger, tick=model.tick)
    assert stocks.balanced
    assert flows.balanced
    deposits = next(row for row in stocks.rows if row.instrument == "deposits")
    assert deposits.sectors["rest_of_world"] >= 0
    assert abs(deposits.total) < 1e-6


def test_positive_fiscal_shock_raises_government_spending_same_seed():
    base = run_economy_zero(ScenarioSpec(months=2, households=200, firms=10, banks=2, seed=8))
    shocked = run_economy_zero(
        ScenarioSpec(
            months=2,
            households=200,
            firms=10,
            banks=2,
            seed=8,
            shocks=[EconomicShockSpec(kind="fiscal_spending", start_month=1, duration_months=2, magnitude_pct=40)],
        )
    )
    assert sum(p.government_spending or 0 for p in shocked.series) > sum(p.government_spending or 0 for p in base.series)
    assert shocked.summary.ledger_balanced
    assert shocked.summary.godley_stocks_balanced
    assert shocked.shocks is not None


def test_external_demand_shock_raises_exports_same_seed():
    base = run_economy_zero(ScenarioSpec(months=2, households=180, firms=9, banks=2, seed=12))
    shocked = run_economy_zero(
        ScenarioSpec(
            months=2,
            households=180,
            firms=9,
            banks=2,
            seed=12,
            shocks=[EconomicShockSpec(kind="external_demand", start_month=1, duration_months=2, magnitude_pct=60)],
        )
    )
    assert shocked.summary.cumulative_exports > base.summary.cumulative_exports
    assert shocked.summary.godley_flows_balanced
