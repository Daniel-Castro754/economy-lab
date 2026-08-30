from fastapi.testclient import TestClient

from economy_lab.main import app
from economy_lab.modules import list_modules


def test_module_registry_has_expected_hub_modules():
    items = list_modules()
    ids = {item["id"] for item in items}
    assert {"simulation", "dynare", "minsky", "mesa", "hark", "analytics", "scenario-ai"} <= ids
    simulation = next(item for item in items if item["id"] == "simulation")
    assert simulation["available"] is True
    assert "xlsx-export" in simulation["capabilities"]
    assert "charts" in simulation["capabilities"]
    minsky = next(item for item in items if item["id"] == "minsky")
    assert "read-only-godley-reconciliation" in minsky["capabilities"]
    assert "/minsky/reconcile" in minsky["routes"]


def test_modules_api_exposes_status_without_silent_fallback():
    client = TestClient(app)
    response = client.get("/api/v1/modules")
    assert response.status_code == 200
    payload = response.json()
    assert any(item["id"] == "dynare" for item in payload)
    assert all("available" in item and "status" in item for item in payload)
    missing = client.get("/api/v1/modules/does-not-exist")
    assert missing.status_code == 404
