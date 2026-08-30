import type { HubModuleInfo } from "../api";

const capabilityLabels: Record<string, string> = {
  "single-simulation": "Simulação individual",
  "batch-experiments": "Experimentos em lote",
  "scenario-shocks": "Choques econômicos",
  charts: "Gráficos",
  "csv-export": "Exportação CSV",
  "xlsx-export": "Exportação Excel",
  "project-history": "Histórico de projetos",
  dsge: "DSGE",
  irf: "Funções impulso-resposta",
  "monetary-policy": "Política monetária",
  "macro-recalibration": "Re-solução macro",
  "hybrid-coupling": "Acoplamento híbrido",
  godley: "Tabelas Godley",
  sfc: "Stock-Flow Consistent",
  "rest-bridge": "Ponte REST",
  "model-sync": "Sincronização de modelo",
  "financial-dynamics": "Dinâmica financeira",
  "agent-activation": "Ativação de agentes",
  agentsets: "AgentSet",
  abm: "Agent-Based Modeling",
  "reproducible-randomness": "Aleatoriedade reproduzível",
  "household-optimization": "Otimização das famílias",
  "consumption-saving": "Consumo e poupança",
  "heterogeneous-agents": "Agentes heterogêneos",
  aggregation: "Agregação",
  comparison: "Comparação",
  duckdb: "DuckDB",
  statistics: "Estatística",
  "natural-language-scenarios": "Cenários em linguagem natural",
  validation: "Validação",
  "review-before-apply": "Revisão antes de aplicar",
  "external-validation": "Validação de motores externos",
  "runtime-smoke-tests": "Smoke tests reais",
  "version-report": "Relatório de versões",
  "compatibility-report": "Relatório de compatibilidade",
  "public-data": "Dados públicos",
  "bcb-sgs": "Banco Central / SGS",
  "ibge-sidra": "IBGE / SIDRA",
  "world-bank": "World Bank",
  ipeadata: "Ipeadata",
  "calibration-targets": "Metas de calibração",
  "calibration-report": "Relatório de calibração"
};

export function ModuleWorkspace({
  module,
  onOpenSimulation,
  onActivate
}: {
  module: HubModuleInfo;
  onOpenSimulation: () => void;
  onActivate?: () => void;
}) {
  return (
    <section className="moduleWorkspace panel">
      <div className="moduleHero">
        <div>
          <span className="eyebrow">MÓDULO · {module.kind.toUpperCase()}</span>
          <h2>{module.title}</h2>
          <p>{module.description}</p>
        </div>
        <span className={module.available ? "moduleStatus available" : "moduleStatus missing"}>
          {module.available ? "Disponível" : "Indisponível"} · {module.status}
        </span>
      </div>

      <div className="moduleColumns">
        <div>
          <h3>Capacidades</h3>
          <div className="capabilityGrid">
            {module.capabilities.map((capability) => (
              <span key={capability}>{capabilityLabels[capability] ?? capability}</span>
            ))}
          </div>
        </div>
        <div>
          <h3>Dependências</h3>
          {module.dependencies.length ? (
            <ul>{module.dependencies.map((dependency) => <li key={dependency}>{dependency}</li>)}</ul>
          ) : <p className="muted">Nenhuma dependência externa obrigatória.</p>}
          {module.routes.length > 0 && <>
            <h3>Contratos do Hub</h3>
            <code className="routeList">{module.routes.join("\n")}</code>
          </>}
        </div>
      </div>

      <div className="moduleActions">
        {onActivate && <button type="button" onClick={onActivate} disabled={!module.available}>Usar este módulo no cenário</button>}
        <button type="button" className="secondaryButton" onClick={onOpenSimulation}>Abrir Simulation Lab</button>
      </div>
      {!module.available && <p className="warning">O módulo permanece visível no Hub mesmo quando a dependência externa não está instalada. Isso permite configurar o projeto sem acoplamento silencioso.</p>}
    </section>
  );
}
