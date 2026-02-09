# Quick test for SetThreadExecutionState API
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class SleepTest {
    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);

    public const uint ES_CONTINUOUS       = 0x80000000;
    public const uint ES_SYSTEM_REQUIRED  = 0x00000001;
    public const uint ES_DISPLAY_REQUIRED = 0x00000002;

    public static uint PreventSleep() {
        return SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED);
    }

    public static uint AllowSleep() {
        return SetThreadExecutionState(ES_CONTINUOUS);
    }
}
"@

$result = [SleepTest]::PreventSleep()
if ($result -ne 0) {
    Write-Host "SUCCESS: SetThreadExecutionState works correctly (returned $result)"
} else {
    Write-Host "FAIL: SetThreadExecutionState returned 0"
}

# Clean up
[SleepTest]::AllowSleep() | Out-Null
Write-Host "Cleaned up - sleep prevention cleared"
