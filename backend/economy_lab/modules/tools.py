from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable

from .registry import get_module


@dataclass(frozen=True)
class HubTool:
    id: str
    module_id: str
    title: str
    description: str
    capability: str
    route: str | None = None
    output_kinds: tuple[str, ...] = ()
    status_provider: Callable[[], tuple[bool, str]] | None = None

    def status(self) -> dict[str, object]:
        module = get_module(self.module_id)
        available = bool(module and module.get("available", False))
        status = str(module.get("status", "unknown")) if module else "module-missing"
        if self.status_provider is not None:
            available, status = self.status_provider()
        return {
            **asdict(self),
            "output_kinds": list(self.output_kinds),
            "available": available,
            "status": status,
            "status_provider": None,
        }


_TOOLS: tuple[HubTool, ...] = (
    HubTool("simulation-simple", "simulation", "Simulação simples", "Modelo macro agregado de 7 anos com quatro decisões anuais, ambiente externo, aprovação e conversão para o modo detalhado.", "simple-macro", "/simple/start", ("annual-game", "charts", "csv", "xlsx")),
    HubTool("simulation-run", "simulation", "Simulação única", "Executa um ScenarioSpec no Economy Zero e retorna série temporal, SFC e indicadores.", "single-simulation", "/simulate", ("result", "charts", "csv", "xlsx")),
    HubTool("simulation-jobs", "simulation", "Fila de simulações", "Executa ScenarioSpec em uma fila persistente com progresso, cancelamento seguro e timeout.", "persistent-jobs", "/jobs/simulations", ("job", "progress", "result")),
    HubTool("simulation-replay", "simulation", "Manifesto e replay", "Verifica hashes de cenário, ambiente e resultado; reproduz uma execução imutável com linhagem explícita.", "verified-replay", "/runs/{id}/replay", ("manifest", "sha256", "verification")),
    HubTool("simulation-batch", "simulation", "Experimentos em lote", "Varia parâmetros e seeds para comparar cenários com estatísticas agregadas.", "batch-experiments", "/experiments/run", ("comparison", "charts", "csv", "xlsx")),
    HubTool("simulation-charts", "simulation", "Gráficos", "Visualiza séries temporais e comparações sem alterar o resultado armazenado.", "charts", None, ("svg",)),
    HubTool("simulation-export", "simulation", "Exportações", "Extrai resultados exatos para CSV e Excel com abas de auditoria.", "xlsx-export", "/exports/simulation.xlsx", ("csv", "xlsx")),
    HubTool("dynare-template", "dynare", "Gerador .mod", "Gera um modelo Novo-Keynesiano Dynare auditável sem executar código arbitrário.", "model-template", "/labs/dynare/template", ("mod", "text")),
    HubTool("dynare-irf", "dynare", "Executor de IRF", "Executa Dynare/Octave e retorna respostas impulso-resposta do modelo de referência.", "irf", "/labs/dynare/run", ("series", "chart", "csv")),
    HubTool("minsky-introspection", "minsky", "Introspecção REST", "Lista membros e assinaturas da árvore REST do Minsky.", "introspection", "/labs/minsky/command", ("json",)),
    HubTool("minsky-variables", "minsky", "Variáveis", "Lê e escreve variáveis explicitamente mapeadas no modelo Minsky conectado.", "model-sync", "/labs/minsky/command", ("json",)),
    HubTool("minsky-runtime", "minsky", "Step / Reset", "Avança ou reinicia o modelo Minsky conectado sem tocar no ledger do Simulation Lab.", "financial-dynamics", "/labs/minsky/command", ("json",)),
    HubTool("minsky-financial-controller", "minsky", "Controlador financeiro", "Captura uma trajetória de controles bancários explicitamente mapeados e reutiliza como Financial Profile ativo no Simulation Lab.", "active-financial-profile", "/labs/minsky/financial/run", ("series", "profile", "chart", "csv")),
    HubTool("minsky-godley-reconciliation", "minsky", "Reconciliação Godley", "Compara células de um template .mky conhecido com o Ledger/SFC por mapeamento explícito e sem permitir escrita de saldos externos.", "read-only-godley-reconciliation", "/minsky/reconcile", ("json", "reconciliation-report", "sha256-evidence")),
    HubTool("mesa-wealth", "mesa", "Wealth Exchange", "Executa um ABM standalone de troca de riqueza para explorar ativação e emergência.", "wealth-exchange-demo", "/labs/mesa/run", ("series", "chart", "csv")),
    HubTool("mesa-components", "mesa", "Componentes Mesa", "Testa e salva componentes intercambiáveis de ativação, busca das famílias, firmas e mercado de trabalho.", "component-profiles", "/labs/mesa/component/run", ("series", "chart", "profile")),
    HubTool("hark-policy", "hark", "Política de consumo e renda", "Resolve c(m) por grupos de renda e sincroniza risco de desemprego, renda permanente/transitória e preferências em Household Profiles.", "policy-curve", "/labs/hark/run", ("table", "chart", "csv", "profile")),
    HubTool("data-fetch", "data-calibration", "Buscar série pública", "Consulta e normaliza BCB/SGS, IBGE/SIDRA, World Bank ou Ipeadata em um EconomicSeries comum.", "public-data", "/data/fetch", ("series", "table", "json")),
    HubTool("data-calibrate", "data-calibration", "Avaliar calibração", "Compara momentos explícitos entre séries reais e o resultado do Simulation Lab, sem estimar parâmetros estruturais automaticamente.", "calibration-targets", "/calibration/evaluate", ("score", "table", "xlsx")),
    HubTool("validation-external", "validation", "Qualificar motores externos", "Executa detecção, smoke e integração real; registra versões, evidências e hash do relatório, diferenciando ausência de falha.", "external-validation", "/validation/external-engines", ("json", "compatibility-report")),
    HubTool("analytics-compare", "analytics", "Comparador", "Agrega experimentos e compara resultados por parâmetro e seed.", "comparison", None, ("table", "chart")),
    HubTool("analytics-sql", "analytics", "Consulta analítica", "Reserva a camada DuckDB/SQL para análise de grandes conjuntos de execuções.", "duckdb", None, ("table",)),
    HubTool("scenario-compiler", "scenario-ai", "Compilador de cenário", "Converte texto em ScenarioSpec proposto e validado para revisão humana.", "natural-language-scenarios", "/scenario/compile", ("scenario-spec",)),
    HubTool("model-builder", "scenario-ai", "Model Builder", "Converte uma descrição econômica em ModelSpec declarativo, mostra lacunas e compila somente campos suportados para ScenarioSpec.", "model-spec", "/model/compile", ("model-spec", "scenario-spec", "validation-report")),
    HubTool("model-validator", "scenario-ai", "Validador ModelSpec", "Valida JSON vindo de qualquer provedor/LLM e rejeita campos executáveis ou fora do contrato antes de compilar para o simulador.", "validation", "/model/validate", ("model-spec", "validation-report")),
)


def list_tools(module_id: str | None = None) -> list[dict[str, object]]:
    tools = _TOOLS if module_id is None else tuple(tool for tool in _TOOLS if tool.module_id == module_id)
    return [tool.status() for tool in tools]


def get_tool(tool_id: str) -> dict[str, object] | None:
    for tool in _TOOLS:
        if tool.id == tool_id:
            return tool.status()
    return None
