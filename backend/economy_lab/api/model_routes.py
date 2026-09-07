from fastapi import APIRouter, HTTPException

from economy_lab.ai.scenario_builder import compile_scenario_prompt
from economy_lab.ai.model_builder import (
    build_model_from_prompt,
    compile_model_to_scenario,
    validate_model_candidate,
    model_provider_catalog,
)
from economy_lab.core.schemas import (
    ScenarioDraftRequest,
    ScenarioDraftResponse,
    ModelDraftRequest,
    ModelDraftResponse,
    ModelCandidateValidationRequest,
    ModelCandidateValidationResponse,
    ModelToScenarioRequest,
    ModelToScenarioResponse,
    ModelProviderInfo,
)

router = APIRouter()


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
