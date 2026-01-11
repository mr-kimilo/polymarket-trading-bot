# ============================================================================
# Keep System Awake - PowerShell Script
# 
# This script keeps the system awake by simulating keyboard activity.
# It runs in the background and sends a keystroke every 60 seconds.
# 
# This is an alternative method that doesn't require admin privileges
# to change power settings.
# 
# Usage:
#   powershell -ExecutionPolicy Bypass -File keep_awake.ps1
# 
# Or run from start_monitor_keepawake.bat
# ============================================================================

Write-Host "============================================================================"
Write-Host "Keep System Awake - Background Process"
Write-Host "============================================================================"
Write-Host ""
Write-Host "This script prevents Windows from sleeping by simulating activity."
Write-Host "Press Ctrl+C to stop."
Write-Host ""

# Load Windows Forms assembly for sending keys
Add-Type -AssemblyName System.Windows.Forms

# Function to simulate a key press (F15 key - doesn't affect anything visible)
function Send-KeepAwake {
    # Use F15 key - it doesn't interfere with normal operations
    [System.Windows.Forms.SendKeys]::SendWait("{F15}")
}

# Interval in seconds
$interval = 60

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Keep-awake started. Sending F15 every $interval seconds..."

# Main loop
while ($true) {
    try {
        Send-KeepAwake
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        # Uncomment the line below if you want to see activity
        # Write-Host "[$timestamp] Keep-awake pulse sent"
        Start-Sleep -Seconds $interval
    }
    catch {
        Write-Host "Error: $_"
        Start-Sleep -Seconds 5
    }
}
