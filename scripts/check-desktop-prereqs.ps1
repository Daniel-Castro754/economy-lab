$ErrorActionPreference = "Stop"

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

$pythonCandidates = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCandidates += [pscustomobject]@{ Command = "py"; Arguments = @("-3") }
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCandidates += [pscustomobject]@{ Command = "python"; Arguments = @() }
}
if (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pythonCandidates += [pscustomobject]@{ Command = "python3"; Arguments = @() }
}

$pythonSelection = $null
foreach ($candidate in $pythonCandidates) {
    $version = Get-PythonVersion -Command $candidate.Command -Arguments $candidate.Arguments
    if ($null -ne $version -and ($version.Major -gt 3 -or ($version.Major -eq 3 -and $version.Minor -ge 12))) {
        $pythonSelection = [pscustomobject]@{ Candidate = $candidate; Version = $version }
        break
    }
}

$failed = $false
if ($null -ne $pythonSelection) {
    Write-Host ("[OK] Python >=3.12: {0} ({1})" -f $pythonSelection.Candidate.Command, $pythonSelection.Version) -ForegroundColor Green
} else {
    Write-Host "[FALTA] Python >=3.12 (instale uma versão compatível ou configure o Python Launcher)" -ForegroundColor Yellow
    $failed = $true
}

$checks = @(
    @{ Name = "Node.js"; Command = { node --version } },
    @{ Name = "npm"; Command = { npm --version } },
    @{ Name = "Rust"; Command = { rustc --version } },
    @{ Name = "Cargo"; Command = { cargo --version } }
)

foreach ($check in $checks) {
    try {
        $value = & $check.Command 2>&1
        Write-Host ("[OK] {0}: {1}" -f $check.Name, ($value -join " ")) -ForegroundColor Green
    } catch {
        Write-Host ("[FALTA] {0}" -f $check.Name) -ForegroundColor Yellow
        $failed = $true
    }
}
if ($failed) { exit 1 }
