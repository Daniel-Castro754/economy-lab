import { invoke, isTauri } from "@tauri-apps/api/core";

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
  apiBasePromise ??= resolveApiBase().catch((error) => {
    apiBasePromise = null;
    throw error;
  });
  return apiBasePromise;
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const base = await apiBase();
  return fetch(`${base}${path}`, init);
}

export async function downloadFromResponse(response: Response, fallbackName: string): Promise<void> {
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
