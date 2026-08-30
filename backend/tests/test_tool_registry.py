from fastapi.testclient import TestClient

from economy_lab.main import app
from economy_lab.modules import get_tool, list_tools


def test_tools_are_individual_hub_parts():
    tools = list_tools()
    ids = {tool["id"] for tool in tools}
    assert "simulation-run" in ids
    assert "dynare-template" in ids
    assert "dynare-irf" in ids
    assert "minsky-introspection" in ids
    assert "minsky-variables" in ids
    assert "minsky-godley-reconciliation" in ids
    assert "mesa-wealth" in ids
    assert "hark-policy" in ids


def test_tools_can_be_filtered_by_module():
    dynare = list_tools("dynare")
    assert {tool["module_id"] for tool in dynare} == {"dynare"}
    assert {tool["id"] for tool in dynare} == {"dynare-template", "dynare-irf"}


def test_tool_availability_inherits_module_status():
    tool = get_tool("simulation-run")
    assert tool is not None
    assert tool["available"] is True
    assert tool["status"] == "ready"


def test_tools_api_catalog_and_detail():
    client = TestClient(app)
    response = client.get("/api/v1/tools?module_id=simulation")
    assert response.status_code == 200
    assert any(item["id"] == "simulation-export" for item in response.json())

    detail = client.get("/api/v1/tools/dynare-template")
    assert detail.status_code == 200
    assert detail.json()["module_id"] == "dynare"

    missing = client.get("/api/v1/tools/nope")
    assert missing.status_code == 404
