<#
.SYNOPSIS
Sets up the AWS Nuclear Button Local Worker to run silently on Windows Startup.

.DESCRIPTION
This script will:
1. Install PyInstaller and dependencies.
2. Compile the Python script (sqs_worker.py) into a standalone .exe file.
3. The .exe will be completely silent (no terminal window will pop up).
4. Create a shortcut in your Windows Startup folder so it runs every time you log in.
#>

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " AWS Nuclear Button - Windows Setup " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Ensure we are in the correct directory
$ScriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
Set-Location -Path $ScriptDir

Write-Host "`n[1/3] Installing dependencies (PyInstaller)..." -ForegroundColor Yellow
pip install pyinstaller boto3
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install dependencies. Make sure Python/pip is installed." -ForegroundColor Red
    Exit
}

Write-Host "`n[2/3] Compiling Python script to silent .exe..." -ForegroundColor Yellow
# --noconsole hides the terminal window
# --onefile packages everything into a single exe
python -m PyInstaller --noconsole --onefile sqs_worker.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to compile the script." -ForegroundColor Red
    Exit
}

# The compiled exe will be in the 'dist' folder. Let's move it out to the main folder.
$ExePath = Join-Path -Path $ScriptDir -ChildPath "sqs_worker.exe"
$DistExe = Join-Path -Path $ScriptDir -ChildPath "dist\sqs_worker.exe"

if (Test-Path $DistExe) {
    Move-Item -Path $DistExe -Destination $ExePath -Force
    # Clean up PyInstaller temp folders
    Remove-Item -Path (Join-Path -Path $ScriptDir -ChildPath "build") -Recurse -Force
    Remove-Item -Path (Join-Path -Path $ScriptDir -ChildPath "dist") -Recurse -Force
    Remove-Item -Path (Join-Path -Path $ScriptDir -ChildPath "sqs_worker.spec") -Force
} else {
    Write-Host "[ERROR] Could not find the compiled exe." -ForegroundColor Red
    Exit
}
Write-Host "[SUCCESS] Compiled successfully: $ExePath" -ForegroundColor Green

Write-Host "`n[3/3] Creating Windows Startup Shortcut..." -ForegroundColor Yellow
# Get the Startup folder path
$StartupFolder = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path -Path $StartupFolder -ChildPath "AWS_Kill_Switch.lnk"

# Create the shortcut using COM
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description = "AWS Nuclear Button Background Worker"
$Shortcut.Save()

Write-Host "[SUCCESS] Shortcut created in Startup folder!" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "[DONE] Setup Complete!" -ForegroundColor Green
Write-Host "The kill switch worker will now start silently in the background"
Write-Host "every time you turn on your laptop."
Write-Host "`nTo check if it is working, you can view the log file at:"
Write-Host (Join-Path -Path $ScriptDir -ChildPath "worker.log")
Write-Host "`nYou can manually start it now by double-clicking:"
Write-Host $ExePath
Write-Host "========================================" -ForegroundColor Cyan
