from dataclasses import asdict
from hashlib import sha256
import os
from pathlib import Path
import secrets
from time import perf_counter


from fastapi import APIRouter, Header, HTTPException, Request, Response

from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.ai.scenario_builder import compile_scenario_prompt
from economy_lab.ai.model_builder import build_model_from_prompt, compile_model_to_scenario, validate_model_candidate, model_provider_catalog
from economy_lab.core.shocks import EconomicShock
from economy_lab.finance import FinancialGuidance
from economy_lab.core.schemas import (
    AuthorityRegistryEntry,
    AuthorityPlanEntry,
    DynareStatusResponse,
    HealthResponse,
    MinskyExchangeResponse,
    MinskyReconciliationRequest,
    MinskyReconciliationResponse,
    MinskyStatusResponse,
    ScenarioDraftRequest,
    ScenarioDraftResponse,
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
    HubModuleInfo,
    HubToolInfo,
    SimulationExportRequest,
    BatchExportRequest,
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
    LabProfileCreateRequest,
    ProfileSummary,
    ProfileRecord,
    ProfileApplyRequest,
    ProfileApplyResponse,
    SimulationPresetInfo,
    PresetApplyRequest,
    ExternalValidationRequest,
    ExternalValidationReportResponse,
    DataFetchRequest, EconomicSeriesResponse, DataSourceCatalogItem, DataCacheStatus,
    CalibrationRequest, CalibrationResponse, CalibrationExportRequest, CalibrationFitRequest, CalibrationFitResponse,
    ModelDraftRequest, ModelDraftResponse, ModelCandidateValidationRequest,
    ModelCandidateValidationResponse, ModelToScenarioRequest, ModelToScenarioResponse, ModelProviderInfo,
)
from economy_lab.core.simulation import run_simulation
from economy_lab.core.reproducibility import stable_hash, runtime_differences
from economy_lab.core.authority import authority_registry_payload, authority_plan_payload
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
from economy_lab.modules import list_modules, get_module, list_tools, get_tool
from economy_lab.reporting import simulation_csv_bytes, batch_csv_bytes, simulation_xlsx_bytes, batch_xlsx_bytes, calibration_xlsx_bytes, simple_csv_bytes, simple_xlsx_bytes
from economy_lab.labs import dynare_template, minsky_command, run_dynare_lab, run_hark_lab, run_mesa_lab, run_mesa_component_lab, run_minsky_financial_controller
from economy_lab.profiles import apply_profile_to_scenario, build_lab_profile, list_simulation_presets, apply_preset
from economy_lab.validation import validate_external_engines
from economy_lab.data import data_catalog, fetch_economic_series, cache_status
from economy_lab.calibration import evaluate_calibration, fit_calibration

from economy_lab.simple import (
    SimpleInitialConfig, SimpleRunRequest, SimpleRunResult, SimpleScenarioInfo,
    SimpleStartResponse, SimpleStepRequest, SimpleStepResponse, SimpleToAdvancedRequest,
    SimpleToAdvancedResponse, list_simple_scenarios, run_simple, simple_to_advanced, start_simple, step_simple,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        engine_version="2.13.0",
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




@router.get("/modules", response_model=list[HubModuleInfo])
def modules_catalog() -> list[HubModuleInfo]:
    return [HubModuleInfo(**item) for item in list_modules()]


@router.get("/modules/{module_id}", response_model=HubModuleInfo)
def module_detail(module_id: str) -> HubModuleInfo:
    item = get_module(module_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return HubModuleInfo(**item)


@router.get("/tools", response_model=list[HubToolInfo])
def tools_catalog(module_id: str | None = None) -> list[HubToolInfo]:
    return [HubToolInfo(**item) for item in list_tools(module_id)]


@router.get("/tools/{tool_id}", response_model=HubToolInfo)
def tool_detail(tool_id: str) -> HubToolInfo:
    item = get_tool(tool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return HubToolInfo(**item)


@router.get("/authority/registry", response_model=list[AuthorityRegistryEntry])
def authority_registry() -> list[AuthorityRegistryEntry]:
    """Return the frozen canonical-variable ownership contract."""
    return [AuthorityRegistryEntry(**item) for item in authority_registry_payload()]


@router.post("/authority/plan", response_model=list[AuthorityPlanEntry])
def authority_plan(spec: ScenarioSpec) -> list[AuthorityPlanEntry]:
    """Resolve the active canonical owner for each field in a scenario."""
    return [AuthorityPlanEntry(**item) for item in authority_plan_payload(spec)]


@router.get("/profiles", response_model=list[ProfileSummary])
def list_profiles(kind: str | None = None, module_id: str | None = None) -> list[ProfileSummary]:
    return [ProfileSummary(**item) for item in _project_store().list_profiles(kind=kind, module_id=module_id)]


@router.post("/profiles/from-lab", response_model=ProfileRecord, status_code=201)
def create_profile_from_lab(request: LabProfileCreateRequest) -> ProfileRecord:
    try:
        built = build_lab_profile(module_id=request.module_id, inputs=request.inputs, outputs=request.outputs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    item = _project_store().create_profile(
        name=request.name, description=request.description, kind=built["kind"], module_id=built["module_id"],
        compatibility=built["compatibility"], payload=built["payload"], scenario_patch=built["scenario_patch"],
    )
    return ProfileRecord(**item)


@router.get("/profiles/{profile_id}", response_model=ProfileRecord)
def get_profile(profile_id: str) -> ProfileRecord:
    item = _project_store().get_profile(profile_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileRecord(**item)


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: str) -> None:
    if not _project_store().delete_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")


@router.post("/profiles/{profile_id}/apply", response_model=ProfileApplyResponse)
def apply_profile(profile_id: str, request: ProfileApplyRequest) -> ProfileApplyResponse:
    item = _project_store().get_profile(profile_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        scenario, changes = apply_profile_to_scenario(request.scenario, item)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ProfileApplyResponse(profile=ProfileSummary(**item), scenario=scenario, changes=changes)


@router.get("/simulation/presets", response_model=list[SimulationPresetInfo])
def simulation_presets() -> list[SimulationPresetInfo]:
    return [SimulationPresetInfo(**item) for item in list_simulation_presets()]


@router.post("/simulation/presets/{preset_id}/apply", response_model=ScenarioSpec)
def apply_simulation_preset(preset_id: str, request: PresetApplyRequest) -> ScenarioSpec:
    try:
        return apply_preset(request.scenario, preset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preset not found") from exc



@router.get("/data/catalog", response_model=list[DataSourceCatalogItem])
def economic_data_catalog() -> list[DataSourceCatalogItem]:
    return [DataSourceCatalogItem(**item) for item in data_catalog()]


@router.get("/data/cache/status", response_model=DataCacheStatus)
def economic_data_cache_status() -> DataCacheStatus:
    return DataCacheStatus(**cache_status())


@router.post("/data/fetch", response_model=EconomicSeriesResponse)
def economic_data_fetch(request: DataFetchRequest) -> EconomicSeriesResponse:
    try:
        return fetch_economic_series(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"External data source failed: {exc}") from exc


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


@router.post("/exports/calibration.xlsx")
def export_calibration_xlsx(request: CalibrationExportRequest) -> Response:
    return _download_response(
        calibration_xlsx_bytes(request.scenario, request.calibration, request.fit),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "economy-lab-calibration.xlsx",
    )


def _download_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/exports/simulation.csv")
def export_simulation_csv(request: SimulationExportRequest) -> Response:
    return _download_response(
        simulation_csv_bytes(request.result),
        "text/csv; charset=utf-8",
        "economy-lab-simulation.csv",
    )


@router.post("/exports/simulation.xlsx")
def export_simulation_xlsx(request: SimulationExportRequest) -> Response:
    return _download_response(
        simulation_xlsx_bytes(request.scenario, request.result),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "economy-lab-simulation.xlsx",
    )


@router.post("/exports/batch.csv")
def export_batch_csv(request: BatchExportRequest) -> Response:
    return _download_response(
        batch_csv_bytes(request.result),
        "text/csv; charset=utf-8",
        "economy-lab-experiment.csv",
    )


@router.post("/exports/batch.xlsx")
def export_batch_xlsx(request: BatchExportRequest) -> Response:
    return _download_response(
        batch_xlsx_bytes(request.result),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "economy-lab-experiment.xlsx",
    )


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
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
        raise HTTPException(status_code=502, detail=f"Minsky REST command failed: {exc}") from exc


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
        raise HTTPException(status_code=502, detail=f"Minsky financial controller failed: {exc}") from exc


@router.post("/validation/external-engines", response_model=ExternalValidationReportResponse)
def validate_external_engines_route(request: ExternalValidationRequest) -> ExternalValidationReportResponse:
    report = validate_external_engines(
        request.engines,
        smoke_tests=request.smoke_tests,
        integration_tests=request.integration_tests,
        dynare_timeout_seconds=request.dynare_timeout_seconds,
        minsky_timeout_seconds=request.minsky_timeout_seconds,
        economy_lab_version="2.13.0",
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
        template_path = Path(request.model_path or "")
        if not template_path.is_file():
            raise HTTPException(
                status_code=422,
                detail="The live .mky template must exist locally so its SHA-256 can be verified",
            )
        digest = sha256()
        with template_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != request.template_sha256.lower():
            raise HTTPException(status_code=422, detail="The .mky template SHA-256 does not match")

        try:
            client = MinskyRestClient()
            client.load_model(str(template_path))
            if request.reset_before:
                client.reset()
            for _ in range(request.steps):
                client.step()
            observed_values = capture_minsky_values(client, mappings)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"Minsky reconciliation capture failed: {exc}") from exc

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


@router.post("/scenario/compile", response_model=ScenarioDraftResponse)
def compile_scenario(request: ScenarioDraftRequest) -> ScenarioDraftResponse:
    try:
        spec, assumptions, changes = compile_scenario_prompt(request.prompt, request.base)
        return ScenarioDraftResponse(
            recognized_changes=changes,
            assumptions=assumptions,
            spec=spec,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/model/providers", response_model=list[ModelProviderInfo])
def model_providers() -> list[ModelProviderInfo]:
    return [ModelProviderInfo(**item) for item in model_provider_catalog()]


@router.post("/model/compile", response_model=ModelDraftResponse)
def compile_model(request: ModelDraftRequest) -> ModelDraftResponse:
    try:
        model, scenario, compilation, proposal = build_model_from_prompt(request.prompt, request.base)
        return ModelDraftResponse(
            provider=proposal.provider,
            recognized_changes=list(proposal.recognized),
            provider_assumptions=list(proposal.assumptions),
            model_spec=model,
            compiled_scenario=scenario,
            compilation=compilation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/model/validate", response_model=ModelCandidateValidationResponse)
def validate_model_candidate_route(request: ModelCandidateValidationRequest) -> ModelCandidateValidationResponse:
    try:
        model = validate_model_candidate(request.candidate)
        scenario, compilation = compile_model_to_scenario(model)
        return ModelCandidateValidationResponse(model_spec=model, compiled_scenario=scenario, compilation=compilation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/model/to-scenario", response_model=ModelToScenarioResponse)
def model_to_scenario(request: ModelToScenarioRequest) -> ModelToScenarioResponse:
    try:
        scenario, compilation = compile_model_to_scenario(request.model_spec, request.base_scenario)
        return ModelToScenarioResponse(scenario=scenario, compilation=compilation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/simple/scenarios", response_model=list[SimpleScenarioInfo])
def simple_scenarios() -> list[SimpleScenarioInfo]:
    return list_simple_scenarios()


@router.post("/simple/start", response_model=SimpleStartResponse)
def simple_start(config: SimpleInitialConfig) -> SimpleStartResponse:
    try:
        return start_simple(config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/simple/step", response_model=SimpleStepResponse)
def simple_step(request: SimpleStepRequest) -> SimpleStepResponse:
    try:
        return step_simple(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/simple/run", response_model=SimpleRunResult)
def simple_run(request: SimpleRunRequest) -> SimpleRunResult:
    try:
        return run_simple(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/simple/to-advanced", response_model=SimpleToAdvancedResponse)
def simple_convert_to_advanced(request: SimpleToAdvancedRequest) -> SimpleToAdvancedResponse:
    return simple_to_advanced(request)


@router.post("/exports/simple.csv")
def export_simple_csv(request: SimpleRunResult) -> Response:
    return _download_response(simple_csv_bytes(request), "text/csv; charset=utf-8", "economy-lab-simple.csv")


@router.post("/exports/simple.xlsx")
def export_simple_xlsx(request: SimpleRunResult) -> Response:
    return _download_response(
        simple_xlsx_bytes(request),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "economy-lab-simple.xlsx",
    )


@router.post("/simulate", response_model=SimulationResult)
def simulate(spec: ScenarioSpec) -> SimulationResult:
    try:
        return run_simulation(spec)
    except (EngineUnavailableError, DynareUnavailableError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DynareExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    replay = store.save_run(
        project_id=source["project_id"],
        scenario=scenario,
        result=result,
        duration_ms=(perf_counter() - started) * 1000.0,
        engine_version="2.13.0",
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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    duration_ms = (perf_counter() - started) * 1000.0
    run = store.save_run(
        project_id=project_id,
        scenario=spec,
        result=result,
        duration_ms=duration_ms,
        engine_version="2.13.0",
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
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    item = store.save_experiment(project_id=project_id, result=result, engine_version="2.13.0")
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
