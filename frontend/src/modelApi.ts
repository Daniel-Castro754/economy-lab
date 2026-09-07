import { apiFetch } from "./apiClient";
import type { EconomicShockSpec, ScenarioSpec } from "./api";

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
