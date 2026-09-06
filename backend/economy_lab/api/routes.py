from dataclasses import asdict
from hashlib import sha256
import logging
import os
from pathlib import Path
import secrets
from time import perf_counter


from fastapi import APIRouter, Header, HTTPException, Request

from economy_lab import __version__
from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.core.shocks import EconomicShock
from economy_lab.finance import FinancialGuidance
from economy_lab.core.schemas import (
    DynareStatusResponse,
    HealthResponse,
    MinskyExchangeResponse,
    MinskyReconciliationRequest,
    MinskyReconciliationResponse,
    MinskyStatusResponse,
    ScenarioSpec,
    SimulationResult,
    StorageStatusResponse,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectSummary,
    ProjectRecord,
    ProjectRunRequest,
    JobStatus,
    SimulationJobCreateRequest,
    ProjectSimulationJobCreateRequest,
    SimulationJobSummary,
    SimulationJobRecord,
    RunSummary,
    RunRecord,
    RunManifest,
    RunManifestResponse,
    ReplayResponse,
    ReplayVerification,
    ProjectSimulationResponse,
    BatchExperimentRequest,
    BatchExperimentResponse,
    ProjectBatchRequest,
    ExperimentSummary,
    ExperimentRecord,
    DynareLabRequest,
    DynareTemplateResponse,
    DynareLabResponse,
    MesaLabRequest,
    MesaLabResponse,
    MesaComponentRequest,
    MesaComponentResponse,
    HarkLabRequest,
    HarkLabResponse,
    MinskyLabCommandRequest,
    MinskyLabCommandResponse,
    MinskyFinancialCaptureRequest,
    MinskyFinancialCaptureResponse,
    ExternalValidationRequest,
    ExternalValidationReportResponse,
    CalibrationRequest, CalibrationResponse, CalibrationFitRequest, CalibrationFitResponse,
)
from economy_lab.core.simulation import run_simulation
from economy_lab.core.reproducibility import stable_hash, runtime_differences
from economy_lab.engines.dynare_adapter import (
    DynareExecutionError,
    DynareUnavailableError,
    dynare_status,
)
from economy_lab.engines.hark_adapter import EngineUnavailableError, hark_available
from economy_lab.engines.mesa_adapter import mesa_available
from economy_lab.engines.minsky_adapter import (
    MinskyRestClient,
    bridge_status,
    build_godley_export,
    minsky_rest_configured,
)
from economy_lab.engines.minsky_reconciliation import (
    MinskyGodleyCellMapping,
    ReconciliationContractError,
    capture_minsky_values,
    reconcile_godley_payload,
)
from economy_lab.storage import ProjectStore
from economy_lab.jobs import get_job_manager
from economy_lab.experiments import run_batch_experiment
from economy_lab.labs import dynare_template, minsky_command, run_dynare_lab, run_hark_lab, run_mesa_lab, run_mesa_component_lab, run_minsky_financial_controller
from economy_lab.validation import validate_external_engines
from economy_lab.calibration import evaluate_calibration, fit_calibration

from economy_lab.api.simple_routes import router as simple_router
from economy_lab.api.catalog_routes import router as catalog_router
from economy_lab.api.profile_routes import router as profile_router
from economy_lab.api.export_routes import router as export_router
from economy_lab.api.data_routes import router as data_router
from economy_lab.api.model_routes import router as model_router

logger = logging.getLogger(__name__)

from economy_lab.api.runtime_routes import router as runtime_router

router = APIRouter()
router.include_router(runtime_router)
router.include_router(simple_router)
router.include_router(catalog_router)
router.include_router(profile_router)
router.include_router(export_router)
router.include_router(data_router)
router.include_router(model_router)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        engine_version=__version__,
        mesa_available=mesa_available(),
        hark_available=hark_available(),
        minsky_rest_configured=minsky_rest_configured(),
        dynare_ready=dynare_status().ready,
        runtime_mode=os.getenv("ECONOMY_LAB_RUNTIME_MODE", "web-local"),
        runtime_instance=os.getenv("ECONOMY_LAB_RUNTIME_INSTANCE"),
    )


@router.post("/runtime/shutdown")
def runtime_shutdown(
    request: Request,
    x_economy_lab_shutdown_token: str | None = Header(default=None),
) -> dict[str, str]:
    """Gracefully stop only a desktop-managed backend instance.

    The endpoint is unavailable in ordinary web/development mode and requires
    a per-process token injected by the Tauri shell.
    """

    expected = os.getenv("ECONOMY_LAB_SHUTDOWN_TOKEN")
    if not expected:
        raise HTTPException(status_code=404, detail="Desktop shutdown is not enabled")
    if not x_economy_lab_shutdown_token or not secrets.compare_digest(
        x_economy_lab_shutdown_token, expected
    ):
        raise HTTPException(status_code=403, detail="Invalid desktop shutdown token")

    callback = getattr(request.app.state, "request_desktop_shutdown", None)
    if callback is None:
        raise HTTPException(status_code=503, detail="Desktop shutdown callback unavailable")
    callback()
    return {"status": "shutting_down"}


@router.post("/calibration/evaluate", response_model=CalibrationResponse)
def calibration_evaluate(request: CalibrationRequest) -> CalibrationResponse:
    try:
        return evaluate_calibration(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/calibration/fit", response_model=CalibrationFitResponse)
def calibration_fit(request: CalibrationFitRequest) -> CalibrationFitResponse:
    try:
        return fit_calibration(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/labs/dynare/template", response_model=DynareTemplateResponse)
def dynare_lab_template(request: DynareLabRequest) -> DynareTemplateResponse:
    source = dynare_template(
        irf_periods=request.irf_periods,
        monetary_shock_pp=request.monetary_shock_bp / 100.0,
        beta=request.beta, sigma=request.sigma, kappa=request.kappa,
        rho_i=request.rho_i, phi_pi=request.phi_pi, phi_x=request.phi_x,
    )
    return DynareTemplateResponse(source=source)


@router.post("/labs/dynare/run", response_model=DynareLabResponse)
def dynare_lab_run(request: DynareLabRequest) -> DynareLabResponse:
    try:
        payload = run_dynare_lab(
            irf_periods=request.irf_periods,
            monetary_shock_pp=request.monetary_shock_bp / 100.0,
            neutral_nominal_rate=request.neutral_nominal_rate,
            beta=request.beta, sigma=request.sigma, kappa=request.kappa,
            rho_i=request.rho_i, phi_pi=request.phi_pi, phi_x=request.phi_x,
            timeout_seconds=request.timeout_seconds,
        )
        return DynareLabResponse(**payload)
    except DynareUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DynareExecutionError as exc:
        logger.exception("Dynare/Octave execution failed")
        raise HTTPException(status_code=502, detail="Dynare/Octave execution failed") from exc


@router.post("/labs/mesa/run", response_model=MesaLabResponse)
def mesa_lab_run(request: MesaLabRequest) -> MesaLabResponse:
    try:
        return MesaLabResponse(**run_mesa_lab(**request.model_dump()))
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/labs/mesa/component/run", response_model=MesaComponentResponse)
def mesa_component_lab_run(request: MesaComponentRequest) -> MesaComponentResponse:
    try:
        return MesaComponentResponse(**run_mesa_component_lab(**request.model_dump()))
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/labs/hark/run", response_model=HarkLabResponse)
def hark_lab_run(request: HarkLabRequest) -> HarkLabResponse:
    try:
        return HarkLabResponse(**run_hark_lab(**request.model_dump()))
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/labs/minsky/command", response_model=MinskyLabCommandResponse)
def minsky_lab_command(request: MinskyLabCommandRequest) -> MinskyLabCommandResponse:
    try:
        return MinskyLabCommandResponse(**minsky_command(**request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Minsky REST command failed")
        raise HTTPException(status_code=502, detail="Minsky REST command failed") from exc


@router.post("/labs/minsky/financial/run", response_model=MinskyFinancialCaptureResponse)
def minsky_financial_run(request: MinskyFinancialCaptureRequest) -> MinskyFinancialCaptureResponse:
    try:
        payload = run_minsky_financial_controller(
            steps=request.steps,
            reset_before=request.reset_before,
            unit_mode=request.unit_mode,
            mapping=request.mapping.model_dump(),
        )
        return MinskyFinancialCaptureResponse(**payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Minsky financial controller failed")
        raise HTTPException(status_code=502, detail="Minsky financial controller failed") from exc


@router.post("/validation/external-engines", response_model=ExternalValidationReportResponse)
def validate_external_engines_route(request: ExternalValidationRequest) -> ExternalValidationReportResponse:
    report = validate_external_engines(
        request.engines,
        smoke_tests=request.smoke_tests,
        integration_tests=request.integration_tests,
        dynare_timeout_seconds=request.dynare_timeout_seconds,
        minsky_timeout_seconds=request.minsky_timeout_seconds,
        economy_lab_version=__version__,
    )
    return ExternalValidationReportResponse(**report.to_dict())


@router.get("/dynare/status", response_model=DynareStatusResponse)
def dynare_status_route() -> DynareStatusResponse:
    status = dynare_status()
    return DynareStatusResponse(
        configured=status.configured,
        ready=status.ready,
        octave_executable=status.octave_executable,
        dynare_matlab_path=status.dynare_matlab_path,
        dynare_version_hint=status.dynare_version_hint,
        error=status.error,
    )


@router.get("/minsky/status", response_model=MinskyStatusResponse)
def minsky_status() -> MinskyStatusResponse:
    status = bridge_status()
    return MinskyStatusResponse(**asdict(status))


@router.post("/minsky/export", response_model=MinskyExchangeResponse)
def minsky_export(spec: ScenarioSpec) -> MinskyExchangeResponse:
    if spec.mode != "economy_zero":
        raise HTTPException(status_code=422, detail="Minsky export requires economy_zero mode")
    try:
        config = EconomyZeroConfig(
            households=spec.households,
            firms=spec.firms,
            banks=spec.banks,
            seed=spec.seed,
            initial_employment_rate=max(0.05, min(1.0, 1.0 - spec.initial_unemployment / 100.0)),
            income_tax_rate=spec.income_tax / 100.0,
            public_spending_change=spec.public_spending_change / 100.0,
            policy_rate=spec.policy_rate / 100.0,
            activation_engine=spec.activation_engine,
            household_behavior=spec.household_behavior,
            minimum_bank_capital_ratio=spec.minimum_bank_capital_ratio / 100.0,
            target_reserve_ratio=spec.target_reserve_ratio / 100.0,
            credit_supply_factor=spec.bank_credit_supply_factor,
            default_writeoff_ratio=spec.default_writeoff_ratio / 100.0,
            interbank_spread=spec.interbank_spread / 100.0,
            central_bank_penalty_spread=spec.central_bank_penalty_spread / 100.0,
            financial_guidance=tuple(
                FinancialGuidance(
                    month=item.month, minimum_capital_ratio=item.minimum_bank_capital_ratio / 100.0,
                    target_reserve_ratio=item.target_reserve_ratio / 100.0, credit_supply_factor=item.credit_supply_factor,
                    default_writeoff_ratio=item.default_writeoff_ratio / 100.0, interbank_spread=item.interbank_spread / 100.0,
                    central_bank_penalty_spread=item.central_bank_penalty_spread / 100.0,
                ) for item in spec.financial_guidance
            ),
        shocks=tuple(
            EconomicShock(
                kind=shock.kind,
                start_month=shock.start_month,
                duration_months=shock.duration_months,
                magnitude_pct=shock.magnitude_pct,
                label=shock.label,
            )
            for shock in spec.shocks
        ),
        )
        model = EconomyZeroModel(config)
        model.run(spec.months)
        export = build_godley_export(model.ledger, tick=model.tick).to_payload()
        return MinskyExchangeResponse(
            schema_name=str(export["schema"]),
            tick=int(export["tick"]),
            columns=list(export["columns"]),
            stocks=list(export["stocks"]),
            flows=list(export["flows"]),
        )
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/minsky/reconcile", response_model=MinskyReconciliationResponse)
def minsky_reconcile(request: MinskyReconciliationRequest) -> MinskyReconciliationResponse:
    """Reconcile a known Minsky template without mutating Ledger/SFC state."""

    mappings = tuple(
        MinskyGodleyCellMapping(**item.model_dump(mode="python"))
        for item in request.mappings
    )
    observed_values = dict(request.observed_values)

    if request.source_mode == "live":
        # --- template-directory hardening ---
        template_dir_env = os.environ.get("ECONOMY_LAB_MINSKY_TEMPLATE_DIR", "").strip()
        if not template_dir_env:
            raise HTTPException(
                status_code=422,
                detail=(
                    "ECONOMY_LAB_MINSKY_TEMPLATE_DIR is not configured; "
                    "set it to the trusted Minsky template directory "
                    "before using live reconciliation"
                ),
            )

        raw_path = Path(request.model_path)  # schema guarantees non-None for live

        # Best-effort symlink guard (mitigates TOCTOU as far as practical)
        if raw_path.is_symlink():
            raise HTTPException(
                status_code=422,
                detail="Symlinked template paths are not allowed",
            )

        # Canonical resolution — expanduser handles ~ ; resolve(strict=True)
        # ensures the path exists and collapses .., symlinks, etc.
        try:
            template_dir = Path(template_dir_env).expanduser().resolve(strict=True)
        except OSError:
            raise HTTPException(
                status_code=500,
                detail="Trusted template directory is not accessible",
            )
        if not template_dir.is_dir():
            raise HTTPException(
                status_code=500,
                detail="Trusted template directory is not accessible",
            )

        try:
            resolved_path = raw_path.expanduser().resolve(strict=True)
        except OSError:
            raise HTTPException(
                status_code=422,
                detail="The live .mky template must exist locally so its SHA-256 can be verified",
            )

        if not resolved_path.is_file():
            raise HTTPException(
                status_code=422,
                detail="The live .mky template must exist locally so its SHA-256 can be verified",
            )

        # Verify real .mky extension on the resolved (canonical) path
        if resolved_path.suffix.lower() != ".mky":
            raise HTTPException(
                status_code=422,
                detail="Resolved template path must have a real .mky extension",
            )

        # Containment: resolved path must be inside the trusted template directory
        try:
            resolved_path.relative_to(template_dir)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="model_path must reside inside ECONOMY_LAB_MINSKY_TEMPLATE_DIR",
            )

        # SHA-256 verification on the validated path
        digest = sha256()
        with resolved_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != request.template_sha256.lower():
            raise HTTPException(status_code=422, detail="The .mky template SHA-256 does not match")

        try:
            client = MinskyRestClient()
            client.load_model(str(resolved_path))
            if request.reset_before:
                client.reset()
            for _ in range(request.steps):
                client.step()
            observed_values = capture_minsky_values(client, mappings)
        except (OSError, ValueError) as exc:
            logger.exception("Minsky reconciliation capture failed")
            raise HTTPException(status_code=502, detail="Minsky reconciliation capture failed") from exc

    try:
        report = reconcile_godley_payload(
            request.canonical.model_dump(mode="python"),
            template_id=request.template_id,
            template_sha256=request.template_sha256,
            mappings=mappings,
            observed_values=observed_values,
            absolute_tolerance=request.absolute_tolerance,
            relative_tolerance=request.relative_tolerance,
            require_full_coverage=request.require_full_coverage,
        )
    except ReconciliationContractError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MinskyReconciliationResponse(**report.to_dict())


@router.post("/simulate", response_model=SimulationResult)
def simulate(spec: ScenarioSpec) -> SimulationResult:
    try:
        return run_simulation(spec)
    except (EngineUnavailableError, DynareUnavailableError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DynareExecutionError as exc:
        logger.exception("Dynare/Octave execution failed")
        raise HTTPException(status_code=502, detail="Dynare/Octave execution failed") from exc


def _project_store() -> ProjectStore:
    return ProjectStore()


@router.get("/storage/status", response_model=StorageStatusResponse)
def storage_status() -> StorageStatusResponse:
    return StorageStatusResponse(**_project_store().status())


@router.post("/jobs/simulations", response_model=SimulationJobRecord, status_code=202)
def create_simulation_job(request: SimulationJobCreateRequest) -> SimulationJobRecord:
    try:
        item = get_job_manager().submit(
            request.scenario,
            project_id=request.project_id,
            save_scenario=request.save_scenario,
            timeout_seconds=request.timeout_seconds,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    return SimulationJobRecord(**item)


@router.get("/jobs", response_model=list[SimulationJobSummary])
def list_simulation_jobs(
    status: JobStatus | None = None,
    project_id: str | None = None,
    limit: int = 50,
) -> list[SimulationJobSummary]:
    items = _project_store().list_jobs(status=status, project_id=project_id, limit=limit)
    return [SimulationJobSummary(**item) for item in items]


@router.get("/jobs/{job_id}", response_model=SimulationJobRecord)
def get_simulation_job(job_id: str) -> SimulationJobRecord:
    item = _project_store().get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return SimulationJobRecord(**item)


@router.post("/jobs/{job_id}/cancel", response_model=SimulationJobRecord)
def cancel_simulation_job(job_id: str) -> SimulationJobRecord:
    current = _project_store().get_job(job_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if current["status"] in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Job is already terminal")
    item = get_job_manager().cancel(job_id)
    assert item is not None
    return SimulationJobRecord(**item)


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects() -> list[ProjectSummary]:
    return [ProjectSummary(**item) for item in _project_store().list_projects()]


@router.post("/projects", response_model=ProjectRecord, status_code=201)
def create_project(request: ProjectCreateRequest) -> ProjectRecord:
    item = _project_store().create_project(
        name=request.name,
        description=request.description,
        scenario=request.scenario,
    )
    return ProjectRecord(**item)


@router.get("/projects/{project_id}", response_model=ProjectRecord)
def get_project(project_id: str) -> ProjectRecord:
    item = _project_store().get_project(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRecord(**item)


@router.put("/projects/{project_id}", response_model=ProjectRecord)
def update_project(project_id: str, request: ProjectUpdateRequest) -> ProjectRecord:
    item = _project_store().update_project(
        project_id,
        name=request.name,
        description=request.description,
        scenario=request.scenario,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRecord(**item)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    if not _project_store().delete_project(project_id):
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/projects/{project_id}/runs", response_model=list[RunSummary])
def list_project_runs(project_id: str, limit: int = 50) -> list[RunSummary]:
    store = _project_store()
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return [RunSummary(**item) for item in store.list_runs(project_id, limit=limit)]


@router.get("/runs/{run_id}", response_model=RunRecord)
def get_run(run_id: str) -> RunRecord:
    item = _project_store().get_run(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunRecord(**item)


@router.get("/runs/{run_id}/manifest", response_model=RunManifestResponse)
def get_run_manifest(run_id: str) -> RunManifestResponse:
    store = _project_store()
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    item = store.get_run_manifest(run_id)
    if item is None:
        raise HTTPException(
            status_code=409,
            detail="Run predates manifest schema v1.0 and cannot be verified",
        )
    if stable_hash(item["manifest"]) != item["manifest_hash"]:
        raise HTTPException(status_code=409, detail="Stored run manifest hash is invalid")
    return RunManifestResponse(**item)


@router.post("/runs/{run_id}/replay", response_model=ReplayResponse, status_code=201)
def replay_run(run_id: str) -> ReplayResponse:
    store = _project_store()
    source = store.get_run(run_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if source["manifest"] is None or source["manifest_hash"] is None:
        raise HTTPException(
            status_code=409,
            detail="Run predates manifest schema v1.0 and cannot be replayed",
        )
    manifest = RunManifest.model_validate(source["manifest"])
    if stable_hash(manifest) != source["manifest_hash"]:
        raise HTTPException(status_code=409, detail="Stored run manifest hash is invalid")
    if stable_hash(source["scenario"]) != manifest.scenario_hash:
        raise HTTPException(status_code=409, detail="Stored scenario does not match its manifest")
    if stable_hash(source["result"]) != manifest.result_hash:
        raise HTTPException(status_code=409, detail="Stored result does not match its manifest")

    scenario = ScenarioSpec.model_validate(source["scenario"])
    started = perf_counter()
    try:
        result = run_simulation(scenario)
    except (EngineUnavailableError, DynareUnavailableError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DynareExecutionError as exc:
        logger.exception("Dynare/Octave execution failed")
        raise HTTPException(status_code=502, detail="Dynare/Octave execution failed") from exc
    replay = store.save_run(
        project_id=source["project_id"],
        scenario=scenario,
        result=result,
        duration_ms=(perf_counter() - started) * 1000.0,
        engine_version=__version__,
        save_scenario=False,
        replay_of_run_id=run_id,
    )
    replay_manifest = RunManifest.model_validate(replay["manifest"])
    differences = runtime_differences(
        manifest.runtime_versions, replay_manifest.runtime_versions
    )
    scenario_match = manifest.scenario_hash == replay_manifest.scenario_hash
    result_match = manifest.result_hash == replay_manifest.result_hash
    experiment_match = manifest.experiment_hash == replay_manifest.experiment_hash
    environment_match = not differences
    warnings = list(dict.fromkeys(manifest.warnings + replay_manifest.warnings))
    if differences:
        warnings.append("Runtime versions changed between the source run and replay.")
    if not result_match:
        warnings.append("Replay result hash diverged from the source run.")
    status = (
        "matched"
        if scenario_match and result_match and experiment_match and environment_match
        else "environment_changed"
        if scenario_match and result_match and not environment_match
        else "diverged"
    )
    return ReplayResponse(
        source_run_id=run_id,
        replay_run=RunRecord(**replay),
        verification=ReplayVerification(
            status=status,
            scenario_match=scenario_match,
            result_match=result_match,
            experiment_match=experiment_match,
            environment_match=environment_match,
            expected_result_hash=manifest.result_hash,
            actual_result_hash=replay_manifest.result_hash,
            runtime_differences=differences,
            warnings=warnings,
        ),
    )


@router.post("/projects/{project_id}/simulate", response_model=ProjectSimulationResponse)
def simulate_project(project_id: str, request: ProjectRunRequest) -> ProjectSimulationResponse:
    store = _project_store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    spec = request.scenario or ScenarioSpec.model_validate(project["scenario"])
    started = perf_counter()
    try:
        result = run_simulation(spec)
    except (EngineUnavailableError, DynareUnavailableError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DynareExecutionError as exc:
        logger.exception("Dynare/Octave execution failed")
        raise HTTPException(status_code=502, detail="Dynare/Octave execution failed") from exc
    duration_ms = (perf_counter() - started) * 1000.0
    run = store.save_run(
        project_id=project_id,
        scenario=spec,
        result=result,
        duration_ms=duration_ms,
        engine_version=__version__,
        save_scenario=request.save_scenario,
    )
    refreshed = store.get_project(project_id)
    assert refreshed is not None
    return ProjectSimulationResponse(
        project=ProjectRecord(**refreshed),
        run=RunRecord(**run),
        result=result,
    )


@router.post(
    "/projects/{project_id}/jobs/simulations",
    response_model=SimulationJobRecord,
    status_code=202,
)
def create_project_simulation_job(
    project_id: str, request: ProjectSimulationJobCreateRequest
) -> SimulationJobRecord:
    store = _project_store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    scenario = request.scenario or ScenarioSpec.model_validate(project["scenario"])
    item = get_job_manager().submit(
        scenario,
        project_id=project_id,
        save_scenario=request.save_scenario,
        timeout_seconds=request.timeout_seconds,
    )
    return SimulationJobRecord(**item)


@router.post("/experiments/run", response_model=BatchExperimentResponse)
def run_experiment(request: BatchExperimentRequest) -> BatchExperimentResponse:
    try:
        return run_batch_experiment(request)
    except (EngineUnavailableError, DynareUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DynareExecutionError as exc:
        logger.exception("Dynare/Octave execution failed")
        raise HTTPException(status_code=502, detail="Dynare/Octave execution failed") from exc


@router.post("/projects/{project_id}/experiments", response_model=ExperimentRecord, status_code=201)
def run_project_experiment(project_id: str, request: ProjectBatchRequest) -> ExperimentRecord:
    store = _project_store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    base = request.scenario or ScenarioSpec.model_validate(project["scenario"])
    batch_request = BatchExperimentRequest(
        base=base, axis=request.axis, values=request.values, repetitions=request.repetitions, seed_step=request.seed_step
    )
    try:
        result = run_batch_experiment(batch_request)
    except (EngineUnavailableError, DynareUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DynareExecutionError as exc:
        logger.exception("Dynare/Octave execution failed")
        raise HTTPException(status_code=502, detail="Dynare/Octave execution failed") from exc
    item = store.save_experiment(project_id=project_id, result=result, engine_version=__version__)
    return ExperimentRecord(**item)


@router.get("/projects/{project_id}/experiments", response_model=list[ExperimentSummary])
def list_project_experiments(project_id: str, limit: int = 30) -> list[ExperimentSummary]:
    store = _project_store()
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return [ExperimentSummary(**item) for item in store.list_experiments(project_id, limit=limit)]


@router.get("/experiments/{experiment_id}", response_model=ExperimentRecord)
def get_experiment(experiment_id: str) -> ExperimentRecord:
    item = _project_store().get_experiment(experiment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return ExperimentRecord(**item)
