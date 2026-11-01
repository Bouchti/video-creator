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
from .models import ProjectManifest, ProjectState, Shot, caption_settings, estimated_remaining_seconds
from .planner import build_visual_screenplay, plan_shots, reseed, validate_duration


DEFAULT_STYLE = "cinematic realism, tactile detail, restrained teal and amber grade, motivated natural light"


def new_project_dir(root: Path, concept: str, folders) -> Path:
    """A fresh `<UTC stamp>-<slug>` project folder under `root` (suffixed -2, -3... if taken), with `folders`."""
    identity = f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{slugify(concept)}"
    project_dir, suffix = root / identity, 2
    while project_dir.exists():
        project_dir = root / f"{identity}-{suffix}"
        suffix += 1
    for folder in folders:
        (project_dir / folder).mkdir(parents=True, exist_ok=True)
    return project_dir


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
    from agents.leader import research_topic
    research = research_topic(concept)
    script = evaluate_with_retry(
        concept,
        tone="mysterious",
        max_retries=3,
        target_seconds=duration,
        mode="local-ai",
        source="local-ai",
        content_mode="documentary",
        research=research,
    )
    if not script:
        raise RuntimeError("Script generation failed after three evaluated attempts")
    script["visual_style"] = visual_style or script.get("visual_style") or DEFAULT_STYLE
    return script


def export_screenplay(manifest: ProjectManifest) -> Path:
    """Write the full-story source of truth; clip prompts receive only a local scene window."""
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
    ai_upscale: str | None = None,
) -> ProjectManifest:
    """ai_upscale: a Real-ESRGAN model name for this project's final upscale ("x2plus", "off"...);
    None leaves it to LOCAL_VIDEO_AI_UPSCALE."""
    config = config or PipelineConfig()
    duration = validate_duration(duration)
    backend = preferred_backend.lower().replace("h3", "minimax").replace("wan 2.2", "wan")
    if backend not in BACKENDS:
        raise ValueError("preferred_backend must be auto, minimax, or wan")
    project_dir = new_project_dir(config.output_root, concept,
                                  ("shots", "rejected", "superseded", "input", "audio", "render", "logs"))
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
        captions=captions or caption_settings(narration_enabled),
        settings={
            "retry_limit": config.retry_limit,
            "fallback_failures": config.fallback_failures,
            "services": config.tool_versions(),
            "wan_workflow": str(config.wan_workflow),
            "final": {"width": 1080, "height": 1920, "fps": 30, "video_codec": "h264", "audio_codec": "aac"},
            "prompt_strategy": "single-beat+frame-reference",
            "visual_qc": {"local_artifact_detection": True, "semantic_review": True, "minimum_score": 7},
            },
    )
    if ai_upscale is not None:
        manifest.settings["ai_upscale"] = ai_upscale
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


def set_reference_image(
    project: str | Path, image: str | Path, config: PipelineConfig | None = None,
) -> ProjectManifest:
    manifest = load_project(project, config)
    source = validate_input_file(image, IMAGE_EXTENSIONS)
    target = Path(manifest.project_dir) / "input" / f"reference{source.suffix.lower()}"
    if source != target.resolve():
        shutil.copy2(source, target)
    manifest.reference_image = str(target.relative_to(manifest.project_dir))
    manifest.record("reference_image_set", path=manifest.reference_image)
    manifest.save()
    return manifest


def adopt_reviewed_clip(
    project: str | Path, shot_number: int, clip: str | Path,
    config: PipelineConfig | None = None,
) -> ProjectManifest:
    """Adopt an archived candidate only after it passes current technical and semantic gates."""
    config = config or PipelineConfig()
    manifest = load_project(project, config)
    if not 1 <= shot_number <= len(manifest.shots):
        raise ValueError(f"shot_number must be between 1 and {len(manifest.shots)}")
    source = validate_input_file(clip, {".mp4", ".mov", ".mkv", ".webm"}, 2 * 1024 * 1024 * 1024)
    shot = manifest.shots[shot_number - 1]
    from .validation import extract_last_frame, validate_clip
    from .visual_review import review_clip
    report = validate_clip(
        source, config, config.minimax_width, config.minimax_height, config.minimax_seconds,
    )
    reference = None
    if shot.index > 0 and manifest.shots[shot.index - 1].last_frame:
        candidate = resolve_within(manifest.project_dir, manifest.shots[shot.index - 1].last_frame)
        reference = candidate if candidate.is_file() else None
    elif manifest.reference_image:
        candidate = resolve_within(manifest.project_dir, manifest.reference_image)
        reference = candidate if candidate.is_file() else None
    semantic = review_clip(source, shot, reference, manifest)
    report["semantic_review"] = semantic
    if not semantic.get("valid", False):
        raise ValueError(f"Clip did not pass semantic review: {semantic.get('problems') or semantic}")
    target = Path(manifest.project_dir) / "shots" / f"{shot.id}-reviewed.mp4"
    shutil.copy2(source, target)
    last_frame = Path(manifest.project_dir) / "shots" / f"{shot.id}-last.jpg"
    extract_last_frame(target, last_frame, config)
    shot.status = "accepted"
    shot.backend = "minimax-reviewed"
    shot.output = str(target.relative_to(manifest.project_dir))
    shot.last_frame = str(last_frame.relative_to(manifest.project_dir))
    shot.validation = report
    shot.error = None
    manifest.active_shot = None
    manifest.outputs = {}
    manifest.record("reviewed_clip_adopted", shot=shot.id, source=str(source),
                    acceptance=semantic.get("acceptance"), average=semantic.get("average_score"))
    manifest.set_state(ProjectState.QUEUED, reason="reviewed_clip_adopted")
    manifest.save()
    return manifest


def reset_shot(project: str | Path, shot_number: int, config: PipelineConfig | None = None) -> ProjectManifest:
    manifest = load_project(project, config)
    if not 1 <= shot_number <= len(manifest.shots):
        raise ValueError(f"shot_number must be between 1 and {len(manifest.shots)}")
    requeue_shot(manifest, manifest.shots[shot_number - 1])
    manifest.save()
    return manifest


def requeue_shot(manifest: ProjectManifest, shot: Shot) -> None:
    """Supersede a shot's clip and queue it for a fresh generation (the manifest is not saved)."""
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
    # A new seed: with the same seed, keyframe and prompt MiniMax returns the very take being replaced
    # (the Hegdahl hook came back frame-for-frame identical, cap glitch included).
    shot.seed = reseed(shot, len(shot.attempts) + 1)
    shot.attempts = []
    # A regenerated shot is no longer salvaged: a stale mark would both count against the run's
    # degradation budget and keep the shot from serving as a still source for its neighbours.
    shot.degraded = ""
    manifest.outputs = {}
    manifest.set_state(ProjectState.QUEUED, reason="shot_regeneration", shot=shot.id)


def replan_project(project: str | Path, config: PipelineConfig | None = None) -> ProjectManifest:
    """Archive prior generations and rebuild prompts from the existing reviewed script."""
    manifest = load_project(project, config)
    root = Path(manifest.project_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    archive = root / "superseded" / f"replan-{stamp}"
    archive.mkdir(parents=True, exist_ok=False)
    current_manifest = root / "project.json"
    if current_manifest.is_file():
        shutil.copy2(current_manifest, archive / "project-before-replan.json")
    shots_dir = root / "shots"
    archived_files = 0
    if shots_dir.is_dir():
        archived_shots = archive / "shots"
        archived_shots.mkdir()
        for source in shots_dir.iterdir():
            if source.is_file():
                shutil.move(str(source), str(archived_shots / source.name))
                archived_files += 1
    manifest.shots, manifest.continuity = plan_shots(
        manifest.script, manifest.concept, manifest.duration_seconds, manifest.visual_style,
        manifest.preferred_backend, manifest.ambience, manifest.fps,
    )
    manifest.outputs = {}
    manifest.active_shot = None
    manifest.started_at = None
    manifest.completed_at = None
    manifest.elapsed_seconds = 0.0
    manifest.error = None
    manifest.settings.update({
        "prompt_strategy": "single-beat+frame-reference",
        "visual_qc": {"local_artifact_detection": True, "semantic_review": True, "minimum_score": 7},
    })
    export_screenplay(manifest)
    manifest.record("project_replanned", archive=str(archive.relative_to(root)), archived_files=archived_files,
                    reason="immersive_local_scene_prompts_and_visual_critique")
    manifest.set_state(ProjectState.QUEUED)
    manifest.save()
    return manifest


def refresh_project_from_shot(
    project: str | Path, from_shot: int, config: PipelineConfig | None = None,
) -> ProjectManifest:
    """Rebuild future prompts while preserving earlier accepted story continuity."""
    manifest = load_project(project, config)
    if not 1 <= from_shot <= len(manifest.shots):
        raise ValueError(f"from_shot must be between 1 and {len(manifest.shots)}")
    root = Path(manifest.project_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    archive = root / "superseded" / f"refresh-from-{from_shot:03d}-{stamp}"
    archive.mkdir(parents=True, exist_ok=False)
    shutil.copy2(root / "project.json", archive / "project-before-refresh.json")
    archived: list[str] = []
    # Same shot count as the existing plan, so earlier accepted shots keep their place.
    planned, continuity = plan_shots(
        manifest.script, manifest.concept, manifest.duration_seconds, manifest.visual_style,
        manifest.preferred_backend, manifest.ambience, manifest.fps, shot_count=len(manifest.shots),
    )
    archive_shots = archive / "shots"
    for index in range(from_shot - 1, len(manifest.shots)):
        previous = manifest.shots[index]
        for relative in (previous.output, previous.last_frame):
            if not relative:
                continue
            source = resolve_within(root, relative)
            if not source.is_file():
                continue
            archive_shots.mkdir(exist_ok=True)
            destination = archive_shots / source.name
            if destination.exists():
                destination = archive_shots / f"{previous.id}-{source.name}"
            shutil.move(str(source), str(destination))
            archived.append(str(destination.relative_to(root)))
        manifest.shots[index] = planned[index]
    manifest.continuity = continuity
    manifest.outputs = {}
    manifest.active_shot = None
    manifest.completed_at = None
    manifest.error = None
    manifest.settings.update({
        "prompt_strategy": "single-beat+frame-reference+screenplay-camera",
        "visual_qc": {
            "local_artifact_detection": True,
            "semantic_review": True,
            "minimum_score": 7,
            "story_progression_required": True,
        },
    })
    export_screenplay(manifest)
    manifest.record(
        "future_shots_refreshed", from_shot=from_shot,
        archive=str(archive.relative_to(root)), archived=archived,
    )
    manifest.set_state(ProjectState.PAUSED, reason="quality_fixes_ready_for_review")
    manifest.save()
    return manifest


def project_status(manifest: ProjectManifest) -> dict[str, Any]:
    completed = sum(s.status == "accepted" for s in manifest.shots)
    return {
        "project": manifest.id,
        "state": manifest.state,
        "active_shot": manifest.active_shot,
        "completed": completed,
        "total": len(manifest.shots),
        "elapsed_seconds": round(manifest.elapsed_seconds, 1),
        "estimated_remaining_seconds": round(estimated_remaining_seconds(manifest), 1),
        "preferred_backend": manifest.preferred_backend,
        "last_error": manifest.error,
        "outputs": manifest.outputs,
    }
