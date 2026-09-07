import { useEffect, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { getMinskyStatus } from "../../engineApi";
import type { MinskyStatus, ExternalEngineCheck } from "../../engineApi";
import { saveEnginePaths } from "./runtimeEnginesApi";
import type { EnginePaths } from "./runtimeEnginesApi";
import { ValidationSummary } from "./ValidationSummary";
import { ENGINES } from "./catalog";

const entry = ENGINES.find(item => item.id === "minsky")!;

async function openExternalLink(url: string) {
  if (isTauri()) {
    try {
      const { openUrl } = await import("@tauri-apps/plugin-opener");
      await openUrl(url);
      return;
    } catch {
      // fall through to browser fallback below
    }
  }
  window.open(url, "_blank", "noreferrer");
}

type MinskyCardProps = {
  paths: EnginePaths;
  onPathsSaved: (paths: EnginePaths) => void;
  check?: ExternalEngineCheck;
};

export function MinskyCard({ paths, onPathsSaved, check }: MinskyCardProps) {
  const [status, setStatus] = useState<MinskyStatus | null>(null);
  const [restUrl, setRestUrl] = useState(paths.MINSKY_REST_URL);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => { void getMinskyStatus().then(setStatus).catch(e => setError(e instanceof Error ? e.message : String(e))); }, []);

  async function save() {
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await saveEnginePaths({ ...paths, MINSKY_REST_URL: restUrl });
      onPathsSaved(saved);
      setMessage("Caminhos salvos. Reabra o aplicativo para atualizar todos os indicadores dos módulos.");
      setStatus(await getMinskyStatus());
    } catch (e) { setError(e instanceof Error ? e.message : "Falha ao salvar caminhos."); }
    finally { setBusy(false); }
  }

  return <div className="extensionCard">
    <h4>{entry.name}</h4>
    <p className="muted">{entry.description}</p>
    <div className="extensionLinks">
      {entry.links.map(link => <button type="button" key={link.url} className="secondaryButton" onClick={() => void openExternalLink(link.url)}>{link.label}</button>)}
    </div>
    {status && <div className="settingsStatus"><span>Status</span><strong className={status.reachable ? "ok" : "bad"}>{status.reachable ? "Conectado" : status.configured ? "Configurado, mas offline" : "Não configurado"}</strong></div>}
    {status?.object_type && <p className="muted">Modelo carregado: {status.object_type}</p>}
    {status?.error && <p className="muted">{status.error}</p>}
    {error && <p className="bad" role="alert">{error}</p>}
    <label className="settingsField"><span>Endereço REST do Minsky</span><input value={restUrl} placeholder="http://127.0.0.1:8000" onChange={event => setRestUrl(event.target.value)} /></label>
    <button type="button" className="secondaryButton" disabled={busy} onClick={() => void save()}>Salvar endereço</button>
    {message && <p role="status">{message}</p>}
    <ValidationSummary check={check} />
  </div>;
}
