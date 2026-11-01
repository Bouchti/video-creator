"""AI 2x upscale of accepted clips before assembly (Real-ESRGAN on the GPU).

MiniMax renders 544x960; assembly needs 1080x1920. Without this pass that 2x is a plain lanczos
stretch. Models (UPSCALE_MODELS):
  x2plus       RealESRGAN_x2plus: the full RRDB network at its native 2x. Real detail on structures,
               stone, water and landscapes; the default for every local-ai film (~10 min per video).
  x4plus       RealESRGAN_x4plus: the same network at 4x, scaled back to 2x. ~4x slower than x2plus.
  general-x4v3 the compact network, 4x scaled back to 2x. Fast, but smooths skin and texture into a
               painted look.

The model runs in FreeVideo's engine Python, which already has CUDA PyTorch. MiniMax keeps its
weights resident on the GPU between shots, so its idle worker is stopped first; FreeVideo starts
a new one on its next job. Any failure falls back to the plain resize in assembly.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

import requests

from config.paths import PROJECT_ROOT

from .config import PipelineConfig, resolve_within
from .freevideo import engine_python, freevideo_root
from .models import ProjectManifest

log = logging.getLogger("pipeline")

WORKER = Path(__file__).with_name("upscale_worker.py")
_RELEASES = "https://github.com/xinntao/Real-ESRGAN/releases/download"
UPSCALE_MODELS = {
    "x2plus": {"file": "RealESRGAN_x2plus.pth", "url": f"{_RELEASES}/v0.2.1/RealESRGAN_x2plus.pth",
               "arch": "rrdb", "scale": 2, "batch": 1, "mb": 64},
    "x4plus": {"file": "RealESRGAN_x4plus.pth", "url": f"{_RELEASES}/v0.1.0/RealESRGAN_x4plus.pth",
               "arch": "rrdb", "scale": 4, "batch": 1, "mb": 64},
    "general-x4v3": {"file": "realesr-general-x4v3.pth", "url": f"{_RELEASES}/v0.2.5.0/realesr-general-x4v3.pth",
                     "arch": "compact", "scale": 4, "batch": 4, "mb": 5},
}
_OFF = {"", "0", "off", "none", "false", "no"}


def upscale_model_name(manifest: ProjectManifest | None = None) -> str | None:
    """The Real-ESRGAN model for this project, or None for the plain resize.

    A project's own `ai_upscale` setting wins (EVOLUTION_UPSCALE for evolution films); otherwise
    LOCAL_VIDEO_AI_UPSCALE: x2plus by default, 0/off for the plain resize, "1" for general-x4v3 (its old
    meaning), or a model name.
    """
    settings = manifest.settings if manifest is not None else {}
    value = settings.get("ai_upscale") if "ai_upscale" in settings else os.getenv("LOCAL_VIDEO_AI_UPSCALE", "x2plus")
    name = str(value or "").strip().lower()
    if name in _OFF:
        return None
    name = "general-x4v3" if name == "1" else name
    if name not in UPSCALE_MODELS:
        log.warning("Unknown AI upscale model %r (choose %s); using the plain resize", value, ", ".join(UPSCALE_MODELS))
        return None
    return name


def ai_upscale_enabled(manifest: ProjectManifest | None = None) -> bool:
    return upscale_model_name(manifest) is not None


def model_path(name: str = "general-x4v3") -> Path:
    override = os.getenv("LOCAL_VIDEO_UPSCALE_MODEL")
    if override and Path(override).name == UPSCALE_MODELS[name]["file"]:
        return Path(override)
    return Path(PROJECT_ROOT) / "models" / "upscale" / UPSCALE_MODELS[name]["file"]


def ensure_model(name: str = "general-x4v3") -> Path:
    path = model_path(name)
    if path.is_file():
        return path
    spec = UPSCALE_MODELS[name]
    path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading the Real-ESRGAN %s model (%s MB) to %s", name, spec["mb"], path)
    response = requests.get(spec["url"], timeout=600)
    response.raise_for_status()
    partial = path.with_suffix(".part")
    partial.write_bytes(response.content)
    partial.replace(path)
    return path


def stop_idle_freevideo_worker() -> None:
    """Release MiniMax's resident GPU memory; only called once every shot is accepted."""
    marker = "freevideo_engine.resident_worker"
    if os.name == "nt":
        command = ["powershell", "-NoProfile", "-Command",
                   f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{marker}*' }} "
                   "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"]
    else:
        command = ["pkill", "-f", marker]
    subprocess.run(command, capture_output=True, timeout=60)


def upscaled_name(source: Path, model: str = "general-x4v3") -> str:
    stat = source.stat()
    tag = "" if model == "general-x4v3" else f"-{model}"      # general-x4v3 keeps its old cache names
    return f"{source.stem}-{stat.st_size}-{int(stat.st_mtime)}{tag}-x2.mp4"


def upscale_clips(manifest: ProjectManifest, config: PipelineConfig) -> dict[str, Path]:
    """Return {shot id: upscaled clip}; cached per source clip and model so re-assembly is instant."""
    name = upscale_model_name(manifest)
    if not name:
        return {}
    python = engine_python(freevideo_root())
    if not python.is_file():
        log.warning("AI upscale skipped: FreeVideo's Python (with CUDA PyTorch) is missing at %s", python)
        return {}
    spec = UPSCALE_MODELS[name]
    folder = Path(manifest.project_dir) / "render" / "upscaled"
    folder.mkdir(parents=True, exist_ok=True)
    done: dict[str, Path] = {}
    pending: list[tuple[str, Path, Path]] = []
    for shot in manifest.shots:
        source = resolve_within(manifest.project_dir, shot.output)
        target = folder / upscaled_name(source, name)
        if target.is_file():
            done[shot.id] = target
        else:
            pending.append((shot.id, source, target))
    if not pending:
        return done
    try:
        model = ensure_model(name)
        stop_idle_freevideo_worker()
        pairs = [str(path) for _, source, target in pending for path in (source, target.with_suffix(".part.mp4"))]
        log.info("AI upscale: Real-ESRGAN %s on %s clip(s)", name, len(pending))
        process = subprocess.run(
            [str(python), "-B", str(WORKER), "--model", str(model), "--arch", spec["arch"],
             "--scale", str(spec["scale"]), "--batch", str(spec["batch"]), "--ffmpeg", config.ffmpeg, *pairs],
            capture_output=True, text=True, timeout=4 * 3600,
        )
        finished = {json.loads(line)["source"] for line in process.stdout.splitlines() if line.startswith("{")}
        for shot_id, source, target in pending:
            partial = target.with_suffix(".part.mp4")
            if str(source) in finished and partial.is_file():
                partial.replace(target)
                done[shot_id] = target
        if process.returncode != 0:
            log.warning("AI upscale stopped early; the rest use the plain resize: %s", process.stderr[-800:])
    except Exception as exc:
        log.warning("AI upscale skipped; using the plain resize: %s", exc)
    log.info("AI upscale (%s): %s of %s clips sharpened", name, len(done), len(manifest.shots))
    return done
