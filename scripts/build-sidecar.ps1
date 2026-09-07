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

function Test-PythonVersion {
    param(
        [string]$Command,
        [string[]]$Arguments = @()
    )

    $version = Get-PythonVersion -Command $Command -Arguments $Arguments
    return ($null -ne $version -and ($version.Major -gt 3 -or ($version.Major -eq 3 -and $version.Minor -ge 12)))
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

$systemPython = $null
if (-not (Test-Path $python)) {
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
        if (Test-PythonVersion -Command $candidate.Command -Arguments $candidate.Arguments) {
            $systemPython = $candidate
            break
        }
    }
    if ($null -eq $systemPython) {
        throw "Python >=3.12 não encontrado. Instale uma versão compatível para criar o ambiente do sidecar."
    }

    & $systemPython.Command @($systemPython.Arguments) -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível criar o ambiente virtual do sidecar." }
}

if (-not (Test-Path $python)) {
    throw "O ambiente virtual do sidecar não contém Scripts\python.exe."
}
if (-not (Test-PythonVersion -Command $python)) {
    throw "O ambiente virtual do sidecar usa Python incompatível; é necessário Python >=3.12. Use -RecreateVenv para recriá-lo."
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar pip." }
if ($SkipSimulationEngines) {
    & $python -m pip install -e "$backend[desktop]"
} else {
    & $python -m pip install -e "$backend[desktop,simulation]"
}
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependências do backend." }

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
if ($LASTEXITCODE -ne 0) { throw "Falha ao empacotar o backend com PyInstaller." }

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
