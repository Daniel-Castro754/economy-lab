import pytest

from economy_lab.core.schemas import ScenarioSpec
from economy_lab.engines.minsky_adapter import MinskyRestClient, MinskyTemplateBridge, bridge_status
import economy_lab.engines.minsky_adapter as minsky_adapter
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


@pytest.mark.parametrize(
    ("base_url", "normalized_url"),
    [
        ("http://localhost.:8000/", "http://localhost.:8000"),
        ("http://127.0.0.1:8000/api/", "http://127.0.0.1:8000/api/"),
        ("http://[::1]:8000/", "http://[::1]:8000"),
        ("https://minsky.example.test/api/", "https://minsky.example.test/api/"),
        ("https://localhost:8000/", "https://localhost:8000"),
    ],
)
def test_client_accepts_safe_rest_urls_without_network(base_url, normalized_url):
    client = MinskyRestClient(base_url=base_url)
    assert client.base_url == normalized_url
    assert client._url("/minsky/@type") == f"{normalized_url.rstrip('/')}/minsky/@type"


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://localhost:8000",
        "http://minsky.example.test:8000",
        "http://192.0.2.1:8000",
        "http://user:secret@localhost:8000",
        "https://minsky.example.test?token=secret",
        "https://minsky.example.test?",
        "https://minsky.example.test/#fragment",
        "https://minsky.example.test/#",
        "https:///minsky",
        "https://[::1",
    ],
)
def test_client_rejects_unsafe_or_malformed_rest_urls_without_leaking_values(base_url):
    with pytest.raises(ValueError) as exc_info:
        MinskyRestClient(base_url=base_url)
    assert base_url not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_client_validates_environment_rest_url_without_network(monkeypatch):
    monkeypatch.setenv("MINSKY_REST_URL", "http://minsky.example.test:8000")
    with pytest.raises(ValueError, match="HTTPS for non-loopback hosts"):
        MinskyRestClient()


def test_client_rejects_oversized_rest_response(monkeypatch):
    class FakeResponse:
        headers: dict[str, str] = {}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, _limit: int) -> bytes:
            return b"12345"

    monkeypatch.setattr(minsky_adapter, "_MAX_REST_RESPONSE_BYTES", 4)
    monkeypatch.setattr(minsky_adapter.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    client = MinskyRestClient(base_url="http://127.0.0.1:8000")

    with pytest.raises(ValueError, match="exceeds the allowed size"):
        client.get("/minsky/@type")


def test_godley_export_has_json_and_csv():
    model = EconomyZeroModel(EconomyZeroConfig(households=120, firms=8, banks=2, seed=7))
    model.run(2)
    export = build_godley_export(model.ledger, tick=model.tick)
    assert export.to_payload()["schema"] == "economy-lab-godley-v1.0"
    assert "instrument" in export.matrix_csv("stocks")
    assert "households" in export.matrix_csv("flows")
