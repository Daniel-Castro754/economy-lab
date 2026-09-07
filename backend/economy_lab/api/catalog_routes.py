from fastapi import APIRouter, HTTPException

from economy_lab.core.schemas import (
    AuthorityRegistryEntry,
    AuthorityPlanEntry,
    HubModuleInfo,
    HubToolInfo,
    ScenarioSpec,
)
from economy_lab.core.authority import authority_registry_payload, authority_plan_payload
from economy_lab.modules import list_modules, get_module, list_tools, get_tool

router = APIRouter()


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
