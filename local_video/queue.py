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
from config.paths import PROJECT_ROOT

from . import fast
from .assembly import assemble_project, ensure_narration
from .backends import BackendAdapter, GenerationResult, MiniMaxAdapter, _remove_generated_audio, build_backends
from .freevideo import clear_orphaned_jobs, ensure_minimax, recover_server
from .keyframes import fresh_openings, keyframe_id, prepare_keyframes, usable_keyframe, wardrobe_for
from .config import PipelineConfig, default_output_root, resolve_within
from .models import MANIFEST_LOCK, ProjectManifest, ProjectState, completed_shots, estimated_remaining_seconds
from .planner import (
    MAX_DURATION, MIN_DURATION, MINIMAX_SUFFIX, WAN_SUFFIX, allocate_frames, allocate_story_frames, _continuity, construct_prompt, continuation_source, framing_for, framing_scale, payoff_of,
    reseed, shot_objects, beat_handoff, _names_cast,
)
from .project import load_project, requeue_shot
from .preflight import run_preflight
from .validation import bar_metrics, bar_problem, extract_last_frame, ffprobe, media_metadata, validate_clip, validate_final
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


class ReviewerUnavailable(RuntimeError):
    """The clip reviewer is out of budget or usage: no take can be judged, so the run stops resumably.

    The Ghost Army run (2026-10-31) hit CLAUDE_TOKEN_BUDGET at shot 10 and went on "rejecting" every
    unreviewed take; each remaining shot would have burned four MiniMax takes and ended as a still.
    """


_REVIEWER_OUT = ("BudgetExceeded", "UsageLimit")


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


def _rebuilt_prompt(shot, description: str, camera: str, script: dict | None = None) -> str:
    """A fresh H3 prompt for this shot around a new description, from the fields the shot keeps.

    With the script it keeps what planning had: the beat's own end state (`continuity_out`) and
    whether the story tracks its cast. Without it, every resume rebuilt prompts from the action's
    last sentence, which the prompt already holds, so "By the end of the clip" vanished from every
    resumed shot (Hegdahl run, 2026-10-29) and a cast-free shot lost "none of the named characters".
    """
    beats = (script or {}).get("beats") if isinstance((script or {}).get("beats"), list) else []
    planned = script is not None and 0 <= shot.index < len(beats)
    handoff = (beat_handoff(script, shot.index) if planned else "") or payoff_of(shot.subject_action)
    tracks_cast = _names_cast(script) if script is not None else bool(shot.cast)
    return construct_prompt(
        subject_action=description,
        camera_action=camera,
        ambience=shot.ambience,
        continuity=shot.continuity or {},
        framing=framing_for(shot.subject_action, camera),
        backend="wan" if WAN_SUFFIX in shot.prompt else "minimax",
        cast_names=list(shot.cast) if tracks_cast else None,
        light=shot.light,
        handoff=handoff,
    )


def _retake_prompt(shot, correction: str, has_reference: bool, script: dict | None = None) -> str:
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
    return _rebuilt_prompt(shot, description, shot.camera_action, script)


def _repair_prompt(shot, script: dict | None = None) -> str:
    """The last take for a shot every normal take failed: hold on its end state, with no move.

    On the 2026-10-27 volcano run MiniMax ignored every reveal it was given: a pan to "another"
    lava flow kept the first flow and drifted to a green hill, and a close-up of a wave on rock
    pulled back to a wide aerial on all six takes. A locked-off view of the payoff is the one
    thing it renders reliably, and the narration still carries the beat.
    """
    held = (f"{payoff_of(shot.subject_action)} The framing, distance and angle stay exactly the same "
            "in every frame; the only motion is natural motion inside the scene, such as water, "
            "grass, cloth or drifting cloud, in crisp clear light.")
    return _rebuilt_prompt(shot, held, "locked-off static camera", script)


EARLY_RESTAGE_AFTER = 2


def _fatal_takes(shot) -> int:
    """Takes of the current staging the reviewer rejected, for any reason, or that went soft. Lighthouse shot-009
    (faint embers) went soft twice and windmill shot-009 (a miller shouldering a tailpole) was marked down four
    times for the same miss: a third take of a staging rejected twice rarely passes. Earlier clean takes stay
    available to the fallback after a restage, so nothing is lost by restaging."""
    return sum(1 for attempt in shot.attempts if not attempt.get("superseded")
               and (((attempt.get("validation") or {}).get("semantic_review") or {}).get("valid") is False
                    or "goes soft" in str(attempt.get("error") or "")))


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
        # Fast mode (see fast.py): a wall-clock deadline for the whole pipeline, set per run.
        self._fast = False
        # Planned stills (LOCAL_VIDEO_PLANNED_STILLS=1) is the only mode that trades quality for the deadline:
        # fewer takes, flawed keyframes kept, stills for rejected clips. The default never does.
        self._rushed = False
        self._deadline: float | None = None

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
        if manifest.shots[index].id in manifest.settings.get("open_fresh", []):
            return None              # the shot doctor found the inherited frame cannot become this shot
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

    def _recheck_first_take(self, manifest: ProjectManifest, index: int) -> None:
        """Pre-flight a shot again on the frame it will really open on, now that its source is accepted.

        The run-start pre-flight sees no frame for a continuation whose source is not accepted yet:
        Hegdahl shot-022 opened blind on shot-021's one-official close-up for a beat with three officials
        and a stack of pages, and was rejected for exactly that. Free when the plan is unchanged.
        """
        shot = manifest.shots[index]
        planned = (shot.prompt, self._reference_for(manifest, index))
        try:
            self._doctor_shots(manifest, {index + 1})
        except Exception as exc:
            log.warning("Shot doctor recheck for %s skipped: %s", shot.id, exc)
        if (shot.prompt, self._reference_for(manifest, index)) != planned:
            self._cancel_speculation(manifest, "the shot doctor replanned it from its real first frame")

    def _generate_shot(self, manifest: ProjectManifest, index: int) -> bool:
        shot = manifest.shots[index]
        for prior in shot.attempts:
            if prior.get("status") in {"generating", "validating"}:
                prior.update(status="failed", error="generation process ended before the attempt completed",
                             ended_at=time.time())
        if not shot.attempts and not self._rushed:
            self._recheck_first_take(manifest, index)
        sequence = self._backend_sequence(manifest)
        primary_failures = 0
        total_attempts = self.config.retry_limit + 1
        infrastructure_retry_limit = 2
        # One extra take with the move stripped out, spent only once every normal take was rejected.
        repair_used = not self.config.repair_take or self._rushed
        repairing = False
        if self._rushed:
            total_attempts = min(total_attempts, 2)
        maximum_attempts = total_attempts + infrastructure_retry_limit + (0 if repair_used else 1)
        creative_failures = 0
        infrastructure_failures = 0
        last_error = "No backend was attempted"
        revision_notes: list[tuple[float, str]] = []
        restarted_server = False
        for prior in shot.attempts:
            if prior.get("superseded"):
                continue
            review = (prior.get("validation") or {}).get("semantic_review") or {}
            correction = str(review.get("revision_prompt") or "").strip()
            if not correction and not review.get("valid", True):
                correction = shot.subject_action
            if correction and not review.get("valid", True):
                revision_notes.append((float(review.get("average_score") or 0), correction[:1200]))
        for attempt_index in range(maximum_attempts):
            if self._rushed and attempt_index and not self._can_retake(manifest, index):
                log.info("Local AI %s: no time for a retake before the deadline; salvaging", shot.id)
                manifest.record("retake_skipped_deadline", shot=shot.id)
                break
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
            if not available and backend_name == "minimax" and not restarted_server:
                # ComfyUI aborted inside FLUX ("Fatal Python error: Aborted") and the last two stray-dog shots
                # became animated stills seconds later: a dead server is restarted before any fallback.
                restarted_server = True
                log.warning("Local AI %s: MiniMax is unavailable (%s); restarting FreeVideo", shot.id, reason)
                self._restart_minimax(manifest)
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
                if (reference is None and backend_name == "minimax" and not self._rushed
                        and isinstance(self.backends.get("minimax"), MiniMaxAdapter)
                        and index in fresh_openings(manifest)):
                    # The last take retired this shot's keyframe. Without a first frame MiniMax frames the
                    # shot itself: shot-004's five text-only takes came back as stacked panels and a
                    # letterboxed strip. Draw a new first frame instead.
                    self._cancel_speculation(manifest, "a first frame is being redrawn")
                    try:
                        prepare_keyframes(manifest, self.config, {index + 1},
                                          view=(lambda s: fast.frame_view(manifest, s)) if self._fast else None)
                    except Exception as exc:
                        log.warning("Keyframe redraw for %s failed: %s", shot.id, exc)
                    reference = self._reference_for(manifest, index)
                if reference is not None and reference.parent.name == "keyframes":
                    attempt["keyframe"] = keyframe_id(reference)
                candidate_shot = _prompt_for_backend(shot, backend_name)
                if repairing:
                    attempt["repair"] = True
                    repair = _repair_prompt(candidate_shot, manifest.script)
                    worn = " ".join(f"{name} wears exactly: {outfit}."
                                    for name, outfit in wardrobe_for(manifest, shot).items() if outfit)
                    if worn:   # the last-resort take drew Hegdahl in denim without it (shot-014)
                        repair = _rebuilt_prompt(candidate_shot, f"{payoff_of(candidate_shot.subject_action)} {worn} "
                                                 "The framing, distance and angle stay exactly the same in every "
                                                 "frame.", "locked-off static camera", manifest.script)
                    candidate_shot = replace(candidate_shot, prompt=repair)
                    manifest.settings.get("shot_doctor_take", {}).pop(shot.id, None)   # not a doctored plan
                elif revision_notes:
                    best_correction = max(revision_notes, key=lambda item: item[0])[1]
                    prompt = self._retake(manifest, index, candidate_shot, best_correction, reference)
                    redrawn = self._reference_for(manifest, index)
                    if redrawn != reference:          # the retake opened the shot fresh on a new first frame
                        reference = redrawn
                        attempt.pop("keyframe", None)
                        if reference is not None and reference.parent.name == "keyframes":
                            attempt["keyframe"] = keyframe_id(reference)
                    candidate_shot = replace(candidate_shot, prompt=prompt)
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
                if visual_report.get("skipped") and any(name in str(visual_report.get("reason") or "")
                                                        for name in _REVIEWER_OUT):
                    attempt.update(status="interrupted", ended_at=time.time(),
                                   error=str(visual_report.get("reason")))
                    shot.status = "pending"
                    manifest.error = f"{visual_report.get('reason')}; resume the project once the reviewer is back"
                    manifest.record("reviewer_unavailable", shot=shot.id, reason=str(visual_report.get("reason")))
                    manifest.save()
                    raise ReviewerUnavailable(manifest.error)
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
            except ReviewerUnavailable:
                raise
            except Exception as exc:
                # The next shot was rendering from this take's last frame; that frame is now wrong. A next
                # shot opening on its own keyframe (fast mode) keeps rendering.
                job = self._speculation
                if not job or self._reference_source(manifest, job["index"]) == index:
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
                # Two fatal rejections of one staging: a third take of it rarely passes (lighthouse shot-003 drew
                # two fires, then a blaze, then two fires again for "exactly one tiny pinpoint"). Restage now.
                restage_now = ((isinstance(exc, VisualReviewRejected) or "goes soft" in str(exc)) and self._fast and not self._rushed
                               and _fatal_takes(shot) >= EARLY_RESTAGE_AFTER
                               and not fast.designed(manifest, shot).get("restaged_after_failure"))
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
                if restage_now:
                    log.info("Local AI %s: %d rejected takes of this staging; restaging instead of retaking",
                             shot.id, _fatal_takes(shot))
                    if self._restage_failed_shot(manifest, index, early=True):
                        return self._generate_shot(manifest, index)
                    # No new staging came back: the remaining takes of the old one are still better than a still.
        if self._restage_failed_shot(manifest, index):
            return self._generate_shot(manifest, index)
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
        if self._fast:            # stills are already rendered: the next shot the GPU will need
            following = next((shot.index for shot in self._pending_motion(manifest, index + 1)
                              if not shot.attempts), len(manifest.shots))
        if (not self.config.speculative_next_shot or following >= len(manifest.shots) or self._speculation
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
        if self._rushed:
            # A weak take reads as a weird scene; the shot's own reviewed keyframe as a still does not.
            floor = int(os.getenv("LOCAL_VIDEO_VISION_MIN_SCORE") or 7) - 1
            clean = [take for take in clean if take[0] >= floor]
        if clean and self._restore_take(manifest, shot, clean[0][2], "shot_accepted_best_take"):
            return True
        if self._rushed and fast.hires_keyframe(manifest, shot) is not None and self._finish_still(
                manifest, shot, planned=False, reason=last_error[:300]):
            log.warning("Local AI %s: no take passed review; its approved keyframe plays as a still", shot.id)
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
        """The project's narration (assembly.ensure_narration), retimed to the planned length when first voiced."""
        fresh = not (Path(manifest.project_dir) / "audio" / "narration.mp3").is_file()
        narration = ensure_narration(manifest)
        if narration and fresh:
            self._fit_narration_length(manifest, narration, get_duration(str(narration)))
            manifest.save()
        return narration

    def _fit_narration_length(self, manifest: ProjectManifest, narration: Path, duration: float) -> float:
        """Retime the voice so the video lands on its planned length (61-65 s for the default 65).

        The timeline follows the voice plus about 1.5 s, and voices differ in pace: the slow Edge voice
        turned a 65 s plan into an 82 s video. atempo keeps the pitch; the change is capped so a voice
        never sounds rushed or dragged.
        """
        planned = float(manifest.duration_seconds)
        if (os.getenv("LOCAL_VIDEO_FIT_NARRATION", "1") == "0" or not duration
                or planned - 5.5 <= duration <= planned - 1.5):
            return duration
        factor = min(1.25, max(0.85, duration / (planned - 2.5)))
        retimed = narration.with_name("narration-retimed.mp3")
        result = subprocess.run([self.config.ffmpeg, "-v", "error", "-y", "-i", str(narration), "-filter:a",
                                 f"atempo={factor:.4f}", "-c:a", "libmp3lame", "-b:a", "160k", str(retimed)],
                                capture_output=True, text=True)
        if result.returncode != 0 or not retimed.is_file():
            log.warning("Narration retiming failed (%s); keeping %.1f s", result.stderr[-200:], duration)
            return duration
        retimed.replace(narration)
        fitted = get_duration(str(narration))
        log.info("Narration retimed x%.3f: %.1f s -> %.1f s (planned video %d s)", factor, duration, fitted, planned)
        manifest.record("narration_retimed", factor=round(factor, 4), before=round(duration, 2), after=round(fitted, 2))
        return fitted

    def _retake(self, manifest: ProjectManifest, index: int, shot, correction: str, reference: Path | None) -> str:
        """The next take's prompt, planned by the shot doctor against the failure it must not repeat.

        Retakes used the reviewer's correction alone: no wardrobe lock and none of the doctor's checks,
        so Hegdahl shot-010 failed four times on clones, rows instead of a semicircle and changed
        clothes. The doctor now sees the rejected take's problems, the real start frame and the
        wardrobe; without it, the reviewer's correction still gets the wardrobe lock.
        """
        from . import shot_doctor
        outfits = wardrobe_for(manifest, manifest.shots[index])
        reviewed = [a for a in manifest.shots[index].attempts if (a.get("validation") or {}).get("semantic_review")]
        review = reviewed[-1]["validation"]["semantic_review"] if reviewed else {}
        failure = "; ".join([*(review.get("fatal_problems") or []), *(review.get("problems") or [])])[:1500]
        if shot_doctor.enabled() and self.visual_reviewer is review_clip:
            beats = manifest.script.get("beats") if isinstance(manifest.script.get("beats"), list) else []
            end = beat_handoff(manifest.script, shot.index) if 0 <= shot.index < len(beats) else ""
            result = shot_doctor.examine(shot, end, reference, outfits,
                                         failed=f"{failure}\nThe reviewer's suggested fix: {correction}")
            if (result and reference is not None and not result.get("start_frame_fits", True)
                    and self._reference_source(manifest, index) is not None
                    and shot.id not in manifest.settings.get("open_fresh", [])):
                # Hegdahl shot-014 (pacing alone) inherited a frame holding him AND another prisoner and was
                # rejected for it: draw its own first frame now. The early render of the next shot is cancelled
                # and ComfyUI's models freed first, so FLUX has the GPU.
                manifest.settings.setdefault("open_fresh", []).append(shot.id)
                manifest.record("shots_open_fresh", shots=[shot.id])
                log.info("Shot doctor %s: the inherited first frame cannot become this shot; drawing its own",
                         shot.id)
                if isinstance(self.backends.get("minimax"), MiniMaxAdapter):
                    self._cancel_speculation(manifest, "a first frame is being redrawn")
                    try:
                        prepare_keyframes(manifest, self.config, {index + 1})
                    except Exception as exc:
                        log.warning("Keyframe redraw for %s failed: %s", shot.id, exc)
                fresh = self._reference_for(manifest, index)
                if fresh is not None:
                    result = shot_doctor.examine(shot, end, fresh, outfits,
                                                 failed=f"{failure}\nThe reviewer's suggested fix: {correction}") or result
            if result:
                # The reviewer judges this take's staging against the plan it was rendered from.
                manifest.settings.setdefault("shot_doctor_take", {})[shot.id] = result["description"]
                log.info("Shot doctor retake %s: %s; %s", shot.id, result["camera"], "; ".join(result["risks"])[:200])
                return _rebuilt_prompt(shot, result["description"], result["camera"], manifest.script)
        worn = " ".join(f"{name} wears exactly: {outfit}." for name, outfit in outfits.items() if outfit)
        return _retake_prompt(shot, f"{correction} {worn}".strip(), reference is not None, manifest.script)

    def _doctor_shots(self, manifest: ProjectManifest, shots: set[int] | None = None) -> None:
        """Pre-flight every shot that has not been reviewed yet (see shot_doctor) and apply the result.

        Cached per shot against its beat, end state and keyframe, so a resume re-applies it for free
        after _upgrade_prompts rebuilt the prompts, and only new or changed shots cost a call. Shots
        already reviewed keep their reviewer-led retakes.
        """
        from . import shot_doctor
        # Only alongside the real reviewer: a run with a stub reviewer (tests, QC off) has no vision model.
        if not shot_doctor.enabled() or self.visual_reviewer is not review_clip:
            return
        cache: dict[str, Any] = manifest.settings.setdefault("shot_doctor", {})
        beats = manifest.script.get("beats") if isinstance(manifest.script.get("beats"), list) else []
        ready, jobs = [], []
        for index, shot in enumerate(manifest.shots):
            if (shots is not None and index + 1 not in shots) or shot.status == "accepted":
                continue
            if any((a.get("validation") or {}).get("semantic_review") for a in shot.attempts):
                continue
            end = beat_handoff(manifest.script, shot.index) if 0 <= shot.index < len(beats) else ""
            # The frame the take will really open on: a continuation opens on its source's last frame,
            # not on a keyframe (Hegdahl shot-010 was doctored blind while shot-009's last frame was on
            # disk). Unknown until that source is accepted; the fingerprint then changes and it re-checks.
            source = self._reference_source(manifest, index)
            if source is not None and not manifest.shots[source].last_frame:
                keyframe = None
            else:
                keyframe = self._reference_for(manifest, index)
            outfits = wardrobe_for(manifest, shot)
            key = shot_doctor.fingerprint(shot, end, keyframe, outfits)
            if (cache.get(shot.id) or {}).get("for") == key:
                ready.append(shot)
            else:
                jobs.append((shot, end, keyframe, outfits, key))
        unfit: list[int] = []
        redraw: list[int] = []
        if jobs:
            log.info("Shot doctor: checking %d shot(s) before their first take", len(jobs))
            results = shot_doctor.examine_all([job[:4] for job in jobs])
            for (shot, _, start, _, key), result in zip(jobs, results):
                if not result:
                    continue
                # Only a frame the doctor actually saw can be judged unfit; without one it guesses.
                if (start is not None and not result.get("start_frame_fits", True)
                        and self._reference_source(manifest, shot.index) is not None
                        and isinstance(self.backends.get("minimax"), MiniMaxAdapter)):
                    # The inherited frame cannot become this shot (Hegdahl shot-010: a face close-up for a
                    # medium shot of a semicircle, rejected six times): open fresh on its own keyframe.
                    unfit.append(shot.index)
                    log.info("Shot doctor %s: the inherited first frame cannot become this shot; it opens fresh",
                             shot.id)
                    continue
                redrawn = manifest.settings.setdefault("keyframe_redrawn_by_doctor", [])
                if (start is not None and not result.get("start_frame_fits", True)
                        and start.parent.name == "keyframes" and shot.id not in redrawn
                        and isinstance(self.backends.get("minimax"), MiniMaxAdapter)):
                    # The shot's own keyframe shows the wrong subject (windmill shot-013: six sails and a statue
                    # on the cap for a four-sailed tower mill; every take opened on it and failed). Redraw it once
                    # before the first take instead of spending two takes to retire it.
                    redrawn.append(shot.id)
                    redraw.append(shot.index)
                    log.info("Shot doctor %s: its keyframe does not show this shot; redrawing it before take 1",
                             shot.id)
                    continue
                cache[shot.id] = dict(result, **{"for": key})
                ready.append(shot)
                log.info("Shot doctor %s: %s; %s", shot.id, result["camera"],
                         "; ".join(result["risks"])[:240] or "no risks")
        if unfit:
            manifest.settings.setdefault("open_fresh", []).extend(manifest.shots[i].id for i in unfit)
            manifest.record("shots_open_fresh", shots=[manifest.shots[i].id for i in unfit])
            # FLUX needs the card: an early render of the next shot must not be running.
            self._cancel_speculation(manifest, "a first frame is being drawn")
            prepare_keyframes(manifest, self.config, {i + 1 for i in unfit})
            self._doctor_shots(manifest, {i + 1 for i in unfit})
        if redraw:
            manifest.record("keyframes_redrawn_by_doctor", shots=[manifest.shots[i].id for i in redraw])
            self._cancel_speculation(manifest, "a first frame is being redrawn")
            retired = Path(manifest.project_dir) / "superseded" / "keyframes-retired"
            retired.mkdir(parents=True, exist_ok=True)
            for i in redraw:
                for name in (f"{manifest.shots[i].id}.png", f"{manifest.shots[i].id}.hires.png"):
                    path = Path(manifest.project_dir) / "keyframes" / name
                    if path.is_file():
                        path.replace(retired / f"{int(time.time())}-{name}")
            try:
                prepare_keyframes(manifest, self.config, {i + 1 for i in redraw},
                                  view=(lambda s: fast.frame_view(manifest, s)) if self._fast else None,
                                  all_shots=True)
            except Exception as exc:          # the doctor still plans the take; the retake path redraws later
                log.warning("Keyframe redraw before take 1 failed: %s", exc)
            self._doctor_shots(manifest, {i + 1 for i in redraw})
        for shot in ready:
            result = cache[shot.id]
            shot.camera_action = result["camera"]
            shot.prompt = _rebuilt_prompt(shot, result["description"], result["camera"], manifest.script)
            manifest.settings.setdefault("shot_doctor_take", {})[shot.id] = result["description"]
        if ready:
            manifest.record("shots_doctored", shots=[shot.id for shot in ready])
        manifest.save()

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
            prompt = _rebuilt_prompt(shot, shot.subject_action, shot.camera_action, manifest.script)
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
            cleared = clear_orphaned_jobs(self.config)
            if cleared:
                manifest.record("comfy_orphans_cleared", detail=cleared)
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
        # Answering HTTP is not working: after a CUDA out-of-memory error ComfyUI still answers but runs its
        # dead job forever, and after a native abort it does not answer at all. recover_server handles both.
        detail = recover_server(self.config)
        available = not detail.startswith("restart failed")
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

    def _requeue_boxed_clips(self, manifest: ProjectManifest, shots: set[int] | None) -> None:
        """Queue again any accepted clip that plays letterboxed, accepted before validation measured bars."""
        requeued = []
        for shot in manifest.shots:
            if shot.status != "accepted" or not shot.output or (shots is not None and shot.index + 1 not in shots):
                continue
            clip = resolve_within(manifest.project_dir, shot.output)
            problem = bar_problem(bar_metrics(clip)) if clip.is_file() else ""
            if problem:
                log.warning("Local AI %s: accepted clip is %s; generating it again", shot.id, problem)
                requeue_shot(manifest, shot)
                requeued.append(shot.id)
        if requeued:
            manifest.record("boxed_clips_requeued", shots=requeued)
            manifest.save()

    # ------------------------------------------------------------------------------------------------
    # Fast mode: the whole video inside the pipeline's wall-clock budget (see fast.py)

    def _seconds_left(self) -> float:
        return (self._deadline or time.time() + 3600) - time.time() - fast.RESERVE_SECONDS

    def _pending_motion(self, manifest: ProjectManifest, start: int = 0) -> list:
        return [shot for shot in manifest.shots[start:]
                if shot.status != "accepted" and fast.is_motion(manifest, shot)
                and (self._selected is None or shot.index + 1 in self._selected)]

    def _prepare_fast(self, manifest: ProjectManifest, shots: set[int] | None) -> None:
        """Plan which shots move, draw every shot's keyframe in parallel, and finish the stills on the way."""
        with MANIFEST_LOCK:
            # Every shot opens on its own reviewed keyframe: hard cuts, so no shot waits for another's clip.
            opened = manifest.settings.setdefault("open_fresh", [])
            opened.extend(shot.id for shot in manifest.shots if shot.id not in opened)
            # Screen direction only matters across a continuous take; across cuts the lock just failed
            # good frames (Zanzibar shot-016: a warship's bow pointing left, three takes).
            for shot in manifest.shots:
                if shot.status != "accepted" and (shot.continuity or {}).get("screen_geography"):
                    shot.continuity = {**shot.continuity, "screen_geography": ""}
        pending = [shot for shot in manifest.shots
                   if shot.status != "accepted" and (shots is None or shot.index + 1 in shots)]
        if not pending:
            return
        cost = fast.clip_cost(manifest)
        left = self._seconds_left() - fast.keyframe_stage_seconds(len(pending)) - 60
        count = fast.motion_budget(len(pending), left, cost) if fast.planned_stills() else len(pending)
        fast.design_shots(manifest, count)
        self._direct_clips(manifest, pending)
        motion = [shot.id for shot in manifest.shots if fast.is_motion(manifest, shot)]
        log.info("Fast plan: %d of %d shots as MiniMax clips (%s); %.0f min left of "
                 "the budget, ~%.0f s per clip", len(motion), len(manifest.shots), ", ".join(motion) or "none",
                 max(0.0, self._seconds_left()) / 60, cost)
        started = time.monotonic()
        made = prepare_keyframes(
            manifest, self.config, shots, workers=int(os.getenv("KEYFRAME_WORKERS") or 4),
            view=lambda shot: fast.frame_view(manifest, shot), on_ready=self._after_keyframe(manifest),
            all_shots=True, keep_flawed=self._rushed)
        log.info("Fast plan: %d keyframe(s) drawn in %.0fs", made, time.monotonic() - started)

    def _restage_failed_shot(self, manifest: ProjectManifest, index: int, early: bool = False) -> bool:
        """Every take failed with no clean one to keep: restage the shot once and give it fresh takes.

        `early`: two takes of this staging were rejected; restage now even if one was clean, which stays
        available to the fallback if the new staging fails too.

        Only in fast mode without planned stills (the quality-first default); the fallbacks after this are a
        still picture or a flawed take, which the user never wants (Ghost Army shot-018, 2026-10-31).
        """
        if not self._fast or self._rushed:
            return False
        shot = manifest.shots[index]
        design = fast.designed(manifest, shot)
        if design.get("restaged_after_failure") or not fast.is_motion(manifest, shot):
            return False
        reviews = [(a.get("validation") or {}).get("semantic_review") or {} for a in shot.attempts]
        if not early and any(review and not review.get("fatal_problems") and not review.get("skipped")
                             for review in reviews):
            return False                     # a clean take exists: keep the best of those instead
        failures = [str(item) for review in reviews
                    for item in (review.get("fatal_problems") or review.get("problems") or [])][-6:]
        try:
            staging = fast.restage(manifest, shot, failures or [shot.error or "rejected"])
        except Exception as exc:             # the fallbacks still finish the video
            log.warning("Restaging %s unavailable (%s)", shot.id, exc.__class__.__name__)
            staging = None
        with MANIFEST_LOCK:
            design = manifest.settings.setdefault("fast_design", {}).setdefault(shot.id, {"render": "motion"})
            design["restaged_after_failure"] = True
            if not staging:
                manifest.save()
                return False
            shot.subject_action = design.get("planned_action") or shot.subject_action
            design.update(staging, directed=False, subjects=[], source="designer")
            manifest.record("shot_restaged_after_failure", shot=shot.id, frame=staging["frame"][:300])
        log.warning("Local AI %s: every take failed; restaged as: %s", shot.id, staging["frame"][:200])
        for attempt in shot.attempts:        # their corrections describe the old staging
            attempt["superseded"] = True
        self._direct_clips(manifest, [shot], force=True)
        for name in (f"{shot.id}.png", f"{shot.id}.hires.png"):
            (Path(manifest.project_dir) / "keyframes" / name).unlink(missing_ok=True)
        try:
            prepare_keyframes(manifest, self.config, {index + 1}, view=lambda s: fast.frame_view(manifest, s),
                              all_shots=True)
        except Exception as exc:             # a clip from text is still better than a still
            log.warning("Keyframe redraw for restaged %s failed: %s", shot.id, exc)
        shot.status, shot.error = "pending", None
        manifest.save()
        return True

    def _direct_clips(self, manifest: ProjectManifest, pending: list, force: bool = False) -> None:
        """Each motion shot's clip is generated from, and judged against, the designer's drawable staging.

        The molasses hook asked for "a wave taller than a doorway surging straight toward the camera": FLUX
        drew a dry street three times, and four text-only MiniMax takes made a low flood the reviewer then
        rejected for not towering. The designer restages such beats at a filmable scale; the clip now asks
        for that same staging instead of the plan's original wish.
        """
        directed = []
        with MANIFEST_LOCK:
            for shot in pending:
                design = fast.designed(manifest, shot)
                if (not fast.is_motion(manifest, shot) or design.get("directed") or (shot.attempts and not force)
                        or not design.get("frame") or not design.get("motion")):
                    continue
                design["planned_action"] = shot.subject_action
                shot.subject_action = f"{design['frame'].rstrip('. ')}. {design['motion']}"
                view = shot
                if design.get("source") == "designer":
                    # Only the subjects this staging shows whole: the calm tank shot also carried the moving
                    # molasses, and MiniMax flooded the yard.
                    shown = set(design.get("subjects") or [])
                    objects = str((shot.continuity or {}).get("recurring_objects") or "")
                    kept = [item for item in objects.split("; ") if ":" in item
                            and item.partition(":")[0].split("(")[0].strip() in shown]
                    view = replace(shot, continuity={**(shot.continuity or {}), "recurring_objects": "; ".join(kept)})
                shot.prompt = _rebuilt_prompt(view, shot.subject_action, shot.camera_action, None)
                design["directed"] = True
                directed.append(shot.id)
        if directed:
            manifest.record("clips_directed", shots=directed)
            manifest.save()
            log.info("Fast plan: %d clip(s) follow the designed staging", len(directed))

    def _after_keyframe(self, manifest: ProjectManifest):
        """Runs on the keyframe worker once a shot's frame is accepted: a still is finished there and then,
        and a clip's first-take plan is checked by the shot doctor while FLUX keeps drawing."""
        def ready(index: int, keyframe: Path) -> None:
            shot = manifest.shots[index]
            if shot.status == "accepted":
                return
            if not fast.is_motion(manifest, shot):
                self._finish_still(manifest, shot, planned=True)
                return
            from . import shot_doctor
            if not shot_doctor.enabled() or self.visual_reviewer is not review_clip:
                return
            beats = manifest.script.get("beats") if isinstance(manifest.script.get("beats"), list) else []
            end = beat_handoff(manifest.script, shot.index) if 0 <= shot.index < len(beats) else ""
            reference = self._reference_for(manifest, index)
            with MANIFEST_LOCK:
                outfits = wardrobe_for(manifest, shot)
            key = shot_doctor.fingerprint(shot, end, reference, outfits)
            cache = manifest.settings.setdefault("shot_doctor", {})
            if (cache.get(shot.id) or {}).get("for") == key:
                return
            result = shot_doctor.examine(shot, end, reference, outfits)
            if result:
                with MANIFEST_LOCK:
                    cache[shot.id] = dict(result, **{"for": key})
                log.info("Shot doctor %s: %s; %s", shot.id, result["camera"],
                         "; ".join(result["risks"])[:240] or "no risks")
        return ready

    def _finish_still(self, manifest: ProjectManifest, shot, *, planned: bool, reason: str = "") -> bool:
        """The shot as a parallax camera move over its own approved keyframe."""
        try:
            path = fast.render_still(manifest, shot, self.config)
            if path is None:
                return False
            fast.accept_still(manifest, shot, path, self.config, planned=planned, reason=reason)
        except Exception as exc:
            log.warning("Still for %s failed: %s", shot.id, exc)
            manifest.record("still_failed", shot=shot.id, error=str(exc)[:300])
            return False
        manifest.save()
        self._emit(manifest, "still")
        return True

    def _borrowed_still(self, manifest: ProjectManifest, shot) -> bool:
        """A shot whose every keyframe take failed, as a different camera move over its nearest neighbour's
        frame: the Potsdam run redrew shot-011 mid-clip-phase on the shared GPU and then spent a whole clip on
        it from text, four minutes past its plan."""
        moves = {"push_in": "pull_out", "pull_out": "push_in", "pan_left": "pan_right", "pan_right": "pan_left",
                 "rise": "push_in"}
        for other in sorted(manifest.shots, key=lambda s: (abs(s.index - shot.index), s.index)):
            source = fast.hires_keyframe(manifest, other) if other.id != shot.id else None
            if source is None:
                continue
            move = moves.get(fast.designed(manifest, other).get("still_move") or "push_in", "pull_out")
            try:
                path = fast.render_still(manifest, shot, self.config, source=source, move=move)
                if path is None:
                    return False
                fast.accept_still(manifest, shot, path, self.config, planned=False,
                                  reason=f"no keyframe of its own; {other.id}'s frame, {move}")
            except Exception as exc:
                log.warning("Borrowed still for %s failed: %s", shot.id, exc)
                return False
            log.warning("Local AI %s: no keyframe and no time for a clip; %s's frame plays with a %s",
                        shot.id, other.id, move)
            manifest.save()
            return True
        return False

    def _fit_motion_budget(self, manifest: ProjectManifest, index: int) -> None:
        """Turn the least motion-dependent pending clips into stills until the rest fit the deadline.

        Only with planned stills: otherwise every shot stays a clip and the deadline only limits retakes.
        """
        if not fast.planned_stills():
            return
        pending = self._pending_motion(manifest, index)
        cost = fast.clip_cost(manifest)
        while pending and self._seconds_left() < cost * len(pending):
            victim = min(pending, key=lambda shot: (fast.designed(manifest, shot).get("motion_need", 0), -shot.index))
            pending.remove(victim)
            if fast.hires_keyframe(manifest, victim) is None:
                continue                      # nothing to animate: it stays a clip
            if self._speculation and self._speculation["index"] == victim.index:
                self._cancel_speculation(manifest, f"{victim.id} became a still to meet the deadline")
            fast.demote(manifest, victim, f"{self._seconds_left() / 60:.1f} min left for {len(pending) + 1} clips "
                                          f"of ~{cost:.0f} s")
            self._finish_still(manifest, victim, planned=True, reason="deadline")

    def _room_for_one_more_clip(self, manifest: ProjectManifest, index: int) -> bool:
        """One clip beyond those still planned after `index` fits before the deadline."""
        later = len(self._pending_motion(manifest, index + 1))
        return self._seconds_left() >= fast.clip_cost(manifest) * (later + 1)

    def _can_retake(self, manifest: ProjectManifest, index: int) -> bool:
        """A retake only once no planned clip is still waiting, and only inside the deadline.

        Retakes passed about as often as first takes (2 of 4 on the 2026-10-31 pig run), so the time is
        better spent on another planned motion shot: retakes there made the deadline turn three of them
        into stills. A rejected shot falls back to its approved keyframe meanwhile.
        """
        return not self._pending_motion(manifest, index + 1) and self._room_for_one_more_clip(manifest, index)

    def run(self, project: str | Path | ProjectManifest, shots: set[int] | None = None) -> ProjectManifest:
        manifest = project if isinstance(project, ProjectManifest) else load_project(project, self.config)
        self._selected = shots
        self._fast = fast.enabled() and isinstance(self.backends.get("minimax"), MiniMaxAdapter)
        self._rushed = self._fast and fast.planned_stills()
        self._deadline = fast.pipeline_started() + fast.budget_seconds() if self._fast else None
        try:
            return self._run(manifest, shots)
        finally:
            # A pause, cancel or failure must not leave a render running on the GPU.
            self._cancel_speculation(manifest, "the run stopped")

    def _run(self, manifest: ProjectManifest, shots: set[int] | None) -> ProjectManifest:
        with FileLock(self.config.output_root / GPU_LOCK_NAME):
            self._silence_accepted_clips(manifest)
            self._requeue_boxed_clips(manifest, shots)
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
            if self._fast:
                try:
                    self._prepare_fast(manifest, shots)
                except Exception as exc:     # whatever was drawn stays; missing shots become clips
                    log.warning("Fast plan incomplete: %s", exc, exc_info=True)
            elif isinstance(self.backends.get("minimax"), MiniMaxAdapter):
                try:
                    prepare_keyframes(manifest, self.config, shots)
                except Exception as exc:     # keyframes only improve the look; never block the run
                    log.warning("Keyframes skipped: %s", exc)
            try:
                self._doctor_shots(manifest, shots)
            except Exception as exc:         # the pre-flight only improves first takes; never block the run
                log.warning("Shot doctor skipped: %s", exc)
            for index, shot in enumerate(manifest.shots):
                if shots is not None and index + 1 not in shots:
                    continue
                if shot.status == "accepted" and shot.output and resolve_within(manifest.project_dir, shot.output).is_file():
                    continue
                if self._fast:
                    if fast.is_motion(manifest, shot):
                        self._fit_motion_budget(manifest, index)
                    if not fast.is_motion(manifest, shot) and (
                            shot.status == "accepted" or self._finish_still(manifest, shot, planned=True)):
                        continue
                    if (not fast.is_motion(manifest, shot) and not self._room_for_one_more_clip(manifest, index - 1)
                            and self._borrowed_still(manifest, shot)):
                        continue             # no keyframe and no time for a clip from text
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
