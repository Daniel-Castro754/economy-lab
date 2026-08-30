param([switch]$SkipSimulationEngines)
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

& (Join-Path $PSScriptRoot "build-sidecar.ps1") -SkipSimulationEngines:$SkipSimulationEngines
Set-Location $root
npm install
npm --prefix frontend install
npx tauri build --config src-tauri/tauri.conf.json
