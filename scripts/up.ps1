# Bring the whole local Airlock stack up after a reboot, in order:
#   1. the Switch server (and its database), detached from Switch Console
#   2. both envoys
#   3. Acme's checkout app on :4242 (the endpoint PayCo delivers webhooks to)
# Switch Console must be open for the managed agents (claude-acme, opencode-payco).
#   powershell -ExecutionPolicy Bypass -File scripts\up.ps1
$root = Split-Path $PSScriptRoot -Parent
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start-switch-server.ps1")
if ($LASTEXITCODE -ne 0) { Write-Host "Switch server didn't start"; exit 1 }

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "envoys.ps1") restart

$app = Join-Path $root "demo\acme-app"
if (-not (Get-NetTCPConnection -State Listen -LocalPort 4242 -ErrorAction SilentlyContinue)) {
    $envVars = @{}
    Get-Content (Join-Path $app ".env") | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object {
        $k, $v = $_ -split '=', 2; $envVars[$k] = $v
    }
    # Start-Process with redirected output: an inherited console handle would keep
    # whatever launched this script waiting for the app to exit.
    foreach ($k in $envVars.Keys) { [Environment]::SetEnvironmentVariable($k, $envVars[$k], "Process") }
    $logs = Join-Path $root ".airlock\logs"
    Start-Process -FilePath "node" -ArgumentList "server.js" -WorkingDirectory $app -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "acme-app.log") -RedirectStandardError (Join-Path $logs "acme-app.err.log")
    Write-Host "Acme checkout app started on :4242"
} else {
    Write-Host "Acme checkout app already on :4242"
}
if (-not (Get-Process | Where-Object ProcessName -like "Switch Console*")) {
    Write-Host "Open Switch Console so claude-acme and opencode-payco can run."
}
