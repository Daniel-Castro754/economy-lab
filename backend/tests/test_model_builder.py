from fastapi.testclient import TestClient
import pytest

from economy_lab.ai.model_builder import (
    build_model_from_prompt,
    compile_model_to_scenario,
    validate_model_candidate,
)
from economy_lab.core.schemas import ModelSpec
from economy_lab.main import app


def test_model_builder_creates_structured_partial_model():
    model, scenario, report, proposal = build_model_from_prompt(
        "Crie uma economia exportadora de commodities, com alta desigualdade e sistema bancário concentrado. "
        "Simule 36 meses com 8000 famílias e 140 empresas, inflação 5%, desemprego 8% e Selic 12%."
    )
    assert model.horizon_months == 36
    assert model.population.households == 8000
    assert model.population.firms == 140
    assert model.population.banks == 3
    assert model.traits.economic_base == "commodity_exporter"
    assert model.traits.inequality == "high"
    assert model.traits.banking_concentration == "high"
    assert model.engines.households == "hark"
    assert "hark" in model.recommended_modules
    assert "minsky" in model.recommended_modules
    assert scenario.months == 36
    assert scenario.initial_inflation == 5
    assert scenario.initial_unemployment == 8
    assert scenario.policy_rate == 12
    assert scenario.household_behavior == "hark"
    assert report.status == "partial"
    assert any("commod" in item.lower() for item in report.unsupported_features)
    assert proposal.provider == "safe-local-model-planner-v1.0"


def test_model_builder_explicit_engines_and_quarterly_macro():
    model, scenario, report, _ = build_model_from_prompt(
        "Use Mesa, HARK, Minsky e Dynare em modo híbrido com re-solução trimestral. Simule 24 meses."
    )
    assert model.engines.agents == "mesa"
    assert model.engines.households == "hark"
    assert model.engines.financial == "minsky_profile"
    assert model.engines.macro == "dynare"
    assert model.engines.macro_coupling == "hybrid"
    assert model.engines.macro_recalibration == "quarterly"
    assert scenario.activation_engine == "mesa"
    assert scenario.household_behavior == "hark"
    assert scenario.financial_engine == "minsky_profile"
    assert scenario.macro_engine == "dynare"
    assert scenario.macro_recalibration == "quarterly"
    assert any("Financial Profile" in item or "Minsky" in item for item in report.partial_features)


def test_model_candidate_rejects_executable_fields():
    candidate = ModelSpec().model_dump(mode="python")
    candidate["python_code"] = "import os; os.system('echo bad')"
    with pytest.raises(ValueError, match="forbidden executable field"):
        validate_model_candidate(candidate)


def test_model_candidate_forbids_unknown_nested_fields():
    candidate = ModelSpec().model_dump(mode="python")
    candidate["policy"]["magic_parameter"] = 123
    with pytest.raises(ValueError):
        validate_model_candidate(candidate)


def test_model_to_scenario_respects_base_but_model_has_authority_on_mapped_fields():
    model = ModelSpec(horizon_months=18)
    scenario, report = compile_model_to_scenario(model)
    assert scenario.months == 18
    assert scenario.households == model.population.households
    assert report.status == "full"


def test_model_compile_api_returns_reviewable_contract():
    client = TestClient(app)
    response = client.post(
        "/api/v1/model/compile",
        json={"prompt": "Economia com alta desigualdade, 6000 famílias, 120 empresas e 4 bancos por 30 meses."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_review"] is True
    assert payload["provider"] == "safe-local-model-planner-v1.0"
    assert payload["model_spec"]["population"]["households"] == 6000
    assert payload["compiled_scenario"]["months"] == 30
    assert payload["compilation"]["status"] == "partial"


def test_model_validate_api_rejects_code_payload():
    client = TestClient(app)
    candidate = ModelSpec().model_dump(mode="json")
    candidate["script"] = "rm -rf /"
    response = client.post("/api/v1/model/validate", json={"candidate": candidate})
    assert response.status_code == 422
    assert "forbidden executable field" in response.text


def test_model_to_scenario_api_compiles_edited_model():
    client = TestClient(app)
    model = ModelSpec(name="Edited", horizon_months=12).model_dump(mode="json")
    response = client.post("/api/v1/model/to-scenario", json={"model_spec": model})
    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"]["name"] == "Edited"
    assert payload["scenario"]["months"] == 12


def test_model_provider_catalog_exposes_only_safe_local_provider_in_v22():
    client = TestClient(app)
    response = client.get("/api/v1/model/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload == [{
        "id": "safe-local-model-planner-v1.0",
        "title": "Local deterministic planner",
        "kind": "local",
        "available": True,
        "requires_network": False,
        "status": "ready",
    }]


def test_modelspec_compiles_capital_household_credit_and_bail_in():
    from economy_lab.ai.model_builder import build_model_from_prompt
    model, scenario, report, _ = build_model_from_prompt(
        "Economia com capital produtivo, crédito às famílias e resolução por bail-in por 24 meses"
    )
    assert model.productive_capital is True
    assert model.household_credit is True
    assert model.bank_resolution_mode == "bail_in"
    assert scenario.household_credit_enabled is True
    assert scenario.bank_resolution_mode == "bail_in"
    assert report.status in {"full", "partial"}


def test_modelspec_compiles_unemployment_benefits_and_labor_supply():
    model, scenario, report, _ = build_model_from_prompt(
        "Economia com seguro-desemprego, reposição 55% e oferta de trabalho com salário de reserva por 18 meses"
    )
    assert model.unemployment_benefits is True
    assert model.unemployment_benefit_replacement_rate == 55
    assert model.labor_supply_mode == "reservation_wage"
    assert scenario.unemployment_benefits_enabled is True
    assert scenario.unemployment_benefit_replacement_rate == 55
    assert scenario.labor_supply_mode == "reservation_wage"
    assert report.status in {"full", "partial"}
