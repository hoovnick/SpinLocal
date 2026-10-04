# SpinLocal — Register Windows Task Scheduler job
# Run this ONCE as Administrator to set up auto-start on login.
# Right-click this file -> "Run with PowerShell" (as Admin)

$taskName = "SpinLocal"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbsPath   = Join-Path $scriptDir "start_silent.vbs"

$action   = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument "`"$vbsPath`""

$trigger  = New-ScheduledTaskTrigger -AtLogon

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit 0 `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $taskName `
    -Action   $action `
    -Trigger  $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Force

Write-Host ""
Write-Host "SpinLocal task registered successfully." -ForegroundColor Green
Write-Host "It will start automatically the next time you log into Windows."
Write-Host ""
Write-Host "To start it right now without rebooting, run:"
Write-Host "  Start-ScheduledTask -TaskName 'SpinLocal'" -ForegroundColor Cyan
Write-Host ""
Write-Host "To remove it later:"
Write-Host "  Unregister-ScheduledTask -TaskName 'SpinLocal' -Confirm:`$false" -ForegroundColor Yellow
