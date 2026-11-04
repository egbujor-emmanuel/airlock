# Starts the local Switch server (switch-core) detached from Switch Console,
# so closing the Console window no longer stops it. PostgreSQL is already
# detached; this starts it too if it isn't running. Safe to run twice.
$ErrorActionPreference = "Stop"
$native = "$env:APPDATA\switchdash\local-switch-server\native"
$envFile = "$native\run\switch-core.env"
$settings = @{}
Get-Content $envFile | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    $settings[$k] = $v
}
$port = $settings["SERVER_PORT"]

function Test-Health {
    try { return (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$port/health" -TimeoutSec 3).StatusCode -eq 200 }
    catch { return $false }
}

if (Test-Health) { Write-Host "Switch server already running on http://127.0.0.1:$port"; exit 0 }

$dbUp = Get-NetTCPConnection -State Listen -LocalPort $settings["DB_PORT"] -ErrorAction SilentlyContinue
if (-not $dbUp) {
    $pgCtl = Get-ChildItem "$native\toolchain" -Recurse -Filter pg_ctl.exe | Select-Object -First 1 -ExpandProperty FullName
    Write-Host "Starting PostgreSQL..."
    # Not `& $pgCtl ... -w`: pg_ctl leaves postgres holding its output pipe, so the
    # call never returns. Start it detached and poll the port instead.
    $pgArgs = @("start", "-D", "`"$native\pgdata`"", "-l", "`"$native\logs\postgres.log`"",
                "-o", "`"-p $($settings['DB_PORT']) -h 127.0.0.1`"")
    Start-Process -FilePath $pgCtl -ArgumentList $pgArgs -WindowStyle Hidden | Out-Null
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Get-NetTCPConnection -State Listen -LocalPort $settings["DB_PORT"] -ErrorAction SilentlyContinue) { break }
    }
}

$python = Get-ChildItem "$native\switch-core" -Recurse -Filter python.exe |
    Where-Object FullName -like "*\venv\Scripts\*" | Select-Object -First 1 -ExpandProperty FullName
$psi = New-Object System.Diagnostics.ProcessStartInfo $python, "-m switch_core.main"
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.WorkingDirectory = Split-Path (Split-Path (Split-Path $python))
[void]$psi.EnvironmentVariables.Remove("ELECTRON_RUN_AS_NODE")
foreach ($k in $settings.Keys) { $psi.EnvironmentVariables[$k] = $settings[$k] }
$proc = [System.Diagnostics.Process]::Start($psi)
Write-Host "Starting switch-core (pid $($proc.Id))..."

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    if (Test-Health) { Write-Host "Switch server is running on http://127.0.0.1:$port"; exit 0 }
}
Write-Host "switch-core did not answer in 60 s. See $native\logs\switch-core.log"
exit 1
