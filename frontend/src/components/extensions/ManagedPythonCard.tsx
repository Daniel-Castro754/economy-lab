import { useEffect, useState } from "react";
import type { ExternalEngineCheck } from "../../engineApi";
import { requestRuntimeEngines } from "./runtimeEnginesApi";
import type { RuntimeEngines } from "./runtimeEnginesApi";
import { ValidationSummary } from "./ValidationSummary";

const ACTIVE_POLL_MS = 2000;
const IDLE_POLL_MS = 10000;

export function ManagedPythonCard({ checks }: { checks?: ExternalEngineCheck[] }) {
  const [runtime, setRuntime] = useState<RuntimeEngines | null>(null);
  const [error, setError] = useState("");
  const [log, setLog] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: number | undefined;
    async function tick() {
      try {
        const value = await requestRuntimeEngines<RuntimeEngines>();
        if (!alive) return;
        setRuntime(value);
        setError("");
        timer = window.setTimeout(tick, value.state === "installing" ? ACTIVE_POLL_MS : IDLE_POLL_MS);
      } catch (e) {
        if (!alive) return;
        setError(e instanceof Error ? e.message : "Falha ao consultar o ambiente.");
        timer = window.setTimeout(tick, IDLE_POLL_MS);
      }
    }
    void tick();
    return () => { alive = false; if (timer !== undefined) window.clearTimeout(timer); };
  }, []);

  async function install() {
    setBusy(true); setError(""); setLog(null);
    try { setRuntime(await requestRuntimeEngines<RuntimeEngines>("/install", { method: "POST" })); }
    catch (e) { setError(e instanceof Error ? e.message : "Falha na instalação."); }
    finally { setBusy(false); }
  }

  const mesaCheck = checks?.find(check => check.engine === "mesa");
  const harkCheck = checks?.find(check => check.engine === "hark");

  return <div className="extensionCard engineSettings">
    <h4>Mesa e HARK</h4>
    <p className="muted">Simple Macro e Economy Zero no preset Basic funcionam com o instalador base. Mesa e HARK usam um Python próprio, separado do Python do Windows.</p>
    {error && <p className="bad" role="alert">{error}</p>}
    {!runtime && <p role="status">Consultando ambiente…</p>}
    {runtime && <>
      <div className="settingsStatus"><span>Ambiente em uso</span><strong>{runtime.backend_kind === "managed" ? "Python do Economy Lab" : runtime.backend_kind === "bundled" ? "Backend base incorporado" : "Desenvolvimento"}</strong></div>
      <p className="runtimePath">{runtime.managed_directory}</p>
      <p role="status">{runtime.message}</p>
      {runtime.state === "installing" && <><progress max={100} value={runtime.progress} aria-label="Instalação dos motores" /><p>Mantenha o aplicativo aberto. O download requer internet e pode levar alguns minutos.</p></>}
      {runtime.restart_required && <p className="warning">Instalação concluída. Feche todas as janelas do Economy Lab e abra novamente para ativar os motores.</p>}
      <button type="button" disabled={busy || runtime.state === "installing" || !runtime.installer_available || runtime.restart_required} onClick={() => void install()}>{runtime.state === "installing" ? "Instalando motores…" : runtime.managed_python ? "Reparar Mesa e HARK" : "Instalar Mesa e HARK"}</button>
      {!runtime.installer_available && <p>Instalação integrada indisponível neste pacote. Use o instalador Windows atualizado.</p>}
      <p>Após instalar os motores, os comandos <code>economy-lab-python</code> e <code>economy-lab-pip</code> ficam no PATH do usuário para novos terminais. A instalação pela interface usa caminhos absolutos.</p>
      <button type="button" className="secondaryButton" onClick={async () => { try { setLog((await requestRuntimeEngines<{ log: string }>("/log")).log); } catch (e) { setError(String(e)); } }}>Ver diagnóstico da instalação</button>
      {log !== null && <pre className="runtimeLog">{log}</pre>}
    </>}
    <div className="extensionValidation">
      <p className="muted subsectionLabel">Mesa</p>
      <ValidationSummary check={mesaCheck} />
      <p className="muted subsectionLabel">HARK</p>
      <ValidationSummary check={harkCheck} />
    </div>
  </div>;
}
