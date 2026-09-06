from fastapi.testclient import TestClient

from economy_lab.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["engine_version"] == "2.13.2"


def test_desktop_webview_origin_is_allowed_by_cors():
    response = client.options(
        "/api/v1/simple/scenarios",
        headers={
            "Origin": "http://tauri.localhost",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://tauri.localhost"


def test_cors_desktop_mode_allows_tauri_but_blocks_vite(monkeypatch):
    monkeypatch.setenv("ECONOMY_LAB_RUNTIME_MODE", "desktop-sidecar")
    tauri = client.options(
        "/api/v1/health",
        headers={"Origin": "http://tauri.localhost", "Access-Control-Request-Method": "GET"},
    )
    assert tauri.status_code == 200
    assert tauri.headers["access-control-allow-origin"] == "http://tauri.localhost"

    vite = client.options(
        "/api/v1/health",
        headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in vite.headers


def test_cors_non_desktop_allows_vite(monkeypatch):
    monkeypatch.setenv("ECONOMY_LAB_RUNTIME_MODE", "web-local")
    vite = client.options(
        "/api/v1/health",
        headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "GET"},
    )
    assert vite.status_code == 200
    assert vite.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_simulate_economy_zero_endpoint():
    response = client.post(
        "/api/v1/simulate",
        json={
            "name": "API smoke",
            "months": 2,
            "households": 200,
            "firms": 8,
            "banks": 2,
            "seed": 2,
            "mode": "economy_zero",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "economy-zero-labor-benefits-v2.4"
    assert len(payload["series"]) == 2
    assert payload["summary"]["ledger_balanced"] is True
    assert payload["banking"] is not None
    assert len(payload["banking"]["banks"]) == 2
    assert payload["accounting"]["stocks_balanced"] is True
    assert payload["accounting"]["flows_balanced"] is True


def test_minsky_status_and_export_routes():
    from fastapi.testclient import TestClient
    from economy_lab.main import app
    client = TestClient(app)
    status = client.get('/api/v1/minsky/status')
    assert status.status_code == 200
    assert 'configured' in status.json()
    payload = {
        'name': 'Minsky export test', 'months': 1, 'households': 120,
        'firms': 8, 'banks': 2, 'seed': 4, 'mode': 'economy_zero'
    }
    exported = client.post('/api/v1/minsky/export', json=payload)
    assert exported.status_code == 200
    data = exported.json()
    assert data['schema_name'] == 'economy-lab-godley-v1.0'
    assert data['tick'] == 1
    assert data['stocks']


def test_dynare_status_route():
    response = client.get("/api/v1/dynare/status")
    assert response.status_code == 200
    payload = response.json()
    assert "ready" in payload
    assert "configured" in payload


def test_runtime_shutdown_is_disabled_outside_desktop(monkeypatch):
    monkeypatch.delenv("ECONOMY_LAB_SHUTDOWN_TOKEN", raising=False)
    response = client.post("/api/v1/runtime/shutdown")
    assert response.status_code == 404


def test_runtime_shutdown_requires_token_and_calls_callback(monkeypatch):
    from economy_lab.main import app

    called = {"value": False}
    app.state.request_desktop_shutdown = lambda: called.__setitem__("value", True)
    monkeypatch.setenv("ECONOMY_LAB_SHUTDOWN_TOKEN", "test-secret")

    denied = client.post(
        "/api/v1/runtime/shutdown",
        headers={"X-Economy-Lab-Shutdown-Token": "wrong"},
    )
    assert denied.status_code == 403
    assert called["value"] is False

    accepted = client.post(
        "/api/v1/runtime/shutdown",
        headers={"X-Economy-Lab-Shutdown-Token": "test-secret"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "shutting_down"
    assert called["value"] is True


def test_project_storage_api_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("ECONOMY_LAB_DB_PATH", str(tmp_path / "api.sqlite3"))
    payload = {
        "name": "Saved scenario", "months": 1, "households": 120,
        "firms": 8, "banks": 2, "seed": 11, "mode": "economy_zero"
    }
    created = client.post("/api/v1/projects", json={
        "name": "Projeto API", "description": "persistência", "scenario": payload
    })
    assert created.status_code == 201
    project = created.json()
    project_id = project["id"]

    saved_run = client.post(
        f"/api/v1/projects/{project_id}/simulate",
        json={"scenario": payload, "save_scenario": True},
    )
    assert saved_run.status_code == 200
    result = saved_run.json()
    assert result["result"]["summary"]["ledger_balanced"] is True
    run_id = result["run"]["id"]

    history = client.get(f"/api/v1/projects/{project_id}/runs")
    assert history.status_code == 200
    assert history.json()[0]["id"] == run_id

    reopened = client.get(f"/api/v1/runs/{run_id}")
    assert reopened.status_code == 200
    assert reopened.json()["scenario"]["seed"] == 11

    status = client.get("/api/v1/storage/status")
    assert status.status_code == 200
    assert status.json()["projects"] == 1
    assert status.json()["runs"] == 1


def test_batch_experiment_api(monkeypatch, tmp_path):
    monkeypatch.setenv("ECONOMY_LAB_DB_PATH", str(tmp_path / "batch-api.sqlite3"))
    base = {
        "name": "Batch API", "months": 2, "households": 120,
        "firms": 8, "banks": 2, "seed": 21, "mode": "economy_zero"
    }
    temporary = client.post("/api/v1/experiments/run", json={
        "base": base, "axis": "policy_rate", "values": [8, 12], "repetitions": 2, "seed_step": 1
    })
    assert temporary.status_code == 200
    assert temporary.json()["total_runs"] == 4
    assert all(row["all_accounting_balanced"] for row in temporary.json()["aggregates"])

    created = client.post("/api/v1/projects", json={"name": "Batch project", "scenario": base})
    project_id = created.json()["id"]
    saved = client.post(f"/api/v1/projects/{project_id}/experiments", json={
        "axis": "policy_rate", "values": [9, 11], "repetitions": 1, "scenario": base
    })
    assert saved.status_code == 201
    experiment_id = saved.json()["id"]
    history = client.get(f"/api/v1/projects/{project_id}/experiments")
    assert history.status_code == 200
    assert history.json()[0]["id"] == experiment_id
    reopened = client.get(f"/api/v1/experiments/{experiment_id}")
    assert reopened.status_code == 200
    assert reopened.json()["result"]["total_runs"] == 2


def test_profile_and_preset_api_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("ECONOMY_LAB_DB_PATH", str(tmp_path / "profiles-api.sqlite3"))
    created = client.post("/api/v1/profiles/from-lab", json={
        "module_id": "dynare", "name": "NK API", "description": "",
        "inputs": {
            "irf_periods": 16, "monetary_shock_bp": 125, "neutral_nominal_rate": 7,
            "beta": 0.99, "sigma": 1.2, "kappa": 0.12, "rho_i": 0.75,
            "phi_pi": 1.7, "phi_x": 0.3, "timeout_seconds": 120,
        },
    })
    assert created.status_code == 201
    profile = created.json()
    assert profile["kind"] == "macro"
    assert profile["scenario_patch"]["dynare_phi_pi"] == 1.7

    listed = client.get("/api/v1/profiles")
    assert listed.status_code == 200
    assert any(item["id"] == profile["id"] for item in listed.json())

    applied = client.post(f"/api/v1/profiles/{profile['id']}/apply", json={"scenario": {
        "name": "Profile apply", "months": 6, "households": 200, "firms": 8, "banks": 2
    }})
    assert applied.status_code == 200
    assert applied.json()["scenario"]["macro_engine"] == "dynare"
    assert applied.json()["scenario"]["dynare_phi_pi"] == 1.7

    presets = client.get("/api/v1/simulation/presets")
    assert presets.status_code == 200
    assert any(item["id"] == "basic" for item in presets.json())
    basic = client.post("/api/v1/simulation/presets/basic/apply", json={"scenario": applied.json()["scenario"]})
    assert basic.status_code == 200
    assert basic.json()["macro_engine"] == "off"
    assert basic.json()["activation_engine"] == "native"


def test_external_validation_endpoint(monkeypatch):
    from economy_lab.validation.external_engines import (
        ExternalEngineCheck, ExternalValidationReport, ExternalValidationStage
    )
    import economy_lab.api.routes as routes

    stage = ExternalValidationStage(
        name="detect-import", status="pass", duration_ms=2.0, summary="detected"
    )
    checks = (
        ExternalEngineCheck(
            engine="mesa", status="pass", installed_or_configured=True,
            version="3.5.1", duration_ms=10.0, summary="ok", details={},
            qualification_level="runtime-verified", compatibility="compatible",
            target_version="3.5.1", integrated_smoke_passed=True, stages=(stage,),
        ),
        ExternalEngineCheck(engine="hark", status="unavailable", installed_or_configured=False, version=None, duration_ms=1.0, summary="missing", stages=(stage,)),
        ExternalEngineCheck(engine="dynare", status="unavailable", installed_or_configured=False, version=None, duration_ms=1.0, summary="missing", stages=(stage,)),
        ExternalEngineCheck(engine="minsky", status="unavailable", installed_or_configured=False, version=None, duration_ms=1.0, summary="missing", stages=(stage,)),
    )
    fake = ExternalValidationReport(
        schema="economy-lab-external-validation-v2.7",
        report_id="00000000-0000-4000-8000-000000000001",
        report_digest="a" * 64,
        generated_at="2026-08-29T00:00:00+00:00",
        economy_lab_version="2.11.0",
        platform="Windows 11 (AMD64)",
        python_version="3.12.0",
        environment={"python_bits": 64},
        requested_engines=("mesa", "hark", "dynare", "minsky"),
        smoke_tests=True, integration_tests=True,
        status="partial", qualification_ready=False,
        passed=1, failed=0, unavailable=3, runtime_verified=1, read_only_verified=0,
        checks=checks,
    )
    monkeypatch.setattr(routes, "validate_external_engines", lambda *args, **kwargs: fake)
    response = client.post("/api/v1/validation/external-engines", json={"smoke_tests": True, "integration_tests": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "economy-lab-external-validation-v2.7"
    assert payload["qualification_ready"] is False
    assert payload["runtime_verified"] == 1
    assert payload["checks"][0]["engine"] == "mesa"
    assert payload["checks"][0]["qualification_level"] == "runtime-verified"
    assert payload["checks"][0]["stages"][0]["name"] == "detect-import"


def test_data_catalog_and_cache_status(monkeypatch, tmp_path):
    monkeypatch.setenv("ECONOMY_LAB_DATA_CACHE", str(tmp_path / "cache"))
    catalog = client.get("/api/v1/data/catalog")
    assert catalog.status_code == 200
    ids = {item["id"] for item in catalog.json()}
    assert {"bcb_sgs", "ibge_sidra", "world_bank", "ipeadata"}.issubset(ids)
    status = client.get("/api/v1/data/cache/status")
    assert status.status_code == 200
    assert status.json()["entries"] == 0


def test_calibration_api_uses_existing_result():
    scenario = {"name": "Calibration API", "months": 2, "households": 120, "firms": 8, "banks": 2, "seed": 5}
    sim = client.post("/api/v1/simulate", json=scenario)
    assert sim.status_code == 200
    series = {
        "source": "bcb_sgs", "series_id": "432", "title": "Selic", "unit": "%", "frequency": "daily",
        "fetched_at": "2026-08-29T00:00:00+00:00", "cached": False, "request_url": "https://example.invalid",
        "metadata": {}, "observations": [{"date": "2026-08-01", "value": 12.0}], "warning": "test"
    }
    response = client.post("/api/v1/calibration/evaluate", json={
        "scenario": scenario, "result": sim.json(),
        "targets": [{"metric": "policy_rate", "series": series, "statistic": "last", "weight": 1, "scale_floor": 1}]
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_scenario_patch"]["policy_rate"] == 12.0
    assert payload["requires_review"] is True


def test_calibration_fit_api(monkeypatch):
    from economy_lab.core.schemas import CalibrationFitResponse, CalibrationResponse
    import economy_lab.api.routes as routes

    fake = CalibrationFitResponse(
        baseline_score=70, best_score=82, evaluations=5, rounds_completed=1, converged=False,
        parameters=["policy_rate"], best_scenario_patch={"policy_rate": 11.0},
        final_calibration=CalibrationResponse(engine="test", score=82, normalized_rmse=.2, metrics=[], warning="test"),
        trace=[], warning="bounded test",
    )
    monkeypatch.setattr(routes, "fit_calibration", lambda request: fake)
    response = client.post("/api/v1/calibration/fit", json={
        "scenario": {"name": "Fit", "months": 2, "households": 100, "firms": 5, "banks": 1},
        "targets": [{
            "metric": "policy_rate", "statistic": "last", "weight": 1, "scale_floor": 1,
            "series": {
                "source": "bcb_sgs", "series_id": "432", "title": "Selic", "unit": "%", "frequency": "daily",
                "fetched_at": "2026-08-29T00:00:00+00:00", "cached": False, "request_url": "https://example.invalid",
                "metadata": {}, "observations": [{"date": "2026-08-01", "value": 12.0}], "warning": "test"
            }
        }],
        "parameters": ["policy_rate"], "max_evaluations": 4, "max_rounds": 1
    })
    assert response.status_code == 200
    assert response.json()["best_scenario_patch"]["policy_rate"] == 11.0


def test_scenario_rejects_extra_fields():
    response = client.post(
        "/api/v1/simulate",
        json={
            "name": "Extra field test",
            "months": 2,
            "households": 200,
            "firms": 8,
            "banks": 2,
            "seed": 1,
            "mode": "economy_zero",
            "nonexistent_field": 42,
        },
    )
    assert response.status_code == 422


def test_scenario_rejects_nan_and_infinity():
    import json

    # Raw malformed JSON must reach the API, bypassing httpx's strict encoder.
    for value in (float("nan"), float("inf"), -float("inf")):
        response = client.post(
            "/api/v1/simulate",
            content=json.dumps({
                "name": "Invalid number", "months": 2, "households": 200,
                "firms": 8, "banks": 2, "seed": 1, "initial_inflation": value,
            }),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422
        assert response.json()["detail"]


def test_project_create_rejects_extra_fields():
    response = client.post("/api/v1/projects", json={
        "name": "Strict", "description": "", "extra_key": True,
        "scenario": {"name": "S", "months": 1, "households": 120, "firms": 8, "banks": 2},
    })
    assert response.status_code == 422


def test_data_fetch_rejects_extra_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("ECONOMY_LAB_DATA_CACHE", str(tmp_path))
    response = client.post("/api/v1/data/fetch", json={
        "source": "bcb_sgs", "series_id": "432", "bogus": 1,
    })
    assert response.status_code == 422


def test_all_expected_routes_present_and_not_duplicated():
    import warnings

    expected = [
        ("/simple/scenarios", "GET"),
        ("/simple/start", "POST"),
        ("/simple/step", "POST"),
        ("/simple/run", "POST"),
        ("/simple/to-advanced", "POST"),
        ("/exports/simple.csv", "POST"),
        ("/exports/simple.xlsx", "POST"),
        ("/modules", "GET"),
        ("/modules/{module_id}", "GET"),
        ("/tools", "GET"),
        ("/tools/{tool_id}", "GET"),
        ("/authority/registry", "GET"),
        ("/authority/plan", "POST"),
        ("/profiles", "GET"),
        ("/profiles/from-lab", "POST"),
        ("/profiles/{profile_id}", "GET"),
        ("/profiles/{profile_id}", "DELETE"),
        ("/profiles/{profile_id}/apply", "POST"),
        ("/simulation/presets", "GET"),
        ("/simulation/presets/{preset_id}/apply", "POST"),
        ("/exports/calibration.xlsx", "POST"),
        ("/exports/simulation.csv", "POST"),
        ("/exports/simulation.xlsx", "POST"),
        ("/exports/batch.csv", "POST"),
        ("/exports/batch.xlsx", "POST"),
        ("/data/catalog", "GET"),
        ("/data/cache/status", "GET"),
        ("/data/fetch", "POST"),
        ("/scenario/compile", "POST"),
        ("/model/providers", "GET"),
        ("/model/compile", "POST"),
        ("/model/validate", "POST"),
        ("/model/to-scenario", "POST"),
    ]

    # Verify the public schema, including nested routers. Duplicate operation
    # IDs are reported by FastAPI while generating OpenAPI.
    app.openapi_schema = None
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        schema = app.openapi()
    assert not any("Duplicate Operation ID" in str(item.message) for item in emitted)
    for path, method in expected:
        assert method.lower() in schema["paths"].get(f"/api/v1{path}", {}), f"Missing route: {method} {path}"
