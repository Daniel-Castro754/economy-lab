import { useEffect, useState } from "react";
import { apiFetch } from "../apiClient";

type Paths = { OCTAVE_EXECUTABLE: string; DYNARE_MATLAB_PATH: string; MINSKY_REST_URL: string };
type Runtime = {
  state: string; message: string; progress: number; installer_available: boolean;
  managed_directory: string; managed_python: string | null; active_python: string;
  backend_kind: string; restart_required: boolean; commands_directory: string; paths: Partial<Paths>;
};
const emptyPaths: Paths = { OCTAVE_EXECUTABLE: "", DYNARE_MATLAB_PATH: "", MINSKY_REST_URL: "" };

async function request<T>(path = "", init?: RequestInit): Promise<T> {
  const response = await apiFetch(`/runtime/engines${path}`, init);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Não foi possível configurar os motores.");
  return data;
}

export function EngineSettings() {
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [paths, setPaths] = useState<Paths>(emptyPaths);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [log, setLog] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true, first = true;
    async function refresh() {
      try {
        const value = await request<Runtime>();
        if (!alive) return;
        setRuntime(value);
        if (first) { setPaths({ ...emptyPaths, ...value.paths }); first = false; }
      } catch (e) { if (alive) setError(e instanceof Error ? e.message : "Falha ao consultar o ambiente."); }
    }
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => { alive = false; window.clearInterval(timer); };
  }, []);
  async function install() {
    setBusy(true); setError(""); setMessage(""); setLog(null);
    try { setRuntime(await request<Runtime>("/install", { method: "POST" })); }
    catch (e) { setError(e instanceof Error ? e.message : "Falha na instalação."); }
    finally { setBusy(false); }
  }
  async function save() {
    setBusy(true); setError(""); setMessage("");
    try {
      setPaths(await request<Paths>("/paths", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(paths) }));
      setMessage("Caminhos salvos. Reabra o aplicativo para atualizar todos os indicadores dos módulos.");
    } catch (e) { setError(e instanceof Error ? e.message : "Falha ao salvar caminhos."); }
    finally { setBusy(false); }
  }
  return <section className="settingsSection engineSettings"><h3>Motores</h3>
    <p>Simple Macro e Economy Zero no preset Basic funcionam com o instalador base. Mesa e HARK usam um Python próprio, separado do Python do Windows.</p>
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
      <button type="button" className="secondaryButton" onClick={async () => { try { setLog((await request<{ log: string }>("/log")).log); } catch (e) { setError(String(e)); } }}>Ver diagnóstico da instalação</button>
      {log !== null && <pre className="runtimeLog">{log}</pre>}
    </>}
    <h4>Dynare e Minsky</h4><p>Instale esses programas separadamente e informe os caminhos. Deixe em branco para usar a descoberta padrão.</p>
    {([["OCTAVE_EXECUTABLE", "Executável do Octave", "C:\\Program Files\\GNU Octave\\octave-cli.exe"], ["DYNARE_MATLAB_PATH", "Pasta matlab do Dynare", "C:\\dynare\\matlab"], ["MINSKY_REST_URL", "Endereço REST do Minsky", "http://127.0.0.1:8000"]] as const).map(([key, label, placeholder]) => <label className="settingsField" key={key}><span>{label}</span><input value={paths[key]} placeholder={placeholder} onChange={e => setPaths({ ...paths, [key]: e.target.value })} /></label>)}
    <button type="button" className="secondaryButton" disabled={busy || !runtime} onClick={() => void save()}>Salvar caminhos dos motores</button>
    {message && <p role="status">{message}</p>}
  </section>;
}
