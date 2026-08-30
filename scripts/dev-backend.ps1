$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m uvicorn economy_lab.main:app --reload --host 127.0.0.1 --port 8765
