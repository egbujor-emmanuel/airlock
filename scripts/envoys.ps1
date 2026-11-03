# Start, stop or restart both envoys in the background.
#   powershell -ExecutionPolicy Bypass -File scripts\envoys.ps1 restart
param([ValidateSet("start", "stop", "restart", "status")] [string]$Action = "restart")
$root = Split-Path $PSScriptRoot -Parent
$exe = Join-Path $root ".venv\Scripts\airlock-envoy.exe"

function Get-Envoys {
    # Match the envoy executable and its python child by path, never by a
    # command-line substring (the shell that runs this would match too).
    Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -eq $exe -or
        ($_.Name -like "python*.exe" -and $_.ParentProcessId -in
            (Get-CimInstance Win32_Process | Where-Object ExecutablePath -eq $exe).ProcessId)
    }
}

function Stop-Envoys { Get-Envoys | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } }

function Start-Envoys {
    New-Item -ItemType Directory -Force (Join-Path $root ".airlock\logs") | Out-Null
    foreach ($org in "acme", "payco") {
        $log = Join-Path $root ".airlock\logs\envoy-$org.log"
        Start-Process -FilePath $exe -ArgumentList $org -WorkingDirectory $root -WindowStyle Hidden `
            -RedirectStandardError $log -RedirectStandardOutput "$log.out"
    }
}

switch ($Action) {
    "stop" { Stop-Envoys }
    "start" { Start-Envoys }
    "restart" { Stop-Envoys; Start-Sleep -Seconds 1; Start-Envoys }
}
Start-Sleep -Seconds 2
"{0} envoy process(es) running" -f @(Get-Envoys | Where-Object ExecutablePath -eq $exe).Count
