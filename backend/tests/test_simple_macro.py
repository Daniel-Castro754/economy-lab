from fastapi.testclient import TestClient

from economy_lab.main import app
from economy_lab.simple import (
    SimpleInitialConfig, SimplePolicyDecision, SimpleRunRequest, SimpleStepRequest,
    initial_state, run_simple, simple_to_advanced, step_simple,
)
from economy_lab.simple.models import SimpleToAdvancedRequest
from economy_lab.reporting import simple_csv_bytes, simple_xlsx_bytes


def test_simple_baseline_runs_seven_years_deterministically():
    config = SimpleInitialConfig(scenario_id="baseline")
    decisions = [SimplePolicyDecision() for _ in range(7)]
    result = run_simple(SimpleRunRequest(config=config, decisions=decisions))
    again = run_simple(SimpleRunRequest(config=config, decisions=decisions))
    assert result.completed_years == 7
    assert result.final_state == again.final_state
    assert len(result.years) == 7
    assert all(0 <= item.state.approval <= 100 for item in result.years)
    assert all(item.year == idx for idx, item in enumerate(result.years, 1))


def test_simple_policy_tradeoff_tighter_policy_lowers_activity():
    config = SimpleInitialConfig(scenario_id="baseline")
    state = initial_state(config)
    loose = step_simple(SimpleStepRequest(
        config=config, state=state,
        decision=SimplePolicyDecision(interest_rate=2, income_tax=18, corporate_tax=20, government_spending=24),
    )).result
    tight = step_simple(SimpleStepRequest(
        config=config, state=state,
        decision=SimplePolicyDecision(interest_rate=8, income_tax=25, corporate_tax=28, government_spending=19),
    )).result
    assert loose.state.real_gdp_growth > tight.state.real_gdp_growth
    assert loose.state.unemployment < tight.state.unemployment


def test_simple_deflation_is_penalized():
    config = SimpleInitialConfig(scenario_id="global_recession", initial_inflation=0.2)
    state = initial_state(config)
    result = step_simple(SimpleStepRequest(
        config=config, state=state,
        decision=SimplePolicyDecision(interest_rate=18, income_tax=35, corporate_tax=35, government_spending=12),
    )).result
    if result.state.inflation < 0:
        assert result.score.inflation < 10
        assert any("Deflação" in item for item in result.warnings)


def test_simple_debt_accumulates_under_large_deficits():
    config = SimpleInitialConfig(scenario_id="baseline", initial_debt_to_gdp=50)
    decisions = [SimplePolicyDecision(interest_rate=7, income_tax=10, corporate_tax=10, government_spending=35) for _ in range(4)]
    result = run_simple(SimpleRunRequest(config=config, decisions=decisions))
    assert result.final_state.debt_to_gdp > 50
    assert any(item.state.budget_deficit_to_gdp > 0 for item in result.years)


def test_simple_conversion_to_advanced_preserves_main_macro_conditions():
    config = SimpleInitialConfig()
    result = run_simple(SimpleRunRequest(config=config, decisions=[SimplePolicyDecision()] * 2))
    converted = simple_to_advanced(SimpleToAdvancedRequest(config=config, state=result.final_state, months=36))
    scenario = converted.scenario
    assert scenario["months"] == 36
    assert scenario["initial_inflation"] == result.final_state.inflation
    assert scenario["initial_unemployment"] == result.final_state.unemployment
    assert scenario["policy_rate"] == result.final_state.last_interest_rate
    assert converted.limitations


def test_simple_exports_have_history():
    result = run_simple(SimpleRunRequest(decisions=[SimplePolicyDecision()] * 3))
    csv_data = simple_csv_bytes(result)
    xlsx_data = simple_xlsx_bytes(result)
    assert b"real_gdp_growth" in csv_data
    assert xlsx_data.startswith(b"PK")
    assert len(xlsx_data) > 3000


def test_simple_api_flow():
    client = TestClient(app)
    scenarios = client.get("/api/v1/simple/scenarios")
    assert scenarios.status_code == 200
    assert len(scenarios.json()) == 3
    config = {"scenario_id": "volatile"}
    start = client.post("/api/v1/simple/start", json=config)
    assert start.status_code == 200
    payload = start.json()
    step = client.post("/api/v1/simple/step", json={
        "config": payload["config"],
        "state": payload["state"],
        "decision": {"interest_rate": 5, "income_tax": 20, "corporate_tax": 22, "government_spending": 22},
    })
    assert step.status_code == 200
    assert step.json()["result"]["year"] == 1
