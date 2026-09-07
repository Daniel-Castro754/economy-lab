from fastapi.testclient import TestClient

from economy_lab.ai.scenario_builder import compile_scenario_prompt
from economy_lab.main import app


def test_local_scenario_compiler_creates_validated_shocks():
    spec, assumptions, changes = compile_scenario_prompt(
        "Simule 36 meses com 5000 famílias, 100 empresas e 3 bancos. "
        "Selic 12%. Produtividade +10% no mês 4 por 6 meses e demanda externa -15%."
    )
    assert spec.months == 36
    assert spec.policy_rate == 12
    assert spec.households == 5000
    assert len(spec.shocks) == 2
    assert spec.shocks[0].start_month == 4
    assert spec.shocks[0].duration_months == 6
    assert any("produtividade" in item for item in changes)
    assert assumptions


def test_shock_duration_does_not_override_horizon():
    spec, _, _ = compile_scenario_prompt(
        "Horizonte 24 meses. Produtividade +5% no mês 3 por 4 meses."
    )
    assert spec.months == 24
    assert spec.shocks[0].duration_months == 4


def test_scenario_compile_api_returns_reviewable_proposal():
    client = TestClient(app)
    response = client.post(
        "/api/v1/scenario/compile",
        json={"prompt": "Simular 18 meses, juros 9%, gasto público +20% no mês 2 por 3 meses"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_review"] is True
    assert payload["compiler"] == "safe-local-parser-v1.0"
    assert payload["spec"]["months"] == 18
    assert payload["spec"]["policy_rate"] == 9
    assert payload["spec"]["shocks"][0]["kind"] == "fiscal_spending"
