"""Shared path configuration for the video pipeline."""

import glob
import os
import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

# Resolve project root dynamically from this file's location
# (config/ -> parent -> project root)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

# Ensure project root is on sys.path so `agents` is importable
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def get_env_path() -> str:
    return os.path.join(PROJECT_ROOT, ".env")


def get_output_dir() -> str:
    d = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(d, exist_ok=True)
    return d


def get_log_file() -> str:
    d = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "pipeline.log")


def get_temp_dir() -> str:
    return tempfile.gettempdir()


def get_comfy_workflow_path() -> str:
    """Default path to the exported ComfyUI API-format workflow JSON."""
    return os.path.join(PROJECT_ROOT, "config", "comfy_workflow_wan.json")


# Shared constants
CLAUDE_MODEL = "claude-sonnet-4-6"

_FFMPEG_INSTALL_HINT = (
    "FFmpeg is required but ffprobe/ffmpeg were not found. Install with:\n"
    "  winget install --id Gyan.FFmpeg --exact\n"
    "Then restart your terminal or IDE so the updated PATH is picked up."
)


def _ffmpeg_exe_name(tool: str) -> str:
    return f"{tool}.exe" if os.name == "nt" else tool


def _ffmpeg_candidates(tool: str) -> list[str]:
    exe = _ffmpeg_exe_name(tool)
    env_key = f"{tool.upper()}_PATH"
    override = os.getenv(env_key)
    if override:
        return [override]

    bin_dir = os.getenv("FFMPEG_BIN")
    if bin_dir:
        return [os.path.join(bin_dir, exe)]

    candidates = []
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        candidates.append(os.path.join(local, "Microsoft", "WinGet", "Links", exe))
        pattern = os.path.join(
            local, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "*", "bin", exe
        )
        candidates.extend(glob.glob(pattern))

    return candidates


@lru_cache(maxsize=2)
def get_ffmpeg_tool(tool: str) -> str:
    """Resolve ffmpeg or ffprobe, including common Windows install locations."""
    found = shutil.which(tool)
    if found:
        return found

    for candidate in _ffmpeg_candidates(tool):
        if candidate and os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(_FFMPEG_INSTALL_HINT)


def get_ffmpeg() -> str:
    return get_ffmpeg_tool("ffmpeg")


def get_ffprobe() -> str:
    return get_ffmpeg_tool("ffprobe")
