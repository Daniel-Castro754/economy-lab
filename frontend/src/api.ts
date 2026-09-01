import { invoke, isTauri } from "@tauri-apps/api/core";

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

let apiBasePromise: Promise<string> | null = null;

async function resolveApiBase(): Promise<string> {
  const configured = import.meta.env.VITE_API_URL as string | undefined;
  if (configured) return configured.replace(/\/$/, "");

  if (isTauri()) {
    const desktopBase = await invoke<string>("backend_api_base");
    return `${desktopBase.replace(/\/$/, "")}/api/v1`;
  }

  return "http://127.0.0.1:8765/api/v1";
}

async function apiBase(): Promise<string> {
  apiBasePromise ??= resolveApiBase();
  return apiBasePromise;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const base = await apiBase();
  return fetch(`${base}${path}`, init);
}

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

export type SimulationJobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export type SimulationJobRecord = {
  id: string;
  project_id?: string | null;
  kind: "simulation";
  status: SimulationJobStatus;
  run_id?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  progress: number;
  current_step: number;
  total_steps: number;
  stage: string;
  timeout_seconds: number;
  cancellation_requested: boolean;
  error_code?: string | null;
  error_message?: string | null;
  scenario: ScenarioSpec;
  result?: SimulationResult | null;
  save_scenario: boolean;
};

export async function createSimulationJob(
  scenario: ScenarioSpec,
  projectId: string | null,
  timeoutSeconds = 300,
): Promise<SimulationJobRecord> {
  const response = await apiFetch("/jobs/simulations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario,
      project_id: projectId,
      save_scenario: true,
      timeout_seconds: timeoutSeconds,
    }),
  });
  if (!response.ok) throw new Error(`Fila de simulação falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function getSimulationJob(jobId: string): Promise<SimulationJobRecord> {
  const response = await apiFetch(`/jobs/${jobId}`);
  if (!response.ok) throw new Error(`Consulta da simulação falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function cancelSimulationJob(jobId: string): Promise<SimulationJobRecord> {
  const response = await apiFetch(`/jobs/${jobId}/cancel`, { method: "POST" });
  if (!response.ok) throw new Error(`Cancelamento falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}


export type SimpleScenarioId = "baseline" | "global_recession" | "volatile";
export type SimpleExternalYear = { year: number; world_growth: number; consumer_confidence: number; label: string };
export type SimpleScenarioInfo = { id: SimpleScenarioId; title: string; description: string; years: SimpleExternalYear[] };
export type SimpleInitialConfig = {
  scenario_id: SimpleScenarioId; initial_gdp_index: number; initial_potential_gdp_index: number;
  initial_inflation: number; initial_unemployment: number; initial_debt_to_gdp: number; initial_approval: number;
  potential_growth: number; inflation_target: number; natural_unemployment: number; neutral_interest_rate: number;
  baseline_income_tax: number; baseline_corporate_tax: number; baseline_government_spending: number;
};
export type SimplePolicyDecision = { interest_rate: number; income_tax: number; corporate_tax: number; government_spending: number };
export type SimpleEconomyState = {
  year: number; gdp_index: number; potential_gdp_index: number; real_gdp_growth: number; inflation: number; unemployment: number;
  debt_to_gdp: number; budget_deficit_to_gdp: number; primary_balance_to_gdp: number; tax_revenue_to_gdp: number;
  debt_interest_cost_to_gdp: number; output_gap: number; approval: number; price_index: number;
  last_interest_rate: number; last_income_tax: number; last_corporate_tax: number; last_government_spending: number;
};
export type SimpleScoreBreakdown = { growth: number; unemployment: number; inflation: number; fiscal: number; total: number };
export type SimpleYearResult = { year: number; external: SimpleExternalYear; decision: SimplePolicyDecision; state: SimpleEconomyState; score: SimpleScoreBreakdown; explanation: string[]; warnings: string[] };
export type SimpleStartResponse = { model: string; warning: string; config: SimpleInitialConfig; state: SimpleEconomyState; next_external: SimpleExternalYear };
export type SimpleStepResponse = { model: string; result: SimpleYearResult; completed: boolean; next_external?: SimpleExternalYear | null };
export type SimpleRunResult = { model: string; warning: string; config: SimpleInitialConfig; initial_state: SimpleEconomyState; years: SimpleYearResult[]; final_state: SimpleEconomyState; completed_years: number };
export type SimpleToAdvancedResponse = { scenario: ScenarioSpec; mapped_fields: string[]; limitations: string[] };

export async function listSimpleScenarios(): Promise<SimpleScenarioInfo[]> {
  const response = await apiFetch("/simple/scenarios");
  if (!response.ok) throw new Error(`Cenários simples falharam: ${response.status}`);
  return response.json();
}

export async function startSimple(config: Partial<SimpleInitialConfig>): Promise<SimpleStartResponse> {
  const response = await apiFetch("/simple/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config) });
  if (!response.ok) throw new Error(`Inicialização simples falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function stepSimple(config: SimpleInitialConfig, state: SimpleEconomyState, decision: SimplePolicyDecision): Promise<SimpleStepResponse> {
  const response = await apiFetch("/simple/step", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ config, state, decision }) });
  if (!response.ok) throw new Error(`Turno simples falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function convertSimpleToAdvanced(config: SimpleInitialConfig, state: SimpleEconomyState, decision?: SimplePolicyDecision, months = 24): Promise<SimpleToAdvancedResponse> {
  const response = await apiFetch("/simple/to-advanced", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ config, state, decision, months }) });
  if (!response.ok) throw new Error(`Conversão para o modo detalhado falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function exportSimpleFile(format: "csv" | "xlsx", result: SimpleRunResult): Promise<void> {
  const response = await apiFetch(`/exports/simple.${format}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(result) });
  return downloadFromResponse(response, `economy-lab-simple.${format}`);
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


export type MinskyStatus = {
  configured: boolean;
  reachable: boolean;
  object_type?: string | null;
  model_time?: number | null;
  error?: string | null;
};

export async function getMinskyStatus(): Promise<MinskyStatus> {
  const response = await apiFetch("/minsky/status");
  if (!response.ok) throw new Error(`Minsky status falhou: ${response.status}`);
  return response.json();
}

export async function exportMinsky(spec: ScenarioSpec): Promise<Record<string, unknown>> {
  const response = await apiFetch("/minsky/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec)
  });
  if (!response.ok) throw new Error(`Minsky export falhou: ${response.status}`);
  return response.json();
}


export type DynareStatus = {
  configured: boolean;
  ready: boolean;
  octave_executable?: string | null;
  dynare_matlab_path?: string | null;
  dynare_version_hint?: string | null;
  error?: string | null;
};

export async function getDynareStatus(): Promise<DynareStatus> {
  const response = await apiFetch("/dynare/status");
  if (!response.ok) throw new Error(`Dynare status falhou: ${response.status}`);
  return response.json();
}

export type StorageStatus = {
  database_path: string;
  schema_version: number;
  projects: number;
  runs: number;
  experiments: number;
  profiles: number;
};

export type ProjectSummary = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  last_run_id?: string | null;
  run_count: number;
};

export type ProjectRecord = ProjectSummary & {
  scenario: ScenarioSpec;
};

export type RunSummary = {
  id: string;
  project_id: string;
  scenario_name: string;
  created_at: string;
  duration_ms: number;
  engine_version: string;
  final_gdp_index: number;
  final_inflation: number;
  final_unemployment: number;
  ledger_balanced: boolean;
  godley_stocks_balanced: boolean;
  godley_flows_balanced: boolean;
};

export type RunRecord = RunSummary & {
  scenario: ScenarioSpec;
  result: SimulationResult;
};

export async function getStorageStatus(): Promise<StorageStatus> {
  const response = await apiFetch("/storage/status");
  if (!response.ok) throw new Error(`Storage status falhou: ${response.status}`);
  return response.json();
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const response = await apiFetch("/projects");
  if (!response.ok) throw new Error(`Listagem de projetos falhou: ${response.status}`);
  return response.json();
}

export async function createProject(name: string, scenario: ScenarioSpec, description = ""): Promise<ProjectRecord> {
  const response = await apiFetch("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, scenario })
  });
  if (!response.ok) throw new Error(`Criação de projeto falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function getProject(projectId: string): Promise<ProjectRecord> {
  const response = await apiFetch(`/projects/${projectId}`);
  if (!response.ok) throw new Error(`Abertura de projeto falhou: ${response.status}`);
  return response.json();
}

export async function updateProject(projectId: string, name: string, scenario: ScenarioSpec, description = ""): Promise<ProjectRecord> {
  const response = await apiFetch(`/projects/${projectId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, scenario })
  });
  if (!response.ok) throw new Error(`Salvamento de projeto falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await apiFetch(`/projects/${projectId}`, { method: "DELETE" });
  if (!response.ok && response.status !== 204) throw new Error(`Exclusão de projeto falhou: ${response.status}`);
}

export async function listProjectRuns(projectId: string, limit = 20): Promise<RunSummary[]> {
  const response = await apiFetch(`/projects/${projectId}/runs?limit=${limit}`);
  if (!response.ok) throw new Error(`Histórico do projeto falhou: ${response.status}`);
  return response.json();
}

export async function getRun(runId: string): Promise<RunRecord> {
  const response = await apiFetch(`/runs/${runId}`);
  if (!response.ok) throw new Error(`Abertura da execução falhou: ${response.status}`);
  return response.json();
}

export async function simulateProject(projectId: string, scenario: ScenarioSpec): Promise<{ project: ProjectRecord; run: RunRecord; result: SimulationResult }> {
  const response = await apiFetch(`/projects/${projectId}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario, save_scenario: true })
  });
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`Simulação salva falhou: ${response.status}${raw ? ` — ${raw}` : ""}`);
  }
  return response.json();
}

export type BatchAxis = "policy_rate" | "income_tax" | "public_spending_change" | "minimum_bank_capital_ratio" | "target_reserve_ratio";

export type BatchAggregate = {
  axis_value: number;
  runs: number;
  mean_gdp_index: number;
  std_gdp_index: number;
  mean_inflation: number;
  std_inflation: number;
  mean_unemployment: number;
  std_unemployment: number;
  mean_defaults: number;
  mean_bank_credit: number;
  mean_bank_capital_ratio: number;
  mean_credit_rationed: number;
  all_accounting_balanced: boolean;
};

export type BatchExperimentResponse = {
  experiment_engine: string;
  analytics_engine: string;
  axis: BatchAxis;
  values: number[];
  repetitions: number;
  total_runs: number;
  duration_ms: number;
  base_scenario: ScenarioSpec;
  aggregates: BatchAggregate[];
  runs: Array<{
    axis_value: number;
    repetition: number;
    seed: number;
    duration_ms: number;
    final_gdp_index: number;
    final_inflation: number;
    final_unemployment: number;
    cumulative_defaults: number;
    final_bank_credit: number;
    final_bank_capital_ratio: number;
    cumulative_credit_rationed: number;
    ledger_balanced: boolean;
    godley_stocks_balanced: boolean;
    godley_flows_balanced: boolean;
  }>;
  warning: string;
};

export type ExperimentSummary = {
  id: string;
  project_id: string;
  created_at: string;
  axis: BatchAxis;
  values: number[];
  repetitions: number;
  total_runs: number;
  duration_ms: number;
  engine_version: string;
};

export type ExperimentRecord = ExperimentSummary & { result: BatchExperimentResponse };

export async function runBatchExperiment(
  base: ScenarioSpec,
  axis: BatchAxis,
  values: number[],
  repetitions: number
): Promise<BatchExperimentResponse> {
  const response = await apiFetch("/experiments/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base, axis, values, repetitions, seed_step: 1 })
  });
  if (!response.ok) throw new Error(`Experimento em lote falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function runProjectExperiment(
  projectId: string,
  scenario: ScenarioSpec,
  axis: BatchAxis,
  values: number[],
  repetitions: number
): Promise<ExperimentRecord> {
  const response = await apiFetch(`/projects/${projectId}/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario, axis, values, repetitions, seed_step: 1 })
  });
  if (!response.ok) throw new Error(`Experimento salvo falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function listProjectExperiments(projectId: string, limit = 10): Promise<ExperimentSummary[]> {
  const response = await apiFetch(`/projects/${projectId}/experiments?limit=${limit}`);
  if (!response.ok) throw new Error(`Histórico de experimentos falhou: ${response.status}`);
  return response.json();
}

export async function getExperiment(experimentId: string): Promise<ExperimentRecord> {
  const response = await apiFetch(`/experiments/${experimentId}`);
  if (!response.ok) throw new Error(`Abertura do experimento falhou: ${response.status}`);
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

async function downloadFromResponse(response: Response, fallbackName: string): Promise<void> {
  if (!response.ok) throw new Error(`Exportação falhou: ${response.status} — ${await response.text()}`);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function exportSimulationFile(
  format: "csv" | "xlsx",
  scenario: ScenarioSpec,
  result: SimulationResult
): Promise<void> {
  const response = await apiFetch(`/exports/simulation.${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario, result })
  });
  return downloadFromResponse(response, `economy-lab-simulation.${format}`);
}

export async function exportBatchFile(
  format: "csv" | "xlsx",
  result: BatchExperimentResponse
): Promise<void> {
  const response = await apiFetch(`/exports/batch.${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result })
  });
  return downloadFromResponse(response, `economy-lab-experiment.${format}`);
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

// v1.5 standalone module laboratories
export type DynareLabRequest = {
  irf_periods: number;
  monetary_shock_bp: number;
  neutral_nominal_rate: number;
  beta: number;
  sigma: number;
  kappa: number;
  rho_i: number;
  phi_pi: number;
  phi_x: number;
  timeout_seconds: number;
};

export type DynareLabResponse = {
  engine: string;
  model_name: string;
  model_kind: string;
  period_unit: string;
  shock_name: string;
  shock_size_pp: number;
  neutral_nominal_rate: number;
  parameters: Record<string, number>;
  irf: Array<{ period: number; output_gap: number; inflation_gap: number; policy_rate_gap: number }>;
  warning: string;
};

export async function getDynareTemplate(request: DynareLabRequest): Promise<string> {
  const response = await apiFetch("/labs/dynare/template", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error(`Template Dynare falhou: ${response.status} — ${await response.text()}`);
  const payload = await response.json() as { source: string };
  return payload.source;
}

export async function runDynareLab(request: DynareLabRequest): Promise<DynareLabResponse> {
  const response = await apiFetch("/labs/dynare/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error(`Dynare Lab falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export type MesaLabRequest = { agents: number; steps: number; initial_wealth: number; transfer_amount: number; seed: number };
export type MesaComponentRequest = {
  component: "activation" | "household_search" | "firm_behavior" | "labor_market";
  steps: number; seed: number; activation_pattern: "random" | "fixed"; shopping_sample_size: number;
  cheapest_choice_probability: number; price_adjustment_strength: number; hiring_strength: number; layoff_strength: number; matching_efficiency: number;
};
export type MesaComponentResponse = {
  engine: string; component: string; scenario_patch: Record<string, unknown>; metrics: Record<string, number | string>; path: Array<Record<string, number>>; warning: string;
};
export type MesaLabResponse = {
  engine: string; model: string; agents: number; steps: number; seed: number;
  initial_total_wealth: number; final_total_wealth: number; mean_wealth: number; median_wealth: number;
  max_wealth: number; gini: number; zero_wealth_share: number;
  path: Array<{ step: number; gini: number; zero_wealth_share: number; max_wealth: number }>;
  warning: string;
};
export async function runMesaLab(request: MesaLabRequest): Promise<MesaLabResponse> {
  const response = await apiFetch("/labs/mesa/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error(`Mesa Lab falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function runMesaComponentLab(request: MesaComponentRequest): Promise<MesaComponentResponse> {
  const response = await apiFetch("/labs/mesa/component/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error(`Mesa Component Lab falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export type HarkLabRequest = {
  annual_interest_rate: number; crra: number; annual_discount_factor: number;
  unemployment_probability: number; unemployment_replacement_rate: number;
  permanent_shock_std: number; transitory_shock_std: number; permanent_income_memory: number;
  income_groups: number; income_risk_dispersion: number; max_market_resources: number; points: number;
};
export type HarkPolicyPoint = { market_resources: number; consumption: number; saving: number; consumption_share: number };
export type HarkLabResponse = {
  engine: string; model: string; parameters: Record<string, number>;
  policy_curve: HarkPolicyPoint[];
  group_profiles: Array<{ income_group: number; unemployment_probability: number; policy_curve: HarkPolicyPoint[] }>;
  warning: string;
};
export async function runHarkLab(request: HarkLabRequest): Promise<HarkLabResponse> {
  const response = await apiFetch("/labs/hark/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error(`HARK Lab falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export type MinskyLabAction = "members" | "signature" | "step" | "reset" | "get_variable" | "set_variable";
export async function runMinskyCommand(payload: { action: MinskyLabAction; path?: string; variable_id?: string; value?: number }): Promise<unknown> {
  const response = await apiFetch("/labs/minsky/command", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`Minsky Lab falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export type ProfileKind = "macro" | "financial" | "agents" | "households" | "households_market" | "firms" | "labor_market";
export type ProfileSummary = {
  id: string; name: string; description: string; kind: ProfileKind; module_id: string; compatibility: string; created_at: string; updated_at: string;
};
export type ProfileRecord = ProfileSummary & { payload: Record<string, unknown>; scenario_patch: Record<string, unknown> };
export type SimulationPresetInfo = { id: string; title: string; description: string; requirements: string[]; patch: Record<string, unknown> };

export async function listProfiles(): Promise<ProfileSummary[]> {
  const response = await apiFetch("/profiles");
  if (!response.ok) throw new Error(`Profiles falharam: ${response.status}`);
  return response.json();
}

export async function createLabProfile(payload: { module_id: "dynare" | "minsky" | "mesa" | "hark"; name: string; description?: string; inputs: Record<string, unknown>; outputs?: Record<string, unknown> | null }): Promise<ProfileRecord> {
  const response = await apiFetch("/profiles/from-lab", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error(`Criação do Profile falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function applyProfile(profileId: string, scenario: ScenarioSpec): Promise<{ profile: ProfileSummary; scenario: ScenarioSpec; changes: string[] }> {
  const response = await apiFetch(`/profiles/${profileId}/apply`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario }) });
  if (!response.ok) throw new Error(`Aplicação do Profile falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function deleteProfile(profileId: string): Promise<void> {
  const response = await apiFetch(`/profiles/${profileId}`, { method: "DELETE" });
  if (!response.ok) throw new Error(`Exclusão do Profile falhou: ${response.status}`);
}

export async function listSimulationPresets(): Promise<SimulationPresetInfo[]> {
  const response = await apiFetch("/simulation/presets");
  if (!response.ok) throw new Error(`Presets falharam: ${response.status}`);
  return response.json();
}

export async function applySimulationPreset(presetId: string, scenario: ScenarioSpec): Promise<ScenarioSpec> {
  const response = await apiFetch(`/simulation/presets/${presetId}/apply`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario }) });
  if (!response.ok) throw new Error(`Preset falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}



export type MinskyFinancialMapping = {
  minimum_bank_capital_ratio: string;
  target_reserve_ratio: string;
  credit_supply_factor: string;
  default_writeoff_ratio: string;
  interbank_spread: string;
  central_bank_penalty_spread: string;
};

export type MinskyFinancialCaptureRequest = {
  steps: number;
  reset_before: boolean;
  unit_mode: "decimal" | "percent";
  mapping: MinskyFinancialMapping;
};

export type MinskyFinancialCaptureResponse = {
  engine: string;
  unit_mode: string;
  mapping: MinskyFinancialMapping;
  points: FinancialGuidancePoint[];
  warning: string;
};

export async function runMinskyFinancialController(request: MinskyFinancialCaptureRequest): Promise<MinskyFinancialCaptureResponse> {
  const response = await apiFetch("/labs/minsky/financial/run", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error(`Controlador financeiro Minsky falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export type ExternalEngineValidationStatus = "pass" | "fail" | "unavailable";
export type ExternalValidationStage = {
  name: string;
  status: "pass" | "fail" | "unavailable" | "skipped";
  duration_ms: number;
  summary: string;
  details: Record<string, unknown>;
  error?: string | null;
};
export type ExternalEngineCheck = {
  engine: "mesa" | "hark" | "dynare" | "minsky";
  status: ExternalEngineValidationStatus;
  installed_or_configured: boolean;
  version?: string | null;
  duration_ms: number;
  summary: string;
  details: Record<string, unknown>;
  error?: string | null;
  qualification_level: "none" | "detected" | "read-only-verified" | "runtime-verified";
  compatibility: "compatible" | "warning" | "unknown";
  target_version?: string | null;
  integrated_smoke_passed: boolean;
  stages: ExternalValidationStage[];
};
export type ExternalValidationReport = {
  schema: string;
  report_id: string;
  report_digest: string;
  generated_at: string;
  economy_lab_version: string;
  platform: string;
  python_version: string;
  environment: Record<string, unknown>;
  requested_engines: Array<"mesa" | "hark" | "dynare" | "minsky">;
  smoke_tests: boolean;
  integration_tests: boolean;
  status: "ready" | "partial" | "failed";
  qualification_ready: boolean;
  passed: number;
  failed: number;
  unavailable: number;
  runtime_verified: number;
  read_only_verified: number;
  checks: ExternalEngineCheck[];
};

export async function validateExternalEngines(payload: {
  engines?: Array<"mesa" | "hark" | "dynare" | "minsky">;
  smoke_tests?: boolean;
  integration_tests?: boolean;
  dynare_timeout_seconds?: number;
  minsky_timeout_seconds?: number;
} = {}): Promise<ExternalValidationReport> {
  const response = await apiFetch("/validation/external-engines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      engines: payload.engines ?? ["mesa", "hark", "dynare", "minsky"],
      smoke_tests: payload.smoke_tests ?? true,
      integration_tests: payload.integration_tests ?? true,
      dynare_timeout_seconds: payload.dynare_timeout_seconds ?? 60,
      minsky_timeout_seconds: payload.minsky_timeout_seconds ?? 3
    })
  });
  if (!response.ok) throw new Error(`Validação dos motores falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

// v2.1 public economic data + calibration layer
export type DataSourceId = "bcb_sgs" | "ibge_sidra" | "world_bank" | "ipeadata";
export type EconomicObservation = { date: string; value: number };
export type EconomicSeries = {
  source: DataSourceId;
  series_id: string;
  title: string;
  unit: string;
  frequency: string;
  fetched_at: string;
  cached: boolean;
  request_url: string;
  metadata: Record<string, unknown>;
  observations: EconomicObservation[];
  warning: string;
};
export type DataSourceCatalogItem = {
  id: DataSourceId;
  title: string;
  description: string;
  identifier_label: string;
  examples: Array<Record<string, unknown>>;
  notes: string[];
};
export type DataFetchRequest = {
  source: DataSourceId;
  series_id: string;
  title?: string;
  unit?: string;
  frequency?: string;
  start_date?: string | null;
  end_date?: string | null;
  source_options?: Record<string, string | number | boolean>;
  use_cache?: boolean;
  refresh?: boolean;
  timeout_seconds?: number;
};
export type CalibrationMetric = "inflation" | "unemployment" | "policy_rate" | "gdp_growth" | "bank_credit_growth" | "bank_capital_ratio";
export type CalibrationStatistic = "last" | "mean" | "median" | "std";
export type CalibrationComparisonMode = "moment" | "aligned_path";
export type CalibrationFrequency = "auto" | "monthly" | "quarterly" | "annual";
export type CalibrationAggregation = "last" | "mean";
export type CalibrationParameter = "initial_inflation" | "initial_unemployment" | "policy_rate" | "public_spending_change" | "minimum_bank_capital_ratio" | "target_reserve_ratio" | "labor_matching_efficiency";
export type CalibrationTargetInput = {
  metric: CalibrationMetric;
  series: EconomicSeries;
  statistic: CalibrationStatistic;
  weight?: number;
  scale_floor?: number;
  comparison_mode?: CalibrationComparisonMode;
  alignment_frequency?: CalibrationFrequency;
  aggregation?: CalibrationAggregation;
};
export type CalibrationMetricResult = {
  metric: CalibrationMetric;
  statistic: CalibrationStatistic;
  source: DataSourceId;
  series_id: string;
  real_value: number;
  simulated_value: number;
  error: number;
  normalized_error: number;
  weight: number;
  weighted_loss: number;
  real_observations: number;
  simulated_observations: number;
  comparison_mode: CalibrationComparisonMode;
  aligned_frequency?: string | null;
  aligned_observations: number;
  path_mae?: number | null;
  path_rmse?: number | null;
  aligned_points: Array<{ period: string; real_value: number; simulated_value: number; error: number }>;
};
export type CalibrationResponse = {
  engine: string;
  score: number;
  normalized_rmse: number;
  metrics: CalibrationMetricResult[];
  suggested_scenario_patch: Record<string, number>;
  requires_review: boolean;
  warning: string;
};
export type CalibrationFitStep = { evaluation: number; round: number; parameter: CalibrationParameter | "baseline"; candidate_value?: number | null; score: number; accepted: boolean };
export type CalibrationFitResponse = {
  engine: string; baseline_score: number; best_score: number; evaluations: number; rounds_completed: number; converged: boolean;
  parameters: CalibrationParameter[]; best_scenario_patch: Record<string, number>; final_calibration: CalibrationResponse;
  validation_score?: number | null; validation_calibration?: CalibrationResponse | null;
  trace: CalibrationFitStep[]; requires_review: boolean; warning: string;
};

export async function listDataSources(): Promise<DataSourceCatalogItem[]> {
  const response = await apiFetch("/data/catalog");
  if (!response.ok) throw new Error(`Catálogo de dados falhou: ${response.status}`);
  return response.json();
}

export async function fetchEconomicSeries(request: DataFetchRequest): Promise<EconomicSeries> {
  const response = await apiFetch("/data/fetch", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request)
  });
  if (!response.ok) throw new Error(`Busca de série falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function evaluateCalibration(payload: {
  scenario: ScenarioSpec; result: SimulationResult; targets: CalibrationTargetInput[]; simulation_start_date?: string | null; simulation_end_date?: string | null;
}): Promise<CalibrationResponse> {
  const response = await apiFetch("/calibration/evaluate", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`Calibração falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function fitCalibration(payload: {
  scenario: ScenarioSpec; targets: CalibrationTargetInput[]; parameters: CalibrationParameter[]; simulation_start_date?: string | null; simulation_end_date?: string | null; max_evaluations?: number; max_rounds?: number; minimum_score_improvement?: number; training_end_date?: string | null; validation_start_date?: string | null;
}): Promise<CalibrationFitResponse> {
  const response = await apiFetch("/calibration/fit", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`Ajuste limitado falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function exportCalibrationFile(scenario: ScenarioSpec, calibration: CalibrationResponse, fit?: CalibrationFitResponse | null): Promise<void> {
  const response = await apiFetch("/exports/calibration.xlsx", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario, calibration, fit: fit ?? null })
  });
  return downloadFromResponse(response, "economy-lab-calibration.xlsx");
}

// v2.2 safe ModelSpec / AI model-builder layer
export type ModelSpec = {
  schema_version: "economy-lab-modelspec-v1.0";
  name: string;
  description: string;
  source_prompt: string;
  horizon_months: number;
  population: { households: number; firms: number; banks: number };
  engines: {
    agents: "native" | "mesa";
    households: "heuristic" | "hark";
    financial: "native" | "minsky_profile";
    macro: "off" | "dynare";
    macro_coupling: "advisory" | "hybrid";
    macro_recalibration: "static_irf" | "quarterly";
  };
  markets: { labor: boolean; goods: boolean; credit: boolean; external: boolean };
  policy: { inflation: number; unemployment: number; policy_rate: number; income_tax: number; public_spending_change: number };
  traits: {
    economic_base: "generic" | "mixed" | "commodity_exporter" | "industrial" | "services";
    inequality: "low" | "medium" | "high";
    banking_concentration: "low" | "medium" | "high";
    openness: "low" | "medium" | "high";
  };
  shocks: EconomicShockSpec[];
  hark_income_groups: number;
  hark_income_risk_dispersion: number;
  productive_capital: boolean;
  household_credit: boolean;
  unemployment_benefits: boolean;
  unemployment_benefit_replacement_rate: number;
  labor_supply_mode: "inelastic" | "reservation_wage";
  bank_resolution_mode: "none" | "government_recapitalization" | "bail_in";
  requested_capabilities: string[];
  recommended_modules: Array<"mesa" | "hark" | "minsky" | "dynare">;
  profile_refs: Record<string, string>;
  assumptions: string[];
};

export type ModelCompilationReport = {
  status: "full" | "partial";
  applied_fields: string[];
  partial_features: string[];
  unsupported_features: string[];
  assumptions: string[];
  warning: string;
};

export type ModelDraft = {
  provider: string;
  requires_review: boolean;
  recognized_changes: string[];
  provider_assumptions: string[];
  model_spec: ModelSpec;
  compiled_scenario: ScenarioSpec;
  compilation: ModelCompilationReport;
};

export async function compileModel(prompt: string, base?: ModelSpec | null): Promise<ModelDraft> {
  const response = await apiFetch("/model/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, base: base ?? null })
  });
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`Model Builder falhou: ${response.status} — ${raw}`);
  }
  return response.json();
}

export async function validateModelSpecCandidate(candidate: Record<string, unknown>): Promise<{
  valid: boolean;
  model_spec: ModelSpec;
  compiled_scenario: ScenarioSpec;
  compilation: ModelCompilationReport;
}> {
  const response = await apiFetch("/model/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate })
  });
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`ModelSpec inválido: ${response.status} — ${raw}`);
  }
  return response.json();
}
