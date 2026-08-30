"""Reusable module profiles and Simulation Lab presets.

Profiles are resolved into ordinary ScenarioSpec fields before a simulation starts.
The kernel never dereferences a profile at runtime, which keeps saved scenarios
reproducible and lets Basic mode work with zero external dependencies.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from economy_lab.core.schemas import (
    DynareLabRequest,
    FinancialGuidancePoint,
    HarkLabRequest,
    MesaLabRequest,
    MesaComponentRequest,
    ScenarioSpec,
)

PROFILE_KINDS = {"macro", "financial", "agents", "households", "households_market", "firms", "labor_market"}


def build_lab_profile(*, module_id: str, inputs: dict[str, Any], outputs: dict[str, Any] | None = None) -> dict[str, Any]:
    module_id = module_id.strip().lower()
    payload: dict[str, Any] = {"inputs": deepcopy(inputs)}
    if outputs is not None:
        payload["outputs"] = deepcopy(outputs)

    if module_id == "dynare":
        validated = DynareLabRequest.model_validate(inputs)
        patch = {
            "macro_engine": "dynare",
            "dynare_monetary_shock_bp": validated.monetary_shock_bp,
            "dynare_irf_periods": validated.irf_periods,
            "dynare_neutral_nominal_rate": validated.neutral_nominal_rate,
            "dynare_beta": validated.beta,
            "dynare_sigma": validated.sigma,
            "dynare_kappa": validated.kappa,
            "dynare_rho_i": validated.rho_i,
            "dynare_phi_pi": validated.phi_pi,
            "dynare_phi_x": validated.phi_x,
        }
        return {
            "kind": "macro", "module_id": "dynare", "compatibility": "active",
            "payload": payload, "scenario_patch": patch,
        }

    if module_id == "mesa":
        if "component" not in inputs:
            MesaLabRequest.model_validate(inputs)
            return {
                "kind": "agents", "module_id": "mesa", "compatibility": "active",
                "payload": payload, "scenario_patch": {"activation_engine": "mesa"},
            }
        component = MesaComponentRequest.model_validate(inputs)
        common = {"activation_engine": "mesa"}
        if component.component == "activation":
            return {
                "kind": "agents", "module_id": "mesa", "compatibility": "active-component",
                "payload": payload, "scenario_patch": {**common, "mesa_activation_pattern": component.activation_pattern},
            }
        if component.component == "household_search":
            return {
                "kind": "households_market", "module_id": "mesa", "compatibility": "active-component",
                "payload": payload, "scenario_patch": {
                    **common,
                    "household_shopping_sample_size": component.shopping_sample_size,
                    "household_cheapest_choice_probability": component.cheapest_choice_probability,
                },
            }
        if component.component == "firm_behavior":
            return {
                "kind": "firms", "module_id": "mesa", "compatibility": "active-component",
                "payload": payload, "scenario_patch": {
                    **common,
                    "firm_price_adjustment_strength": component.price_adjustment_strength,
                    "firm_hiring_strength": component.hiring_strength,
                    "firm_layoff_strength": component.layoff_strength,
                },
            }
        return {
            "kind": "labor_market", "module_id": "mesa", "compatibility": "active-component",
            "payload": payload, "scenario_patch": {**common, "labor_matching_efficiency": component.matching_efficiency},
        }

    if module_id == "hark":
        validated = HarkLabRequest.model_validate(inputs)
        return {
            "kind": "households", "module_id": "hark", "compatibility": "active",
            "payload": payload, "scenario_patch": {
                "household_behavior": "hark",
                "hark_crra": validated.crra,
                "hark_annual_discount_factor": validated.annual_discount_factor,
                "hark_state_mode": "employment_income",
                "hark_unemployment_probability": validated.unemployment_probability,
                "hark_unemployment_replacement_rate": validated.unemployment_replacement_rate,
                "unemployment_benefits_enabled": True,
                "unemployment_benefit_replacement_rate": validated.unemployment_replacement_rate * 100.0,
                "hark_permanent_shock_std": validated.permanent_shock_std,
                "hark_transitory_shock_std": validated.transitory_shock_std,
                "hark_permanent_income_memory": validated.permanent_income_memory,
                "hark_income_groups": validated.income_groups,
                "hark_income_risk_dispersion": validated.income_risk_dispersion,
            },
        }

    if module_id == "minsky":
        # v1.7 supports an active *control profile*. Minsky may provide a
        # deterministic path of banking-control variables, but never raw ledger
        # balances. This preserves one accounting authority while still using
        # Minsky's dynamic-system output inside the Simulation Lab.
        raw_points = []
        if isinstance(outputs, dict) and isinstance(outputs.get("points"), list):
            raw_points = list(outputs["points"])
        elif isinstance(inputs.get("financial_controls"), dict):
            raw_points = [{"month": 1, **dict(inputs["financial_controls"])}]

        if raw_points:
            points = [FinancialGuidancePoint.model_validate(item) for item in raw_points]
            points = sorted(points, key=lambda item: item.month)
            first = points[0]
            patch = {
                "financial_engine": "minsky_profile",
                "minimum_bank_capital_ratio": first.minimum_bank_capital_ratio,
                "target_reserve_ratio": first.target_reserve_ratio,
                "bank_credit_supply_factor": first.credit_supply_factor,
                "default_writeoff_ratio": first.default_writeoff_ratio,
                "interbank_spread": first.interbank_spread,
                "central_bank_penalty_spread": first.central_bank_penalty_spread,
                "financial_guidance": [point.model_dump(mode="python") for point in points],
            }
            return {
                "kind": "financial", "module_id": "minsky",
                "compatibility": "active-path" if len(points) > 1 else "active-static",
                "payload": payload, "scenario_patch": patch,
            }

        # Legacy snapshots/introspection remain useful, but cannot influence the
        # simulator until explicit canonical controls are supplied.
        return {
            "kind": "financial", "module_id": "minsky", "compatibility": "assistive-only",
            "payload": payload, "scenario_patch": {},
        }

    raise ValueError(f"unsupported profile module: {module_id}")


def apply_profile_to_scenario(scenario: ScenarioSpec, profile: dict[str, Any]) -> tuple[ScenarioSpec, list[str]]:
    data = scenario.model_dump(mode="python")
    changes: list[str] = []
    for key, value in dict(profile.get("scenario_patch") or {}).items():
        if key not in ScenarioSpec.model_fields:
            raise ValueError(f"profile attempts to change unknown ScenarioSpec field: {key}")
        if key == "financial_guidance":
            value = [item for item in list(value or []) if int(item.get("month", 0)) <= int(data.get("months", 0))]
        before = data.get(key)
        data[key] = value
        if before != value:
            changes.append(f"{key}: {before} → {value}")

    applied = dict(data.get("applied_profiles") or {})
    kind = str(profile.get("kind") or "")
    profile_id = str(profile.get("id") or "transient")
    if kind in PROFILE_KINDS:
        applied[kind] = profile_id
    data["applied_profiles"] = applied
    return ScenarioSpec.model_validate(data), changes


def list_simulation_presets() -> list[dict[str, Any]]:
    return [
        {
            "id": "basic", "title": "Basic", "description": "Somente motores próprios do Economy Lab; não exige software externo.",
            "requirements": [],
            "patch": {
                "activation_engine": "native", "household_behavior": "heuristic", "macro_engine": "off",
                "financial_engine": "native", "bank_credit_supply_factor": 1.0, "default_writeoff_ratio": 35.0,
                "interbank_spread": 1.0, "central_bank_penalty_spread": 2.0, "financial_guidance": [],
                "macro_coupling": "advisory", "macro_recalibration": "static_irf", "applied_profiles": {},
            },
        },
        {
            "id": "intermediate", "title": "Intermediate", "description": "Mesa + HARK com SFC/bancos nativos e macro simplificada.",
            "requirements": ["mesa", "hark"],
            "patch": {
                "activation_engine": "mesa", "household_behavior": "hark", "macro_engine": "off",
                "macro_coupling": "advisory", "macro_recalibration": "static_irf",
            },
        },
        {
            "id": "macro-hybrid", "title": "Macro Hybrid", "description": "Dynare acoplado ao simulador; ABM/SFC realizados continuam autoritativos.",
            "requirements": ["dynare"],
            "patch": {
                "macro_engine": "dynare", "macro_coupling": "hybrid", "macro_recalibration": "quarterly",
            },
        },
        {
            "id": "full-current", "title": "Full atual", "description": "Mesa + HARK + Dynare; um Minsky Financial Profile ativo pode controlar crédito/liquidez sem substituir o ledger.",
            "requirements": ["mesa", "hark", "dynare"],
            "patch": {
                "activation_engine": "mesa", "household_behavior": "hark", "macro_engine": "dynare",
                "macro_coupling": "hybrid", "macro_recalibration": "quarterly",
            },
        },
        {
            "id": "custom", "title": "Custom", "description": "Mantém a configuração atual para composição manual por módulos e Profiles.",
            "requirements": [], "patch": {},
        },
    ]


def apply_preset(scenario: ScenarioSpec, preset_id: str) -> ScenarioSpec:
    preset = next((item for item in list_simulation_presets() if item["id"] == preset_id), None)
    if preset is None:
        raise KeyError(preset_id)
    data = scenario.model_dump(mode="python")
    data.update(deepcopy(preset["patch"]))
    return ScenarioSpec.model_validate(data)
