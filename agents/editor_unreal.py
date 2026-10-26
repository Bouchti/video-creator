"""Adapter from the shared script/evaluation system to the Unreal renderer."""

from __future__ import annotations

from pathlib import Path

from unreal_video.config import UnrealConfig
from unreal_video.project import create_project
from unreal_video.runner import UnrealPipeline


def process_video(script: dict, voice: str = "mysterious", *, duration: int = 60,
                  visual_style: str | None = None, music: str = "subtle cinematic", captions: bool = True,
                  narration_enabled: bool = True) -> str:
    config = UnrealConfig()
    if visual_style:
        script = {**script, "visual_style": visual_style}
    project = create_project(script, duration, voice, music, captions, narration_enabled, config)
    project = UnrealPipeline(config).run(project)
    if project.state != "completed":
        raise RuntimeError(project.error or f"Unreal project ended in state {project.state}")
    return str((Path(project.project_dir) / project.outputs["video"]).resolve())
