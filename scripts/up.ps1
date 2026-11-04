# Bring the local Airlock stack up after a reboot:
#   1. checks the Switch server is up. Switch Console owns it: open Console, Server > Start.
#   2. both envoys
#   3. Acme's checkout app on :4242 (the endpoint PayCo delivers webhooks to)
# Don't run start-switch-server.ps1 while Console is open: Console retries its own start,
# finds the port taken, and its failed-start cleanup stops the database under you.
#   powershell -ExecutionPolicy Bypass -File scripts\up.ps1
$root = Split-Path $PSScriptRoot -Parent
try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:61913/health -TimeoutSec 3 | Out-Null }
catch { Write-Host "Switch server isn't up. Open Switch Console, go to its Server page and press Start."; exit 1 }

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
