# setup.ps1 — One-shot setup for the Video Creator pipeline on a new Windows machine.
# Safe to re-run: every step checks before acting.
#
# USAGE:
#   Right-click PowerShell → "Run as administrator" is NOT needed.
#   From the repo root:  .\setup.ps1
#
# WHAT IT DOES:
#   1. Checks Python 3.10+
#   2. pip-installs all requirements
#   3. Installs FFmpeg via winget (if missing)
#   4. Creates .env from .env.example (if missing)
#   5. Detects Pinokio / ComfyUI and clones required custom nodes
#   6. Downloads the three Wan 2.2 model files into ComfyUI's models/ dirs
#   7. Smoke-tests all Python imports
#
# PREREQUISITE (manual, one-time):
#   Install Pinokio from https://pinokio.computer → then open Pinokio,
#   search "ComfyUI", and click Install. Launch it once so it creates the
#   models/ directory. Then run this script.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ── Helpers ──────────────────────────────────────────────────────────────────
function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    [OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    [WARN] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "    [FAIL] $msg" -ForegroundColor Red; exit 1 }
function Write-Info($msg) { Write-Host "           $msg" -ForegroundColor DarkGray }

# ── Paths ─────────────────────────────────────────────────────────────────────
# Default Pinokio install. Adjust PINOKIO_ROOT if you installed Pinokio elsewhere.
$PINOKIO_ROOT    = "C:\pinokio"
$PINOKIO_MODELS  = "$PINOKIO_ROOT\api\comfy.git\app\models"
$PINOKIO_NODES   = "$PINOKIO_ROOT\api\comfy.git\app\custom_nodes"

# ComfyUI model sub-directories (must match the paths hardcoded in comfy_workflow_wan.json)
$DIR_UNET = "$PINOKIO_MODELS\unet"
$DIR_TE   = "$PINOKIO_MODELS\text_encoders"
$DIR_VAE  = "$PINOKIO_MODELS\vae"          # final file lives at vae\split_files\vae\wan2.2_vae.safetensors


# ══════════════════════════════════════════════════════════════════════════════
# 1. Python version check
# ══════════════════════════════════════════════════════════════════════════════
Write-Step "Checking Python version"
try {
    $ver = python --version 2>&1
} catch {
    Write-Fail "Python not found on PATH. Install Python 3.10+ from https://python.org and re-run."
}
if ($ver -match "Python (\d+)\.(\d+)") {
    $major = [int]$Matches[1]; $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
        Write-Fail "Python 3.10+ required — found $ver. Install a newer version and re-run."
    }
    Write-OK $ver
} else {
    Write-Fail "Could not parse Python version: $ver"
}


# ══════════════════════════════════════════════════════════════════════════════
# 2. Python dependencies
# ══════════════════════════════════════════════════════════════════════════════
Write-Step "Installing Python dependencies (requirements.txt)"
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt
# huggingface_hub CLI is needed for model downloads; install with [cli] extras.
python -m pip install "huggingface_hub[cli]" -q
Write-OK "Python packages installed"


# ══════════════════════════════════════════════════════════════════════════════
# 3. FFmpeg
# ══════════════════════════════════════════════════════════════════════════════
Write-Step "Checking FFmpeg"
$ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegCmd) {
    Write-OK "ffmpeg already on PATH ($($ffmpegCmd.Source))"
} else {
    Write-Host "    ffmpeg not found — installing via winget..."
    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements

    # Try to add the new bin dir to the current session PATH immediately.
    $pattern = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*-full_build\bin"
    $ffBin = Resolve-Path $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ffBin) {
        $env:PATH = "$ffBin;$env:PATH"
        Write-OK "FFmpeg installed and added to PATH for this session ($ffBin)"
    } else {
        Write-OK "FFmpeg installed via winget"
    }
    Write-Warn "Open a NEW terminal after setup so ffmpeg is permanently on PATH."
}


# ══════════════════════════════════════════════════════════════════════════════
# 4. .env file
# ══════════════════════════════════════════════════════════════════════════════
Write-Step "Setting up .env"
$envPath = Join-Path $PSScriptRoot ".env"
if (Test-Path $envPath) {
    Write-OK ".env already exists — not overwriting"
} else {
    Copy-Item (Join-Path $PSScriptRoot ".env.example") $envPath
    Write-Warn ".env created from .env.example — open it and fill in your API keys:"
    Write-Info "  ANTHROPIC_API_KEY  — required for all modes (script generation, evaluation)"
    Write-Info "  ELEVENLABS_API_KEY — required for voiceover"
    Write-Info "  PEXELS_API_KEY     — required for --source pexels"
    Write-Info "  PIXABAY_API_KEY    — optional, extra free stock source for --source pexels"
    Write-Info "  COVERR_API_KEY     — optional, extra free stock source for --source pexels"
    Write-Info "  FAL_API_KEY        — required for --source hailuo (paid cloud AI)"
    Write-Info "  TAVILY_API_KEY     — required for auto topic discovery (Leader Agent)"
    Write-Info ""
    Write-Info "  COMFYUI_URL, COMFY_TIMEOUT — pre-filled with good defaults for local use"
}


# ══════════════════════════════════════════════════════════════════════════════
# 5. Pinokio / ComfyUI detection
# ══════════════════════════════════════════════════════════════════════════════
Write-Step "Detecting Pinokio / ComfyUI"
if (-not (Test-Path $PINOKIO_MODELS)) {
    Write-Warn "ComfyUI models directory not found at: $PINOKIO_MODELS"
    Write-Host ""
    Write-Host "    To finish setup, do these steps ONCE then re-run this script:" -ForegroundColor Yellow
    Write-Info "  1. Download Pinokio from https://pinokio.computer and run the installer"
    Write-Info "  2. Open Pinokio → Discover → search 'ComfyUI' → Install"
    Write-Info "  3. Click Start next to ComfyUI and wait for it to fully load (http://127.0.0.1:8188)"
    Write-Info "  4. Stop ComfyUI, then re-run:  .\setup.ps1"
    Write-Host ""
    Write-Host "    Steps 5-7 (custom nodes + model downloads) will run automatically on re-run." -ForegroundColor Yellow
    Write-Host ""
    Write-Step "Partial setup complete"
    Write-Host "  API keys, FFmpeg and Python packages are ready." -ForegroundColor Green
    Write-Host "  Re-run setup.ps1 after installing Pinokio + ComfyUI." -ForegroundColor Green
    exit 0
}
Write-OK "ComfyUI models directory found: $PINOKIO_MODELS"


# ══════════════════════════════════════════════════════════════════════════════
# 6. ComfyUI custom nodes
# ══════════════════════════════════════════════════════════════════════════════
Write-Step "Installing ComfyUI custom nodes"

# These three nodes are required for the Wan 2.2 GGUF workflow.
$CUSTOM_NODES = @(
    # GGUF model loaders (UnetLoaderGGUF, CLIPLoaderGGUF) — required by workflow
    @{ name = "ComfyUI-GGUF";            url = "https://github.com/city96/ComfyUI-GGUF.git" },
    # VHS_VideoCombine node — required to save the final mp4
    @{ name = "ComfyUI-VideoHelperSuite"; url = "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git" },
    # ExtraModels — required for Wan sampler nodes (Wan22ImageToVideoLatent, etc.)
    @{ name = "ComfyUI_ExtraModels";     url = "https://github.com/city96/ComfyUI_ExtraModels.git" }
)

foreach ($node in $CUSTOM_NODES) {
    $dest = Join-Path $PINOKIO_NODES $node.name
    if (Test-Path $dest) {
        Write-OK "$($node.name) already installed — pulling latest"
        git -C $dest pull --ff-only -q
    } else {
        Write-Host "    Cloning $($node.name)..."
        git clone --depth=1 $node.url $dest
        Write-OK "$($node.name) installed"
    }
}

# Install node Python requirements (each node may have its own requirements.txt).
$comfyPython = "$PINOKIO_ROOT\api\comfy.git\app\env\Scripts\python.exe"
if (Test-Path $comfyPython) {
    foreach ($node in $CUSTOM_NODES) {
        $nodeReqs = Join-Path $PINOKIO_NODES "$($node.name)\requirements.txt"
        if (Test-Path $nodeReqs) {
            Write-Host "    Installing requirements for $($node.name) into ComfyUI venv..."
            & $comfyPython -m pip install -r $nodeReqs -q
        }
    }
    Write-OK "Node Python requirements installed"
} else {
    Write-Warn "ComfyUI venv not found at $comfyPython — node requirements not installed."
    Write-Info "ComfyUI Manager will install them automatically on next launch."
}


# ══════════════════════════════════════════════════════════════════════════════
# 7. Wan 2.2 model downloads
#    Three files total: UNet (~5 GB), text encoder (~3.9 GB), VAE (~450 MB)
#    Total download: ~9-10 GB. This step is idempotent; already-downloaded files
#    are skipped.
#
#    HuggingFace repo references (verify at https://huggingface.co if a download
#    fails — model repos occasionally move or get renamed):
#      UNet:    city96/Wan2.2-TI2V-5B-GGUF
#      Encoder: city96/umt5-xxl-encoder-GGUF
#      VAE:     Comfy-Org/Wan_2.2_ComfyUI_repackaged
# ══════════════════════════════════════════════════════════════════════════════
Write-Step "Downloading Wan 2.2 model files (~9-10 GB total)"

# Create target directories
@($DIR_UNET, $DIR_TE, "$DIR_VAE\split_files\vae") | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Force $_ | Out-Null
    }
}

# ── 7a. UNet (Wan 2.2 TI2V-5B, Q8_0 quantization, ~5.1 GB) ──────────────────
$unetFile = "$DIR_UNET\Wan2.2-TI2V-5B-Q8_0.gguf"
if (Test-Path $unetFile) {
    Write-OK "UNet already downloaded: Wan2.2-TI2V-5B-Q8_0.gguf"
} else {
    Write-Host "    Downloading Wan2.2-TI2V-5B-Q8_0.gguf (~5.1 GB) — this takes a few minutes..."
    huggingface-cli download `
        city96/Wan2.2-TI2V-5B-GGUF `
        Wan2.2-TI2V-5B-Q8_0.gguf `
        --local-dir $DIR_UNET
    Write-OK "UNet downloaded"
}

# ── 7b. Text encoder (umt5-xxl, Q5_K_M quantization, ~3.9 GB) ───────────────
$teFile = "$DIR_TE\umt5-xxl-encoder-Q5_K_M.gguf"
if (Test-Path $teFile) {
    Write-OK "Text encoder already downloaded: umt5-xxl-encoder-Q5_K_M.gguf"
} else {
    Write-Host "    Downloading umt5-xxl-encoder-Q5_K_M.gguf (~3.9 GB)..."
    huggingface-cli download `
        city96/umt5-xxl-encoder-GGUF `
        umt5-xxl-encoder-Q5_K_M.gguf `
        --local-dir $DIR_TE
    Write-OK "Text encoder downloaded"
}

# ── 7c. VAE (wan2.2_vae.safetensors, ~450 MB) ────────────────────────────────
# The workflow expects: models/vae/split_files/vae/wan2.2_vae.safetensors
# huggingface-cli preserves the subfolder structure when we set --local-dir to
# the vae/ root, producing exactly that nested path.
$vaeFile = "$DIR_VAE\split_files\vae\wan2.2_vae.safetensors"
if (Test-Path $vaeFile) {
    Write-OK "VAE already downloaded: wan2.2_vae.safetensors"
} else {
    Write-Host "    Downloading wan2.2_vae.safetensors (~450 MB)..."
    huggingface-cli download `
        Comfy-Org/Wan_2.2_ComfyUI_repackaged `
        split_files/vae/wan2.2_vae.safetensors `
        --local-dir $DIR_VAE
    Write-OK "VAE downloaded"
}


# ══════════════════════════════════════════════════════════════════════════════
# 8. Smoke test — verify Python imports
# ══════════════════════════════════════════════════════════════════════════════
Write-Step "Verifying Python imports"
$result = python -c @"
import anthropic, requests, websocket, dotenv, faster_whisper, huggingface_hub
print('All core imports OK')
"@ 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK $result
} else {
    Write-Warn "Import check failed: $result"
    Write-Info "Try running:  python -m pip install -r requirements.txt"
}


# ══════════════════════════════════════════════════════════════════════════════
# 9. Final summary
# ══════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host ("=" * 65) -ForegroundColor Cyan
Write-Host "  SETUP COMPLETE" -ForegroundColor Cyan
Write-Host ("=" * 65) -ForegroundColor Cyan
Write-Host ""

# Check .env for unfilled keys
$unfilled = Get-Content $envPath | Where-Object { $_ -match "^[A-Z_]+=\s*$" }
if ($unfilled) {
    Write-Host "  ACTION REQUIRED: fill in these keys in .env:" -ForegroundColor Yellow
    $unfilled | ForEach-Object { Write-Info "  $_" }
    Write-Host ""
}

Write-Host "  Launch ComfyUI:" -ForegroundColor Green
Write-Info "  Open Pinokio → click Start next to ComfyUI"
Write-Info "  Wait until http://127.0.0.1:8188 responds, then run the pipeline."
Write-Host ""
Write-Host "  Run the pipeline:" -ForegroundColor Green
Write-Info "  python main.py --source comfy `"your topic`"   # local AI video (slow, best quality)"
Write-Info "  python main.py --source pexels `"your topic`"  # stock footage (instant, free)"
Write-Info "  python main.py --source hailuo `"your topic`"  # cloud AI video (fast, ~\$1.50)"
Write-Info "  python main.py                                # auto topic (uses Leader Agent)"
Write-Host ""
Write-Host "  For longer videos add --duration 90 (default is 75 seconds)." -ForegroundColor DarkGray
Write-Host ""
