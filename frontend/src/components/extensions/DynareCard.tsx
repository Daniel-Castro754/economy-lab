import { useEffect, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import { getDynareStatus } from "../../engineApi";
import type { DynareStatus, ExternalEngineCheck } from "../../engineApi";
import { saveEnginePaths } from "./runtimeEnginesApi";
import type { EnginePaths } from "./runtimeEnginesApi";
import { PathField } from "./PathField";
import { ValidationSummary } from "./ValidationSummary";
import { ENGINES } from "./catalog";

const entry = ENGINES.find(item => item.id === "dynare")!;

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

type DynareCardProps = {
  paths: EnginePaths;
  onPathsSaved: (paths: EnginePaths) => void;
  check?: ExternalEngineCheck;
};

export function DynareCard({ paths, onPathsSaved, check }: DynareCardProps) {
  const [status, setStatus] = useState<DynareStatus | null>(null);
  const [octave, setOctave] = useState(paths.OCTAVE_EXECUTABLE);
  const [matlabPath, setMatlabPath] = useState(paths.DYNARE_MATLAB_PATH);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => { void getDynareStatus().then(setStatus).catch(e => setError(e instanceof Error ? e.message : String(e))); }, []);

  async function save() {
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await saveEnginePaths({ ...paths, OCTAVE_EXECUTABLE: octave, DYNARE_MATLAB_PATH: matlabPath });
      onPathsSaved(saved);
      setMessage("Caminhos salvos. Reabra o aplicativo para atualizar todos os indicadores dos módulos.");
      setStatus(await getDynareStatus());
    } catch (e) { setError(e instanceof Error ? e.message : "Falha ao salvar caminhos."); }
    finally { setBusy(false); }
  }

  return <div className="extensionCard">
    <h4>{entry.name}</h4>
    <p className="muted">{entry.description}</p>
    <div className="extensionLinks">
      {entry.links.map(link => <button type="button" key={link.url} className="secondaryButton" onClick={() => void openExternalLink(link.url)}>{link.label}</button>)}
    </div>
    {status && <div className="settingsStatus"><span>Status</span><strong className={status.ready ? "ok" : "bad"}>{status.ready ? "Pronto" : status.configured ? "Configurado, mas indisponível" : "Não configurado"}</strong></div>}
    {status?.dynare_version_hint && <p className="muted">Versão detectada: {status.dynare_version_hint}</p>}
    {status?.error && <p className="muted">{status.error}</p>}
    {error && <p className="bad" role="alert">{error}</p>}
    <PathField label="Executável do Octave" value={octave} placeholder="C:\Program Files\GNU Octave\octave-cli.exe" kind="file" onChange={setOctave} />
    <PathField label="Pasta matlab do Dynare" value={matlabPath} placeholder="C:\dynare\matlab" kind="folder" onChange={setMatlabPath} />
    <button type="button" className="secondaryButton" disabled={busy} onClick={() => void save()}>Salvar caminhos</button>
    {message && <p role="status">{message}</p>}
    <ValidationSummary check={check} />
  </div>;
}
