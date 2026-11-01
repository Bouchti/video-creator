"""
Stage 3 - script.json: beats (narration, on-screen title, stat with a fact_id, visual intent, shot type,
target seconds), written by the model and held to hard checks in code; failures go back as notes (2 rewrites).
"""
from __future__ import annotations

import json
import logging
import re

from agents import llm

from .. import kits
from ..runner import StageError

log = logging.getLogger("pipeline")
WPM = (150, 165)
SHOT_TYPES = ["hero", "peel", "section", "close", "lengthwise", "quarter"]
NUMBER_WORDS = {"five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
                "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "hundred": 100,
                "hundreds": 100, "thousand": 1000, "thousands": 1000, "million": 10 ** 6, "millions": 10 ** 6,
                "billion": 10 ** 9, "billions": 10 ** 9, "half": 0.5, "dozen": 12, "dozens": 12}
JARGON = re.compile(r"\b(TDC|BDC|top dead cent(?:re|er)|crank degrees?|stoichiometric|BTDC|ATDC|"
                    r"volumetric efficiency|thermal efficiency|psi|bar\b|torque curve)\b", re.I)
TELEGRAM = re.compile(r"^\W*\w+(?: \w+)?:\s")          # "Suck: the piston drops"
BANNED = re.compile(r"\b(comment|like and|subscribe|follow for|smash|link in bio)\b", re.I)

SYSTEM = """You write narration for premium 60-90 second vertical 3D cutaway explainers ("how it's built").
It is read aloud by a warm human narrator, so write the way a great teacher talks to a curious friend: full,
flowing sentences joined by "so", "then", "which", "and that"; varied sentence length; never a list, a label
or a telegram ("Suck: the piston drops" reads like a robot). Every sentence makes the viewer see something
happen on screen. Cause before effect, and no step skipped: the viewer must be able to retell the whole chain.
No filler ("in this video", "let's dive in"), no hype adjectives. Numbers only from the verified fact list,
quoted faithfully (round only when the fact says "about")."""

SCHEMA = {
    "type": "object",
    "properties": {
        "beats": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"},
            "mechanism": {"type": "string", "description": "a brief mechanism id, or hook / outro"},
            "narration": {"type": "string"},
            "title": {"type": "string", "description": "big step title, 1-2 words, or empty"},
            "stat": {"type": ["object", "null"], "properties": {
                "fact_id": {"type": "string"}, "display": {"type": "string", "description": "e.g. '2,500 °C'"}},
                "required": ["fact_id", "display"]},
            "fact_ids": {"type": "array", "items": {"type": "string"},
                         "description": "every fact this beat's narration relies on"},
            "visual": {"type": "string", "description": "what changes on screen, concretely"},
            "shot_type": {"type": "string", "enum": SHOT_TYPES},
            "seconds": {"type": "number"},
        }, "required": ["id", "mechanism", "narration", "title", "stat", "fact_ids", "visual", "shot_type",
                        "seconds"]}},
    },
    "required": ["beats"],
}


def inputs(run):
    return [run.path("brief.json"), run.path("facts.json")]


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.,%-]*", text))


def _numbers(text: str):
    """Numbers a viewer would hear as a claim: digits, and spelled numbers above four."""
    nums = [m.group(0) for m in re.finditer(r"\d[\d,.]*", text)]
    nums += [w for w in re.findall(r"[a-z]+", text.lower()) if w in NUMBER_WORDS]
    return nums


def _digits(s: str) -> str:
    return re.sub(r"[^\d]", "", s)


def check(script: dict, brief: dict, facts: dict) -> list[str]:
    errs = []
    beats = script.get("beats", [])
    by_id = {f["id"]: f for f in facts["facts"]}
    hi_beats = max(16, round(brief["target_seconds"] / 4))
    if not 8 <= len(beats) <= hi_beats:
        errs.append(f"use 8-{hi_beats} beats (got {len(beats)})")
    total_words = sum(word_count(b["narration"]) for b in beats)
    lo, hi = (brief["target_seconds"] * w / 60 for w in WPM)
    if not lo * 0.95 <= total_words <= hi * 1.03:
        errs.append(f"narration must total {lo:.0f}-{hi:.0f} words for {brief['target_seconds']} s at "
                    f"{WPM[0]}-{WPM[1]} wpm (got {total_words})")
    if beats:
        first = re.split(r"(?<=[.?!])\s", beats[0]["narration"].strip())[0]
        if word_count(first) > 14 or not ("?" in first or _numbers(first) or re.search(r"\d", first)):
            errs.append("beat 1's first sentence is the hook: at most 14 words, with a question or a surprising "
                        "number, landing in the first 1.5 s")
        last = beats[-1]["narration"].strip()
        if not last.endswith("?"):
            errs.append("the last beat must end with a question to the viewer (no 'comment below' wording)")
    for b in beats:
        n = b["narration"]
        if BANNED.search(n):
            errs.append(f"{b['id']}: never ask for comments, likes or follows; just ask the question")
        sentences = [s for s in re.split(r"(?<=[.?!])\s+", n.strip()) if s]
        if len(sentences) > 3 or word_count(n) > 40:
            errs.append(f"{b['id']}: one idea per beat (max 3 sentences, 40 words)")
        for sen in sentences:
            if TELEGRAM.search(sen) or (word_count(sen) <= 2 and b is not beats[-1]):
                errs.append(f"{b['id']}: '{sen}' reads like a label, not speech: say it as a full sentence "
                            "(no 'Word:' openers, no one- or two-word sentences)")
        for fid in b.get("fact_ids", []):
            if fid not in by_id:
                errs.append(f"{b['id']}: unknown fact_id '{fid}'")
        stat = b.get("stat")
        if stat:
            f = by_id.get(stat["fact_id"])
            if f is None:
                errs.append(f"{b['id']}: stat uses unknown fact_id '{stat['fact_id']}'")
            elif _digits(f["value"]) and _digits(f["value"])[:2] not in _digits(stat["display"]):
                errs.append(f"{b['id']}: stat '{stat['display']}' does not match fact value '{f['value']}'")
        used = [by_id[x] for x in b.get("fact_ids", []) + ([stat["fact_id"]] if stat else []) if x in by_id]
        pool = " ".join(f"{f['value']} {f['claim']} {f['quote']}" for f in used).lower()
        for num in _numbers(n):
            d = _digits(num)
            if d and d not in _digits(pool) and num.strip(".,") not in pool:
                errs.append(f"{b['id']}: the number '{num}' must come from a fact listed in fact_ids")
            elif not d and not used:
                errs.append(f"{b['id']}: '{num}' is a quantity: cite the fact it comes from in fact_ids")
    per = {}
    for b in beats:
        per[b["mechanism"]] = per.get(b["mechanism"], 0) + 1
    for m, n in per.items():
        if n > 3:
            errs.append(f"mechanism '{m}' has {n} beats: give each 1-3 beats and balance the time across them")
    for b in beats:
        if JARGON.search(b["narration"]):
            errs.append(f"{b['id']}: '{JARGON.search(b['narration']).group(0)}' is jargon a 12-year-old can't "
                        "follow: say it plainly")
    covered = {b["mechanism"] for b in beats}
    for m in brief["mechanisms"]:
        if m["id"] not in covered:
            errs.append(f"no beat explains mechanism '{m['id']}'")
    return errs


def run(run):
    brief = run.need("brief.json")
    facts = run.need("facts.json")
    kit = kits.KITS[brief["kit"]]
    fact_lines = "\n".join(f"- {f['id']}: {f['claim']} [value: {f['value']} {f['unit']}]" for f in facts["facts"])
    mech = "\n".join(f"- {m['id']}: {m['name']} ({kit['mechanisms'][m['id']]['explains']})"
                     for m in brief["mechanisms"])
    lo, hi = (brief["target_seconds"] * w / 60 for w in WPM)
    tr = kit.get("tracker")
    tracker_rule = ("\n- The camera holds on one cylinder in slow motion while you explain " +
                    ", ".join(tr["mechanisms"]) + ": give each of them one beat that says what the piston, the "
                    "valves and the gas are doing, and name the stroke in it (the on-screen tracker lights "
                    "up with your words).") if tr else ""
    prompt = f"""Write the script for "{brief['title']}" ({brief['topic']}), {brief['target_seconds']} s.
Angle: {brief['angle']}
Hook: {brief['hook']}
The 3D model on screen: {kit['subject']}.

Explain these mechanisms in this order (beat.mechanism = the id; extra beats use "hook" or "outro"):
{mech}

Verified facts you may use (cite each one a beat relies on in fact_ids; numbers only from here):
{fact_lines}

Rules:
- {lo:.0f} to {hi:.0f} words in total (spoken at {WPM[0]}-{WPM[1]} words per minute). 8-{max(16, round(brief['target_seconds'] / 4))} beats.
- Explain the whole machine from start to finish in the order above, every step, so a viewer could retell
  the full chain: where things come from, what happens, what it causes next.{tracker_rule}
- Beat 1 is the hook: its first sentence (max 14 words) has a question or a surprising number and lands in 1.5 s.
- Something visibly changes at least every 1.5 s: write visual intents that move (a cut opens, a valve snaps
  open, the spark fires, the camera dives in).
- One idea per beat, max 3 sentences, max 40 words. Each mechanism beat gets a 1-2 word step title (e.g. INTAKE).
- Spoken style: full flowing sentences, linked so each one leads into the next; no labels, colons or
  one-word sentences; contractions are fine.
- A curious 12-year-old must follow the cause and effect of every sentence: plain words, no unexplained
  jargon (no "TDC", "crank degrees", "thermal efficiency"); compare to everyday things when it helps.
- Give each mechanism 1-3 beats and balance the time across them; facts serve the explanation, not the
  other way round (skip a fact rather than add a beat for it).
- Put a stat (fact_id + short display text) on the beats where a number is the point; at most one per beat.
- The last beat asks the viewer a genuine question (no 'comment below', no 'like', no 'follow') and its visual
  returns to the opening view so the video loops seamlessly.
- Shot types: hero (whole machine, closed), peel (the cut opens), section (inside, mid), close (a detail),
  lengthwise (all cylinders), quarter (inside and outside together)."""
    notes = ""
    for attempt in range(3):
        out = llm.ask(SYSTEM, prompt + notes, SCHEMA, effort="high", label="cutaway_script")
        for i, b in enumerate(out["beats"]):
            b["id"] = f"b{i + 1:02d}"
            b["title"] = b.get("title", "").strip().upper()
        errs = check(out, brief, facts)
        if not errs:
            break
        log.warning("[script] attempt %d: %d problems: %s", attempt + 1, len(errs), "; ".join(errs[:6]))
        notes = ("\n\nYour previous draft broke these rules; fix every one and keep what worked:\n- "
                 + "\n- ".join(errs) + "\n\nPrevious draft:\n" + json.dumps(out, indent=1))
    out["errors"] = errs
    out["words"] = sum(word_count(b["narration"]) for b in out["beats"])
    run.save("script.json", out)


def validate(run):
    script = run.need("script.json")
    errs = check(script, run.need("brief.json"), run.need("facts.json"))
    if errs:
        raise StageError("script fails hard checks:\n- " + "\n- ".join(errs))
