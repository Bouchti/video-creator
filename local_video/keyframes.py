"""Photoreal first frames from FLUX.1-schnell for shots that open fresh.

Text-only video generation drifts into a soft, dreamy look; a sharp photographic still as the first
frame anchors MiniMax to real-world texture and light. Only fresh openings get one (the first shot
and hard cuts): continuing shots open on the previous clip's last frame, as before.

FLUX runs in FreeVideo's ComfyUI with core nodes only (an all-in-one fp8 checkpoint), before any
clip is generated, and is unloaded afterwards so MiniMax gets the GPU back. Any failure skips the
keyframes and the shot falls back to text-only generation.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

from .comfy import ComfyClient, ComfyError
from .config import PipelineConfig, env_int
from .models import ProjectManifest, Shot
from .planner import PHOTO_LOOK, continuation_source, framing_for, framing_scale, shot_objects

log = logging.getLogger("pipeline")

PEER_DRIVES = Path(r"C:\pinokio\drive\drives\peers")
# A keyframe that keeps failing review is dropped so the last takes can generate without it.
KEYFRAME_FAILURE_LIMIT = 2


def keyframes_enabled() -> bool:
    return env_int("LOCAL_VIDEO_KEYFRAMES", 1, 0, 1) == 1


def checkpoint_name() -> str:
    return os.getenv("KEYFRAME_CHECKPOINT", "flux1-schnell-fp8.safetensors")


def models_dir() -> Path | None:
    """Folder whose checkpoints/ holds the FLUX checkpoint (KEYFRAME_MODELS_DIR, else a Pinokio drive)."""
    configured = os.getenv("KEYFRAME_MODELS_DIR")
    if configured:
        return Path(configured).expanduser()
    if PEER_DRIVES.is_dir():
        for found in PEER_DRIVES.glob(f"*/checkpoints/{checkpoint_name()}"):
            return found.parent.parent
    return None


def has_checkpoint(url: str) -> bool:
    try:
        spec = requests.get(f"{url}/object_info/CheckpointLoaderSimple", timeout=30).json()
        choice = spec["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return False
    # Older ComfyUI lists the names first; newer sends ["COMBO", {"options": [...]}].
    names = choice[0] if isinstance(choice[0], list) else (choice[1] or {}).get("options", [])
    return checkpoint_name() in names


def keyframe_path(manifest: ProjectManifest, shot: Shot) -> Path:
    return Path(manifest.project_dir) / "keyframes" / f"{shot.id}.png"


def fresh_openings(manifest: ProjectManifest) -> list[int]:
    """Shots that open on no earlier frame: the first (without a user reference) and hard cuts."""
    labels = [(s.scene.lower(), s.light.lower()) for s in manifest.shots]
    casts = [s.cast for s in manifest.shots]
    scales = [framing_scale(s.subject_action) for s in manifest.shots]
    objects = [shot_objects(manifest.script, s.continuity) for s in manifest.shots]
    indices = []
    for index, shot in enumerate(manifest.shots):
        if index == 0:
            if not manifest.reference_image:
                indices.append(index)
        elif shot.scene and continuation_source(labels, index, casts, scales, objects) is None:
            indices.append(index)
    return indices


def usable_keyframe(manifest: ProjectManifest, shot: Shot) -> Path | None:
    path = keyframe_path(manifest, shot)
    if not path.is_file():
        return None
    failed = sum(1 for attempt in shot.attempts if attempt.get("status") == "failed" and attempt.get("keyframe"))
    return path if failed < KEYFRAME_FAILURE_LIMIT else None


def _clip_sentences(text: str, limit: int) -> str:
    """Whole sentences up to limit characters; a cut mid-word ("near the main cone, n.") reads as noise."""
    if len(text) <= limit:
        return text
    kept = ""
    for sentence in re.split(r"(?<=[.;])\s+", text):
        if len(kept) + len(sentence) + 1 > limit:
            break
        kept = f"{kept} {sentence}".strip()
    return kept or text[:limit].rsplit(" ", 1)[0]


def keyframe_prompt(shot: Shot) -> str:
    """The still the clip opens on, described the same way the clip itself is.

    This image becomes the clip's first frame AND the continuity reference the reviewer compares
    that frame against, so anything the clip brief says about look that is missing here turns into a
    rejection. It used to omit `visual_style`, which carries the palette and grade: a brief asking
    for an ash-grey sky and a charcoal-and-steel grade produced a pale-blue cone under a clear sky,
    and the reviewer then reported "frame 1 does not match the start image".

    Where the camera stands and the light lead the prompt, ahead of the subject: FLUX weighs the
    opening words most, and with them buried after the setting every volcano keyframe came out as a
    drone view under a pale sky, even for an "ash-darkened overcast" shot. MiniMax cannot move the
    camera down to the sea or darken the sky in three seconds, so every take of those shots failed.
    """
    continuity = shot.continuity or {}
    light = shot.light or continuity.get("time_of_day")
    parts = [f"Photograph, {framing_for(shot.subject_action, shot.camera_action)}"]
    if light:
        parts.append(f"Light and sky in every part of the frame: {light}")
    parts.append(f"Subject: {shot.subject_action}")
    if continuity.get("location"):
        parts.append(f"Setting: {_clip_sentences(str(continuity['location']), 400)}")
    style = continuity.get("visual_style")
    if style:                                  # the same palette and grade the clip is rendered with
        parts.append(f"Visual style: {str(style)[:400]}")
    if shot.cast and continuity.get("characters"):
        names = ", ".join(shot.cast)
        parts.append(f"Exactly one of each named person ({names}), never two look-alikes; everyone else "
                     f"dressed differently. Look: {str(continuity['characters'])[:500]}")
    parts.append("9:16 portrait composition, the subject filling a clear share of the frame")
    parts.append(f"{PHOTO_LOOK}, realistic skin and materials, no text, no watermark")
    return ". ".join(part.rstrip(". ") for part in parts) + "."


def workflow(prompt: str, seed: int, width: int, height: int) -> dict[str, Any]:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint_name()}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
        "4": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
            "seed": seed, "steps": env_int("KEYFRAME_STEPS", 4, 1, 50), "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "vc_keyframe"}},
    }


def _image_item(history: dict[str, Any]) -> dict[str, Any]:
    for node in (history.get("outputs") or {}).values():
        for item in node.get("images", []) if isinstance(node, dict) else []:
            if str(item.get("filename", "")).lower().endswith(".png"):
                return item
    raise ComfyError("ComfyUI completed but returned no keyframe image")


def _fit(source: Path, target: Path, config: PipelineConfig) -> None:
    """Crop the still to MiniMax's frame so the first frame is not stretched."""
    width, height = config.minimax_width, config.minimax_height
    subprocess.run(
        [config.ffmpeg, "-y", "-loglevel", "error", "-i", str(source), "-vf",
         f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height}",
         str(target)],
        check=True, capture_output=True, timeout=120,
    )


def prepare_keyframes(manifest: ProjectManifest, config: PipelineConfig, selected: set[int] | None = None) -> int:
    """Generate any missing keyframes for pending fresh openings; returns how many were made."""
    if not keyframes_enabled() or not config.minimax_url:
        return 0
    pending = [
        index for index in fresh_openings(manifest)
        if (selected is None or index + 1 in selected)
        and manifest.shots[index].status != "accepted"
        and not keyframe_path(manifest, manifest.shots[index]).is_file()
    ]
    if not pending:
        return 0
    if not has_checkpoint(config.minimax_url):
        log.warning("Keyframes skipped: %s is not visible to ComfyUI at %s (set KEYFRAME_MODELS_DIR "
                    "and restart FreeVideo)", checkpoint_name(), config.minimax_url)
        manifest.record("keyframes_skipped", reason="checkpoint not found")
        return 0
    from .upscale import stop_idle_freevideo_worker
    stop_idle_freevideo_worker()        # MiniMax's resident weights would leave FLUX no VRAM
    client = ComfyClient(config.minimax_url, timeout=900, poll_seconds=1.0)
    width = env_int("KEYFRAME_WIDTH", 720, 256, 2048) // 16 * 16
    height = env_int("KEYFRAME_HEIGHT", 1280, 256, 2048) // 16 * 16
    made = 0
    try:
        for index in pending:
            shot = manifest.shots[index]
            target = keyframe_path(manifest, shot)
            started = time.monotonic()
            try:
                prompt_id = client.submit(workflow(keyframe_prompt(shot), shot.seed, width, height))
                raw = client.download(_image_item(client.wait(prompt_id)), target.with_suffix(".raw.png"))
                _fit(raw, target, config)
                raw.unlink(missing_ok=True)
            except (ComfyError, TimeoutError, requests.RequestException, subprocess.SubprocessError, OSError) as exc:
                log.warning("Keyframe for %s failed (%s); the shot will generate from text", shot.id, exc)
                manifest.record("keyframe_failed", shot=shot.id, error=str(exc)[:500])
                continue
            made += 1
            log.info("Keyframe %s ready in %.0fs", shot.id, time.monotonic() - started)
            manifest.record("keyframe_generated", shot=shot.id, path=str(target.relative_to(manifest.project_dir)))
    finally:
        client.free_memory()
        manifest.save()
    return made
