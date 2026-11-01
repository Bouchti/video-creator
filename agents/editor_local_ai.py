"""Integration adapter from the existing editor architecture to local_video."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from local_video.config import PipelineConfig
from local_video.models import caption_settings
from local_video.project import create_project, load_project
from local_video.queue import QueueBusyError, QueueRunner, ReviewerUnavailable

log = logging.getLogger(__name__)


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
    ai_upscale: str | None = None,
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
        captions=caption_settings(captions, burn_in=captions, export_srt=captions),
        voice=voice,
        config=config,
        script=script,
        ai_upscale=ai_upscale,
    )
    # The queue resumes a project from disk, reusing every accepted shot, so a run that stopped on
    # a transient fault (FreeVideo crash, CUDA error, a locked file) is picked up again instead of
    # failing the whole pipeline. A pause or cancel the user asked for is respected.
    resumes = int(os.getenv("LOCAL_VIDEO_RESUME_ATTEMPTS") or 2)
    for attempt in range(resumes + 1):
        try:
            project = QueueRunner(config).run(project)
        except (QueueBusyError, ReviewerUnavailable):     # retrying cannot help; the project resumes later
            raise
        except Exception as exc:
            if attempt == resumes:
                raise
            log.warning("Local AI run crashed (%s); resuming the project.", exc)
        else:
            if project.state == "completed" or project.state in {"paused", "cancelled"} or attempt == resumes:
                break
            log.warning("Local AI run ended in state %s (%s); resuming the project, %d resume(s) left.",
                        project.state, project.error, resumes - attempt)
        time.sleep(30)
        project = load_project(project.project_dir)
    if project.state != "completed":
        raise RuntimeError(project.error or f"Local AI project ended in state {project.state}")
    warnings = list(project.settings.get("quality_warnings") or [])
    if warnings:
        script["quality_warnings"] = warnings
    review = project.settings.get("final_creative_review") or {}
    script["publish_hold"] = not review.get("valid", False)
    return str((Path(project.project_dir) / project.outputs["video"]).resolve())
