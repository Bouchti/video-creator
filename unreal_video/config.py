"""Configuration and Unreal Editor discovery for the local UE5 renderer."""

from __future__ import annotations

import glob
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from agents.media import FFMPEG, FFPROBE
from config.paths import PROJECT_ROOT


def find_unreal_editor() -> Path | None:
    configured = (os.getenv("UNREAL_EDITOR_CMD") or "").strip().strip('"')
    candidates = [Path(configured)] if configured else []
    command = shutil.which("UnrealEditor-Cmd.exe") or shutil.which("UnrealEditor-Cmd")
    if command:
        candidates.append(Path(command))
    patterns = [
        r"C:\Program Files\Epic Games\UE_*\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
        r"D:\Epic Games\UE_*\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
        r"D:\Unreal Engine\UE_*\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    ]
    for pattern in patterns:
        candidates.extend(Path(value) for value in sorted(glob.glob(pattern), reverse=True))
    return next((path.resolve() for path in candidates if path.is_file()), None)


@dataclass
class UnrealConfig:
    editor: Path | None = field(default_factory=find_unreal_editor)
    project: Path = field(default_factory=lambda: Path(
        os.getenv("UNREAL_PROJECT") or Path(PROJECT_ROOT) / "unreal" / "VideoCreatorUE" / "VideoCreatorUE.uproject"
    ).expanduser().resolve())
    output_root: Path = field(default_factory=lambda: Path(
        os.getenv("UNREAL_OUTPUT_DIR") or Path(PROJECT_ROOT) / "output" / "unreal_projects"
    ).expanduser().resolve())
    setup_script: Path = field(default_factory=lambda: Path(
        PROJECT_ROOT, "unreal", "VideoCreatorUE", "Content", "Python", "build_sequence.py"
    ).resolve())
    width: int = field(default_factory=lambda: int(os.getenv("UNREAL_WIDTH", "1080")))
    height: int = field(default_factory=lambda: int(os.getenv("UNREAL_HEIGHT", "1920")))
    fps: int = field(default_factory=lambda: int(os.getenv("UNREAL_FPS", "30")))
    timeout: int = field(default_factory=lambda: int(os.getenv("UNREAL_TIMEOUT", "7200")))
    minimum_free_gb: float = field(default_factory=lambda: float(os.getenv("UNREAL_MIN_FREE_GB", "15")))
    ffmpeg: str = FFMPEG
    ffprobe: str = FFPROBE

    def __post_init__(self) -> None:
        if (self.width, self.height) != (1080, 1920):
            raise ValueError("The Unreal production route currently requires 1080x1920 output")
        if self.fps != 30:
            raise ValueError("The Unreal production route currently requires 30 fps")
        self.output_root.mkdir(parents=True, exist_ok=True)
