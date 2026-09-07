from __future__ import annotations

from dataclasses import dataclass
from random import Random
from statistics import fmean

from economy_lab.abm.agents import Bank, CentralBank, Firm, Government, Household, RestOfWorld
from economy_lab.core.shocks import EconomicShock, ShockRuntime, ShockState
from economy_lab.engines.hark_adapter import ConsumptionPolicy, create_consumption_policy
from economy_lab.engines.mesa_adapter import ActivationRuntime, create_activation_runtime
from economy_lab.finance import (
    Ledger,
    Posting,
    FinancialControls,
    FinancialGuidance,
    guidance_for_month,
    aggregate_capital_ratio,
    assert_sector_accounting,
    bank_financials,
    sector_balance_sheets,
)


def gini(values: list[float]) -> float:
    cleaned = sorted(max(0.0, float(value)) for value in values)
    n = len(cleaned)
    total = sum(cleaned)
    if n == 0 or total <= 0:
        return 0.0
    weighted = sum((index + 1) * value for index, value in enumerate(cleaned))
    return max(0.0, min(1.0, (2 * weighted) / (n * total) - (n + 1) / n))


@dataclass(frozen=True, slots=True)
class EconomyZeroConfig:
    households: int = 5000
    firms: int = 100
    banks: int = 3
    seed: int = 42
    initial_employment_rate: float = 0.90
    base_wage: float = 3000.0
    base_price: float = 10.0
    productivity: float = 330.0
    initial_household_deposit: float = 4000.0
    initial_firm_deposit: float = 120000.0
    income_tax_rate: float = 0.20
    public_spending_change: float = 0.0
    policy_rate: float = 0.10
    activation_engine: str = "native"
    mesa_activation_pattern: str = "random"
    household_shopping_sample_size: int = 4
    household_cheapest_choice_probability: float = 1.0
    firm_price_adjustment_strength: float = 1.0
    firm_hiring_strength: float = 1.0
    firm_layoff_strength: float = 1.0
    labor_matching_efficiency: float = 1.0
    initial_capital_per_worker: float = 1200.0
    capital_unit_cost: float = 25.0
    annual_capital_depreciation_rate: float = 0.08
    firm_investment_propensity: float = 0.12
    capital_output_elasticity: float = 0.30
    household_behavior: str = "heuristic"
    hark_crra: float = 2.0
    hark_annual_discount_factor: float = 0.96
    hark_state_mode: str = "employment_income"
    hark_unemployment_probability: float = 0.05
    hark_unemployment_replacement_rate: float = 0.30
    hark_permanent_shock_std: float = 0.04
    hark_transitory_shock_std: float = 0.10
    hark_permanent_income_memory: float = 0.18
    hark_income_groups: int = 5
    hark_income_risk_dispersion: float = 0.35
    unemployment_benefits_enabled: bool = True
    unemployment_benefit_replacement_rate: float = 0.45
    unemployment_benefit_waiting_months: int = 1
    unemployment_benefit_max_months: int = 6
    unemployment_benefit_cap: float = 3500.0
    labor_supply_mode: str = "reservation_wage"
    labor_search_intensity: float = 0.90
    reservation_wage_ratio: float = 0.75
    benefit_search_disincentive: float = 0.20
    wealth_search_disincentive: float = 0.10
    job_separation_risk_memory: float = 0.25
    initial_bank_equity_ratio: float = 0.10
    minimum_bank_capital_ratio: float = 0.08
    target_reserve_ratio: float = 0.10
    credit_supply_factor: float = 1.0
    default_writeoff_ratio: float = 0.35
    interbank_spread: float = 0.01
    central_bank_penalty_spread: float = 0.02
    household_credit_enabled: bool = True
    household_credit_income_multiple: float = 0.50
    household_credit_liquidity_target_months: float = 3.0
    household_credit_spread: float = 0.06
    household_principal_repayment_rate: float = 0.04
    household_default_writeoff_ratio: float = 0.50
    bank_resolution_mode: str = "government_recapitalization"
    bank_resolution_trigger_ratio: float = 0.02
    bank_resolution_target_ratio: float = 0.10
    bail_in_household_protection: float = 2000.0
    bail_in_firm_protection: float = 20_000.0
    financial_guidance: tuple[FinancialGuidance, ...] = ()
    base_import_share: float = 0.08
    base_export_share: float = 0.08
    shocks: tuple[EconomicShock, ...] = ()


@dataclass(frozen=True, slots=True)
class MonthMetrics:
    month: int
    gdp_index: float
    price_index: float
    inflation: float
    unemployment: float
    policy_rate: float
    household_consumption: float
    government_spending: float
    corporate_debt: float
    bank_credit: float
    bank_deposits: float
    gini_wealth: float
    firm_defaults: int
    bank_reserves: float
    central_bank_advances: float
    government_debt: float
    private_net_financial_wealth: float
    bank_capital: float
    bank_capital_ratio: float
    undercapitalized_banks: int
    interbank_credit: float
    bank_profit_loss: float
    credit_rationed: float
    default_losses: float
    exports: float
    imports: float
    net_exports: float
    business_investment: float
    productive_capital: float
    household_debt: float
    household_credit: float
    household_defaults: int
    bank_resolutions: int
    public_recapitalization: float
    bail_in_losses: float
    unemployment_benefits: float
    labor_force_participation: float
    job_separation_rate: float
    job_finding_rate: float
    active_shocks: dict[str, float]


class EconomyZeroModel:
    """Small deterministic-by-seed ABM with a transaction-level accounting ledger.

    It is a structural sandbox, not a calibrated representation of a country.
    The model deliberately favors inspectability and accounting correctness over
    realism. Each month runs a fixed causal sequence that later adapters can
    replace with Mesa/HARK/Minsky/Dynare components.
    """

    def __init__(self, config: EconomyZeroConfig):
        self.config = config
        self.random = Random(config.seed)
        self.ledger = Ledger()
        self.tick = 0
        self.households: list[Household] = []
        self.firms: list[Firm] = []
        self.banks = [Bank(id=i) for i in range(config.banks)]
        self.government = Government(bank_id=0)
        self.rest_of_world = RestOfWorld(bank_id=0)
        self.central_bank = CentralBank(policy_rate=config.policy_rate)
        self.shock_runtime = ShockRuntime(config.shocks)
        self.current_shocks = ShockState(month=0)
        # External macro guidance is signal-only: it never edits ledger positions.
        self.macro_demand_signal_pp = 0.0
        self.macro_inflation_signal_pp = 0.0
        self.base_financial_controls = FinancialControls(
            minimum_capital_ratio=config.minimum_bank_capital_ratio,
            target_reserve_ratio=config.target_reserve_ratio,
            credit_supply_factor=config.credit_supply_factor,
            default_writeoff_ratio=config.default_writeoff_ratio,
            interbank_spread=config.interbank_spread,
            central_bank_penalty_spread=config.central_bank_penalty_spread,
        )
        self.financial_guidance_path = tuple(sorted(config.financial_guidance, key=lambda item: item.month))
        self.financial_controls = FinancialControls(
            minimum_capital_ratio=self.base_financial_controls.minimum_capital_ratio,
            target_reserve_ratio=self.base_financial_controls.target_reserve_ratio,
            credit_supply_factor=self.base_financial_controls.credit_supply_factor,
            default_writeoff_ratio=self.base_financial_controls.default_writeoff_ratio,
            interbank_spread=self.base_financial_controls.interbank_spread,
            central_bank_penalty_spread=self.base_financial_controls.central_bank_penalty_spread,
        )
        self.price_history: list[float] = []
        self.real_gdp_baseline: float | None = None
        self._month_consumption = 0.0
        self._month_government_spending = 0.0
        self._month_defaults = 0
        self._month_credit_rationed = 0.0
        self._month_default_losses = 0.0
        self._month_bank_profit_loss = 0.0
        self._month_exports = 0.0
        self._month_imports = 0.0
        self._month_business_investment = 0.0
        self._month_household_defaults = 0
        self._month_bank_resolutions = 0
        self._month_public_recapitalization = 0.0
        self._month_bail_in_losses = 0.0
        self._month_unemployment_benefits = 0.0
        self._month_job_separations = 0
        self._month_job_matches = 0
        self._month_job_seekers = 0
        self._month_employed_at_start = 0
        self._recent_job_separation_rate = max(0.001, min(0.50, config.hark_unemployment_probability))
        self._create_agents()
        self._assign_household_income_groups()
        self._open_balance_sheets()
        self._seed_employment()
        self._seed_productive_capital()
        self.consumption_policy: ConsumptionPolicy = create_consumption_policy(
            config.household_behavior,
            crra=config.hark_crra,
            annual_discount_factor=config.hark_annual_discount_factor,
            state_mode=config.hark_state_mode,
            unemployment_probability=config.hark_unemployment_probability,
            unemployment_replacement_rate=(
                config.unemployment_benefit_replacement_rate
                if config.unemployment_benefits_enabled
                else config.hark_unemployment_replacement_rate
            ),
            permanent_shock_std=config.hark_permanent_shock_std,
            transitory_shock_std=config.hark_transitory_shock_std,
            permanent_income_memory=config.hark_permanent_income_memory,
            income_groups=config.hark_income_groups,
            income_risk_dispersion=config.hark_income_risk_dispersion,
        )
        self.activation_runtime: ActivationRuntime = create_activation_runtime(
            config.activation_engine, self
        )
        self._active_firms_for_consumption: list[Firm] = []
        self._aggregate_unemployment_rate_for_consumption = 0.0

    def _create_agents(self) -> None:
        cfg = self.config
        for household_id in range(cfg.households):
            # Light heterogeneity: wages are log-normal-ish and consumption propensities differ.
            wage_multiplier = max(0.55, min(2.8, self.random.lognormvariate(0.0, 0.28)))
            self.households.append(
                Household(
                    id=household_id,
                    bank_id=household_id % cfg.banks,
                    wage=cfg.base_wage * wage_multiplier,
                    propensity_to_consume=self.random.uniform(0.75, 0.95),
                )
            )

        for firm_id in range(cfg.firms):
            self.firms.append(
                Firm(
                    id=firm_id,
                    bank_id=firm_id % cfg.banks,
                    price=cfg.base_price * self.random.uniform(0.97, 1.03),
                    productivity=cfg.productivity * self.random.uniform(0.85, 1.15),
                    wage_offer=cfg.base_wage * self.random.uniform(0.92, 1.08),
                )
            )

    def _assign_household_income_groups(self) -> None:
        groups = max(1, min(10, int(self.config.hark_income_groups)))
        ordered = sorted(self.households, key=lambda household: household.wage)
        total = max(1, len(ordered))
        for rank, household in enumerate(ordered):
            household.income_group = min(groups - 1, (rank * groups) // total)
            household.permanent_income_estimate = max(
                1.0, household.wage * max(0.0, 1.0 - self.config.income_tax_rate)
            )

    def _open_balance_sheets(self) -> None:
        cfg = self.config
        for household in self.households:
            self.ledger.open_instrument_pair(
                tick=0,
                description="Opening household deposit",
                asset_account=household.deposit_account,
                liability_account=household.bank_deposit_liability,
                amount=cfg.initial_household_deposit,
            )

        for firm in self.firms:
            self.ledger.open_instrument_pair(
                tick=0,
                description="Opening firm deposit",
                asset_account=firm.deposit_account,
                liability_account=firm.bank_deposit_liability,
                amount=cfg.initial_firm_deposit,
            )

        # Government begins with a small buffer; its mirror is a bank deposit liability.
        opening_government_cash = cfg.firms * cfg.base_wage * 2.0
        self.ledger.open_instrument_pair(
            tick=0,
            description="Opening government deposit",
            asset_account=self.government.deposit_account,
            liability_account=self.government.bank_deposit_liability,
            amount=opening_government_cash,
        )

        # The external sector starts with domestic deposits used to settle trade.
        # This is an opening stock, not monthly income creation; the matching bank
        # deposit liability is included in reserves and the Godley matrix below.
        opening_foreign_cash = max(1_000_000.0, cfg.households * cfg.base_wage * 0.50)
        self.ledger.open_instrument_pair(
            tick=0,
            description="Opening rest-of-world domestic deposit",
            asset_account=self.rest_of_world.deposit_account,
            liability_account=self.rest_of_world.bank_deposit_liability,
            amount=opening_foreign_cash,
        )

        # Households convert part of their opening deposits into bank equity. This
        # is an asset swap for households and a liability reclassification for the
        # bank, so it creates paid-in capital without creating private wealth.
        self._seed_bank_capital()

        # Seed an explicit monetary base. Opening reserves back deposits plus paid-in
        # equity, so the equity conversion genuinely leaves each bank with a positive
        # capital buffer instead of shrinking both liabilities and reserve assets.
        total_opening_reserves = 0.0
        for bank in self.banks:
            deposits = max(0.0, -self.ledger.sum_prefix(f"bank:{bank.id}:deposit_liability"))
            paid_in_equity = max(0.0, -self.ledger.balance(bank.equity_liability))
            opening_reserves = deposits + paid_in_equity
            if opening_reserves <= 0:
                continue
            self.ledger.open_instrument_pair(
                tick=0,
                description=f"Opening reserves for bank {bank.id}",
                asset_account=bank.reserve_asset,
                liability_account=self.central_bank.reserve_liability(bank.id),
                amount=opening_reserves,
            )
            total_opening_reserves += opening_reserves

        if total_opening_reserves > 0:
            self.ledger.open_instrument_pair(
                tick=0,
                description="Opening government bonds backing monetary base",
                asset_account=self.central_bank.government_bond_asset,
                liability_account=self.government.debt_liability,
                amount=total_opening_reserves,
            )
        assert_sector_accounting(self.ledger, tick=0)

    def apply_macro_guidance(
        self,
        *,
        policy_rate_pct: float,
        demand_signal_pp: float = 0.0,
        inflation_signal_pp: float = 0.0,
    ) -> None:
        """Apply bounded exogenous macro signals for the next ABM month.

        The signals influence behavior only. Realized output, prices, employment
        and every financial position remain endogenous to Economy Zero.
        """
        self.central_bank.policy_rate = max(-0.05, min(1.0, policy_rate_pct / 100.0))
        self.macro_demand_signal_pp = max(-5.0, min(5.0, float(demand_signal_pp)))
        self.macro_inflation_signal_pp = max(-5.0, min(5.0, float(inflation_signal_pp)))

    def _refresh_financial_controls(self) -> None:
        self.financial_controls = guidance_for_month(
            self.financial_guidance_path, self.tick, self.base_financial_controls
        )

    def _seed_bank_capital(self) -> None:
        ratio = max(0.0, min(0.50, self.config.initial_bank_equity_ratio))
        if ratio <= 0:
            return
        for household in self.households:
            deposit = max(0.0, self.ledger.balance(household.deposit_account))
            contribution = deposit * ratio
            if contribution <= self.ledger.tolerance:
                continue
            bank = self.banks[household.bank_id]
            self.ledger.post(
                tick=0,
                description=f"Opening bank equity household {household.id} -> bank {bank.id}",
                postings=[
                    Posting(household.deposit_account, -contribution),
                    Posting(household.bank_deposit_liability, contribution),
                    Posting(household.bank_equity_asset, contribution),
                    Posting(bank.equity_liability, -contribution),
                ],
            )

    def _seed_employment(self) -> None:
        target = int(round(len(self.households) * self.config.initial_employment_rate))
        household_ids = list(range(len(self.households)))
        self.random.shuffle(household_ids)
        for index, household_id in enumerate(household_ids[:target]):
            firm = self.firms[index % len(self.firms)]
            firm.employees.add(household_id)
            self.households[household_id].employed_by = firm.id

    def _seed_productive_capital(self) -> None:
        for firm in self.firms:
            workers = max(1, len(firm.employees))
            firm.capital_stock = workers * self.config.initial_capital_per_worker

    def _depreciate_productive_capital(self) -> None:
        monthly_rate = max(0.0, min(1.0, self.config.annual_capital_depreciation_rate / 12.0))
        for firm in self.firms:
            depreciation = max(0.0, firm.capital_stock * monthly_rate)
            firm.last_depreciation = depreciation
            firm.capital_stock = max(0.0, firm.capital_stock - depreciation)
            firm.last_investment = 0.0

    def _ensure_deposit(self, firm: Firm, required: float) -> None:
        available = self.ledger.balance(firm.deposit_account)
        shortfall = max(0.0, required - available)
        if shortfall <= 0:
            return

        current_debt = max(0.0, -self.ledger.balance(firm.loan_liability))
        firm_cap = max(50_000.0, 18.0 * max(firm.last_revenue, firm.wage_offer))
        desired = min(shortfall, max(0.0, firm_cap - current_debt))
        if desired <= 0:
            return

        bank = bank_financials(self.ledger, firm.bank_id)
        headroom = bank.lending_headroom(self.financial_controls.minimum_capital_ratio)
        lend = min(desired * self.financial_controls.credit_supply_factor, headroom)
        self._month_credit_rationed += max(0.0, desired - lend)
        if lend > self.ledger.tolerance:
            self.ledger.create_bank_loan(
                tick=self.tick,
                description=f"Working-capital loan to firm {firm.id}",
                bank_loan_asset=firm.bank_loan_asset,
                borrower_loan_liability=firm.loan_liability,
                borrower_deposit_asset=firm.deposit_account,
                bank_deposit_liability=firm.bank_deposit_liability,
                amount=lend,
            )

    def _extend_household_credit(self, household: Household) -> float:
        if not self.config.household_credit_enabled or household.employed_by is None:
            return 0.0
        deposit = max(0.0, self.ledger.balance(household.deposit_account))
        after_tax_monthly = max(1.0, household.wage * (1.0 - self.config.income_tax_rate))
        liquidity_target = self.config.household_credit_liquidity_target_months * after_tax_monthly
        if deposit >= liquidity_target:
            return 0.0
        debt = max(0.0, -self.ledger.balance(household.consumer_loan_liability))
        debt_cap = after_tax_monthly * 12.0 * self.config.household_credit_income_multiple
        desired = min(liquidity_target - deposit, max(0.0, debt_cap - debt))
        if desired <= self.ledger.tolerance:
            return 0.0
        bank = bank_financials(self.ledger, household.bank_id)
        headroom = bank.lending_headroom(self.financial_controls.minimum_capital_ratio)
        lend = min(desired * self.financial_controls.credit_supply_factor, headroom)
        self._month_credit_rationed += max(0.0, desired - lend)
        if lend <= self.ledger.tolerance:
            return 0.0
        return self.ledger.create_bank_loan(
            tick=self.tick,
            description=f"Consumer credit to household {household.id}",
            bank_loan_asset=household.bank_consumer_loan_asset,
            borrower_loan_liability=household.consumer_loan_liability,
            borrower_deposit_asset=household.deposit_account,
            bank_deposit_liability=household.bank_deposit_liability,
            amount=lend,
        )

    def _service_household_interest(self) -> None:
        for household in self.households:
            debt = max(0.0, -self.ledger.balance(household.consumer_loan_liability))
            if debt <= self.ledger.tolerance:
                continue
            annual_rate = max(-0.05, self.central_bank.policy_rate + self.config.household_credit_spread)
            interest = debt * annual_rate / 12.0
            if interest <= 0:
                continue
            available = max(0.0, self.ledger.balance(household.deposit_account))
            paid = min(available, interest)
            if paid > self.ledger.tolerance:
                self.ledger.post(
                    tick=self.tick,
                    description=f"Consumer loan interest household {household.id}",
                    postings=[
                        Posting(household.deposit_account, -paid),
                        Posting(household.bank_deposit_liability, paid),
                    ],
                )
            unpaid = interest - paid
            if unpaid > self.ledger.tolerance:
                self.ledger.capitalize_interest(
                    tick=self.tick,
                    description=f"Capitalized consumer interest household {household.id}",
                    bank_loan_asset=household.bank_consumer_loan_asset,
                    borrower_loan_liability=household.consumer_loan_liability,
                    amount=unpaid,
                )

    def _repay_household_principal(self) -> None:
        rate = max(0.0, min(1.0, self.config.household_principal_repayment_rate))
        for household in self.households:
            debt = max(0.0, -self.ledger.balance(household.consumer_loan_liability))
            cash = max(0.0, self.ledger.balance(household.deposit_account))
            if debt <= self.ledger.tolerance or cash <= self.ledger.tolerance:
                continue
            buffer = max(250.0, 0.20 * max(household.permanent_income_estimate, household.wage))
            scheduled = debt * rate
            repayment = min(debt, scheduled, max(0.0, cash - buffer))
            if repayment <= self.ledger.tolerance:
                continue
            self.ledger.post(
                tick=self.tick,
                description=f"Consumer loan principal household {household.id}",
                postings=[
                    Posting(household.deposit_account, -repayment),
                    Posting(household.bank_deposit_liability, repayment),
                    Posting(household.consumer_loan_liability, repayment),
                    Posting(household.bank_consumer_loan_asset, -repayment),
                ],
            )

    def _handle_household_defaults(self) -> None:
        for household in self.households:
            debt = max(0.0, -self.ledger.balance(household.consumer_loan_liability))
            if debt <= self.ledger.tolerance:
                household.months_credit_distressed = 0
                continue
            cash = max(0.0, self.ledger.balance(household.deposit_account))
            income_anchor = max(1.0, household.permanent_income_estimate, household.wage * 0.30)
            distressed = household.employed_by is None and cash < 0.20 * income_anchor
            household.months_credit_distressed = household.months_credit_distressed + 1 if distressed else 0
            if household.months_credit_distressed < 4 or debt <= 4.0 * income_anchor:
                continue
            writeoff = debt * max(0.0, min(1.0, self.config.household_default_writeoff_ratio))
            if writeoff <= self.ledger.tolerance:
                continue
            self.ledger.write_off_loan(
                tick=self.tick,
                description=f"Consumer credit default household {household.id}",
                bank_loan_asset=household.bank_consumer_loan_asset,
                borrower_loan_liability=household.consumer_loan_liability,
                amount=writeoff,
            )
            household.credit_defaults += 1
            household.months_credit_distressed = 0
            self._month_household_defaults += 1
            self._month_default_losses += writeoff

    def _service_interest(self) -> None:
        self._service_household_interest()
        for firm in self.firms:
            debt = max(0.0, -self.ledger.balance(firm.loan_liability))
            if debt <= 1e-8:
                continue
            annual_rate = max(-0.05, self.central_bank.policy_rate + self.banks[firm.bank_id].spread)
            interest = debt * annual_rate / 12.0
            if interest <= 0:
                continue

            # Interest paid to the lending bank extinguishes part of the firm's
            # deposit. The bank's net financial worth rises because its loan asset
            # remains while its deposit liability falls. Equity is reported as the
            # residual of the sector balance sheet rather than a synthetic account.
            available = max(0.0, self.ledger.balance(firm.deposit_account))
            paid = min(available, interest)
            if paid > 0:
                self.ledger.post(
                    tick=self.tick,
                    description=f"Interest payment by firm {firm.id}",
                    postings=[
                        Posting(firm.deposit_account, -paid),
                        Posting(firm.bank_deposit_liability, paid),
                    ],
                )
            unpaid = interest - paid
            if unpaid > 1e-8:
                self.ledger.capitalize_interest(
                    tick=self.tick,
                    description=f"Capitalized interest for firm {firm.id}",
                    bank_loan_asset=firm.bank_loan_asset,
                    borrower_loan_liability=firm.loan_liability,
                    amount=unpaid,
                )

    def _labor_supply_state(self, household: Household) -> None:
        """Update participation, search effort and reservation wage for an unemployed household.

        This is a deliberately small labor-supply bridge. It is not a structural
        labor-leisure solver: benefits and liquid wealth can reduce search effort
        and raise the reservation wage, while the actual job match still occurs in
        the ABM labor market.
        """
        if household.employed_by is not None:
            household.labor_force_participating = True
            household.search_intensity = 0.0
            household.reservation_wage = 0.0
            return
        if self.config.labor_supply_mode == "inelastic":
            household.labor_force_participating = True
            household.search_intensity = 1.0
            household.reservation_wage = 0.0
            return

        deposit = max(0.0, self.ledger.balance(household.deposit_account))
        income_anchor = max(1.0, household.permanent_income_estimate, household.wage * (1.0 - self.config.income_tax_rate))
        benefit_ratio = max(0.0, min(1.5, household.last_unemployment_benefit / income_anchor))
        wealth_months = max(0.0, min(12.0, deposit / income_anchor))
        search = self.config.labor_search_intensity
        search *= max(0.05, 1.0 - self.config.benefit_search_disincentive * benefit_ratio)
        search *= max(0.05, 1.0 - self.config.wealth_search_disincentive * min(1.0, wealth_months / 6.0))
        household.search_intensity = max(0.0, min(1.0, search))
        household.labor_force_participating = household.search_intensity > 0.0
        household.reservation_wage = max(0.0, household.wage * self.config.reservation_wage_ratio * (1.0 + 0.25 * benefit_ratio + 0.03 * wealth_months))

    def _update_unemployment_spells(self) -> None:
        for household in self.households:
            if household.employed_by is None:
                household.unemployment_spell_months += 1
            else:
                if household.unemployment_spell_months > 0:
                    household.benefit_months_received = 0
                household.unemployment_spell_months = 0
                household.last_unemployment_benefit = 0.0
                household.last_transfer_income = 0.0

    def _adjust_labor(self) -> None:
        self._month_employed_at_start = sum(h.employed_by is not None for h in self.households)
        self._month_job_separations = 0
        self._month_job_matches = 0

        unemployed = [household for household in self.households if household.employed_by is None]
        self.random.shuffle(unemployed)

        # Firms with excess stock shrink modestly; firms that sold most of available
        # output seek workers. Job separations are counted explicitly so HARK can
        # use an observed transition risk rather than equating unemployment with a
        # monthly dismissal probability.
        vacancies: list[Firm] = []

        def separate(firm: Firm, household_id: int) -> None:
            if household_id not in firm.employees:
                return
            firm.employees.remove(household_id)
            household = self.households[household_id]
            household.employed_by = None
            household.job_separations += 1
            self._month_job_separations += 1
            unemployed.append(household)

        for firm in self.firms:
            capacity = max(1.0, len(firm.employees) * firm.productivity)
            inventory_months = firm.inventory / capacity
            if self.macro_demand_signal_pp < -0.50 and len(firm.employees) > 2 and self.config.firm_layoff_strength > 0:
                macro_layoffs = min(
                    max(1, int(len(firm.employees) * 0.005 * abs(self.macro_demand_signal_pp) * self.config.firm_layoff_strength)),
                    max(1, len(firm.employees) // 20),
                )
                for household_id in list(firm.employees)[:macro_layoffs]:
                    separate(firm, household_id)
            if inventory_months > 1.8 and len(firm.employees) > 1 and self.config.firm_layoff_strength > 0:
                layoffs = max(1, int(len(firm.employees) * 0.03 * self.config.firm_layoff_strength))
                for household_id in list(firm.employees)[:layoffs]:
                    separate(firm, household_id)
            elif self.tick > 1 and firm.last_units_sold >= 0.85 * capacity:
                base_vacancies = max(1, int(len(firm.employees) * 0.02 * self.config.firm_hiring_strength) or 1) if self.config.firm_hiring_strength > 0 else 0
                vacancies.extend([firm] * base_vacancies)
            if self.macro_demand_signal_pp > 0.50:
                extra = max(1, int(len(firm.employees) * 0.003 * self.macro_demand_signal_pp * self.config.firm_hiring_strength)) if self.config.firm_hiring_strength > 0 else 0
                vacancies.extend([firm] * extra)

        # Deduplicate workers who were already unemployed and were appended again
        # through a separation path.
        unemployed = list({household.id: household for household in unemployed if household.employed_by is None}.values())
        for household in unemployed:
            self._labor_supply_state(household)
        seekers = [
            household for household in unemployed
            if household.labor_force_participating and self.random.random() <= household.search_intensity
        ]
        self._month_job_seekers = len(seekers)
        self.random.shuffle(vacancies)
        self.random.shuffle(seekers)
        match_count = int(min(len(vacancies), len(seekers)) * self.config.labor_matching_efficiency)
        vacancies = vacancies[:match_count]
        seekers = seekers[:match_count]
        for firm, household in zip(vacancies, seekers):
            if household.employed_by is not None:
                continue
            if self.config.labor_supply_mode == "reservation_wage" and firm.wage_offer + 1e-9 < household.reservation_wage:
                continue
            household.employed_by = firm.id
            firm.employees.add(household.id)
            household.accepted_jobs += 1
            self._month_job_matches += 1

        self._update_unemployment_spells()
        observed = self._month_job_separations / max(1, self._month_employed_at_start)
        memory = max(0.01, min(1.0, self.config.job_separation_risk_memory))
        self._recent_job_separation_rate = (1.0 - memory) * self._recent_job_separation_rate + memory * observed

    def _produce_firm(self, firm: Firm) -> None:
        workers = len(firm.employees)
        if workers <= 0:
            return
        stochastic_productivity = self.random.uniform(0.98, 1.02)
        macro_factor = max(0.90, min(1.10, 1.0 + 0.0020 * self.macro_demand_signal_pp))
        productivity_factor = max(0.50, min(2.00, 1.0 + self.current_shocks.productivity_pct / 100.0))
        reference_capital = max(1.0, workers * self.config.initial_capital_per_worker)
        capital_intensity = max(0.05, firm.capital_stock / reference_capital)
        capital_factor = max(0.55, min(1.60, capital_intensity ** self.config.capital_output_elasticity))
        firm.inventory += (
            workers * firm.productivity * stochastic_productivity * macro_factor * productivity_factor * capital_factor
        )

    def _produce(self) -> None:
        self.activation_runtime.produce_firms()

    def _pay_wages_and_taxes(self) -> float:
        total_gross_wages = 0.0
        # Reset realized labor income each month. Without this, an unemployed
        # household would retain the previous month's wage as if it were current.
        for household in self.households:
            household.last_income = 0.0
            household.last_transfer_income = 0.0
            household.last_unemployment_benefit = 0.0
        tax_rate = self.config.income_tax_rate
        for firm in self.firms:
            payroll = sum(self.households[hid].wage for hid in firm.employees)
            self._ensure_deposit(firm, payroll)
            for household_id in list(firm.employees):
                household = self.households[household_id]
                gross = household.wage
                paid = self.ledger.transfer_deposit(
                    tick=self.tick,
                    description=f"Wage firm {firm.id} -> household {household.id}",
                    source_asset=firm.deposit_account,
                    source_bank_liability=firm.bank_deposit_liability,
                    destination_asset=household.deposit_account,
                    destination_bank_liability=household.bank_deposit_liability,
                    amount=gross,
                    target_reserve_ratio=self.financial_controls.target_reserve_ratio,
                )
                household.last_income = paid
                total_gross_wages += paid
                if paid <= 0:
                    continue
                tax = paid * tax_rate
                self.ledger.transfer_deposit(
                    tick=self.tick,
                    description=f"Income tax household {household.id}",
                    source_asset=household.deposit_account,
                    source_bank_liability=household.bank_deposit_liability,
                    destination_asset=self.government.deposit_account,
                    destination_bank_liability=self.government.bank_deposit_liability,
                    amount=tax,
                    target_reserve_ratio=self.financial_controls.target_reserve_ratio,
                )
        return total_gross_wages

    def _pay_unemployment_benefits(self) -> float:
        """Pay explicit unemployment transfers through the SFC ledger.

        Benefits are transfers, not government final consumption: they therefore
        do not enter G directly. They augment household deposits/resources and can
        subsequently affect consumption through the household decision engine.
        """
        if not self.config.unemployment_benefits_enabled or self.config.unemployment_benefit_max_months <= 0:
            return 0.0
        replacement = max(0.0, min(1.0, self.config.unemployment_benefit_replacement_rate))
        waiting = max(0, self.config.unemployment_benefit_waiting_months)
        maximum_months = max(0, self.config.unemployment_benefit_max_months)
        cap = max(0.0, self.config.unemployment_benefit_cap)
        scheduled: list[tuple[Household, float]] = []
        for household in self.households:
            if household.employed_by is not None:
                continue
            if household.unemployment_spell_months <= waiting:
                continue
            if household.benefit_months_received >= maximum_months:
                continue
            reference_income = max(1.0, household.wage, household.permanent_income_estimate / max(0.05, 1.0 - self.config.income_tax_rate))
            amount = reference_income * replacement
            if cap > 0:
                amount = min(amount, cap)
            if amount > self.ledger.tolerance:
                scheduled.append((household, amount))

        total_target = sum(amount for _, amount in scheduled)
        available = max(0.0, self.ledger.balance(self.government.deposit_account))
        if total_target > available:
            self._finance_government_shortfall(total_target - available)

        paid_total = 0.0
        for household, amount in scheduled:
            paid = self.ledger.transfer_deposit(
                tick=self.tick,
                description=f"Unemployment benefit government -> household {household.id}",
                source_asset=self.government.deposit_account,
                source_bank_liability=self.government.bank_deposit_liability,
                destination_asset=household.deposit_account,
                destination_bank_liability=household.bank_deposit_liability,
                amount=amount,
                target_reserve_ratio=self.financial_controls.target_reserve_ratio,
            )
            if paid <= self.ledger.tolerance:
                continue
            household.last_transfer_income += paid
            household.last_unemployment_benefit = paid
            household.benefit_months_received += 1
            paid_total += paid
        return paid_total

    def _consume_household(self, household: Household) -> float:
        active_firms = self._active_firms_for_consumption
        self._extend_household_credit(household)
        deposit = max(0.0, self.ledger.balance(household.deposit_account))
        # Compute the household decision even if the goods market has no active
        # sellers. For HARK this also synchronizes employment/income state.
        budget = self.consumption_policy.budget(
            household=household,
            deposit=deposit,
            income_tax_rate=self.config.income_tax_rate,
            annual_policy_rate=self.central_bank.policy_rate,
            aggregate_unemployment_rate=self._aggregate_unemployment_rate_for_consumption,
            observed_job_separation_rate=self._recent_job_separation_rate,
        )
        if not active_firms:
            household.last_consumption = 0.0
            return 0.0
        # Dynare output guidance is a marginal demand signal, not a target.
        demand_multiplier = max(0.80, min(1.20, 1.0 + 0.0035 * self.macro_demand_signal_pp))
        budget *= demand_multiplier

        # A small imported-consumption share settles against the explicit
        # rest-of-world deposit. Higher import costs reduce real import demand.
        import_share = self.config.base_import_share * max(
            0.20,
            min(2.00, 1.0 - 0.005 * self.current_shocks.import_cost_pct),
        )
        import_budget = min(deposit, budget * max(0.0, min(0.40, import_share)))
        import_paid = 0.0
        if import_budget > self.ledger.tolerance:
            import_paid = self.ledger.transfer_deposit(
                tick=self.tick,
                description=f"Imports household {household.id} -> rest of world",
                source_asset=household.deposit_account,
                source_bank_liability=household.bank_deposit_liability,
                destination_asset=self.rest_of_world.deposit_account,
                destination_bank_liability=self.rest_of_world.bank_deposit_liability,
                amount=import_budget,
                target_reserve_ratio=self.financial_controls.target_reserve_ratio,
            )
            self._month_imports += import_paid

        updated_deposit = max(0.0, self.ledger.balance(household.deposit_account))
        remaining = min(updated_deposit, max(0.0, budget - import_paid))
        spent = import_paid

        for _ in range(3):
            if remaining <= 0.01 or not active_firms:
                break
            sample_size = min(self.config.household_shopping_sample_size, len(active_firms))
            candidates = self.random.sample(active_firms, sample_size)
            available = [firm for firm in candidates if firm.inventory > 1e-8]
            if not available:
                continue
            if self.random.random() <= self.config.household_cheapest_choice_probability:
                firm = min(available, key=lambda item: item.price)
            else:
                firm = self.random.choice(available)
            purchase_value = min(remaining, firm.inventory * firm.price)
            paid = self.ledger.transfer_deposit(
                tick=self.tick,
                description=f"Consumption household {household.id} -> firm {firm.id}",
                source_asset=household.deposit_account,
                source_bank_liability=household.bank_deposit_liability,
                destination_asset=firm.deposit_account,
                destination_bank_liability=firm.bank_deposit_liability,
                amount=purchase_value,
                target_reserve_ratio=self.financial_controls.target_reserve_ratio,
            )
            if paid <= 0:
                break
            actual_units = paid / firm.price
            firm.inventory = max(0.0, firm.inventory - actual_units)
            firm.last_units_sold += actual_units
            firm.last_revenue += paid
            remaining -= paid
            spent += paid

        household.last_consumption = spent
        self._month_consumption += spent
        return spent

    def _consume(self) -> float:
        self._month_consumption = 0.0
        employed = sum(household.employed_by is not None for household in self.households)
        active_unemployed = sum(
            household.employed_by is None and household.labor_force_participating
            for household in self.households
        )
        self._aggregate_unemployment_rate_for_consumption = active_unemployed / max(1, employed + active_unemployed)
        self._active_firms_for_consumption = [
            firm for firm in self.firms if firm.inventory > 1e-8
        ]
        if self._active_firms_for_consumption:
            self.activation_runtime.consume_households()
        self._active_firms_for_consumption = []
        return self._month_consumption

    def _finance_government_shortfall(self, amount: float) -> None:
        if amount <= 0:
            return
        bank = self.banks[self.government.bank_id]
        self.ledger.post(
            tick=self.tick,
            description="Simplified government deficit financing",
            postings=[
                Posting(self.government.debt_liability, -amount),
                Posting(self.central_bank.government_bond_asset, amount),
                Posting(self.government.deposit_account, amount),
                Posting(self.government.bank_deposit_liability, -amount),
                Posting(bank.reserve_asset, amount),
                Posting(self.central_bank.reserve_liability(bank.id), -amount),
            ],
        )

    def _external_demand(self, gross_wages: float) -> float:
        """Rest-of-world purchases from domestic firms (exports)."""
        multiplier = max(0.0, 1.0 + self.current_shocks.external_demand_pct / 100.0)
        target = max(0.0, gross_wages * self.config.base_export_share * multiplier)
        available_cash = max(0.0, self.ledger.balance(self.rest_of_world.deposit_account))
        remaining = min(target, available_cash)
        exported = 0.0
        firms = [firm for firm in self.firms if firm.inventory > 1e-8]
        self.random.shuffle(firms)
        for firm in firms:
            if remaining <= 0.01:
                break
            purchase = min(
                remaining,
                firm.inventory * firm.price,
                target / max(1, len(firms) // 3),
            )
            paid = self.ledger.transfer_deposit(
                tick=self.tick,
                description=f"Exports firm {firm.id} -> rest of world",
                source_asset=self.rest_of_world.deposit_account,
                source_bank_liability=self.rest_of_world.bank_deposit_liability,
                destination_asset=firm.deposit_account,
                destination_bank_liability=firm.bank_deposit_liability,
                amount=purchase,
                target_reserve_ratio=self.financial_controls.target_reserve_ratio,
            )
            if paid <= 0:
                continue
            units = paid / firm.price
            firm.inventory = max(0.0, firm.inventory - units)
            firm.last_units_sold += units
            firm.last_revenue += paid
            remaining -= paid
            exported += paid
        return exported

    def _government_demand(self, gross_wages: float) -> float:
        fiscal_multiplier = 1.0 + self.config.public_spending_change + self.current_shocks.fiscal_spending_pct / 100.0
        target = max(0.0, gross_wages * 0.20 * max(0.0, fiscal_multiplier))
        available = max(0.0, self.ledger.balance(self.government.deposit_account))
        if target > available:
            self._finance_government_shortfall(target - available)

        remaining = target
        spent = 0.0
        firms = self.firms[:]
        self.random.shuffle(firms)
        for firm in firms:
            if remaining <= 0.01:
                break
            if firm.inventory <= 1e-8:
                continue
            purchase = min(remaining, firm.inventory * firm.price, target / max(1, len(firms) // 3))
            paid = self.ledger.transfer_deposit(
                tick=self.tick,
                description=f"Government procurement from firm {firm.id}",
                source_asset=self.government.deposit_account,
                source_bank_liability=self.government.bank_deposit_liability,
                destination_asset=firm.deposit_account,
                destination_bank_liability=firm.bank_deposit_liability,
                amount=purchase,
                target_reserve_ratio=self.financial_controls.target_reserve_ratio,
            )
            if paid <= 0:
                continue
            units = paid / firm.price
            firm.inventory = max(0.0, firm.inventory - units)
            firm.last_units_sold += units
            firm.last_revenue += paid
            remaining -= paid
            spent += paid
        return spent

    def _business_investment(self) -> float:
        total = 0.0
        if self.config.firm_investment_propensity <= 0 or self.config.capital_unit_cost <= 0:
            return total
        buyers = self.firms[:]
        self.random.shuffle(buyers)
        for buyer in buyers:
            replacement_value = buyer.last_depreciation * self.config.capital_unit_cost
            expansion_value = max(0.0, buyer.last_revenue) * self.config.firm_investment_propensity
            target = replacement_value + expansion_value
            if target <= self.ledger.tolerance:
                continue
            self._ensure_deposit(buyer, target)
            available_cash = max(0.0, self.ledger.balance(buyer.deposit_account))
            remaining = min(target, max(0.0, available_cash * 0.30))
            sellers = [firm for firm in self.firms if firm.id != buyer.id and firm.inventory > 1e-8]
            self.random.shuffle(sellers)
            for seller in sellers:
                if remaining <= self.ledger.tolerance:
                    break
                purchase = min(remaining, seller.inventory * seller.price)
                paid = self.ledger.transfer_deposit(
                    tick=self.tick,
                    description=f"Capital investment firm {buyer.id} <- firm {seller.id}",
                    source_asset=buyer.deposit_account,
                    source_bank_liability=buyer.bank_deposit_liability,
                    destination_asset=seller.deposit_account,
                    destination_bank_liability=seller.bank_deposit_liability,
                    amount=purchase,
                    target_reserve_ratio=self.financial_controls.target_reserve_ratio,
                )
                if paid <= self.ledger.tolerance:
                    continue
                goods_units = paid / max(seller.price, 1e-8)
                seller.inventory = max(0.0, seller.inventory - goods_units)
                seller.last_units_sold += goods_units
                seller.last_revenue += paid
                acquired_capital = paid / self.config.capital_unit_cost
                buyer.capital_stock += acquired_capital
                buyer.last_investment += paid
                total += paid
                remaining -= paid
        return total

    def _repay_principal(self) -> None:
        for firm in self.firms:
            debt = max(0.0, -self.ledger.balance(firm.loan_liability))
            cash = max(0.0, self.ledger.balance(firm.deposit_account))
            if debt <= 0 or cash <= 0:
                continue
            # Firms preserve a liquidity buffer and amortize only excess cash.
            buffer = max(2.0 * firm.wage_offer * max(1, len(firm.employees)), 20_000.0)
            repayment = min(debt, max(0.0, cash - buffer) * 0.25)
            if repayment <= 0:
                continue
            self.ledger.post(
                tick=self.tick,
                description=f"Principal repayment by firm {firm.id}",
                postings=[
                    Posting(firm.deposit_account, -repayment),
                    Posting(firm.bank_deposit_liability, repayment),
                    Posting(firm.loan_liability, repayment),
                    Posting(firm.bank_loan_asset, -repayment),
                ],
            )

    def _handle_defaults(self) -> None:
        for firm in self.firms:
            debt = max(0.0, -self.ledger.balance(firm.loan_liability))
            if debt <= 0:
                continue
            revenue_anchor = max(firm.last_revenue, 1.0)
            cash = max(0.0, self.ledger.balance(firm.deposit_account))
            if debt > 36.0 * revenue_anchor and cash < firm.wage_offer:
                # In the MVP we restructure/write off 35% rather than remove the firm,
                # keeping population sizes stable for comparison across scenarios.
                writeoff = debt * self.financial_controls.default_writeoff_ratio
                self.ledger.write_off_loan(
                    tick=self.tick,
                    description=f"Partial default firm {firm.id}",
                    bank_loan_asset=firm.bank_loan_asset,
                    borrower_loan_liability=firm.loan_liability,
                    amount=writeoff,
                )
                firm.defaults += 1
                self._month_defaults += 1
                self._month_default_losses += writeoff

    def _public_recapitalize_bank(self, bank: Bank, amount: float) -> float:
        amount = max(0.0, amount)
        if amount <= self.ledger.tolerance:
            return 0.0
        self.ledger.post(
            tick=self.tick,
            description=f"Public recapitalization bank {bank.id}",
            postings=[
                Posting(bank.reserve_asset, amount),
                Posting(self.central_bank.reserve_liability(bank.id), -amount),
                Posting(self.central_bank.government_bond_asset, amount),
                Posting(self.government.debt_liability, -amount),
            ],
        )
        self._month_public_recapitalization += amount
        return amount

    def _bail_in_bank(self, bank: Bank, amount: float) -> float:
        remaining = max(0.0, amount)
        if remaining <= self.ledger.tolerance:
            return 0.0
        accounts: list[tuple[str, str, float]] = []
        for household in self.households:
            if household.bank_id != bank.id:
                continue
            balance = max(0.0, self.ledger.balance(household.deposit_account))
            eligible = max(0.0, balance - self.config.bail_in_household_protection)
            if eligible > self.ledger.tolerance:
                accounts.append((household.deposit_account, household.bank_deposit_liability, eligible))
        for firm in self.firms:
            if firm.bank_id != bank.id:
                continue
            balance = max(0.0, self.ledger.balance(firm.deposit_account))
            eligible = max(0.0, balance - self.config.bail_in_firm_protection)
            if eligible > self.ledger.tolerance:
                accounts.append((firm.deposit_account, firm.bank_deposit_liability, eligible))
        total_eligible = sum(item[2] for item in accounts)
        haircut_total = min(remaining, total_eligible)
        if haircut_total <= self.ledger.tolerance:
            return 0.0
        applied = 0.0
        for asset, liability, eligible in accounts:
            haircut = haircut_total * eligible / total_eligible
            if haircut <= self.ledger.tolerance:
                continue
            self.ledger.post(
                tick=self.tick,
                description=f"Bank {bank.id} bail-in deposit haircut",
                postings=[Posting(asset, -haircut), Posting(liability, haircut)],
            )
            applied += haircut
        self._month_bail_in_losses += applied
        return applied

    def _resolve_banks(self) -> None:
        mode = self.config.bank_resolution_mode
        if mode == "none":
            return
        for bank in self.banks:
            report = bank_financials(self.ledger, bank.id)
            trigger = self.config.bank_resolution_trigger_ratio
            if report.regulatory_capital >= 0 and report.capital_ratio >= trigger:
                continue
            target_capital = self.config.bank_resolution_target_ratio * max(report.risk_weighted_assets, 1.0)
            needed = max(0.0, target_capital - report.regulatory_capital)
            if needed <= self.ledger.tolerance:
                continue
            resolution_mode = mode
            if mode == "bail_in":
                absorbed = self._bail_in_bank(bank, needed)
                remaining = max(0.0, needed - absorbed)
                if remaining > self.ledger.tolerance:
                    self._public_recapitalize_bank(bank, remaining)
                    resolution_mode = "bail_in+public_backstop"
            else:
                self._public_recapitalize_bank(bank, needed)
            bank.resolutions += 1
            bank.last_resolution_mode = resolution_mode
            self._month_bank_resolutions += 1

    def _service_bank_liquidity(self) -> None:
        interbank_rate = max(0.0, self.central_bank.policy_rate + self.financial_controls.interbank_spread)
        central_bank_rate = max(
            0.0, self.central_bank.policy_rate + self.financial_controls.central_bank_penalty_spread
        )
        for bank in self.banks:
            self.ledger.service_interbank_positions(
                tick=self.tick,
                borrower_id=bank.id,
                annual_rate=interbank_rate,
                target_reserve_ratio=self.financial_controls.target_reserve_ratio,
            )
            self.ledger.service_central_bank_advance(
                tick=self.tick,
                bank_id=bank.id,
                annual_rate=central_bank_rate,
                target_reserve_ratio=self.financial_controls.target_reserve_ratio,
            )

    def _update_price_firm(self, firm: Firm) -> None:
        capacity = max(1.0, len(firm.employees) * firm.productivity)
        stock_ratio = firm.inventory / capacity
        utilization = firm.last_units_sold / capacity
        adjustment = 0.0
        if utilization > 0.95 and stock_ratio < 0.4:
            adjustment += 0.010
        elif stock_ratio > 1.8:
            adjustment -= 0.006
        # Financing costs transmit policy rates weakly into markups.
        debt = max(0.0, -self.ledger.balance(firm.loan_liability))
        if debt > 0:
            adjustment += min(
                0.0025,
                debt
                / max(1.0, firm.last_revenue + 100_000.0)
                * self.central_bank.policy_rate
                / 12,
            )
        # Convert annualized p.p. price guidance into a deliberately weak monthly
        # pricing signal. Firms still set realized prices endogenously.
        adjustment += (self.macro_inflation_signal_pp / 100.0 / 12.0) * 0.25
        adjustment += (self.current_shocks.cost_push_pct / 100.0 / 12.0) * 0.50
        adjustment += (self.current_shocks.import_cost_pct / 100.0 / 12.0) * 0.12
        adjustment *= self.config.firm_price_adjustment_strength
        firm.price = max(self.config.base_price * 0.35, firm.price * (1 + adjustment))

    def _update_prices(self) -> None:
        self.activation_runtime.update_firm_prices()

    def _collect_metrics(self) -> MonthMetrics:
        price_index = fmean(firm.price for firm in self.firms)
        self.price_history.append(price_index)
        nominal_final_demand = (
            self._month_consumption + self._month_government_spending + self._month_business_investment
            + self._month_exports - self._month_imports
        )
        real_final_demand = nominal_final_demand / max(price_index, 1e-8)
        if self.real_gdp_baseline is None:
            self.real_gdp_baseline = max(real_final_demand, 1e-8)
        gdp_index = 100.0 * real_final_demand / self.real_gdp_baseline

        if len(self.price_history) >= 13:
            previous = self.price_history[-13]
            inflation = 100.0 * (price_index / previous - 1.0)
        elif len(self.price_history) >= 2:
            previous = self.price_history[-2]
            monthly = price_index / previous - 1.0
            inflation = 100.0 * ((1.0 + monthly) ** 12 - 1.0)
        else:
            inflation = 0.0

        employed = sum(household.employed_by is not None for household in self.households)
        active_unemployed = sum(
            household.employed_by is None and household.labor_force_participating
            for household in self.households
        )
        labor_force = employed + active_unemployed
        unemployment = 100.0 * active_unemployed / max(1, labor_force)
        labor_force_participation = 100.0 * labor_force / max(1, len(self.households))
        job_separation_rate = 100.0 * self._month_job_separations / max(1, self._month_employed_at_start)
        job_finding_rate = 100.0 * self._month_job_matches / max(1, self._month_job_seekers)
        corporate_debt = sum(
            max(0.0, -self.ledger.balance(firm.loan_liability)) for firm in self.firms
        )
        household_debt = sum(
            max(0.0, -self.ledger.balance(household.consumer_loan_liability)) for household in self.households
        )
        corporate_credit = sum(max(0.0, self.ledger.balance(firm.bank_loan_asset)) for firm in self.firms)
        household_credit = sum(max(0.0, self.ledger.balance(household.bank_consumer_loan_asset)) for household in self.households)
        bank_credit = corporate_credit + household_credit
        productive_capital = sum(max(0.0, firm.capital_stock) for firm in self.firms)
        deposits = sum(max(0.0, self.ledger.balance(h.deposit_account)) for h in self.households)
        deposits += sum(max(0.0, self.ledger.balance(f.deposit_account)) for f in self.firms)
        wealth = [
            max(0.0, self.ledger.balance(h.deposit_account))
            + max(0.0, self.ledger.balance(h.bank_equity_asset))
            for h in self.households
        ]
        bank_reserves = sum(max(0.0, self.ledger.balance(bank.reserve_asset)) for bank in self.banks)
        central_bank_advances = sum(
            max(0.0, self.ledger.balance(self.central_bank.advance_asset(bank.id)))
            for bank in self.banks
        )
        government_debt = max(0.0, -self.ledger.balance(self.government.debt_liability))
        balance_sheets = {item.sector: item for item in sector_balance_sheets(self.ledger)}
        private_net_financial_wealth = (
            balance_sheets["households"].net_financial_worth
            + balance_sheets["firms"].net_financial_worth
        )
        bank_reports = [bank_financials(self.ledger, bank.id) for bank in self.banks]
        bank_capital = sum(item.regulatory_capital for item in bank_reports)
        bank_capital_ratio = aggregate_capital_ratio(bank_reports)
        undercapitalized_banks = sum(
            not item.compliant(self.financial_controls.minimum_capital_ratio) for item in bank_reports
        )
        interbank_credit = sum(item.interbank_assets for item in bank_reports)

        return MonthMetrics(
            month=self.tick,
            gdp_index=gdp_index,
            price_index=price_index,
            inflation=inflation,
            unemployment=unemployment,
            policy_rate=100.0 * self.central_bank.policy_rate,
            household_consumption=self._month_consumption,
            government_spending=self._month_government_spending,
            corporate_debt=corporate_debt,
            bank_credit=bank_credit,
            bank_deposits=deposits,
            gini_wealth=gini(wealth),
            firm_defaults=self._month_defaults,
            bank_reserves=bank_reserves,
            central_bank_advances=central_bank_advances,
            government_debt=government_debt,
            private_net_financial_wealth=private_net_financial_wealth,
            bank_capital=bank_capital,
            bank_capital_ratio=bank_capital_ratio,
            undercapitalized_banks=undercapitalized_banks,
            interbank_credit=interbank_credit,
            bank_profit_loss=self._month_bank_profit_loss,
            credit_rationed=self._month_credit_rationed,
            default_losses=self._month_default_losses,
            exports=self._month_exports,
            imports=self._month_imports,
            net_exports=self._month_exports - self._month_imports,
            business_investment=self._month_business_investment,
            productive_capital=productive_capital,
            household_debt=household_debt,
            household_credit=household_credit,
            household_defaults=self._month_household_defaults,
            bank_resolutions=self._month_bank_resolutions,
            public_recapitalization=self._month_public_recapitalization,
            bail_in_losses=self._month_bail_in_losses,
            unemployment_benefits=self._month_unemployment_benefits,
            labor_force_participation=labor_force_participation,
            job_separation_rate=job_separation_rate,
            job_finding_rate=job_finding_rate,
            active_shocks=self.current_shocks.as_dict(),
        )

    def step(self) -> MonthMetrics:
        self.tick += 1
        self.current_shocks = self.shock_runtime.state_for_month(self.tick)
        self._refresh_financial_controls()
        self._month_consumption = 0.0
        self._month_government_spending = 0.0
        self._month_defaults = 0
        self._month_credit_rationed = 0.0
        self._month_default_losses = 0.0
        self._month_exports = 0.0
        self._month_imports = 0.0
        self._month_business_investment = 0.0
        self._month_household_defaults = 0
        self._month_bank_resolutions = 0
        self._month_public_recapitalization = 0.0
        self._month_bail_in_losses = 0.0
        self._month_unemployment_benefits = 0.0
        self._month_job_separations = 0
        self._month_job_matches = 0
        self._month_job_seekers = 0
        self._month_employed_at_start = 0
        opening_bank_capital = sum(
            bank_financials(self.ledger, bank.id).regulatory_capital for bank in self.banks
        )
        self._service_interest()
        self._adjust_labor()
        self._depreciate_productive_capital()
        self._produce()
        gross_wages = self._pay_wages_and_taxes()
        self._month_unemployment_benefits = self._pay_unemployment_benefits()
        # Previous-month sales are needed by labor and working-capital rules above.
        # Reset only when the current goods market is about to open.
        for firm in self.firms:
            firm.last_units_sold = 0.0
            firm.last_revenue = 0.0
        self._month_government_spending = self._government_demand(gross_wages)
        self._month_consumption = self._consume()
        self._month_exports = self._external_demand(gross_wages)
        self._month_business_investment = self._business_investment()
        self._repay_principal()
        self._repay_household_principal()
        self._handle_defaults()
        self._handle_household_defaults()
        self._resolve_banks()
        self._service_bank_liquidity()
        ending_bank_capital = sum(
            bank_financials(self.ledger, bank.id).regulatory_capital for bank in self.banks
        )
        self._month_bank_profit_loss = ending_bank_capital - opening_bank_capital
        self._update_prices()
        assert_sector_accounting(self.ledger, tick=self.tick)
        return self._collect_metrics()

    def run(self, months: int) -> list[MonthMetrics]:
        if months < 1:
            raise ValueError("months must be >= 1")
        return [self.step() for _ in range(months)]
