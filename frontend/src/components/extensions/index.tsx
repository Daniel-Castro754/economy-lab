import { useEffect, useState } from "react";
import { validateExternalEngines } from "../../engineApi";
import type { ExternalValidationReport } from "../../engineApi";
import { requestRuntimeEngines, emptyEnginePaths } from "./runtimeEnginesApi";
import type { EnginePaths, RuntimeEngines } from "./runtimeEnginesApi";
import { ManagedPythonCard } from "./ManagedPythonCard";
import { DynareCard } from "./DynareCard";
import { MinskyCard } from "./MinskyCard";

export function ExtensionsPanel() {
  const [paths, setPaths] = useState<EnginePaths>(emptyEnginePaths);
  const [report, setReport] = useState<ExternalValidationReport | null>(null);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    let alive = true;
    void requestRuntimeEngines<RuntimeEngines>().then(value => {
      if (alive) setPaths({ ...emptyEnginePaths, ...value.paths });
    }).catch(() => { /* ManagedPythonCard surfaces this error already */ });
    return () => { alive = false; };
  }, []);

  async function validate() {
    setValidating(true); setValidationError("");
    try { setReport(await validateExternalEngines({})); }
    catch (e) { setValidationError(e instanceof Error ? e.message : "Falha ao validar motores."); }
    finally { setValidating(false); }
  }

  return <section className="settingsSection extensionsPanel">
    <h3>Extensões</h3>
    <p>Motores externos que o Economy Lab pode usar. Mesa e HARK têm instalação automática; Dynare/Octave e Minsky são instalados separadamente.</p>

    <ManagedPythonCard checks={report?.checks} />
    <DynareCard paths={paths} onPathsSaved={setPaths} check={report?.checks.find(check => check.engine === "dynare")} />
    <MinskyCard paths={paths} onPathsSaved={setPaths} check={report?.checks.find(check => check.engine === "minsky")} />

    <div className="extensionValidationTrigger">
      <button type="button" className="secondaryButton" disabled={validating} onClick={() => void validate()}>{validating ? "Validando (pode levar ~1 minuto)…" : "Validar instalação"}</button>
      {validationError && <p className="bad" role="alert">{validationError}</p>}
      {report && <p className="muted">Última validação: {report.passed} ok · {report.failed} falhas · {report.unavailable} indisponíveis</p>}
    </div>
  </section>;
}
