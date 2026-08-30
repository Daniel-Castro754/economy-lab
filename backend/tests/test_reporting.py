import io
import zipfile

from fastapi.testclient import TestClient

from economy_lab.core.schemas import BatchExperimentRequest, ScenarioSpec
from economy_lab.core.simulation import run_simulation
from economy_lab.experiments import run_batch_experiment
from economy_lab.main import app
from economy_lab.reporting import (
    batch_csv_bytes,
    batch_xlsx_bytes,
    simulation_csv_bytes,
    simulation_xlsx_bytes,
)


def _scenario() -> ScenarioSpec:
    return ScenarioSpec(months=3, households=120, firms=8, banks=2, seed=123)


def test_simulation_csv_and_xlsx_include_audit_data():
    scenario = _scenario()
    result = run_simulation(scenario)
    csv_payload = simulation_csv_bytes(result).decode("utf-8-sig")
    assert "month" in csv_payload
    assert "gdp_index" in csv_payload
    assert "bank_credit" in csv_payload

    xlsx = simulation_xlsx_bytes(scenario, result)
    with zipfile.ZipFile(io.BytesIO(xlsx)) as archive:
        names = set(archive.namelist())
        assert "xl/workbook.xml" in names
        assert "xl/styles.xml" in names
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        assert "Resumo" in workbook
        assert "Série mensal" in workbook
        assert "Godley estoques" in workbook
        assert "Bancos" in workbook
        assert "Motor financeiro" in workbook


def test_batch_exports_and_api_download_headers():
    scenario = _scenario()
    batch = run_batch_experiment(BatchExperimentRequest(base=scenario, values=[8, 12], repetitions=1))
    assert "mean_gdp_index" in batch_csv_bytes(batch).decode("utf-8-sig")
    with zipfile.ZipFile(io.BytesIO(batch_xlsx_bytes(batch))) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        assert "Comparação" in workbook
        assert "Execuções" in workbook

    client = TestClient(app)
    result = run_simulation(scenario)
    response = client.post("/api/v1/exports/simulation.xlsx", json={
        "scenario": scenario.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
    })
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert "economy-lab-simulation.xlsx" in response.headers["content-disposition"]
    assert response.content[:2] == b"PK"
