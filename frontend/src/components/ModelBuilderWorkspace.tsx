import { useState } from "react";
import {
  compileModel,
  HubModuleInfo,
  ModelDraft,
  ModelSpec,
  ScenarioSpec,
  validateModelSpecCandidate
} from "../api";

type Props = {
  module: HubModuleInfo;
  selectedTool: string;
  onApplyScenario: (scenario: ScenarioSpec) => void;
  onOpenSimulation: () => void;
};

const examplePrompt = "Crie uma economia exportadora de commodities, com alta desigualdade e sistema bancário concentrado. Simule 36 meses com 8.000 famílias, 140 empresas, inflação de 5%, desemprego de 8% e Selic de 12%. Use HARK e Dynare em modo híbrido.";

function downloadJson(name: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function EnginePlan({ model }: { model: ModelSpec }) {
  return (
    <div className="cards">
      <article><span>Agentes</span><strong>{model.engines.agents}</strong></article>
      <article><span>Famílias</span><strong>{model.engines.households}</strong></article>
      <article><span>Financeiro</span><strong>{model.engines.financial}</strong></article>
      <article><span>Macro</span><strong>{model.engines.macro}</strong></article>
      <article><span>Acoplamento</span><strong>{model.engines.macro_coupling}</strong></article>
      <article><span>Re-solução</span><strong>{model.engines.macro_recalibration}</strong></article>
    </div>
  );
}

export function ModelBuilderWorkspace({ module, selectedTool, onApplyScenario, onOpenSimulation }: Props) {
  const [prompt, setPrompt] = useState(examplePrompt);
  const [draft, setDraft] = useState<ModelDraft | null>(null);
  const [status, setStatus] = useState("Pronto para montar um ModelSpec declarativo.");
  const [candidateText, setCandidateText] = useState("");

  async function build() {
    setStatus("Montando ModelSpec e validando contratos…");
    try {
      const value = await compileModel(prompt);
      setDraft(value);
      setCandidateText(JSON.stringify(value.model_spec, null, 2));
      setStatus("ModelSpec pronto para revisão. Nada foi executado no kernel.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Falha no Model Builder");
    }
  }

  async function validateCandidate() {
    setStatus("Validando JSON contra o contrato ModelSpec…");
    try {
      const raw = JSON.parse(candidateText) as Record<string, unknown>;
      const value = await validateModelSpecCandidate(raw);
      setDraft({
        provider: "external-json-validation",
        requires_review: true,
        recognized_changes: [],
        provider_assumptions: [],
        model_spec: value.model_spec,
        compiled_scenario: value.compiled_scenario,
        compilation: value.compilation
      });
      setStatus("ModelSpec válido. O cenário compilado continua aguardando revisão.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "ModelSpec inválido");
    }
  }

  const validatorMode = selectedTool === "model-validator";

  return (
    <section className="grid">
      <div className="panel controls">
        <h2>{validatorMode ? "Validador ModelSpec" : "Model Builder"}</h2>
        <p className="muted">{module.description}</p>

        {!validatorMode ? (
          <>
            <label>Descrição econômica</label>
            <textarea rows={10} value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            <button type="button" onClick={build}>Gerar ModelSpec</button>
            <p className="muted">Provider atual: <strong>safe-local-model-planner-v1.0</strong>. Provedores LLM futuros terão de devolver o mesmo contrato JSON.</p>
          </>
        ) : (
          <>
            <label>Candidate ModelSpec JSON</label>
            <textarea
              rows={18}
              value={candidateText}
              onChange={(event) => setCandidateText(event.target.value)}
              placeholder="Cole aqui um ModelSpec produzido por outro provedor/LLM."
            />
            <button type="button" onClick={validateCandidate}>Validar e compilar</button>
            <p className="muted">Campos executáveis e campos desconhecidos são rejeitados antes de qualquer compilação para ScenarioSpec.</p>
          </>
        )}
        <p className="warning">{status}</p>
      </div>

      <div className="panel results">
        <h2>Revisão do modelo</h2>
        {!draft ? <p className="muted">Nenhum ModelSpec gerado ainda.</p> : (
          <>
            <div className={`ledgerState ${draft.compilation.status === "full" ? "ok" : "bad"}`}>
              Compilação: {draft.compilation.status === "full" ? "suporte completo" : "suporte parcial — revisar lacunas"}
            </div>
            <h3>{draft.model_spec.name}</h3>
            <p>{draft.model_spec.description}</p>
            <div className="cards">
              <article><span>Horizonte</span><strong>{draft.model_spec.horizon_months} meses</strong></article>
              <article><span>Famílias</span><strong>{draft.model_spec.population.households.toLocaleString("pt-BR")}</strong></article>
              <article><span>Empresas</span><strong>{draft.model_spec.population.firms}</strong></article>
              <article><span>Bancos</span><strong>{draft.model_spec.population.banks}</strong></article>
              <article><span>Base econômica</span><strong>{draft.model_spec.traits.economic_base}</strong></article>
              <article><span>Desigualdade</span><strong>{draft.model_spec.traits.inequality}</strong></article>
            </div>

            <h3>Plano de motores</h3>
            <EnginePlan model={draft.model_spec} />

            {draft.recognized_changes.length > 0 && (
              <><h3>Interpretado do pedido</h3><ul>{draft.recognized_changes.map((item) => <li key={item}>{item}</li>)}</ul></>
            )}
            {draft.compilation.partial_features.length > 0 && (
              <><h3>Representação parcial</h3><ul>{draft.compilation.partial_features.map((item) => <li key={item}>{item}</li>)}</ul></>
            )}
            {draft.compilation.unsupported_features.length > 0 && (
              <><h3>Ainda não suportado</h3><ul>{draft.compilation.unsupported_features.map((item) => <li key={item}>{item}</li>)}</ul></>
            )}
            {draft.model_spec.assumptions.length > 0 && (
              <><h3>Hipóteses explícitas</h3><ul>{draft.model_spec.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></>
            )}

            <h3>ScenarioSpec compilado</h3>
            <p className="muted">Aplicar apenas leva a configuração para o Simulation Lab. A simulação ainda exige uma ação separada.</p>
            <div className="exportActions">
              <button type="button" onClick={() => { onApplyScenario(draft.compiled_scenario); onOpenSimulation(); }}>Aplicar ao Simulation Lab</button>
              <button type="button" className="secondaryButton" onClick={() => downloadJson("economy-lab-modelspec.json", draft.model_spec)}>Baixar ModelSpec JSON</button>
            </div>
            <p className="warning">{draft.compilation.warning}</p>
          </>
        )}
      </div>
    </section>
  );
}
