"""Fail-fast production checks performed before any expensive shot generation."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agents import claude_cli
from agents.voice import credit_status, elevenlabs_keys

from .config import PipelineConfig
from .models import ProjectManifest


def _tool_ok(tool: str) -> bool:
    try:
        return subprocess.run(
            [tool, "-version"], capture_output=True, timeout=10,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_preflight(
    manifest: ProjectManifest,
    config: PipelineConfig,
    backends: dict[str, Any],
    *,
    require_visual_qc: bool = True,
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []

    checks["ffmpeg"] = _tool_ok(config.ffmpeg)
    checks["ffprobe"] = _tool_ok(config.ffprobe)
    if not checks["ffmpeg"]:
        problems.append("FFmpeg is unavailable")
    if not checks["ffprobe"]:
        problems.append("FFprobe is unavailable")

    sequence = ["minimax", "wan"] if manifest.preferred_backend == "auto" else [manifest.preferred_backend]
    backend_status = {}
    for name in sequence:
        adapter = backends.get(name)
        ok, reason = adapter.available() if adapter else (False, "adapter is missing")
        backend_status[name] = {"available": bool(ok), "reason": str(reason)}
    checks["backends"] = backend_status
    if not any(value["available"] for value in backend_status.values()):
        problems.append("No configured video backend is available")

    free_bytes = shutil.disk_usage(Path(manifest.project_dir)).free
    checks["free_disk_gb"] = round(free_bytes / 1024 ** 3, 2)
    minimum_gb = float(os.getenv("LOCAL_VIDEO_MIN_FREE_GB", "5"))
    if checks["free_disk_gb"] < minimum_gb:
        problems.append(f"Only {checks['free_disk_gb']} GB free; {minimum_gb:g} GB is required")

    if require_visual_qc and os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") != "1":
        checks["visual_qc_claude_cli"] = claude_cli.available()
        if not checks["visual_qc_claude_cli"]:
            problems.append("Claude Code (`claude -p`, subscription login) is required for fail-closed visual QC")

    narration = str(manifest.script.get("spoken_script") or "")
    # A redo or resume reuses the rendered narration (QueueRunner._narration), so it needs no
    # credits; checking anyway refused a six-shot redo once the keys ran low.
    rendered = (Path(manifest.project_dir) / "audio" / "narration.mp3").is_file()
    checks["narration_reused"] = rendered
    if manifest.narration_enabled and narration.strip() and not rendered:
        keys = elevenlabs_keys()
        checks["elevenlabs_keys"] = len(keys)
        if not keys:
            problems.append("No ElevenLabs key is configured")
        else:
            required = len(narration)
            statuses = [(name, credit_status(key)) for name, key in keys]
            checks["elevenlabs"] = [
                {"name": name, "valid": status["valid"], "remaining": status.get("remaining"),
                 "status_code": status.get("status_code")}
                for name, status in statuses
            ]
            usable = [status for _, status in statuses if status["valid"]]
            if not usable:
                problems.append("No ElevenLabs key passed the subscription/permission check")
            elif all(int(status["remaining"] or 0) < required for status in usable):
                problems.append(f"No ElevenLabs key has the {required} characters required for narration")

    report = {"valid": not problems, "checks": checks, "problems": problems}
    if problems:
        raise RuntimeError("Preflight failed: " + "; ".join(problems))
    return report
