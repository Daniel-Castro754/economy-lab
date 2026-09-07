import { useMemo, useState } from "react";
import {
  DynareLabRequest, DynareLabResponse, HarkLabRequest, HarkLabResponse, HubModuleInfo,
  MesaLabRequest, MesaLabResponse, MesaComponentRequest, MesaComponentResponse, MinskyFinancialCaptureRequest, MinskyFinancialCaptureResponse, getDynareTemplate, runDynareLab, runHarkLab, runMesaLab, runMesaComponentLab, runMinskyCommand, runMinskyFinancialController
} from "../api";

type SaveProfilePayload = {
  module_id: "dynare" | "minsky" | "mesa" | "hark";
  name: string;
  inputs: Record<string, unknown>;
  outputs?: Record<string, unknown> | null;
  apply?: boolean;
};

type LabProps = {
  module: HubModuleInfo;
  selectedTool: string;
  onOpenSimulation: () => void;
  onSaveProfile: (payload: SaveProfilePayload) => Promise<void>;
};

function LabHeader({ module, onOpenSimulation }: { module: HubModuleInfo; onOpenSimulation: () => void }) {
  return <>
    <div className="moduleHero">
      <div><span className="eyebrow">LABORATÓRIO · {module.kind.toUpperCase()}</span><h2>{module.title}</h2><p>{module.description}</p></div>
      <span className={module.available ? "moduleStatus available" : "moduleStatus missing"}>{module.available ? "Disponível" : "Indisponível"} · {module.status}</span>
    </div>
    <div className="moduleActions"><button type="button" className="secondaryButton" onClick={onOpenSimulation}>Abrir Simulation Lab</button></div>
  </>;
}

function ProfileActions({ profileName, setProfileName, onSave, compatibility }: { profileName: string; setProfileName: (value: string) => void; onSave: (apply: boolean) => void; compatibility?: string }) {
  return <div className="profileComposer">
    <label>Nome do Profile<input value={profileName} maxLength={120} onChange={e => setProfileName(e.target.value)} /></label>
    <div className="moduleActions">
      <button type="button" className="secondaryButton" onClick={() => onSave(false)}>Salvar Profile</button>
      <button type="button" onClick={() => onSave(true)}>Salvar e enviar ao Simulation Lab</button>
    </div>
    {compatibility && <p className="muted">Integração no simulador: {compatibility}</p>}
  </div>;
}

function SimpleLines({ rows, xKey, series }: { rows: Record<string, number>[]; xKey: string; series: Array<{ key: string; label: string }> }) {
  const width = 760, height = 260, pad = 34;
  const values = rows.flatMap(row => series.map(item => Number(row[item.key] ?? 0)));
  const minY = Math.min(0, ...values), maxY = Math.max(1e-9, ...values);
  const x = (index: number) => pad + (rows.length <= 1 ? 0 : index * (width - pad * 2) / (rows.length - 1));
  const y = (value: number) => height - pad - (value - minY) * (height - pad * 2) / Math.max(1e-9, maxY - minY);
  return <div className="chartCard"><div className="chartLegend">{series.map((s, i) => <span key={s.key}><b>{i + 1}</b>{s.label}</span>)}</div>
    <svg viewBox={`0 0 ${width} ${height}`} className="chartSvg" role="img">
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} className="axisLine" />
      <line x1={pad} y1={pad} x2={pad} y2={height - pad} className="axisLine" />
      {series.map((item, i) => <polyline key={item.key} points={rows.map((row, index) => `${x(index)},${y(Number(row[item.key] ?? 0))}`).join(" ")} fill="none" className={`labSeries labSeries${i + 1}`} strokeWidth="2.5" />)}
      {rows.length > 0 && <text x={pad} y={height - 8} className="axisText">{String(rows[0][xKey])}</text>}
      {rows.length > 1 && <text x={width - pad} y={height - 8} textAnchor="end" className="axisText">{String(rows[rows.length - 1][xKey])}</text>}
    </svg>
  </div>;
}

function downloadCsv(filename: string, rows: Array<Record<string, string | number>>) {
  if (rows.length === 0) return;
  const columns = Object.keys(rows[0]);
  const escape = (value: string | number) => { const text = String(value); return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text; };
  const csv = [columns.join(","), ...rows.map(row => columns.map(column => escape(row[column] ?? "")).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" }); const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function DynareLab({ module, selectedTool, onOpenSimulation, onSaveProfile }: LabProps) {
  const [params, setParams] = useState<DynareLabRequest>({ irf_periods: 24, monetary_shock_bp: 100, neutral_nominal_rate: 8, beta: .99, sigma: 1, kappa: .10, rho_i: .80, phi_pi: 1.5, phi_x: .25, timeout_seconds: 120 });
  const [result, setResult] = useState<DynareLabResponse | null>(null); const [source, setSource] = useState(""); const [message, setMessage] = useState(""); const [profileName, setProfileName] = useState("Macro NK");
  const set = (key: keyof DynareLabRequest, value: number) => setParams(p => ({ ...p, [key]: value }));
  async function template() { try { setSource(await getDynareTemplate(params)); setMessage("Template gerado localmente; nada foi executado."); } catch (e) { setMessage(e instanceof Error ? e.message : "Falha"); } }
  async function run() { try { setMessage("Executando Dynare/Octave…"); setResult(await runDynareLab(params)); setMessage("IRF concluída"); } catch (e) { setMessage(e instanceof Error ? e.message : "Falha"); } }
  const save = (apply: boolean) => onSaveProfile({ module_id: "dynare", name: profileName || "Macro NK", inputs: params as unknown as Record<string, unknown>, outputs: asRecord(result), apply });
  const rows = useMemo(() => (result?.irf ?? []).map(p => ({ period: p.period, produto: p.output_gap, inflacao: p.inflation_gap, juros: p.policy_rate_gap })), [result]);
  return <section className="moduleWorkspace panel"><LabHeader module={module} onOpenSimulation={onOpenSimulation} />
    <div className="labGrid"><div className="labControls"><h3>Modelo Novo-Keynesiano</h3>
      <label>Choque monetário (bp)<input type="number" value={params.monetary_shock_bp} onChange={e => set("monetary_shock_bp", +e.target.value)} /></label>
      <label>Horizonte IRF<input type="number" value={params.irf_periods} onChange={e => set("irf_periods", +e.target.value)} /></label>
      <label>Taxa neutra nominal (%)<input type="number" step="0.25" value={params.neutral_nominal_rate} onChange={e => set("neutral_nominal_rate", +e.target.value)} /></label>
      <label>β<input type="number" step="0.005" value={params.beta} onChange={e => set("beta", +e.target.value)} /></label>
      <label>σ<input type="number" step="0.05" value={params.sigma} onChange={e => set("sigma", +e.target.value)} /></label>
      <label>κ<input type="number" step="0.01" value={params.kappa} onChange={e => set("kappa", +e.target.value)} /></label>
      <label>φπ<input type="number" step="0.05" value={params.phi_pi} onChange={e => set("phi_pi", +e.target.value)} /></label>
      <label>φx<input type="number" step="0.05" value={params.phi_x} onChange={e => set("phi_x", +e.target.value)} /></label>
      <label>ρi<input type="number" step="0.05" value={params.rho_i} onChange={e => set("rho_i", +e.target.value)} /></label>
      <div className="moduleActions">{selectedTool === "dynare-template" && <button type="button" className="secondaryButton" onClick={template}>Gerar .mod</button>}{selectedTool === "dynare-irf" && <button type="button" onClick={run} disabled={!module.available}>Executar IRF</button>}</div>
      <ProfileActions profileName={profileName} setProfileName={setProfileName} onSave={save} compatibility="ativa: parâmetros estruturais + choque/IRF entram no cenário" />
      <p className="muted">{message}</p>
    </div><div className="labOutput"><h3>{selectedTool === "dynare-template" ? "Gerador de modelo .mod" : "Resposta impulso-resposta"}</h3>
      {selectedTool === "dynare-irf" && (result ? <><div className="cards"><article><span>Choque</span><strong>{result.shock_size_pp.toFixed(2)} p.p.</strong></article><article><span>Períodos</span><strong>{result.irf.length}</strong></article><article><span>Motor</span><strong>{result.engine}</strong></article></div><SimpleLines rows={rows} xKey="period" series={[{ key: "produto", label: "Hiato produto" }, { key: "inflacao", label: "Inflação" }, { key: "juros", label: "Juros" }]} /><button type="button" className="secondaryButton" onClick={() => downloadCsv("dynare-irf.csv", rows)}>Exportar IRF CSV</button></> : <p className="muted">Execute a IRF quando Dynare/Octave estiver disponível.</p>)}
      {selectedTool === "dynare-template" && (source ? <><pre className="codePreview">{source}</pre><button type="button" className="secondaryButton" onClick={() => { const blob = new Blob([source], {type: "text/plain"}); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href=url; a.download="economy_lab_nk.mod"; a.click(); URL.revokeObjectURL(url); }}>Baixar .mod</button></> : <p className="muted">Gere um template auditável mesmo sem Dynare instalado.</p>)}
    </div></div></section>;
}

function MesaLab({ module, onOpenSimulation, onSaveProfile }: LabProps) {
  const [mode, setMode] = useState<"wealth" | "component">("component");
  const [params, setParams] = useState<MesaLabRequest>({ agents: 100, steps: 200, initial_wealth: 10, transfer_amount: 1, seed: 42 });
  const [componentParams, setComponentParams] = useState<MesaComponentRequest>({
    component: "household_search", steps: 60, seed: 42, activation_pattern: "random",
    shopping_sample_size: 4, cheapest_choice_probability: 1, price_adjustment_strength: 1,
    hiring_strength: 1, layoff_strength: 1, matching_efficiency: 1
  });
  const [result, setResult] = useState<MesaLabResponse | null>(null);
  const [componentResult, setComponentResult] = useState<MesaComponentResponse | null>(null);
  const [message, setMessage] = useState("");
  const [profileName, setProfileName] = useState("Componente Mesa");

  async function run() {
    try {
      setMessage("Executando Mesa…");
      if (mode === "wealth") {
        setResult(await runMesaLab(params)); setComponentResult(null);
      } else {
        setComponentResult(await runMesaComponentLab(componentParams)); setResult(null);
      }
      setMessage("Concluído");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Falha"); }
  }
  const save = (apply: boolean) => onSaveProfile({
    module_id: "mesa", name: profileName || "Componente Mesa",
    inputs: (mode === "wealth" ? params : componentParams) as unknown as Record<string, unknown>,
    outputs: asRecord(mode === "wealth" ? result : componentResult), apply
  });
  const wealthRows = useMemo(() => (result?.path ?? []).map(p => ({ step: p.step, gini: p.gini, semRiqueza: p.zero_wealth_share })), [result]);
  const componentRows = useMemo(() => (componentResult?.path ?? []).map(row => ({ ...row } as Record<string, number>)), [componentResult]);
  const compatibility = mode === "wealth" ? "ativa: Mesa assume a ativação dos agentes" : "active-component: envia somente a mecânica selecionada ao Simulation Lab";

  return <section className="moduleWorkspace panel">
    <LabHeader module={module} onOpenSimulation={onOpenSimulation} />
    <div className="labGrid">
      <div className="labControls">
        <h3>Mesa Lab</h3>
        <label>Ferramenta
          <select value={mode} onChange={e => setMode(e.target.value as "wealth" | "component")}>
            <option value="component">Component Profiles</option><option value="wealth">Wealth Exchange demo</option>
          </select>
        </label>
        {mode === "wealth" && <>
          <label>Agentes<input type="number" value={params.agents} onChange={e => setParams(p => ({ ...p, agents: +e.target.value }))} /></label>
          <label>Passos<input type="number" value={params.steps} onChange={e => setParams(p => ({ ...p, steps: +e.target.value }))} /></label>
          <label>Riqueza inicial<input type="number" value={params.initial_wealth} onChange={e => setParams(p => ({ ...p, initial_wealth: +e.target.value }))} /></label>
          <label>Transferência<input type="number" value={params.transfer_amount} onChange={e => setParams(p => ({ ...p, transfer_amount: +e.target.value }))} /></label>
        </>}
        {mode === "component" && <>
          <label>Componente
            <select value={componentParams.component} onChange={e => setComponentParams(p => ({ ...p, component: e.target.value as MesaComponentRequest["component"] }))}>
              <option value="activation">Ativação</option><option value="household_search">Famílias · busca/preço</option><option value="firm_behavior">Empresas · preço/emprego</option><option value="labor_market">Mercado de trabalho</option>
            </select>
          </label>
          <label>Passos do preview<input type="number" value={componentParams.steps} onChange={e => setComponentParams(p => ({ ...p, steps: +e.target.value }))} /></label>
          {componentParams.component === "activation" && <label>Ativação
            <select value={componentParams.activation_pattern} onChange={e => setComponentParams(p => ({ ...p, activation_pattern: e.target.value as "random" | "fixed" }))}>
              <option value="random">Aleatória (shuffle_do)</option><option value="fixed">Fixa (do)</option>
            </select>
          </label>}
          {componentParams.component === "household_search" && <>
            <label>Amostra de lojas<input type="number" min="1" max="20" value={componentParams.shopping_sample_size} onChange={e => setComponentParams(p => ({ ...p, shopping_sample_size: +e.target.value }))} /></label>
            <label>Prob. escolher menor preço<input type="number" step="0.05" min="0" max="1" value={componentParams.cheapest_choice_probability} onChange={e => setComponentParams(p => ({ ...p, cheapest_choice_probability: +e.target.value }))} /></label>
          </>}
          {componentParams.component === "firm_behavior" && <>
            <label>Força ajuste de preço<input type="number" step="0.1" value={componentParams.price_adjustment_strength} onChange={e => setComponentParams(p => ({ ...p, price_adjustment_strength: +e.target.value }))} /></label>
            <label>Força contratação<input type="number" step="0.1" value={componentParams.hiring_strength} onChange={e => setComponentParams(p => ({ ...p, hiring_strength: +e.target.value }))} /></label>
            <label>Força demissão<input type="number" step="0.1" value={componentParams.layoff_strength} onChange={e => setComponentParams(p => ({ ...p, layoff_strength: +e.target.value }))} /></label>
          </>}
          {componentParams.component === "labor_market" && <label>Eficiência do matching<input type="number" min="0" max="1" step="0.05" value={componentParams.matching_efficiency} onChange={e => setComponentParams(p => ({ ...p, matching_efficiency: +e.target.value }))} /></label>}
        </>}
        <button type="button" onClick={run} disabled={!module.available}>Executar Mesa</button>
        <ProfileActions profileName={profileName} setProfileName={setProfileName} onSave={save} compatibility={compatibility} />
        <p className="muted">{message}</p>
      </div>
      <div className="labOutput">
        <h3>{mode === "wealth" ? "Distribuição emergente" : "Preview do componente"}</h3>
        {mode === "wealth" && (result ? <>
          <div className="cards"><article><span>Gini</span><strong>{result.gini.toFixed(3)}</strong></article><article><span>Sem riqueza</span><strong>{(result.zero_wealth_share * 100).toFixed(1)}%</strong></article><article><span>Riqueza máx.</span><strong>{result.max_wealth.toFixed(1)}</strong></article></div>
          <SimpleLines rows={wealthRows} xKey="step" series={[{ key: "gini", label: "Gini" }, { key: "semRiqueza", label: "Parcela sem riqueza" }]} />
          <button type="button" className="secondaryButton" onClick={() => downloadCsv("mesa-wealth-path.csv", wealthRows)}>Exportar CSV</button><p className="warning">{result.warning}</p>
        </> : <p className="muted">Execute o demo.</p>)}
        {mode === "component" && (componentResult ? <>
          <div className="cards">{Object.entries(componentResult.metrics).slice(0,4).map(([key,value]) => <article key={key}><span>{key}</span><strong>{String(value)}</strong></article>)}</div>
          <pre className="codePreview">{JSON.stringify(componentResult.scenario_patch, null, 2)}</pre>
          {componentRows.length > 0 && <button type="button" className="secondaryButton" onClick={() => downloadCsv("mesa-component-path.csv", componentRows)}>Exportar CSV</button>}
          <p className="warning">{componentResult.warning}</p>
        </> : <p className="muted">Escolha um componente para testar isoladamente e depois salvar/enviar como Profile.</p>)}
      </div>
    </div>
  </section>;
}


function HarkLab({ module, onOpenSimulation, onSaveProfile }: LabProps) {
  const [params, setParams] = useState<HarkLabRequest>({
    annual_interest_rate: .08, crra: 2, annual_discount_factor: .96,
    unemployment_probability: .05, unemployment_replacement_rate: .30,
    permanent_shock_std: .04, transitory_shock_std: .10, permanent_income_memory: .18,
    income_groups: 5, income_risk_dispersion: .35, max_market_resources: 12, points: 30
  });
  const [result, setResult] = useState<HarkLabResponse | null>(null);
  const [message, setMessage] = useState("");
  const [profileName, setProfileName] = useState("Famílias HARK stateful");
  async function run() { try { setMessage("Resolvendo políticas HARK por grupo de renda…"); setResult(await runHarkLab(params)); setMessage("Concluído"); } catch (e) { setMessage(e instanceof Error ? e.message : "Falha"); } }
  const save = (apply: boolean) => onSaveProfile({ module_id: "hark", name: profileName || "Famílias HARK stateful", inputs: params as unknown as Record<string, unknown>, outputs: asRecord(result), apply });
  const rows = useMemo(() => (result?.policy_curve ?? []).map(p => ({ recursos: p.market_resources, consumo: p.consumption, poupanca: p.saving })), [result]);
  return <section className="moduleWorkspace panel"><LabHeader module={module} onOpenSimulation={onOpenSimulation} /><div className="labGrid"><div className="labControls"><h3>Consumo, renda e risco</h3>
    <label>Juros anual (decimal)<input type="number" step="0.01" value={params.annual_interest_rate} onChange={e => setParams(p => ({ ...p, annual_interest_rate: +e.target.value }))} /></label>
    <label>CRRA<input type="number" step="0.1" value={params.crra} onChange={e => setParams(p => ({ ...p, crra: +e.target.value }))} /></label>
    <label>Fator de desconto anual<input type="number" step="0.01" value={params.annual_discount_factor} onChange={e => setParams(p => ({ ...p, annual_discount_factor: +e.target.value }))} /></label>
    <label>Prob. desemprego mensal<input type="number" step="0.01" min="0.001" max="0.5" value={params.unemployment_probability} onChange={e => setParams(p => ({ ...p, unemployment_probability: +e.target.value }))} /></label>
    <label>Reposição de renda no desemprego<input type="number" step="0.05" min="0" max="1" value={params.unemployment_replacement_rate} onChange={e => setParams(p => ({ ...p, unemployment_replacement_rate: +e.target.value }))} /></label>
    <label>Volatilidade renda permanente<input type="number" step="0.01" min="0" max="1" value={params.permanent_shock_std} onChange={e => setParams(p => ({ ...p, permanent_shock_std: +e.target.value }))} /></label>
    <label>Volatilidade renda transitória<input type="number" step="0.01" min="0" max="2" value={params.transitory_shock_std} onChange={e => setParams(p => ({ ...p, transitory_shock_std: +e.target.value }))} /></label>
    <label>Memória da renda permanente<input type="number" step="0.05" min="0.01" max="1" value={params.permanent_income_memory} onChange={e => setParams(p => ({ ...p, permanent_income_memory: +e.target.value }))} /></label>
    <label>Grupos de renda<input type="number" min="1" max="10" value={params.income_groups} onChange={e => setParams(p => ({ ...p, income_groups: +e.target.value }))} /></label>
    <label>Dispersão do risco por renda<input type="number" step="0.05" min="0" max="1" value={params.income_risk_dispersion} onChange={e => setParams(p => ({ ...p, income_risk_dispersion: +e.target.value }))} /></label>
    <label>Recursos normalizados máx.<input type="number" value={params.max_market_resources} onChange={e => setParams(p => ({ ...p, max_market_resources: +e.target.value }))} /></label>
    <button type="button" onClick={run} disabled={!module.available}>Resolver HARK</button>
    <ProfileActions profileName={profileName} setProfileName={setProfileName} onSave={save} compatibility="ativa: emprego, renda permanente/transitória, risco de desemprego e grupos de renda entram na decisão das famílias" /><p className="muted">{message}</p></div>
    <div className="labOutput"><h3>Função de política c(m)</h3>{result ? <><SimpleLines rows={rows} xKey="recursos" series={[{ key: "consumo", label: "Consumo" }, { key: "poupanca", label: "Poupança" }]} />
      <div className="tableWrap"><table><thead><tr><th>Grupo</th><th>Risco desemprego</th><th>Consumo c(m=mediano)</th></tr></thead><tbody>{result.group_profiles.map(group => { const point = group.policy_curve[Math.floor(group.policy_curve.length / 2)]; return <tr key={group.income_group}><td>Grupo {group.income_group}</td><td>{(group.unemployment_probability * 100).toFixed(2)}%</td><td>{point?.consumption.toFixed(3) ?? "—"}</td></tr>; })}</tbody></table></div>
      <div className="tableWrap"><table><thead><tr><th>Recursos</th><th>Consumo</th><th>Poupança</th></tr></thead><tbody>{result.policy_curve.slice(0, 12).map(p => <tr key={p.market_resources}><td>{p.market_resources.toFixed(2)}</td><td>{p.consumption.toFixed(3)}</td><td>{p.saving.toFixed(3)}</td></tr>)}</tbody></table></div>
      <button type="button" className="secondaryButton" onClick={() => downloadCsv("hark-policy-curve.csv", rows)}>Exportar CSV</button><p className="warning">{result.warning}</p></> : <p className="muted">HARK resolve decisões; o Simulation Lab sincroniza emprego/renda, mas os pagamentos continuam no ledger.</p>}</div></div></section>;
}

function MinskyLab({ module, selectedTool, onOpenSimulation, onSaveProfile }: LabProps) {
  const [path, setPath] = useState("/minsky");
  const [variable, setVariable] = useState(":policy_rate");
  const [value, setValue] = useState(0);
  const [output, setOutput] = useState<unknown>(null);
  const [financial, setFinancial] = useState<MinskyFinancialCaptureResponse | null>(null);
  const [message, setMessage] = useState("");
  const [profileName, setProfileName] = useState("Financeiro Minsky");
  const [capture, setCapture] = useState<MinskyFinancialCaptureRequest>({
    steps: 12,
    reset_before: false,
    unit_mode: "decimal",
    mapping: {
      minimum_bank_capital_ratio: ":bank_min_capital_ratio",
      target_reserve_ratio: ":bank_target_reserve_ratio",
      credit_supply_factor: ":credit_supply_factor",
      default_writeoff_ratio: ":default_writeoff_ratio",
      interbank_spread: ":interbank_spread",
      central_bank_penalty_spread: ":cb_penalty_spread"
    }
  });

  async function command(action: "members" | "signature" | "step" | "reset" | "get_variable" | "set_variable") {
    try { setMessage(`Minsky: ${action}…`); setOutput(await runMinskyCommand({ action, path, variable_id: variable, value })); setMessage("Concluído"); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Falha"); }
  }
  async function runFinancial() {
    try {
      setMessage("Capturando trajetória financeira do Minsky…");
      const result = await runMinskyFinancialController(capture);
      setFinancial(result); setOutput(result); setMessage(`${result.points.length} pontos financeiros capturados`);
    } catch (e) { setMessage(e instanceof Error ? e.message : "Falha"); }
  }
  const save = (apply: boolean) => onSaveProfile({
    module_id: "minsky",
    name: profileName || "Financeiro Minsky",
    inputs: selectedTool === "minsky-financial-controller"
      ? { selected_tool: selectedTool, ...(capture as unknown as Record<string, unknown>) }
      : { path, variable_id: variable, value, selected_tool: selectedTool },
    outputs: asRecord(selectedTool === "minsky-financial-controller" ? financial : output),
    apply
  });
  const rows = useMemo(() => (financial?.points ?? []).map(p => ({
    mes: p.month,
    capital: p.minimum_bank_capital_ratio,
    reservas: p.target_reserve_ratio,
    credito: p.credit_supply_factor * 100,
    writeoff: p.default_writeoff_ratio
  })), [financial]);
  const title = selectedTool === "minsky-introspection" ? "Introspecção REST"
    : selectedTool === "minsky-variables" ? "Editor de variáveis"
    : selectedTool === "minsky-financial-controller" ? "Controlador financeiro"
    : "Controle de execução";

  return <section className="moduleWorkspace panel"><LabHeader module={module} onOpenSimulation={onOpenSimulation} /><div className="labGrid"><div className="labControls"><h3>{title}</h3>
    {selectedTool === "minsky-introspection" && <><label>Caminho REST<input value={path} onChange={e => setPath(e.target.value)} /></label><div className="moduleActions"><button type="button" onClick={() => command("members")} disabled={!module.available}>@list</button><button type="button" className="secondaryButton" onClick={() => command("signature")} disabled={!module.available}>@signature</button></div></>}
    {selectedTool === "minsky-variables" && <><label>Variable ID<input value={variable} onChange={e => setVariable(e.target.value)} /></label><label>Valor<input type="number" value={value} onChange={e => setValue(+e.target.value)} /></label><div className="moduleActions"><button type="button" onClick={() => command("get_variable")} disabled={!module.available}>Ler variável</button><button type="button" onClick={() => command("set_variable")} disabled={!module.available}>Escrever variável</button></div></>}
    {selectedTool === "minsky-runtime" && <div className="moduleActions"><button type="button" onClick={() => command("step")} disabled={!module.available}>Step</button><button type="button" className="secondaryButton" onClick={() => command("reset")} disabled={!module.available}>Reset</button></div>}
    {selectedTool === "minsky-financial-controller" && <>
      <label>Passos / meses<input type="number" min="1" max="240" value={capture.steps} onChange={e => setCapture(c => ({ ...c, steps: +e.target.value }))} /></label>
      <label>Unidades<select value={capture.unit_mode} onChange={e => setCapture(c => ({ ...c, unit_mode: e.target.value as "decimal" | "percent" }))}><option value="decimal">Razões decimais (0,08 = 8%)</option><option value="percent">Percentuais (8 = 8%)</option></select></label>
      <label className="inlineCheck"><input type="checkbox" checked={capture.reset_before} onChange={e => setCapture(c => ({ ...c, reset_before: e.target.checked }))} /> Resetar Minsky antes</label>
      <h4>Mapeamento explícito</h4>
      {Object.entries(capture.mapping).map(([key, mapped]) => <label key={key}>{key}<input value={mapped} onChange={e => setCapture(c => ({ ...c, mapping: { ...c.mapping, [key]: e.target.value } }))} /></label>)}
      <button type="button" onClick={runFinancial} disabled={!module.available}>Capturar trajetória financeira</button>
    </>}
    <ProfileActions profileName={profileName} setProfileName={setProfileName} onSave={save} compatibility={selectedTool === "minsky-financial-controller" && financial ? "ativa: trajetória controla crédito, reservas, capital, defaults e spreads; ledger continua autoritativo" : "assistiva até existir uma trajetória financeira canônica"} /><p className="muted">{message}</p></div>
    <div className="labOutput"><h3>{selectedTool === "minsky-financial-controller" ? "Trajetória financeira" : "Resposta Minsky"}</h3>
      {selectedTool === "minsky-financial-controller" && financial ? <>
        <SimpleLines rows={rows} xKey="mes" series={[{ key: "capital", label: "Capital mínimo %" }, { key: "reservas", label: "Reservas %" }, { key: "credito", label: "Oferta crédito (índice %)" }, { key: "writeoff", label: "Write-off %" }]} />
        <div className="tableWrap"><table><thead><tr><th>Mês</th><th>Capital mín.</th><th>Reserva</th><th>Crédito</th><th>Write-off</th></tr></thead><tbody>{financial.points.slice(0, 24).map(p => <tr key={p.month}><td>{p.month}</td><td>{p.minimum_bank_capital_ratio.toFixed(2)}%</td><td>{p.target_reserve_ratio.toFixed(2)}%</td><td>{(p.credit_supply_factor * 100).toFixed(1)}%</td><td>{p.default_writeoff_ratio.toFixed(1)}%</td></tr>)}</tbody></table></div>
        <button type="button" className="secondaryButton" onClick={() => downloadCsv("minsky-financial-path.csv", rows)}>Exportar trajetória CSV</button>
        <p className="warning">{financial.warning}</p>
      </> : <><pre className="codePreview">{output ? JSON.stringify(output, null, 2) : "Conecte o Minsky REST para usar esta ferramenta individual."}</pre><p className="warning">Somente variáveis explicitamente mapeadas entram no Simulation Lab; saldos contábeis externos são recusados.</p></>}
    </div></div></section>;
}

export function LabWorkspace(props: LabProps) {
  if (props.module.id === "dynare") return <DynareLab {...props} />;
  if (props.module.id === "minsky") return <MinskyLab {...props} />;
  if (props.module.id === "mesa") return <MesaLab {...props} />;
  if (props.module.id === "hark") return <HarkLab {...props} />;
  return null;
}
