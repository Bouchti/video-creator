"""Runtime discovery, environment settings, and safe path helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import requests
from dotenv import load_dotenv

from config.paths import PROJECT_ROOT, get_comfy_workflow_path, get_env_path
from agents.media import FFMPEG, FFPROBE

load_dotenv(get_env_path())


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
BACKENDS = {"auto", "minimax", "wan"}
# Assembly slows a clip by at most this factor before it has to freeze the last frame,
# and the longest transition (crossfade) borrows this much extra footage from a shot.
MAX_CLIP_STRETCH = 1.12
MAX_TRANSITION_SECONDS = 4 / 30


def minimum_clip_seconds(shot_seconds: float) -> float:
    """Shortest generated clip that fills a shot without a frozen tail."""
    return (shot_seconds + MAX_TRANSITION_SECONDS) / MAX_CLIP_STRETCH


def env_int(name: str, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None and raw != "" else default
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum or maximum is not None and value > maximum:
        bound = f" between {minimum} and {maximum}" if maximum is not None else f" >= {minimum}"
        raise ValueError(f"{name} must be{bound}")
    return value


def env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.getenv(name)
    try:
        value = float(raw) if raw is not None and raw != "" else default
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def slugify(value: str, limit: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:limit].strip("-")
    return slug or "video-project"


def resolve_within(root: str | Path, relative: str | Path) -> Path:
    """Resolve *relative* under root and reject traversal or absolute paths."""
    base = Path(root).resolve()
    value = Path(relative)
    if value.is_absolute():
        raise ValueError("Expected a project-relative path, not an absolute path")
    resolved = (base / value).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Path escapes project directory: {relative}") from exc
    return resolved


def validate_input_file(path: str | Path, extensions: set[str], max_bytes: int = 100 * 1024 * 1024) -> Path:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Input file does not exist: {source}")
    if source.suffix.lower() not in extensions:
        raise ValueError(f"Unsupported file type {source.suffix}; expected {sorted(extensions)}")
    if source.stat().st_size > max_bytes:
        raise ValueError(f"Input file is larger than {max_bytes // (1024 * 1024)} MB")
    return source


def _pinokio_home() -> Path | None:
    config = Path.home() / ".pinokio" / "config.json"
    try:
        value = json.loads(config.read_text(encoding="utf-8")).get("home")
        return Path(value).expanduser() if value else None
    except (OSError, ValueError, TypeError):
        return None


def _candidate_urls(explicit: Iterable[str | None], fallbacks: Iterable[str]) -> list[str]:
    values: list[str] = []
    for value in explicit:
        if value:
            values.append(value.rstrip("/"))
    # The two ports are conventional fallbacks only; explicit configuration and
    # launcher metadata always win.
    values.extend(fallbacks)
    return list(dict.fromkeys(values))


def probe_node(url: str, class_type: str, timeout: float = 2.0) -> bool:
    try:
        response = requests.get(f"{url}/object_info/{class_type}", timeout=timeout)
        return response.ok and class_type in response.json()
    except (requests.RequestException, ValueError):
        return False


def probe_model(url: str, class_type: str, input_name: str, model_name: str, timeout: float = 2.0) -> bool:
    try:
        response = requests.get(f"{url}/object_info/{class_type}", timeout=timeout)
        choices = response.json()[class_type]["input"]["required"][input_name][0]
        return model_name in choices
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return False


def discover_comfy_url(
    kind: str,
    configured: str | None = None,
    required_models: Iterable[tuple[str, str, str]] = (),
) -> str | None:
    """Find a compatible running ComfyUI without assuming one installation path."""
    required = ["FreeVideoGenerate"] if kind == "minimax" else [
        "UnetLoaderGGUF", "CLIPLoaderGGUF", "Wan22ImageToVideoLatent", "CreateVideo", "SaveVideo"
    ]
    explicit = [
        configured,
        os.getenv("MINIMAX_COMFYUI_URL") if kind == "minimax" else os.getenv("WAN_COMFYUI_URL"),
        os.getenv("COMFYUI_URL"),
    ]
    fallbacks = (
        ["http://127.0.0.1:8190", "http://127.0.0.1:8188"]
        if kind == "minimax" else
        ["http://127.0.0.1:8188", "http://127.0.0.1:8190"]
    )
    for url in _candidate_urls(explicit, fallbacks):
        if (all(probe_node(url, node) for node in required)
                and all(probe_model(url, node, field, model) for node, field, model in required_models)):
            return url
    return None


@dataclass
class PipelineConfig:
    discover_services: bool = True
    output_root: Path = field(default_factory=lambda: Path(
        os.getenv("LOCAL_VIDEO_OUTPUT_DIR") or Path(PROJECT_ROOT) / "output" / "projects"
    ).expanduser().resolve())
    minimax_url: str | None = None
    wan_url: str | None = None
    wan_workflow: Path = field(default_factory=lambda: Path(
        os.getenv("WAN_WORKFLOW") or os.getenv("COMFY_WORKFLOW") or get_comfy_workflow_path()
    ).expanduser().resolve())
    retry_limit: int = field(default_factory=lambda: env_int("LOCAL_VIDEO_RETRY_LIMIT", 2, 0, 10))
    fallback_failures: int = field(default_factory=lambda: env_int("LOCAL_VIDEO_FALLBACK_FAILURES", 2, 1, 10))
    # Share of shots that may be salvaged (a rejected take kept, or a still push-in) before the run
    # stops to save GPU hours. 100 = never stop, the default: a run always finishes its video, and
    # the salvage count is reported as a quality warning instead.
    max_degraded_percent: int = field(
        default_factory=lambda: env_int("LOCAL_VIDEO_MAX_DEGRADED_PERCENT", 100, 0, 100))
    # Once every normal take of a shot is rejected, render one more with the camera locked off.
    repair_take: bool = field(default_factory=lambda: env_int("LOCAL_VIDEO_REPAIR_TAKE", 1, 0, 1) == 1)
    # 1 = a final creative review reject fails the run. 0 (default) = the video is delivered and the
    # reject is reported as a quality warning, which holds auto-publishing for that video.
    final_review_blocks: bool = field(
        default_factory=lambda: env_int("LOCAL_VIDEO_FINAL_REVIEW_BLOCKS", 0, 0, 1) == 1)
    generation_timeout: int = field(default_factory=lambda: env_int("LOCAL_VIDEO_GENERATION_TIMEOUT", 3600, 60, 86400))
    poll_seconds: float = field(default_factory=lambda: env_float("LOCAL_VIDEO_POLL_SECONDS", 2.0, 0.1))
    minimax_width: int = field(default_factory=lambda: env_int("MINIMAX_WIDTH", 544, 256, 4096))
    minimax_height: int = field(default_factory=lambda: env_int("MINIMAX_HEIGHT", 960, 256, 4096))
    minimax_seconds: float = field(default_factory=lambda: env_float("MINIMAX_SECONDS", 3.0, 1.625))
    wan_width: int = field(default_factory=lambda: env_int("WAN_WIDTH", 480, 128, 2048))
    wan_height: int = field(default_factory=lambda: env_int("WAN_HEIGHT", 832, 128, 2048))
    wan_frames: int = field(default_factory=lambda: env_int("WAN_FRAMES", 33, 5, 1001))
    wan_fps: int = field(default_factory=lambda: env_int("WAN_FPS", 16, 1, 120))
    wan_steps: int = field(default_factory=lambda: env_int("WAN_STEPS", 20, 1, 100))
    wan_cfg: float = field(default_factory=lambda: env_float("WAN_CFG", 5.0, 0.0))
    wan_model: str = field(default_factory=lambda: os.getenv("WAN_MODEL", "Wan2.2-TI2V-5B-Q5_K_M.gguf"))
    wan_encoder: str = field(default_factory=lambda: os.getenv("WAN_ENCODER", "umt5-xxl-encoder-Q4_K_M.gguf"))
    wan_vae: str = field(default_factory=lambda: os.getenv("WAN_VAE", "wan2.2_vae.safetensors"))
    upscale_filter: str = field(default_factory=lambda: os.getenv("LOCAL_VIDEO_UPSCALE_FILTER", "lanczos").lower())
    # Render the next shot while Claude reviews the current one; cancelled if the review rejects it.
    speculative_next_shot: bool = field(default_factory=lambda: env_int("LOCAL_VIDEO_SPECULATIVE", 1, 0, 1) == 1)
    ffmpeg: str = FFMPEG
    ffprobe: str = FFPROBE

    def __post_init__(self) -> None:
        if self.upscale_filter not in {"lanczos", "bicubic", "spline"}:
            raise ValueError("LOCAL_VIDEO_UPSCALE_FILTER must be lanczos, bicubic, or spline")
        self.output_root.mkdir(parents=True, exist_ok=True)
        if self.discover_services:
            self.minimax_url = discover_comfy_url("minimax", self.minimax_url)
            self.wan_url = discover_comfy_url("wan", self.wan_url, [
                ("UnetLoaderGGUF", "unet_name", self.wan_model),
                ("CLIPLoaderGGUF", "clip_name", self.wan_encoder),
                ("VAELoader", "vae_name", self.wan_vae),
            ])

    def backend_available(self, backend: str) -> bool:
        return bool(self.minimax_url if backend == "minimax" else self.wan_url if backend == "wan" else False)

    def tool_versions(self) -> dict[str, str | None]:
        return {
            "ffmpeg": shutil.which(self.ffmpeg) or self.ffmpeg,
            "ffprobe": shutil.which(self.ffprobe) or self.ffprobe,
            "minimax_url": self.minimax_url,
            "wan_url": self.wan_url,
        }
