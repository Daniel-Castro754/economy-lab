from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from economy_lab.main import app
from economy_lab.engines.hark_adapter import EngineUnavailableError, hark_available
from economy_lab.engines.mesa_adapter import mesa_available
from economy_lab.labs.standalone import dynare_template, minsky_command, run_hark_lab, run_mesa_lab
from economy_lab.modules import get_module


def test_dynare_template_is_available_without_external_execution():
    source = dynare_template(irf_periods=12, monetary_shock_pp=1.25, phi_pi=1.7)
    assert "model(linear)" in source
    assert "stoch_simul" in source
    assert "phi_pi = 1.7" in source
    client = TestClient(app)
    response = client.post("/api/v1/labs/dynare/template", json={"irf_periods": 12, "monetary_shock_bp": 125})
    assert response.status_code == 200
    assert "var x pi i" in response.json()["source"]


def test_module_registry_exposes_standalone_lab_contracts():
    assert "/labs/dynare/run" in get_module("dynare")["routes"]
    assert "/labs/minsky/command" in get_module("minsky")["routes"]
    assert "/labs/mesa/run" in get_module("mesa")["routes"]
    assert "/labs/hark/run" in get_module("hark")["routes"]
    assert "standalone-lab" in get_module("dynare")["capabilities"]


def test_minsky_command_protocol_with_fake_client(monkeypatch):
    class FakeClient:
        def __init__(self):
            pass
        def list_members(self, path):
            return ["a", "b", path]
        def signature(self, path):
            return {"path": path, "args": []}
        def step(self):
            return {"t": 1}
        def reset(self):
            return {"t": 0}
        def get_variable_value(self, variable_id):
            return 3.25
        def set_variable_value(self, variable_id, value):
            return {"id": variable_id, "value": value}

    monkeypatch.setattr("economy_lab.labs.standalone.MinskyRestClient", FakeClient)
    assert minsky_command(action="members", path="/minsky")["result"][0] == "a"
    assert minsky_command(action="get_variable", variable_id=":x")["result"] == 3.25
    assert minsky_command(action="set_variable", variable_id=":x", value=4.0)["result"]["value"] == 4.0


def test_minsky_lab_api_can_return_typed_command(monkeypatch):
    monkeypatch.setattr(
        "economy_lab.api.routes.minsky_command",
        lambda **kwargs: {"engine": "minsky-rest", "action": kwargs["action"], "result": ["minsky", "t"]},
    )
    response = TestClient(app).post("/api/v1/labs/minsky/command", json={"action": "members", "path": "/minsky"})
    assert response.status_code == 200
    assert response.json()["action"] == "members"


def test_mesa_lab_conserves_wealth_when_installed():
    if not mesa_available():
        with pytest.raises(EngineUnavailableError):
            run_mesa_lab(agents=20, steps=5)
        return
    result = run_mesa_lab(agents=20, steps=10, initial_wealth=10, transfer_amount=1, seed=7)
    assert result["final_total_wealth"] == pytest.approx(result["initial_total_wealth"])
    assert 0 <= result["gini"] <= 1
    assert result["path"][-1]["step"] == 10


def test_hark_lab_returns_policy_curve_when_installed():
    if not hark_available():
        with pytest.raises(EngineUnavailableError):
            run_hark_lab(points=8)
        return
    result = run_hark_lab(points=8, max_market_resources=6)
    assert len(result["policy_curve"]) == 8
    for point in result["policy_curve"]:
        assert point["consumption"] <= point["market_resources"] + 1e-9
        assert point["saving"] >= 0
