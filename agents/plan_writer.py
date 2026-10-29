"""
Write a director plan (the scenario) for a world, entertainment first, then validate it.

    plan = write("septic", facts="...", angle="the floating tank")   # validated plan dict

The picture is fixed by the world (engine/director/worlds.py): a hero, and a gag in every beat. The plan
decides what the narrator SAYS and what text appears. Viewers scroll for fun, not for lessons: the facts are
the punchlines of the gags, never advice. A plan that breaks a rule gets one repair turn; if it still fails,
the world's reference plan is used, so a run never stops here (problems are logged as warnings).
"""
import json
import logging
import os
import re

from config.paths import PROJECT_ROOT
from engine.director.worlds import WORLDS

log = logging.getLogger("pipeline")
WORDS = (140, 162)      # ~58-62 s of narration at the measured ~2.55 words/s after pause tightening
PLANS = os.path.join(PROJECT_ROOT, "engine", "director", "plans")

SCENARIO_RULES = """You are the head writer of a funny animated short (60-65 s, vertical, TikTok / YouTube
Shorts / Reels). People scroll to be ENTERTAINED. They stay for a character, a surprise and a laugh; they
learn something only because it is the punchline. The animation already exists; you write the narrator's
lines and the on-screen text for it.

THE FORMAT
1. Cold open (<= 12 words): the most absurd moment of the film, shown first, said as a deadpan fact about the
   hero ("Meet Flushy. A four-ton tank just launched him out of the ground.").
   hook_text: <= 5 words, a shocked question or exclamation, never a title ("LAUNCHED BY A TANK?!").
2. Then rewind and follow the hero through the world. Every beat = one gag the picture already shows: name
   it with a comic comparison (a bouncer, a sorting hat, Pac-Man), then the real fact as the punchline.
3. Narrator voice: dry, quick, playful, like a nature documentary about something ridiculous. Talk ABOUT the
   hero, never TO the viewer. No "you should", no tips, no lessons, no "remember", no "make sure".
4. Escalate: normal -> funny -> going wrong -> disaster -> the cold open makes sense (the payoff).
5. Ending: a short button joke after the payoff (<= 12 words), then one teaser line for the next episode.
6. Rhythm: sentences of 3-12 words (a list may reach 16). Fragments are fine. One idea per sentence.
7. Name things only while they are on screen. Every fact comes from the fact sheet.
8. On-screen text: labels 1-3 words naming what the picture shows, pinned to a listed anchor, timed on a word
   of that beat; at most one stamp/counter per beat (<= 3 words, it must be a joke, not a warning);
   2-3 short chapter titles that are jokes too ("The sorting hat... tank")."""

ADVICE = re.compile(r"\b(you should|make sure|remember to|don't forget|never pump|always|tip|lesson:|"
                    r"keep (it|yours|your)|be sure|avoid)\b", re.I)


def schema(spec):
    beat = {
        "type": "object", "additionalProperties": False,
        "required": ["id", "text", "hook_text", "chapter", "labels", "callouts", "emphasis", "end_card"],
        "properties": {
            "id": {"type": "string", "enum": spec["order"]},
            "text": {"type": "string"},
            "hook_text": {"type": "string"},
            "chapter": {"type": "string"},
            "end_card": {"type": "string"},
            "emphasis": {"type": "array", "items": {"type": "string"}},
            "labels": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["text", "anchor", "at"],
                "properties": {"text": {"type": "string"}, "anchor": {"type": "string", "enum": spec["anchors"]},
                               "at": {"type": "string"}}}},
            "callouts": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["kind", "text", "tone", "at"],
                "properties": {"kind": {"type": "string", "enum": ["stamp", "counter"]}, "text": {"type": "string"},
                               "tone": {"type": "string", "enum": ["good", "bad"]}, "at": {"type": "string"}}}},
        },
    }
    return {"type": "object", "additionalProperties": False,
            "required": ["title", "caption", "hashtags", "facts", "beats"],
            "properties": {"title": {"type": "string"}, "caption": {"type": "string"},
                           "hashtags": {"type": "array", "items": {"type": "string"}},
                           "facts": {"type": "array", "items": {"type": "string"}},
                           "beats": {"type": "array", "items": beat}}}


def _words(text):
    return re.findall(r"[A-Za-z0-9$'\-]+", text)


def _has(text, word):
    return word.lower().strip(".,:;?!") in {w.lower() for w in _words(text)}


def validate(plan, spec=None):
    spec = spec or WORLDS[plan["world"]]
    problems = []
    ids = [b["id"] for b in plan["beats"]]
    if ids != spec["order"]:
        problems.append(f"beats must be exactly {spec['order']} in that order (got {ids})")
    n = sum(len(_words(b["text"])) for b in plan["beats"])
    if not WORDS[0] <= n <= WORDS[1]:
        problems.append(f"narration is {n} words; it must be {WORDS[0]}-{WORDS[1]} to land at 60-65 s")
    hook = next((b for b in plan["beats"] if b["id"] == spec["order"][0]), None)
    if hook:
        if len(_words(hook["text"])) > 12:
            problems.append("the cold open must be <= 12 words")
        if not hook.get("hook_text") or len(_words(hook["hook_text"])) > 5:
            problems.append("hook_text must be 1-5 words")
    chapters = [b for b in plan["beats"] if b.get("chapter")]
    if not 2 <= len(chapters) <= 4:
        problems.append(f"use 2-4 chapter titles (got {len(chapters)})")
    if any(b.get("checklist") for b in plan["beats"]):
        problems.append("no checklists: viewers want a story, not a lesson")
    for b in plan["beats"]:
        shot = spec["shots"].get(b["id"], {})
        if ADVICE.search(b["text"]):
            problems.append(f"{b['id']}: '{ADVICE.search(b['text']).group(0)}' is advice; the narrator comments on "
                            "the hero, never instructs the viewer")
        for lb in b.get("labels", []):
            if lb["anchor"] not in spec["anchors"]:
                problems.append(f"{b['id']}: label anchor '{lb['anchor']}' does not exist")
            if not _has(b["text"], lb["at"]):
                problems.append(f"{b['id']}: label cue '{lb['at']}' is not a word of the beat's text")
            if len(_words(lb["text"])) > 3:
                problems.append(f"{b['id']}: label '{lb['text']}' is longer than 3 words")
        if len(b.get("labels", [])) > 3:
            problems.append(f"{b['id']}: more than 3 labels")
        for c in b.get("callouts", []):
            if not _has(b["text"], c["at"]):
                problems.append(f"{b['id']}: callout cue '{c['at']}' is not a word of the beat's text")
        if len(b.get("callouts", [])) > 1:
            problems.append(f"{b['id']}: more than one callout")
        for cue in shot.get("cues", []):
            if not _has(b["text"], cue):
                problems.append(f"{b['id']}: say the word '{cue}' so the animation lands on it")
        long = [s for s in re.split(r"(?<=[.!?:;])\s+", b["text"]) if len(_words(s)) > 16]
        if long:
            problems.append(f"{b['id']}: sentence too long for short-form: '{long[0][:60]}...'")
    return problems


def _clean(plan, world):
    for b in plan["beats"]:
        for k in ("hook_text", "chapter", "end_card", "labels", "callouts", "emphasis"):
            if not b.get(k):
                b.pop(k, None)
    plan["world"] = world
    plan.setdefault("voice", "energetic")
    plan.setdefault("target_seconds", 62)
    slug = re.sub(r"[^a-z0-9]+", "_", plan["title"].lower()).strip("_")[:40]
    plan["id"] = f"{world}_{slug}"
    if plan["beats"] and plan["beats"][1]["id"] == "follow":
        plan["beats"][1]["rewind"] = True
    return plan


def prompt(spec, facts, angle, problems=None, previous=None):
    shots = "\n".join(f"- {k}: {v['shows']} GAG: {v['gag']}." + (f" (say: {', '.join(v['cues'])})" if v["cues"] else "")
                      for k, v in spec["shots"].items())
    ref = json.load(open(os.path.join(PLANS, f"{spec['world']}.json"), encoding="utf-8"))
    example = json.dumps({"beats": ref["beats"][:4]}, indent=1)
    text = (f"FILM: {spec['subject']}\nHERO: {spec['hero']}\n\nBEATS, in this fixed order, and exactly what each "
            f"one shows:\n{shots}\n\nLABEL ANCHORS: {', '.join(spec['anchors'])}\n\nFACT SHEET (use only these):\n"
            f"{facts}\n\nANGLE: {angle or 'the funniest true story this world can tell'}\n\n"
            f"TOTAL NARRATION: {WORDS[0]}-{WORDS[1]} words across all beats.\n\n"
            f"TONE EXAMPLE (first beats of a published plan, do not copy):\n{example}")
    if problems:
        text += ("\n\nYOUR PREVIOUS PLAN BROKE THESE RULES; fix exactly these and keep the rest:\n- "
                 + "\n- ".join(problems) + "\n\nPREVIOUS PLAN:\n" + json.dumps(previous))
    return text


def write(world, facts, angle=None, call=None):
    from agents import ai_router
    call = call or (lambda s, p, sc: ai_router.ask(s, p, sc, effort="high"))
    spec = WORLDS[world]
    plan, problems = None, None
    for _ in range(2):
        plan = _clean(call(SCENARIO_RULES, prompt(spec, facts, angle, problems, plan), schema(spec)), world)
        problems = validate(plan, spec)
        if not problems:
            return plan
    for p in problems:
        log.warning("plan writer: %s (using the reference plan)", p)
    return json.load(open(os.path.join(PLANS, f"{world}.json"), encoding="utf-8"))
