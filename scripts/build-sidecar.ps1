param(
    [switch]$SkipSimulationEngines,
    [switch]$RecreateVenv
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backend = Join-Path $root "backend"
$venv = Join-Path $backend ".venv-desktop"
$python = Join-Path $venv "Scripts\python.exe"
$binaries = Join-Path $root "src-tauri\binaries"
$dist = Join-Path $backend "dist-sidecar"
$work = Join-Path $backend "build-sidecar"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher (py) não encontrado. Instale Python 3.12 para Windows."
}
if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) {
    throw "rustc não encontrado. Instale o toolchain Rust/MSVC exigido pelo Tauri."
}

$rustInfo = & rustc -vV
$hostLine = $rustInfo | Where-Object { $_ -like "host:*" } | Select-Object -First 1
if (-not $hostLine) {
    throw "Não foi possível descobrir o target triple do Rust."
}
$triple = ($hostLine -replace '^host:\s*', '').Trim()

if ($RecreateVenv -and (Test-Path $venv)) {
    Remove-Item -Recurse -Force $venv
}
if (-not (Test-Path $python)) {
    py -3.12 -m venv $venv
}

& $python -m pip install --upgrade pip
if ($SkipSimulationEngines) {
    & $python -m pip install -e "$backend[desktop]"
} else {
    & $python -m pip install -e "$backend[desktop,simulation]"
}

New-Item -ItemType Directory -Force -Path $binaries | Out-Null
Remove-Item -Recurse -Force $dist,$work -ErrorAction SilentlyContinue

$pyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--name", "economy-lab-backend",
    "--paths", $backend,
    "--distpath", $dist,
    "--workpath", $work,
    "--specpath", $work,
    "--collect-all", "uvicorn",
    "--collect-all", "scipy",
    (Join-Path $backend "economy_lab\desktop_entry.py")
)

if (-not $SkipSimulationEngines) {
    $pyInstallerArgs = $pyInstallerArgs[0..($pyInstallerArgs.Count-2)] + @(
        "--collect-all", "mesa",
        "--collect-all", "HARK"
    ) + $pyInstallerArgs[-1]
}

& $python -m PyInstaller @pyInstallerArgs

$isWin = $env:OS -eq "Windows_NT"
$sourceName = if ($isWin) { "economy-lab-backend.exe" } else { "economy-lab-backend" }
$targetName = if ($isWin) { "economy-lab-backend-$triple.exe" } else { "economy-lab-backend-$triple" }
$source = Join-Path $dist $sourceName
$target = Join-Path $binaries $targetName
if (-not (Test-Path $source)) {
    throw "PyInstaller não gerou o sidecar esperado em $source"
}
Copy-Item -Force $source $target
Write-Host "Sidecar pronto: $target" -ForegroundColor Green
