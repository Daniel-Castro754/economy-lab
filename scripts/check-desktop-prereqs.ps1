$ErrorActionPreference = "Stop"
$checks = @(
    @{ Name = "Python 3.12"; Command = { py -3.12 --version } },
    @{ Name = "Node.js"; Command = { node --version } },
    @{ Name = "npm"; Command = { npm --version } },
    @{ Name = "Rust"; Command = { rustc --version } },
    @{ Name = "Cargo"; Command = { cargo --version } }
)

$failed = $false
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
