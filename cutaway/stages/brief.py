"""Stage 1 - brief.json: topic, length, audience, aspect, the kit that films it, its sub-mechanisms (the kit's
whole story when it has one, else 3-5), the hook."""
from __future__ import annotations

import logging

from agents import llm

from .. import kits
from ..runner import StageError

log = logging.getLogger("pipeline")

SYSTEM = """You plan short vertical "how it's built" engineering explainers (TikTok, Reels, Shorts) for a premium
3D cutaway channel. The viewer is curious, smart, 12+, scrolling with the sound maybe off. You only plan videos
that one of the available 3D kits can film; if none fits, say so with kit = "none"."""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "short on-screen title, max 6 words"},
        "kit": {"type": "string"},
        "audience": {"type": "string"},
        "angle": {"type": "string", "description": "the one surprising idea the video is built around"},
        "hook": {"type": "string", "description": "first 1.5 s: the visual payoff and the question or number"},
        "mechanisms": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "name": {"type": "string"}, "why": {"type": "string"}},
            "required": ["id", "name", "why"]}},
        "missing": {"type": "string", "description": "if kit is none: the rig a new kit would need"},
    },
    "required": ["title", "kit", "audience", "angle", "hook", "mechanisms"],
}


def inputs(run):
    return [run.meta.get("topic"), run.meta.get("length"), sorted(kits.KITS)]


def run(run):
    topic = run.meta["topic"]
    prompt = f"""Topic: {topic}
Target length: {run.meta['length']} seconds, vertical 1080x1920.

Available 3D kits (each can film only these sub-mechanisms, by id):
{kits.describe()}

Pick the kit, then its sub-mechanism ids in the order the story should explain them (cause before effect): a
kit with a story ("story: ...") lists them all in that order; otherwise pick 3 to 5. The hook must land in the first 1.5 seconds: a visual payoff plus a question or a surprising number."""
    out = llm.ask(SYSTEM, prompt, SCHEMA, effort="medium", label="cutaway_brief")
    kit = kits.KITS.get(out["kit"])
    if kit is None:
        raise StageError(f"no kit can film '{topic}': needs {out.get('missing') or 'a new assembly'}")
    out["mechanisms"] = [m for m in out["mechanisms"] if m["id"] in kit["mechanisms"]]
    if kit.get("story"):
        # a kit with a story explains its machine from A to Z: every chapter, in order (a pick of 3-5 left
        # whole steps out: the first engine draft never said where the air and fuel come from)
        named = {m["id"]: m for m in out["mechanisms"]}
        out["mechanisms"] = [named.get(m) or {"id": m, "name": m.replace("_", " "),
                                              "why": kit["mechanisms"][m]["explains"]} for m in kit["story"]]
    brief = {"topic": topic, "target_seconds": run.meta["length"], "aspect": "1080x1920", "fps": 30, **out}
    run.save("brief.json", brief)


def validate(run):
    b = run.need("brief.json")
    kit = kits.KITS.get(b.get("kit"))
    if kit is None:
        raise StageError("brief.json names no known kit")
    ids = [m["id"] for m in b["mechanisms"]]
    if kit.get("story"):
        if ids != kit["story"]:
            raise StageError(f"brief must follow the kit's story {kit['story']}, got {ids}")
    elif not 3 <= len(ids) <= 5:
        raise StageError(f"brief needs 3-5 sub-mechanisms the kit can film, got {ids}")
    if len(set(ids)) != len(ids):
        raise StageError("brief repeats a sub-mechanism")
    if not 45 <= b["target_seconds"] <= 90:
        raise StageError("target length out of range")
