# Safe, repeatable Windows setup for Autonomous Video Creator.
# This script never installs or modifies ComfyUI models/nodes. It discovers and
# reuses the user's existing Pinokio/ComfyUI services.

[CmdletBinding()]
param(
    [switch]$SkipPythonInstall
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Write-Step([string]$Message) { Write-Host "`n==> $Message" -ForegroundColor Cyan }
function Write-OK([string]$Message) { Write-Host "    [OK]   $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "    [WARN] $Message" -ForegroundColor Yellow }

Write-Step "Checking Python"
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw "Python 3.10 or newer is required. Install it from python.org, then rerun setup.ps1."
}
$versionText = & python --version 2>&1
if ($versionText -notmatch "Python (\d+)\.(\d+)") {
    throw "Could not parse Python version: $versionText"
}
$major = [int]$Matches[1]
$minor = [int]$Matches[2]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    throw "Python 3.10 or newer is required; found $versionText."
}
Write-OK $versionText

Write-Step "Preparing the virtual environment"
$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    & python -m venv (Join-Path $PSScriptRoot "venv")
}
if (-not $SkipPythonInstall) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
}
Write-OK "Python environment is ready"

Write-Step "Checking FFmpeg"
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not $ffmpeg -or -not $ffprobe) {
    Write-Warn "FFmpeg/FFprobe are missing. Install with: winget install --id Gyan.FFmpeg -e"
} else {
    Write-OK "FFmpeg and FFprobe are available"
}

Write-Step "Preparing environment settings"
$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot ".env.example") -Destination $envPath
    Write-Warn ".env was created. Add Anthropic, Tavily, and ElevenLabs keys before generating."
} else {
    Write-OK ".env already exists; it was not overwritten"
}

Write-Step "Discovering existing local video services"
$serviceFound = $false
foreach ($port in @(8190, 8188)) {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:$port/system_stats" -TimeoutSec 2
        Write-OK "ComfyUI-compatible service is responding on port $port"
        $serviceFound = $true
    } catch {
        Write-Warn "No service responding on port $port"
    }
}
if (-not $serviceFound) {
    Write-Warn "Start the existing FreeVideo/ComfyUI app in Pinokio before running a project."
    Write-Warn "The pipeline will probe ports 8190 and 8188 and verify required nodes/models."
}

Write-Step "Verifying project imports"
& $venvPython -c "import anthropic, cv2, dotenv, faster_whisper, requests, tavily, websocket; import local_video; print('imports OK')"
if ($LASTEXITCODE -ne 0) {
    throw "Import check failed. Run: .\venv\Scripts\python.exe -m pip install -r requirements.txt"
}
Write-OK "Core imports succeeded"

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Cyan
Write-Host "Start the existing Pinokio FreeVideo/ComfyUI service, then run:" -ForegroundColor Green
Write-Host "  .\venv\Scripts\python.exe main.py"
Write-Host ""
Write-Host "The AI will research and choose a current topic. To supply one manually:"
Write-Host '  .\venv\Scripts\python.exe main.py "Why bioluminescent waves glow"'
