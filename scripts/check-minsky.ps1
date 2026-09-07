$ErrorActionPreference = "Stop"
$base = if ($env:MINSKY_REST_URL) { $env:MINSKY_REST_URL.TrimEnd('/') } else { "http://127.0.0.1:8000" }
Write-Host "Checking Minsky REST at $base"
try {
  $type = Invoke-RestMethod -Uri "$base/minsky/@type" -Method Get
  $time = Invoke-RestMethod -Uri "$base/minsky/t" -Method Get
  Write-Host "Connected: $type | t=$time" -ForegroundColor Green
} catch {
  Write-Host "Minsky REST unavailable: $($_.Exception.Message)" -ForegroundColor Yellow
  exit 1
}
