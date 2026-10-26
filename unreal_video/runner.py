"""Headless UE5 build/render orchestration and software-owned post production."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agents.voice import elevenlabs_keys, generate_voiceover
from local_video.assembly import assemble_project
from local_video.config import PipelineConfig
from local_video.models import ProjectManifest, ProjectState
from local_video.validation import validate_clip, validate_final
from local_video.visual_review import review_final_video

from .config import UnrealConfig
from .project import load_project


def build_setup_command(config: UnrealConfig) -> list[str]:
    if config.editor is None:
        raise RuntimeError("Unreal Engine 5 is not installed. Install UE 5.8 or set UNREAL_EDITOR_CMD.")
    return [
        str(config.editor), str(config.project),
        f'-ExecutePythonScript="{config.setup_script}"',
        "-unattended", "-nop4", "-nosplash", "-NoSound", "-stdout", "-FullStdOutLogOutput",
    ]


def build_render_command(config: UnrealConfig, handoff: dict[str, Any]) -> list[str]:
    if config.editor is None:
        raise RuntimeError("Unreal Engine 5 is not installed. Install UE 5.8 or set UNREAL_EDITOR_CMD.")
    return [
        str(config.editor), str(config.project), str(handoff["map"]), "-game",
        f'-LevelSequence={handoff["sequence"]}',
        f'-MoviePipelineConfig={handoff["config"]}',
        "-windowed", f"-resx={config.width}", f"-resy={config.height}",
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
        checks["visual_qc_key"] = bool(os.getenv("ANTHROPIC_API_KEY"))
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
        if not checks["visual_qc_key"] and os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") != "1":
            problems.append("ANTHROPIC_API_KEY is required for fail-closed final visual review")
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
            if not handoff_path.is_file():
                self._run(build_setup_command(self.config), env, root / "logs" / "unreal-setup.log",
                          "Unreal scene setup")
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
            narration = None
            if manifest.narration_enabled:
                narration = root / "audio" / "narration.mp3"
                if not narration.is_file():
                    source, seconds = generate_voiceover(manifest.script["spoken_script"], voice=manifest.voice)
                    shutil.move(source, narration)
                    manifest.record("narration_created", duration=seconds, path=str(narration.relative_to(root)))
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
