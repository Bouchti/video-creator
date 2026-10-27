"""Headless UE5 build/render orchestration and software-owned post production."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agents import ai_router
from agents.beats import _norm_words, script_word_timings
from agents.media import get_duration
from agents.transcription import transcribe_with_whisper
from agents.voice import elevenlabs_keys, generate_voiceover
from local_video.assembly import assemble_project
from local_video.config import PipelineConfig
from local_video.models import ProjectManifest, ProjectState
from local_video.validation import validate_clip, validate_final
from local_video.visual_review import review_final_video

from .config import UnrealConfig
from .planner import ACTION_MEANING, build_recipe, retime_recipe, set_actions
from .project import load_project

def plan_actions(recipe: dict[str, Any], script: dict[str, Any]) -> None:
    """Let the AI choose what each shot acts out (from what the set can show), so the picture
    follows the narration's process step by step; keeps the keyword choice if no backend answers."""
    shots = recipe["shots"]
    if recipe["world"].get("actions_planned_by") == "script":
        return                                            # the script already chose each beat's action
    allowed = list(set_actions(recipe["world"].get("archetype", "workshop")))
    schema = {"type": "object", "required": ["actions"], "properties": {"actions": {
        "type": "array", "minItems": len(shots), "maxItems": len(shots),
        "items": {"type": "string", "enum": allowed}}}}
    lines = "\n".join(f"{k + 1}. {shot['narration_reference']}" for k, shot in enumerate(shots))
    menu = "\n".join(f"- {name}: {ACTION_MEANING.get(name, '')}" for name in allowed)
    prompt = (f"Video: {recipe['title']}\nThe 3D set can act out only these actions:\n{menu}\n\n"
              f"For each narration line below, pick the action whose picture best shows what that line says, "
              f"so a viewer with the sound off follows the process in order. The first line is a cold open "
              f"that states the outcome: give it the most striking action ('finale' or the key process "
              f"action); the second line usually 'establish'; the last line must be 'finale'; vary the "
              f"shots, and apart from the cold open never show a step before the narration reaches it.\n\n{lines}")
    try:
        result = ai_router.ask("You plan shots for an engineering explainer video.", prompt, schema, effort="low")
        actions = result.get("actions") if isinstance(result, dict) else None
    except Exception:                                     # noqa: BLE001 (no backend: keyword choice stands)
        actions = None
    if isinstance(actions, list) and len(actions) == len(shots) and all(a in allowed for a in actions):
        actions[-1] = "finale"
        for shot, action in zip(shots, actions):
            shot["action"] = action
        recipe["world"]["actions_planned_by"] = "ai"


NARRATION_TAIL_SECONDS = 1.2           # the last word lands before the film ends
MIN_SECONDS, MAX_SECONDS = 30, 120
TIKTOK_MIN_SECONDS = 61                # TikTok pays (Creator Rewards) only on videos over 1 minute


def build_setup_command(config: UnrealConfig) -> list[str]:
    if config.editor is None:
        raise RuntimeError("Unreal Engine 5 is not installed. Install UE 5.8 or set UNREAL_EDITOR_CMD.")
    return [
        str(config.editor), str(config.project),
        # forward slashes: Unreal unescapes this argument, so "\t" in C:\Users\tibus became a tab
        f'-ExecutePythonScript="{config.setup_script.as_posix()}"',
        # -nullrhi: building the scene renders nothing, and the editor's first viewport frame can
        # crash the GPU shader compiler (dxilconv) on a project full of Fab content
        "-unattended", "-nop4", "-nosplash", "-NoSound", "-nullrhi", "-stdout", "-FullStdOutLogOutput",
    ]


def build_render_command(config: UnrealConfig, handoff: dict[str, Any]) -> list[str]:
    if config.editor is None:
        raise RuntimeError("Unreal Engine 5 is not installed. Install UE 5.8 or set UNREAL_EDITOR_CMD.")
    return [
        str(config.editor), str(config.project), str(handoff["map"]), "-game",
        f'-LevelSequence={handoff["sequence"]}',
        f'-MoviePipelineConfig={handoff["config"]}',
        # -RenderOffscreen: Movie Render Queue writes the frames to disk; its window only ever showed black
        "-RenderOffscreen", "-windowed", f"-resx={config.width}", f"-resy={config.height}",
        "-unattended", "-nop4", "-nosplash", "-NoSound", "-stdout", "-FullStdOutLogOutput",
        "-notexturestreaming",
    ]


class UnrealPipeline:
    def __init__(self, config: UnrealConfig | None = None):
        self.config = config or UnrealConfig()

    def preflight(self, manifest: ProjectManifest) -> dict[str, Any]:
        checks, problems = {}, []
        checks["editor"] = str(self.config.editor) if self.config.editor else None
        checks["project"] = self.config.project.is_file()
        checks["setup_script"] = self.config.setup_script.is_file()
        checks["ffmpeg"] = bool(shutil.which(self.config.ffmpeg) or Path(self.config.ffmpeg).is_file())
        checks["ffprobe"] = bool(shutil.which(self.config.ffprobe) or Path(self.config.ffprobe).is_file())
        checks["free_disk_gb"] = round(shutil.disk_usage(manifest.project_dir).free / 1024 ** 3, 2)
        checks["visual_qc_backend"] = ai_router.available()
        if not self.config.editor:
            problems.append("Unreal Engine 5 was not found; install UE 5.8 or set UNREAL_EDITOR_CMD")
        if not checks["project"]:
            problems.append(f"Unreal project is missing: {self.config.project}")
        if not checks["setup_script"]:
            problems.append(f"Unreal setup script is missing: {self.config.setup_script}")
        if not checks["ffmpeg"] or not checks["ffprobe"]:
            problems.append("FFmpeg and FFprobe are required")
        if checks["free_disk_gb"] < self.config.minimum_free_gb:
            problems.append(f"Only {checks['free_disk_gb']} GB free; Unreal requires "
                            f"at least {self.config.minimum_free_gb:g} GB")
        if not checks["visual_qc_backend"] and os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") != "1":
            problems.append("The configured Codex/Claude/API backend is required for fail-closed final visual review")
        if manifest.narration_enabled and not elevenlabs_keys():
            problems.append("No ElevenLabs key is configured for narration")
        report = {"valid": not problems, "checks": checks, "problems": problems}
        if problems:
            raise RuntimeError("Unreal preflight failed: " + "; ".join(problems))
        return report

    def _run(self, command: list[str], env: dict[str, str], log_path: Path, label: str) -> None:
        result = subprocess.run(command, capture_output=True, text=True, timeout=self.config.timeout, env=env)
        log_path.write_text((result.stdout or "") + "\n--- STDERR ---\n" + (result.stderr or ""),
                            encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"{label} failed (exit {result.returncode}); see {log_path}")

    def _narration(self, manifest: ProjectManifest) -> Path:
        root = Path(manifest.project_dir)
        narration = root / "audio" / "narration.mp3"
        if not narration.is_file():
            source, seconds = generate_voiceover(manifest.script["spoken_script"], voice=manifest.voice)
            shutil.move(source, narration)
            manifest.record("narration_created", duration=seconds, path=str(narration.relative_to(root)))
            manifest.save()
        return narration

    def _fit_to_narration(self, manifest: ProjectManifest, narration: Path, recipe_path: Path) -> None:
        """Size the film to the spoken narration and start each shot as its sentence is spoken."""
        spoken = get_duration(str(narration))
        # asked for over a minute (TikTok's Creator Rewards threshold): never end up just under it
        floor = TIKTOK_MIN_SECONDS if manifest.duration_seconds > 60 else MIN_SECONDS
        duration = max(floor, math.ceil(spoken + NARRATION_TAIL_SECONDS))
        if duration > MAX_SECONDS:
            raise RuntimeError(f"Narration is {spoken:.1f}s; Unreal videos are at most {MAX_SECONDS}s. "
                               "Shorten the script.")
        beats = [b for b in manifest.script.get("beats") or [] if isinstance(b, dict)]
        words = script_word_timings(beats, transcribe_with_whisper(str(narration)), float(duration))
        starts, cursor = [], 0
        for beat in beats:                               # each beat's first spoken word
            count = sum(1 for token in str(beat.get("text") or "").split() if _norm_words(token))
            starts.append(float(words[cursor]["start"]) if cursor < len(words) else float(duration))
            cursor += count
        recipe = build_recipe(manifest.script, duration, self.config.width, self.config.height, self.config.fps)
        recipe = retime_recipe(recipe, starts)
        plan_actions(recipe, manifest.script)
        recipe_path.write_text(json.dumps(recipe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest.duration_seconds = duration
        manifest.shots[0].duration_frames = duration * self.config.fps
        manifest.record("timeline_fitted_to_narration", narration_seconds=round(spoken, 2), seconds=duration)
        manifest.save()

    def _encode_frames(self, manifest: ProjectManifest) -> Path:
        root = Path(manifest.project_dir)
        frames = sorted((root / "frames").glob("*.png"))
        expected = manifest.duration_seconds * manifest.fps
        if len(frames) < expected:
            raise RuntimeError(f"Unreal produced {len(frames)} frames; expected at least {expected}")
        frames = frames[:expected]
        listing = root / "render" / "frames.txt"
        line_duration = 1 / manifest.fps
        lines = []
        for frame in frames:
            escaped = str(frame.resolve()).replace("\\", "/").replace("'", "'\\''")
            lines += [f"file '{escaped}'", f"duration {line_duration:.9f}"]
        last = str(frames[-1].resolve()).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{last}'")
        listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
        target = root / "render" / "unreal-silent.mp4"
        command = [self.config.ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                   "-frames:v", str(expected), "-r", str(manifest.fps), "-an", "-c:v", "libx264",
                   "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                   str(target)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            raise RuntimeError(f"Unreal frame encoding failed: {result.stderr[-1200:]}")
        return target

    def run(self, project: str | Path | ProjectManifest) -> ProjectManifest:
        manifest = project if isinstance(project, ProjectManifest) else load_project(project)
        root = Path(manifest.project_dir)
        final = root / "final.mp4"
        if manifest.state == ProjectState.COMPLETED.value and final.is_file():
            return manifest
        try:
            manifest.settings["preflight"] = self.preflight(manifest)
            manifest.set_state(ProjectState.GENERATING, stage="unreal_setup")
            manifest.save()
            recipe = root / str(manifest.settings["unreal_recipe"])
            handoff_path = root / "handoff.json"
            env = os.environ.copy()
            env.update({
                "VIDEO_CREATOR_RECIPE": str(recipe),
                "VIDEO_CREATOR_OUTPUT": str(root),
                "VIDEO_CREATOR_HANDOFF": str(handoff_path),
            })
            # Voice first: the film is as long as the narration and every shot starts on its own
            # sentence (a fixed 75 s cut a 92 s voiceover off mid-sentence).
            narration = self._narration(manifest) if manifest.narration_enabled else None
            if not handoff_path.is_file():
                if narration:
                    self._fit_to_narration(manifest, narration, recipe)
                self._run(build_setup_command(self.config), env, root / "logs" / "unreal-setup.log",
                          "Unreal scene setup")
            if not handoff_path.is_file():
                raise RuntimeError("Unreal scene setup wrote no handoff: the build script failed inside the "
                                   f"editor (look for 'LogPython: Error' in {root / 'logs' / 'unreal-setup.log'})")
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            frame_dir = root / "frames"
            expected = manifest.duration_seconds * manifest.fps
            if len(list(frame_dir.glob("*.png"))) < expected:
                manifest.set_state(ProjectState.RENDERING, stage="movie_render_queue")
                manifest.save()
                self._run(build_render_command(self.config, handoff), env,
                          root / "logs" / "unreal-render.log", "Unreal Movie Render Queue")
            silent = root / "render" / "unreal-silent.mp4"
            if not silent.is_file():
                silent = self._encode_frames(manifest)
            assembly_config = PipelineConfig(discover_services=False, output_root=self.config.output_root,
                                             ffmpeg=self.config.ffmpeg, ffprobe=self.config.ffprobe)
            validation = validate_clip(silent, assembly_config, 1080, 1920, manifest.duration_seconds)
            shot = manifest.shots[0]
            shot.status = "accepted"
            shot.output = str(silent.relative_to(root))
            shot.validation = validation
            manifest.set_state(ProjectState.ASSEMBLING)
            manifest.save()
            outputs = assemble_project(manifest, assembly_config, narration_path=narration)
            final = root / outputs["video"]
            manifest.settings["technical_validation"] = validate_final(
                final, assembly_config, manifest.duration_seconds)
            creative = review_final_video(final, manifest)
            manifest.settings["final_creative_review"] = creative
            if not creative.get("valid"):
                raise RuntimeError("Final Unreal video failed creative review: " +
                                   str(creative.get("fatal_problems") or creative.get("problems") or
                                       creative.get("reason")))
            manifest.outputs = outputs
            manifest.error = None
            manifest.set_state(ProjectState.COMPLETED)
            manifest.save()
            return manifest
        except BaseException as exc:
            manifest.error = str(exc) or type(exc).__name__
            state = ProjectState.CANCELLED if isinstance(exc, KeyboardInterrupt) else ProjectState.FAILED
            manifest.set_state(state, error=manifest.error)
            manifest.save()
            raise
