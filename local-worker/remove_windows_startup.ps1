<#
.SYNOPSIS
Removes the AWS Nuclear Button Local Worker from Windows Startup and stops the background process.

.DESCRIPTION
This script will:
1. Kill the running sqs_worker.exe in the background (if it is currently running).
2. Delete the shortcut from your Windows Startup folder so it no longer starts on boot.
#>

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " AWS Nuclear Button - Uninstall Startup " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n[1/2] Stopping any running worker processes..." -ForegroundColor Yellow
$ProcessName = "sqs_worker"
$Processes = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue

if ($Processes) {
    Stop-Process -Name $ProcessName -Force
    Write-Host "[SUCCESS] Stopped running kill switch worker!" -ForegroundColor Green
} else {
    Write-Host "[INFO] The worker is not currently running." -ForegroundColor Gray
}

Write-Host "`n[2/2] Removing Windows Startup Shortcut..." -ForegroundColor Yellow
$StartupFolder = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path -Path $StartupFolder -ChildPath "AWS_Kill_Switch.lnk"

if (Test-Path $ShortcutPath) {
    Remove-Item -Path $ShortcutPath -Force
    Write-Host "[SUCCESS] Shortcut removed from Startup folder!" -ForegroundColor Green
} else {
    Write-Host "[INFO] Shortcut not found in Startup folder (already removed)." -ForegroundColor Gray
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "[DONE] Uninstall Complete!" -ForegroundColor Green
Write-Host "The kill switch worker has been stopped and will no longer"
Write-Host "start when you turn on your laptop."
Write-Host "========================================" -ForegroundColor Cyan
