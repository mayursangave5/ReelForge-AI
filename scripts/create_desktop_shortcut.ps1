# Create Desktop Shortcut for ReelForge AI Studio
$ErrorActionPreference = "Stop"

$projectRoot = "S:\REEL"
$batPath = Join-Path $projectRoot "Launch_ReelForge.bat"

if (-not (Test-Path $batPath)) {
    Write-Error "Launcher BAT file not found at: $batPath"
    exit 1
}

$wsh = New-Object -ComObject WScript.Shell
$desktopPaths = @(
    [Environment]::GetFolderPath('Desktop'),
    "C:\Users\sanga\Desktop"
) | Select-Object -Unique

$createdShortcuts = @()

foreach ($desktop in $desktopPaths) {
    if (Test-Path $desktop) {
        $shortcutPath = Join-Path $desktop "ReelForge AI Studio.lnk"
        $shortcut = $wsh.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $batPath
        $shortcut.WorkingDirectory = $projectRoot
        $shortcut.Description = "Launch ReelForge AI Studio Streamlit Dashboard"
        # Video production / film icon (shell32.dll index 14 is the video/film icon)
        $shortcut.IconLocation = "%SystemRoot%\System32\shell32.dll,14"
        $shortcut.WindowStyle = 1 # Normal window
        $shortcut.Save()
        $createdShortcuts += $shortcutPath
        Write-Host "[SUCCESS] Created shortcut: $shortcutPath"
    }
}

Write-Host "Target: $batPath"
Write-Host "Working Directory: $projectRoot"
Write-Host "Done!"
