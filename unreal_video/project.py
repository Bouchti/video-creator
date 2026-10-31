"""Create and load resumable Unreal video projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from local_video.models import ProjectManifest, ProjectState, Shot, caption_settings
from local_video.project import new_project_dir

from .config import UnrealConfig
from .planner import build_recipe


def create_project(script: dict[str, Any], duration: int, voice: str, music: str,
                   captions: bool, narration_enabled: bool,
                   config: UnrealConfig | None = None) -> ProjectManifest:
    config = config or UnrealConfig()
    concept = str(script.get("video_title") or script.get("description") or "Unreal video")
    project_dir = new_project_dir(config.output_root, concept, ("audio", "frames", "logs", "render"))
    recipe = build_recipe(script, duration, config.width, config.height, config.fps)
    recipe_path = project_dir / "recipe.json"
    recipe_path.write_text(json.dumps(recipe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = ProjectManifest(
        id=project_dir.name,
        concept=concept,
        duration_seconds=duration,
        visual_style=str(script.get("visual_style") or recipe["world"]["style"]),
        preferred_backend="unreal",
        project_dir=str(project_dir),
        fps=config.fps,
        width=config.width,
        height=config.height,
        script=script,
        narration_enabled=narration_enabled and bool(str(script.get("spoken_script") or "").strip()),
        voice=voice,
        music=music,
        ambience="silent authored Unreal world",
        captions=caption_settings(captions, burn_in=captions, export_srt=captions),
        shots=[Shot(id="unreal-sequence", index=0, duration_frames=duration * config.fps,
                    prompt="Full validated Unreal Level Sequence", negative_prompt="", seed=0)],
        settings={
            "unreal_recipe": "recipe.json",
            "unreal_project": str(config.project),
            "visual_audio_policy": "silent; narration and captions added only in software post",
            "sound_effects": [],
            "final": {"width": 1080, "height": 1920, "fps": 30,
                      "video_codec": "h264", "audio_codec": "aac"},
        },
    )
    manifest.set_state(ProjectState.QUEUED)
    manifest.record("unreal_recipe_created", shots=len(recipe["shots"]), path="recipe.json")
    manifest.save()
    return manifest


def load_project(value: str | Path) -> ProjectManifest:
    path = Path(value)
    if path.is_dir():
        path = path / "project.json"
    return ProjectManifest.load(path)
