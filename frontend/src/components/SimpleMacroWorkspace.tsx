import { useEffect, useMemo, useState } from "react";
import {
  convertSimpleToAdvanced,
  exportSimpleFile,
  listSimpleScenarios,
  SimpleEconomyState,
  SimpleInitialConfig,
  SimplePolicyDecision,
  SimpleRunResult,
  SimpleScenarioInfo,
  SimpleYearResult,
  startSimple,
  stepSimple,
  ScenarioSpec,
} from "../api";

const defaultConfig: Partial<SimpleInitialConfig> = { scenario_id: "baseline" };
const defaultDecision: SimplePolicyDecision = { interest_rate: 4, income_tax: 20, corporate_tax: 22, government_spending: 22 };
const resultTabs = [
  ["visao", "Visão geral"], ["series", "Séries temporais"], ["setores", "Setores e agentes"],
  ["fiscal", "Fiscal"], ["monetario", "Monetário"], ["bancos", "Bancos"],
  ["sfc", "SFC/Godley"], ["comparacoes", "Comparações"], ["auditoria", "Auditoria"],
] as const;

const scenarioMeta: Record<string, { eyebrow: string; accent: string }> = {
  baseline: { eyebrow: "BASE", accent: "Estável" },
  global_recession: { eyebrow: "CHOQUE", accent: "Recessivo" },
  volatile: { eyebrow: "RISCO", accent: "Volátil" },
};

function pct(value: number) { return `${value.toFixed(1)}%`; }

function ApprovalGauge({ value }: { value: number }) {
  return <div className="approvalGauge"><div className="approvalFill" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /><strong>{value.toFixed(0)}</strong></div>;
}

function MiniTrend({ years }: { years: SimpleYearResult[] }) {
  if (!years.length) return <div className="chartEmptyState">
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 19V5M4 19h16"/><path d="m7 15 4-4 3 2 5-6"/></svg>
    <div><strong>Série temporal ainda não iniciada</strong><span>Escolha o cenário, ajuste as decisões e simule o primeiro ano.</span></div>
  </div>;
  const width = 760, height = 220, left = 48, right = 16, top = 18, bottom = 34;
  const metrics = [
    { key: "real_gdp_growth", label: "PIB", stroke: "#38bdf8" },
    { key: "inflation", label: "Inflação", stroke: "#f59e0b" },
    { key: "unemployment", label: "Desemprego", stroke: "#34d399" },
  ] as const;
  const values = years.flatMap(y => metrics.map(m => y.state[m.key]));
  let min = Math.min(...values, 0), max = Math.max(...values, 1);
  if (max - min < 1) { max += 1; min -= 1; }
  const x = (i: number) => left + (years.length === 1 ? 0 : i / (years.length - 1) * (width-left-right));
  const y = (v: number) => top + (max-v)/(max-min)*(height-top-bottom);
  return <div className="chartCard"><div className="chartHeader"><strong>Trajetória macro</strong><div className="chartLegend">{metrics.map(m => <span key={m.key}><i style={{background:m.stroke}} />{m.label}</span>)}</div></div>
    <svg className="chartSvg" viewBox={`0 0 ${width} ${height}`}>
      {[0,1,2,3,4].map(i => { const yy=top+i/4*(height-top-bottom); const val=max-i/4*(max-min); return <g key={i}><line x1={left} x2={width-right} y1={yy} y2={yy} className="gridLine"/><text x={left-8} y={yy+4} textAnchor="end" className="axisText">{val.toFixed(1)}</text></g> })}
      {metrics.map(m => <polyline key={m.key} fill="none" stroke={m.stroke} strokeWidth="2.5" points={years.map((r,i)=>`${x(i)},${y(r.state[m.key])}`).join(" ")} />)}
      {years.map((r,i)=><text key={r.year} x={x(i)} y={height-10} textAnchor="middle" className="axisText">Ano {r.year}</text>)}
    </svg></div>;
}

export function SimpleMacroWorkspace({ onApplyAdvanced, onStatus }: { onApplyAdvanced: (scenario: ScenarioSpec) => void; onStatus: (message: string) => void }) {
  const [scenarios, setScenarios] = useState<SimpleScenarioInfo[]>([]);
  const [config, setConfig] = useState<SimpleInitialConfig | null>(null);
  const [state, setState] = useState<SimpleEconomyState | null>(null);
  const [initialState, setInitialState] = useState<SimpleEconomyState | null>(null);
  const [nextExternal, setNextExternal] = useState<SimpleScenarioInfo["years"][number] | null>(null);
  const [decision, setDecision] = useState<SimplePolicyDecision>(defaultDecision);
  const [years, setYears] = useState<SimpleYearResult[]>([]);
  const [warning, setWarning] = useState("");
  const [scenarioError, setScenarioError] = useState("");
  const [resultTab, setResultTab] = useState<(typeof resultTabs)[number][0]>("visao");

  async function loadScenarios() {
    setScenarioError("");
    try {
      const items = await listSimpleScenarios();
      setScenarios(items);
      if (!items.length) setScenarioError("O backend não retornou cenários externos.");
    } catch (error) {
      setScenarios([]);
      setScenarioError(error instanceof Error ? error.message : "Falha ao carregar cenários externos.");
    }
  }

  useEffect(() => { void loadScenarios(); }, []);
  useEffect(() => { void reset("baseline"); }, []);

  async function reset(scenarioId: "baseline" | "global_recession" | "volatile") {
    onStatus("Preparando simulação simples…");
    try {
      const started = await startSimple({ ...defaultConfig, scenario_id: scenarioId });
      setConfig(started.config); setState(started.state); setInitialState(started.state); setNextExternal(started.next_external); setYears([]); setWarning(started.warning);
      setDecision({ interest_rate: started.config.neutral_interest_rate, income_tax: started.config.baseline_income_tax, corporate_tax: started.config.baseline_corporate_tax, government_spending: started.config.baseline_government_spending });
      onStatus("Simulação simples pronta");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Falha ao iniciar modo simples";
      setScenarioError(message);
      onStatus(message);
    }
  }

  async function runYear() {
    if (!config || !state || state.year >= 7) return;
    onStatus(`Simulando ano ${state.year + 1}…`);
    try {
      const response = await stepSimple(config, state, decision);
      setState(response.result.state); setYears(current => [...current, response.result]); setNextExternal(response.next_external ?? null);
      onStatus(response.completed ? "Ciclo de 7 anos concluído" : `Ano ${response.result.year} concluído`);
    } catch (e) { onStatus(e instanceof Error ? e.message : "Falha no turno simples"); }
  }

  const runResult: SimpleRunResult | null = useMemo(() => config && state && initialState ? {
    model: "simple-macro-policy-v1", warning, config,
    initial_state: initialState,
    years, final_state: state, completed_years: years.length,
  } : null, [config, state, initialState, years, warning]);

  async function exportFile(format: "csv" | "xlsx") { if (runResult) await exportSimpleFile(format, runResult); }
  async function promote() {
    if (!config || !state) return;
    const converted = await convertSimpleToAdvanced(config, state, decision, 24);
    onApplyAdvanced(converted.scenario);
    onStatus(`Cenário transferido para Economy Zero. ${converted.limitations.length} limitações de conversão registradas.`);
  }

  const latest = years.at(-1);
  const scenarioInfo = scenarios.find(s => s.id === config?.scenario_id);
  const hasMacroDetail = resultTab === "visao" || resultTab === "series";
  const unavailableHere = ["setores", "bancos", "sfc"].includes(resultTab);

  return <section className="simpleMacroShell">
    <div className="simpleGrid">
      <div className="panel controls">
        <div className="panelHeader"><div><small>POLÍTICA ECONÔMICA</small><strong>Decisões — ano {(state?.year ?? 0) + 1}</strong></div><span>Simple Macro</span></div>
        <div className="controlBody">
          <div className="fieldHeading"><span>Cenário externo</span><small>Condições globais para os 7 anos</small></div>
          <div className="scenarioPicker" role="radiogroup" aria-label="Cenário externo">
            {scenarios.map(s => <button type="button" role="radio" aria-checked={config?.scenario_id === s.id} key={s.id} className={config?.scenario_id === s.id ? "scenarioChoice active" : "scenarioChoice"} onClick={() => void reset(s.id as "baseline" | "global_recession" | "volatile")}>
              <span>{scenarioMeta[s.id]?.eyebrow ?? "CENÁRIO"}</span><strong>{s.title}</strong><small>{scenarioMeta[s.id]?.accent ?? "Externo"}</small>
            </button>)}
            {!scenarios.length && <div className="scenarioSkeleton">Carregando cenários externos…</div>}
          </div>
          {scenarioError && <div className="inlineError"><span>{scenarioError}</span><button type="button" className="secondaryButton" onClick={() => { void loadScenarios(); void reset(config?.scenario_id ?? "baseline"); }}>Tentar novamente</button></div>}
          <p className="muted compactHelp">{scenarioInfo?.description}</p>

          <div className="externalCard">
            <div className="externalCardHeader"><div><span>CONDIÇÕES EXTERNAS</span><strong>{nextExternal?.label ?? "Aguardando dados"}</strong></div><em>{state?.year === 7 ? "Concluído" : `Ano ${(state?.year ?? 0) + 1}/7`}</em></div>
            {nextExternal && <div className="externalStats"><div><small>Crescimento mundial</small><b>{pct(nextExternal.world_growth)}</b></div><div><small>Confiança do consumidor</small><b>{nextExternal.consumer_confidence.toFixed(0)}<i>/100</i></b></div></div>}
          </div>

          <div className="policyGroup"><div className="policyGroupTitle"><span>MONETÁRIA</span><small>Banco Central</small></div><div className="simpleDecisionGrid oneColumn">
            <label>Taxa de juros<input className="numberInput" type="number" step="0.25" value={decision.interest_rate} onChange={e => setDecision({...decision, interest_rate:Number(e.target.value)})}/><small>% a.a.</small></label>
          </div></div>
          <div className="policyGroup"><div className="policyGroupTitle"><span>FISCAL</span><small>Governo</small></div><div className="simpleDecisionGrid">
            <label>Imposto de renda<input className="numberInput" type="number" step="1" value={decision.income_tax} onChange={e => setDecision({...decision, income_tax:Number(e.target.value)})}/><small>% renda</small></label>
            <label>Imposto corporativo<input className="numberInput" type="number" step="1" value={decision.corporate_tax} onChange={e => setDecision({...decision, corporate_tax:Number(e.target.value)})}/><small>% lucro</small></label>
            <label className="wideField">Gasto público<input className="numberInput" type="number" step="0.5" value={decision.government_spending} onChange={e => setDecision({...decision, government_spending:Number(e.target.value)})}/><small>% do PIB</small></label>
          </div></div>
          <div className="simpleActions stickyActions"><button type="button" className="runSimulationButton" onClick={runYear} disabled={!state || state.year >= 7}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m9 6 9 6-9 6z"/></svg>{state?.year === 7 ? "7 anos concluídos" : `Simular ano ${(state?.year ?? 0)+1}`}</button><button type="button" className="secondaryButton" onClick={() => void reset(config?.scenario_id ?? "baseline")} title="Reiniciar simulação" aria-label="Reiniciar simulação"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/></svg></button></div>
          <small className="muted">Execução local, determinística e registrada no histórico da sessão.</small>
        </div>
      </div>

      <div className="panel simpleResults">
        <div className="simpleResultTabs">{resultTabs.map(([id,label]) => <button type="button" key={id} className={resultTab === id ? "active" : ""} onClick={() => setResultTab(id)}>{label}</button>)}</div>
        <div className="resultBody">
          <div className="projectTitle resultTitle"><div><span>RESULTADOS ANALÍTICOS</span><strong>{resultTabs.find(([id]) => id === resultTab)?.[1]}</strong></div><span className="resultPeriod">{latest ? `Ano ${latest.year} de 7` : "Condições iniciais"}</span></div>
          {state && !unavailableHere && <div className="simpleKpis">
            {(resultTab === "fiscal" || resultTab === "visao" || resultTab === "series") && <><div><small>Crescimento PIB</small><strong>{pct(state.real_gdp_growth)}</strong></div><div><small>Déficit / PIB</small><strong>{pct(state.budget_deficit_to_gdp)}</strong></div><div><small>Dívida / PIB</small><strong>{pct(state.debt_to_gdp)}</strong></div></>}
            {(resultTab === "monetario" || resultTab === "visao" || resultTab === "series") && <div><small>Inflação</small><strong>{pct(state.inflation)}</strong></div>}
            {(resultTab === "visao" || resultTab === "series") && <div><small>Desemprego</small><strong>{pct(state.unemployment)}</strong></div>}
          </div>}
          {unavailableHere && <div className="levelNotice"><strong>Detalhamento disponível no Economy Zero e Hybrid/Advanced</strong><p>O Simple Macro não simula agentes, bancos ou matrizes SFC. Promova o cenário para acessar esses resultados sem inventar dados nesta tela.</p><button type="button" onClick={() => void promote()}>Enviar ao Economy Zero</button></div>}
          {resultTab === "comparacoes" && <div className="levelNotice"><strong>Compare após gerar mais de uma execução</strong><p>Use o histórico local e os experimentos em lote no Economy Zero para comparar seeds e parâmetros.</p></div>}
          {resultTab === "auditoria" && <div className="auditSummary"><span className="ledgerState ok">✓ Simple Macro consistente</span><p>{warning}</p><p className="muted">Sem Ledger/Godley neste nível. A auditoria SFC completa é aplicada nos níveis 2 e 3.</p></div>}
          {hasMacroDetail && <>
            {state && <div className="approvalBlock"><span>Aprovação</span><ApprovalGauge value={state.approval}/></div>}
            <MiniTrend years={years}/>
            {latest && resultTab === "visao" && <div className="resultNarrative"><div className="explainBox"><strong>Leitura do resultado</strong>{latest.explanation.map((x,i)=><p key={i}>{x}</p>)}</div><div className="simpleAlerts"><strong>Alertas econômicos</strong>{latest.warnings.length ? latest.warnings.map((x,i)=><p className="warning" key={`w${i}`}>{x}</p>) : <p className="muted">Nenhum alerta crítico neste ano.</p>}</div></div>}
          </>}
          {years.length > 0 && ["visao","series","fiscal","monetario"].includes(resultTab) && <div className="tableWrap simpleHistory"><table><thead><tr><th>Ano</th><th>PIB</th><th>Inflação</th><th>Desemprego</th><th>Déficit</th><th>Dívida</th><th>Aprovação</th></tr></thead><tbody>{years.map(y => <tr key={y.year}><td>{y.year}</td><td>{pct(y.state.real_gdp_growth)}</td><td>{pct(y.state.inflation)}</td><td>{pct(y.state.unemployment)}</td><td>{pct(y.state.budget_deficit_to_gdp)}</td><td>{pct(y.state.debt_to_gdp)}</td><td>{y.state.approval.toFixed(0)}</td></tr>)}</tbody></table></div>}
          {years.length > 0 && <div className="projectActions simpleExportActions"><button type="button" className="secondaryButton" onClick={() => void exportFile("csv")}>Exportar CSV</button><button type="button" className="secondaryButton" onClick={() => void exportFile("xlsx")}>Exportar Excel</button><button type="button" onClick={() => void promote()}>Enviar cenário ao Economy Zero</button></div>}
        </div>
      </div>
    </div>
    <p className="muted simpleDisclaimer">{warning}</p>
  </section>;
}
