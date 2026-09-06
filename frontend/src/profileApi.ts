import { apiFetch } from "./apiClient";
import type { ScenarioSpec } from "./api";

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
