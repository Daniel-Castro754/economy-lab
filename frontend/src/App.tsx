import { FormEvent, useEffect, useState } from "react";
import { BatchAxis, BatchExperimentResponse, compileScenario, createLabProfile, createProject, deleteProfile, deleteProject, DesktopRuntimeStatus, DynareStatus, ExperimentSummary, exportBatchFile, exportMinsky, exportSimulationFile, getDesktopRuntimeStatus, getDynareStatus, getExperiment, getHealth, getMinskyStatus, getProject, getRun, getStorageStatus, HealthResponse, HubModuleInfo, HubToolInfo, listModules, listProfiles, listSimulationPresets, listTools, listProjectExperiments, listProjectRuns, listProjects, MinskyStatus, ProfileSummary, ProjectSummary, runBatchExperiment, runProjectExperiment, RunSummary, ScenarioDraft, ScenarioSpec, SimulationPresetInfo, SimulationResult, simulate, simulateProject, StorageStatus, updateProject, applyProfile, applySimulationPreset } from "./api";
import { BatchBarChart, TimeSeriesChart } from "./components/Charts";
import { ModuleWorkspace } from "./components/ModuleWorkspace";
import { LabWorkspace } from "./components/LabWorkspace";
import { ValidationWorkspace } from "./components/ValidationWorkspace";
import { DataCalibrationWorkspace } from "./components/DataCalibrationWorkspace";
import { ModelBuilderWorkspace } from "./components/ModelBuilderWorkspace";
import { SimpleMacroWorkspace } from "./components/SimpleMacroWorkspace";

const initial: ScenarioSpec = {
  name: "Economy Zero",
  months: 24,
  initial_gdp: 100,
  initial_inflation: 4,
  initial_unemployment: 7,
  policy_rate: 10,
  income_tax: 20,
  public_spending_change: 0,
  households: 5000,
  firms: 100,
  banks: 3,
  seed: 42,
  mode: "economy_zero",
  activation_engine: "native",
  mesa_activation_pattern: "random",
  household_shopping_sample_size: 4,
  household_cheapest_choice_probability: 1,
  firm_price_adjustment_strength: 1,
  firm_hiring_strength: 1,
  firm_layoff_strength: 1,
  labor_matching_efficiency: 1,
  initial_capital_per_worker: 1200,
  capital_unit_cost: 25,
  annual_capital_depreciation_rate: 8,
  firm_investment_propensity: 12,
  capital_output_elasticity: 0.30,
  household_behavior: "heuristic",
  minimum_bank_capital_ratio: 8,
  target_reserve_ratio: 10,
  financial_engine: "native",
  bank_credit_supply_factor: 1,
  default_writeoff_ratio: 35,
  interbank_spread: 1,
  central_bank_penalty_spread: 2,
  household_credit_enabled: true,
  household_credit_income_multiple: 0.50,
  household_credit_liquidity_target_months: 3,
  household_credit_spread: 6,
  household_principal_repayment_rate: 4,
  household_default_writeoff_ratio: 50,
  bank_resolution_mode: "government_recapitalization",
  bank_resolution_trigger_ratio: 2,
  bank_resolution_target_ratio: 10,
  bail_in_household_protection: 2000,
  bail_in_firm_protection: 20000,
  financial_guidance: [],
  macro_engine: "off",
  dynare_monetary_shock_bp: 100,
  dynare_irf_periods: 24,
  dynare_neutral_nominal_rate: 8,
  dynare_beta: 0.99,
  dynare_sigma: 1,
  dynare_kappa: 0.10,
  dynare_rho_i: 0.80,
  dynare_phi_pi: 1.50,
  dynare_phi_x: 0.25,
  hark_crra: 2,
  hark_annual_discount_factor: 0.96,
  hark_state_mode: "employment_income",
  hark_unemployment_probability: 0.05,
  hark_unemployment_replacement_rate: 0.30,
  hark_permanent_shock_std: 0.04,
  hark_transitory_shock_std: 0.10,
  hark_permanent_income_memory: 0.18,
  hark_income_groups: 5,
  hark_income_risk_dispersion: 0.35,
  unemployment_benefits_enabled: true,
  unemployment_benefit_replacement_rate: 45,
  unemployment_benefit_waiting_months: 1,
  unemployment_benefit_max_months: 6,
  unemployment_benefit_cap: 3500,
  labor_supply_mode: "reservation_wage",
  labor_search_intensity: 0.90,
  reservation_wage_ratio: 0.75,
  benefit_search_disincentive: 0.20,
  wealth_search_disincentive: 0.10,
  job_separation_risk_memory: 0.25,
  macro_coupling: "advisory",
  macro_coupling_strength: 0.35,
  macro_feedback_strength: 0.15,
  macro_recalibration: "static_irf",
  macro_recalibration_strength: 0.25,
  macro_max_recalibrations: 80,
  shocks: [],
  applied_profiles: {}
};

const sectorLabels: Record<string, string> = {
  households: "Famílias",
  firms: "Empresas",
  banks: "Bancos",
  government: "Governo",
  central_bank: "Banco Central",
  rest_of_world: "Exterior"
};

const instrumentLabels: Record<string, string> = {
  deposits: "Depósitos",
  loans: "Crédito empresarial",
  household_loans: "Crédito às famílias",
  reserves: "Reservas",
  government_bonds: "Títulos públicos",
  central_bank_advances: "Adiantamentos do BC",
  bank_equity: "Capital bancário",
  interbank_loans: "Crédito interbancário",
  other: "Outros"
};

const shockLabels: Record<string, string> = {
  fiscal_spending: "Gasto público",
  productivity: "Produtividade",
  cost_push: "Custos de produção",
  external_demand: "Demanda externa",
  import_cost: "Custo de importação"
};

function money(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    notation: "compact",
    maximumFractionDigits: 2
  }).format(value);
}

function when(value: string) {
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

export default function App() {
  const [spec, setSpec] = useState(initial);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [minskyStatus, setMinskyStatus] = useState<MinskyStatus | null>(null);
  const [dynareStatus, setDynareStatus] = useState<DynareStatus | null>(null);
  const [desktopRuntime, setDesktopRuntime] = useState<DesktopRuntimeStatus | null>(null);
  const [status, setStatus] = useState("Conectando ao motor…");
  const [scenarioPrompt, setScenarioPrompt] = useState("");
  const [draft, setDraft] = useState<ScenarioDraft | null>(null);
  const [storage, setStorage] = useState<StorageStatus | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("Novo projeto");
  const [projectDescription, setProjectDescription] = useState("");
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [batchResult, setBatchResult] = useState<BatchExperimentResponse | null>(null);
  const [batchAxis, setBatchAxis] = useState<BatchAxis>("policy_rate");
  const [batchValues, setBatchValues] = useState("8, 10, 12, 14, 16");
  const [batchRepetitions, setBatchRepetitions] = useState(3);
  const [modules, setModules] = useState<HubModuleInfo[]>([]);
  const [activeModule, setActiveModule] = useState("simulation");
  const [moduleTools, setModuleTools] = useState<HubToolInfo[]>([]);
  const [activeTool, setActiveTool] = useState<string>("simulation-simple");
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [presets, setPresets] = useState<SimulationPresetInfo[]>([]);

  useEffect(() => {
    getDesktopRuntimeStatus().then(setDesktopRuntime).catch(() => setDesktopRuntime(null));
    getHealth()
      .then((value) => {
        setHealth(value);
        setStatus("Pronto");
      })
      .catch(() => setStatus("Backend local indisponível"));
    getMinskyStatus().then(setMinskyStatus).catch(() => setMinskyStatus(null));
    getDynareStatus().then(setDynareStatus).catch(() => setDynareStatus(null));
    getStorageStatus().then(setStorage).catch(() => setStorage(null));
    listProjects().then(setProjects).catch(() => setProjects([]));
    listModules().then(setModules).catch(() => setModules([]));
    listProfiles().then(setProfiles).catch(() => setProfiles([]));
    listSimulationPresets().then(setPresets).catch(() => setPresets([]));
  }, []);

  useEffect(() => {
    listTools(activeModule)
      .then((items) => {
        setModuleTools(items);
        setActiveTool((current) => items.some((item) => item.id === current) ? current : (items[0]?.id ?? ""));
      })
      .catch(() => setModuleTools([]));
  }, [activeModule]);

  async function onCompileScenario() {
    if (!scenarioPrompt.trim()) return;
    setStatus("Compilando proposta de cenário…");
    try {
      setDraft(await compileScenario(scenarioPrompt, spec));
      setStatus("Proposta pronta para revisão");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao compilar cenário");
    }
  }

  async function refreshProjects(selectedId?: string | null) {
    const next = await listProjects();
    setProjects(next);
    setStorage(await getStorageStatus());
    const id = selectedId === undefined ? projectId : selectedId;
    if (id) {
      setRuns(await listProjectRuns(id, 20));
      setExperiments(await listProjectExperiments(id, 10));
    }
  }

  async function onOpenProject(id: string) {
    if (!id) {
      setProjectId(null);
      setRuns([]);
      return;
    }
    setStatus("Abrindo projeto…");
    try {
      const project = await getProject(id);
      setProjectId(project.id);
      setProjectName(project.name);
      setProjectDescription(project.description);
      setSpec(project.scenario);
      setRuns(await listProjectRuns(project.id, 20));
      setExperiments(await listProjectExperiments(project.id, 10));
      setResult(null);
      setBatchResult(null);
      setStatus("Projeto aberto");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao abrir projeto");
    }
  }

  async function onSaveProject() {
    setStatus("Salvando projeto…");
    try {
      const project = projectId
        ? await updateProject(projectId, projectName.trim() || spec.name, spec, projectDescription)
        : await createProject(projectName.trim() || spec.name, spec, projectDescription);
      setProjectId(project.id);
      setProjectName(project.name);
      setProjectDescription(project.description);
      await refreshProjects(project.id);
      setStatus("Projeto salvo localmente");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao salvar projeto");
    }
  }

  function onNewProject() {
    setProjectId(null);
    setProjectName("Novo projeto");
    setProjectDescription("");
    setSpec(initial);
    setResult(null);
    setRuns([]);
    setExperiments([]);
    setBatchResult(null);
    setDraft(null);
    setStatus("Novo projeto não salvo");
  }

  async function onDeleteProject() {
    if (!projectId) return;
    if (!window.confirm(`Excluir o projeto "${projectName}" e todo o histórico de execuções?`)) return;
    setStatus("Excluindo projeto…");
    try {
      await deleteProject(projectId);
      onNewProject();
      await refreshProjects(null);
      setStatus("Projeto excluído");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao excluir projeto");
    }
  }

  async function onOpenRun(runId: string) {
    setStatus("Abrindo execução salva…");
    try {
      const run = await getRun(runId);
      setSpec(run.scenario);
      setResult(run.result);
      setStatus(`Execução de ${when(run.created_at)} carregada`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao abrir execução");
    }
  }


  async function onRunBatch() {
    const values = batchValues.split(/[;,\s]+/).map((value) => Number(value.trim())).filter((value) => Number.isFinite(value));
    if (values.length < 2) {
      setStatus("Informe pelo menos dois valores para comparar");
      return;
    }
    setStatus(`Executando ${values.length * batchRepetitions} simulações em lote…`);
    try {
      if (projectId) {
        const saved = await runProjectExperiment(projectId, spec, batchAxis, values, batchRepetitions);
        setBatchResult(saved.result);
        setExperiments(await listProjectExperiments(projectId, 10));
        setStorage(await getStorageStatus());
        setStatus(`Experimento concluído e salvo · ${saved.result.total_runs} execuções`);
      } else {
        const value = await runBatchExperiment(spec, batchAxis, values, batchRepetitions);
        setBatchResult(value);
        setStatus(`Experimento concluído · ${value.total_runs} execuções não salvas`);
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha no experimento em lote");
    }
  }

  async function onOpenExperiment(experimentId: string) {
    setStatus("Abrindo experimento…");
    try {
      const experiment = await getExperiment(experimentId);
      setBatchResult(experiment.result);
      setStatus(`Experimento de ${when(experiment.created_at)} carregado`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao abrir experimento");
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus(projectId ? "Simulando e salvando…" : "Simulando…");
    try {
      if (projectId) {
        const saved = await simulateProject(projectId, spec);
        setResult(saved.result);
        setProjectName(saved.project.name);
        await refreshProjects(projectId);
        setStatus("Concluído e salvo no histórico");
      } else {
        setResult(await simulate(spec));
        setStatus("Concluído (execução não salva)");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha desconhecida");
    }
  }

  async function onExportSimulation(format: "csv" | "xlsx") {
    if (!result) return;
    setStatus(`Exportando simulação para ${format.toUpperCase()}…`);
    try {
      await exportSimulationFile(format, spec, result);
      setStatus(`Exportação ${format.toUpperCase()} concluída`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha na exportação");
    }
  }

  async function onExportBatch(format: "csv" | "xlsx") {
    if (!batchResult) return;
    setStatus(`Exportando experimento para ${format.toUpperCase()}…`);
    try {
      await exportBatchFile(format, batchResult);
      setStatus(`Exportação ${format.toUpperCase()} concluída`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha na exportação");
    }
  }

  async function refreshProfiles() {
    setProfiles(await listProfiles());
    setStorage(await getStorageStatus());
  }

  async function onApplyProfile(profileId: string) {
    try {
      const applied = await applyProfile(profileId, spec);
      setSpec(applied.scenario);
      setStatus(applied.changes.length ? `Profile aplicado: ${applied.changes.join(" · ")}` : "Profile anexado ao cenário");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao aplicar Profile");
    }
  }

  async function onDeleteProfile(profileId: string) {
    try {
      await deleteProfile(profileId);
      await refreshProfiles();
      setStatus("Profile excluído");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao excluir Profile");
    }
  }

  async function onApplyPreset(presetId: string) {
    try {
      setSpec(await applySimulationPreset(presetId, spec));
      setStatus(`Preset ${presetId} aplicado`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao aplicar preset");
    }
  }

  async function onLabProfile(payload: { module_id: "dynare" | "minsky" | "mesa" | "hark"; name: string; inputs: Record<string, unknown>; outputs?: Record<string, unknown> | null; apply?: boolean }) {
    try {
      const profile = await createLabProfile({ module_id: payload.module_id, name: payload.name, inputs: payload.inputs, outputs: payload.outputs ?? null });
      await refreshProfiles();
      if (payload.apply !== false) {
        const applied = await applyProfile(profile.id, spec);
        setSpec(applied.scenario);
        setActiveModule("simulation");
        setStatus(`${profile.name} salvo e enviado ao Simulation Lab`);
      } else {
        setStatus(`${profile.name} salvo em Meus Profiles`);
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha ao salvar Profile");
    }
  }

  const activeModuleInfo = modules.find((module) => module.id === activeModule);

  return (
    <main className="shell">
      <header>
        <div>
          <span className="eyebrow">ECONOMY LAB · V1.9 HUB</span>
          <h1>Economic Simulation Hub</h1>
          <p>Módulos independentes para simulação, agentes, macroeconomia, SFC/Godley, analytics e cenários.</p>
          <div className="engineBadges">
            <span className={health?.mesa_available ? "available" : "missing"}>
              Mesa {health?.mesa_available ? "disponível" : "não instalado"}
            </span>
            <span className={health?.hark_available ? "available" : "missing"}>
              HARK {health?.hark_available ? "disponível" : "não instalado"}
            </span>
            <span className={health?.minsky_rest_configured ? "available" : "missing"}>
              Minsky {minskyStatus?.reachable ? "conectado" : health?.minsky_rest_configured ? "configurado/offline" : "opcional"}
            </span>
            <span className={dynareStatus?.ready ? "available" : "missing"}>
              Dynare {dynareStatus?.ready ? `pronto${dynareStatus.dynare_version_hint ? ` ${dynareStatus.dynare_version_hint}` : ""}` : "opcional"}
            </span>
            {desktopRuntime && (
              <span className={desktopRuntime.ready ? "available" : "missing"}>
                Desktop {desktopRuntime.ready ? "backend automático" : "backend com erro"}
              </span>
            )}
          </div>
        </div>
        <span className="status">{status}</span>
      </header>

      <nav className="moduleBar" aria-label="Módulos do Economy Lab">
        {modules.map((module) => (
          <button
            type="button"
            key={module.id}
            className={activeModule === module.id ? "moduleTab active" : "moduleTab"}
            onClick={() => setActiveModule(module.id)}
          >
            <span>{module.title}</span>
            <small className={module.available ? "availableDot" : "missingDot"}>{module.available ? "●" : "○"} {module.kind}</small>
          </button>
        ))}
      </nav>

      {moduleTools.length > 0 && (
        <nav className="toolBar" aria-label={`Ferramentas de ${activeModule}`}>
          {moduleTools.map((tool) => (
            <button
              type="button"
              key={tool.id}
              className={activeTool === tool.id ? "toolTab active" : "toolTab"}
              onClick={() => { setActiveTool(tool.id); setStatus(`${tool.title} selecionada`); }}
              title={tool.description}
            >
              <span>{tool.title}</span>
              <small>{tool.output_kinds.join(" · ")}</small>
            </button>
          ))}
        </nav>
      )}

      {activeModule === "simulation" ? (
        activeTool === "simulation-simple" ? (
          <SimpleMacroWorkspace
            onStatus={setStatus}
            onApplyAdvanced={(scenario) => { setSpec(scenario); setActiveTool("simulation-run"); setStatus("Cenário Simple convertido para Economy Zero"); }}
          />
        ) : (
      <section className="grid">
        <form className="panel controls" onSubmit={onSubmit}>
          <h2>Cenário</h2>
          <p className="muted topology">
            {spec.households.toLocaleString("pt-BR")} famílias · {spec.firms} empresas · {spec.banks} bancos
          </p>

          <div className="projectBox">
            <div className="projectTitle">
              <strong>Projeto local</strong>
              <span className="muted">SQLite · {storage?.projects ?? 0} projetos · {storage?.runs ?? 0} execuções · {storage?.experiments ?? 0} lotes · {storage?.profiles ?? 0} profiles</span>
            </div>
            <select value={projectId ?? ""} onChange={(e) => onOpenProject(e.target.value)}>
              <option value="">Projeto não salvo</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>{project.name} ({project.run_count})</option>
              ))}
            </select>
            <input
              className="numberInput"
              value={projectName}
              maxLength={120}
              placeholder="Nome do projeto"
              onChange={(e) => setProjectName(e.target.value)}
            />
            <textarea
              rows={2}
              value={projectDescription}
              maxLength={1000}
              placeholder="Descrição opcional"
              onChange={(e) => setProjectDescription(e.target.value)}
            />
            <div className="projectActions">
              <button type="button" onClick={onSaveProject}>{projectId ? "Salvar alterações" : "Salvar projeto"}</button>
              <button type="button" className="secondaryButton" onClick={onNewProject}>Novo</button>
              {projectId && <button type="button" className="dangerButton" onClick={onDeleteProject}>Excluir</button>}
            </div>
            {projectId && runs.length > 0 && (
              <div className="runHistory">
                <strong>Histórico recente</strong>
                {runs.slice(0, 6).map((run) => (
                  <button type="button" className="runItem" key={run.id} onClick={() => onOpenRun(run.id)}>
                    <span>{when(run.created_at)}</span>
                    <span>PIB {run.final_gdp_index.toFixed(1)} · π {run.final_inflation.toFixed(1)}% · u {run.final_unemployment.toFixed(1)}%</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="profileBox">
            <div className="projectTitle">
              <strong>Motores e Profiles</strong>
              <span className="muted">Basic funciona sem software externo; Profiles trazem configurações dos laboratórios.</span>
            </div>
            <div className="presetGrid">
              {presets.map((preset) => (
                <button type="button" className="secondaryButton" key={preset.id} onClick={() => onApplyPreset(preset.id)} title={preset.description}>
                  {preset.title}
                </button>
              ))}
            </div>
            {Object.keys(spec.applied_profiles ?? {}).length > 0 && (
              <div className="profileChips">
                {Object.entries(spec.applied_profiles).map(([kind, id]) => { const p = profiles.find(item => item.id === id); return <span key={kind}>{kind}: {p?.name ?? id.slice(0, 8)}</span>; })}
              </div>
            )}
            {profiles.length > 0 ? (
              <div className="profileList">
                {profiles.slice(0, 8).map((profile) => (
                  <div className="profileItem" key={profile.id}>
                    <div><strong>{profile.name}</strong><small>{profile.module_id} · {profile.kind} · {profile.compatibility}</small></div>
                    <div className="projectActions"><button type="button" onClick={() => onApplyProfile(profile.id)}>Aplicar</button><button type="button" className="dangerButton" onClick={() => onDeleteProfile(profile.id)}>Excluir</button></div>
                  </div>
                ))}
              </div>
            ) : <p className="muted">Nenhum Profile salvo ainda. Abra Dynare, Mesa, HARK ou Minsky Lab e use “Salvar e enviar”.</p>}
          </div>

          <div className="batchBox">
            <div className="projectTitle">
              <strong>Experimentos em lote</strong>
              <span className="muted">Varra um parâmetro e repita com seeds diferentes</span>
            </div>
            <label>
              Parâmetro comparado
              <select value={batchAxis} onChange={(e) => setBatchAxis(e.target.value as BatchAxis)}>
                <option value="policy_rate">Selic / juros (%)</option>
                <option value="income_tax">Imposto de renda (%)</option>
                <option value="public_spending_change">Variação do gasto público (%)</option>
                <option value="minimum_bank_capital_ratio">Capital mínimo bancário (%)</option>
                <option value="target_reserve_ratio">Reservas alvo (%)</option>
              </select>
            </label>
            <label>
              Valores
              <input className="numberInput" value={batchValues} onChange={(e) => setBatchValues(e.target.value)} placeholder="8, 10, 12, 14, 16" />
            </label>
            <label>
              Repetições por valor
              <input className="numberInput" type="number" min={1} max={10} value={batchRepetitions} onChange={(e) => setBatchRepetitions(Number(e.target.value))} />
            </label>
            <button type="button" onClick={onRunBatch}>Executar comparação</button>
            {projectId && experiments.length > 0 && (
              <div className="runHistory">
                <strong>Lotes recentes</strong>
                {experiments.slice(0, 4).map((experiment) => (
                  <button type="button" className="runItem" key={experiment.id} onClick={() => onOpenExperiment(experiment.id)}>
                    <span>{when(experiment.created_at)} · {experiment.axis}</span>
                    <span>{experiment.total_runs} execuções · {experiment.values.join(" / ")}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="scenarioCompiler">
            <strong>Montar cenário em linguagem natural</strong>
            <textarea
              rows={4}
              value={scenarioPrompt}
              placeholder="Ex.: Simule 36 meses, Selic 12%, produtividade +10% no mês 4 por 6 meses e demanda externa -15%."
              onChange={(e) => setScenarioPrompt(e.target.value)}
            />
            <button type="button" onClick={onCompileScenario}>Gerar proposta</button>
            {draft && (
              <div className="draftReview">
                <p><strong>Revisar antes de aplicar</strong></p>
                <ul>{draft.recognized_changes.map((item) => <li key={item}>{item}</li>)}</ul>
                {draft.assumptions.map((item) => <p className="muted" key={item}>{item}</p>)}
                <div className="draftActions">
                  <button type="button" onClick={() => { setSpec(draft.spec); setDraft(null); setStatus("Proposta aplicada"); }}>Aplicar proposta</button>
                  <button type="button" onClick={() => setDraft(null)}>Descartar</button>
                </div>
              </div>
            )}
          </div>

          {spec.shocks.length > 0 && (
            <div className="shockList">
              <strong>Choques programados</strong>
              {spec.shocks.map((shock, index) => (
                <div className="shockItem" key={`${shock.kind}-${shock.start_month}-${index}`}>
                  <span>{shockLabels[shock.kind] ?? shock.kind}: {shock.magnitude_pct > 0 ? "+" : ""}{shock.magnitude_pct}% · mês {shock.start_month} por {shock.duration_months} meses</span>
                  <button type="button" onClick={() => setSpec({ ...spec, shocks: spec.shocks.filter((_, i) => i !== index) })}>Remover</button>
                </div>
              ))}
            </div>
          )}

          <label>
            Ativação dos agentes
            <select
              value={spec.activation_engine}
              onChange={(e) => setSpec({ ...spec, activation_engine: e.target.value as ScenarioSpec["activation_engine"] })}
            >
              <option value="native">Nativo (referência)</option>
              <option value="mesa" disabled={health !== null && !health.mesa_available}>Mesa 3.5.x</option>
            </select>
          </label>

          <label>
            Decisão das famílias
            <select
              value={spec.household_behavior}
              onChange={(e) => setSpec({ ...spec, household_behavior: e.target.value as ScenarioSpec["household_behavior"] })}
            >
              <option value="heuristic">Heurística transparente</option>
              <option value="hark" disabled={health !== null && !health.hark_available}>HARK / IndShock</option>
            </select>
          </label>

          {spec.household_behavior === "hark" && (
            <>
              <label>
                Sincronização HARK
                <select value={spec.hark_state_mode} onChange={(e) => setSpec({ ...spec, hark_state_mode: e.target.value as ScenarioSpec["hark_state_mode"] })}>
                  <option value="employment_income">Emprego + renda do ABM</option>
                  <option value="normalized">Normalização legada</option>
                </select>
              </label>
              <label>Risco-base de desemprego: <strong>{(spec.hark_unemployment_probability * 100).toFixed(1)}%</strong>
                <input type="range" min="0.005" max="0.20" step="0.005" value={spec.hark_unemployment_probability} onChange={(e) => setSpec({ ...spec, hark_unemployment_probability: Number(e.target.value) })} />
              </label>
              <label>Reposição no desemprego: <strong>{Math.round(spec.hark_unemployment_replacement_rate * 100)}%</strong>
                <input type="range" min="0" max="1" step="0.05" value={spec.hark_unemployment_replacement_rate} onChange={(e) => setSpec({ ...spec, hark_unemployment_replacement_rate: Number(e.target.value) })} />
              </label>
              <label>Grupos de renda
                <input type="number" min="1" max="10" value={spec.hark_income_groups} onChange={(e) => setSpec({ ...spec, hark_income_groups: Number(e.target.value) })} />
              </label>
            </>
          )}

          <div className="subsectionLabel">Mercado de trabalho e benefícios</div>
          <label>
            Seguro-desemprego
            <select value={spec.unemployment_benefits_enabled ? "on" : "off"} onChange={(e) => setSpec({ ...spec, unemployment_benefits_enabled: e.target.value === "on" })}>
              <option value="on">Ativo</option>
              <option value="off">Desligado</option>
            </select>
          </label>
          {spec.unemployment_benefits_enabled && (
            <>
              <label>Reposição do benefício: <strong>{spec.unemployment_benefit_replacement_rate.toFixed(0)}%</strong>
                <input type="range" min="0" max="100" step="5" value={spec.unemployment_benefit_replacement_rate} onChange={(e) => setSpec({ ...spec, unemployment_benefit_replacement_rate: Number(e.target.value) })} />
              </label>
              <label>Carência: <strong>{spec.unemployment_benefit_waiting_months} mês(es)</strong>
                <input type="range" min="0" max="6" step="1" value={spec.unemployment_benefit_waiting_months} onChange={(e) => setSpec({ ...spec, unemployment_benefit_waiting_months: Number(e.target.value) })} />
              </label>
              <label>Duração máxima: <strong>{spec.unemployment_benefit_max_months} meses</strong>
                <input type="range" min="1" max="18" step="1" value={spec.unemployment_benefit_max_months} onChange={(e) => setSpec({ ...spec, unemployment_benefit_max_months: Number(e.target.value) })} />
              </label>
              <label>Teto mensal do benefício
                <input type="number" min="0" step="100" value={spec.unemployment_benefit_cap} onChange={(e) => setSpec({ ...spec, unemployment_benefit_cap: Number(e.target.value) })} />
              </label>
            </>
          )}
          <label>
            Oferta de trabalho
            <select value={spec.labor_supply_mode} onChange={(e) => setSpec({ ...spec, labor_supply_mode: e.target.value as ScenarioSpec["labor_supply_mode"] })}>
              <option value="inelastic">Inelástica / todos procuram</option>
              <option value="reservation_wage">Busca + salário de reserva</option>
            </select>
          </label>
          {spec.labor_supply_mode === "reservation_wage" && (
            <>
              <label>Intensidade-base de busca: <strong>{Math.round(spec.labor_search_intensity * 100)}%</strong>
                <input type="range" min="0.1" max="1" step="0.05" value={spec.labor_search_intensity} onChange={(e) => setSpec({ ...spec, labor_search_intensity: Number(e.target.value) })} />
              </label>
              <label>Salário de reserva: <strong>{Math.round(spec.reservation_wage_ratio * 100)}% do salário-alvo</strong>
                <input type="range" min="0.3" max="1.5" step="0.05" value={spec.reservation_wage_ratio} onChange={(e) => setSpec({ ...spec, reservation_wage_ratio: Number(e.target.value) })} />
              </label>
              <label>Efeito do benefício na busca: <strong>{Math.round(spec.benefit_search_disincentive * 100)}%</strong>
                <input type="range" min="0" max="0.8" step="0.05" value={spec.benefit_search_disincentive} onChange={(e) => setSpec({ ...spec, benefit_search_disincentive: Number(e.target.value) })} />
              </label>
            </>
          )}

          <label>
            Motor macro
            <select
              value={spec.macro_engine}
              onChange={(e) => {
                const macro_engine = e.target.value as ScenarioSpec["macro_engine"];
                setSpec({
                  ...spec,
                  macro_engine,
                  macro_coupling: macro_engine === "off" ? "advisory" : spec.macro_coupling,
                  macro_recalibration: macro_engine === "off" ? "static_irf" : spec.macro_recalibration
                });
              }}
            >
              <option value="off">Desligado</option>
              <option value="dynare" disabled={dynareStatus !== null && !dynareStatus.ready}>Dynare / Octave</option>
            </select>
          </label>

          {spec.macro_engine === "dynare" && (
            <>
              <label>
                Choque monetário: <strong>{spec.dynare_monetary_shock_bp.toFixed(0)} bps</strong>
                <input
                  type="range" min="25" max="500" step="25"
                  value={spec.dynare_monetary_shock_bp}
                  onChange={(e) => setSpec({ ...spec, dynare_monetary_shock_bp: Number(e.target.value) })}
                />
              </label>
              <label>
                IRF Dynare
                <select
                  value={spec.dynare_irf_periods}
                  onChange={(e) => setSpec({ ...spec, dynare_irf_periods: Number(e.target.value) })}
                >
                  <option value={12}>12 trimestres</option>
                  <option value={24}>24 trimestres</option>
                  <option value={40}>40 trimestres</option>
                </select>
              </label>
              <label>
                Acoplamento macro ↔ micro
                <select
                  value={spec.macro_coupling}
                  onChange={(e) => {
                    const macro_coupling = e.target.value as ScenarioSpec["macro_coupling"];
                    setSpec({
                      ...spec,
                      macro_coupling,
                      macro_recalibration: macro_coupling === "advisory" ? "static_irf" : spec.macro_recalibration
                    });
                  }}
                >
                  <option value="advisory">Somente comparar (advisory)</option>
                  <option value="hybrid">Híbrido com feedback</option>
                </select>
              </label>
              {spec.macro_coupling === "hybrid" && (
                <>
                  <label>
                    Força Dynare → ABM: <strong>{Math.round(spec.macro_coupling_strength * 100)}%</strong>
                    <input
                      type="range" min="0" max="1" step="0.05"
                      value={spec.macro_coupling_strength}
                      onChange={(e) => setSpec({ ...spec, macro_coupling_strength: Number(e.target.value) })}
                    />
                  </label>
                  <label>
                    Feedback ABM → macro: <strong>{Math.round(spec.macro_feedback_strength * 100)}%</strong>
                    <input
                      type="range" min="0" max="0.5" step="0.05"
                      value={spec.macro_feedback_strength}
                      onChange={(e) => setSpec({ ...spec, macro_feedback_strength: Number(e.target.value) })}
                    />
                  </label>
                  <label>
                    Atualização do Dynare
                    <select
                      value={spec.macro_recalibration}
                      onChange={(e) => setSpec({ ...spec, macro_recalibration: e.target.value as ScenarioSpec["macro_recalibration"] })}
                    >
                      <option value="static_irf">IRF inicial fixa</option>
                      <option value="quarterly">Reexecutar a cada trimestre</option>
                    </select>
                  </label>
                  {spec.macro_recalibration === "quarterly" && (
                    <label>
                      Adaptação trimestral: <strong>{Math.round(spec.macro_recalibration_strength * 100)}%</strong>
                      <input
                        type="range" min="0" max="1" step="0.05"
                        value={spec.macro_recalibration_strength}
                        onChange={(e) => setSpec({ ...spec, macro_recalibration_strength: Number(e.target.value) })}
                      />
                    </label>
                  )}
                </>
              )}
            </>
          )}

          <section className="scenarioCompiler">
            <h3>Capital, crédito familiar e resolução bancária</h3>
            <div className="grid two">
              <label>Investimento empresarial: <strong>{spec.firm_investment_propensity.toFixed(0)}% da receita</strong>
                <input type="range" min="0" max="40" step="1" value={spec.firm_investment_propensity} onChange={(e) => setSpec({ ...spec, firm_investment_propensity: Number(e.target.value) })} />
              </label>
              <label>Depreciação anual: <strong>{spec.annual_capital_depreciation_rate.toFixed(1)}%</strong>
                <input type="range" min="0" max="30" step="0.5" value={spec.annual_capital_depreciation_rate} onChange={(e) => setSpec({ ...spec, annual_capital_depreciation_rate: Number(e.target.value) })} />
              </label>
              <label>Crédito às famílias
                <select value={spec.household_credit_enabled ? "on" : "off"} onChange={(e) => setSpec({ ...spec, household_credit_enabled: e.target.value === "on" })}>
                  <option value="on">Ativado</option><option value="off">Desativado</option>
                </select>
              </label>
              <label>Limite dívida/renda anual: <strong>{spec.household_credit_income_multiple.toFixed(2)}x</strong>
                <input type="range" min="0" max="2" step="0.05" value={spec.household_credit_income_multiple} onChange={(e) => setSpec({ ...spec, household_credit_income_multiple: Number(e.target.value) })} />
              </label>
              <label>Spread crédito familiar: <strong>{spec.household_credit_spread.toFixed(1)} p.p.</strong>
                <input type="range" min="0" max="25" step="0.5" value={spec.household_credit_spread} onChange={(e) => setSpec({ ...spec, household_credit_spread: Number(e.target.value) })} />
              </label>
              <label>Resolução bancária
                <select value={spec.bank_resolution_mode} onChange={(e) => setSpec({ ...spec, bank_resolution_mode: e.target.value as ScenarioSpec["bank_resolution_mode"] })}>
                  <option value="government_recapitalization">Recapitalização pública</option>
                  <option value="bail_in">Bail-in + backstop público</option>
                  <option value="none">Sem resolução automática</option>
                </select>
              </label>
              <label>Gatilho de resolução: <strong>{spec.bank_resolution_trigger_ratio.toFixed(1)}%</strong>
                <input type="range" min="-10" max="8" step="0.5" value={spec.bank_resolution_trigger_ratio} onChange={(e) => setSpec({ ...spec, bank_resolution_trigger_ratio: Number(e.target.value) })} />
              </label>
              <label>Capital pós-resolução: <strong>{spec.bank_resolution_target_ratio.toFixed(1)}%</strong>
                <input type="range" min="4" max="20" step="0.5" value={spec.bank_resolution_target_ratio} onChange={(e) => setSpec({ ...spec, bank_resolution_target_ratio: Number(e.target.value) })} />
              </label>
            </div>
          </section>

          <label>
            Capital mínimo bancário: <strong>{spec.minimum_bank_capital_ratio.toFixed(1)}%</strong>
            <input
              type="range"
              min="0"
              max="20"
              step="0.5"
              value={spec.minimum_bank_capital_ratio}
              onChange={(e) => setSpec({ ...spec, minimum_bank_capital_ratio: Number(e.target.value) })}
            />
          </label>

          <label>
            Reserva-alvo: <strong>{spec.target_reserve_ratio.toFixed(0)}%</strong>
            <input
              type="range"
              min="0"
              max="50"
              step="1"
              value={spec.target_reserve_ratio}
              onChange={(e) => setSpec({ ...spec, target_reserve_ratio: Number(e.target.value) })}
            />
          </label>

          <label>
            Taxa de juros: <strong>{spec.policy_rate.toFixed(1)}%</strong>
            <input
              type="range"
              min="0"
              max="25"
              step="0.5"
              value={spec.policy_rate}
              onChange={(e) => setSpec({ ...spec, policy_rate: Number(e.target.value) })}
            />
          </label>

          <label>
            Imposto de renda: <strong>{spec.income_tax.toFixed(0)}%</strong>
            <input
              type="range"
              min="0"
              max="50"
              step="1"
              value={spec.income_tax}
              onChange={(e) => setSpec({ ...spec, income_tax: Number(e.target.value) })}
            />
          </label>

          <label>
            Variação do gasto público: <strong>{spec.public_spending_change.toFixed(0)}%</strong>
            <input
              type="range"
              min="-20"
              max="30"
              step="1"
              value={spec.public_spending_change}
              onChange={(e) => setSpec({ ...spec, public_spending_change: Number(e.target.value) })}
            />
          </label>

          <label>
            Horizonte
            <select
              value={spec.months}
              onChange={(e) => setSpec({ ...spec, months: Number(e.target.value) })}
            >
              <option value={12}>12 meses</option>
              <option value={24}>24 meses</option>
              <option value={60}>60 meses</option>
            </select>
          </label>

          <label>
            Semente aleatória
            <input
              className="numberInput"
              type="number"
              min="0"
              value={spec.seed}
              onChange={(e) => setSpec({ ...spec, seed: Number(e.target.value) })}
            />
          </label>

          <button type="submit">Simular Economy Zero</button>
        </form>

        <section className="panel results">
          {batchResult && (
            <section className="accountingBlock batchResults">
              <h3>Comparação de cenários — {batchResult.axis}</h3>
              <p className="muted">{batchResult.total_runs} execuções · {batchResult.repetitions} repetições por valor · agregação {batchResult.analytics_engine}</p>
              <div className="tableWrap">
                <table>
                  <thead><tr><th>Valor</th><th>PIB médio</th><th>Inflação</th><th>Desemprego</th><th>Defaults</th><th>Crédito</th><th>Capital bancário</th><th>SFC</th></tr></thead>
                  <tbody>
                    {batchResult.aggregates.map((row) => (
                      <tr key={row.axis_value}>
                        <td>{row.axis_value.toFixed(2)}</td>
                        <td>{row.mean_gdp_index.toFixed(2)} ± {row.std_gdp_index.toFixed(2)}</td>
                        <td>{row.mean_inflation.toFixed(2)}%</td>
                        <td>{row.mean_unemployment.toFixed(2)}%</td>
                        <td>{row.mean_defaults.toFixed(1)}</td>
                        <td>{money(row.mean_bank_credit)}</td>
                        <td>{row.mean_bank_capital_ratio.toFixed(2)}%</td>
                        <td>{row.all_accounting_balanced ? "✓" : "ERRO"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <BatchBarChart data={batchResult.aggregates} title={`Comparação · ${batchResult.axis}`} />
              <div className="exportActions">
                <button type="button" onClick={() => onExportBatch("xlsx")}>Exportar Excel (.xlsx)</button>
                <button type="button" className="secondaryButton" onClick={() => onExportBatch("csv")}>Exportar CSV</button>
              </div>
              <p className="warning">{batchResult.warning}</p>
            </section>
          )}

          <h2>Resultado</h2>
          {!result ? (
            <p className="muted">Execute um cenário para iniciar a economia multiagente.</p>
          ) : (
            <>
              {result.engines && (
                <div className="engineTrace">
                  <span>Ativação: <strong>{result.engines.activation}</strong></span>
                  <span>Famílias: <strong>{result.engines.household_decision}</strong></span>
                  <span>Contabilidade: <strong>{result.engines.accounting}</strong></span>
                  <span>Minsky: <strong>{result.engines.minsky}</strong></span>
                  <span>Macro: <strong>{result.engines.macro}</strong></span>
                </div>
              )}

              <div className="cards">
                <article><span>PIB real (índice)</span><strong>{result.summary.final_gdp_index.toFixed(2)}</strong></article>
                <article><span>Inflação</span><strong>{result.summary.final_inflation.toFixed(2)}%</strong></article>
                <article><span>Desemprego</span><strong>{result.summary.final_unemployment.toFixed(2)}%</strong></article>
                <article><span>Participação laboral</span><strong>{result.summary.final_labor_force_participation.toFixed(2)}%</strong></article>
                <article><span>Benefícios acumulados</span><strong>{money(result.summary.cumulative_unemployment_benefits)}</strong></article>
                <article><span>Separação média</span><strong>{result.summary.average_job_separation_rate.toFixed(2)}%</strong></article>
                <article><span>Reemprego médio</span><strong>{result.summary.average_job_finding_rate.toFixed(2)}%</strong></article>
                <article><span>Crédito bancário</span><strong>{money(result.summary.final_bank_credit)}</strong></article>
                <article><span>Dívida das famílias</span><strong>{money(result.summary.final_household_debt)}</strong></article>
                <article><span>Capital produtivo</span><strong>{money(result.summary.final_productive_capital)}</strong></article>
                <article><span>Investimento acumulado</span><strong>{money(result.summary.cumulative_business_investment)}</strong></article>
                <article><span>Exportações acumuladas</span><strong>{money(result.summary.cumulative_exports)}</strong></article>
                <article><span>Importações acumuladas</span><strong>{money(result.summary.cumulative_imports)}</strong></article>
                <article><span>Saldo externo acumulado</span><strong>{money(result.summary.cumulative_net_exports)}</strong></article>
                <article><span>Capital bancário</span><strong>{money(result.summary.final_bank_capital)}</strong></article>
                <article><span>Índice de capital</span><strong>{result.summary.final_bank_capital_ratio.toFixed(2)}%</strong></article>
                <article><span>Bancos abaixo do mínimo</span><strong>{result.summary.final_undercapitalized_banks}</strong></article>
                <article><span>Crédito interbancário</span><strong>{money(result.summary.final_interbank_credit)}</strong></article>
                <article><span>Crédito racionado</span><strong>{money(result.summary.cumulative_credit_rationed)}</strong></article>
                <article><span>Perdas com defaults</span><strong>{money(result.summary.cumulative_default_losses)}</strong></article>
                <article><span>Reservas bancárias</span><strong>{money(result.summary.final_bank_reserves)}</strong></article>
                <article><span>Adiantamentos do BC</span><strong>{money(result.summary.final_central_bank_advances)}</strong></article>
                <article><span>Dívida pública</span><strong>{money(result.summary.final_government_debt)}</strong></article>
                <article><span>Riqueza financeira privada</span><strong>{money(result.summary.final_private_net_financial_wealth)}</strong></article>
                <article><span>Gini patrimonial</span><strong>{result.summary.final_gini_wealth.toFixed(3)}</strong></article>
                <article><span>Defaults empresariais</span><strong>{result.summary.cumulative_defaults}</strong></article>
                <article><span>Defaults famílias</span><strong>{result.summary.cumulative_household_defaults}</strong></article>
                <article><span>Resoluções bancárias</span><strong>{result.summary.cumulative_bank_resolutions}</strong></article>
                <article><span>Recapitalização pública</span><strong>{money(result.summary.cumulative_public_recapitalization)}</strong></article>
                <article><span>Perdas por bail-in</span><strong>{money(result.summary.cumulative_bail_in_losses)}</strong></article>
              </div>

              <div className={`ledgerState ${result.summary.ledger_balanced && result.summary.godley_stocks_balanced && result.summary.godley_flows_balanced ? "ok" : "bad"}`}>
                SFC: {result.summary.godley_stocks_balanced && result.summary.godley_flows_balanced
                  ? "ledger + estoques + fluxos balanceados"
                  : "falha nas identidades contábeis"}
              </div>

              {result.labor_market && (
                <section className="accountingBlock">
                  <h3>Mercado de trabalho e benefícios</h3>
                  <div className="cards">
                    <article><span>Benefícios</span><strong>{result.labor_market.benefits_enabled ? "ativos" : "desligados"}</strong></article>
                    <article><span>Reposição</span><strong>{result.labor_market.replacement_rate.toFixed(0)}%</strong></article>
                    <article><span>Participação final</span><strong>{result.labor_market.final_participation_rate.toFixed(2)}%</strong></article>
                    <article><span>Separação média</span><strong>{result.labor_market.average_job_separation_rate.toFixed(2)}%</strong></article>
                    <article><span>Job finding médio</span><strong>{result.labor_market.average_job_finding_rate.toFixed(2)}%</strong></article>
                    <article><span>Transferências acumuladas</span><strong>{money(result.labor_market.cumulative_benefits)}</strong></article>
                  </div>
                  <p className="warning">{result.labor_market.warning}</p>
                </section>
              )}

              {result.household_engine && (
                <section className="accountingBlock">
                  <h3>Famílias — HARK stateful</h3>
                  <p className="muted">{result.household_engine.engine} · modo {result.household_engine.state_mode} · {result.household_engine.income_groups} grupos de renda</p>
                  <div className="cards">
                    <article><span>Emprego</span><strong>{result.household_engine.employment_rate.toFixed(1)}%</strong></article>
                    <article><span>Renda permanente média</span><strong>{money(result.household_engine.average_permanent_income)}</strong></article>
                    <article><span>Renda transitória / permanente</span><strong>{result.household_engine.average_transitory_income_ratio.toFixed(3)}</strong></article>
                    <article><span>Risco desemprego médio</span><strong>{result.household_engine.average_unemployment_probability.toFixed(2)}%</strong></article>
                    <article><span>Benefício médio atual</span><strong>{money(result.household_engine.average_unemployment_benefit)}</strong></article>
                    <article><span>Participação laboral</span><strong>{result.household_engine.labor_force_participation.toFixed(1)}%</strong></article>
                  </div>
                  <div className="tableWrap"><table><thead><tr><th>Grupo</th><th>Famílias</th><th>Emprego</th><th>Participação</th><th>Salário</th><th>Salário reserva</th><th>Busca</th><th>Benefício</th><th>Renda permanente</th><th>Risco desemprego</th><th>Consumo</th><th>Depósito</th></tr></thead><tbody>
                    {result.household_engine.groups.map(group => <tr key={group.group}><td>G{group.group}</td><td>{group.households}</td><td>{group.employment_rate.toFixed(1)}%</td><td>{group.labor_force_participation.toFixed(1)}%</td><td>{money(group.average_wage)}</td><td>{money(group.average_reservation_wage)}</td><td>{(group.average_search_intensity * 100).toFixed(1)}%</td><td>{money(group.average_unemployment_benefit)}</td><td>{money(group.average_permanent_income)}</td><td>{group.average_unemployment_probability.toFixed(2)}%</td><td>{money(group.average_consumption)}</td><td>{money(group.average_deposit)}</td></tr>)}
                  </tbody></table></div>
                  <p className="warning">{result.household_engine.warning}</p>
                </section>
              )}

              {result.financial && (
                <section className="accountingBlock">
                  <h3>Motor financeiro</h3>
                  <p className="muted">{result.financial.engine} · {result.financial.mode}{result.financial.profile_id ? ` · Profile ${result.financial.profile_id.slice(0, 8)}` : ""}</p>
                  <div className="cards">
                    <article><span>Capital mínimo</span><strong>{result.financial.current.minimum_bank_capital_ratio.toFixed(2)}%</strong></article>
                    <article><span>Reserva-alvo</span><strong>{result.financial.current.target_reserve_ratio.toFixed(2)}%</strong></article>
                    <article><span>Oferta de crédito</span><strong>{(result.financial.current.credit_supply_factor * 100).toFixed(1)}%</strong></article>
                    <article><span>Write-off default</span><strong>{result.financial.current.default_writeoff_ratio.toFixed(1)}%</strong></article>
                    <article><span>Spread interbancário</span><strong>{result.financial.current.interbank_spread.toFixed(2)} p.p.</strong></article>
                    <article><span>Penalidade BC</span><strong>{result.financial.current.central_bank_penalty_spread.toFixed(2)} p.p.</strong></article>
                  </div>
                  {result.financial.guidance_points.length > 1 && <p className="muted">Trajetória Minsky ativa com {result.financial.guidance_points.length} pontos mensais.</p>}
                  <p className="warning">{result.financial.warning}</p>
                </section>
              )}

              <section className="visualizationBlock">
                <div className="visualizationHeader">
                  <div><h3>Gráficos da simulação</h3><p className="muted">Visualizações geradas diretamente da série mensal realizada.</p></div>
                  <div className="exportActions">
                    <button type="button" onClick={() => onExportSimulation("xlsx")}>Exportar Excel (.xlsx)</button>
                    <button type="button" className="secondaryButton" onClick={() => onExportSimulation("csv")}>Exportar CSV</button>
                  </div>
                </div>
                <div className="chartGrid">
                  <TimeSeriesChart data={result.series} title="PIB real" series={[{ key: "gdp_index", label: "PIB (índice)" }]} />
                  <TimeSeriesChart data={result.series} title="Inflação, desemprego e juros" series={[
                    { key: "inflation", label: "Inflação" },
                    { key: "unemployment", label: "Desemprego" },
                    { key: "policy_rate", label: "Juros" }
                  ]} />
                  <TimeSeriesChart data={result.series} title="Crédito bancário" series={[{ key: "bank_credit", label: "Crédito" }, { key: "household_debt", label: "Dívida famílias" }]} />
                  <TimeSeriesChart data={result.series} title="Capital produtivo e investimento" series={[{ key: "productive_capital", label: "Capital produtivo" }, { key: "business_investment", label: "Investimento mensal" }]} />
                  <TimeSeriesChart data={result.series} title="Mercado de trabalho" series={[{ key: "unemployment", label: "Desemprego" }, { key: "labor_force_participation", label: "Participação" }, { key: "job_finding_rate", label: "Reemprego" }]} />
                </div>
              </section>

              {result.shocks && (
                <section className="accountingBlock">
                  <h3>Choques econômicos</h3>
                  <div className="tableWrap">
                    <table>
                      <thead><tr><th>Choque</th><th>Magnitude</th><th>Início</th><th>Duração</th></tr></thead>
                      <tbody>
                        {result.shocks.schedules.map((shock, index) => (
                          <tr key={`${shock.kind}-${index}`}>
                            <td>{shockLabels[shock.kind] ?? shock.kind}</td>
                            <td>{shock.magnitude_pct > 0 ? "+" : ""}{shock.magnitude_pct.toFixed(1)}%</td>
                            <td>mês {shock.start_month}</td>
                            <td>{shock.duration_months} meses</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="warning">{result.shocks.warning}</p>
                </section>
              )}

              {result.macro && (
                <section className="accountingBlock">
                  <h3>Dynare — IRF ativa / mais recente</h3>
                  <p className="muted">
                    {result.macro.model_kind} · choque de {result.macro.shock_size_pp.toFixed(2)} p.p. · período: {result.macro.period_unit} · acoplamento: {result.macro.coupling_mode}
                  </p>
                  <div className="tableWrap">
                    <table>
                      <thead>
                        <tr><th>Trimestre</th><th>Hiato do produto</th><th>Inflação</th><th>Juros</th></tr>
                      </thead>
                      <tbody>
                        {result.macro.irf.slice(0, 16).map((point) => (
                          <tr key={point.period}>
                            <td>{point.period}</td>
                            <td>{point.output_gap.toFixed(4)} p.p.</td>
                            <td>{point.inflation_gap.toFixed(4)} p.p.</td>
                            <td>{point.policy_rate_gap.toFixed(4)} p.p.</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="warning">{result.macro.warning}</p>
                </section>
              )}

              {result.coupling && (
                <section className="accountingBlock">
                  <h3>Acoplamento Dynare ↔ ABM/SFC</h3>
                  <p className="muted">
                    Modo: {result.coupling.mode} · força: {Math.round((result.coupling.parameters.coupling_strength ?? 0) * 100)}% · feedback: {Math.round((result.coupling.parameters.feedback_strength ?? 0) * 100)}%
                  </p>
                  <div className="tableWrap">
                    <table>
                      <thead>
                        <tr><th>Mês</th><th>Juros aplicados</th><th>Guia produto</th><th>Produto realizado*</th><th>Inflação</th><th>Estresse financeiro</th></tr>
                      </thead>
                      <tbody>
                        {result.coupling.points.slice(0, 24).map((point) => (
                          <tr key={point.month}>
                            <td>{point.month}</td>
                            <td>{point.applied_policy_rate_pct.toFixed(2)}%</td>
                            <td>{point.output_gap_guidance_pp.toFixed(3)} p.p.</td>
                            <td>{point.realized_output_gap_proxy_pp.toFixed(3)} p.p.</td>
                            <td>{point.realized_inflation_pct.toFixed(2)}%</td>
                            <td>{(point.financial_stress * 100).toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="warning">*Produto realizado é um proxy cíclico, não produto potencial. {result.coupling.warning}</p>
                </section>
              )}

              {result.macro_recalibration && (
                <section className="accountingBlock">
                  <h3>Re-solução macro trimestral</h3>
                  <p className="muted">
                    {result.macro_recalibration.completed_recalibrations} reexecuções · adaptação {Math.round(result.macro_recalibration.adaptation_strength * 100)}% · frequência {result.macro_recalibration.frequency_months} meses
                  </p>
                  <div className="tableWrap">
                    <table>
                      <thead>
                        <tr><th>Trimestre</th><th>Cresc. PIB</th><th>Inflação</th><th>Desemprego</th><th>Estresse</th><th>Choque efetivo</th><th>φπ</th><th>φx</th></tr>
                      </thead>
                      <tbody>
                        {result.macro_recalibration.runs.map((run) => (
                          <tr key={run.quarter}>
                            <td>T{run.quarter} → mês {run.next_start_month}</td>
                            <td>{run.state.quarterly_gdp_growth_pct.toFixed(2)}%</td>
                            <td>{run.state.inflation_pct.toFixed(2)}%</td>
                            <td>{run.state.unemployment_pct.toFixed(2)}%</td>
                            <td>{(run.state.financial_stress * 100).toFixed(1)}%</td>
                            <td>{run.effective_monetary_shock_pp.toFixed(3)} p.p.</td>
                            <td>{(run.parameters.phi_pi ?? 0).toFixed(3)}</td>
                            <td>{(run.parameters.phi_x ?? 0).toFixed(3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="warning">{result.macro_recalibration.warning}</p>
                </section>
              )}

              {result.banking && (
                <section className="accountingBlock">
                  <h3>Sistema bancário</h3>
                  <p className="muted">
                    Capital agregado: {money(result.banking.aggregate_capital)} · razão de capital: {result.banking.aggregate_capital_ratio.toFixed(2)}%
                  </p>
                  <div className="tableWrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Banco</th><th>Capital</th><th>RWA</th><th>Índice</th><th>Empresas</th><th>Famílias</th><th>Interbancário</th><th>BC</th><th>Resolução</th><th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.banking.banks.map((bank) => (
                          <tr key={bank.bank_id}>
                            <td>Banco {bank.bank_id + 1}</td>
                            <td>{money(bank.regulatory_capital)}</td>
                            <td>{money(bank.risk_weighted_assets)}</td>
                            <td>{bank.capital_ratio.toFixed(2)}%</td>
                            <td>{money(bank.corporate_loans)}</td>
                            <td>{money(bank.household_loans)}</td>
                            <td>{money(bank.interbank_borrowing)}</td>
                            <td>{money(bank.central_bank_borrowing)}</td>
                            <td>{bank.resolutions ? `${bank.resolutions} · ${bank.last_resolution_mode}` : "—"}</td>
                            <td>{bank.compliant ? "adequado" : "abaixo do mínimo"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {result.accounting && (
                <section className="accountingBlock">
                  <h3>Balanços setoriais</h3>
                  <div className="tableWrap">
                    <table>
                      <thead>
                        <tr><th>Setor</th><th>Ativos</th><th>Passivos</th><th>Patrimônio financeiro líquido</th></tr>
                      </thead>
                      <tbody>
                        {result.accounting.sector_balance_sheets.map((sheet) => (
                          <tr key={sheet.sector}>
                            <td>{sectorLabels[sheet.sector] ?? sheet.sector}</td>
                            <td>{money(sheet.assets)}</td>
                            <td>{money(sheet.liabilities)}</td>
                            <td>{money(sheet.net_financial_worth)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <h3>Matriz Godley — estoques finais</h3>
                  <div className="tableWrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Instrumento</th>
                          <th>Famílias</th><th>Empresas</th><th>Bancos</th><th>Governo</th><th>BC</th><th>Exterior</th><th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.accounting.stock_rows.map((row) => (
                          <tr key={row.instrument}>
                            <td>{instrumentLabels[row.instrument] ?? row.instrument}</td>
                            <td>{money(row.sectors.households ?? 0)}</td>
                            <td>{money(row.sectors.firms ?? 0)}</td>
                            <td>{money(row.sectors.banks ?? 0)}</td>
                            <td>{money(row.sectors.government ?? 0)}</td>
                            <td>{money(row.sectors.central_bank ?? 0)}</td>
                            <td>{money(row.sectors.rest_of_world ?? 0)}</td>
                            <td>{Math.abs(row.total) < 0.01 ? "0" : money(row.total)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              <section className="accountingBlock">
                <h3>Ponte Minsky</h3>
                <p className="muted">
                  {minskyStatus?.reachable
                    ? `REST conectado (${minskyStatus.object_type ?? "Minsky"}). O Economy Lab continua sendo a fonte contábil.`
                    : "Sem Minsky ao vivo: ainda é possível exportar o snapshot Godley v1.0 em JSON."}
                </p>
                <button type="button" onClick={async () => {
                  const payload = await exportMinsky(spec);
                  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a"); a.href = url; a.download = `economy-lab-minsky-${spec.seed}.json`; a.click();
                  URL.revokeObjectURL(url);
                }}>Exportar Godley para Minsky</button>
              </section>

              <p className="warning">{result.warning}</p>
              <div className="timeline" aria-label="Série do PIB real">
                {result.series.map((point) => (
                  <div
                    key={point.month}
                    title={`Mês ${point.month}: PIB ${point.gdp_index.toFixed(2)} · desemprego ${point.unemployment.toFixed(2)}%`}
                    style={{ height: `${Math.max(8, Math.min(100, point.gdp_index - 40))}%` }}
                  />
                ))}
              </div>
            </>
          )}
        </section>
      </section>
        )
      ) : activeModuleInfo?.id === "validation" ? (
        <ValidationWorkspace module={activeModuleInfo} onOpenSimulation={() => setActiveModule("simulation")} />
      ) : activeModuleInfo?.id === "data-calibration" ? (
        <DataCalibrationWorkspace module={activeModuleInfo} scenario={spec} result={result} onApplyScenario={setSpec} onOpenSimulation={() => setActiveModule("simulation")} />
      ) : activeModuleInfo?.id === "scenario-ai" ? (
        <ModelBuilderWorkspace module={activeModuleInfo} selectedTool={activeTool} onApplyScenario={setSpec} onOpenSimulation={() => setActiveModule("simulation")} />
      ) : activeModuleInfo && ["dynare", "minsky", "mesa", "hark"].includes(activeModuleInfo.id) ? (
        <LabWorkspace
          module={activeModuleInfo}
          selectedTool={activeTool}
          onOpenSimulation={() => setActiveModule("simulation")}
          onSaveProfile={onLabProfile}
        />
      ) : activeModuleInfo ? (
        <ModuleWorkspace
          module={activeModuleInfo}
          onOpenSimulation={() => setActiveModule("simulation")}
        />
      ) : null}
    </main>
  );
}
