"""Generate per-clip stock-footage search queries aligned to narration beats.

The script's `pexels_queries` are deliberately GENERIC so clips cut together
visually — but that makes the footage drift from what the narration is actually
saying. This module instead writes ONE on-topic, stock-findable query per clip,
each matched to the slice of narration that plays over that clip, so a silent
viewer can follow the story.
"""

import logging

from dotenv import load_dotenv

from config.paths import get_env_path
from agents import claude_cli

# Reuse the sentence-aware narration splitter (pure text logic).
from agents.comfy_prompts import narration_beats_for_clips

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

SYSTEM = """You pick stock-footage search queries for a narrated documentary video.
For each narration beat you receive ONE line of voiceover; output ONE search query
that finds real stock clips VISUALLY DEPICTING what that line is about, so a silent
viewer can follow the story.

RULES for EVERY query:
1. 1-3 words, lowercase, a CONCRETE filmable thing (object, place, action, creature).
2. Use COMMON stock-library words that thousands of clips exist for ('ocean waves',
   'ancient ruins', 'city night', 'stock market', 'old map', 'sailing ship').
3. NEVER proper nouns or specific names/dates ('Antikythera', 'Columbus', '1492') —
   they return nothing. Translate them to their GENERIC visual ('greek device',
   'wooden sailing ship', 'old map').
4. Match THIS beat's content — what is being talked about RIGHT NOW — not a generic
   mood word ('mysterious', 'epic', 'history').
5. Stay in the SAME world/era as the surrounding beats so clips cut together.

Output ONLY as the structured output."""


def _build_tool(num_clips: int) -> dict:
    return {
        "name": "submit_stock_queries",
        "description": f"Submit exactly {num_clips} stock-footage queries, one per clip slot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": num_clips,
                    "maxItems": num_clips,
                    "description": (
                        f"Exactly {num_clips} queries in chronological order. Each query = "
                        "1-3 common stock words depicting that clip's narration line."
                    ),
                }
            },
            "required": ["queries"],
        },
    }


def _clean_query(q: str) -> str:
    """Normalise a single query: lowercase, trim, collapse whitespace, drop punctuation."""
    q = " ".join((q or "").lower().split())
    q = q.strip(" .,!?\"'")
    return q


def generate_stock_queries(script: dict, num_clips: int, clip_beats: list) -> list:
    """Use Claude to write one on-topic stock query per clip, aligned to narration.

    Returns a list of `num_clips` query strings. Raises on failure so the caller
    can fall back to the script's generic scene queries.
    """
    if num_clips <= 0:
        return []
    if len(clip_beats) != num_clips:
        clip_beats = narration_beats_for_clips(script, num_clips)

    lines = [f"Clip {i}: {beat}" for i, beat in enumerate(clip_beats, start=1)]

    user = f"""Video title: {script.get("video_title", "")}
World / era (keep all queries inside this): {script.get("visual_style", "")}

Write exactly {num_clips} stock-footage queries — one per clip below, in order.
Each query must visualize what that clip's narration line is about.

{chr(10).join(lines)}

Submit them as the structured output."""

    result = claude_cli.ask(SYSTEM, user, _build_tool(num_clips)["input_schema"])
    queries = [_clean_query(q) for q in (result or {}).get("queries", [])]
    queries = [q for q in queries if q]
    if len(queries) != num_clips:
        raise ValueError(f"Expected {num_clips} stock queries, got {len(queries)}")
    return queries
