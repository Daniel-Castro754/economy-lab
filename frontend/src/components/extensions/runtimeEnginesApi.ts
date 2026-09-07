import { apiFetch } from "../../apiClient";

export type EnginePaths = { OCTAVE_EXECUTABLE: string; DYNARE_MATLAB_PATH: string; MINSKY_REST_URL: string };
export const emptyEnginePaths: EnginePaths = { OCTAVE_EXECUTABLE: "", DYNARE_MATLAB_PATH: "", MINSKY_REST_URL: "" };

export type RuntimeEngines = {
  state: string; message: string; progress: number; installer_available: boolean;
  managed_directory: string; managed_python: string | null; active_python: string;
  backend_kind: string; restart_required: boolean; commands_directory: string; paths: Partial<EnginePaths>;
};

export async function requestRuntimeEngines<T>(path = "", init?: RequestInit): Promise<T> {
  const response = await apiFetch(`/runtime/engines${path}`, init);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Não foi possível configurar os motores.");
  return data;
}

export async function saveEnginePaths(paths: EnginePaths): Promise<EnginePaths> {
  return requestRuntimeEngines<EnginePaths>("/paths", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(paths),
  });
}
