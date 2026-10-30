"""
Rules every director plan obeys, whichever writer made it: the fixed-world plans (engine/director/plans/*.json,
checked against engine/director/worlds.py) and the stage plans of agents/stage_writer.py, which reuses the
advice filter and the word helpers.

    problems = validate(plan)        # [] when the plan obeys every rule
"""
import re

from engine.director.worlds import WORLDS

WORDS = (140, 162)      # ~58-62 s of narration at the measured ~2.55 words/s after pause tightening

ADVICE = re.compile(r"\b(you should|make sure|remember to|don't forget|never pump|always|tip|lesson:|"
                    r"keep (it|yours|your)|be sure|avoid)\b", re.I)


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
