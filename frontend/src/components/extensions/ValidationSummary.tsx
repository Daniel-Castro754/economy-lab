import type { ExternalEngineCheck } from "../../engineApi";

function badgeClass(check: ExternalEngineCheck): string {
  if (check.status === "fail") return "missing";
  if (check.compatibility === "warning") return "offline";
  if (check.qualification_level === "runtime-verified" || check.qualification_level === "read-only-verified") return "ready";
  return "optional";
}

const QUALIFICATION_LABEL: Record<ExternalEngineCheck["qualification_level"], string> = {
  none: "Não detectado",
  detected: "Detectado",
  "read-only-verified": "Verificado (leitura)",
  "runtime-verified": "Verificado em execução",
};

export function ValidationSummary({ check }: { check?: ExternalEngineCheck }) {
  if (!check) return <p className="muted validationHint">Ainda não validado. Use “Validar instalação” para conferir.</p>;

  return <div className="validationSummary">
    <div className="validationBadges">
      <span className={`statusBadge ${badgeClass(check)}`}>{QUALIFICATION_LABEL[check.qualification_level]}</span>
      {check.target_version && <span className="muted">alvo {check.target_version}{check.version ? ` · detectado ${check.version}` : ""}</span>}
    </div>
    <p className="muted">{check.summary}</p>
    {check.stages.length > 0 && <details>
      <summary>Etapas da validação ({check.stages.length})</summary>
      <ul className="validationStages">
        {check.stages.map(stage => <li key={stage.name}><strong className={stage.status === "fail" ? "bad" : stage.status === "pass" ? "ok" : undefined}>{stage.name}</strong><span>{stage.summary}</span></li>)}
      </ul>
    </details>}
  </div>;
}
