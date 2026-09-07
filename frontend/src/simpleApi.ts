import { apiFetch, downloadFromResponse } from "./apiClient";
import type { ScenarioSpec } from "./api";

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
