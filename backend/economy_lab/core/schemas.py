from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthResponse(BaseModel):
    status: str
    engine_version: str
    mesa_available: bool = False
    hark_available: bool = False
    minsky_rest_configured: bool = False
    dynare_ready: bool = False
    runtime_mode: str = "web-local"
    runtime_instance: str | None = None


class EconomicShockSpec(BaseModel):
    kind: Literal[
        "fiscal_spending",
        "productivity",
        "cost_push",
        "external_demand",
        "import_cost",
    ]
    start_month: int = Field(default=1, ge=1, le=240)
    duration_months: int = Field(default=3, ge=1, le=240)
    magnitude_pct: float = Field(ge=-100.0, le=300.0)
    label: str = Field(default="", max_length=120)


class ScenarioDraftRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    base: "ScenarioSpec | None" = None


class ScenarioDraftResponse(BaseModel):
    compiler: str = "safe-local-parser-v1.0"
    requires_review: bool = True
    recognized_changes: list[str]
    assumptions: list[str]
    spec: "ScenarioSpec"


class FinancialGuidancePoint(BaseModel):
    month: int = Field(ge=1, le=240)
    minimum_bank_capital_ratio: float = Field(default=8.0, ge=0, le=30)
    target_reserve_ratio: float = Field(default=10.0, ge=0, le=100)
    credit_supply_factor: float = Field(default=1.0, ge=0.05, le=1.0)
    default_writeoff_ratio: float = Field(default=35.0, ge=0, le=100)
    interbank_spread: float = Field(default=1.0, ge=0, le=20)
    central_bank_penalty_spread: float = Field(default=2.0, ge=0, le=30)
    household_credit_enabled: bool = True
    household_credit_income_multiple: float = Field(default=0.50, ge=0.0, le=5.0)
    household_credit_liquidity_target_months: float = Field(default=3.0, ge=0.0, le=12.0)
    household_credit_spread: float = Field(default=6.0, ge=0.0, le=50.0)
    household_principal_repayment_rate: float = Field(default=4.0, ge=0.0, le=100.0)
    household_default_writeoff_ratio: float = Field(default=50.0, ge=0.0, le=100.0)
    bank_resolution_mode: Literal["none", "government_recapitalization", "bail_in"] = "government_recapitalization"
    bank_resolution_trigger_ratio: float = Field(default=2.0, ge=-50.0, le=30.0)
    bank_resolution_target_ratio: float = Field(default=10.0, ge=0.0, le=50.0)
    bail_in_household_protection: float = Field(default=2000.0, ge=0.0, le=1_000_000.0)
    bail_in_firm_protection: float = Field(default=20_000.0, ge=0.0, le=10_000_000.0)


class DataProvenanceRecord(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    series_id: str = Field(min_length=1, max_length=160)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_at: str | None = Field(default=None, max_length=80)
    observation_start: str | None = Field(default=None, max_length=40)
    observation_end: str | None = Field(default=None, max_length=40)
    frequency: str | None = Field(default=None, max_length=40)
    units: str | None = Field(default=None, max_length=80)


class ScenarioSpec(BaseModel):
    """Validated contract between UI/AI and the simulation kernel."""

    name: str = Field(default="Economy Zero", min_length=1, max_length=80)
    months: int = Field(default=24, ge=1, le=240)
    initial_gdp: float = Field(default=100.0, gt=0)
    initial_inflation: float = Field(default=4.0, ge=-20, le=100)
    initial_unemployment: float = Field(default=7.0, ge=0, le=100)
    policy_rate: float = Field(default=10.0, ge=-10, le=100)
    income_tax: float = Field(default=20.0, ge=0, le=100)
    public_spending_change: float = Field(default=0.0, ge=-50, le=100)
    households: int = Field(default=5000, ge=100, le=100_000)
    firms: int = Field(default=100, ge=5, le=5_000)
    banks: int = Field(default=3, ge=1, le=50)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    mode: Literal["demo", "economy_zero"] = "economy_zero"
    activation_engine: Literal["native", "mesa"] = "native"
    mesa_activation_pattern: Literal["random", "fixed"] = "random"
    household_shopping_sample_size: int = Field(default=4, ge=1, le=20)
    household_cheapest_choice_probability: float = Field(default=1.0, ge=0.0, le=1.0)
    firm_price_adjustment_strength: float = Field(default=1.0, ge=0.1, le=3.0)
    firm_hiring_strength: float = Field(default=1.0, ge=0.0, le=3.0)
    firm_layoff_strength: float = Field(default=1.0, ge=0.0, le=3.0)
    labor_matching_efficiency: float = Field(default=1.0, ge=0.0, le=1.0)
    initial_capital_per_worker: float = Field(default=1200.0, ge=0.0, le=1_000_000.0)
    capital_unit_cost: float = Field(default=25.0, gt=0.0, le=1_000_000.0)
    annual_capital_depreciation_rate: float = Field(default=8.0, ge=0.0, le=100.0)
    firm_investment_propensity: float = Field(default=12.0, ge=0.0, le=100.0)
    capital_output_elasticity: float = Field(default=0.30, ge=0.0, le=1.0)
    household_behavior: Literal["heuristic", "hark"] = "heuristic"
    minimum_bank_capital_ratio: float = Field(default=8.0, ge=0, le=30)
    target_reserve_ratio: float = Field(default=10.0, ge=0, le=100)
    financial_engine: Literal["native", "minsky_profile"] = "native"
    bank_credit_supply_factor: float = Field(default=1.0, ge=0.05, le=1.0)
    default_writeoff_ratio: float = Field(default=35.0, ge=0, le=100)
    interbank_spread: float = Field(default=1.0, ge=0, le=20)
    central_bank_penalty_spread: float = Field(default=2.0, ge=0, le=30)
    household_credit_enabled: bool = True
    household_credit_income_multiple: float = Field(default=0.50, ge=0.0, le=5.0)
    household_credit_liquidity_target_months: float = Field(default=3.0, ge=0.0, le=12.0)
    household_credit_spread: float = Field(default=6.0, ge=0.0, le=50.0)
    household_principal_repayment_rate: float = Field(default=4.0, ge=0.0, le=100.0)
    household_default_writeoff_ratio: float = Field(default=50.0, ge=0.0, le=100.0)
    bank_resolution_mode: Literal["none", "government_recapitalization", "bail_in"] = "government_recapitalization"
    bank_resolution_trigger_ratio: float = Field(default=2.0, ge=-50.0, le=30.0)
    bank_resolution_target_ratio: float = Field(default=10.0, ge=0.0, le=50.0)
    bail_in_household_protection: float = Field(default=2000.0, ge=0.0, le=1_000_000.0)
    bail_in_firm_protection: float = Field(default=20_000.0, ge=0.0, le=10_000_000.0)
    financial_guidance: list[FinancialGuidancePoint] = Field(default_factory=list, max_length=240)
    macro_engine: Literal["off", "dynare"] = "off"
    dynare_monetary_shock_bp: float = Field(default=100.0, gt=0, le=2000)
    dynare_irf_periods: int = Field(default=24, ge=1, le=160)
    dynare_neutral_nominal_rate: float = Field(default=8.0, ge=-5, le=100)
    dynare_beta: float = Field(default=0.99, gt=0.8, lt=1.0)
    dynare_sigma: float = Field(default=1.0, gt=0.01, le=20)
    dynare_kappa: float = Field(default=0.10, gt=0, le=5)
    dynare_rho_i: float = Field(default=0.80, ge=0, lt=1)
    dynare_phi_pi: float = Field(default=1.50, ge=0, le=10)
    dynare_phi_x: float = Field(default=0.25, ge=-5, le=5)
    hark_crra: float = Field(default=2.0, gt=0.05, le=20)
    hark_annual_discount_factor: float = Field(default=0.96, gt=0.5, lt=1.0)
    hark_state_mode: Literal["normalized", "employment_income"] = "employment_income"
    hark_unemployment_probability: float = Field(default=0.05, ge=0.001, le=0.50)
    hark_unemployment_replacement_rate: float = Field(default=0.30, ge=0.0, le=1.0)
    hark_permanent_shock_std: float = Field(default=0.04, ge=0.0, le=1.0)
    hark_transitory_shock_std: float = Field(default=0.10, ge=0.0, le=2.0)
    hark_permanent_income_memory: float = Field(default=0.18, gt=0.0, le=1.0)
    hark_income_groups: int = Field(default=5, ge=1, le=10)
    hark_income_risk_dispersion: float = Field(default=0.35, ge=0.0, le=1.0)
    unemployment_benefits_enabled: bool = True
    unemployment_benefit_replacement_rate: float = Field(default=45.0, ge=0.0, le=100.0)
    unemployment_benefit_waiting_months: int = Field(default=1, ge=0, le=12)
    unemployment_benefit_max_months: int = Field(default=6, ge=0, le=36)
    unemployment_benefit_cap: float = Field(default=3500.0, ge=0.0, le=100_000.0)
    labor_supply_mode: Literal["inelastic", "reservation_wage"] = "reservation_wage"
    labor_search_intensity: float = Field(default=0.90, ge=0.0, le=1.0)
    reservation_wage_ratio: float = Field(default=0.75, ge=0.0, le=2.0)
    benefit_search_disincentive: float = Field(default=0.20, ge=0.0, le=1.0)
    wealth_search_disincentive: float = Field(default=0.10, ge=0.0, le=1.0)
    job_separation_risk_memory: float = Field(default=0.25, ge=0.01, le=1.0)
    macro_coupling: Literal["advisory", "hybrid"] = "advisory"
    macro_coupling_strength: float = Field(default=0.35, ge=0.0, le=1.0)
    macro_feedback_strength: float = Field(default=0.15, ge=0.0, le=1.0)
    macro_recalibration: Literal["static_irf", "quarterly"] = "static_irf"
    macro_recalibration_strength: float = Field(default=0.25, ge=0.0, le=1.0)
    macro_max_recalibrations: int = Field(default=80, ge=0, le=80)
    shocks: list[EconomicShockSpec] = Field(default_factory=list, max_length=12)
    applied_profiles: dict[str, str] = Field(default_factory=dict)
    data_provenance: list[DataProvenanceRecord] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_population_structure(self):
        if self.firms >= self.households:
            raise ValueError("firms must be fewer than households in Economy Zero")
        if self.macro_engine == "off" and self.macro_coupling == "hybrid":
            raise ValueError("hybrid macro coupling requires macro_engine=dynare")
        if self.macro_recalibration == "quarterly" and not (
            self.macro_engine == "dynare" and self.macro_coupling == "hybrid"
        ):
            raise ValueError("quarterly macro recalibration requires Dynare hybrid coupling")
        allowed_profile_kinds = {"macro", "financial", "agents", "households", "households_market", "firms", "labor_market"}
        if any(key not in allowed_profile_kinds for key in self.applied_profiles):
            raise ValueError("applied_profiles contains an unsupported profile kind")
        provenance_keys = [
            (item.source_id, item.series_id, item.content_hash)
            for item in self.data_provenance
        ]
        if len(provenance_keys) != len(set(provenance_keys)):
            raise ValueError("data_provenance entries must be unique")
        for shock in self.shocks:
            if shock.start_month > self.months:
                raise ValueError("shock start_month must be within the simulation horizon")
            if shock.start_month + shock.duration_months - 1 > self.months:
                raise ValueError("shock duration extends beyond the simulation horizon")
        if self.bank_resolution_mode != "none" and self.bank_resolution_target_ratio <= self.bank_resolution_trigger_ratio:
            raise ValueError("bank_resolution_target_ratio must exceed the trigger ratio")
        if self.financial_guidance:
            months = [point.month for point in self.financial_guidance]
            if months != sorted(months) or len(months) != len(set(months)):
                raise ValueError("financial_guidance months must be unique and sorted")
            if months[-1] > self.months:
                raise ValueError("financial_guidance extends beyond the simulation horizon")
            if self.financial_engine != "minsky_profile":
                raise ValueError("financial_guidance requires financial_engine=minsky_profile")
        return self


class TimePoint(BaseModel):
    month: int
    gdp_index: float
    inflation: float
    unemployment: float
    policy_rate: float
    price_index: float | None = None
    household_consumption: float | None = None
    government_spending: float | None = None
    corporate_debt: float | None = None
    bank_credit: float | None = None
    bank_deposits: float | None = None
    gini_wealth: float | None = None
    firm_defaults: int | None = None
    bank_reserves: float | None = None
    central_bank_advances: float | None = None
    government_debt: float | None = None
    private_net_financial_wealth: float | None = None
    bank_capital: float | None = None
    bank_capital_ratio: float | None = None
    undercapitalized_banks: int | None = None
    interbank_credit: float | None = None
    bank_profit_loss: float | None = None
    credit_rationed: float | None = None
    default_losses: float | None = None
    exports: float | None = None
    imports: float | None = None
    net_exports: float | None = None
    business_investment: float | None = None
    productive_capital: float | None = None
    household_debt: float | None = None
    household_credit: float | None = None
    household_defaults: int | None = None
    bank_resolutions: int | None = None
    public_recapitalization: float | None = None
    bail_in_losses: float | None = None
    unemployment_benefits: float | None = None
    labor_force_participation: float | None = None
    job_separation_rate: float | None = None
    job_finding_rate: float | None = None
    active_shocks: dict[str, float] | None = None


class SimulationSummary(BaseModel):
    final_gdp_index: float
    final_inflation: float
    final_unemployment: float
    final_corporate_debt: float = 0.0
    final_bank_credit: float = 0.0
    final_gini_wealth: float = 0.0
    cumulative_defaults: int = 0
    ledger_balanced: bool = True
    final_bank_reserves: float = 0.0
    final_central_bank_advances: float = 0.0
    final_government_debt: float = 0.0
    final_private_net_financial_wealth: float = 0.0
    godley_stocks_balanced: bool = True
    godley_flows_balanced: bool = True
    final_bank_capital: float = 0.0
    final_bank_capital_ratio: float = 0.0
    final_undercapitalized_banks: int = 0
    final_interbank_credit: float = 0.0
    cumulative_bank_profit_loss: float = 0.0
    cumulative_credit_rationed: float = 0.0
    cumulative_default_losses: float = 0.0
    cumulative_exports: float = 0.0
    cumulative_imports: float = 0.0
    cumulative_net_exports: float = 0.0
    final_productive_capital: float = 0.0
    cumulative_business_investment: float = 0.0
    final_household_debt: float = 0.0
    cumulative_household_defaults: int = 0
    cumulative_bank_resolutions: int = 0
    cumulative_public_recapitalization: float = 0.0
    cumulative_bail_in_losses: float = 0.0
    cumulative_unemployment_benefits: float = 0.0
    final_labor_force_participation: float = 0.0
    average_job_separation_rate: float = 0.0
    average_job_finding_rate: float = 0.0


class EngineTrace(BaseModel):
    activation: str
    household_decision: str
    accounting: str = "economy-lab-sfc-v1.0"
    minsky: str = "rest-template-bridge"
    macro: str = "off"


class AuthorityAssignmentView(BaseModel):
    field: str
    source: str
    cadence: Literal["run", "tick"]
    description: str
    category: str


class AuthorityReport(BaseModel):
    registry_version: str
    strict: bool = True
    status: Literal["pass", "fail"]
    complete: bool
    total_claims: int
    claims_by_source: dict[str, int] = Field(default_factory=dict)
    claims_by_field: dict[str, int] = Field(default_factory=dict)
    violations: list[str] = Field(default_factory=list)
    assignments: list[AuthorityAssignmentView] = Field(default_factory=list)


class AuthorityRegistryEntry(BaseModel):
    field: str
    allowed_sources: list[str]
    cadence: Literal["run", "tick"]
    description: str
    category: str


class AuthorityPlanEntry(BaseModel):
    field: str
    source: str
    cadence: Literal["run", "tick"]
    description: str
    category: str


class SectorBalanceSheetView(BaseModel):
    sector: str
    assets: float
    liabilities: float
    net_financial_worth: float
    positions: dict[str, float]


class MatrixRowView(BaseModel):
    instrument: str
    sectors: dict[str, float]
    total: float


class AccountingReport(BaseModel):
    tick: int
    sector_balance_sheets: list[SectorBalanceSheetView]
    stock_rows: list[MatrixRowView]
    flow_rows: list[MatrixRowView]
    stocks_balanced: bool
    flows_balanced: bool


class BankStatusView(BaseModel):
    bank_id: int
    reserves: float
    deposits: float
    corporate_loans: float
    household_loans: float
    interbank_assets: float
    interbank_borrowing: float
    central_bank_borrowing: float
    paid_in_equity: float
    retained_earnings: float
    regulatory_capital: float
    risk_weighted_assets: float
    capital_ratio: float
    minimum_capital_ratio: float
    compliant: bool
    resolutions: int = 0
    last_resolution_mode: str = "none"


class BankingReport(BaseModel):
    aggregate_capital: float
    aggregate_capital_ratio: float
    undercapitalized_banks: int
    aggregate_household_loans: float = 0.0
    total_resolutions: int = 0
    banks: list[BankStatusView]


class CouplingPoint(BaseModel):
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


class CouplingReport(BaseModel):
    mode: str
    authority: dict[str, str]
    parameters: dict[str, float]
    points: list[CouplingPoint]
    warning: str


class MacroStateSnapshot(BaseModel):
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


class MacroRecalibrationPoint(BaseModel):
    quarter: int
    trigger_month: int
    next_start_month: int
    effective_monetary_shock_pp: float
    base_policy_rate_pct: float
    parameters: dict[str, float]
    state: MacroStateSnapshot


class MacroRecalibrationReport(BaseModel):
    mode: str
    frequency_months: int
    adaptation_strength: float
    completed_recalibrations: int
    runs: list[MacroRecalibrationPoint]
    warning: str


class ShockScheduleView(BaseModel):
    kind: str
    start_month: int
    duration_months: int
    magnitude_pct: float
    label: str = ""


class ShockReport(BaseModel):
    engine: str = "economy-lab-shock-runtime-v1.0"
    schedules: list[ShockScheduleView]
    warning: str


class FinancialControlView(BaseModel):
    minimum_bank_capital_ratio: float
    target_reserve_ratio: float
    credit_supply_factor: float
    default_writeoff_ratio: float
    interbank_spread: float
    central_bank_penalty_spread: float


class FinancialEngineReport(BaseModel):
    engine: str
    mode: str
    profile_id: str | None = None
    current: FinancialControlView
    guidance_points: list[FinancialGuidancePoint] = Field(default_factory=list)
    warning: str


class HouseholdIncomeGroupView(BaseModel):
    group: int
    households: int
    employment_rate: float
    average_wage: float
    average_permanent_income: float
    average_transitory_income_ratio: float
    average_unemployment_probability: float
    average_consumption: float
    average_deposit: float
    average_unemployment_benefit: float = 0.0
    labor_force_participation: float = 100.0
    average_reservation_wage: float = 0.0
    average_search_intensity: float = 1.0


class HouseholdEngineReport(BaseModel):
    engine: str
    state_mode: str
    income_groups: int
    employment_rate: float
    average_permanent_income: float
    average_transitory_income_ratio: float
    average_unemployment_probability: float
    average_unemployment_benefit: float = 0.0
    labor_force_participation: float = 100.0
    groups: list[HouseholdIncomeGroupView]
    warning: str


class LaborMarketReport(BaseModel):
    benefits_enabled: bool
    labor_supply_mode: str
    replacement_rate: float
    waiting_months: int
    maximum_benefit_months: int
    benefit_cap: float
    cumulative_benefits: float
    final_participation_rate: float
    average_job_separation_rate: float
    average_job_finding_rate: float
    warning: str


class SimulationResult(BaseModel):
    scenario: str
    model: str
    warning: str
    series: list[TimePoint]
    summary: SimulationSummary
    engines: EngineTrace | None = None
    authority: AuthorityReport | None = None
    accounting: AccountingReport | None = None
    banking: BankingReport | None = None
    financial: FinancialEngineReport | None = None
    household_engine: HouseholdEngineReport | None = None
    labor_market: LaborMarketReport | None = None
    macro: MacroReport | None = None
    coupling: CouplingReport | None = None
    macro_recalibration: MacroRecalibrationReport | None = None
    shocks: ShockReport | None = None




class ExternalValidationRequest(BaseModel):
    engines: list[Literal["mesa", "hark", "dynare", "minsky"]] = Field(
        default_factory=lambda: ["mesa", "hark", "dynare", "minsky"],
        min_length=1, max_length=4,
    )
    smoke_tests: bool = True
    integration_tests: bool = True
    dynare_timeout_seconds: int = Field(default=60, ge=10, le=180)
    minsky_timeout_seconds: float = Field(default=3.0, ge=0.5, le=30.0)


class ExternalValidationStageResponse(BaseModel):
    name: str
    status: Literal["pass", "fail", "unavailable", "skipped"]
    duration_ms: float
    summary: str
    details: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class ExternalEngineCheckResponse(BaseModel):
    engine: Literal["mesa", "hark", "dynare", "minsky"]
    status: Literal["pass", "fail", "unavailable"]
    installed_or_configured: bool
    version: str | None = None
    duration_ms: float
    summary: str
    details: dict[str, object] = Field(default_factory=dict)
    error: str | None = None
    qualification_level: Literal["none", "detected", "read-only-verified", "runtime-verified"] = "none"
    compatibility: Literal["compatible", "warning", "unknown"] = "unknown"
    target_version: str | None = None
    integrated_smoke_passed: bool = False
    stages: list[ExternalValidationStageResponse] = Field(default_factory=list)


class ExternalValidationReportResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    schema_id: str = Field(alias="schema")
    report_id: str
    report_digest: str
    generated_at: str
    economy_lab_version: str
    platform: str
    python_version: str
    environment: dict[str, object] = Field(default_factory=dict)
    requested_engines: list[Literal["mesa", "hark", "dynare", "minsky"]]
    smoke_tests: bool
    integration_tests: bool
    status: Literal["ready", "partial", "failed"]
    qualification_ready: bool
    passed: int
    failed: int
    unavailable: int
    runtime_verified: int
    read_only_verified: int
    checks: list[ExternalEngineCheckResponse]


class DynareStatusResponse(BaseModel):
    configured: bool
    ready: bool
    octave_executable: str | None = None
    dynare_matlab_path: str | None = None
    dynare_version_hint: str | None = None
    error: str | None = None


class MacroIRFPoint(BaseModel):
    period: int
    output_gap: float
    inflation_gap: float
    policy_rate_gap: float


class MacroReport(BaseModel):
    engine: str
    model_name: str
    model_kind: str
    period_unit: str
    shock_name: str
    shock_size_pp: float
    neutral_nominal_rate: float
    parameters: dict[str, float]
    irf: list[MacroIRFPoint]
    coupling_mode: str = "advisory-only"
    warning: str


class MinskyStatusResponse(BaseModel):
    configured: bool
    reachable: bool
    object_type: str | None = None
    model_time: float | None = None
    error: str | None = None


class MinskyExchangeResponse(BaseModel):
    schema_name: str
    tick: int
    columns: list[str]
    stocks: list[dict[str, object]]
    flows: list[dict[str, object]]


class MinskyGodleyCellMappingSpec(BaseModel):
    kind: Literal["stocks", "flows"]
    instrument: str = Field(min_length=1, max_length=120)
    sector: Literal[
        "households", "firms", "banks", "government", "central_bank", "rest_of_world"
    ]
    variable_id: str = Field(min_length=1, max_length=256)
    external_multiplier: float = Field(default=1.0, ge=-1_000_000.0, le=1_000_000.0)
    required: bool = True

    @model_validator(mode="after")
    def validate_multiplier(self):
        if self.external_multiplier == 0:
            raise ValueError("external_multiplier must be non-zero")
        return self


class MinskyReconciliationRequest(BaseModel):
    canonical: MinskyExchangeResponse
    template_id: str = Field(min_length=1, max_length=120)
    template_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    mappings: list[MinskyGodleyCellMappingSpec] = Field(min_length=1, max_length=1000)
    source_mode: Literal["provided", "live"] = "provided"
    observed_values: dict[str, float] = Field(default_factory=dict)
    model_path: str | None = Field(default=None, max_length=1024)
    reset_before: bool = False
    steps: int = Field(default=0, ge=0, le=240)
    absolute_tolerance: float = Field(default=1e-6, ge=0.0, le=1_000_000.0)
    relative_tolerance: float = Field(default=1e-6, ge=0.0, le=1.0)
    require_full_coverage: bool = True

    @model_validator(mode="after")
    def validate_source_contract(self):
        if self.source_mode == "provided" and not self.observed_values:
            raise ValueError("provided source_mode requires observed_values")
        if self.source_mode == "live" and self.observed_values:
            raise ValueError("live source_mode reads Minsky directly; observed_values must be empty")
        if self.source_mode == "live" and self.model_path is None:
            raise ValueError("live source_mode requires a local .mky model_path for hash verification")
        if self.model_path is not None and not self.model_path.lower().endswith(".mky"):
            raise ValueError("model_path must identify a .mky template")
        return self


class MinskyReconciliationCellView(BaseModel):
    kind: Literal["stocks", "flows"]
    instrument: str
    sector: str
    variable_id: str
    expected: float
    observed: float
    normalized_observed: float
    absolute_error: float
    relative_error: float
    within_tolerance: bool


class MinskyReconciliationResponse(BaseModel):
    schema_name: str
    report_id: str
    status: Literal["pass", "partial", "fail"]
    template_id: str
    template_sha256: str
    tick: int
    canonical_hash: str
    mapping_hash: str
    observed_hash: str
    accounting_authority: Literal["ledger_sfc"]
    read_only: bool
    external_can_mutate_ledger: bool
    complete: bool
    full_coverage_required: bool
    canonical_stocks_balanced: bool
    canonical_flows_balanced: bool
    compared_cells: int
    drift_count: int
    missing_mappings: list[str]
    missing_observations: list[str]
    extra_observations: list[str]
    maximum_absolute_error: float
    maximum_relative_error: float
    cells: list[MinskyReconciliationCellView]
    warnings: list[str]


class StorageStatusResponse(BaseModel):
    database_path: str
    schema_version: int
    projects: int
    runs: int
    experiments: int = 0
    profiles: int = 0
    jobs: int = 0


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    scenario: ScenarioSpec


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    scenario: ScenarioSpec | None = None


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    last_run_id: str | None = None
    run_count: int = 0


class ProjectRecord(ProjectSummary):
    scenario: ScenarioSpec


class ProjectRunRequest(BaseModel):
    scenario: ScenarioSpec | None = None
    save_scenario: bool = True


JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class SimulationJobCreateRequest(BaseModel):
    scenario: ScenarioSpec
    project_id: str | None = None
    save_scenario: bool = True
    timeout_seconds: float = Field(default=300.0, ge=1.0, le=3600.0)


class ProjectSimulationJobCreateRequest(BaseModel):
    scenario: ScenarioSpec | None = None
    save_scenario: bool = True
    timeout_seconds: float = Field(default=300.0, ge=1.0, le=3600.0)


class SimulationJobSummary(BaseModel):
    id: str
    project_id: str | None = None
    kind: Literal["simulation"] = "simulation"
    status: JobStatus
    run_id: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    progress: float = Field(ge=0.0, le=100.0)
    current_step: int = Field(ge=0)
    total_steps: int = Field(ge=1)
    stage: str
    timeout_seconds: float
    cancellation_requested: bool = False
    error_code: str | None = None
    error_message: str | None = None


class SimulationJobRecord(SimulationJobSummary):
    scenario: ScenarioSpec
    result: SimulationResult | None = None
    save_scenario: bool = True


class RunSummary(BaseModel):
    id: str
    project_id: str
    scenario_name: str
    created_at: str
    duration_ms: float
    engine_version: str
    final_gdp_index: float
    final_inflation: float
    final_unemployment: float
    ledger_balanced: bool
    godley_stocks_balanced: bool
    godley_flows_balanced: bool
    manifest_hash: str | None = None
    experiment_hash: str | None = None
    replay_of_run_id: str | None = None


class ProfileManifestEntry(BaseModel):
    kind: str
    profile_id: str
    resolved: bool
    module_id: str | None = None
    compatibility: str | None = None
    updated_at: str | None = None
    payload_hash: str | None = None
    scenario_patch_hash: str | None = None


class RunManifest(BaseModel):
    schema_name: Literal["economy-lab-run-manifest-v1.0"] = "economy-lab-run-manifest-v1.0"
    economy_lab_version: str
    scenario_hash: str
    result_hash: str
    experiment_hash: str
    seed: int
    runtime_versions: dict[str, str]
    engine_trace: dict[str, str]
    profiles: list[ProfileManifestEntry] = Field(default_factory=list)
    data_provenance: list[DataProvenanceRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RunRecord(RunSummary):
    scenario: ScenarioSpec
    result: SimulationResult
    manifest: RunManifest | None = None


class RunManifestResponse(BaseModel):
    run_id: str
    manifest_hash: str
    manifest: RunManifest


class ReplayVerification(BaseModel):
    status: Literal["matched", "diverged", "environment_changed"]
    scenario_match: bool
    result_match: bool
    experiment_match: bool
    environment_match: bool
    expected_result_hash: str
    actual_result_hash: str
    runtime_differences: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ReplayResponse(BaseModel):
    source_run_id: str
    replay_run: RunRecord
    verification: ReplayVerification


class ProjectSimulationResponse(BaseModel):
    project: ProjectRecord
    run: RunRecord
    result: SimulationResult


BatchAxis = Literal[
    "policy_rate",
    "income_tax",
    "public_spending_change",
    "minimum_bank_capital_ratio",
    "target_reserve_ratio",
]


class BatchExperimentRequest(BaseModel):
    base: ScenarioSpec
    axis: BatchAxis = "policy_rate"
    values: list[float] = Field(default_factory=lambda: [8.0, 10.0, 12.0, 14.0, 16.0], min_length=2, max_length=12)
    repetitions: int = Field(default=3, ge=1, le=10)
    seed_step: int = Field(default=1, ge=1, le=1000000)

    @model_validator(mode="after")
    def validate_batch(self):
        if len(set(float(v) for v in self.values)) != len(self.values):
            raise ValueError("batch values must be unique")
        if len(self.values) * self.repetitions > 60:
            raise ValueError("batch experiment is limited to 60 simulation runs")
        return self


class ProjectBatchRequest(BaseModel):
    axis: BatchAxis = "policy_rate"
    values: list[float] = Field(default_factory=lambda: [8.0, 10.0, 12.0, 14.0, 16.0], min_length=2, max_length=12)
    repetitions: int = Field(default=3, ge=1, le=10)
    seed_step: int = Field(default=1, ge=1, le=1000000)
    scenario: ScenarioSpec | None = None

    @model_validator(mode="after")
    def validate_batch(self):
        if len(set(float(v) for v in self.values)) != len(self.values):
            raise ValueError("batch values must be unique")
        if len(self.values) * self.repetitions > 60:
            raise ValueError("batch experiment is limited to 60 simulation runs")
        return self


class BatchRunPoint(BaseModel):
    axis_value: float
    repetition: int
    seed: int
    duration_ms: float
    final_gdp_index: float
    final_inflation: float
    final_unemployment: float
    cumulative_defaults: int
    final_bank_credit: float
    final_bank_capital_ratio: float
    cumulative_credit_rationed: float
    ledger_balanced: bool
    godley_stocks_balanced: bool
    godley_flows_balanced: bool


class BatchAggregate(BaseModel):
    axis_value: float
    runs: int
    mean_gdp_index: float
    std_gdp_index: float
    mean_inflation: float
    std_inflation: float
    mean_unemployment: float
    std_unemployment: float
    mean_defaults: float
    mean_bank_credit: float
    mean_bank_capital_ratio: float
    mean_credit_rationed: float
    all_accounting_balanced: bool


class BatchExperimentResponse(BaseModel):
    experiment_engine: str = "economy-lab-batch-v2.0"
    analytics_engine: str
    axis: BatchAxis
    values: list[float]
    repetitions: int
    total_runs: int
    duration_ms: float
    base_scenario: ScenarioSpec
    aggregates: list[BatchAggregate]
    runs: list[BatchRunPoint]
    warning: str


class ExperimentSummary(BaseModel):
    id: str
    project_id: str
    created_at: str
    axis: BatchAxis
    values: list[float]
    repetitions: int
    total_runs: int
    duration_ms: float
    engine_version: str


class ExperimentRecord(ExperimentSummary):
    result: BatchExperimentResponse


ProfileKind = Literal["macro", "financial", "agents", "households", "households_market", "firms", "labor_market"]


class LabProfileCreateRequest(BaseModel):
    module_id: Literal["dynare", "minsky", "mesa", "hark"]
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    inputs: dict[str, object] = Field(default_factory=dict)
    outputs: dict[str, object] | None = None


class ProfileSummary(BaseModel):
    id: str
    name: str
    description: str
    kind: ProfileKind
    module_id: str
    compatibility: str
    created_at: str
    updated_at: str


class ProfileRecord(ProfileSummary):
    payload: dict[str, object]
    scenario_patch: dict[str, object]


class ProfileApplyRequest(BaseModel):
    scenario: ScenarioSpec


class ProfileApplyResponse(BaseModel):
    profile: ProfileSummary
    scenario: ScenarioSpec
    changes: list[str]


class SimulationPresetInfo(BaseModel):
    id: str
    title: str
    description: str
    requirements: list[str]
    patch: dict[str, object]


class PresetApplyRequest(BaseModel):
    scenario: ScenarioSpec



class HubModuleInfo(BaseModel):
    id: str
    title: str
    kind: str
    description: str
    capabilities: list[str]
    dependencies: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    available: bool
    status: str


class HubToolInfo(BaseModel):
    id: str
    module_id: str
    title: str
    description: str
    capability: str
    route: str | None = None
    output_kinds: list[str] = Field(default_factory=list)
    available: bool
    status: str


class DynareLabRequest(BaseModel):
    irf_periods: int = Field(default=24, ge=1, le=160)
    monetary_shock_bp: float = Field(default=100.0, gt=0, le=2000)
    neutral_nominal_rate: float = Field(default=8.0, ge=-5, le=100)
    beta: float = Field(default=0.99, gt=0.8, lt=1.0)
    sigma: float = Field(default=1.0, gt=0.01, le=20)
    kappa: float = Field(default=0.10, gt=0, le=5)
    rho_i: float = Field(default=0.80, ge=0, lt=1)
    phi_pi: float = Field(default=1.50, ge=0, le=10)
    phi_x: float = Field(default=0.25, ge=-5, le=5)
    timeout_seconds: int = Field(default=120, ge=5, le=600)


class DynareTemplateResponse(BaseModel):
    model_name: str = "economy-lab-reference-nk"
    source: str
    warning: str = "Template conhecido do Economy Lab; nenhum código arbitrário é executado."


class DynareLabResponse(BaseModel):
    engine: str
    model_name: str
    model_kind: str
    period_unit: str
    shock_name: str
    shock_size_pp: float
    neutral_nominal_rate: float
    parameters: dict[str, float]
    irf: list[MacroIRFPoint]
    warning: str


class MesaLabRequest(BaseModel):
    agents: int = Field(default=100, ge=10, le=10000)
    steps: int = Field(default=100, ge=1, le=5000)
    initial_wealth: float = Field(default=10.0, gt=0, le=1_000_000)
    transfer_amount: float = Field(default=1.0, gt=0, le=1_000_000)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def validate_transfer(self):
        if self.transfer_amount > self.initial_wealth:
            raise ValueError("transfer_amount cannot exceed initial_wealth")
        return self


class MesaLabPathPoint(BaseModel):
    step: int
    gini: float
    zero_wealth_share: float
    max_wealth: float


class MesaLabResponse(BaseModel):
    engine: str
    model: str
    agents: int
    steps: int
    seed: int
    initial_total_wealth: float
    final_total_wealth: float
    mean_wealth: float
    median_wealth: float
    max_wealth: float
    gini: float
    zero_wealth_share: float
    path: list[MesaLabPathPoint]
    warning: str




class MesaComponentRequest(BaseModel):
    component: Literal["activation", "household_search", "firm_behavior", "labor_market"]
    steps: int = Field(default=60, ge=1, le=2000)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    activation_pattern: Literal["random", "fixed"] = "random"
    shopping_sample_size: int = Field(default=4, ge=1, le=20)
    cheapest_choice_probability: float = Field(default=1.0, ge=0.0, le=1.0)
    price_adjustment_strength: float = Field(default=1.0, ge=0.1, le=3.0)
    hiring_strength: float = Field(default=1.0, ge=0.0, le=3.0)
    layoff_strength: float = Field(default=1.0, ge=0.0, le=3.0)
    matching_efficiency: float = Field(default=1.0, ge=0.0, le=1.0)


class MesaComponentResponse(BaseModel):
    engine: str = "mesa-component-lab"
    component: str
    scenario_patch: dict[str, object]
    metrics: dict[str, float | int | str]
    path: list[dict[str, float | int]] = Field(default_factory=list)
    warning: str


class HarkLabRequest(BaseModel):
    annual_interest_rate: float = Field(default=0.08, ge=-0.20, le=2.0)
    crra: float = Field(default=2.0, gt=0.05, le=20)
    annual_discount_factor: float = Field(default=0.96, gt=0.5, lt=1.0)
    unemployment_probability: float = Field(default=0.05, ge=0.001, le=0.50)
    unemployment_replacement_rate: float = Field(default=0.30, ge=0.0, le=1.0)
    permanent_shock_std: float = Field(default=0.04, ge=0.0, le=1.0)
    transitory_shock_std: float = Field(default=0.10, ge=0.0, le=2.0)
    permanent_income_memory: float = Field(default=0.18, gt=0.0, le=1.0)
    income_groups: int = Field(default=5, ge=1, le=10)
    income_risk_dispersion: float = Field(default=0.35, ge=0.0, le=1.0)
    max_market_resources: float = Field(default=12.0, gt=0.1, le=1000)
    points: int = Field(default=25, ge=5, le=200)


class HarkPolicyPoint(BaseModel):
    market_resources: float
    consumption: float
    saving: float
    consumption_share: float


class HarkIncomeGroupPolicy(BaseModel):
    income_group: int
    unemployment_probability: float
    policy_curve: list[HarkPolicyPoint]


class HarkLabResponse(BaseModel):
    engine: str
    model: str
    parameters: dict[str, float]
    policy_curve: list[HarkPolicyPoint]
    group_profiles: list[HarkIncomeGroupPolicy] = Field(default_factory=list)
    warning: str


class MinskyFinancialMapping(BaseModel):
    minimum_bank_capital_ratio: str = ":bank_min_capital_ratio"
    target_reserve_ratio: str = ":bank_target_reserve_ratio"
    credit_supply_factor: str = ":credit_supply_factor"
    default_writeoff_ratio: str = ":default_writeoff_ratio"
    interbank_spread: str = ":interbank_spread"
    central_bank_penalty_spread: str = ":cb_penalty_spread"


class MinskyFinancialCaptureRequest(BaseModel):
    steps: int = Field(default=12, ge=1, le=240)
    reset_before: bool = False
    unit_mode: Literal["decimal", "percent"] = "decimal"
    mapping: MinskyFinancialMapping = Field(default_factory=MinskyFinancialMapping)


class MinskyFinancialCaptureResponse(BaseModel):
    engine: str = "minsky-rest-financial-controller"
    unit_mode: str
    mapping: dict[str, str]
    points: list[FinancialGuidancePoint]
    warning: str


class MinskyLabCommandRequest(BaseModel):
    action: Literal["members", "signature", "step", "reset", "get_variable", "set_variable"]
    path: str = Field(default="/minsky", min_length=1, max_length=512)
    variable_id: str | None = Field(default=None, max_length=256)
    value: float | None = None


class MinskyLabCommandResponse(BaseModel):
    engine: str
    action: str
    result: object | None = None


class SimulationExportRequest(BaseModel):
    scenario: ScenarioSpec
    result: SimulationResult


class BatchExportRequest(BaseModel):
    result: BatchExperimentResponse


DataSourceId = Literal["bcb_sgs", "ibge_sidra", "world_bank", "ipeadata"]
CalibrationMetric = Literal["inflation", "unemployment", "policy_rate", "gdp_growth", "bank_credit_growth", "bank_capital_ratio"]
CalibrationStatistic = Literal["last", "mean", "median", "std"]
CalibrationComparisonMode = Literal["moment", "aligned_path"]
CalibrationFrequency = Literal["auto", "monthly", "quarterly", "annual"]
CalibrationAggregation = Literal["last", "mean"]
CalibrationParameter = Literal[
    "initial_inflation", "initial_unemployment", "policy_rate", "public_spending_change",
    "minimum_bank_capital_ratio", "target_reserve_ratio", "labor_matching_efficiency",
]


class EconomicObservation(BaseModel):
    date: str
    value: float


class DataFetchRequest(BaseModel):
    source: DataSourceId
    series_id: str = Field(min_length=1, max_length=160)
    title: str = Field(default="", max_length=200)
    unit: str = Field(default="", max_length=80)
    frequency: str = Field(default="", max_length=40)
    start_date: str | None = None
    end_date: str | None = None
    source_options: dict[str, str | int | float | bool] = Field(default_factory=dict)
    use_cache: bool = True
    refresh: bool = False
    timeout_seconds: int = Field(default=30, ge=2, le=120)

    @model_validator(mode="after")
    def validate_dates(self):
        from datetime import date
        start = date.fromisoformat(self.start_date) if self.start_date else None
        end = date.fromisoformat(self.end_date) if self.end_date else None
        if start and end and start > end:
            raise ValueError("start_date must be before or equal to end_date")
        return self


class EconomicSeriesResponse(BaseModel):
    source: DataSourceId
    series_id: str
    title: str
    unit: str = ""
    frequency: str = "unknown"
    fetched_at: str
    cached: bool = False
    request_url: str
    metadata: dict[str, object] = Field(default_factory=dict)
    observations: list[EconomicObservation]
    warning: str


class DataSourceCatalogItem(BaseModel):
    id: DataSourceId
    title: str
    description: str
    identifier_label: str
    examples: list[dict[str, object]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DataCacheStatus(BaseModel):
    directory: str
    entries: int
    bytes: int


class CalibrationTargetSpec(BaseModel):
    metric: CalibrationMetric
    series: EconomicSeriesResponse
    statistic: CalibrationStatistic = "last"
    weight: float = Field(default=1.0, gt=0, le=100)
    scale_floor: float = Field(default=1.0, gt=0)
    comparison_mode: CalibrationComparisonMode = "moment"
    alignment_frequency: CalibrationFrequency = "auto"
    aggregation: CalibrationAggregation = "mean"


class CalibrationRequest(BaseModel):
    scenario: ScenarioSpec
    result: SimulationResult
    targets: list[CalibrationTargetSpec] = Field(min_length=1, max_length=12)
    simulation_start_date: str | None = None
    simulation_end_date: str | None = None

    @model_validator(mode="after")
    def validate_alignment_dates(self):
        from datetime import date
        start = date.fromisoformat(self.simulation_start_date) if self.simulation_start_date else None
        end = date.fromisoformat(self.simulation_end_date) if self.simulation_end_date else None
        if start and end and start > end:
            raise ValueError("simulation_start_date must be before simulation_end_date")
        return self


class CalibrationAlignedPoint(BaseModel):
    period: str
    real_value: float
    simulated_value: float
    error: float


class CalibrationMetricResult(BaseModel):
    metric: CalibrationMetric
    statistic: CalibrationStatistic
    source: DataSourceId
    series_id: str
    real_value: float
    simulated_value: float
    error: float
    normalized_error: float
    weight: float
    weighted_loss: float
    real_observations: int
    simulated_observations: int
    comparison_mode: CalibrationComparisonMode = "moment"
    aligned_frequency: str | None = None
    aligned_observations: int = 0
    path_mae: float | None = None
    path_rmse: float | None = None
    aligned_points: list[CalibrationAlignedPoint] = Field(default_factory=list)


class CalibrationResponse(BaseModel):
    engine: str
    score: float = Field(ge=0, le=100)
    normalized_rmse: float = Field(ge=0)
    metrics: list[CalibrationMetricResult]
    suggested_scenario_patch: dict[str, float] = Field(default_factory=dict)
    requires_review: bool = True
    warning: str


class CalibrationFitRequest(BaseModel):
    scenario: ScenarioSpec
    targets: list[CalibrationTargetSpec] = Field(min_length=1, max_length=12)
    parameters: list[CalibrationParameter] = Field(default_factory=lambda: ["initial_inflation", "initial_unemployment", "policy_rate"], min_length=1, max_length=7)
    simulation_start_date: str | None = None
    simulation_end_date: str | None = None
    max_evaluations: int = Field(default=24, ge=4, le=80)
    max_rounds: int = Field(default=3, ge=1, le=8)
    minimum_score_improvement: float = Field(default=0.05, ge=0.0, le=20.0)
    training_end_date: str | None = None
    validation_start_date: str | None = None

    @model_validator(mode="after")
    def validate_fit_dates_and_parameters(self):
        from datetime import date
        start = date.fromisoformat(self.simulation_start_date) if self.simulation_start_date else None
        end = date.fromisoformat(self.simulation_end_date) if self.simulation_end_date else None
        if start and end and start > end:
            raise ValueError("simulation_start_date must be before simulation_end_date")
        if len(set(self.parameters)) != len(self.parameters):
            raise ValueError("calibration parameters must be unique")
        if bool(self.training_end_date) != bool(self.validation_start_date):
            raise ValueError("training_end_date and validation_start_date must be provided together")
        train_end = date.fromisoformat(self.training_end_date) if self.training_end_date else None
        validation_start = date.fromisoformat(self.validation_start_date) if self.validation_start_date else None
        if train_end and validation_start and train_end >= validation_start:
            raise ValueError("training_end_date must be before validation_start_date")
        return self


class CalibrationFitStep(BaseModel):
    evaluation: int
    round: int
    parameter: CalibrationParameter | Literal["baseline"]
    candidate_value: float | None = None
    score: float
    accepted: bool


class CalibrationFitResponse(BaseModel):
    engine: str = "economy-lab-calibration-fit-v2.6"
    baseline_score: float
    best_score: float
    evaluations: int
    rounds_completed: int
    converged: bool
    parameters: list[CalibrationParameter]
    best_scenario_patch: dict[str, float]
    final_calibration: CalibrationResponse
    validation_score: float | None = None
    validation_calibration: CalibrationResponse | None = None
    trace: list[CalibrationFitStep]
    requires_review: bool = True
    warning: str


class CalibrationExportRequest(BaseModel):
    scenario: ScenarioSpec
    calibration: CalibrationResponse
    fit: CalibrationFitResponse | None = None


# --- v2.2 ModelSpec / safe AI model builder ---------------------------------

class ModelPopulationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    households: int = Field(default=5000, ge=100, le=100_000)
    firms: int = Field(default=100, ge=5, le=5_000)
    banks: int = Field(default=3, ge=1, le=50)

    @model_validator(mode="after")
    def validate_structure(self):
        if self.firms >= self.households:
            raise ValueError("firms must be fewer than households")
        return self


class ModelEnginePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agents: Literal["native", "mesa"] = "native"
    households: Literal["heuristic", "hark"] = "heuristic"
    financial: Literal["native", "minsky_profile"] = "native"
    macro: Literal["off", "dynare"] = "off"
    macro_coupling: Literal["advisory", "hybrid"] = "advisory"
    macro_recalibration: Literal["static_irf", "quarterly"] = "static_irf"

    @model_validator(mode="after")
    def validate_macro_plan(self):
        if self.macro == "off" and self.macro_coupling == "hybrid":
            raise ValueError("hybrid macro coupling requires Dynare")
        if self.macro_recalibration == "quarterly" and not (self.macro == "dynare" and self.macro_coupling == "hybrid"):
            raise ValueError("quarterly macro recalibration requires Dynare hybrid coupling")
        return self


class ModelMarketPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    labor: bool = True
    goods: bool = True
    credit: bool = True
    external: bool = True


class ModelPolicySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inflation: float = Field(default=4.0, ge=-20, le=100)
    unemployment: float = Field(default=7.0, ge=0, le=100)
    policy_rate: float = Field(default=10.0, ge=-10, le=100)
    income_tax: float = Field(default=20.0, ge=0, le=100)
    public_spending_change: float = Field(default=0.0, ge=-50, le=100)


class ModelTraitSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    economic_base: Literal["generic", "mixed", "commodity_exporter", "industrial", "services"] = "generic"
    inequality: Literal["low", "medium", "high"] = "medium"
    banking_concentration: Literal["low", "medium", "high"] = "medium"
    openness: Literal["low", "medium", "high"] = "medium"


class ModelSpec(BaseModel):
    """Declarative economic-model contract proposed by AI/providers.

    It intentionally cannot contain executable source, shell commands or raw
    solver code. ``extra=forbid`` keeps provider output inside this schema.
    """
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["economy-lab-modelspec-v1.0"] = "economy-lab-modelspec-v1.0"
    name: str = Field(default="Modelo econômico", min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    source_prompt: str = Field(default="", max_length=4000)
    horizon_months: int = Field(default=24, ge=1, le=240)
    population: ModelPopulationSpec = Field(default_factory=ModelPopulationSpec)
    engines: ModelEnginePlan = Field(default_factory=ModelEnginePlan)
    markets: ModelMarketPlan = Field(default_factory=ModelMarketPlan)
    policy: ModelPolicySpec = Field(default_factory=ModelPolicySpec)
    traits: ModelTraitSpec = Field(default_factory=ModelTraitSpec)
    shocks: list[EconomicShockSpec] = Field(default_factory=list, max_length=12)
    hark_income_groups: int = Field(default=5, ge=1, le=10)
    hark_income_risk_dispersion: float = Field(default=0.35, ge=0, le=1)
    productive_capital: bool = True
    household_credit: bool = True
    unemployment_benefits: bool = True
    unemployment_benefit_replacement_rate: float = Field(default=45.0, ge=0.0, le=100.0)
    labor_supply_mode: Literal["inelastic", "reservation_wage"] = "reservation_wage"
    bank_resolution_mode: Literal["none", "government_recapitalization", "bail_in"] = "government_recapitalization"
    requested_capabilities: list[str] = Field(default_factory=list, max_length=30)
    recommended_modules: list[Literal["mesa", "hark", "minsky", "dynare"]] = Field(default_factory=list)
    profile_refs: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def validate_model_spec(self):
        for shock in self.shocks:
            if shock.start_month > self.horizon_months:
                raise ValueError("shock start_month must be within ModelSpec horizon")
            if shock.start_month + shock.duration_months - 1 > self.horizon_months:
                raise ValueError("shock duration extends beyond ModelSpec horizon")
        return self


class ModelCompilationReport(BaseModel):
    status: Literal["full", "partial"]
    applied_fields: list[str] = Field(default_factory=list)
    partial_features: list[str] = Field(default_factory=list)
    unsupported_features: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warning: str


class ModelDraftRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    base: ModelSpec | None = None


class ModelDraftResponse(BaseModel):
    provider: str
    requires_review: bool = True
    recognized_changes: list[str]
    provider_assumptions: list[str]
    model_spec: ModelSpec
    compiled_scenario: ScenarioSpec
    compilation: ModelCompilationReport


class ModelCandidateValidationRequest(BaseModel):
    candidate: dict[str, object]


class ModelCandidateValidationResponse(BaseModel):
    valid: bool = True
    model_spec: ModelSpec
    compiled_scenario: ScenarioSpec
    compilation: ModelCompilationReport


class ModelToScenarioRequest(BaseModel):
    model_spec: ModelSpec
    base_scenario: ScenarioSpec | None = None


class ModelToScenarioResponse(BaseModel):
    scenario: ScenarioSpec
    compilation: ModelCompilationReport


class ModelProviderInfo(BaseModel):
    id: str
    title: str
    kind: Literal["local", "external"]
    available: bool
    requires_network: bool
    status: str
