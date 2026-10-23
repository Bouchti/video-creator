"""Script-to-shot planning and backend-aware prompt construction."""

from __future__ import annotations

import hashlib
import math
import random
import re
from typing import Any

from .models import Shot


QUALITY_BAN = (
    "Pure cinematic imagery only. The frame contains no captions, subtitles, title cards, "
    "typography, signs, logos, watermarks, user interfaces, or graphic overlays."
)
MINIMAX_SUFFIX = "cinematic physical motion, coherent anatomy and geometry, stable object identity, natural temporal consistency"
WAN_SUFFIX = "high quality cinematic video, stable motion, coherent subject, detailed lighting, temporal consistency"
CAMERA_MOVES = (
    "slow push-in", "gentle tracking shot", "controlled handheld follow", "smooth orbit",
    "low-angle dolly", "overhead drift", "slow pull-back", "lateral parallax move",
)
FRAMINGS = (
    "24mm wide establishing frame", "35mm medium-wide frame", "50mm medium frame",
    "85mm intimate close-up", "macro detail shot", "low-angle 35mm frame",
)


def validate_duration(seconds: int) -> int:
    if not 60 <= int(seconds) <= 90:
        raise ValueError("TikTok project duration must be between 60 and 90 seconds")
    return int(seconds)


def shot_count_for_duration(seconds: int) -> int:
    return max(20, min(30, round(validate_duration(seconds) / 3.0)))


def allocate_frames(total_seconds: int, shot_count: int, fps: int = 30) -> list[int]:
    if shot_count < 1:
        raise ValueError("shot_count must be positive")
    total = validate_duration(total_seconds) * fps
    base, remainder = divmod(total, shot_count)
    frames = [base + (1 if i < remainder else 0) for i in range(shot_count)]
    if any(not 75 <= value <= 120 for value in frames):
        raise ValueError("Shot plan must average 2.5 to 4 seconds per shot")
    return frames


def _split_text(text: str, count: int) -> list[str]:
    clauses = [value.strip() for value in re.split(r"(?<=[.!?;:])\s+|\n+", text) if value.strip()]
    if not clauses:
        clauses = [text.strip() or "The story develops visually."]
    if len(clauses) >= count:
        groups: list[str] = []
        for i in range(count):
            start = round(i * len(clauses) / count)
            end = round((i + 1) * len(clauses) / count)
            groups.append(" ".join(clauses[start:max(start + 1, end)]))
        return groups
    return [clauses[i % len(clauses)] for i in range(count)]


def _stage(index: int, count: int) -> str:
    ratio = index / max(1, count - 1)
    if index == 0:
        return "opening hook"
    if ratio < 0.48:
        return "development"
    if ratio < 0.72:
        return "escalation"
    if ratio < 0.88:
        return "climax"
    return "satisfying ending"


def _seed(project_key: str, index: int) -> int:
    digest = hashlib.sha256(f"{project_key}:{index}".encode()).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFF


def _continuity(script: dict[str, Any], visual_style: str, concept: str) -> dict[str, Any]:
    characters = script.get("characters") or []
    cast = "; ".join(f"{c.get('name')}: {c.get('look')}" for c in characters if isinstance(c, dict))
    palette = script.get("color_palette") or "consistent restrained cinematic palette"
    return {
        "characters": cast or (
            "one recurring protagonist with exactly the same face, body, clothing, equipment, "
            "and color scheme in every shot"
        ),
        "wardrobe": script.get("wardrobe") or "unchanged clothing and accessories between adjacent shots",
        "vehicles": script.get("vehicles") or "identical vehicle design and markings where present",
        "location": script.get("location") or (
            f"one continuous physical world for {concept}; preserve geography, architecture, scale, "
            "weather, and recurring props between adjacent shots"
        ),
        "palette": palette,
        "time_of_day": script.get("time_of_day") or "consistent time of day unless the story explicitly advances",
        "recurring_objects": "; ".join(str(item) for item in script.get("recurring_objects", []) if item),
        "visual_style": visual_style,
    }


def continuity_text(value: dict[str, Any]) -> str:
    return "; ".join(f"{key.replace('_', ' ')}: {item}" for key, item in value.items() if item)


def construct_prompt(
    *,
    subject_action: str,
    camera_action: str,
    ambience: str,
    continuity: dict[str, Any],
    framing: str,
    backend: str,
    stage: str,
    story_link: str,
    generation_context: str,
    shot_number: int,
    shot_count: int,
) -> str:
    suffix = MINIMAX_SUFFIX if backend == "minimax" else WAN_SUFFIX
    environment = continuity.get("location", "a coherent cinematic environment")
    style = continuity.get("visual_style", "cinematic realism")
    lighting = "motivated natural light with controlled highlights and readable shadow detail"
    atmosphere = "immersive, tactile atmosphere with purposeful depth and restrained color contrast"
    return (
        f"CURRENT RENDER TASK — SHOT {shot_number:02d} OF {shot_count:02d}. Render only this shot, "
        "not a montage and not the other screenplay events. "
        f"CURRENT SHOT (the only event to render): {subject_action}. "
        f"[{stage.upper()}] Lighting: {lighting}. Camera: {camera_action}; {framing}; 9:16 portrait composition. "
        f"Atmosphere: {atmosphere}. Visual style: {style}. {suffix}. {QUALITY_BAN}"
        f" Audio direction: {ambience}, environmental sound only. Dialogue: none. Narration: none. "
        "Voices and vocals: none. The production notes below are silent context; never speak, "
        "display, caption, subtitle, label, or spell any of their words. Do not restart the story, "
        "show an earlier location, or compress multiple scenes into this clip.\n\n"
        f"{generation_context}"
    )


def _physical_descriptions(beats: list[dict[str, Any]], concept: str) -> list[str]:
    """Return only filmable scene descriptions, replacing diagram/title-card instructions."""
    values: list[str | None] = []
    for beat in beats:
        visual = beat.get("visual") if isinstance(beat, dict) else None
        visual = visual if isinstance(visual, dict) else {}
        description = str(visual.get("description") or "").strip()
        kind = str(visual.get("kind") or "").lower()
        looks_graphic = any(token in description.lower() for token in (
            "card reading", "text reading", "title card", "stat card", "key phrase card",
            "timeline graphic", "diagram showing",
        ))
        values.append(None if kind == "diagram" or looks_graphic else description or None)
    if not values:
        return [f"A concrete physical action that advances the story of {concept}"]
    physical = [value for value in values if value]
    fallback = physical[0] if physical else f"A concrete physical action that advances the story of {concept}"
    result: list[str] = []
    for index, value in enumerate(values):
        if value:
            result.append(value)
            continue
        previous = next((values[i] for i in range(index - 1, -1, -1) if values[i]), None)
        following = next((values[i] for i in range(index + 1, len(values)) if values[i]), None)
        result.append(f"A direct visual continuation of {previous or following or fallback}")
    return result


def build_visual_screenplay(
    script: dict[str, Any],
    concept: str,
    continuity: dict[str, Any],
    descriptions: list[str],
) -> str:
    """Create the complete silent screenplay used as the project's source of truth."""
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    premise = script.get("story_premise") or script.get("description") or concept
    goal = script.get("protagonist_goal") or "The protagonist pursues the goal established by the premise."
    stakes = script.get("stakes") or "Failure prevents the protagonist from resolving the central problem."
    payoff = script.get("ending_payoff") or "The final physical action resolves the opening setup."
    lines = [
        "FULL VISUAL SCREENPLAY — SILENT CONTEXT ONLY",
        f"Title: {script.get('video_title') or concept}",
        f"Premise: {premise}",
        f"Protagonist goal: {goal}",
        f"Stakes: {stakes}",
        f"Ending payoff: {payoff}",
        f"Cast and world bible: {continuity_text(continuity)}",
        "Sequence outline:",
    ]
    count = max(len(descriptions), len(beats))
    for index in range(count):
        beat = beats[index] if index < len(beats) and isinstance(beats[index], dict) else {}
        narration = str(beat.get("text") or "").strip()
        visual = descriptions[min(index, len(descriptions) - 1)]
        visual_data = beat.get("visual") if isinstance(beat.get("visual"), dict) else {}
        continuity_in = str(visual_data.get("continuity_in") or "").strip()
        continuity_out = str(visual_data.get("continuity_out") or "").strip()
        line = f"{index + 1:02d}. VISUAL: {visual}"
        if continuity_in:
            line += f" | INHERIT: {continuity_in}"
        if continuity_out:
            line += f" | HANDOFF: {continuity_out}"
        if narration:
            line += f" | VOICEOVER REFERENCE (never speak or display): {narration}"
        lines.append(line)
    return "\n".join(lines)


def build_generation_context(
    script: dict[str, Any],
    concept: str,
    continuity: dict[str, Any],
    descriptions: list[str],
    index: int,
) -> str:
    """Build a compact local window so a short clip renders one beat, not the whole story."""
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []

    def beat_data(position: int) -> tuple[str, str, str, str]:
        beat = beats[position] if position < len(beats) and isinstance(beats[position], dict) else {}
        visual = beat.get("visual") if isinstance(beat.get("visual"), dict) else {}
        return (
            descriptions[min(position, len(descriptions) - 1)],
            str(visual.get("continuity_in") or "").strip(),
            str(visual.get("continuity_out") or "").strip(),
            str(beat.get("text") or "").strip(),
        )

    premise = script.get("story_premise") or script.get("description") or concept
    current, inherit, handoff, narration = beat_data(index)
    lines = [
        "STORY BIBLE (render only CURRENT SHOT)",
        f"Required starting state: {inherit or 'begin exactly where the previous shot ended'}",
        f"Required ending state: {handoff or 'finish with a clear visual handoff to the next action'}",
        f"Narration meaning to support silently: {narration or 'advance this exact story beat visually'}",
        f"Character identity lock: {continuity.get('characters')}",
        f"World lock: {continuity.get('location')}; palette: {continuity.get('palette')}",
        f"Recurring prop lock: {continuity.get('recurring_objects') or 'preserve every established prop exactly'}",
        f"Story intent: {premise} Goal: {script.get('protagonist_goal') or 'complete the central objective'}. "
        f"Stakes: {script.get('stakes') or 'failure prevents it'}. "
        f"Payoff: {script.get('ending_payoff') or 'resolve the opening setup'}",
    ]
    if index > 0:
        _, _, previous_handoff, _ = beat_data(index - 1)
        lines.append(
            "PREVIOUS SHOT (inherit, never replay): "
            + (previous_handoff or "continue its final pose, props, lighting, and geography")
        )
    if index + 1 < len(descriptions):
        _, following_in, _, _ = beat_data(index + 1)
        lines.append(
            "NEXT SHOT (motivate, never render): "
            + (following_in or "preserve the current handoff for the following action")
        )
    lines.append("ONE-SHOT RULE: one continuous moment, one protagonist, one location, no montage, no flashback, no scene reset.")
    return "\n".join(lines)


def plan_shots(
    script: dict[str, Any],
    concept: str,
    duration_seconds: int,
    visual_style: str,
    preferred_backend: str = "auto",
    ambience: str = "natural scene ambience",
    fps: int = 30,
) -> tuple[list[Shot], dict[str, Any]]:
    count = shot_count_for_duration(duration_seconds)
    frames = allocate_frames(duration_seconds, count, fps)
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    narration = script.get("spoken_script") or " ".join(str(b.get("text") or "") for b in beats)
    segments = _split_text(narration, count)
    descriptions = _physical_descriptions(beats, concept)
    continuity = _continuity(script, visual_style, concept)
    prompt_backend = "minimax" if preferred_backend in ("auto", "minimax") else "wan"
    shots: list[Shot] = []
    for index in range(count):
        subject = descriptions[min(len(descriptions) - 1, math.floor(index * len(descriptions) / count))]
        camera = CAMERA_MOVES[index % len(CAMERA_MOVES)]
        framing = FRAMINGS[index % len(FRAMINGS)]
        scene_ambience = ambience or "natural location tone and specific diegetic details"
        previous = descriptions[max(0, min(len(descriptions) - 1, math.floor((index - 1) * len(descriptions) / count)))]
        following = descriptions[min(len(descriptions) - 1, math.floor((index + 1) * len(descriptions) / count))]
        if index == 0:
            story_link = f"Establish the protagonist and world clearly; the next action will be {following}"
        elif index == count - 1:
            story_link = f"Continue directly from {previous}; resolve the action in this final shot"
        else:
            story_link = f"Continue directly from {previous}; end with a visual motivation toward {following}"
        shots.append(Shot(
            id=f"shot-{index + 1:03d}",
            index=index,
            duration_frames=frames[index],
            prompt=construct_prompt(
                subject_action=subject,
                camera_action=camera,
                ambience=scene_ambience,
                continuity=continuity,
                framing=framing,
                backend=prompt_backend,
                stage=_stage(index, count),
                story_link=story_link,
                generation_context=build_generation_context(
                    script, concept, continuity, descriptions,
                    min(len(descriptions) - 1, math.floor(index * len(descriptions) / count)),
                ),
                shot_number=index + 1,
                shot_count=count,
            ),
            negative_prompt=(
                "static image, frozen motion, black frame, low detail, flicker, duplicate subject, "
                "warped anatomy, broken geometry, abrupt lighting change, " + QUALITY_BAN
            ),
            seed=_seed(script.get("video_title") or concept, index),
            narration=segments[index],
            ambience=scene_ambience,
            transition="match_cut" if index and index % 6 == 0 else "crossfade" if index and index % 5 == 0 else "cut",
            continuity=dict(continuity),
            subject_action=subject,
            camera_action=camera,
        ))
    return shots, continuity


def reseed(shot: Shot, attempt: int) -> int:
    rng = random.Random(shot.seed + attempt * 104729)
    return rng.randint(0, 2**31 - 1)
