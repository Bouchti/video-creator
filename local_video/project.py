"""Project creation and non-destructive control operations."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    AUDIO_EXTENSIONS, BACKENDS, IMAGE_EXTENSIONS, PipelineConfig, resolve_within,
    slugify, validate_input_file,
)
from .models import ProjectManifest, ProjectState
from .planner import build_visual_screenplay, plan_shots, validate_duration


DEFAULT_STYLE = "cinematic realism, tactile detail, restrained teal and amber grade, motivated natural light"


def _project_id(concept: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{slugify(concept)}"


def _script_from_narration(concept: str, narration: str, duration: int, visual_style: str) -> dict[str, Any]:
    return {
        "video_title": concept[:100],
        "description": concept,
        "hashtags": ["#story", "#cinematic", "#AIvideo", "#TikTok"],
        "mood": "mysterious",
        "target_duration": duration,
        "spoken_script": narration.strip(),
        "visual_style": visual_style,
        "beats": [],
    }


def generate_script(concept: str, duration: int, visual_style: str, narration_text: str | None = None) -> dict[str, Any]:
    if narration_text is not None:
        if not narration_text.strip():
            return _script_from_narration(concept, "", duration, visual_style)
        return _script_from_narration(concept, narration_text, duration, visual_style)
    from agents.evaluator import evaluate_with_retry
    script = evaluate_with_retry(
        concept,
        tone="mysterious",
        max_retries=3,
        target_seconds=duration,
        mode="local-ai",
    )
    if not script:
        raise RuntimeError("Script generation failed after three evaluated attempts")
    script["visual_style"] = visual_style or script.get("visual_style") or DEFAULT_STYLE
    return script


def export_screenplay(manifest: ProjectManifest) -> Path:
    """Write the exact full-story context embedded in generation prompts."""
    screenplay = build_visual_screenplay(
        manifest.script,
        manifest.concept,
        manifest.continuity,
        [shot.subject_action for shot in manifest.shots],
    )
    target = Path(manifest.project_dir) / "screenplay.txt"
    target.write_text(screenplay + "\n", encoding="utf-8", newline="\n")
    manifest.settings["screenplay"] = str(target.relative_to(manifest.project_dir))
    return target


def create_project(
    concept: str,
    duration: int = 60,
    visual_style: str = DEFAULT_STYLE,
    preferred_backend: str = "auto",
    narration_text: str | None = None,
    narration_enabled: bool = True,
    reference_image: str | Path | None = None,
    music: str = "subtle cinematic",
    ambience: str = "natural location ambience",
    captions: dict[str, Any] | None = None,
    voice: str = "mysterious",
    config: PipelineConfig | None = None,
    script: dict[str, Any] | None = None,
) -> ProjectManifest:
    config = config or PipelineConfig()
    duration = validate_duration(duration)
    backend = preferred_backend.lower().replace("h3", "minimax").replace("wan 2.2", "wan")
    if backend not in BACKENDS:
        raise ValueError("preferred_backend must be auto, minimax, or wan")
    identity = _project_id(concept)
    project_dir = config.output_root / identity
    suffix = 2
    while project_dir.exists():
        project_dir = config.output_root / f"{identity}-{suffix}"
        suffix += 1
    for folder in ("shots", "rejected", "superseded", "input", "audio", "render", "logs"):
        (project_dir / folder).mkdir(parents=True, exist_ok=True)
    manifest = ProjectManifest(
        id=project_dir.name,
        concept=concept.strip(),
        duration_seconds=duration,
        visual_style=visual_style or DEFAULT_STYLE,
        preferred_backend=backend,
        project_dir=str(project_dir),
        narration_enabled=narration_enabled,
        voice=voice,
        music=music,
        ambience=ambience,
        captions=captions or {
            "enabled": narration_enabled,
            "burn_in": True,
            "export_srt": True,
            "word_highlight": True,
            "safe_position": "lower-middle",
        },
        settings={
            "retry_limit": config.retry_limit,
            "fallback_failures": config.fallback_failures,
            "services": config.tool_versions(),
            "wan_workflow": str(config.wan_workflow),
            "final": {"width": 1080, "height": 1920, "fps": 30, "video_codec": "h264", "audio_codec": "aac"},
        },
    )
    music_source = Path(music).expanduser()
    if music_source.exists():
        manifest.settings["music_path"] = str(
            validate_input_file(music_source, AUDIO_EXTENSIONS, 500 * 1024 * 1024)
        )
    manifest.set_state(ProjectState.PLANNING)
    if reference_image:
        source = validate_input_file(reference_image, IMAGE_EXTENSIONS)
        target = project_dir / "input" / f"reference{source.suffix.lower()}"
        shutil.copy2(source, target)
        manifest.reference_image = str(target.relative_to(project_dir))
    manifest.script = script or generate_script(concept, duration, visual_style, narration_text)
    manifest.script.setdefault("story_structure", [
        "opening hook (first two seconds)", "development", "escalation", "climax", "satisfying ending"
    ])
    manifest.shots, manifest.continuity = plan_shots(
        manifest.script, concept, duration, manifest.visual_style, backend, ambience, manifest.fps
    )
    export_screenplay(manifest)
    manifest.record("shot_plan_created", shots=len(manifest.shots), total_frames=sum(s.duration_frames for s in manifest.shots))
    manifest.set_state(ProjectState.QUEUED)
    manifest.save()
    return manifest


def load_project(project: str | Path, config: PipelineConfig | None = None) -> ProjectManifest:
    candidate = Path(project).expanduser()
    if candidate.is_dir():
        candidate = candidate / "project.json"
    elif not candidate.suffix:
        root = (config or PipelineConfig()).output_root
        candidate = resolve_within(root, Path(str(project)) / "project.json")
    if not candidate.is_file():
        raise FileNotFoundError(f"Project manifest not found: {candidate}")
    return ProjectManifest.load(candidate)


def set_control_state(project: str | Path, state: ProjectState, config: PipelineConfig | None = None) -> ProjectManifest:
    manifest = load_project(project, config)
    manifest.set_state(state, requested_by="user")
    manifest.save()
    return manifest


def reset_shot(project: str | Path, shot_number: int, config: PipelineConfig | None = None) -> ProjectManifest:
    manifest = load_project(project, config)
    if not 1 <= shot_number <= len(manifest.shots):
        raise ValueError(f"shot_number must be between 1 and {len(manifest.shots)}")
    shot = manifest.shots[shot_number - 1]
    if shot.output:
        source = resolve_within(manifest.project_dir, shot.output)
        if source.is_file():
            destination = Path(manifest.project_dir) / "superseded" / f"{shot.id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}{source.suffix}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            manifest.record("shot_output_superseded", shot=shot.id, path=str(destination.relative_to(manifest.project_dir)))
    shot.status = "pending"
    shot.output = None
    shot.last_frame = None
    shot.validation = None
    shot.error = None
    shot.attempts = []
    manifest.outputs = {}
    manifest.set_state(ProjectState.QUEUED, reason="shot_regeneration", shot=shot.id)
    manifest.save()
    return manifest


def project_status(manifest: ProjectManifest) -> dict[str, Any]:
    completed = sum(s.status == "accepted" for s in manifest.shots)
    generation_times = [
        float(a.get("generation_seconds") or 0)
        for shot in manifest.shots for a in shot.attempts if a.get("status") == "accepted"
    ]
    average = sum(generation_times) / len(generation_times) if generation_times else 300.0
    remaining = max(0, len(manifest.shots) - completed)
    return {
        "project": manifest.id,
        "state": manifest.state,
        "active_shot": manifest.active_shot,
        "completed": completed,
        "total": len(manifest.shots),
        "elapsed_seconds": round(manifest.elapsed_seconds, 1),
        "estimated_remaining_seconds": round(average * remaining, 1),
        "preferred_backend": manifest.preferred_backend,
        "last_error": manifest.error,
        "outputs": manifest.outputs,
    }
