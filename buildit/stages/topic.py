"""
Stage 1 - brief.json: the machine, the hook object, and the analogy chain planned in the kit's parts.

`pick()` (no topic given) finds a machine people are curious about right now that the kit can build and that the
channel has not covered (runs/buildit/history.json). A topic the kit cannot show stops here, and its missing
parts go to runs/buildit/wishlist.json as kit extensions.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from agents import llm

from ..config import RUNS
from ..kit import hosts, vocab
from ..runner import StageError

log = logging.getLogger("pipeline")
HISTORY = os.path.join(RUNS, "history.json")
WISHLIST = os.path.join(RUNS, "wishlist.json")

STYLE = """The channel shows how a real machine works by BUILDING it in front of you, one part at a time, from
simple analogies. The real machine (the host: a see-through fridge, washer, water heater... in a bright studio)
is the star: every part the story adds flies in and CLICKS INTO its real place on it, pipes connect the parts,
and coloured flow (blue = cold, red = hot) shows what moves where. Story: open on an everyday object doing
something surprising (the hook, 2 s, a curiosity gap), then repeat 4 to 7 times: analogy -> problem ("But...")
-> the part that fixes it, mounted on the machine -> payoff you can SEE. Each part answers the problem the
previous step created. Talk to the viewer as "you"; short punchy sentences; never jargon before the part is on
screen; analogies simplify but are never wrong. The finished machine runs, then end with a question to the
viewer that invites a comment."""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "on-screen title, max 6 words"},
        "machine": {"type": "string", "description": "the complete machine the video ends on"},
        "host": {"type": "string", "enum": list(hosts.HOSTS),
                 "description": "the host machine model the parts mount on (machine = generic open frame)"},
        "hook": {"type": "string", "description": "the everyday object doing something surprising in 2 s"},
        "through_line": {"type": "string", "description": "the object that turns into a real part, if any"},
        "chain": {"type": "array", "items": {"type": "object", "properties": {
            "analogy": {"type": "string"}, "problem": {"type": "string"},
            "part_added": {"type": "string", "description": "the machine part this step adds"},
            "kit_parts": {"type": "array", "items": {"type": "string", "enum": list(vocab.PARTS)}},
            "slot": {"type": "string", "description": "the host slot the part mounts in (its real place)"},
            "payoff": {"type": "string"}}, "required": ["analogy", "problem", "part_added", "kit_parts", "slot",
                                                        "payoff"]}},
        "parts_needed": {"type": "array", "items": {"type": "string"},
                         "description": "every kit part type the video uses"},
        "missing": {"type": "array", "items": {"type": "string"},
                    "description": "parts the story needs that the kit does not have (empty if none)"},
        "can_build": {"type": "boolean"},
    },
    "required": ["title", "machine", "host", "hook", "through_line", "chain", "parts_needed", "missing",
                 "can_build"],
}


def history() -> list[dict]:
    return json.load(open(HISTORY, encoding="utf-8")) if os.path.exists(HISTORY) else []


def remember(topic: str, slug: str):
    h = history()
    h.append({"topic": topic, "slug": slug, "date": datetime.now().isoformat(timespec="seconds")})
    os.makedirs(RUNS, exist_ok=True)
    json.dump(h, open(HISTORY, "w", encoding="utf-8"), indent=1)


def pick() -> str:
    """A machine topic people search for now, buildable with the kit, not covered yet."""
    done = [h["topic"] for h in history()]
    schema = {"type": "object", "properties": {"candidates": {"type": "array", "items": {"type": "object", "properties": {
        "topic": {"type": "string", "description": "phrased 'How a ... works'"},
        "why_now": {"type": "string"}, "kit_parts": {"type": "array", "items": {"type": "string"}}},
        "required": ["topic", "why_now", "kit_parts"]}}}, "required": ["candidates"]}
    out = llm.ask("You are a producer for a short-form engineering explainer channel.",
                  f"""{STYLE}

Find 5 machines or devices people are curious about right now (search current news, seasons, viral questions)
that this 3D kit can build out of its parts, ranked best first. Not one of these, already made: {done or 'none'}.

{vocab.describe()}""", schema, effort="medium", web=True, label="buildit_pick")
    for c in out["candidates"]:
        if c["topic"] not in done and all(p in vocab.PARTS for p in c["kit_parts"]):
            log.info("[topic] picked '%s' (%s)", c["topic"], c["why_now"])
            return c["topic"]
    return out["candidates"][0]["topic"]


def inputs(run):
    return [run.meta.get("topic"), run.meta.get("length"), run.meta.get("lang"), sorted(vocab.PARTS)]


def run(run):
    topic = run.meta["topic"]
    out = llm.ask("You plan short vertical machine explainers built from analogies, for a 3D kit.",
                  f"""{STYLE}

Topic: {topic}
Length: {run.meta['length']} seconds, English narration.

Choose the host machine model (the real product the parts mount on). Plan the analogy chain (4 to 7 steps)
using only these 3D kit parts; put each step's parts in kit_parts and the host slot where that part really sits
(e.g. a fridge's evaporator inside_top, compressor back_bottom, condenser back_middle). The hook object is a
prop; it may later fly into the machine as the real part it resembles. Analogies may simplify but must not be
wrong. If the story needs a part the kit does not have, list it in `missing` and set can_build false.

{vocab.describe()}""", SCHEMA, effort="high", label="buildit_brief")
    out["parts_needed"] = sorted({p for p in out["parts_needed"] if p in vocab.PARTS} |
                                 {p for s in out["chain"] for p in s["kit_parts"] if p in vocab.PARTS})
    brief = {"topic": topic, "target_seconds": run.meta["length"], "lang": run.meta.get("lang", "en"), **out}
    run.save("brief.json", brief)
    if not out["can_build"] or out["missing"]:
        wish = json.load(open(WISHLIST, encoding="utf-8")) if os.path.exists(WISHLIST) else []
        wish.append({"topic": topic, "missing": out["missing"], "date": datetime.now().isoformat(timespec="seconds")})
        json.dump(wish, open(WISHLIST, "w", encoding="utf-8"), indent=1)


def validate(run):
    b = run.need("brief.json")
    if not b.get("can_build") or b.get("missing"):
        raise StageError(f"the kit cannot film '{b['topic']}': missing {b.get('missing')} (logged in wishlist.json)")
    if not 4 <= len(b["chain"]) <= 8:
        raise StageError(f"the analogy chain needs 4-7 steps, got {len(b['chain'])}")
    if b.get("host") not in hosts.HOSTS:
        raise StageError(f"unknown host machine '{b.get('host')}'")
