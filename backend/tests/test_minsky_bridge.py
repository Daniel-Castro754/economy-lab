from economy_lab.core.schemas import ScenarioSpec
from economy_lab.engines.minsky_adapter import MinskyRestClient, MinskyTemplateBridge, bridge_status
from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.engines.minsky_adapter import build_godley_export


class FakeClient(MinskyRestClient):
    def __init__(self):
        self.base_url = "http://fake"
        self.timeout = 1
        self.values = {":policy_rate": 0.1, ":bank_credit": 12.0}

    def get(self, path: str):
        if path == "/minsky/@type": return "::minsky::Minsky"
        if path == "/minsky/t": return 2.0
        if "/variableValues/@elem/" in path:
            key = path.split("/@elem/", 1)[1].rsplit("/value", 1)[0]
            return self.values[key]
        raise KeyError(path)

    def put(self, path: str, payload):
        if "/variableValues/@elem/" in path:
            key = path.split("/@elem/", 1)[1].rsplit("/value", 1)[0]
            self.values[key] = float(payload)
            return self.values[key]
        return None


def test_handshake_and_template_roundtrip():
    client = FakeClient()
    status = client.handshake()
    assert status.reachable
    assert status.object_type == "::minsky::Minsky"
    bridge = MinskyTemplateBridge(client, {"policy_rate": ":policy_rate", "bank_credit": ":bank_credit"})
    assert bridge.push({"policy_rate": 0.15}) == {"policy_rate": 0.15}
    pulled = bridge.pull()
    assert pulled["policy_rate"] == 0.15
    assert pulled["bank_credit"] == 12.0


def test_bridge_status_without_configuration(monkeypatch):
    monkeypatch.delenv("MINSKY_REST_URL", raising=False)
    status = bridge_status()
    assert not status.configured
    assert not status.reachable


def test_godley_export_has_json_and_csv():
    model = EconomyZeroModel(EconomyZeroConfig(households=120, firms=8, banks=2, seed=7))
    model.run(2)
    export = build_godley_export(model.ledger, tick=model.tick)
    assert export.to_payload()["schema"] == "economy-lab-godley-v1.0"
    assert "instrument" in export.matrix_csv("stocks")
    assert "households" in export.matrix_csv("flows")
