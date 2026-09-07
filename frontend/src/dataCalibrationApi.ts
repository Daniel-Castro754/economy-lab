import { apiFetch, downloadFromResponse } from "./apiClient";
import type { DataProvenanceRecord, ScenarioSpec, SimulationResult } from "./api";

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
  provenance?: DataProvenanceRecord | null;
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
