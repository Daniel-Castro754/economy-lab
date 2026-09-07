from fastapi import APIRouter, HTTPException

from economy_lab.core.schemas import (
    LabProfileCreateRequest,
    ProfileSummary,
    ProfileRecord,
    ProfileApplyRequest,
    ProfileApplyResponse,
    SimulationPresetInfo,
    PresetApplyRequest,
    ScenarioSpec,
)
from economy_lab.profiles import apply_profile_to_scenario, build_lab_profile, list_simulation_presets, apply_preset
from economy_lab.storage import ProjectStore

router = APIRouter()


def _project_store() -> ProjectStore:
    return ProjectStore()


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
