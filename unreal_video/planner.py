"""Convert an approved full script into a safe, deterministic Unreal scene recipe."""

from __future__ import annotations

import hashlib
import re
from typing import Any

ARCHETYPES = {
    "water": ("water", "pool", "river", "ocean", "flood", "pipe", "dam", "septic", "well"),
    "bridge": ("bridge", "arch", "truss", "span"),
    "house": ("house", "home", "basement", "roof", "wall", "foundation", "building"),
    "tower": ("tower", "skyscraper", "mast", "wind turbine"),
    "transport": ("car", "truck", "boat", "ship", "plane", "train", "road", "vehicle"),
    "machine": ("engine", "reactor", "generator", "pump", "turbine", "machine", "motor"),
    "underground": ("underground", "soil", "tunnel", "mine", "buried", "groundwater"),
}

CAMERAS = {"orbit", "dolly_in", "dolly_out", "crane_up", "tracking", "static"}


def _archetype(text: str) -> str:
    value = text.lower()
    scores = {name: sum(word in value for word in words) for name, words in ARCHETYPES.items()}
    name, score = max(scores.items(), key=lambda row: row[1])
    return name if score else "workshop"


def _camera(value: str, index: int) -> str:
    cleaned = re.sub(r"[^a-z_]+", "_", value.lower()).strip("_")
    aliases = {"push_in": "dolly_in", "pull_out": "dolly_out", "pan": "tracking",
               "tilt": "crane_up", "zoom_in": "dolly_in", "zoom_out": "dolly_out"}
    cleaned = aliases.get(cleaned, cleaned)
    return cleaned if cleaned in CAMERAS else ("orbit" if index % 2 else "dolly_in")


def _seed(title: str, index: int) -> int:
    digest = hashlib.sha256(f"{title}:{index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _allocate_frames(duration: int, texts: list[str], fps: int) -> list[int]:
    total = int(duration * fps)
    weights = [max(1, len(re.findall(r"\b\w+\b", text))) for text in texts]
    raw = [total * weight / sum(weights) for weight in weights]
    frames = [max(1, int(value)) for value in raw]
    difference = total - sum(frames)
    order = sorted(range(len(frames)), key=lambda index: raw[index] - int(raw[index]), reverse=True)
    step = 1 if difference > 0 else -1
    for offset in range(abs(difference)):
        index = order[offset % len(order)]
        if step > 0 or frames[index] > 1:
            frames[index] += step
    if sum(frames) != total:
        frames[-1] += total - sum(frames)
    return frames


def build_recipe(script: dict[str, Any], duration: int, width: int = 1080,
                 height: int = 1920, fps: int = 30) -> dict[str, Any]:
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    if len(beats) < 2:
        raise ValueError("Unreal rendering requires at least two script beats")
    texts = [str(beat.get("text") or "").strip() for beat in beats]
    if any(not text for text in texts):
        raise ValueError("Every Unreal beat needs narration text")
    frames = _allocate_frames(duration, texts, fps)
    title = str(script.get("video_title") or "Untitled Unreal video")
    shots, cursor = [], 0
    for index, (beat, count) in enumerate(zip(beats, frames)):
        visual = beat.get("visual") if isinstance(beat.get("visual"), dict) else {}
        description = str(visual.get("description") or beat["text"]).strip()
        end = cursor + count
        shots.append({
            "id": f"shot_{index + 1:03d}",
            "index": index,
            "start_frame": cursor,
            "end_frame": end,
            "description": description,
            "narration_reference": str(beat["text"]).strip(),
            "archetype": _archetype(description + " " + title),
            "camera": _camera(str(visual.get("camera") or ""), index),
            "seed": _seed(title, index),
            "overlay": visual.get("overlay") if isinstance(visual.get("overlay"), dict) else None,
        })
        cursor = end
    recipe = {
        "schema_version": 1,
        "title": title,
        "world": {
            "style": str(script.get("visual_style") or "stylized cinematic engineering diorama"),
            "continuity": "one coherent physical world; recurring materials, scale and lighting",
            "palette": ["#18324A", "#E17B3F", "#E8D8B0", "#4D8B67", "#65B8D0"],
        },
        "render": {"width": width, "height": height, "fps": fps, "total_frames": cursor,
                   "audio": False, "captions": False, "transition_sounds": False},
        "shots": shots,
    }
    validate_recipe(recipe)
    return recipe


def validate_recipe(recipe: dict[str, Any]) -> None:
    render = recipe.get("render") or {}
    if (render.get("width"), render.get("height"), render.get("fps")) != (1080, 1920, 30):
        raise ValueError("Unreal recipe must be 1080x1920 at 30 fps")
    if any(render.get(name) is not False for name in ("audio", "captions", "transition_sounds")):
        raise ValueError("Unreal must render silent visuals without captions or transition sounds")
    shots = recipe.get("shots")
    if not isinstance(shots, list) or len(shots) < 2:
        raise ValueError("Unreal recipe needs at least two shots")
    cursor = 0
    for shot in shots:
        if shot.get("start_frame") != cursor or int(shot.get("end_frame", 0)) <= cursor:
            raise ValueError("Unreal shot frame ranges must be contiguous and non-empty")
        if shot.get("camera") not in CAMERAS:
            raise ValueError(f"Unsupported Unreal camera move: {shot.get('camera')}")
        if not str(shot.get("description") or "").strip():
            raise ValueError("Every Unreal shot requires a concrete visual description")
        cursor = int(shot["end_frame"])
    if cursor != int(render.get("total_frames", -1)):
        raise ValueError("Unreal recipe total_frames does not match its shots")
