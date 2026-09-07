from fastapi import APIRouter, HTTPException, Response

from economy_lab.reporting import simple_csv_bytes, simple_xlsx_bytes
from economy_lab.simple import (
    SimpleInitialConfig, SimpleRunRequest, SimpleRunResult, SimpleScenarioInfo,
    SimpleStartResponse, SimpleStepRequest, SimpleStepResponse, SimpleToAdvancedRequest,
    SimpleToAdvancedResponse, list_simple_scenarios, run_simple, simple_to_advanced, start_simple, step_simple,
)

router = APIRouter()


def _download_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
