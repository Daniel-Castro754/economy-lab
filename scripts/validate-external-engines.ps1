param(
  [switch]$Strict,
  [switch]$StrictQualification,
  [switch]$NoSmoke,
  [switch]$NoIntegration,
  [switch]$InstallPythonEngines,
  [int]$DynareTimeout = 60,
  [double]$MinskyTimeout = 3,
  [string]$OutputDirectory = "validation-reports",
  [string]$OctaveExecutable = "",
  [string]$DynareMatlabPath = "",
  [string]$MinskyRestUrl = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
  $Python = $VenvPython
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  $Python = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $Python = "python"
} else {
  throw "Python não encontrado. Crie backend\.venv ou instale Python 3.12+."
}

if ($OctaveExecutable) { $env:OCTAVE_EXECUTABLE = $OctaveExecutable }
if ($DynareMatlabPath) { $env:DYNARE_MATLAB_PATH = $DynareMatlabPath }
if ($MinskyRestUrl) { $env:MINSKY_REST_URL = $MinskyRestUrl }

$PythonPrefix = @()
if ($Python -eq "py") { $PythonPrefix += "-3.12" }

if ($InstallPythonEngines) {
  Write-Host "Instalando/qualificando dependências Python Mesa + HARK..." -ForegroundColor Yellow
  Push-Location $Backend
  try {
    & $Python @PythonPrefix -m pip install -e ".[simulation,dev]"
    if ($LASTEXITCODE -ne 0) { throw "pip install falhou com código $LASTEXITCODE" }
  } finally { Pop-Location }
}

$OutputDir = if ([System.IO.Path]::IsPathRooted($OutputDirectory)) { $OutputDirectory } else { Join-Path $Root $OutputDirectory }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$JsonPath = Join-Path $OutputDir "external-engine-qualification-$Stamp.json"
$MarkdownPath = Join-Path $OutputDir "external-engine-qualification-$Stamp.md"
$env:PYTHONPATH = $Backend

$ArgsList = @()
$ArgsList += $PythonPrefix
$ArgsList += @("-m", "economy_lab.validation.cli", "--output", $JsonPath, "--markdown-output", $MarkdownPath, "--dynare-timeout", "$DynareTimeout", "--minsky-timeout", "$MinskyTimeout")
if ($Strict) { $ArgsList += "--strict" }
if ($StrictQualification) { $ArgsList += "--strict-qualification" }
if ($NoSmoke) { $ArgsList += "--no-smoke" }
if ($NoIntegration) { $ArgsList += "--no-integration" }

Write-Host "Economy Lab v2.11 - External Engine Qualification" -ForegroundColor Cyan
Write-Host "JSON: $JsonPath"
Write-Host "Markdown: $MarkdownPath"
& $Python @ArgsList
$Code = $LASTEXITCODE

if (Test-Path $JsonPath) { Write-Host "Evidência JSON salva: $JsonPath" -ForegroundColor Green }
if (Test-Path $MarkdownPath) { Write-Host "Relatório Markdown salvo: $MarkdownPath" -ForegroundColor Green }
exit $Code
