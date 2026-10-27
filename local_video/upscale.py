"""AI 2x upscale of accepted clips before assembly (Real-ESRGAN general-x4v3 on the GPU).

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

from .config import PipelineConfig, env_int, resolve_within
from .freevideo import engine_python, freevideo_root
from .models import ProjectManifest

log = logging.getLogger("pipeline")

WORKER = Path(__file__).with_name("upscale_worker.py")
MODEL_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth"


def ai_upscale_enabled() -> bool:
    # Off by default: Real-ESRGAN general smooths skin and texture into a painted look.
    return env_int("LOCAL_VIDEO_AI_UPSCALE", 0, 0, 1) == 1


def model_path() -> Path:
    return Path(os.getenv("LOCAL_VIDEO_UPSCALE_MODEL")
                or Path(PROJECT_ROOT) / "models" / "upscale" / "realesr-general-x4v3.pth")


def ensure_model() -> Path:
    path = model_path()
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Downloading the Real-ESRGAN upscale model (5 MB) to %s", path)
    response = requests.get(MODEL_URL, timeout=120)
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


def upscaled_name(source: Path) -> str:
    stat = source.stat()
    return f"{source.stem}-{stat.st_size}-{int(stat.st_mtime)}-x2.mp4"


def upscale_clips(manifest: ProjectManifest, config: PipelineConfig) -> dict[str, Path]:
    """Return {shot id: upscaled clip}; cached per source clip so re-assembly is instant."""
    if not ai_upscale_enabled():
        return {}
    python = engine_python(freevideo_root())
    if not python.is_file():
        log.warning("AI upscale skipped: FreeVideo's Python (with CUDA PyTorch) is missing at %s", python)
        return {}
    folder = Path(manifest.project_dir) / "render" / "upscaled"
    folder.mkdir(parents=True, exist_ok=True)
    done: dict[str, Path] = {}
    pending: list[tuple[str, Path, Path]] = []
    for shot in manifest.shots:
        source = resolve_within(manifest.project_dir, shot.output)
        target = folder / upscaled_name(source)
        if target.is_file():
            done[shot.id] = target
        else:
            pending.append((shot.id, source, target))
    if not pending:
        return done
    try:
        model = ensure_model()
        stop_idle_freevideo_worker()
        pairs = [str(path) for _, source, target in pending for path in (source, target.with_suffix(".part.mp4"))]
        process = subprocess.run(
            [str(python), "-B", str(WORKER), "--model", str(model), "--ffmpeg", config.ffmpeg, *pairs],
            capture_output=True, text=True, timeout=3600,
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
    log.info("AI upscale: %s of %s clips sharpened", len(done), len(manifest.shots))
    return done
