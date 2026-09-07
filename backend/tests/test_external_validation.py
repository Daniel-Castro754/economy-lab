from economy_lab.validation import (
    ENGINE_ORDER,
    REPORT_SCHEMA,
    validate_external_engines,
    verify_report_digest,
)


def test_validation_report_is_well_formed_on_current_runtime():
    report = validate_external_engines(smoke_tests=False, integration_tests=False)
    assert report.schema == REPORT_SCHEMA == "economy-lab-external-validation-v2.7"
    assert report.requested_engines == ENGINE_ORDER
    assert len(report.checks) == 4
    assert report.passed + report.failed + report.unavailable == 4
    assert report.status in {"ready", "partial", "failed"}
    assert len(report.report_id) >= 32
    assert len(report.report_digest) == 64
    assert verify_report_digest(report) is True
    assert report.environment["python_bits"] in {32, 64}
    assert all(check.duration_ms >= 0 for check in report.checks)
    assert all(check.stages for check in report.checks)


def test_validation_report_digest_detects_mutation():
    report = validate_external_engines(["mesa"], smoke_tests=False, integration_tests=False)
    payload = report.to_dict()
    assert verify_report_digest(payload) is True
    payload["economy_lab_version"] = "tampered"
    assert verify_report_digest(payload) is False


def test_validation_markdown_contains_evidence_table():
    report = validate_external_engines(["mesa"], smoke_tests=False, integration_tests=False)
    markdown = report.to_markdown()
    assert "External Engine Qualification" in markdown
    assert "Report ID" in markdown
    assert "| Engine | Status | Qualification" in markdown
    assert "## MESA" in markdown


def test_detection_only_never_claims_runtime_verified():
    report = validate_external_engines(smoke_tests=False, integration_tests=False)
    assert all(check.qualification_level in {"none", "detected"} for check in report.checks)
    assert report.runtime_verified == 0
    assert report.read_only_verified == 0


def test_validation_rejects_unknown_engine():
    try:
        validate_external_engines(["unknown"])  # type: ignore[list-item]
    except ValueError as exc:
        assert "unsupported external engine" in str(exc)
    else:
        raise AssertionError("unknown engine must be rejected")


def test_optional_engine_modules_can_be_imported_independently():
    # Regression for the qualification CLI: importing an optional engine must
    # not force EconomyZeroModel and recreate a HARK <-> ABM circular import.
    from economy_lab.engines.hark_adapter import hark_available
    from economy_lab.engines.mesa_adapter import mesa_available
    assert isinstance(hark_available(), bool)
    assert isinstance(mesa_available(), bool)


def test_environment_fingerprint_does_not_expose_minsky_url(monkeypatch):
    monkeypatch.setenv("MINSKY_REST_URL", "http://secret-host.example:9999")
    report = validate_external_engines(["mesa"], smoke_tests=False, integration_tests=False)
    flags = report.environment["configuration_flags"]
    assert flags["MINSKY_REST_URL"] is True
    assert "secret-host" not in str(report.environment)


def _fake_balanced_sim(*, activation="native", household="heuristic", macro="off", macro_report=None):
    from types import SimpleNamespace
    return SimpleNamespace(
        summary=SimpleNamespace(
            ledger_balanced=True,
            godley_stocks_balanced=True,
            godley_flows_balanced=True,
        ),
        engines=SimpleNamespace(
            activation=activation,
            household_decision=household,
            macro=macro,
        ),
        macro=macro_report,
    )


def test_mesa_success_path_reaches_runtime_verified(monkeypatch):
    import economy_lab.engines.mesa_adapter as mesa_adapter
    import economy_lab.labs.standalone as standalone
    import economy_lab.core.simulation as simulation
    from economy_lab.validation import validate_mesa

    monkeypatch.setattr(mesa_adapter, "mesa_available", lambda: True)
    monkeypatch.setattr(standalone, "run_mesa_lab", lambda **kwargs: {
        "initial_total_wealth": 120.0,
        "final_total_wealth": 120.0,
        "agents": 12,
        "steps": 4,
        "gini": 0.1,
    })
    monkeypatch.setattr(simulation, "run_economy_zero", lambda spec: _fake_balanced_sim(activation="mesa-3.5-agentset"))
    check = validate_mesa(smoke_test=True, integration_test=True)
    assert check.status == "pass"
    assert check.qualification_level == "runtime-verified"
    assert check.integrated_smoke_passed is True
    assert [stage.status for stage in check.stages] == ["pass", "pass", "pass"]


def test_hark_success_path_reaches_runtime_verified(monkeypatch):
    import economy_lab.engines.hark_adapter as hark_adapter
    import economy_lab.labs.standalone as standalone
    import economy_lab.core.simulation as simulation
    from economy_lab.validation import validate_hark

    monkeypatch.setattr(hark_adapter, "hark_available", lambda: True)
    monkeypatch.setattr(standalone, "run_hark_lab", lambda **kwargs: {
        "policy_curve": [
            {"market_resources": float(i + 1), "consumption": float(i + 1) * 0.7, "saving": float(i + 1) * 0.3}
            for i in range(5)
        ],
        "group_profiles": [{}, {}],
    })
    monkeypatch.setattr(simulation, "run_economy_zero", lambda spec: _fake_balanced_sim(household="hark-indshock-stateful"))
    check = validate_hark(smoke_test=True, integration_test=True)
    assert check.status == "pass"
    assert check.qualification_level == "runtime-verified"
    assert check.integrated_smoke_passed is True


def test_dynare_success_path_reaches_runtime_verified(monkeypatch):
    from types import SimpleNamespace
    import economy_lab.engines.dynare_adapter as dynare_adapter
    import economy_lab.core.simulation as simulation
    from economy_lab.validation import validate_dynare

    monkeypatch.setattr(dynare_adapter, "dynare_status", lambda: dynare_adapter.DynareStatus(
        configured=True,
        octave_executable="C:/octave/octave-cli.exe",
        dynare_matlab_path="C:/dynare/7.1/matlab",
        dynare_version_hint="7.1",
        ready=True,
        error=None,
    ))
    points = tuple(
        dynare_adapter.DynareIRFPoint(period=i + 1, output_gap=-0.1, inflation_gap=-0.05, policy_rate_gap=0.2)
        for i in range(4)
    )
    monkeypatch.setattr(dynare_adapter, "run_reference_nk_model", lambda **kwargs: SimpleNamespace(
        points=points,
        model_name="qualification-nk",
        results_file="C:/tmp/qualification_results.mat",
    ))
    monkeypatch.setattr(simulation, "run_economy_zero", lambda spec: _fake_balanced_sim(
        macro="dynare-7.x-reference-nk-v1.0",
        macro_report=SimpleNamespace(irf=[1, 2, 3, 4]),
    ))
    check = validate_dynare(smoke_test=True, integration_test=True, timeout_seconds=20)
    assert check.status == "pass"
    assert check.qualification_level == "runtime-verified"
    assert check.integrated_smoke_passed is True


def test_minsky_success_path_is_read_only_verified(monkeypatch):
    import economy_lab.engines.minsky_adapter as minsky_adapter
    from economy_lab.validation import validate_minsky

    monkeypatch.setattr(minsky_adapter, "bridge_status", lambda: minsky_adapter.MinskyBridgeStatus(
        configured=True, reachable=True, object_type="Minsky", model_time=1.0, error=None
    ))

    class FakeClient:
        def __init__(self, timeout=3.0):
            self.timeout = timeout
        def list_members(self, path="/minsky"):
            return ["t", "variableValues", "godleyItems"]

    monkeypatch.setattr(minsky_adapter, "MinskyRestClient", FakeClient)
    check = validate_minsky(smoke_test=True, timeout_seconds=1.0)
    assert check.status == "pass"
    assert check.qualification_level == "read-only-verified"
    assert check.integrated_smoke_passed is False
    assert all(stage.status == "pass" for stage in check.stages)
