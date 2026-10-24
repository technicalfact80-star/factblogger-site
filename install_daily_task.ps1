$ErrorActionPreference = 'Stop'
$taskName = 'FactBlogger Daily Automation'
$scriptPath = Join-Path $PSScriptRoot 'run_daily_automation.bat'
$workingDir = $PSScriptRoot
if (-not (Test-Path $scriptPath)) {
    throw "Could not find run_daily_automation.bat at $scriptPath"
}
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$scriptPath`"" -WorkingDirectory $workingDir
$trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Creates FactBlogger evergreen and news drafts using local Ollama; pushes/publishes only as configured.' -Force | Out-Null
Write-Host "Created Windows scheduled task '$taskName' (daily at 9:00 AM)."
Write-Host 'Test it with: Start-ScheduledTask -TaskName "FactBlogger Daily Automation"'
Write-Host 'View logs in logs\automation.log. The PC and Ollama must be available.'
