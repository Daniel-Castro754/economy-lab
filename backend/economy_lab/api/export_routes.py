from fastapi import APIRouter, Response

from economy_lab.core.schemas import (
    CalibrationExportRequest,
    SimulationExportRequest,
    BatchExportRequest,
)
from economy_lab.reporting import simulation_csv_bytes, batch_csv_bytes, simulation_xlsx_bytes, batch_xlsx_bytes, calibration_xlsx_bytes

router = APIRouter()


def _download_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/exports/calibration.xlsx")
def export_calibration_xlsx(request: CalibrationExportRequest) -> Response:
    return _download_response(
        calibration_xlsx_bytes(request.scenario, request.calibration, request.fit),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "economy-lab-calibration.xlsx",
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
