param([switch]$SkipSimulationEngines)
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")

Write-Host "Preparando backend sidecar local..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "build-sidecar.ps1") -SkipSimulationEngines:$SkipSimulationEngines

Set-Location $root
npm install
npm --prefix frontend install
Write-Host "Abrindo Economy Lab. O backend será iniciado automaticamente pelo Tauri." -ForegroundColor Green
npx tauri dev --config src-tauri/tauri.conf.json
