"""Serialized, resumable shot generation and project orchestration."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from contextlib import AbstractContextManager
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from agents.audio_fx import pick_music
from agents.editor_hailuo import generate_voiceover
from config.paths import PROJECT_ROOT

from .assembly import assemble_project
from .backends import BackendAdapter, GenerationResult, build_backends
from .config import PipelineConfig, resolve_within
from .models import ProjectManifest, ProjectState, completed_shots
from .planner import MINIMAX_SUFFIX, WAN_SUFFIX, reseed
from .project import load_project
from .validation import extract_last_frame, validate_clip, validate_final
from .visual_review import review_clip

log = logging.getLogger("pipeline")


class QueueBusyError(RuntimeError):
    pass


class FileLock(AbstractContextManager):
    """Cross-process exclusive lock with safe stale-owner recovery."""

    def __init__(self, path: Path):
        self.path = path
        self.owned = False

    @staticmethod
    def _alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            # On Windows, os.kill(pid, 0) can affect the target process's exit
            # status. Query the process handle instead so lock inspection is
            # strictly non-destructive.
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            process_query_limited_information = 0x1000
            still_active = 259
            handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = json.loads(self.path.read_text(encoding="utf-8"))
                pid = int(owner.get("pid") or 0)
            except (OSError, ValueError, TypeError):
                pid = 0
            if self._alive(pid):
                raise QueueBusyError(f"The GPU queue is already owned by process {pid}")
            try:
                self.path.unlink()
            except OSError as exc:
                raise QueueBusyError(f"Could not recover stale GPU queue lock: {exc}") from exc
            return self.__enter__()
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "started": time.time()}, stream)
        self.owned = True
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.owned:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self.owned = False
        return False


def _music_path(manifest: ProjectManifest) -> Path | None:
    if manifest.music.strip().lower() in {"", "none", "off", "no music"}:
        return None
    configured = manifest.settings.get("music_path")
    if configured:
        value = Path(configured).expanduser().resolve()
        if value.is_file():
            return value
    folder = Path(os.getenv("MUSIC_DIR") or Path(PROJECT_ROOT) / "assets" / "music")
    tracks = [path for path in folder.glob("*") if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"}]
    preference = {token for token in manifest.music.lower().replace("-", " ").split() if len(token) > 2}
    if tracks and preference:
        tracks.sort(key=lambda path: sum(token in path.stem.lower() for token in preference), reverse=True)
        if any(token in tracks[0].stem.lower() for token in preference):
            return tracks[0]
    picked = pick_music()
    return Path(picked) if picked else None


def _prompt_for_backend(shot, backend: str):
    if backend == "wan" and MINIMAX_SUFFIX in shot.prompt:
        return replace(shot, prompt=shot.prompt.replace(MINIMAX_SUFFIX, WAN_SUFFIX))
    if backend == "minimax" and WAN_SUFFIX in shot.prompt:
        return replace(shot, prompt=shot.prompt.replace(WAN_SUFFIX, MINIMAX_SUFFIX))
    return shot


class QueueRunner:
    def __init__(
        self,
        config: PipelineConfig | None = None,
        backends: dict[str, BackendAdapter] | None = None,
        validator: Callable[..., dict[str, Any]] = validate_clip,
        assembler: Callable[..., dict[str, str]] = assemble_project,
        extractor: Callable[..., Path] = extract_last_frame,
        visual_reviewer: Callable[..., dict[str, Any]] = review_clip,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.config = config or PipelineConfig()
        self.backends = backends or build_backends(self.config)
        self.validator = validator
        self.assembler = assembler
        self.extractor = extractor
        self.visual_reviewer = visual_reviewer
        self.progress = progress

    def _emit(self, manifest: ProjectManifest, backend: str | None = None, error: str | None = None) -> None:
        done = completed_shots(manifest)
        times = [
            float(attempt.get("generation_seconds") or 0)
            for shot in manifest.shots for attempt in shot.attempts if attempt.get("status") == "accepted"
        ]
        average = sum(times) / len(times) if times else 300.0
        value = {
            "state": manifest.state,
            "active_shot": manifest.active_shot,
            "completed": done,
            "total": len(manifest.shots),
            "elapsed_seconds": round(manifest.elapsed_seconds, 1),
            "estimated_remaining_seconds": round(average * (len(manifest.shots) - done), 1),
            "backend": backend,
            "error": error,
        }
        log.info(
            "Local AI %s | shot %s | %s/%s | backend=%s | elapsed=%.1fs | ETA=%.1fs%s",
            value["state"], value["active_shot"] or "-", done, len(manifest.shots), backend or "-",
            value["elapsed_seconds"], value["estimated_remaining_seconds"],
            f" | error={error}" if error else "",
        )
        if self.progress:
            self.progress(value)

    def _control_state(self, manifest: ProjectManifest) -> str:
        try:
            return ProjectManifest.load(Path(manifest.project_dir) / "project.json").state
        except (OSError, ValueError, TypeError):
            return manifest.state

    def _log(self, manifest: ProjectManifest, event: dict[str, Any]) -> None:
        path = Path(manifest.project_dir) / "logs" / "generation.jsonl"
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _backend_sequence(self, manifest: ProjectManifest) -> list[str]:
        if manifest.preferred_backend == "auto":
            return ["minimax", "wan"]
        return [manifest.preferred_backend]

    def _reference_for(self, manifest: ProjectManifest, index: int) -> Path | None:
        if index > 0:
            previous = manifest.shots[index - 1]
            if previous.last_frame:
                candidate = resolve_within(manifest.project_dir, previous.last_frame)
                if candidate.is_file():
                    return candidate
        if manifest.reference_image:
            candidate = resolve_within(manifest.project_dir, manifest.reference_image)
            if candidate.is_file():
                return candidate
        return None

    def _generate_shot(self, manifest: ProjectManifest, index: int) -> bool:
        shot = manifest.shots[index]
        sequence = self._backend_sequence(manifest)
        primary_failures = 0
        total_attempts = self.config.retry_limit + 1
        last_error = "No backend was attempted"
        revision_notes: list[str] = []
        for attempt_index in range(total_attempts):
            backend_name = sequence[0]
            if len(sequence) > 1 and primary_failures >= self.config.fallback_failures:
                backend_name = sequence[1]
            backend = self.backends[backend_name]
            available, reason = backend.available()
            if not available:
                last_error = reason
                if backend_name == "minimax" and len(sequence) > 1:
                    primary_failures = self.config.fallback_failures
                    manifest.record("backend_fallback", shot=shot.id, from_backend="minimax", to_backend="wan", reason=reason)
                    manifest.save()
                    backend_name = "wan"
                    backend = self.backends[backend_name]
                    available, reason = backend.available()
                    if not available:
                        last_error = reason
                        break
                else:
                    break
            if backend_name != sequence[0] and not any(
                e.get("event") == "backend_fallback" and e.get("shot") == shot.id for e in manifest.events
            ):
                manifest.record(
                    "backend_fallback", shot=shot.id, from_backend=sequence[0], to_backend=backend_name,
                    reason=f"{primary_failures} MiniMax attempts failed",
                )
            if attempt_index:
                shot.seed = reseed(shot, attempt_index)
            attempt: dict[str, Any] = {
                "number": len(shot.attempts) + 1,
                "backend": backend_name,
                "seed": shot.seed,
                "started_at": time.time(),
                "status": "generating",
            }
            shot.backend = backend_name
            shot.status = "generating"
            shot.error = None
            shot.attempts.append(attempt)
            manifest.active_shot = shot.id
            manifest.set_state(ProjectState.GENERATING, shot=shot.id, backend=backend_name)
            manifest.save()
            self._emit(manifest, backend_name)
            target = Path(manifest.project_dir) / "shots" / f"{shot.id}-attempt-{attempt['number']:02d}.mp4"
            try:
                def submitted(prompt_id: str) -> None:
                    attempt["prompt_id"] = prompt_id
                    manifest.save()

                candidate_shot = _prompt_for_backend(shot, backend_name)
                if revision_notes:
                    candidate_shot = replace(
                        candidate_shot,
                        prompt=candidate_shot.prompt + "\nMANDATORY CORRECTIONS FROM THE PREVIOUS REVIEW: "
                        + " ".join(revision_notes[-2:]),
                    )
                reference = self._reference_for(manifest, index)
                result: GenerationResult = backend.generate(candidate_shot, target, reference, submitted)
                attempt.update({
                    "prompt_id": result.prompt_id,
                    "generation_seconds": round(result.elapsed_seconds, 3),
                    "model": result.model,
                    "settings": result.settings,
                    "status": "validating",
                })
                requested_stop = self._control_state(manifest)
                if requested_stop not in {ProjectState.PAUSED.value, ProjectState.CANCELLED.value}:
                    requested_stop = None
                manifest.elapsed_seconds += result.elapsed_seconds
                manifest.set_state(ProjectState.VALIDATING, shot=shot.id, backend=backend_name)
                manifest.save()
                width = self.config.minimax_width if backend_name == "minimax" else self.config.wan_width
                height = self.config.minimax_height if backend_name == "minimax" else self.config.wan_height
                seconds = self.config.minimax_seconds if backend_name == "minimax" else self.config.wan_frames / self.config.wan_fps
                report = self.validator(result.path, self.config, width, height, seconds)
                visual_report = self.visual_reviewer(result.path, shot, reference, manifest)
                report["semantic_review"] = visual_report
                attempt["validation"] = report
                if not visual_report.get("valid", False):
                    corrections = str(visual_report.get("revision_prompt") or "").strip()
                    if not corrections:
                        corrections = "; ".join(
                            [*visual_report.get("fatal_problems", []), *visual_report.get("problems", [])]
                        )
                    revision_notes.append(corrections or "Match the assigned action and continuity exactly.")
                    raise ValueError("visual review rejected clip: " + revision_notes[-1])
                shot.validation = report
                shot.output = str(result.path.relative_to(manifest.project_dir))
                frame_path = Path(manifest.project_dir) / "shots" / f"{shot.id}-last.jpg"
                try:
                    self.extractor(result.path, frame_path, self.config)
                    shot.last_frame = str(frame_path.relative_to(manifest.project_dir))
                except Exception as frame_error:
                    manifest.record("continuity_frame_failed", shot=shot.id, error=str(frame_error))
                shot.status = "accepted"
                attempt["status"] = "accepted"
                attempt["validation"] = report
                manifest.record("shot_accepted", shot=shot.id, backend=backend_name, attempt=attempt["number"])
                latest_control = self._control_state(manifest)
                if latest_control in {ProjectState.PAUSED.value, ProjectState.CANCELLED.value}:
                    requested_stop = latest_control
                if requested_stop:
                    manifest.state = requested_stop
                    manifest.record("control_applied_after_active_shot", state=requested_stop, shot=shot.id)
                manifest.save()
                self._log(manifest, {"shot": shot.id, **attempt})
                self._emit(manifest, backend_name)
                return True
            except Exception as exc:
                last_error = str(exc)
                attempt.update(status="failed", error=last_error, ended_at=time.time())
                shot.status = "retrying" if attempt_index + 1 < total_attempts else "failed"
                shot.error = last_error
                if backend_name == "minimax":
                    primary_failures += 1
                if target.is_file():
                    rejected = Path(manifest.project_dir) / "rejected" / target.name
                    try:
                        shutil.move(str(target), str(rejected))
                        attempt["rejected_output"] = str(rejected.relative_to(manifest.project_dir))
                    except OSError:
                        pass
                manifest.record("shot_attempt_failed", shot=shot.id, backend=backend_name,
                                attempt=attempt["number"], error=last_error)
                requested_stop = self._control_state(manifest)
                if requested_stop in {ProjectState.PAUSED.value, ProjectState.CANCELLED.value}:
                    manifest.state = requested_stop
                manifest.save()
                self._log(manifest, {"shot": shot.id, **attempt})
                self._emit(manifest, backend_name, last_error)
                if requested_stop in {ProjectState.PAUSED.value, ProjectState.CANCELLED.value}:
                    return False
        reference = self._reference_for(manifest, index)
        if reference and manifest.settings.get("allow_still_replacement", False):
            replacement = Path(manifest.project_dir) / "shots" / f"{shot.id}-still-replacement.mp4"
            duration = shot.duration_seconds
            frames = max(1, round(duration * 30))
            video_filter = (
                f"scale={self.config.minimax_width}:{self.config.minimax_height}:"
                "force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={self.config.minimax_width}:{self.config.minimax_height},"
                f"zoompan=z='min(zoom+0.0008,1.08)':d={frames}:"
                f"s={self.config.minimax_width}x{self.config.minimax_height}:fps=30,format=yuv420p"
            )
            command = [
                self.config.ffmpeg, "-y", "-loop", "1", "-i", str(reference),
                "-vf", video_filter, "-t", f"{duration:.6f}", "-an", "-c:v", "libx264",
                "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(replacement),
            ]
            process = subprocess.run(command, capture_output=True, text=True, timeout=300)
            if process.returncode == 0 and replacement.is_file():
                try:
                    report = self.validator(
                        replacement, self.config, self.config.minimax_width,
                        self.config.minimax_height, duration,
                    )
                    shot.backend = "still-replacement"
                    shot.validation = report
                    shot.output = str(replacement.relative_to(manifest.project_dir))
                    shot.status = "accepted"
                    shot.error = None
                    frame_path = Path(manifest.project_dir) / "shots" / f"{shot.id}-last.jpg"
                    try:
                        self.extractor(replacement, frame_path, self.config)
                        shot.last_frame = str(frame_path.relative_to(manifest.project_dir))
                    except Exception:
                        pass
                    manifest.record("shot_replaced_with_animated_still", shot=shot.id, reference=str(reference))
                    manifest.save()
                    self._emit(manifest, "still-replacement")
                    return True
                except Exception as replacement_error:
                    last_error = f"{last_error}; still replacement failed: {replacement_error}"
            elif process.returncode != 0:
                last_error = f"{last_error}; still replacement failed: {process.stderr[-500:]}"
        shot.status = "failed"
        shot.error = last_error
        manifest.error = f"{shot.id}: {last_error}"
        manifest.save()
        return False

    def _narration(self, manifest: ProjectManifest) -> Path | None:
        if not manifest.narration_enabled or not str(manifest.script.get("spoken_script") or "").strip():
            return None
        target = Path(manifest.project_dir) / "audio" / "narration.mp3"
        if target.is_file():
            return target
        source, duration = generate_voiceover(manifest.script["spoken_script"], voice=manifest.voice)
        shutil.move(source, target)
        manifest.record("narration_created", duration=duration, path=str(target.relative_to(manifest.project_dir)))
        manifest.save()
        return target

    def run(self, project: str | Path | ProjectManifest, shots: set[int] | None = None) -> ProjectManifest:
        manifest = project if isinstance(project, ProjectManifest) else load_project(project, self.config)
        lock_path = self.config.output_root / ".gpu-generation.lock"
        with FileLock(lock_path):
            if manifest.started_at is None:
                from .models import utc_now
                manifest.started_at = utc_now()
            manifest.error = None
            manifest.set_state(ProjectState.QUEUED, resumed=completed_shots(manifest) > 0)
            manifest.save()
            for index, shot in enumerate(manifest.shots):
                if shots is not None and index + 1 not in shots:
                    continue
                if shot.status == "accepted" and shot.output and resolve_within(manifest.project_dir, shot.output).is_file():
                    continue
                control = self._control_state(manifest)
                if control in {ProjectState.PAUSED.value, ProjectState.CANCELLED.value}:
                    manifest.state = control
                    manifest.active_shot = None
                    manifest.record("queue_stopped", reason=control)
                    manifest.save()
                    return manifest
                if not self._generate_shot(manifest, index):
                    control = self._control_state(manifest)
                    if control in {ProjectState.PAUSED.value, ProjectState.CANCELLED.value}:
                        manifest.state = control
                        manifest.active_shot = None
                        manifest.record("queue_stopped", reason=control)
                        manifest.save()
                        return manifest
                    manifest.active_shot = None
                    manifest.set_state(
                        ProjectState.PARTIALLY_COMPLETED if completed_shots(manifest) else ProjectState.FAILED,
                        failed_shot=shot.id,
                    )
                    manifest.save()
                    return manifest
            if shots is not None and completed_shots(manifest) < len(manifest.shots):
                manifest.active_shot = None
                manifest.set_state(ProjectState.PARTIALLY_COMPLETED, reason="selected_shots_only")
                manifest.save()
                return manifest
            try:
                manifest.active_shot = None
                manifest.set_state(ProjectState.ASSEMBLING)
                manifest.save()
                self._emit(manifest)
                narration = self._narration(manifest)
                manifest.set_state(ProjectState.RENDERING)
                manifest.save()
                self._emit(manifest)
                manifest.outputs = self.assembler(manifest, self.config, narration, _music_path(manifest))
                final = resolve_within(manifest.project_dir, manifest.outputs["video"])
                report = validate_final(final, self.config, manifest.duration_seconds)
                manifest.settings["final_validation"] = report
                from .models import utc_now
                manifest.completed_at = utc_now()
                manifest.set_state(ProjectState.COMPLETED)
            except Exception as exc:
                manifest.error = str(exc)
                manifest.set_state(ProjectState.PARTIALLY_COMPLETED, stage="assembly", error=str(exc))
            manifest.save()
            return manifest
