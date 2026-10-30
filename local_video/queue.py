"""Serialized, resumable shot generation and project orchestration."""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import threading
import time
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from agents.audio_fx import pick_music
from agents.media import get_duration
from agents.voice import generate_voiceover
from config.paths import PROJECT_ROOT

from .assembly import assemble_project
from .backends import BackendAdapter, GenerationResult, MiniMaxAdapter, _remove_generated_audio, build_backends
from .freevideo import ensure_minimax
from .keyframes import prepare_keyframes, usable_keyframe
from .config import PipelineConfig, default_output_root, resolve_within
from .models import ProjectManifest, ProjectState, completed_shots, estimated_remaining_seconds
from .planner import (
    MAX_DURATION, MIN_DURATION, MINIMAX_SUFFIX, WAN_SUFFIX, allocate_frames, allocate_story_frames, _continuity, construct_prompt, continuation_source, framing_for, framing_scale, payoff_of,
    reseed, shot_objects,
)
from .project import load_project
from .preflight import run_preflight
from .validation import extract_last_frame, ffprobe, media_metadata, validate_clip, validate_final
from .visual_review import review_clip, review_final_video

log = logging.getLogger("pipeline")

# Breathing room after the last spoken word before the video ends.
NARRATION_TAIL_SECONDS = 0.6


TIKTOK_MIN_SECONDS = 61                # TikTok pays (Creator Rewards) only on videos over 1 minute

class QueueBusyError(RuntimeError):
    pass


GPU_LOCK_NAME = ".gpu-generation.lock"


class VisualReviewRejected(ValueError):
    """A usable render that failed the director's story/continuity review."""


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

    @staticmethod
    def _created_at(pid: int) -> float | None:
        """Unix time the process started, or None when it cannot be read."""
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
            kernel32.GetProcessTimes.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return None
            try:
                times = [wintypes.FILETIME() for _ in range(4)]
                if not kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
                    return None
                ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
                return (ticks - 116444736000000000) / 1e7
            finally:
                kernel32.CloseHandle(handle)
        try:
            import psutil
            return psutil.Process(pid).create_time()
        except Exception:
            return None

    @classmethod
    def _owner_alive(cls, pid: int, started: float) -> bool:
        if not cls._alive(pid):
            return False
        # The owner wrote the lock after it started. A process with that pid that started
        # later is a different program that reused the number (typically after a reboot).
        created = cls._created_at(pid)
        return not (created is not None and started and created > started + 1)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = json.loads(self.path.read_text(encoding="utf-8"))
                pid = int(owner.get("pid") or 0)
                started = float(owner.get("started") or 0)
            except (OSError, ValueError, TypeError, AttributeError):
                pid, started = 0, 0.0
            if self._owner_alive(pid, started):
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


@contextmanager
def gpu_lock(root: Path | None = None):
    """Hold the GPU lock every route shares (local-ai, director, Chatterbox), waiting while another run owns it."""
    lock = FileLock((root or default_output_root()) / GPU_LOCK_NAME)
    while True:
        try:
            lock.__enter__()
            break
        except QueueBusyError as exc:
            log.info("GPU busy (%s); waiting", exc)
            time.sleep(60)
    try:
        yield lock
    finally:
        lock.__exit__(None, None, None)


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


DEGRADATION_KIND = {
    "shot_accepted_best_take": "best_take",
    "shot_accepted_flawed_take": "flawed_take",
    "shot_replaced_with_animated_still": "still",
}


def _prompt_for_backend(shot, backend: str):
    if backend == "wan" and MINIMAX_SUFFIX in shot.prompt:
        return replace(shot, prompt=shot.prompt.replace(MINIMAX_SUFFIX, WAN_SUFFIX))
    if backend == "minimax" and WAN_SUFFIX in shot.prompt:
        return replace(shot, prompt=shot.prompt.replace(WAN_SUFFIX, MINIMAX_SUFFIX))
    return shot


def _rebuilt_prompt(shot, description: str, camera: str) -> str:
    """A fresh H3 prompt for this shot around a new description, from the fields the shot keeps."""
    return construct_prompt(
        subject_action=description,
        camera_action=camera,
        ambience=shot.ambience,
        continuity=shot.continuity or {},
        framing=framing_for(shot.subject_action, camera),
        backend="wan" if WAN_SUFFIX in shot.prompt else "minimax",
        cast_names=list(shot.cast) or None,
        light=shot.light,
        handoff=payoff_of(shot.subject_action),
    )


def _retake_prompt(shot, correction: str, has_reference: bool) -> str:
    """The next take: the reviewer's corrected description of the shot, as a clean H3 prompt.

    Retakes used to stack orders ("DIRECTOR'S RETAKE", the review note, then the whole first
    prompt) into 1,000+ words that still carried the wording behind the defect; later takes
    passed no more often than first ones (31% against 28%). The reviewer's revision_prompt is
    already a positive description written for the generator, so it replaces the beat text; the
    beat's own end state stays the target. `has_reference` is applied by the backend, which
    marks the supplied first frame.
    """
    correction = correction.strip()
    # A short note ("Keep the regulator visible.") amends the beat; a full description replaces it.
    description = correction if len(correction) >= 60 else f"{shot.subject_action} {correction}".strip()
    return _rebuilt_prompt(shot, description, shot.camera_action)


def _repair_prompt(shot) -> str:
    """The last take for a shot every normal take failed: hold on its end state, with no move.

    On the 2026-10-27 volcano run MiniMax ignored every reveal it was given: a pan to "another"
    lava flow kept the first flow and drifted to a green hill, and a close-up of a wave on rock
    pulled back to a wide aerial on all six takes. A locked-off view of the payoff is the one
    thing it renders reliably, and the narration still carries the beat.
    """
    held = (f"{payoff_of(shot.subject_action)} The framing, distance and angle stay exactly the same "
            "in every frame; the only motion is natural motion inside the scene, such as water, "
            "smoke, steam, cloud or light.")
    return _rebuilt_prompt(shot, held, "locked-off static camera")


def _is_infrastructure_failure(exc: Exception) -> bool:
    """Identify transient service/GPU failures that should not spend a creative attempt."""
    if isinstance(exc, VisualReviewRejected):
        return False
    message = str(exc).lower()
    return any(token in message for token in (
        "cuda error", "acceleratorerror", "worker exited", "generation timeout",
        "timed out", "connection error", "connection aborted", "connection refused",
        "service unavailable", "remote end closed", "comfyui generation failed",
        "connection lost", "max retries exceeded", "actively refused",
    ))


class QueueRunner:
    def __init__(
        self,
        config: PipelineConfig | None = None,
        backends: dict[str, BackendAdapter] | None = None,
        validator: Callable[..., dict[str, Any]] = validate_clip,
        assembler: Callable[..., dict[str, str]] = assemble_project,
        extractor: Callable[..., Path] = extract_last_frame,
        visual_reviewer: Callable[..., dict[str, Any]] = review_clip,
        final_reviewer: Callable[..., dict[str, Any]] = review_final_video,
        preflight: Callable[..., dict[str, Any]] = run_preflight,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.config = config or PipelineConfig()
        self.backends = backends or build_backends(self.config)
        self.validator = validator
        self.assembler = assembler
        self.extractor = extractor
        self.visual_reviewer = visual_reviewer
        self.final_reviewer = final_reviewer
        self.preflight = preflight
        self.progress = progress
        self._speculation: dict[str, Any] | None = None
        self._selected: set[int] | None = None

    def _emit(self, manifest: ProjectManifest, backend: str | None = None, error: str | None = None) -> None:
        done = completed_shots(manifest)
        value = {
            "state": manifest.state,
            "active_shot": manifest.active_shot,
            "completed": done,
            "total": len(manifest.shots),
            "elapsed_seconds": round(manifest.elapsed_seconds, 1),
            "estimated_remaining_seconds": round(estimated_remaining_seconds(manifest), 1),
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

    @staticmethod
    def _reference_source(manifest: ProjectManifest, index: int) -> int | None:
        return continuation_source(
            [(s.scene.lower(), s.light.lower()) for s in manifest.shots], index, [s.cast for s in manifest.shots],
            [framing_scale(s.subject_action) for s in manifest.shots],
            [shot_objects(manifest.script, s.continuity) for s in manifest.shots],
        )

    def _reference_for(self, manifest: ProjectManifest, index: int) -> Path | None:
        source = self._reference_source(manifest, index)
        if source is not None:
            previous = manifest.shots[source]
            if previous.last_frame:
                candidate = resolve_within(manifest.project_dir, previous.last_frame)
                if candidate.is_file():
                    return candidate
        if index > 0 and manifest.shots[index].scene:
            # A hard cut opens fresh; a shared reference image would drag every cut back to one frame.
            return usable_keyframe(manifest, manifest.shots[index])
        if manifest.reference_image:
            candidate = resolve_within(manifest.project_dir, manifest.reference_image)
            if candidate.is_file():
                return candidate
        return usable_keyframe(manifest, manifest.shots[index])

    def _generate_shot(self, manifest: ProjectManifest, index: int) -> bool:
        shot = manifest.shots[index]
        for prior in shot.attempts:
            if prior.get("status") in {"generating", "validating"}:
                prior.update(status="failed", error="generation process ended before the attempt completed",
                             ended_at=time.time())
        sequence = self._backend_sequence(manifest)
        primary_failures = 0
        total_attempts = self.config.retry_limit + 1
        infrastructure_retry_limit = 2
        # One extra take with the move stripped out, spent only once every normal take was rejected.
        repair_used = not self.config.repair_take
        repairing = False
        maximum_attempts = total_attempts + infrastructure_retry_limit + (0 if repair_used else 1)
        creative_failures = 0
        infrastructure_failures = 0
        last_error = "No backend was attempted"
        revision_notes: list[tuple[float, str]] = []
        for prior in shot.attempts:
            review = (prior.get("validation") or {}).get("semantic_review") or {}
            correction = str(review.get("revision_prompt") or "").strip()
            if not correction and not review.get("valid", True):
                correction = shot.subject_action
            if correction and not review.get("valid", True):
                revision_notes.append((float(review.get("average_score") or 0), correction[:1200]))
        for attempt_index in range(maximum_attempts):
            if creative_failures >= total_attempts:
                if repair_used or not revision_notes:
                    break
                repair_used, repairing = True, True
                total_attempts += 1
                manifest.record("shot_repair_take", shot=shot.id)
                log.warning("Local AI %s: every take was rejected; trying one held-camera repair take.", shot.id)
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

                reference = self._reference_for(manifest, index)
                if reference is not None and reference.parent.name == "keyframes":
                    attempt["keyframe"] = True
                candidate_shot = _prompt_for_backend(shot, backend_name)
                if repairing:
                    attempt["repair"] = True
                    candidate_shot = replace(candidate_shot, prompt=_repair_prompt(candidate_shot))
                elif revision_notes:
                    best_correction = max(revision_notes, key=lambda item: item[0])[1]
                    candidate_shot = replace(
                        candidate_shot,
                        prompt=_retake_prompt(candidate_shot, best_correction, reference is not None),
                    )
                job = None if revision_notes else self._take_speculation(manifest, index, backend_name, shot.seed)
                if job:
                    attempt.update(started_at=job["started_at"], speculative=True)
                    if job["prompt_id"]:
                        attempt["prompt_id"] = job["prompt_id"]
                    if job["error"]:
                        raise job["error"]
                    result: GenerationResult = job["result"]
                else:
                    result = backend.generate(candidate_shot, target, reference, submitted)
                if self._control_state(manifest) not in {ProjectState.PAUSED.value, ProjectState.CANCELLED.value}:
                    self._start_speculation(manifest, index, result.path, backend_name)
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
                seconds = backend.clip_seconds(shot)
                report = self.validator(result.path, self.config, width, height, seconds)
                visual_report = self.visual_reviewer(result.path, shot, reference, manifest)
                report["semantic_review"] = visual_report
                attempt["validation"] = report
                if not visual_report.get("valid", False):
                    corrections = str(visual_report.get("revision_prompt") or "").strip()
                    if not corrections:
                        corrections = (
                            f"Render the assigned current action exactly: {shot.subject_action}. "
                            f"Use {shot.camera_action}. Preserve the required start and end states, one continuous "
                            "take, one protagonist, stable anatomy and identity."
                        )
                    correction = (corrections or "Match the assigned action and continuity exactly.")[:1200]
                    revision_notes.append((float(visual_report.get("average_score") or 0), correction))
                    # Log what the reviewer saw wrong; the correction is the next take's prompt and
                    # says nothing about why this take failed.
                    reasons = [*visual_report.get("fatal_problems", []), *visual_report.get("problems", [])]
                    reason = " | ".join(str(item) for item in reasons[:3]) or visual_report.get("reason") or correction
                    raise VisualReviewRejected(
                        f"visual review rejected clip (avg {visual_report.get('average_score', '?')}, "
                        f"{visual_report.get('acceptance', 'rejected')}): {str(reason)[:600]}"
                    )
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
                attempt["ended_at"] = time.time()
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
                # The next shot was rendering from this take's last frame; that frame is now wrong.
                self._cancel_speculation(manifest, f"{shot.id} attempt {attempt['number']} failed")
                last_error = str(exc)
                attempt.update(status="failed", error=last_error, ended_at=time.time())
                transient = _is_infrastructure_failure(exc)
                if transient and infrastructure_failures < infrastructure_retry_limit:
                    infrastructure_failures += 1
                    manifest.record(
                        "infrastructure_retry", shot=shot.id, backend=backend_name,
                        retry=infrastructure_failures, limit=infrastructure_retry_limit,
                    )
                    if backend_name == "minimax":
                        self._restart_minimax(manifest)
                else:
                    creative_failures += 1
                retries_left = creative_failures < total_attempts and attempt_index + 1 < maximum_attempts
                shot.status = "retrying" if retries_left else "failed"
                shot.error = last_error
                if backend_name == "minimax" and not isinstance(exc, VisualReviewRejected):
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
        if self._accept_fallback(manifest, index, last_error):
            return True
        shot.status = "failed"
        shot.error = last_error
        manifest.error = f"{shot.id}: {last_error}"
        manifest.save()
        return False

    def _start_speculation(self, manifest: ProjectManifest, index: int, clip: Path, backend_name: str) -> None:
        """Render the next shot while this take is reviewed, from this take's last frame.

        Only a fresh next shot on the primary backend is started, with exactly the prompt, seed,
        reference and target its first attempt would use, so an accepted take loses nothing.
        """
        following = index + 1
        if (not self.config.speculative_next_shot or following >= len(manifest.shots)
                or (self._selected is not None and following + 1 not in self._selected)):
            return
        shot = manifest.shots[following]
        if shot.attempts or shot.status == "accepted" or backend_name != self._backend_sequence(manifest)[0]:
            return
        if self._reference_source(manifest, following) == index:
            frame = Path(manifest.project_dir) / "shots" / f"{manifest.shots[index].id}-candidate-last.jpg"
            try:
                self.extractor(clip, frame, self.config)
            except Exception:
                return
        else:
            frame = self._reference_for(manifest, following)  # a cut: it never opens on this take
        backend = self.backends[backend_name]
        candidate = _prompt_for_backend(shot, backend_name)
        job: dict[str, Any] = {
            "index": following, "backend": backend_name, "seed": shot.seed, "started_at": time.time(),
            "target": Path(manifest.project_dir) / "shots" / f"{shot.id}-attempt-01.mp4",
            "prompt_id": None, "result": None, "error": None,
        }

        def work() -> None:
            try:
                job["result"] = backend.generate(candidate, job["target"], frame,
                                                 lambda prompt_id: job.__setitem__("prompt_id", prompt_id))
            except Exception as exc:
                job["error"] = exc

        job["thread"] = threading.Thread(target=work, name=f"speculative-{shot.id}", daemon=True)
        job["thread"].start()
        self._speculation = job
        manifest.record("speculative_shot_started", shot=shot.id)

    def _take_speculation(self, manifest: ProjectManifest, index: int, backend_name: str, seed: int):
        """Hand over the next shot's early render if it matches this attempt, waiting for it to finish."""
        job = self._speculation
        if not job:
            return None
        if (job["index"], job["backend"], job["seed"]) != (index, backend_name, seed):
            self._cancel_speculation(manifest, "the plan for that shot changed")
            return None
        self._speculation = None
        job["thread"].join()
        return job

    def _cancel_speculation(self, manifest: ProjectManifest, reason: str) -> None:
        job, self._speculation = self._speculation, None
        if not job:
            return
        thread = job["thread"]
        deadline = time.monotonic() + 60
        while thread.is_alive() and not job["prompt_id"] and time.monotonic() < deadline:
            thread.join(0.5)  # it needs a prompt id before it can be cancelled
        if thread.is_alive() and job["prompt_id"]:
            self.backends[job["backend"]].cancel(job["prompt_id"])
        thread.join(300)
        try:
            job["target"].unlink(missing_ok=True)
        except OSError:
            pass
        manifest.record("speculative_shot_cancelled", shot=manifest.shots[job["index"]].id, reason=reason)
        manifest.save()

    def _finish_fallback(self, manifest: ProjectManifest, shot, path: Path, report: dict[str, Any],
                         backend: str, event: str, **details: Any) -> bool:
        shot.backend = backend
        shot.validation = report
        shot.output = str(path.relative_to(manifest.project_dir))
        shot.status = "accepted"
        shot.error = None
        # "accepted" here means "kept so the run can continue", not "passed review". Record which
        # compromise was made: the degradation budget counts these, and a still is never reused as a
        # continuity source.
        shot.degraded = DEGRADATION_KIND.get(event, "salvaged")
        frame_path = Path(manifest.project_dir) / "shots" / f"{shot.id}-last.jpg"
        try:
            self.extractor(path, frame_path, self.config)
            shot.last_frame = str(frame_path.relative_to(manifest.project_dir))
        except Exception as frame_error:
            manifest.record("continuity_frame_failed", shot=shot.id, error=str(frame_error))
        manifest.record(event, shot=shot.id, degraded=shot.degraded, **details)
        manifest.save()
        log.warning("Local AI %s: no take passed review; %s so the video can continue.",
                    shot.id, event.replace("_", " "))
        self._emit(manifest, backend)
        return True

    def _restore_take(self, manifest: ProjectManifest, shot, attempt: dict[str, Any], event: str) -> bool:
        source = resolve_within(manifest.project_dir, attempt["rejected_output"])
        target = Path(manifest.project_dir) / "shots" / source.name
        try:
            shutil.move(str(source), str(target))
        except OSError:
            return False
        attempt["status"] = "accepted"
        attempt.pop("rejected_output", None)
        review = attempt["validation"].get("semantic_review") or {}
        return self._finish_fallback(
            manifest, shot, target, attempt["validation"], attempt.get("backend") or "minimax", event,
            attempt=attempt.get("number"), score=review.get("average_score"),
            fatal_problems=review.get("fatal_problems") or [],
        )

    def _still_replacement(self, manifest: ProjectManifest, shot, reference: Path | None) -> bool:
        """A slow push-in on reference; with no reference, a dark ash-grey card (the very last resort)."""
        replacement = Path(manifest.project_dir) / "shots" / f"{shot.id}-still-replacement.mp4"
        duration = shot.duration_seconds
        frames = max(1, round(duration * 30))
        width, height = self.config.minimax_width, self.config.minimax_height
        video_filter = (
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={width}:{height},"
            f"zoompan=z='min(zoom+0.0008,1.08)':d={frames}:"
            f"s={width}x{height}:fps=30,format=yuv420p"
        )
        source = (["-loop", "1", "-i", str(reference)] if reference is not None
                  else ["-f", "lavfi", "-i", f"color=c=0x1c1f22:s={width}x{height}:r=30"])
        command = [
            self.config.ffmpeg, "-y", *source,
            "-vf", video_filter, "-t", f"{duration:.6f}", "-an", "-c:v", "libx264",
            "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(replacement),
        ]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as exc:
            manifest.record("still_replacement_failed", shot=shot.id, error=str(exc))
            return False
        if process.returncode != 0 or not replacement.is_file():
            manifest.record("still_replacement_failed", shot=shot.id, error=process.stderr[-500:])
            return False
        try:
            report = self.validator(replacement, self.config, self.config.minimax_width,
                                    self.config.minimax_height, duration)
        except Exception as exc:
            if reference is not None:
                manifest.record("still_replacement_failed", shot=shot.id, error=str(exc))
                return False
            report = {"valid": False, "error": str(exc)}  # a flat card is frozen by design
        return self._finish_fallback(manifest, shot, replacement, report, "still-replacement",
                                     "shot_replaced_with_animated_still",
                                     reference=str(reference) if reference is not None else "plain card")

    def _accept_fallback(self, manifest: ProjectManifest, index: int, last_error: str) -> bool:
        """When every take was rejected, keep the video going with the least bad option.

        Order: the best reviewed take without fatal problems, then a slow push-in on a real
        generated frame, then the best reviewed take even with fatal problems. Takes that failed
        technical validation (black, frozen, wrong size) are never used.
        """
        shot = manifest.shots[index]
        takes = []
        for attempt in shot.attempts:
            review = (attempt.get("validation") or {}).get("semantic_review")
            relative = attempt.get("rejected_output")
            if not review or not relative or not resolve_within(manifest.project_dir, relative).is_file():
                continue
            takes.append((float(review.get("average_score") or 0), bool(review.get("fatal_problems")), attempt))
        takes.sort(key=lambda take: take[0], reverse=True)
        clean = [take for take in takes if not take[1]]
        if clean and self._restore_take(manifest, shot, clean[0][2], "shot_accepted_best_take"):
            return True
        reference = self._still_source(manifest, index)
        if reference and self._still_replacement(manifest, shot, reference):
            return True
        if takes and self._restore_take(manifest, shot, takes[0][2], "shot_accepted_flawed_take"):
            return True
        # Nothing reviewable was rendered (every attempt was an infrastructure or technical failure).
        # A run must still finish, so animate the nearest real image, and only then a plain card.
        for candidate in self._last_resort_frames(manifest, index):
            if self._still_replacement(manifest, shot, candidate):
                return True
        return self._still_replacement(manifest, shot, None)

    def _last_resort_frames(self, manifest: ProjectManifest, index: int) -> list[Path]:
        """Real images to animate when the shot has none of its own: its keyframe, the nearest
        genuinely rendered frame from any other shot, then the project reference image."""
        frames: list[Path] = []
        keyframe = usable_keyframe(manifest, manifest.shots[index])
        if keyframe:
            frames.append(keyframe)
        others = sorted((s for i, s in enumerate(manifest.shots) if i != index), key=lambda s: abs(s.index - index))
        for other in others:
            if other.status == "accepted" and other.degraded != "still" and other.last_frame:
                frame = resolve_within(manifest.project_dir, other.last_frame)
                if frame.is_file():
                    frames.append(frame)
                    break
        if manifest.reference_image:
            reference = resolve_within(manifest.project_dir, manifest.reference_image)
            if reference.is_file():
                frames.append(reference)
        return frames

    def _still_source(self, manifest: ProjectManifest, index: int) -> Path | None:
        """A frame to build a still push-in from, never one belonging to another still.

        Chaining them turns consecutive shots into zooms of a single frame several shots back, which
        is precisely the "repeated variations of the same scene, so the edit loops instead of
        progressing" defect the final creative review rejects. With no real frame to fall back on,
        no still is made: failing the shot is better than manufacturing that defect.
        """
        source = self._reference_source(manifest, index)
        seen = set()
        while source is not None and source not in seen and manifest.shots[source].degraded == "still":
            seen.add(source)
            source = self._reference_source(manifest, source)
        if source is None or source in seen:
            return None
        previous = manifest.shots[source]
        if not previous.last_frame:
            return None
        candidate = resolve_within(manifest.project_dir, previous.last_frame)
        return candidate if candidate.is_file() else None

    @staticmethod
    def _recovery_hint(manifest: ProjectManifest, redo=()) -> str:
        """Name the project and the exact command that reuses everything already rendered."""
        lines = [f"The render so far is kept in {manifest.project_dir}"]
        selection = ",".join(str(shot.index + 1) for shot in redo)
        if selection:
            # --redo is required: those shots are marked accepted, and the queue skips an accepted
            # shot, so `--shots` on its own would re-review the same edit and fail again.
            lines.append("Fix those shots' prompts, then re-render only them (every other shot is reused):")
            lines.append(f'  python -m local_video.cli run "{manifest.project_dir}" '
                         f'--shots {selection} --redo')
        return "\n".join(lines)

    def _degradation_stop(self, manifest: ProjectManifest, shots: set[int] | None) -> str | None:
        """Stop while the GPU bill is small once salvaged shots make the final review hopeless.

        Every salvaged shot costs the final creative review its story-coherence, continuity and
        pacing scores, so a heavily salvaged render spends hours building a video that gate rejects.
        The remaining shots cannot recover those scores, so there is nothing to gain by finishing.
        The budget is always the whole video's, since that is what the final review sees: sizing it
        from a --shots redo gave a six-shot redo a budget of one, so two hard shots stopped it.
        """
        allowed = self.config.max_degraded_percent
        if allowed >= 100:
            return None
        planned = len(manifest.shots)
        finished = [shot for shot in manifest.shots if shot.status == "accepted"]
        degraded = [shot for shot in finished if shot.degraded]
        budget = planned * allowed // 100
        if not planned or len(degraded) <= budget:
            return None
        stills = sum(1 for shot in degraded if shot.degraded == "still")
        return (
            f"{len(degraded)} of the {len(finished)} finished shots had to be salvaged because no take "
            f"passed review ({stills} replaced with a still push-in). That is past the "
            f"{allowed}% budget ({budget} of {planned} shots), and the remaining shots cannot raise the "
            f"final creative review's story, continuity and pacing scores back over its threshold. "
            f"The run stopped here instead of rendering the rest for a video that gate would reject. "
            f"The prompts are most likely asking for something the backend cannot generate.\n"
            + self._recovery_hint(manifest, degraded)
        )

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

    @staticmethod
    def _upgrade_prompts(manifest: ProjectManifest) -> None:
        """Give a project planned before prompts followed H3's layout the new prompt on resume.

        Done for every unfinished shot before anything renders: the next shot's early render reads
        its stored prompt, so upgrading shot by shot let each one's first take go out in the old
        wording.
        """
        beats = manifest.script.get("beats") if isinstance(manifest.script.get("beats"), list) else []
        upgraded = []
        for shot in manifest.shots:
            if shot.status == "accepted" or not shot.subject_action:
                continue
            if len(beats) == len(manifest.shots):
                # The world lock saved at planning time predates the per-scene filters: a resumed
                # shore shot still carried "Open Pacific sea: a tropical ocean seen from a
                # palm-lined beach", drew it, and its reviewer judged it against it.
                shot.continuity = _continuity(manifest.script, manifest.visual_style, manifest.concept, shot.index)
            prompt = _rebuilt_prompt(shot, shot.subject_action, shot.camera_action)
            if prompt != shot.prompt:
                shot.prompt = prompt
                upgraded.append(shot.id)
        if upgraded:
            manifest.record("shot_prompts_upgraded", shots=upgraded)
            manifest.save()

    def _prepare_minimax(self, manifest: ProjectManifest) -> None:
        """Start FreeVideo when MiniMax is wanted, and never fall back to Wan silently."""
        if "minimax" not in self._backend_sequence(manifest) or not isinstance(self.backends.get("minimax"), MiniMaxAdapter):
            return
        available, detail = ensure_minimax(self.config)
        if available:
            self.backends["minimax"] = MiniMaxAdapter(self.config)
            return
        if manifest.preferred_backend == "minimax":
            raise RuntimeError(f"MiniMax H3 was requested but is unavailable: {detail}")
        manifest.record("minimax_unavailable_at_start", reason=detail)
        manifest.save()
        log.warning("=" * 70)
        log.warning("MiniMax H3 is UNAVAILABLE: %s", detail)
        log.warning("Every shot of this video will use the Wan 2.2 fallback.")
        log.warning("=" * 70)

    def _restart_minimax(self, manifest: ProjectManifest) -> None:
        """After a crash or lost connection, bring FreeVideo back before the retry."""
        if not isinstance(self.backends.get("minimax"), MiniMaxAdapter):
            return
        available, detail = ensure_minimax(self.config)
        manifest.record("minimax_restart_check", available=available, detail=detail)
        if available:
            self.backends["minimax"] = MiniMaxAdapter(self.config)

    def _fit_to_narration(self, manifest: ProjectManifest, narration: Path) -> None:
        """Retime the shot plan to the real voiceover so the final cut never truncates it.

        The script only targets a word count; the spoken length is known once ElevenLabs
        has read it. Shot prompts are unchanged; only their on-screen durations move.
        """
        spoken = get_duration(str(narration))
        needed = spoken + NARRATION_TAIL_SECONDS
        if needed > MAX_DURATION:
            raise ValueError(
                f"Narration is {spoken:.1f}s; local AI videos are at most {MAX_DURATION}s. "
                "Shorten the script and resume."
            )
        # asked for over a minute (TikTok's Creator Rewards threshold): never end up just under it
        floor = TIKTOK_MIN_SECONDS if manifest.duration_seconds > 60 else MIN_DURATION
        target = max(MIN_DURATION, floor, math.ceil(needed))
        if target == manifest.duration_seconds:
            return
        beats = [b for b in manifest.script.get("beats") or [] if isinstance(b, dict)]
        try:
            frames = (allocate_story_frames(target, [str(b.get("text") or "") for b in beats], manifest.fps)
                      if len(beats) == len(manifest.shots) else allocate_frames(target, len(manifest.shots), manifest.fps))
        except ValueError:
            if needed <= manifest.duration_seconds:
                return  # cannot shorten this plan further; a quiet tail is harmless
            raise ValueError(
                f"Narration is {spoken:.1f}s, which {len(manifest.shots)} shots cannot cover "
                f"(project is {manifest.duration_seconds}s). Shorten the script and resume."
            )
        for shot, count in zip(manifest.shots, frames):
            shot.duration_frames = count
        manifest.record("timeline_fitted_to_narration", narration_seconds=round(spoken, 3),
                        from_seconds=manifest.duration_seconds, to_seconds=target)
        log.info("Local AI timeline fitted to narration: %.1fs voice -> %ss video (was %ss)",
                 spoken, target, manifest.duration_seconds)
        manifest.duration_seconds = target
        manifest.save()

    def _silence_accepted_clips(self, manifest: ProjectManifest) -> None:
        """Upgrade legacy accepted clips so native model audio can never reach assembly."""
        changed: list[str] = []
        metadata_changed = False
        for shot in manifest.shots:
            if shot.status != "accepted" or not shot.output:
                continue
            clip = resolve_within(manifest.project_dir, shot.output)
            if not clip.is_file():
                continue
            try:
                has_audio = media_metadata(ffprobe(clip, self.config)).get("has_audio")
            except ValueError:
                continue
            if has_audio:
                _remove_generated_audio(clip, self.config.ffmpeg)
                changed.append(shot.id)
            if shot.validation and (
                shot.validation.get("has_audio") is not False
                or shot.validation.get("audio_codec") is not None
            ):
                shot.validation["has_audio"] = False
                shot.validation["audio_codec"] = None
                metadata_changed = True
        if changed:
            manifest.record("accepted_clip_audio_removed", shots=changed)
        if changed or metadata_changed:
            manifest.save()

    def run(self, project: str | Path | ProjectManifest, shots: set[int] | None = None) -> ProjectManifest:
        manifest = project if isinstance(project, ProjectManifest) else load_project(project, self.config)
        self._selected = shots
        try:
            return self._run(manifest, shots)
        finally:
            # A pause, cancel or failure must not leave a render running on the GPU.
            self._cancel_speculation(manifest, "the run stopped")

    def _run(self, manifest: ProjectManifest, shots: set[int] | None) -> ProjectManifest:
        with FileLock(self.config.output_root / GPU_LOCK_NAME):
            self._silence_accepted_clips(manifest)
            self._upgrade_prompts(manifest)
            # Start FreeVideo before preflight checks the backends: a stopped server is not a
            # missing one. A missing model or a failed/too-long voiceover stops the run before GPU work.
            try:
                self._prepare_minimax(manifest)
            except Exception as exc:
                manifest.error = f"backend: {exc}"
                manifest.set_state(ProjectState.FAILED, stage="backend", error=str(exc))
                manifest.save()
                return manifest
            try:
                manifest.settings["preflight"] = self.preflight(
                    manifest, self.config, self.backends,
                    require_visual_qc=self.visual_reviewer is review_clip,
                )
            except Exception as exc:
                manifest.error = str(exc)
                manifest.set_state(ProjectState.FAILED, stage="preflight", error=str(exc))
                manifest.save()
                self._emit(manifest, error=str(exc))
                raise
            manifest.record("preflight_passed")
            manifest.save()
            if manifest.started_at is None:
                from .models import utc_now
                manifest.started_at = utc_now()
            manifest.error = None
            manifest.set_state(ProjectState.QUEUED, resumed=completed_shots(manifest) > 0)
            manifest.save()
            try:
                narration = self._narration(manifest)
                if narration:
                    self._fit_to_narration(manifest, narration)
            except Exception as exc:
                manifest.error = f"narration: {exc}"
                manifest.set_state(ProjectState.FAILED, stage="narration", error=str(exc))
                manifest.save()
                return manifest
            if isinstance(self.backends.get("minimax"), MiniMaxAdapter):
                try:
                    prepare_keyframes(manifest, self.config, shots)
                except Exception as exc:     # keyframes only improve the look; never block the run
                    log.warning("Keyframes skipped: %s", exc)
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
                hopeless = self._degradation_stop(manifest, shots)
                if hopeless:
                    manifest.active_shot = None
                    manifest.error = hopeless
                    manifest.record("stopped_degradation_budget", shot=shot.id)
                    manifest.set_state(ProjectState.PARTIALLY_COMPLETED, stage="generation", error=hopeless)
                    manifest.save()
                    log.error("Local AI stopped: %s", hopeless)
                    self._emit(manifest, error=hopeless)
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
                try:
                    manifest.outputs = self.assembler(manifest, self.config, narration, _music_path(manifest))
                except Exception as exc:
                    # Assembly is ffmpeg over files already on disk; one retry clears a locked or
                    # half-written intermediate.
                    log.warning("Local AI assembly failed (%s); retrying once.", exc)
                    manifest.record("assembly_retry", error=str(exc))
                    manifest.outputs = self.assembler(manifest, self.config, narration, _music_path(manifest))
                final = resolve_within(manifest.project_dir, manifest.outputs["video"])
                report = validate_final(final, self.config, manifest.duration_seconds)
                manifest.settings["final_validation"] = report
                try:
                    creative_report = self.final_reviewer(final, manifest)
                except Exception as exc:
                    creative_report = {"valid": False, "reason": f"final review crashed: {exc}"}
                manifest.settings["final_creative_review"] = creative_report
                warnings: list[str] = []
                degraded = [shot for shot in manifest.shots if shot.degraded]
                if degraded:
                    stills = sum(1 for shot in degraded if shot.degraded == "still")
                    warnings.append(f"{len(degraded)} of {len(manifest.shots)} shots were salvaged rather than "
                                    f"passing review ({stills} are still push-ins): "
                                    + ", ".join(shot.id for shot in degraded))
                if not creative_report.get("valid", False):
                    details = creative_report.get("fatal_problems") or creative_report.get("problems") or [
                        creative_report.get("reason", "final creative review failed")
                    ]
                    rejection = "Final creative review rejected the video: " + "; ".join(details[:5])
                    if self.config.final_review_blocks:
                        # The assembled video and every accepted shot stay on disk, so say so: this
                        # rejection is a prompt problem to repair, not a render to throw away.
                        raise RuntimeError(rejection + ("\n" + warnings[0] if warnings else "") + "\n"
                                           + self._recovery_hint(manifest, degraded))
                    warnings.insert(0, rejection)
                manifest.settings["quality_warnings"] = warnings
                for warning in warnings:
                    log.warning("Local AI quality warning: %s", warning)
                if warnings:
                    log.warning("Local AI delivered the video anyway. %s", self._recovery_hint(manifest, degraded))
                from .models import utc_now
                manifest.completed_at = utc_now()
                manifest.set_state(ProjectState.COMPLETED)
            except Exception as exc:
                manifest.error = str(exc)
                manifest.set_state(ProjectState.PARTIALLY_COMPLETED, stage="assembly", error=str(exc))
            manifest.save()
            return manifest
