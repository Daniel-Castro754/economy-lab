import { invoke, isTauri } from "@tauri-apps/api/core";
import { apiFetch } from "./apiClient";

export * from "./simpleApi";
export * from "./engineApi";
export * from "./workspaceApi";
export * from "./profileApi";

export type EconomicShockSpec = {
  kind: "fiscal_spending" | "productivity" | "cost_push" | "external_demand" | "import_cost";
  start_month: number;
  duration_months: number;
  magnitude_pct: number;
  label: string;
};

export type FinancialGuidancePoint = {
  month: number;
  minimum_bank_capital_ratio: number;
  target_reserve_ratio: number;
  credit_supply_factor: number;
  default_writeoff_ratio: number;
  interbank_spread: number;
  central_bank_penalty_spread: number;
};

export type DataProvenanceRecord = {
  source_id: string;
  series_id: string;
  content_hash: string;
  retrieved_at: string | null;
  observation_start: string | null;
  observation_end: string | null;
  frequency: string | null;
  units: string | null;
};

export type ScenarioSpec = {
  name: string;
  months: number;
  initial_gdp: number;
  initial_inflation: number;
  initial_unemployment: number;
  policy_rate: number;
  income_tax: number;
  public_spending_change: number;
  households: number;
  firms: number;
  banks: number;
  seed: number;
  mode: "demo" | "economy_zero";
  activation_engine: "native" | "mesa";
  mesa_activation_pattern: "random" | "fixed";
  household_shopping_sample_size: number;
  household_cheapest_choice_probability: number;
  firm_price_adjustment_strength: number;
  firm_hiring_strength: number;
  firm_layoff_strength: number;
  labor_matching_efficiency: number;
  initial_capital_per_worker: number;
  capital_unit_cost: number;
  annual_capital_depreciation_rate: number;
  firm_investment_propensity: number;
  capital_output_elasticity: number;
  household_behavior: "heuristic" | "hark";
  minimum_bank_capital_ratio: number;
  target_reserve_ratio: number;
  financial_engine: "native" | "minsky_profile";
  bank_credit_supply_factor: number;
  default_writeoff_ratio: number;
  interbank_spread: number;
  central_bank_penalty_spread: number;
  household_credit_enabled: boolean;
  household_credit_income_multiple: number;
  household_credit_liquidity_target_months: number;
  household_credit_spread: number;
  household_principal_repayment_rate: number;
  household_default_writeoff_ratio: number;
  bank_resolution_mode: "none" | "government_recapitalization" | "bail_in";
  bank_resolution_trigger_ratio: number;
  bank_resolution_target_ratio: number;
  bail_in_household_protection: number;
  bail_in_firm_protection: number;
  financial_guidance: FinancialGuidancePoint[];
  macro_engine: "off" | "dynare";
  dynare_monetary_shock_bp: number;
  dynare_irf_periods: number;
  dynare_neutral_nominal_rate: number;
  dynare_beta: number;
  dynare_sigma: number;
  dynare_kappa: number;
  dynare_rho_i: number;
  dynare_phi_pi: number;
  dynare_phi_x: number;
  hark_crra: number;
  hark_annual_discount_factor: number;
  hark_state_mode: "normalized" | "employment_income";
  hark_unemployment_probability: number;
  hark_unemployment_replacement_rate: number;
  hark_permanent_shock_std: number;
  hark_transitory_shock_std: number;
  hark_permanent_income_memory: number;
  hark_income_groups: number;
  hark_income_risk_dispersion: number;
  unemployment_benefits_enabled: boolean;
  unemployment_benefit_replacement_rate: number;
  unemployment_benefit_waiting_months: number;
  unemployment_benefit_max_months: number;
  unemployment_benefit_cap: number;
  labor_supply_mode: "inelastic" | "reservation_wage";
  labor_search_intensity: number;
  reservation_wage_ratio: number;
  benefit_search_disincentive: number;
  wealth_search_disincentive: number;
  job_separation_risk_memory: number;
  macro_coupling: "advisory" | "hybrid";
  macro_coupling_strength: number;
  macro_feedback_strength: number;
  macro_recalibration: "static_irf" | "quarterly";
  macro_recalibration_strength: number;
  macro_max_recalibrations: number;
  shocks: EconomicShockSpec[];
  applied_profiles: Record<string, string>;
  data_provenance: DataProvenanceRecord[];
};

export type HealthResponse = {
  status: string;
  engine_version: string;
  mesa_available: boolean;
  hark_available: boolean;
  minsky_rest_configured: boolean;
  dynare_ready: boolean;
  runtime_mode: string;
  runtime_instance?: string | null;
};

export type TimePoint = {
  month: number;
  gdp_index: number;
  inflation: number;
  unemployment: number;
  policy_rate: number;
  price_index?: number | null;
  household_consumption?: number | null;
  government_spending?: number | null;
  corporate_debt?: number | null;
  bank_credit?: number | null;
  bank_deposits?: number | null;
  gini_wealth?: number | null;
  firm_defaults?: number | null;
  bank_reserves?: number | null;
  central_bank_advances?: number | null;
  government_debt?: number | null;
  private_net_financial_wealth?: number | null;
  bank_capital?: number | null;
  bank_capital_ratio?: number | null;
  undercapitalized_banks?: number | null;
  interbank_credit?: number | null;
  bank_profit_loss?: number | null;
  credit_rationed?: number | null;
  default_losses?: number | null;
  exports?: number | null;
  imports?: number | null;
  net_exports?: number | null;
  business_investment?: number | null;
  productive_capital?: number | null;
  household_debt?: number | null;
  household_credit?: number | null;
  household_defaults?: number | null;
  bank_resolutions?: number | null;
  public_recapitalization?: number | null;
  bail_in_losses?: number | null;
  unemployment_benefits?: number | null;
  labor_force_participation?: number | null;
  job_separation_rate?: number | null;
  job_finding_rate?: number | null;
  active_shocks?: Record<string, number> | null;
};

export type SectorBalanceSheet = {
  sector: string;
  assets: number;
  liabilities: number;
  net_financial_worth: number;
  positions: Record<string, number>;
};

export type MatrixRow = {
  instrument: string;
  sectors: Record<string, number>;
  total: number;
};

export type AccountingReport = {
  tick: number;
  sector_balance_sheets: SectorBalanceSheet[];
  stock_rows: MatrixRow[];
  flow_rows: MatrixRow[];
  stocks_balanced: boolean;
  flows_balanced: boolean;
};

export type BankStatus = {
  bank_id: number;
  reserves: number;
  deposits: number;
  corporate_loans: number;
  household_loans: number;
  interbank_assets: number;
  interbank_borrowing: number;
  central_bank_borrowing: number;
  paid_in_equity: number;
  retained_earnings: number;
  regulatory_capital: number;
  risk_weighted_assets: number;
  capital_ratio: number;
  minimum_capital_ratio: number;
  compliant: boolean;
  resolutions: number;
  last_resolution_mode: string;
};

export type BankingReport = {
  aggregate_capital: number;
  aggregate_capital_ratio: number;
  undercapitalized_banks: number;
  aggregate_household_loans: number;
  total_resolutions: number;
  banks: BankStatus[];
};

export type SimulationResult = {
  scenario: string;
  model: string;
  warning: string;
  series: TimePoint[];
  engines?: {
    activation: string;
    household_decision: string;
    accounting: string;
    minsky: string;
    macro: string;
  } | null;
  accounting?: AccountingReport | null;
  banking?: BankingReport | null;
  household_engine?: {
    engine: string;
    state_mode: string;
    income_groups: number;
    employment_rate: number;
    average_permanent_income: number;
    average_transitory_income_ratio: number;
    average_unemployment_probability: number;
    average_unemployment_benefit: number;
    labor_force_participation: number;
    groups: Array<{
      group: number; households: number; employment_rate: number; average_wage: number;
      average_permanent_income: number; average_transitory_income_ratio: number;
      average_unemployment_probability: number; average_consumption: number; average_deposit: number;
      average_unemployment_benefit: number; labor_force_participation: number;
      average_reservation_wage: number; average_search_intensity: number;
    }>;
    warning: string;
  } | null;
  labor_market?: {
    benefits_enabled: boolean;
    labor_supply_mode: string;
    replacement_rate: number;
    waiting_months: number;
    maximum_benefit_months: number;
    benefit_cap: number;
    cumulative_benefits: number;
    final_participation_rate: number;
    average_job_separation_rate: number;
    average_job_finding_rate: number;
    warning: string;
  } | null;
  financial?: {
    engine: string;
    mode: string;
    profile_id?: string | null;
    current: Omit<FinancialGuidancePoint, "month">;
    guidance_points: FinancialGuidancePoint[];
    warning: string;
  } | null;
  macro?: {
    engine: string;
    model_name: string;
    model_kind: string;
    period_unit: string;
    shock_name: string;
    shock_size_pp: number;
    neutral_nominal_rate: number;
    parameters: Record<string, number>;
    coupling_mode: string;
    warning: string;
    irf: Array<{
      period: number;
      output_gap: number;
      inflation_gap: number;
      policy_rate_gap: number;
    }>;
  } | null;

  macro_recalibration?: {
    mode: string;
    frequency_months: number;
    adaptation_strength: number;
    completed_recalibrations: number;
    warning: string;
    runs: Array<{
      quarter: number;
      trigger_month: number;
      next_start_month: number;
      effective_monetary_shock_pp: number;
      base_policy_rate_pct: number;
      parameters: Record<string, number>;
      state: {
        quarter: number;
        end_month: number;
        gdp_index: number;
        quarterly_gdp_growth_pct: number;
        inflation_pct: number;
        unemployment_pct: number;
        policy_rate_pct: number;
        bank_credit: number;
        quarterly_credit_growth_pct: number;
        bank_capital_ratio_pct: number;
        financial_stress: number;
      };
    }>;
  } | null;

  shocks?: {
    engine: string;
    warning: string;
    schedules: EconomicShockSpec[];
  } | null;

  coupling?: {
    mode: string;
    authority: Record<string, string>;
    parameters: Record<string, number>;
    warning: string;
    points: Array<{
      month: number;
      output_gap_guidance_pp: number;
      inflation_guidance_pp: number;
      dynare_policy_gap_pp: number;
      feedback_policy_gap_pp: number;
      applied_policy_rate_pct: number;
      demand_signal_pp: number;
      price_signal_pp: number;
      realized_gdp_index: number;
      realized_output_gap_proxy_pp: number;
      realized_inflation_pct: number;
      realized_unemployment_pct: number;
      financial_stress: number;
      output_residual_pp: number;
      inflation_residual_pp: number;
    }>;
  } | null;
  summary: {
    final_gdp_index: number;
    final_inflation: number;
    final_unemployment: number;
    final_corporate_debt: number;
    final_bank_credit: number;
    final_gini_wealth: number;
    cumulative_defaults: number;
    ledger_balanced: boolean;
    final_bank_reserves: number;
    final_central_bank_advances: number;
    final_government_debt: number;
    final_private_net_financial_wealth: number;
    godley_stocks_balanced: boolean;
    godley_flows_balanced: boolean;
    final_bank_capital: number;
    final_bank_capital_ratio: number;
    final_undercapitalized_banks: number;
    final_interbank_credit: number;
    cumulative_bank_profit_loss: number;
    cumulative_credit_rationed: number;
    cumulative_default_losses: number;
    cumulative_exports: number;
    cumulative_imports: number;
    cumulative_net_exports: number;
    final_productive_capital: number;
    cumulative_business_investment: number;
    final_household_debt: number;
    cumulative_household_defaults: number;
    cumulative_bank_resolutions: number;
    cumulative_public_recapitalization: number;
    cumulative_bail_in_losses: number;
    cumulative_unemployment_benefits: number;
    final_labor_force_participation: number;
    average_job_separation_rate: number;
    average_job_finding_rate: number;
  };
};

export type DesktopRuntimeStatus = {
  api_base: string;
  instance_id: string;
  ready: boolean;
  last_error?: string | null;
};

export async function getDesktopRuntimeStatus(): Promise<DesktopRuntimeStatus | null> {
  if (!isTauri()) return null;
  return invoke<DesktopRuntimeStatus>("backend_runtime_status");
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await apiFetch("/health");
  if (!response.ok) throw new Error(`Health check falhou: ${response.status}`);
  return response.json();
}

export async function simulate(spec: ScenarioSpec): Promise<SimulationResult> {
  const response = await apiFetch("/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec)
  });

  if (!response.ok) {
    const raw = await response.text();
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: string };
      detail = parsed.detail ?? raw;
    } catch {
      // Keep raw response if it is not JSON.
    }
    throw new Error(`Erro da API: ${response.status}${detail ? ` — ${detail}` : ""}`);
  }

  return response.json();
}

export type ScenarioDraft = {
  compiler: string;
  requires_review: boolean;
  recognized_changes: string[];
  assumptions: string[];
  spec: ScenarioSpec;
};

export async function compileScenario(prompt: string, base: ScenarioSpec): Promise<ScenarioDraft> {
  const response = await apiFetch("/scenario/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, base })
  });
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`Compilador de cenário falhou: ${response.status} — ${raw}`);
  }
  return response.json();
}


export type HubModuleInfo = {
  id: string;
  title: string;
  kind: string;
  description: string;
  capabilities: string[];
  dependencies: string[];
  routes: string[];
  available: boolean;
  status: string;
};

export async function listModules(): Promise<HubModuleInfo[]> {
  const response = await apiFetch("/modules");
  if (!response.ok) throw new Error(`Catálogo de módulos falhou: ${response.status}`);
  return response.json();
}

export type HubToolInfo = {
  id: string;
  module_id: string;
  title: string;
  description: string;
  capability: string;
  route?: string | null;
  output_kinds: string[];
  available: boolean;
  status: string;
};

export async function listTools(moduleId?: string): Promise<HubToolInfo[]> {
  const query = moduleId ? `?module_id=${encodeURIComponent(moduleId)}` : "";
  const response = await apiFetch(`/tools${query}`);
  if (!response.ok) throw new Error(`Catálogo de ferramentas falhou: ${response.status}`);
  return response.json();
}

export * from "./dataCalibrationApi";
export * from "./modelApi";
