# Build Lumin.exe and place a desktop shortcut.
# Requires: pip install pyinstaller
#
# Usage:
#   ./build_exe.ps1
#
# Output: dist/Lumin.exe + Desktop\Lumin.lnk

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Installing build dependency (pyinstaller)..."
python -m pip install pyinstaller --quiet

Write-Host "Building Lumin.exe..."
python -m PyInstaller --noconfirm --clean `
    --name Lumin `
    --onefile `
    --windowed `
    --paths "$PSScriptRoot" `
    --hidden-import groq `
    --hidden-import edge_tts `
    --hidden-import pygame `
    --hidden-import speech_recognition `
    --hidden-import pyaudio `
    --hidden-import httpx `
    --hidden-import ddgs `
    --hidden-import duckduckgo_search `
    --hidden-import lumin `
    --hidden-import lumin_config `
    --hidden-import lumin_memory `
    --hidden-import lumin_personality `
    --hidden-import lumin_theme `
    --hidden-import lumin_tools `
    --hidden-import lumin_web `
    --collect-all edge_tts `
  lumin_launcher.py

$dist = Join-Path $PSScriptRoot "dist"
$exe = Join-Path $dist "Lumin.exe"

if (-not (Test-Path $exe)) {
    throw "Build failed - $exe not found."
}

$envFile = Join-Path $dist ".env"
$envLocal = Join-Path $PSScriptRoot ".env"
$envExample = Join-Path $PSScriptRoot ".env.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envLocal) {
        Copy-Item $envLocal $envFile
        Write-Host "Copied project .env -> dist\.env"
    } elseif (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Host "Copied .env.example -> dist\.env (add your GROQ_API_KEY)"
    }
}

$dataDir = Join-Path $dist "data"
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Lumin.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $dist
$shortcut.Description = "Lumin voice assistant"
$shortcut.Save()

Write-Host ""
Write-Host "Done."
Write-Host "  Executable: $exe"
Write-Host "  Desktop shortcut: $shortcutPath"
Write-Host ""
Write-Host "Edit dist\.env with your GROQ_API_KEY before first run."
