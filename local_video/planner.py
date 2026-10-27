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
# Camera language, not "cinematic": plain photographic wording keeps the models out of the dreamy, painterly look.
PHOTO_LOOK = (
    "real documentary footage shot on a full-frame camera, 35mm lens, natural light, true-to-life "
    "textures and colours, sharp focus, physically plausible motion"
)
MINIMAX_SUFFIX = PHOTO_LOOK + ", coherent anatomy, stable object identity"
WAN_SUFFIX = PHOTO_LOOK + ", stable motion, coherent subject"
REALISM_BAN = (
    "painting, illustration, concept art, CGI, 3D render, cartoon, anime, dreamy haze, glow, bloom, "
    "soft focus, blurry, oversaturated colours, fantasy lighting, morphing, melting shapes"
)
CAMERA_MOVES = (
    "slow push-in", "gentle tracking shot", "controlled handheld follow", "smooth orbit",
    "low-angle dolly", "overhead drift", "slow pull-back", "lateral parallax move",
)
FRAMINGS = (
    "24mm wide establishing frame", "35mm medium-wide frame", "50mm medium frame",
    "85mm intimate close-up", "macro detail shot", "low-angle 35mm frame",
)


def _camera_plan(subject: str, index: int) -> tuple[str, str]:
    """Honor explicit screenplay composition instead of adding a conflicting camera preset."""
    action = subject.lower()
    if "extreme close-up" in action or "macro" in action:
        return "controlled macro push-in", "macro detail shot"
    if "close-up" in action or "close shot" in action:
        return "slow intimate push-in", "85mm intimate close-up"
    if "low angle" in action or "looking up" in action or "floor level" in action:
        return "slow low-angle drift", "24mm low-angle wide frame"
    if "top-down" in action or "overhead" in action or "looking straight down" in action:
        return "slow overhead drift", "24mm overhead wide frame"
    if "side angle" in action or "side shot" in action or "from the side" in action:
        return "gentle lateral tracking shot", "35mm side-angle medium-wide frame"
    if "wide" in action:
        return CAMERA_MOVES[index % len(CAMERA_MOVES)], "24mm wide establishing frame"
    if "medium" in action:
        return CAMERA_MOVES[index % len(CAMERA_MOVES)], "50mm medium frame"
    return CAMERA_MOVES[index % len(CAMERA_MOVES)], FRAMINGS[index % len(FRAMINGS)]


MIN_DURATION, MAX_DURATION = 30, 90


def validate_duration(seconds: int) -> int:
    if not MIN_DURATION <= int(seconds) <= MAX_DURATION:
        raise ValueError(f"Short-form project duration must be between {MIN_DURATION} and {MAX_DURATION} seconds")
    return int(seconds)


def shot_count_for_duration(seconds: int) -> int:
    return max(10, min(30, round(validate_duration(seconds) / 3.0)))


def allocate_frames(total_seconds: int, shot_count: int, fps: int = 30) -> list[int]:
    if shot_count < 1:
        raise ValueError("shot_count must be positive")
    total = validate_duration(total_seconds) * fps
    base, remainder = divmod(total, shot_count)
    frames = [base + (1 if i < remainder else 0) for i in range(shot_count)]
    if any(not 75 <= value <= 120 for value in frames):
        raise ValueError("Shot plan must average 2.5 to 4 seconds per shot")
    return frames


def allocate_story_frames(total_seconds: int, beat_texts: list[str], fps: int = 30) -> list[int]:
    """Allocate 2.5-4 second shots by narration density and story position."""
    if not beat_texts:
        return allocate_frames(total_seconds, shot_count_for_duration(total_seconds), fps)
    total = validate_duration(total_seconds) * fps
    count = len(beat_texts)
    if not count * 75 <= total <= count * 120:
        return allocate_frames(total_seconds, count, fps)
    weights: list[float] = []
    for index, text in enumerate(beat_texts):
        words = max(1, len(str(text).split()))
        position = index / max(1, count - 1)
        story_emphasis = 0.9 if index == 0 else 1.12 if position >= 0.8 else 1.0
        weights.append(max(0.75, min(1.35, words / 7.0)) * story_emphasis)
    raw = [total * weight / sum(weights) for weight in weights]
    frames = [max(75, min(120, round(value))) for value in raw]
    delta = total - sum(frames)
    while delta:
        direction = 1 if delta > 0 else -1
        candidates = [
            index for index, value in enumerate(frames)
            if (direction > 0 and value < 120) or (direction < 0 and value > 75)
        ]
        if not candidates:
            raise ValueError("Could not allocate exact dynamic shot durations")
        candidates.sort(key=lambda index: raw[index] - frames[index], reverse=direction > 0)
        for index in candidates:
            if not delta:
                break
            frames[index] += direction
            delta -= direction
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


def character_look(character: dict[str, Any], beat_index: int | None) -> str:
    """The one appearance a character has at a beat (0-based); later `look_changes` win."""
    look = str(character.get("look") or "")
    if beat_index is None:
        return look
    changes = [c for c in character.get("look_changes") or [] if isinstance(c, dict) and c.get("look")]
    for change in sorted(changes, key=lambda c: int(c.get("from_beat") or 0)):
        if int(change.get("from_beat") or 0) - 1 <= beat_index:
            look = str(change["look"])
    return look


def _beat_visual(script: dict[str, Any], beat_index: int) -> dict[str, Any]:
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    beat = beats[beat_index] if 0 <= beat_index < len(beats) and isinstance(beats[beat_index], dict) else {}
    return beat.get("visual") if isinstance(beat.get("visual"), dict) else {}


def beat_cast(script: dict[str, Any], beat_index: int) -> list[dict[str, Any]]:
    """The script characters a beat names in its visual description or continuity notes."""
    characters = [c for c in script.get("characters") or [] if isinstance(c, dict)]
    visual = _beat_visual(script, beat_index)
    text = " ".join(str(visual.get(key) or "") for key in ("description", "continuity_in", "continuity_out"))
    return [c for c in characters if str(c.get("name") or "").strip()
            and re.search(rf"\b{re.escape(str(c['name']).strip())}\b", text, re.IGNORECASE)]


def _names_cast(script: dict[str, Any]) -> bool:
    """True when the beats name their characters, so a beat naming nobody really shows nobody."""
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    return any(beat_cast(script, index) for index in range(len(beats)))


def beat_labels(script: dict[str, Any], beat_index: int) -> tuple[str, str]:
    """The beat's place and light labels, lower-cased; empty for scripts written without them."""
    visual = _beat_visual(script, beat_index)
    return (str(visual.get("scene") or "").strip().lower(), str(visual.get("light") or "").strip().lower())


def continuation_source(
    labels: list[tuple[str, str]], index: int, casts: list[list[str]] | None = None,
) -> int | None:
    """The earlier shot whose last frame this shot opens on, or None for a fresh opening.

    A labelled shot continues the latest earlier shot in the same place and light, so a cut
    back to a place keeps its look and a cut elsewhere never morphs out of an unrelated frame.
    A return to an earlier shot also needs the same cast: opening a two-army shot on a frame of
    one hero charging the camera makes the model add the enemy beside him.
    Unlabelled scripts keep the old rule: every shot continues the previous one.
    """
    if index <= 0 or index >= len(labels):
        return None
    if not labels[index][0]:
        return index - 1
    same_cast = (lambda prior: True) if casts is None else (
        lambda prior: prior == index - 1 or sorted(casts[prior]) == sorted(casts[index]))
    return next((prior for prior in range(index - 1, -1, -1)
                 if labels[prior] == labels[index] and same_cast(prior)), None)


def _words(text: str, size: int = 5) -> set[str]:
    return set(re.findall(rf"[a-z]{{{size},}}", text.lower().replace("'s", "")))


def _for_light(text: str, script: dict[str, Any], beat_index: int) -> str:
    """Drop clauses about another beat's light, so a style line about the eclipse stays out of dawn."""
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    light = beat_labels(script, beat_index)[1]
    if not light or not text:
        return text
    others = set().union(*(_words(beat_labels(script, i)[1]) for i in range(len(beats)))) - _words(light)
    clauses = [part for part in re.split(r"\s*[;,]\s*", text) if part and not _words(part) & others]
    return ", ".join(clauses)


def _for_scene(text: str, script: dict[str, Any], beat_index: int, split: str = r"\s*[;,]\s*") -> str:
    """Drop clauses that belong only to another scene, so the fire never sees the modern trench.

    A clause naming another scene's label words is dropped unless it also names this beat's own.
    """
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    scene = beat_labels(script, beat_index)[0]
    if not scene or not text:
        return text
    own = _words(scene)
    others = set().union(*(_words(beat_labels(script, i)[0]) for i in range(len(beats)))) - own
    clauses = [part for part in re.split(split, text)
               if part.strip() and (not _words(part) & others or _words(part) & own)]
    return (" " if split == _SENTENCES else ", ").join(part.strip() for part in clauses)


# Whole sentences: a world description's commas belong to one place and must stay together.
# Titles are not sentence ends ("Dr. Cara").
_SENTENCES = r"(?<=[.;])(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bSt\.)(?<!\bMrs\.)\s+"


def beat_objects(script: dict[str, Any], beat_index: int) -> list[str]:
    """The recurring objects a beat's visual mentions; the rest are not in this shot.

    An object matches by its head noun ("The orange ash layer" -> "layer"): matching any word
    put the buried ash layer into every fire shot that mentions orange flames.
    """
    visual = _beat_visual(script, beat_index)
    text = _words(" ".join(str(visual.get(key) or "") for key in ("description", "continuity_out")), 4)
    present = []
    for item in script.get("recurring_objects") or []:
        name = re.split(r"\s+[—–-]\s+|[:;(]", str(item))[0]
        head = re.findall(r"[a-z]{4,}", name.lower().replace("'s", ""))
        if head and head[-1] in text:
            present.append(str(item))
    return present


def payoff_of(subject_action: str) -> str:
    """The beat's final sentence: what must be on screen when the clip ends."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", subject_action) if part.strip()]
    return sentences[-1] if sentences else subject_action


def _continuity(
    script: dict[str, Any], visual_style: str, concept: str, beat_index: int | None = None,
) -> dict[str, Any]:
    characters = [c for c in script.get("characters") or [] if isinstance(c, dict)]
    nobody = ""
    if beat_index is not None:
        # Only the characters this beat names: a listed bystander's costume (a cap, medals)
        # otherwise leaks onto whoever is on screen, and a crowd shot gains posing leads.
        named = beat_cast(script, beat_index)
        if named or not _names_cast(script):
            characters = named or characters
        else:
            characters = []
            nobody = "no named character in this shot; any people are anonymous background figures"
    cast = "; ".join(
        f"{c.get('name')}: {character_look(c, beat_index)}" for c in characters if isinstance(c, dict)
    )
    palette = script.get("color_palette") or "consistent restrained cinematic palette"
    time_of_day = script.get("time_of_day") or "consistent time of day unless the story explicitly advances"
    objects = script.get("recurring_objects", [])
    location = script.get("location") or (
        f"one continuous physical world for {concept}; preserve geography, architecture, scale, "
        "weather, and recurring props between adjacent shots"
    )
    geography = script.get("screen_geography") or ""
    if beat_index is not None:
        palette = _for_scene(_for_light(palette, script, beat_index), script, beat_index)
        visual_style = _for_scene(_for_light(visual_style, script, beat_index), script, beat_index)
        location = _for_scene(location, script, beat_index, _SENTENCES)
        geography = _for_scene(geography, script, beat_index, _SENTENCES)
        scene = beat_labels(script, beat_index)[0]
        if scene and geography:
            # A character never seen in this place (Boudica at the modern dig) loses their rules here.
            beats = script.get("beats") if isinstance(script.get("beats"), list) else []
            here = {str(c.get("name")).strip() for i in range(len(beats)) if beat_labels(script, i)[0] == scene
                    for c in beat_cast(script, i)}
            absent = [str(c.get("name")).strip() for c in script.get("characters") or []
                      if isinstance(c, dict) and str(c.get("name") or "").strip() not in here]
            parts = re.split(r"(?<=;)\s+|" + _SENTENCES, geography)
            geography = " ".join(part for part in parts if not any(
                re.search(rf"\b{re.escape(name)}\b", part, re.IGNORECASE) for name in absent if name))
        time_of_day = beat_labels(script, beat_index)[1] or time_of_day
        objects = beat_objects(script, beat_index)
    return {
        "characters": cast or nobody or (
            "one recurring protagonist with exactly the same face, body, clothing, equipment, "
            "and color scheme in every shot"
        ),
        "wardrobe": script.get("wardrobe") or "unchanged clothing and accessories between adjacent shots",
        "vehicles": script.get("vehicles") or "identical vehicle design and markings where present",
        "location": location,
        "palette": palette,
        "screen_geography": geography,
        "time_of_day": time_of_day,
        "recurring_objects": "; ".join(str(item) for item in objects if item),
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
    cast_names: list[str] | None = None,
    light: str = "",
    opening: str = "continue",
) -> str:
    suffix = MINIMAX_SUFFIX if backend == "minimax" else WAN_SUFFIX
    # First takes get what makes retakes pass: the payoff and the exact cast stated up front.
    cast = ""
    if cast_names:
        cast = (
            f"ON SCREEN: exactly {len(cast_names)} named character{'s' if len(cast_names) > 1 else ''} "
            f"({', '.join(cast_names)}), each appearing once; no duplicate or mirrored copies. "
            "Every other figure is an anonymous extra who looks clearly different: other hair, plain "
            "drab clothing, never the named character's cloak, colours, or signature item. "
        )
    elif cast_names is not None:
        cast = "ON SCREEN: none of the story's named characters; only anonymous figures, if any. "
    environment = continuity.get("location", "a coherent cinematic environment")
    style = continuity.get("visual_style", "photographic realism")
    lighting = "natural daylight with real shadows and no haze"
    if light:
        lighting = f"{light}, held steady for the whole clip (this shot only; later story light never appears early)"
    atmosphere = "clear air, crisp detail, everyday real-world colour"
    scope = (
        "Do not restart the story, show an earlier location, or compress multiple scenes into this clip."
        if opening == "continue" else "Do not compress multiple scenes into this clip."
    )
    return (
        f"CURRENT RENDER TASK — SHOT {shot_number:02d} OF {shot_count:02d}. Render only this shot, "
        "not a montage and not the other screenplay events. "
        f"CURRENT SHOT (the only event to render): {subject_action}. "
        "END-FRAME PAYOFF (clearly visible before the clip ends; move toward it from the first second): "
        f"{payoff_of(subject_action)} {cast}"
        f"[{stage.upper()}] Lighting: {lighting}. Camera: {camera_action}; {framing}; 9:16 portrait composition. "
        f"Atmosphere: {atmosphere}. Visual style: {style}. {suffix}. {QUALITY_BAN}"
        f" Audio direction: {ambience}, environmental sound only. Dialogue: none. Narration: none. "
        "Voices and vocals: none. The production notes below are silent context; never speak, "
        f"display, caption, subtitle, label, or spell any of their words. {scope}\n\n"
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
    opening: str = "continue",
) -> str:
    """Build a compact local window so a short clip renders one beat, not the whole story.

    `opening` is "continue" (starts on the previous shot's last frame), "return" (starts on an
    earlier frame of the same place and light) or "new" (a hard cut with no start image).
    """
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

    _, inherit, handoff, _ = beat_data(index)
    start = {
        "continue": f"Required starting state: {inherit or 'begin exactly where the previous shot ended'}",
        "return": "RETURN TO AN EARLIER PLACE: the start image is this same place and light from an earlier "
                  "moment; keep its geography and every character's exact clothing, then play this shot's action.",
        "new": "NEW SCENE (hard cut): open directly on this shot's own place and light; nothing from the "
               "previous shot's frame carries over except each named character's exact appearance.",
    }[opening]
    lines = [
        "SINGLE-SHOT CONTINUITY LOCK",
        "WHOLE-STORY CONTRACT: "
        f"{script.get('story_premise') or concept} Goal: {script.get('protagonist_goal', '')} "
        f"Final payoff: {script.get('ending_payoff', '')}",
        start,
        f"Required ending state: {handoff or 'finish with a clear visual handoff to the next action'}",
        f"Character identity lock: {continuity.get('characters')}",
        "The current shot's own description wins over the identity lock for age, size, and pose.",
        f"World lock: {continuity.get('location')}"
        + (f"; palette: {continuity['palette']}" if continuity.get("palette") else ""),
        f"Light and sky in this shot: {continuity.get('time_of_day')}",
    ]
    if continuity.get("screen_geography"):
        lines.append(
            f"SCREEN GEOGRAPHY (fixed for the whole film): {continuity['screen_geography']}. "
            "Opposing sides face each other across a visible gap; they never move side by side or mix."
        )
    if index > 0 and opening == "continue":
        _, _, previous_handoff, _ = beat_data(index - 1)
        lines.append(
            "PREVIOUS SHOT (inherit, never replay): "
            + (previous_handoff or "continue its final pose, props, lighting, and geography")
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
    shot_count: int | None = None,
) -> tuple[list[Shot], dict[str, Any]]:
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    count = shot_count or len(beats) or shot_count_for_duration(duration_seconds)
    beat_texts = [str(beat.get("text") or "") for beat in beats] if beats else [""] * count
    frames = (allocate_story_frames(duration_seconds, beat_texts, fps) if len(beat_texts) == count
              else allocate_frames(duration_seconds, count, fps))
    narration = script.get("spoken_script") or " ".join(str(b.get("text") or "") for b in beats)
    # One beat per shot: its own sentence ("Dr. Cara" must not split at the abbreviation).
    texts = [str(b.get("text") or "").strip() for b in beats if isinstance(b, dict)]
    segments = texts if len(texts) == count and all(texts) else _split_text(narration, count)
    descriptions = _physical_descriptions(beats, concept)
    continuity = _continuity(script, visual_style, concept)
    prompt_backend = "minimax" if preferred_backend in ("auto", "minimax") else "wan"
    beat_of = [min(len(descriptions) - 1, math.floor(index * len(descriptions) / count)) for index in range(count)]
    labels = [beat_labels(script, beat) for beat in beat_of]
    casts = [[str(c["name"]).strip() for c in beat_cast(script, beat)] for beat in beat_of]
    names_cast = _names_cast(script)
    shots: list[Shot] = []
    for index in range(count):
        beat_index = beat_of[index]
        subject = descriptions[beat_index]
        source = continuation_source(labels, index, casts)
        opening = "continue" if source == index - 1 else "new" if source is None and index else "return"
        if index == 0:
            opening = "new" if labels[0][0] else "continue"
        cast_names = [str(c["name"]).strip() for c in beat_cast(script, beat_index)]
        # Each shot carries only the looks its beat needs (a cub scene never sees the adult).
        shot_continuity = _continuity(script, visual_style, concept, beat_index)
        camera, framing = _camera_plan(subject, index)
        scene_ambience = ambience or "natural location tone and specific diegetic details"
        previous = descriptions[max(0, min(len(descriptions) - 1, math.floor((index - 1) * len(descriptions) / count)))]
        following = descriptions[min(len(descriptions) - 1, math.floor((index + 1) * len(descriptions) / count))]
        if index == 0:
            story_link = f"Establish the protagonist and world clearly; the next action will be {following}"
        elif index == count - 1:
            story_link = f"Continue directly from {previous}; resolve the action in this final shot"
        else:
            story_link = f"Continue directly from {previous}; end with a visual motivation toward {following}"
        transition = str(_beat_visual(script, beat_index).get("transition") or "cut")
        if index == 0 or transition not in {"cut", "match_cut", "crossfade"}:
            transition = "cut"
        shots.append(Shot(
            id=f"shot-{index + 1:03d}",
            index=index,
            duration_frames=frames[index],
            prompt=construct_prompt(
                subject_action=subject,
                camera_action=camera,
                ambience=scene_ambience,
                continuity=shot_continuity,
                framing=framing,
                backend=prompt_backend,
                stage=_stage(index, count),
                story_link=story_link,
                generation_context=build_generation_context(
                    script, concept, shot_continuity, descriptions, beat_index, opening,
                ),
                shot_number=index + 1,
                shot_count=count,
                cast_names=cast_names if names_cast else None,
                light=labels[index][1],
                opening=opening,
            ),
            negative_prompt=(
                "static image, frozen motion, black frame, low detail, flicker, duplicate subject, "
                "warped anatomy, broken geometry, abrupt lighting change, " + REALISM_BAN + ". " + QUALITY_BAN
            ),
            seed=_seed(script.get("video_title") or concept, index),
            narration=segments[index],
            ambience=scene_ambience,
            transition=transition,
            continuity=shot_continuity,
            subject_action=subject,
            camera_action=camera,
            scene=labels[index][0],
            light=labels[index][1],
            cast=cast_names,
        ))
    return shots, continuity


def reseed(shot: Shot, attempt: int) -> int:
    rng = random.Random(shot.seed + attempt * 104729)
    return rng.randint(0, 2**31 - 1)
