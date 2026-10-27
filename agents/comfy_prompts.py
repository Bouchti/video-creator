"""Generate per-clip visual prompts for local ComfyUI / Wan text-to-video."""

import json
import logging
import os
import re

from dotenv import load_dotenv

from config.paths import get_env_path
from agents import claude_cli

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

MAX_PROMPT_CHARS = int(os.getenv("COMFY_MAX_PROMPT_CHARS", "220"))

SYSTEM = """You write ultra-literal text-to-video prompts for a LOCAL AI model (Wan 2.2).
The model is weak at abstract language — it needs concrete, filmable visuals.

RULES for EVERY clip prompt:
1. ONE sentence, 20-35 words max. Subject and action FIRST.
2. Show EXACTLY what the narration line describes — a silent viewer must understand the story.
3. Name visible nouns from the narration (people, animals, places, objects, maps, money, ships).
4. Same recurring subject + world as visual_style across all clips (one continuous documentary).
5. Include shot type + camera motion (wide shot, close-up, slow pan).
6. NO abstract mood words alone (mysterious, epic, dramatic) without a visible subject.
7. NO text overlays, subtitles, logos, or UI.
8. Content safety: no blood, weapons, suffering, violence.

Output ONLY as the structured output."""


def _build_tool(num_clips: int) -> dict:
    return {
        "name": "submit_clip_prompts",
        "description": f"Submit exactly {num_clips} literal video prompts, one per clip slot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "clip_prompts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": num_clips,
                    "maxItems": num_clips,
                    "description": (
                        f"Exactly {num_clips} prompts in chronological order. Each prompt = "
                        "one filmable moment matching that clip's narration line."
                    ),
                }
            },
            "required": ["clip_prompts"],
        },
    }


def finalize_wan_prompt(core: str, visual_style: str = "") -> str:
    """Keep prompts short enough for Wan/umt5; append compact style anchor."""
    core = " ".join(core.split())
    style = " ".join((visual_style or "").split())
    if style and style.lower() not in core.lower():
        prompt = f"{core}, {style}"
    else:
        prompt = core
    if len(prompt) > MAX_PROMPT_CHARS:
        prompt = prompt[:MAX_PROMPT_CHARS].rsplit(",", 1)[0].strip()
    return prompt


def narration_beats_for_clips(script: dict, num_clips: int) -> list[str]:
    """Split narration into num_clips chronological beats (sentence-aware)."""
    text = (script.get("spoken_script") or "").strip()
    if not text or num_clips <= 0:
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        sentences = [text]
    beats = []
    for i in range(num_clips):
        start = (i * len(sentences)) // num_clips
        end = ((i + 1) * len(sentences) - 1) // num_clips
        beats.append(" ".join(sentences[start : end + 1]))
    return beats


def generate_clip_prompts(script: dict, num_clips: int, clip_beats: list[str]) -> list[str]:
    """Use Claude to write one literal Wan prompt per clip, aligned to narration."""
    if num_clips <= 0:
        return []
    if len(clip_beats) != num_clips:
        clip_beats = narration_beats_for_clips(script, num_clips)

    lines = []
    for i, beat in enumerate(clip_beats, start=1):
        lines.append(f"Clip {i} narration: {beat}")

    user = f"""Video title: {script.get("video_title", "")}
Visual style (append briefly to every prompt): {script.get("visual_style", "")}
Mood: {script.get("mood", "")}

Storyboard scenes (for world continuity — stay inside this world):
{json.dumps(script.get("scenes", []), indent=2)}

Write exactly {num_clips} literal video prompts — one per clip below, in order.
Each prompt must visualize ONLY what that narration line says.

{chr(10).join(lines)}

Submit them as the structured output."""

    result = claude_cli.ask(SYSTEM, user, _build_tool(num_clips)["input_schema"])
    prompts = (result or {}).get("clip_prompts", [])
    if len(prompts) != num_clips:
        raise ValueError(f"Expected {num_clips} clip prompts, got {len(prompts)}")
    style = script.get("visual_style", "")
    return [finalize_wan_prompt(p, style) for p in prompts]


def fallback_clip_prompt(script: dict, clip_beat: str, variant: int = 0) -> str:
    """Narration-first fallback when Claude clip prompts are unavailable."""
    variant_cues = (
        "",
        "Close-up of ",
        "Wide shot of ",
        "Tracking shot of ",
    )
    cue = variant_cues[variant % len(variant_cues)]
    core = f"{cue}photoreal documentary footage showing {clip_beat}"
    return finalize_wan_prompt(core, script.get("visual_style", ""))
