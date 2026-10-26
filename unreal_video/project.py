"""Create and load resumable Unreal video projects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_video.config import slugify
from local_video.models import ProjectManifest, ProjectState, Shot

from .config import UnrealConfig
from .planner import build_recipe


def create_project(script: dict[str, Any], duration: int, voice: str, music: str,
                   captions: bool, narration_enabled: bool,
                   config: UnrealConfig | None = None) -> ProjectManifest:
    config = config or UnrealConfig()
    concept = str(script.get("video_title") or script.get("description") or "Unreal video")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = f"{stamp}-{slugify(concept)}"
    project_dir = config.output_root / base
    suffix = 2
    while project_dir.exists():
        project_dir = config.output_root / f"{base}-{suffix}"
        suffix += 1
    for folder in ("audio", "frames", "logs", "render"):
        (project_dir / folder).mkdir(parents=True, exist_ok=True)
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
        captions={"enabled": captions, "burn_in": captions, "export_srt": captions,
                  "word_highlight": True, "safe_position": "lower-middle"},
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
