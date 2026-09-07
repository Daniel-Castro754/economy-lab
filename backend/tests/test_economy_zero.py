from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.core.schemas import ScenarioSpec
from economy_lab.core.simulation import run_economy_zero


def test_economy_zero_returns_requested_horizon_and_balanced_ledger():
    spec = ScenarioSpec(
        months=6,
        households=300,
        firms=10,
        banks=2,
        seed=7,
        mode="economy_zero",
    )
    result = run_economy_zero(spec)
    assert len(result.series) == 6
    assert result.series[-1].month == 6
    assert result.summary.ledger_balanced is True
    assert result.summary.final_bank_credit == result.summary.final_corporate_debt + result.summary.final_household_debt


def test_economy_zero_is_reproducible_by_seed():
    spec = ScenarioSpec(
        months=4,
        households=250,
        firms=8,
        banks=2,
        seed=123,
        mode="economy_zero",
    )
    first = run_economy_zero(spec)
    second = run_economy_zero(spec)
    assert first.model_dump() == second.model_dump()


def test_model_ledger_remains_balanced_after_multiple_months():
    model = EconomyZeroModel(
        EconomyZeroConfig(households=200, firms=8, banks=2, seed=11)
    )
    model.run(8)
    model.ledger.assert_balanced()
    assert len(model.ledger.transactions) > 0


def test_native_runtime_and_heuristic_policy_are_reported():
    spec = ScenarioSpec(
        months=2,
        households=200,
        firms=8,
        banks=2,
        seed=19,
        activation_engine="native",
        household_behavior="heuristic",
    )
    result = run_economy_zero(spec)
    assert result.engines is not None
    assert result.engines.activation == "native"
    assert result.engines.household_decision == "heuristic"
    assert result.engines.accounting == "economy-lab-sfc-v1.0"


def test_opening_bank_capital_is_positive_and_credit_is_capital_constrained():
    from economy_lab.finance import bank_financials

    model = EconomyZeroModel(
        EconomyZeroConfig(
            households=100,
            firms=5,
            banks=1,
            seed=17,
            initial_bank_equity_ratio=0.02,
            minimum_bank_capital_ratio=0.20,
        )
    )
    before = bank_financials(model.ledger, 0)
    assert before.regulatory_capital > 0

    firm = model.firms[0]
    current_cash = model.ledger.balance(firm.deposit_account)
    model._ensure_deposit(firm, current_cash + 100_000)
    after = bank_financials(model.ledger, 0)

    assert after.corporate_loans <= before.regulatory_capital / 0.20 + 1e-6
    assert model._month_credit_rationed > 0


def test_loan_writeoff_reduces_bank_regulatory_capital():
    from economy_lab.finance import bank_financials

    model = EconomyZeroModel(EconomyZeroConfig(households=100, firms=5, banks=1, seed=4))
    firm = model.firms[0]
    model.ledger.create_bank_loan(
        tick=1,
        description="test loan",
        bank_loan_asset=firm.bank_loan_asset,
        borrower_loan_liability=firm.loan_liability,
        borrower_deposit_asset=firm.deposit_account,
        bank_deposit_liability=firm.bank_deposit_liability,
        amount=10_000,
    )
    before = bank_financials(model.ledger, 0).regulatory_capital
    model.ledger.write_off_loan(
        tick=1,
        description="test loss",
        bank_loan_asset=firm.bank_loan_asset,
        borrower_loan_liability=firm.loan_liability,
        amount=2_500,
    )
    after = bank_financials(model.ledger, 0).regulatory_capital
    assert round(before - after, 6) == 2500


def test_bank_interest_income_increases_regulatory_capital():
    from economy_lab.finance import bank_financials

    model = EconomyZeroModel(EconomyZeroConfig(households=100, firms=5, banks=1, seed=22))
    firm = model.firms[0]
    model.ledger.create_bank_loan(
        tick=0,
        description="interest test loan",
        bank_loan_asset=firm.bank_loan_asset,
        borrower_loan_liability=firm.loan_liability,
        borrower_deposit_asset=firm.deposit_account,
        bank_deposit_liability=firm.bank_deposit_liability,
        amount=12_000,
    )
    before = bank_financials(model.ledger, 0).regulatory_capital
    model.tick = 1
    model._service_interest()
    after = bank_financials(model.ledger, 0).regulatory_capital

    assert after > before


def test_principal_repayment_does_not_change_bank_regulatory_capital():
    from economy_lab.finance import bank_financials

    model = EconomyZeroModel(EconomyZeroConfig(households=100, firms=5, banks=1, seed=23))
    firm = model.firms[0]
    model.ledger.create_bank_loan(
        tick=0,
        description="principal test loan",
        bank_loan_asset=firm.bank_loan_asset,
        borrower_loan_liability=firm.loan_liability,
        borrower_deposit_asset=firm.deposit_account,
        bank_deposit_liability=firm.bank_deposit_liability,
        amount=40_000,
    )
    # Add enough existing cash for the firm's buffer plus amortization.
    model.ledger.open_instrument_pair(
        tick=0,
        description="extra firm liquidity",
        asset_account=firm.deposit_account,
        liability_account=firm.bank_deposit_liability,
        amount=80_000,
    )
    before = bank_financials(model.ledger, 0).regulatory_capital
    model.tick = 1
    model._repay_principal()
    after = bank_financials(model.ledger, 0).regulatory_capital

    assert abs(after - before) < 1e-6


def test_macro_guidance_changes_policy_rate_without_touching_ledger_balance():
    from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel

    model = EconomyZeroModel(EconomyZeroConfig(households=120, firms=8, banks=2, seed=7))
    model.apply_macro_guidance(
        policy_rate_pct=12.5,
        demand_signal_pp=-0.5,
        inflation_signal_pp=-0.1,
    )
    metrics = model.step()
    assert metrics.policy_rate == 12.5
    model.ledger.assert_balanced()
