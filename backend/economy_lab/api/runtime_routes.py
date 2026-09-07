import os
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from economy_lab.runtime import manager

router = APIRouter(prefix="/runtime/engines", tags=["runtime"])


def trusted_request(request: Request):
    origin = request.headers.get("origin")
    allowed = {"tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"}
    if os.getenv("ECONOMY_LAB_RUNTIME_MODE") != "desktop-sidecar":
        allowed.update({"http://127.0.0.1:5173", "http://localhost:5173"})
    if origin and origin not in allowed:
        raise HTTPException(403, "Origem não autorizada para configurar motores locais.")


@router.get("")
def get_status():
    return manager.status()


@router.get("/log")
def get_log():
    return {"log": manager.installation_log()}


@router.post("/install", status_code=202)
def install(request: Request):
    trusted_request(request)
    try:
        return manager.start_install()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


class EnginePaths(BaseModel):
    model_config = ConfigDict(extra="forbid")
    OCTAVE_EXECUTABLE: str = ""
    DYNARE_MATLAB_PATH: str = ""
    MINSKY_REST_URL: str = ""


@router.put("/paths")
def save_paths(values: EnginePaths, request: Request):
    trusted_request(request)
    try:
        return manager.save_paths(values.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
