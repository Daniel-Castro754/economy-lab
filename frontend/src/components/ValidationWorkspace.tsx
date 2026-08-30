import { useState } from "react";
import type { ExternalValidationReport, HubModuleInfo } from "../api";
import { validateExternalEngines } from "../api";

function statusLabel(status: "pass" | "fail" | "unavailable") {
  if (status === "pass") return "PASS";
  if (status === "fail") return "FAIL";
  return "UNAVAILABLE";
}

export function ValidationWorkspace({ module, onOpenSimulation }: { module: HubModuleInfo; onOpenSimulation: () => void }) {
  const [report, setReport] = useState<ExternalValidationReport | null>(null);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("Execute a qualificação para testar os runtimes externos desta instalação.");

  async function run() {
    setRunning(true);
    setMessage("Executando detecção, smoke tests e integração real…");
    try {
      const next = await validateExternalEngines({ smoke_tests: true, integration_tests: true });
      setReport(next);
      setMessage(next.qualification_ready
        ? "Instalação qualificada para os motores solicitados."
        : next.status === "failed"
          ? "Há falha de integração em pelo menos um motor."
          : "Qualificação parcial: há motor ausente ou nível de evidência insuficiente.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Falha ao qualificar motores externos");
    } finally {
      setRunning(false);
    }
  }

  function download() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `external-engine-qualification-${report.report_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return <section className="moduleWorkspace panel">
    <div className="moduleHero">
      <div><span className="eyebrow">BACKEND QUALIFICATION · RUNTIME REAL</span><h2>{module.title}</h2><p>{module.description}</p></div>
      <span className="moduleStatus available">Disponível · builtin</span>
    </div>
    <div className="moduleActions">
      <button type="button" onClick={run} disabled={running}>{running ? "Qualificando…" : "Qualificar Mesa + HARK + Dynare + Minsky"}</button>
      <button type="button" className="secondaryButton" onClick={download} disabled={!report}>Baixar evidência JSON</button>
      <button type="button" className="secondaryButton" onClick={onOpenSimulation}>Abrir Simulation Lab</button>
    </div>
    <p className="muted">{message}</p>
    {report && <>
      <div className="metricGrid">
        <article><span>Status</span><strong>{report.status.toUpperCase()}</strong></article>
        <article><span>Qualificado</span><strong>{report.qualification_ready ? "SIM" : "NÃO"}</strong></article>
        <article><span>Runtime verificado</span><strong>{report.runtime_verified}</strong></article>
        <article><span>Somente leitura</span><strong>{report.read_only_verified}</strong></article>
      </div>
      <p className="muted">{report.platform} · Python {report.python_version} · Economy Lab {report.economy_lab_version}</p>
      <p className="muted">Report ID {report.report_id} · SHA-256 {report.report_digest.slice(0, 16)}…</p>
      <div className="tableWrap"><table><thead><tr><th>Motor</th><th>Status</th><th>Qualificação</th><th>Versão</th><th>Compat.</th><th>Tempo</th></tr></thead><tbody>
        {report.checks.map(check => <tr key={check.engine}>
          <td>{check.engine.toUpperCase()}</td><td>{statusLabel(check.status)}</td><td>{check.qualification_level}</td><td>{check.version ?? "—"}</td><td>{check.compatibility}</td><td>{check.duration_ms.toFixed(0)} ms</td>
        </tr>)}
      </tbody></table></div>
      {report.checks.map(check => <details key={`${check.engine}-stages`}><summary>{check.engine.toUpperCase()} · evidências por etapa</summary>
        <div className="tableWrap"><table><thead><tr><th>Etapa</th><th>Status</th><th>Tempo</th><th>Evidência</th></tr></thead><tbody>{check.stages.map(stage => <tr key={`${check.engine}-${stage.name}`}><td>{stage.name}</td><td>{stage.status.toUpperCase()}</td><td>{stage.duration_ms.toFixed(0)} ms</td><td>{stage.summary}{stage.error ? ` · ${stage.error}` : ""}</td></tr>)}</tbody></table></div>
      </details>)}
      <p className="warning">Minsky permanece somente leitura nesta etapa. A reconciliação controlada de um .mky será fechada no bloco SFC/Minsky posterior.</p>
    </>}
  </section>;
}
