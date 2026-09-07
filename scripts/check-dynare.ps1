$ErrorActionPreference = "Stop"

Write-Host "Economy Lab - Dynare/Octave check" -ForegroundColor Cyan
Write-Host "OCTAVE_EXECUTABLE=$env:OCTAVE_EXECUTABLE"
Write-Host "DYNARE_MATLAB_PATH=$env:DYNARE_MATLAB_PATH"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backend = Join-Path $root "backend"
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $python = "py"
    $env:PYTHONPATH = $backend
}

Push-Location $backend
try {
    & $python -c "from economy_lab.engines.dynare_adapter import dynare_status; import json; print(json.dumps(dynare_status().__dict__, indent=2, ensure_ascii=False))"
} finally {
    Pop-Location
}
