param([switch]$SkipSimulationEngines)
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

& (Join-Path $PSScriptRoot "build-sidecar.ps1") -SkipSimulationEngines:$SkipSimulationEngines
& (Join-Path $PSScriptRoot "prepare-runtime-tools.ps1")
Set-Location $root
npm ci
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependências desktop." }
npm --prefix frontend ci
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependências do frontend." }
npx --no-install tauri build --config src-tauri/tauri.conf.json
if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar o instalador Tauri." }
