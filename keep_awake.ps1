# ============================================================================
# Keep System Awake - PowerShell Script
# 
# This script prevents Windows from entering sleep/standby by calling
# the Windows SetThreadExecutionState API every 60 seconds.
#
# Why NOT SendKeys:
#   SendKeys only sends keystrokes to the foreground window and does NOT
#   reliably prevent Windows sleep. When run minimized/hidden, it has no
#   effect. SetThreadExecutionState is the correct Windows API.
#
# Flags used:
#   ES_CONTINUOUS (0x80000000) - keep the state until cleared
#   ES_SYSTEM_REQUIRED (0x00000001) - prevent system sleep
#   ES_DISPLAY_REQUIRED (0x00000002) - prevent display off (optional)
#
# No admin privileges required.
# 
# Usage:
#   powershell -ExecutionPolicy Bypass -File keep_awake.ps1
# 
# Or run from start_monitor_keepawake.bat / run_rebound_live.bat
# ============================================================================

Write-Host "============================================================================"
Write-Host "Keep System Awake - Background Process"
Write-Host "============================================================================"
Write-Host ""
Write-Host "This script prevents Windows from sleeping using SetThreadExecutionState API."
Write-Host "Press Ctrl+C to stop."
Write-Host ""

# Import SetThreadExecutionState from kernel32.dll
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class SleepPreventer {
    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);

    // Flags
    public const uint ES_CONTINUOUS       = 0x80000000;
    public const uint ES_SYSTEM_REQUIRED  = 0x00000001;
    public const uint ES_DISPLAY_REQUIRED = 0x00000002;

    public static uint PreventSleep() {
        return SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        );
    }

    public static uint AllowSleep() {
        return SetThreadExecutionState(ES_CONTINUOUS);
    }
}
"@

# Interval in seconds between refresh calls
$interval = 60

# Set initial state
$result = [SleepPreventer]::PreventSleep()
if ($result -eq 0) {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] WARNING: SetThreadExecutionState failed!" -ForegroundColor Red
} else {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Keep-awake started (SetThreadExecutionState). Refreshing every $interval seconds..."
}

# Register cleanup handler to restore normal sleep behavior on exit
Register-EngineEvent PowerShell.Exiting -Action {
    [SleepPreventer]::AllowSleep()
    Write-Host "Sleep prevention cleared."
} | Out-Null

# Main loop - periodically refresh the execution state
# This ensures the flag stays active even if Windows resets it
while ($true) {
    try {
        [SleepPreventer]::PreventSleep() | Out-Null
        # Uncomment the line below if you want to see activity
        # Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Keep-awake refreshed"
        Start-Sleep -Seconds $interval
    }
    catch {
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Error: $_" -ForegroundColor Red
        Start-Sleep -Seconds 5
    }
}
