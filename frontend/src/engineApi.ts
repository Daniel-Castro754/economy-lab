import { apiFetch } from "./apiClient";
import type { FinancialGuidancePoint, ScenarioSpec } from "./api";

export type EngineId = "mesa" | "hark" | "dynare" | "minsky";

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
  engine: EngineId;
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
  requested_engines: EngineId[];
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
  engines?: EngineId[];
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
