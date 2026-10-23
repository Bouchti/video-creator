"""Integration adapter from the existing editor architecture to local_video."""

from __future__ import annotations

from pathlib import Path

from local_video.config import PipelineConfig
from local_video.project import create_project
from local_video.queue import QueueRunner


def process_video(
    script: dict,
    voice: str = "mysterious",
    *,
    duration: int = 60,
    backend: str = "auto",
    visual_style: str | None = None,
    reference_image: str | None = None,
    music: str = "subtle cinematic",
    ambience: str = "natural location ambience",
    captions: bool = True,
    narration_enabled: bool = True,
) -> str:
    config = PipelineConfig()
    concept = script.get("video_title") or script.get("description") or "Untitled local AI video"
    project = create_project(
        concept=concept,
        duration=duration,
        visual_style=visual_style or script.get("visual_style") or "cinematic realism",
        preferred_backend=backend,
        narration_enabled=narration_enabled and bool(script.get("spoken_script")),
        reference_image=reference_image,
        music=music,
        ambience=ambience,
        captions={"enabled": captions, "burn_in": captions, "export_srt": captions, "word_highlight": True},
        voice=voice,
        config=config,
        script=script,
    )
    project = QueueRunner(config).run(project)
    if project.state != "completed":
        raise RuntimeError(project.error or f"Local AI project ended in state {project.state}")
    return str((Path(project.project_dir) / project.outputs["video"]).resolve())
