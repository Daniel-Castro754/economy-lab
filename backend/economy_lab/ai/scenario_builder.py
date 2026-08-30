"""Safe natural-language -> ScenarioSpec proposal compiler.

This module is intentionally provider-neutral. In v1.0 it includes a small,
deterministic Portuguese parser so the full validation contract works without
an API key. A future LLM provider must still emit a candidate ScenarioSpec and
pass the same Pydantic validation before simulation.
"""
from __future__ import annotations

import re
from copy import deepcopy

from economy_lab.core.schemas import EconomicShockSpec, ScenarioSpec


def _number(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", "."))


def _search_number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return _number(match.group(1)) if match else None


def _timing(text: str) -> tuple[int, int]:
    start = _search_number(r"(?:a partir do|no|m[eê]s)\s+(?:m[eê]s\s+)?(\d+)", text)
    duration = _search_number(r"por\s+(\d+)\s+mes(?:es)?", text)
    return int(start or 1), int(duration or 3)


def compile_scenario_prompt(
    prompt: str,
    base: ScenarioSpec | None = None,
) -> tuple[ScenarioSpec, list[str], list[str]]:
    if not prompt.strip():
        raise ValueError("prompt cannot be empty")
    source = base.model_dump(mode="python") if base is not None else ScenarioSpec().model_dump(mode="python")
    candidate = deepcopy(source)
    assumptions: list[str] = []
    changes: list[str] = []
    text = " ".join(prompt.strip().split())

    scalar_rules = [
        ("months", r"(?:simule|simular|horizonte(?: de)?|cen[aá]rio de)\s+(\d+)\s+mes(?:es)?", "meses"),
        ("households", r"([\d\.]+)\s+fam[ií]lias", "famílias"),
        ("firms", r"([\d\.]+)\s+empresas", "empresas"),
        ("banks", r"(\d+)\s+bancos", "bancos"),
        ("policy_rate", r"(?:selic|taxa de juros|juros)\s*(?:de|em|=)?\s*([\d\.,]+)\s*%", "juros"),
        ("income_tax", r"(?:imposto de renda|ir)\s*(?:de|em|=)?\s*([\d\.,]+)\s*%", "imposto de renda"),
    ]
    for field, pattern, label in scalar_rules:
        value = _search_number(pattern, text)
        if value is None:
            continue
        if field in {"months", "households", "firms", "banks"}:
            value = int(value)
        candidate[field] = value
        changes.append(f"{label}: {value}")

    lower = text.lower()
    if "mesa" in lower:
        candidate["activation_engine"] = "mesa"
        changes.append("ativação: Mesa")
    if "hark" in lower:
        candidate["household_behavior"] = "hark"
        changes.append("famílias: HARK")
    if "dynare" in lower:
        candidate["macro_engine"] = "dynare"
        changes.append("macro: Dynare")
    if "híbrido" in lower or "hibrido" in lower:
        candidate["macro_engine"] = "dynare"
        candidate["macro_coupling"] = "hybrid"
        changes.append("acoplamento: híbrido")
    if "trimestral" in lower and candidate.get("macro_coupling") == "hybrid":
        candidate["macro_recalibration"] = "quarterly"
        changes.append("Dynare: re-solução trimestral")

    shock_patterns = [
        ("fiscal_spending", r"(?:gasto p[uú]blico|choque fiscal)\s*([+\-]?\s*[\d\.,]+)\s*%", "gasto público"),
        ("productivity", r"produtividade\s*([+\-]?\s*[\d\.,]+)\s*%", "produtividade"),
        ("cost_push", r"(?:choque de custo|custos? de produ[cç][aã]o)\s*([+\-]?\s*[\d\.,]+)\s*%", "custos"),
        ("external_demand", r"(?:demanda externa|exporta[cç][oõ]es)\s*([+\-]?\s*[\d\.,]+)\s*%", "demanda externa"),
        ("import_cost", r"(?:custo de importa[cç][aã]o|importa[cç][oõ]es.*custo)\s*([+\-]?\s*[\d\.,]+)\s*%", "custo de importação"),
    ]
    shocks = list(candidate.get("shocks") or [])
    start, duration = _timing(text)
    for kind, pattern, label in shock_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        magnitude = _number(match.group(1).replace(" ", ""))
        shocks.append(
            EconomicShockSpec(
                kind=kind,
                start_month=start,
                duration_months=duration,
                magnitude_pct=magnitude,
                label=f"Compilado de linguagem natural: {label}",
            ).model_dump(mode="python")
        )
        changes.append(f"choque {label}: {magnitude:+g}% (mês {start}, {duration} meses)")
    candidate["shocks"] = shocks

    if shocks and "por " not in lower:
        assumptions.append("Choques sem duração explícita foram configurados por 3 meses.")
    if shocks and not re.search(r"(?:a partir do|no|m[eê]s)\s+(?:m[eê]s\s+)?\d+", lower):
        assumptions.append("Choques sem início explícito começam no mês 1.")
    assumptions.append("A proposta é apenas configuração; o compilador não altera código nem contas do ledger.")

    return ScenarioSpec.model_validate(candidate), assumptions, changes
