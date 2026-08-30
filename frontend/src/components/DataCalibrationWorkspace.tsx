import { useEffect, useMemo, useState } from "react";
import type {
  CalibrationAggregation, CalibrationComparisonMode, CalibrationFitResponse, CalibrationFrequency,
  CalibrationMetric, CalibrationParameter, CalibrationResponse, CalibrationStatistic, CalibrationTargetInput,
  DataSourceCatalogItem, DataSourceId, EconomicSeries, HubModuleInfo, ScenarioSpec, SimulationResult
} from "../api";
import {
  evaluateCalibration, exportCalibrationFile, fetchEconomicSeries, fitCalibration, listDataSources
} from "../api";

const metricLabels: Record<CalibrationMetric, string> = {
  inflation: "Inflação",
  unemployment: "Desemprego",
  policy_rate: "Juros / política monetária",
  gdp_growth: "Crescimento do PIB",
  bank_credit_growth: "Crescimento do crédito",
  bank_capital_ratio: "Índice de capital bancário"
};

const parameterLabels: Record<CalibrationParameter, string> = {
  initial_inflation: "Inflação inicial",
  initial_unemployment: "Desemprego inicial",
  policy_rate: "Taxa de juros",
  public_spending_change: "Variação do gasto público",
  minimum_bank_capital_ratio: "Capital mínimo bancário",
  target_reserve_ratio: "Reserva-alvo bancária",
  labor_matching_efficiency: "Eficiência do matching"
};

type TargetRow = CalibrationTargetInput & { localId: string };

export function DataCalibrationWorkspace({
  module, scenario, result, onApplyScenario, onOpenSimulation
}: {
  module: HubModuleInfo;
  scenario: ScenarioSpec;
  result: SimulationResult | null;
  onApplyScenario: (next: ScenarioSpec) => void;
  onOpenSimulation: () => void;
}) {
  const [catalog, setCatalog] = useState<DataSourceCatalogItem[]>([]);
  const [source, setSource] = useState<DataSourceId>("bcb_sgs");
  const [seriesId, setSeriesId] = useState("432");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [endDate, setEndDate] = useState("");
  const [country, setCountry] = useState("BRA");
  const [ibgePeriods, setIbgePeriods] = useState("-12");
  const [ibgeVariable, setIbgeVariable] = useState("all");
  const [series, setSeries] = useState<EconomicSeries | null>(null);
  const [metric, setMetric] = useState<CalibrationMetric>("policy_rate");
  const [statistic, setStatistic] = useState<CalibrationStatistic>("last");
  const [comparisonMode, setComparisonMode] = useState<CalibrationComparisonMode>("moment");
  const [alignmentFrequency, setAlignmentFrequency] = useState<CalibrationFrequency>("auto");
  const [aggregation, setAggregation] = useState<CalibrationAggregation>("mean");
  const [weight, setWeight] = useState(1);
  const [targets, setTargets] = useState<TargetRow[]>([]);
  const [simulationStartDate, setSimulationStartDate] = useState("");
  const [calibration, setCalibration] = useState<CalibrationResponse | null>(null);
  const [fit, setFit] = useState<CalibrationFitResponse | null>(null);
  const [fitParameters, setFitParameters] = useState<CalibrationParameter[]>(["initial_inflation", "initial_unemployment", "policy_rate"]);
  const [trainingEndDate, setTrainingEndDate] = useState("");
  const [validationStartDate, setValidationStartDate] = useState("");
  const [status, setStatus] = useState("Carregue uma série e monte uma cesta de metas.");

  useEffect(() => { listDataSources().then(setCatalog).catch(() => setCatalog([])); }, []);
  const activeSource = useMemo(() => catalog.find((item) => item.id === source), [catalog, source]);
  const recent = series?.observations.slice(-12) ?? [];

  async function loadSeries() {
    setStatus("Consultando fonte pública…"); setCalibration(null); setFit(null);
    try {
      const source_options: Record<string, string> = {};
      if (source === "world_bank") source_options.country = country;
      if (source === "ibge_sidra") {
        source_options.periods = ibgePeriods;
        source_options.variable = ibgeVariable;
        source_options.localities = "N1[all]";
      }
      const loaded = await fetchEconomicSeries({
        source, series_id: seriesId, start_date: startDate || null, end_date: endDate || null,
        source_options, use_cache: true, timeout_seconds: 30
      });
      setSeries(loaded);
      setStatus(`${loaded.observations.length} observações carregadas${loaded.cached ? " do cache local" : ""}.`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Falha ao consultar série."); }
  }

  function addTarget() {
    if (!series) return;
    setTargets((current) => [...current, {
      localId: `${Date.now()}-${current.length}`,
      metric, series, statistic, weight, scale_floor: 1,
      comparison_mode: comparisonMode, alignment_frequency: alignmentFrequency, aggregation
    }]);
    setStatus(`Meta adicionada: ${metricLabels[metric]} · ${series.title}.`);
  }

  function removeTarget(localId: string) {
    setTargets((current) => current.filter((item) => item.localId !== localId));
    setCalibration(null); setFit(null);
  }

  function payloadTargets(): CalibrationTargetInput[] {
    return targets.map(({ localId: _localId, ...target }) => target);
  }

  async function calibrate() {
    if (!result || !targets.length) return;
    setStatus("Comparando cesta de metas com a simulação atual…"); setFit(null);
    try {
      const report = await evaluateCalibration({
        scenario, result, targets: payloadTargets(), simulation_start_date: simulationStartDate || null
      });
      setCalibration(report); setStatus(`Calibração multialvo · score ${report.score.toFixed(1)}/100.`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Falha na calibração."); }
  }

  async function runFit() {
    if (!targets.length || !fitParameters.length) return;
    setStatus("Executando ajuste limitado; cada candidato reexecuta o Simulation Lab…");
    try {
      const fitted = await fitCalibration({
        scenario, targets: payloadTargets(), parameters: fitParameters,
        simulation_start_date: simulationStartDate || null, max_evaluations: 24, max_rounds: 3,
        training_end_date: trainingEndDate || null, validation_start_date: validationStartDate || null
      });
      setFit(fitted); setCalibration(fitted.final_calibration);
      setStatus(`Ajuste concluído · ${fitted.baseline_score.toFixed(1)} → ${fitted.best_score.toFixed(1)} em ${fitted.evaluations} avaliações.`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Falha no ajuste limitado."); }
  }

  function applyPatch(patch: Record<string, number>) {
    onApplyScenario({ ...scenario, ...patch });
    setStatus("Patch aplicado ao formulário do Simulation Lab. Revise antes de executar.");
  }

  function toggleParameter(parameter: CalibrationParameter) {
    setFitParameters((current) => current.includes(parameter) ? current.filter((item) => item !== parameter) : [...current, parameter]);
  }

  return <section className="panel dataCalibrationWorkspace">
    <div className="moduleHero">
      <div><span className="eyebrow">MÓDULO · DADOS REAIS · v2.6</span><h2>{module.title}</h2><p>{module.description}</p></div>
      <span className="moduleStatus available">Multialvo · alinhamento · ajuste limitado</span>
    </div>

    <div className="moduleColumns">
      <div>
        <h3>1. Série econômica</h3>
        <label>Fonte<select value={source} onChange={(e) => setSource(e.target.value as DataSourceId)}>
          {(catalog.length ? catalog : [{ id: "bcb_sgs", title: "BCB — SGS" } as DataSourceCatalogItem]).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select></label>
        <label>{activeSource?.identifier_label ?? "Identificador"}<input value={seriesId} onChange={(e) => setSeriesId(e.target.value)} /></label>
        {source === "world_bank" && <label>País<input value={country} onChange={(e) => setCountry(e.target.value)} /></label>}
        {source === "ibge_sidra" && <div className="inlineFields"><label>Períodos<input value={ibgePeriods} onChange={(e) => setIbgePeriods(e.target.value)} /></label><label>Variável<input value={ibgeVariable} onChange={(e) => setIbgeVariable(e.target.value)} /></label></div>}
        <div className="inlineFields"><label>Início<input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></label><label>Fim<input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></label></div>
        <button type="button" onClick={loadSeries}>Carregar série</button>
        {activeSource?.notes?.map((note) => <p className="muted" key={note}>{note}</p>)}
      </div>

      <div>
        <h3>2. Transformar em meta</h3>
        <label>Métrica<select value={metric} onChange={(e) => setMetric(e.target.value as CalibrationMetric)}>{Object.entries(metricLabels).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <label>Comparação<select value={comparisonMode} onChange={(e) => setComparisonMode(e.target.value as CalibrationComparisonMode)}><option value="moment">Momento agregado</option><option value="aligned_path">Trajetória alinhada</option></select></label>
        {comparisonMode === "moment" ? <label>Momento<select value={statistic} onChange={(e) => setStatistic(e.target.value as CalibrationStatistic)}><option value="last">Último valor</option><option value="mean">Média</option><option value="median">Mediana</option><option value="std">Desvio padrão</option></select></label> : <>
          <label>Frequência<select value={alignmentFrequency} onChange={(e) => setAlignmentFrequency(e.target.value as CalibrationFrequency)}><option value="auto">Automática</option><option value="monthly">Mensal</option><option value="quarterly">Trimestral</option><option value="annual">Anual</option></select></label>
          <label>Agregação<select value={aggregation} onChange={(e) => setAggregation(e.target.value as CalibrationAggregation)}><option value="mean">Média no período</option><option value="last">Último valor do período</option></select></label>
        </>}
        <label>Peso<input type="number" min="0.1" max="100" step="0.5" value={weight} onChange={(e) => setWeight(Number(e.target.value))} /></label>
        <button type="button" onClick={addTarget} disabled={!series}>Adicionar à cesta</button>
      </div>
    </div>

    <p className="statusLine">{status}</p>
    {series && <div className="panelInset"><h3>{series.title}</h3><p>{series.source} · {series.series_id} · {series.frequency} · {series.unit || "unidade não informada"}</p><table><thead><tr><th>Data/período</th><th>Valor</th></tr></thead><tbody>{recent.map((point) => <tr key={`${point.date}-${point.value}`}><td>{point.date}</td><td>{point.value.toLocaleString("pt-BR")}</td></tr>)}</tbody></table></div>}

    <div className="panelInset">
      <h3>3. Cesta de metas reais</h3>
      {!targets.length ? <p className="muted">Adicione inflação, desemprego, juros, PIB, crédito ou capital bancário. O score combina os pesos definidos.</p> : <div className="tableWrap"><table><thead><tr><th>Métrica</th><th>Série</th><th>Modo</th><th>Peso</th><th></th></tr></thead><tbody>{targets.map((target) => <tr key={target.localId}><td>{metricLabels[target.metric]}</td><td>{target.series.source}:{target.series.series_id}</td><td>{target.comparison_mode === "aligned_path" ? `trajetória · ${target.alignment_frequency}` : target.statistic}</td><td>{target.weight ?? 1}</td><td><button type="button" className="secondaryButton" onClick={() => removeTarget(target.localId)}>Remover</button></td></tr>)}</tbody></table></div>}
      <label>Data inicial da simulação para alinhamento<input type="date" value={simulationStartDate} onChange={(e) => setSimulationStartDate(e.target.value)} /></label>
      <p className="muted">Se ficar vazio, a v2.6 ancora o último mês simulado na observação real mais recente. Para pesquisas reproduzíveis, informe uma data.</p>
      <div className="moduleActions"><button type="button" onClick={calibrate} disabled={!result || !targets.length}>Avaliar cesta</button>{!result && <button type="button" className="secondaryButton" onClick={onOpenSimulation}>Executar simulação primeiro</button>}</div>
    </div>

    <div className="panelInset">
      <h3>4. Ajuste quantitativo limitado</h3>
      <p className="muted">Busca coordenada auditável. Não estima β, CRRA, κ ou outros parâmetros estruturais.</p>
      <div className="engineBadges">{(Object.keys(parameterLabels) as CalibrationParameter[]).map((parameter) => <label key={parameter} className={fitParameters.includes(parameter) ? "available" : "optional"}><input type="checkbox" checked={fitParameters.includes(parameter)} onChange={() => toggleParameter(parameter)} /> {parameterLabels[parameter]}</label>)}</div>
      <div className="inlineFields"><label>Fim do treino<input type="date" value={trainingEndDate} onChange={(e) => setTrainingEndDate(e.target.value)} /></label><label>Início da validação<input type="date" value={validationStartDate} onChange={(e) => setValidationStartDate(e.target.value)} /></label></div>
      <p className="muted">Preencha as duas datas para reservar uma janela histórica que não influencia a busca e serve apenas para validação fora da amostra.</p>
      <button type="button" onClick={runFit} disabled={!targets.length || !fitParameters.length}>Procurar patch melhor</button>
    </div>

    {calibration && <div className="panelInset"><h3>Resultado da calibração</h3><div className="metricCards"><div><span>Score</span><strong>{calibration.score.toFixed(1)}/100</strong></div><div><span>Erro normalizado</span><strong>{calibration.normalized_rmse.toFixed(3)}</strong></div></div>
      <div className="tableWrap"><table><thead><tr><th>Métrica</th><th>Modo</th><th>Real</th><th>Simulado</th><th>Erro</th><th>N alinhado</th></tr></thead><tbody>{calibration.metrics.map((item, index) => <tr key={`${item.metric}-${item.series_id}-${index}`}><td>{metricLabels[item.metric]}</td><td>{item.comparison_mode}</td><td>{item.real_value.toFixed(3)}</td><td>{item.simulated_value.toFixed(3)}</td><td>{item.error.toFixed(3)}</td><td>{item.aligned_observations}</td></tr>)}</tbody></table></div>
      <p className="warning">{calibration.warning}</p>
      <div className="moduleActions"><button type="button" onClick={() => applyPatch(calibration.suggested_scenario_patch)} disabled={!Object.keys(calibration.suggested_scenario_patch).length}>Aplicar patch inicial</button><button type="button" className="secondaryButton" onClick={() => exportCalibrationFile(scenario, calibration, fit)}>Exportar Excel</button><button type="button" className="secondaryButton" onClick={onOpenSimulation}>Abrir Simulation Lab</button></div>
    </div>}

    {fit && <div className="panelInset"><h3>Ajuste limitado</h3><div className="metricCards"><div><span>Baseline</span><strong>{fit.baseline_score.toFixed(1)}</strong></div><div><span>Melhor score</span><strong>{fit.best_score.toFixed(1)}</strong></div><div><span>Avaliações</span><strong>{fit.evaluations}</strong></div></div>
      {fit.validation_score != null && <p><strong>Score fora da amostra:</strong> {fit.validation_score.toFixed(1)}/100</p>}
      <div className="tableWrap"><table><thead><tr><th>Parâmetro</th><th>Valor sugerido</th></tr></thead><tbody>{Object.entries(fit.best_scenario_patch).map(([key, value]) => <tr key={key}><td>{parameterLabels[key as CalibrationParameter] ?? key}</td><td>{value.toFixed(4)}</td></tr>)}</tbody></table></div>
      <p className="warning">{fit.warning}</p>
      <button type="button" onClick={() => applyPatch(fit.best_scenario_patch)} disabled={!Object.keys(fit.best_scenario_patch).length}>Aplicar melhor patch ao formulário</button>
    </div>}
  </section>;
}
