from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable

from economy_lab.engines.dynare_adapter import dynare_status
from economy_lab.engines.hark_adapter import hark_available
from economy_lab.engines.mesa_adapter import mesa_available
from economy_lab.engines.minsky_adapter import bridge_status


@dataclass(frozen=True)
class HubModule:
    id: str
    title: str
    kind: str
    description: str
    capabilities: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    status_provider: Callable[[], tuple[bool, str]] | None = None
    routes: tuple[str, ...] = ()

    def status(self) -> dict[str, object]:
        available = True
        status = "ready"
        if self.status_provider is not None:
            available, status = self.status_provider()
        return {
            **asdict(self),
            "capabilities": list(self.capabilities),
            "dependencies": list(self.dependencies),
            "routes": list(self.routes),
            "available": bool(available),
            "status": status,
            "status_provider": None,
        }


def _dynare_status() -> tuple[bool, str]:
    value = dynare_status()
    if value.ready:
        suffix = f" {value.dynare_version_hint}" if value.dynare_version_hint else ""
        return True, f"ready{suffix}"
    if value.configured:
        return False, value.error or "configured-offline"
    return False, "not-configured"


def _minsky_status() -> tuple[bool, str]:
    value = bridge_status()
    if value.reachable:
        return True, "connected"
    if value.configured:
        return False, value.error or "configured-offline"
    return False, "not-configured"


def _mesa_status() -> tuple[bool, str]:
    ok = mesa_available()
    return ok, "ready" if ok else "not-installed"


def _hark_status() -> tuple[bool, str]:
    ok = hark_available()
    return ok, "ready" if ok else "not-installed"


def _analytics_status() -> tuple[bool, str]:
    try:
        import duckdb  # type: ignore  # noqa: F401
        return True, "duckdb-ready"
    except Exception:
        return True, "python-statistics"


_MODULES: tuple[HubModule, ...] = (
    HubModule(
        id="simulation",
        title="Simulation Lab",
        kind="builtin",
        description="Executa cenários ABM/SFC, choques, lotes, gráficos e exportações auditáveis.",
        capabilities=(
            "simple-macro", "single-simulation", "batch-experiments", "scenario-shocks", "charts",
            "productive-capital", "business-investment", "household-credit", "bank-resolution",
            "unemployment-benefits", "labor-supply", "job-transitions", "seven-year-policy-game",
            "csv-export", "xlsx-export", "project-history",
            "persistent-jobs", "job-progress", "job-cancellation", "job-timeouts",
            "run-manifests", "experiment-hashes", "verified-replay",
        ),
        routes=("/simple/start", "/simple/step", "/simple/run", "/simulate", "/jobs/simulations", "/jobs/{id}", "/runs/{id}/manifest", "/runs/{id}/replay", "/experiments/run", "/exports/simple.xlsx", "/exports/simulation.xlsx", "/exports/batch.xlsx"),
    ),
    HubModule(
        id="dynare",
        title="Dynare Lab",
        kind="external-software",
        description="Motor DSGE/Novo-Keynesiano, IRFs e re-solução macro trimestral via GNU Octave.",
        capabilities=("dsge", "irf", "monetary-policy", "macro-recalibration", "hybrid-coupling", "standalone-lab", "model-template"),
        dependencies=("Dynare", "GNU Octave"),
        status_provider=_dynare_status,
        routes=("/dynare/status", "/labs/dynare/template", "/labs/dynare/run"),
    ),
    HubModule(
        id="minsky",
        title="Minsky Lab",
        kind="external-software",
        description="Integração SFC/Godley, dinâmica financeira e sincronização REST com modelos .mky.",
        capabilities=("godley", "sfc", "rest-bridge", "model-sync", "financial-dynamics", "standalone-lab", "introspection", "active-financial-profile", "read-only-godley-reconciliation", "template-sha256-verification"),
        dependencies=("Minsky REST"),
        status_provider=_minsky_status,
        routes=("/minsky/status", "/minsky/export", "/minsky/reconcile", "/labs/minsky/command", "/labs/minsky/financial/run"),
    ),
    HubModule(
        id="mesa",
        title="Mesa Lab",
        kind="python-framework",
        description="Ativação e infraestrutura de agentes para famílias, empresas e outros agentes ABM.",
        capabilities=("agent-activation", "agentsets", "abm", "reproducible-randomness", "standalone-lab", "wealth-exchange-demo", "component-profiles", "household-search", "firm-behavior", "labor-matching"),
        dependencies=("Mesa 3.5.x"),
        status_provider=_mesa_status,
        routes=("/labs/mesa/run", "/labs/mesa/component/run"),
    ),
    HubModule(
        id="hark",
        title="HARK Lab / Econ-ARK",
        kind="python-framework",
        description="Decisões intertemporais e heterogeneidade microeconômica de consumo/poupança.",
        capabilities=("household-optimization", "consumption-saving", "heterogeneous-agents", "employment-income-state", "income-groups", "unemployment-risk", "benefit-income", "job-separation-risk", "standalone-lab", "policy-curve"),
        dependencies=("Econ-ARK HARK",),
        status_provider=_hark_status,
        routes=("/labs/hark/run",),
    ),
    HubModule(
        id="data-calibration",
        title="Data & Calibration",
        kind="builtin",
        description="Normaliza séries públicas, alinha frequências, combina metas e executa calibração quantitativa limitada com validação fora da amostra.",
        capabilities=("public-data", "bcb-sgs", "ibge-sidra", "world-bank", "ipeadata", "calibration-targets", "frequency-alignment", "bounded-fit", "train-validation", "calibration-report"),
        routes=("/data/catalog", "/data/fetch", "/calibration/evaluate", "/calibration/fit", "/exports/calibration.xlsx"),
    ),
    HubModule(
        id="validation",
        title="Engine Diagnostics",
        kind="builtin",
        description="Executa smoke tests reais e registra compatibilidade de Mesa, HARK, Dynare/Octave e Minsky REST.",
        capabilities=("external-qualification", "runtime-smoke-tests", "economy-zero-integration-smoke", "version-report", "sha256-evidence", "compatibility-report"),
        routes=("/validation/external-engines",),
    ),
    HubModule(
        id="analytics",
        title="Analytics",
        kind="builtin",
        description="Agregação de experimentos, estatísticas e camada analítica opcional com DuckDB.",
        capabilities=("aggregation", "comparison", "duckdb", "statistics"),
        dependencies=("DuckDB optional"),
        status_provider=_analytics_status,
    ),
    HubModule(
        id="scenario-ai",
        title="Scenario AI",
        kind="builtin",
        description="Compila linguagem natural em ScenarioSpec e ModelSpec declarativo, sempre com validação/revisão antes do kernel.",
        capabilities=("natural-language-scenarios", "model-spec", "provider-abstraction", "validation", "review-before-apply", "no-code-execution"),
        routes=("/scenario/compile", "/model/providers", "/model/compile", "/model/validate", "/model/to-scenario"),
    ),
)


def list_modules() -> list[dict[str, object]]:
    return [module.status() for module in _MODULES]


def get_module(module_id: str) -> dict[str, object] | None:
    for module in _MODULES:
        if module.id == module_id:
            return module.status()
    return None
