import { apiFetch, downloadFromResponse } from "./apiClient";
import type { ScenarioSpec, SimulationResult } from "./api";

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
  const response = await apiFetch(`/jobs/${jobId}`, { signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error(`Consulta da simulação falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export async function cancelSimulationJob(jobId: string): Promise<SimulationJobRecord> {
  const response = await apiFetch(`/jobs/${jobId}/cancel`, { method: "POST" });
  if (!response.ok) throw new Error(`Cancelamento falhou: ${response.status} — ${await response.text()}`);
  return response.json();
}

export type StorageStatus = {
  database_path: string;
  schema_version: number;
  projects: number;
  runs: number;
  experiments: number;
  profiles: number;
  jobs: number;
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
  manifest_hash?: string | null;
  experiment_hash?: string | null;
  replay_of_run_id?: string | null;
};

export type RunRecord = RunSummary & {
  scenario: ScenarioSpec;
  result: SimulationResult;
  manifest?: Record<string, unknown> | null;
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
