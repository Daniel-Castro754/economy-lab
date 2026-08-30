$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\backend"
try {
    .\.venv\Scripts\python.exe -c "from economy_lab.engines.mesa_adapter import mesa_available; from economy_lab.engines.hark_adapter import hark_available; print('Mesa:', mesa_available()); print('HARK:', hark_available())"
} finally {
    Pop-Location
}
