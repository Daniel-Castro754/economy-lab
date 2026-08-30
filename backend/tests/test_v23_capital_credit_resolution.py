from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.finance import bank_financials


def small_model(**overrides):
    cfg = EconomyZeroConfig(
        households=30,
        firms=3,
        banks=1,
        seed=11,
        initial_employment_rate=0.8,
        **overrides,
    )
    return EconomyZeroModel(cfg)


def test_productive_capital_depreciates_and_investment_is_recorded():
    model = small_model(firm_investment_propensity=0.20)
    opening = sum(firm.capital_stock for firm in model.firms)
    metrics = model.step()
    assert opening > 0
    assert metrics.productive_capital > 0
    assert metrics.business_investment >= 0
    assert any(firm.last_depreciation > 0 for firm in model.firms)
    model.ledger.assert_balanced()


def test_household_credit_creates_matching_loan_and_deposit():
    model = small_model(initial_household_deposit=100.0, household_credit_liquidity_target_months=3.0)
    household = next(item for item in model.households if item.employed_by is not None)
    model.tick = 1
    before = model.ledger.balance(household.deposit_account)
    lent = model._extend_household_credit(household)
    assert lent > 0
    assert model.ledger.balance(household.deposit_account) == before + lent
    assert -model.ledger.balance(household.consumer_loan_liability) == lent
    assert model.ledger.balance(household.bank_consumer_loan_asset) == lent
    model.ledger.assert_balanced()


def test_household_default_writes_off_consumer_credit():
    model = small_model(household_default_writeoff_ratio=0.50)
    household = model.households[0]
    firm = model.firms[0]
    model.tick = 1
    model.ledger.create_bank_loan(
        tick=1,
        description="test household loan",
        bank_loan_asset=household.bank_consumer_loan_asset,
        borrower_loan_liability=household.consumer_loan_liability,
        borrower_deposit_asset=household.deposit_account,
        bank_deposit_liability=household.bank_deposit_liability,
        amount=20_000.0,
    )
    model.ledger.transfer_deposit(
        tick=1,
        description="drain household cash",
        source_asset=household.deposit_account,
        source_bank_liability=household.bank_deposit_liability,
        destination_asset=firm.deposit_account,
        destination_bank_liability=firm.bank_deposit_liability,
        amount=model.ledger.balance(household.deposit_account),
    )
    household.employed_by = None
    household.permanent_income_estimate = 2_000.0
    for tick in range(1, 5):
        model.tick = tick
        model._handle_household_defaults()
    assert household.credit_defaults == 1
    assert model._month_household_defaults == 1
    assert 0 < -model.ledger.balance(household.consumer_loan_liability) < 20_000.0
    model.ledger.assert_balanced()


def _force_bank_insolvency(model: EconomyZeroModel, amount: float = 150_000.0):
    firm = model.firms[0]
    model.tick = 1
    model.ledger.create_bank_loan(
        tick=1,
        description="resolution stress loan",
        bank_loan_asset=firm.bank_loan_asset,
        borrower_loan_liability=firm.loan_liability,
        borrower_deposit_asset=firm.deposit_account,
        bank_deposit_liability=firm.bank_deposit_liability,
        amount=amount,
    )
    model.ledger.write_off_loan(
        tick=1,
        description="resolution stress loss",
        bank_loan_asset=firm.bank_loan_asset,
        borrower_loan_liability=firm.loan_liability,
        amount=amount,
    )


def test_public_resolution_restores_insolvent_bank_without_breaking_sfc():
    model = small_model(
        bank_resolution_mode="government_recapitalization",
        bank_resolution_trigger_ratio=0.02,
        bank_resolution_target_ratio=0.10,
    )
    _force_bank_insolvency(model)
    assert bank_financials(model.ledger, 0).regulatory_capital < 0
    model._resolve_banks()
    assert model._month_bank_resolutions == 1
    assert model._month_public_recapitalization > 0
    assert bank_financials(model.ledger, 0).regulatory_capital >= 0
    model.ledger.assert_balanced()


def test_bail_in_absorbs_losses_before_public_backstop():
    model = small_model(
        bank_resolution_mode="bail_in",
        bank_resolution_trigger_ratio=0.02,
        bank_resolution_target_ratio=0.10,
        bail_in_household_protection=0.0,
        bail_in_firm_protection=0.0,
    )
    _force_bank_insolvency(model, amount=80_000.0)
    model._resolve_banks()
    assert model._month_bank_resolutions == 1
    assert model._month_bail_in_losses > 0
    assert bank_financials(model.ledger, 0).regulatory_capital >= 0
    model.ledger.assert_balanced()
