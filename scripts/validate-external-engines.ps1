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

function Get-PythonVersion {
  param(
    [string]$Command,
    [string[]]$Arguments = @()
  )

  try {
    $output = (& $Command @Arguments --version 2>&1 | Out-String).Trim()
  } catch {
    return $null
  }
  if ($LASTEXITCODE -ne 0) { return $null }

  $match = [regex]::Match($output, 'Python\s+(\d+)\.(\d+)(?:\.(\d+))?')
  if (-not $match.Success) { return $null }
  $major = $match.Groups[1].Value
  $minor = $match.Groups[2].Value
  $patch = if ($match.Groups[3].Success) { $match.Groups[3].Value } else { "0" }
  return [version]::Parse("$major.$minor.$patch")
}

$Python = $null
$PythonPrefix = @()
if (Test-Path $VenvPython) {
  $version = Get-PythonVersion -Command $VenvPython
  if ($null -eq $version -or -not ($version.Major -gt 3 -or ($version.Major -eq 3 -and $version.Minor -ge 12))) {
    throw "backend\.venv usa Python incompatível; é necessário Python >=3.12."
  }
  $Python = $VenvPython
} else {
  $candidates = @()
  if (Get-Command py -ErrorAction SilentlyContinue) {
    $candidates += [pscustomobject]@{ Command = "py"; Arguments = @("-3") }
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    $candidates += [pscustomobject]@{ Command = "python"; Arguments = @() }
  }
  if (Get-Command python3 -ErrorAction SilentlyContinue) {
    $candidates += [pscustomobject]@{ Command = "python3"; Arguments = @() }
  }
  foreach ($candidate in $candidates) {
    $version = Get-PythonVersion -Command $candidate.Command -Arguments $candidate.Arguments
    if ($null -ne $version -and ($version.Major -gt 3 -or ($version.Major -eq 3 -and $version.Minor -ge 12))) {
      $Python = $candidate.Command
      $PythonPrefix = $candidate.Arguments
      break
    }
  }
  if ($null -eq $Python) {
    throw "Python >=3.12 não encontrado. Crie backend\.venv ou instale uma versão compatível."
  }
}

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

Write-Host "Economy Lab - External Engine Qualification" -ForegroundColor Cyan
Write-Host "JSON: $JsonPath"
Write-Host "Markdown: $MarkdownPath"
& $Python @ArgsList
$Code = $LASTEXITCODE

if (Test-Path $JsonPath) { Write-Host "Evidência JSON salva: $JsonPath" -ForegroundColor Green }
if (Test-Path $MarkdownPath) { Write-Host "Relatório Markdown salvo: $MarkdownPath" -ForegroundColor Green }
exit $Code
