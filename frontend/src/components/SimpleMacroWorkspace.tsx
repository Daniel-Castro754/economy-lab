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

function pct(value: number) { return `${value.toFixed(1)}%`; }

function ApprovalGauge({ value }: { value: number }) {
  return <div className="approvalGauge"><div className="approvalFill" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /><strong>{value.toFixed(0)}</strong></div>;
}

function MiniTrend({ years }: { years: SimpleYearResult[] }) {
  if (!years.length) return null;
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

  useEffect(() => { listSimpleScenarios().then(setScenarios).catch(() => setScenarios([])); }, []);
  useEffect(() => { void reset("baseline"); }, []);

  async function reset(scenarioId: "baseline" | "global_recession" | "volatile") {
    onStatus("Preparando simulação simples…");
    try {
      const started = await startSimple({ ...defaultConfig, scenario_id: scenarioId });
      setConfig(started.config); setState(started.state); setInitialState(started.state); setNextExternal(started.next_external); setYears([]); setWarning(started.warning);
      setDecision({ interest_rate: started.config.neutral_interest_rate, income_tax: started.config.baseline_income_tax, corporate_tax: started.config.baseline_corporate_tax, government_spending: started.config.baseline_government_spending });
      onStatus("Simulação simples pronta");
    } catch (e) { onStatus(e instanceof Error ? e.message : "Falha ao iniciar modo simples"); }
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

  return <section className="simpleMacroShell">
    <div className="simpleHero">
      <div><span className="eyebrow">Nível 1 · Simulação simples</span><h2>Política macro em 7 anos</h2><p>Quatro decisões por ano, ambiente externo e feedback imediato. Sem agentes, Godley ou motores externos.</p></div>
      <div className="levelSwitcher"><span className="levelActive">1 · Simples</span><span>2 · Economy Zero</span><span>3 · Hybrid</span></div>
    </div>

    <div className="simpleGrid">
      <div className="panel controls">
        <h3>Cenário externo</h3>
        <select value={config?.scenario_id ?? "baseline"} onChange={e => void reset(e.target.value as any)}>
          {scenarios.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
        </select>
        <p className="muted">{scenarioInfo?.description}</p>

        <div className="externalCard">
          <strong>{state?.year === 7 ? "Simulação concluída" : `Ano ${(state?.year ?? 0) + 1} de 7`}</strong>
          {nextExternal && <><span>{nextExternal.label}</span><div className="externalStats"><div><small>Crescimento mundial</small><b>{pct(nextExternal.world_growth)}</b></div><div><small>Confiança</small><b>{nextExternal.consumer_confidence.toFixed(0)}/100</b></div></div></>}
        </div>

        <h3>Suas decisões</h3>
        <label>Taxa de juros (%)<input className="numberInput" type="number" step="0.25" value={decision.interest_rate} onChange={e => setDecision({...decision, interest_rate:Number(e.target.value)})}/></label>
        <label>Imposto de renda (%)<input className="numberInput" type="number" step="1" value={decision.income_tax} onChange={e => setDecision({...decision, income_tax:Number(e.target.value)})}/></label>
        <label>Imposto corporativo (%)<input className="numberInput" type="number" step="1" value={decision.corporate_tax} onChange={e => setDecision({...decision, corporate_tax:Number(e.target.value)})}/></label>
        <label>Gasto público (% do PIB)<input className="numberInput" type="number" step="0.5" value={decision.government_spending} onChange={e => setDecision({...decision, government_spending:Number(e.target.value)})}/></label>
        <button type="button" onClick={runYear} disabled={!state || state.year >= 7}>{state?.year === 7 ? "7 anos concluídos" : `Simular ano ${(state?.year ?? 0)+1}`}</button>
        <button type="button" className="secondaryButton" onClick={() => void reset(config?.scenario_id ?? "baseline")}>Reiniciar</button>
      </div>

      <div className="panel simpleResults">
        <div className="projectTitle"><strong>Resultados</strong><span className="muted">{latest ? `Ano ${latest.year}` : "Condições iniciais"}</span></div>
        {state && <div className="simpleKpis">
          <div><small>Crescimento PIB</small><strong>{pct(state.real_gdp_growth)}</strong></div>
          <div><small>Inflação</small><strong>{pct(state.inflation)}</strong></div>
          <div><small>Desemprego</small><strong>{pct(state.unemployment)}</strong></div>
          <div><small>Déficit / PIB</small><strong>{pct(state.budget_deficit_to_gdp)}</strong></div>
          <div><small>Dívida / PIB</small><strong>{pct(state.debt_to_gdp)}</strong></div>
        </div>}
        {state && <div className="approvalBlock"><span>Aprovação</span><ApprovalGauge value={state.approval}/></div>}
        {latest && <div className="explainBox"><strong>O que aconteceu</strong>{latest.explanation.map((x,i)=><p key={i}>{x}</p>)}{latest.warnings.map((x,i)=><p className="warningText" key={`w${i}`}>{x}</p>)}</div>}
        <MiniTrend years={years}/>
        {years.length > 0 && <div className="projectActions"><button type="button" className="secondaryButton" onClick={() => void exportFile("csv")}>CSV</button><button type="button" className="secondaryButton" onClick={() => void exportFile("xlsx")}>Excel</button><button type="button" onClick={() => void promote()}>Analisar no Economy Zero</button></div>}
      </div>
    </div>

    {years.length > 0 && <div className="panel"><h3>Histórico</h3><div className="tableWrap"><table><thead><tr><th>Ano</th><th>PIB</th><th>Inflação</th><th>Desemprego</th><th>Déficit</th><th>Dívida</th><th>Aprovação</th></tr></thead><tbody>{years.map(y => <tr key={y.year}><td>{y.year}</td><td>{pct(y.state.real_gdp_growth)}</td><td>{pct(y.state.inflation)}</td><td>{pct(y.state.unemployment)}</td><td>{pct(y.state.budget_deficit_to_gdp)}</td><td>{pct(y.state.debt_to_gdp)}</td><td>{y.state.approval.toFixed(0)}</td></tr>)}</tbody></table></div></div>}
    <p className="muted simpleDisclaimer">{warning}</p>
  </section>;
}
