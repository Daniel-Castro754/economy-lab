"""Safe natural-language -> ModelSpec -> ScenarioSpec pipeline.

The AI/provider layer is deliberately separated from the economic kernel.
Providers may only propose JSON-compatible ModelSpec candidates. Candidates
are validated with strict Pydantic schemas and compiled through an explicit
mapping before a ScenarioSpec can reach the simulation engine.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Protocol

from economy_lab.core.schemas import (
    EconomicShockSpec,
    ModelCompilationReport,
    ModelEnginePlan,
    ModelMarketPlan,
    ModelPolicySpec,
    ModelPopulationSpec,
    ModelSpec,
    ModelTraitSpec,
    ScenarioSpec,
)

_FORBIDDEN_PROVIDER_KEYS = {
    "code", "python", "python_code", "script", "shell", "command",
    "commands", "sql", "mod_source", "dynare_code", "javascript",
    "executable", "subprocess",
}


@dataclass(frozen=True)
class ProviderProposal:
    provider: str
    candidate: dict[str, Any]
    assumptions: tuple[str, ...] = ()
    recognized: tuple[str, ...] = ()


class ModelCandidateProvider(Protocol):
    id: str

    def propose(self, prompt: str, base: ModelSpec | None = None) -> ProviderProposal: ...


def _number(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", "."))


def _search_number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return _number(match.group(1)) if match else None


def _assert_no_executable_fields(value: Any, path: str = "candidate") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _FORBIDDEN_PROVIDER_KEYS:
                raise ValueError(f"ModelSpec candidate contains forbidden executable field: {path}.{key}")
            _assert_no_executable_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_executable_fields(child, f"{path}[{index}]")


def validate_model_candidate(candidate: dict[str, Any]) -> ModelSpec:
    _assert_no_executable_fields(candidate)
    return ModelSpec.model_validate(candidate)


class LocalRuleModelProvider:
    """Deterministic Portuguese model planner used without an external LLM."""

    id = "safe-local-model-planner-v1.0"

    def propose(self, prompt: str, base: ModelSpec | None = None) -> ProviderProposal:
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        source = base.model_dump(mode="python") if base else ModelSpec().model_dump(mode="python")
        candidate = deepcopy(source)
        text = " ".join(prompt.strip().split())
        lower = text.lower()
        recognized: list[str] = []
        assumptions: list[str] = []

        candidate["description"] = text[:500]
        candidate["source_prompt"] = text[:4000]

        months = _search_number(r"(?:simule|simular|horizonte(?: de)?|por)\s+(\d+)\s+mes", text)
        households = _search_number(r"([\d\.]+)\s+fam[ií]lias", text)
        firms = _search_number(r"([\d\.]+)\s+empresas", text)
        banks = _search_number(r"(\d+)\s+bancos", text)
        if months is not None:
            candidate["horizon_months"] = int(months); recognized.append(f"horizonte: {int(months)} meses")
        if households is not None:
            candidate["population"]["households"] = int(households); recognized.append(f"famílias: {int(households)}")
        if firms is not None:
            candidate["population"]["firms"] = int(firms); recognized.append(f"empresas: {int(firms)}")
        if banks is not None:
            candidate["population"]["banks"] = int(banks); recognized.append(f"bancos: {int(banks)}")

        rate = _search_number(r"(?:selic|taxa de juros|juros)\s*(?:de|em|=)?\s*([\d\.,]+)\s*%", text)
        inflation = _search_number(r"infla[cç][aã]o\s*(?:de|em|=)?\s*([\d\.,]+)\s*%", text)
        unemployment = _search_number(r"desemprego\s*(?:de|em|=)?\s*([\d\.,]+)\s*%", text)
        income_tax = _search_number(r"(?:imposto de renda|ir)\s*(?:de|em|=)?\s*([\d\.,]+)\s*%", text)
        if rate is not None:
            candidate["policy"]["policy_rate"] = rate; recognized.append(f"juros: {rate:g}%")
        if inflation is not None:
            candidate["policy"]["inflation"] = inflation; recognized.append(f"inflação inicial: {inflation:g}%")
        if unemployment is not None:
            candidate["policy"]["unemployment"] = unemployment; recognized.append(f"desemprego inicial: {unemployment:g}%")
        if income_tax is not None:
            candidate["policy"]["income_tax"] = income_tax; recognized.append(f"IR: {income_tax:g}%")

        traits = candidate["traits"]
        if any(term in lower for term in ("commodit", "exportadora de commodities", "exportador de commodities")):
            traits["economic_base"] = "commodity_exporter"
            traits["openness"] = "high"
            candidate["markets"]["external"] = True
            candidate["requested_capabilities"].append("commodity-sector")
            recognized.append("estrutura: exportadora de commodities")
            assumptions.append("O setor externo existe, mas a especialização setorial em commodities ainda é descritiva no ModelSpec.")
        elif "industrial" in lower:
            traits["economic_base"] = "industrial"; recognized.append("estrutura: industrial")
        elif "servi" in lower and "econom" in lower:
            traits["economic_base"] = "services"; recognized.append("estrutura: serviços")

        if "alta desigualdade" in lower or "desigualdade elevada" in lower:
            traits["inequality"] = "high"
            candidate["engines"]["households"] = "hark"
            candidate["hark_income_groups"] = 5
            candidate["hark_income_risk_dispersion"] = 0.55
            candidate["recommended_modules"].append("hark")
            recognized.append("desigualdade: alta")
            assumptions.append("Alta desigualdade é aproximada por maior heterogeneidade de risco/renda; a distribuição empírica ainda exige calibração.")
        elif "baixa desigualdade" in lower:
            traits["inequality"] = "low"
            candidate["hark_income_risk_dispersion"] = 0.15
            recognized.append("desigualdade: baixa")

        if "sistema bancário concentrado" in lower or "sistema bancario concentrado" in lower or "bancos concentrados" in lower:
            traits["banking_concentration"] = "high"
            if banks is None:
                candidate["population"]["banks"] = 3
                assumptions.append("Concentração bancária alta foi aproximada por 3 bancos quando nenhum número foi informado.")
            candidate["recommended_modules"].append("minsky")
            recognized.append("concentração bancária: alta")
        elif "bancário pulverizado" in lower or "bancario pulverizado" in lower:
            traits["banking_concentration"] = "low"
            if banks is None:
                candidate["population"]["banks"] = 10
            recognized.append("concentração bancária: baixa")

        if "mesa" in lower:
            candidate["engines"]["agents"] = "mesa"; candidate["recommended_modules"].append("mesa"); recognized.append("agentes: Mesa")
        if "hark" in lower:
            candidate["engines"]["households"] = "hark"; candidate["recommended_modules"].append("hark"); recognized.append("famílias: HARK")
        if "minsky" in lower:
            candidate["engines"]["financial"] = "minsky_profile"; candidate["recommended_modules"].append("minsky"); recognized.append("financeiro: Minsky Profile")
        if "dynare" in lower or "dsge" in lower:
            candidate["engines"]["macro"] = "dynare"; candidate["recommended_modules"].append("dynare"); recognized.append("macro: Dynare")
        if "híbrido" in lower or "hibrido" in lower:
            candidate["engines"]["macro"] = "dynare"
            candidate["engines"]["macro_coupling"] = "hybrid"
            candidate["recommended_modules"].append("dynare")
            recognized.append("macro: acoplamento híbrido")
        if "re-solução trimestral" in lower or "resolução trimestral" in lower or "recalibração trimestral" in lower:
            candidate["engines"]["macro"] = "dynare"
            candidate["engines"]["macro_coupling"] = "hybrid"
            candidate["engines"]["macro_recalibration"] = "quarterly"
            recognized.append("macro: re-solução trimestral")

        if "sem crédito às famílias" in lower or "sem credito as familias" in lower:
            candidate["household_credit"] = False
            recognized.append("crédito às famílias: desativado")
        elif "crédito às famílias" in lower or "credito as familias" in lower or "crédito familiar" in lower:
            candidate["household_credit"] = True
            recognized.append("crédito às famílias: ativado")
        if "sem capital produtivo" in lower:
            candidate["productive_capital"] = False
            recognized.append("capital produtivo: desativado")
        elif "capital produtivo" in lower or "investimento empresarial" in lower:
            candidate["productive_capital"] = True
            recognized.append("capital produtivo: ativado")
        if "sem seguro-desemprego" in lower or "sem seguro desemprego" in lower or "sem benefício de desemprego" in lower:
            candidate["unemployment_benefits"] = False
            recognized.append("seguro-desemprego: desligado")
        elif "seguro-desemprego" in lower or "seguro desemprego" in lower or "benefício de desemprego" in lower:
            candidate["unemployment_benefits"] = True
            recognized.append("seguro-desemprego: ativo")
            replacement = _search_number(r"(?:reposi[cç][aã]o|benef[ií]cio)(?:\s+de)?\s*([\d\.,]+)\s*%", text)
            if replacement is not None:
                candidate["unemployment_benefit_replacement_rate"] = replacement
                recognized.append(f"reposição do benefício: {replacement:g}%")
        if "oferta de trabalho inelástica" in lower or "oferta de trabalho inelastica" in lower:
            candidate["labor_supply_mode"] = "inelastic"
            recognized.append("oferta de trabalho: inelástica")
        elif "salário de reserva" in lower or "salario de reserva" in lower or "oferta de trabalho" in lower:
            candidate["labor_supply_mode"] = "reservation_wage"
            recognized.append("oferta de trabalho: salário de reserva")

        if "bail-in" in lower or "bail in" in lower:
            candidate["bank_resolution_mode"] = "bail_in"
            recognized.append("resolução bancária: bail-in")
        elif "recapitalização pública" in lower or "recapitalizacao publica" in lower:
            candidate["bank_resolution_mode"] = "government_recapitalization"
            recognized.append("resolução bancária: recapitalização pública")

        # Simple shock extraction reuses the same explicit shock contract as ScenarioSpec.
        start_match = re.search(r"(?:no|m[eê]s|a partir do m[eê]s)\s+(\d+)", lower)
        duration_match = re.search(r"por\s+(\d+)\s+mes", lower)
        start = int(start_match.group(1)) if start_match else 1
        duration = int(duration_match.group(1)) if duration_match else 3
        shock_patterns = (
            ("fiscal_spending", r"(?:gasto p[uú]blico|choque fiscal)\s*([+\-]?\s*[\d\.,]+)\s*%", "gasto público"),
            ("productivity", r"produtividade\s*([+\-]?\s*[\d\.,]+)\s*%", "produtividade"),
            ("cost_push", r"(?:choque de custo|custos? de produ[cç][aã]o)\s*([+\-]?\s*[\d\.,]+)\s*%", "custos"),
            ("external_demand", r"(?:demanda externa|exporta[cç][oõ]es)\s*([+\-]?\s*[\d\.,]+)\s*%", "demanda externa"),
            ("import_cost", r"(?:custo de importa[cç][aã]o|custo das importa[cç][oõ]es)\s*([+\-]?\s*[\d\.,]+)\s*%", "custo de importação"),
        )
        shocks = list(candidate.get("shocks", []))
        for kind, pattern, label in shock_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            magnitude = _number(match.group(1).replace(" ", ""))
            shocks.append(EconomicShockSpec(kind=kind, start_month=start, duration_months=duration, magnitude_pct=magnitude, label=f"ModelSpec: {label}").model_dump(mode="python"))
            recognized.append(f"choque {label}: {magnitude:+g}%")
        candidate["shocks"] = shocks

        candidate["recommended_modules"] = sorted(set(candidate["recommended_modules"]))
        candidate["requested_capabilities"] = sorted(set(candidate["requested_capabilities"]))
        if not recognized:
            assumptions.append("Nenhuma característica quantitativa explícita foi reconhecida; os defaults auditáveis do Economy Zero foram mantidos.")
        assumptions.append("A proposta é um ModelSpec declarativo. Nenhum código, comando de shell ou transação contábil é gerado pela IA.")
        candidate["assumptions"] = list(dict.fromkeys([*candidate.get("assumptions", []), *assumptions]))
        return ProviderProposal(self.id, candidate, tuple(assumptions), tuple(recognized))


def compile_model_to_scenario(model: ModelSpec, base: ScenarioSpec | None = None) -> tuple[ScenarioSpec, ModelCompilationReport]:
    raw = base.model_dump(mode="python") if base else ScenarioSpec().model_dump(mode="python")
    applied: list[str] = []
    partial: list[str] = []
    unsupported: list[str] = []

    mappings = {
        "name": model.name,
        "months": model.horizon_months,
        "households": model.population.households,
        "firms": model.population.firms,
        "banks": model.population.banks,
        "initial_inflation": model.policy.inflation,
        "initial_unemployment": model.policy.unemployment,
        "policy_rate": model.policy.policy_rate,
        "income_tax": model.policy.income_tax,
        "public_spending_change": model.policy.public_spending_change,
        "activation_engine": model.engines.agents,
        "household_behavior": model.engines.households,
        "financial_engine": model.engines.financial,
        "macro_engine": model.engines.macro,
        "macro_coupling": model.engines.macro_coupling,
        "macro_recalibration": model.engines.macro_recalibration,
        "hark_income_groups": model.hark_income_groups,
        "hark_income_risk_dispersion": model.hark_income_risk_dispersion,
        "household_credit_enabled": model.household_credit,
        "unemployment_benefits_enabled": model.unemployment_benefits,
        "unemployment_benefit_replacement_rate": model.unemployment_benefit_replacement_rate,
        "labor_supply_mode": model.labor_supply_mode,
        "bank_resolution_mode": model.bank_resolution_mode,
        "shocks": [shock.model_dump(mode="python") for shock in model.shocks],
        "applied_profiles": dict(model.profile_refs),
    }
    for key, value in mappings.items():
        raw[key] = value
        applied.append(key)

    if not model.productive_capital:
        raw["firm_investment_propensity"] = 0.0
        raw["capital_output_elasticity"] = 0.0
        applied.extend(["firm_investment_propensity", "capital_output_elasticity"])
    if model.engines.macro == "off":
        raw["macro_coupling"] = "advisory"
        raw["macro_recalibration"] = "static_irf"
    disabled_markets = [name for name, enabled in model.markets.model_dump(mode="python").items() if not enabled]
    if disabled_markets:
        partial.append("Desativação de mercados ainda não é compilada no Economy Zero; mercados mantidos ativos: " + ", ".join(disabled_markets) + ".")
    if model.engines.financial == "minsky_profile" and not raw.get("financial_guidance"):
        # Static Minsky mode is valid; the explicit profile is attached later through Profiles.
        partial.append("Minsky foi selecionado, mas nenhum Financial Profile foi anexado; o cenário usa os controles estáticos atuais até revisão.")
    if model.traits.economic_base in {"commodity_exporter", "industrial", "services"}:
        partial.append(f"A base econômica '{model.traits.economic_base}' é descritiva; o Economy Zero ainda não possui matriz setorial completa.")
    if model.traits.inequality != "medium":
        partial.append("O nível de desigualdade é aproximado por heterogeneidade HARK; a distribuição-alvo deve ser calibrada com dados reais.")
    if model.traits.banking_concentration != "medium":
        partial.append("Concentração bancária é aproximada pelo número de bancos; participação de mercado endógena ainda não está modelada.")
    for capability in model.requested_capabilities:
        if capability == "commodity-sector":
            unsupported.append("commodity-sector: requer setores produtivos explícitos, previsto para etapa posterior.")

    scenario = ScenarioSpec.model_validate(raw)
    report = ModelCompilationReport(
        status="partial" if partial or unsupported else "full",
        applied_fields=applied,
        partial_features=partial,
        unsupported_features=unsupported,
        assumptions=list(model.assumptions),
        warning="ModelSpec compila somente para contratos conhecidos. Recursos parciais permanecem explícitos e exigem revisão antes da simulação.",
    )
    return scenario, report


def build_model_from_prompt(prompt: str, base: ModelSpec | None = None, provider: ModelCandidateProvider | None = None) -> tuple[ModelSpec, ScenarioSpec, ModelCompilationReport, ProviderProposal]:
    selected = provider or LocalRuleModelProvider()
    proposal = selected.propose(prompt, base)
    model = validate_model_candidate(proposal.candidate)
    scenario, report = compile_model_to_scenario(model)
    return model, scenario, report, proposal


def model_provider_catalog() -> list[dict[str, object]]:
    return [
        {
            "id": LocalRuleModelProvider.id,
            "title": "Local deterministic planner",
            "kind": "local",
            "available": True,
            "requires_network": False,
            "status": "ready",
        }
    ]
