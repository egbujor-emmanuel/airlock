# Drive desktop apps for the demo recording: focus a window, send keys, click, screenshot.
#   . .\video\drive.ps1 ; Focus-App Telegram ; Send-Keys "^f" ; Shot "path.png"
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class W {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, int d, IntPtr e);
  [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, IntPtr e);
}
"@
$ffmpeg = "ffmpeg"

function Focus-App([string]$name) {
    $p = Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object MainWindowHandle -ne 0 | Select-Object -First 1
    if (-not $p) { throw "no window for $name" }
    [W]::keybd_event(0x12, 0, 0, [IntPtr]::Zero); [W]::keybd_event(0x12, 0, 2, [IntPtr]::Zero)  # Alt tap unlocks focus
    $h = $p.MainWindowHandle
    for ($i = 0; $i -lt 5 -and [W]::GetForegroundWindow() -ne $h; $i++) {
        [W]::ShowWindow($h, 6) | Out-Null; [W]::ShowWindow($h, 3) | Out-Null   # minimise then maximise forces it forward
        (New-Object -ComObject WScript.Shell).AppActivate($p.Id) | Out-Null
        [W]::BringWindowToTop($h) | Out-Null; [W]::SetForegroundWindow($h) | Out-Null
        Start-Sleep -Milliseconds 700
    }
    if ([W]::GetForegroundWindow() -ne $h) { throw "could not bring $name to the front; no keys sent" }
    $script:target = $h
}
function Assert-Front { if ([W]::GetForegroundWindow() -ne $script:target) { throw "focus moved away; stopping" } }
function Send-Keys([string]$keys, [int]$wait = 400) { Assert-Front; [System.Windows.Forms.SendKeys]::SendWait($keys); Start-Sleep -Milliseconds $wait }
function Click([int]$x, [int]$y) { Assert-Front; [W]::SetCursorPos($x, $y); Start-Sleep -Milliseconds 120; [W]::mouse_event(2, 0, 0, 0, [IntPtr]::Zero); [W]::mouse_event(4, 0, 0, 0, [IntPtr]::Zero); Start-Sleep -Milliseconds 400 }
function Wheel([int]$x, [int]$y, [int]$notches) { [W]::SetCursorPos($x, $y); [W]::mouse_event(0x0800, 0, 0, 120 * $notches, [IntPtr]::Zero); Start-Sleep -Milliseconds 250 }
function Shot([string]$path) { & $ffmpeg -y -v error -f gdigrab -i desktop -frames:v 1 -vf "scale=1000:-1" $path }
