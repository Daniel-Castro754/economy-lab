$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"

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

$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
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

    $systemPython = $null
    foreach ($candidate in $candidates) {
        if (Test-PythonVersion -Command $candidate.Command -Arguments $candidate.Arguments) {
            $systemPython = $candidate
            break
        }
    }
    if ($null -eq $systemPython) {
        throw "Python >=3.12 não encontrado. Instale uma versão compatível ou crie backend\.venv manualmente."
    }

    & $systemPython.Command @($systemPython.Arguments) -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível criar backend\.venv com Python $($systemPython.Command)." }
}

if (-not (Test-Path $venvPython)) {
    throw "O ambiente virtual backend\.venv não contém Scripts\python.exe."
}
if (-not (Test-PythonVersion -Command $venvPython)) {
    throw "backend\.venv usa Python incompatível; é necessário Python >=3.12."
}

& $venvPython -m pip install -e ".[dev]"
& $venvPython -m uvicorn economy_lab.main:app --reload --host 127.0.0.1 --port 8765
