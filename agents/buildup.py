"""
BUILD-UP format for the explainer route (--source explainer), the @youbuiltit structure:

    "If you <crudest version>, you have a <thing>. But <real problem>, so <real fix>. This is a
     <part name>. But ... so ... Add <finishing touches>. Congratulations, you've built a <thing>."

The viewer builds the thing in their head from its dumbest working version, fixing one real
problem at a time in the physical order of the build. There is no hook staged on the finished
build and no rewind: the film starts on the first build step (rendered hookless by
engine/films/cutaway_film.py, film JSON "format": "buildup").

agents/showrunner.py asks this module for the voice, rules, checks, editor notes and tone example
whenever the set is a registered explainer set (engine/sets EXPLAINER) and EXPLAINER_FORMAT is
"buildup" (the default; EXPLAINER_FORMAT=hook brings back the old hook + rewind explainer).
"""
import os
import re

from engine import sets

FORMAT = "buildup"
OPEN_RE = re.compile(r"^\s*if you\b", re.I)
HAVE_RE = re.compile(r"\byou(?:'ve| have)(?: got)?\s+(?:a|an|the|your)\b|\byou(?:'ve| have) (?:just )?(?:made|got)\b", re.I)
END_RE = re.compile(r"congratulations,?\s+you(?:'ve| have)\s+(?:just\s+)?built\b[^.!?]*[.!]?\s*$", re.I)
NAME_RE = re.compile(r"\b(?:this|that) is (?:a|an|the|called)\b|\bit'?s called\b|\bcalled an? \b", re.I)
OPEN_MAX_WORDS = 34
BEAT_MAX_WORDS = 32
MAX_STICKERS = 4
HERO_NAMES = re.compile(r"\bMax\b")

STYLE = """You write narration for 55-75 second vertical 3D cutaway BUILD-UP explainers (TikTok, Reels,
Shorts), the format of @youbuiltit: the viewer builds the thing in their head, starting from the
crudest version that technically works and fixing one real problem at a time until it is the real thing.

THE FORMAT (follow it exactly):
- THE OPENING: the very first words of beat 1 are "If you". Give the crudest version that technically
  works, then "you have a <thing>". The shape: "If you dig a hole in your backyard and fill it with
  water, you have a pool." Concrete, physical, a little funny in its simplicity. Never a question,
  never "Did you know", never a statistic first.
- THE CHAIN: then problem, fix, problem, fix, in the physical order of the build. A problem starts with
  "But" (or "And" / "Then" for variety) and is a real, specific failure of the version so far; its fix
  starts with "so" and is the real engineering answer that solves exactly that failure. Sentences flow
  into each other with but / so / and, spoken like one confident explanation that never stops moving.
- NAME IT: right after a fix, give the part its real name in a short sentence: "This is a relief
  valve." Name at least two parts in the video.
- ONE PICTURE PER HARD IDEA: when a principle is abstract, one short everyday comparison ("like a
  seesaw").
- ONE HUMAN DETAIL: one year, inventor, record or picturable number from the fact sheet, placed where
  it lands hardest.
- THE FINISHING TOUCHES: the last beat races through two or three final details ("Add tiles, a ladder
  and a light"), at least one of them a surprising true detail.
- THE ENDING: the very last sentence is exactly "Congratulations, you've built a <thing>." (or "an
  <thing>"). Nothing after it. No question to the viewer, no call to action.
- VOICE: second person ("you"), present tense, plain words a 12-year-old gets, contractions, no
  character names, no "we", no "in this video", at most one exclamation mark. Humour only when it
  costs no information.
- CONCRETE AND TRUE: numbers only from the model facts or the fact sheet.
- SYNC: each beat's words describe what that beat's action shows on screen (the action catalogue).
- Spoken English only: no emojis, no markdown, no stage directions, digits are fine."""

DIRECTIONS = {
    "plain": "Calm and crisp: each fix lands as a small 'oh, that's clever' moment. No jokes needed.",
    "numbers": "Numbers-forward: every problem or fix carries one picturable number or comparison.",
    "history": "Give the single best human story (an inventor, a famous failure, a year) its own moment.",
}

TOPIC_NOTE = """

These are BUILD-UP explainers (no characters): the hook line is the OPENING sentence and must start
with "If you" and end with "you have a <thing>" (at most 20 words), and hook_action is the FIRST build
action (the film starts on the first build step; there is no hook staged on the finished build)."""

CRITIQUE_NOTE = """

FORMAT NOTE (build-up explainer, overrides anything above that assumes a hook, a hero or a question):
"hook" grades the "If you ..., you have a ..." opening (concrete, crude, instantly clear); "fun" grades
rhythm and the satisfaction of each fix (the but / so chain, named parts, one great human detail), not
jokes; "story_flow" requires every fix to answer exactly the problem just named. The script must end
with "Congratulations, you've built a <thing>." and must NOT end with a question."""


def enabled(set_id) -> bool:
    if (os.getenv("EXPLAINER_FORMAT") or FORMAT).strip().lower() != FORMAT:
        return False
    return set_id in list(getattr(sets, "EXPLAINER", []))


def _beat_actions(sp, beat):
    return list(getattr(sp, "beat_actions", lambda b: list(b.get("actions") or [b.get("action")]))(beat))


def _order(sp):
    return list(getattr(sp, "BUILD_ORDER", None) or getattr(sp, "STORY_ORDER", None) or [])


def validate(sp, beats) -> list:
    """The set's action rules without the hook / rewind opening: the build in order, explainers after
    their prerequisite, an outro only at the end."""
    errs = []
    for k, b in enumerate(beats):
        n = len(_beat_actions(sp, b))
        if not 1 <= n <= 4:
            errs.append(f"beat {k + 1} has {n} actions; 1-4 allowed")
    acts = [a for b in beats for a in _beat_actions(sp, b)]
    unknown = [a for a in acts if a not in sp.ACTIONS]
    if unknown:
        errs.append(f"unknown actions: {unknown}")
    banned = [a for a in acts if sp.ACTIONS.get(a, {}).get("kind") in ("hook", "rewind")]
    if banned:
        errs.append(f"no hook or rewind in a build-up explainer: remove {banned}; beat 1 is the first build step")
    order = _order(sp)
    build = [a for a in acts if sp.ACTIONS.get(a, {}).get("kind") in ("build", "story", "fail", "fix")]
    if order and build != order:
        errs.append(f"build actions must appear exactly once each, in order: {order} (got {build})")
    if order and acts and acts[0] != order[0]:
        errs.append(f"beat 1 must start with the first build action '{order[0]}'")
    for i, a in enumerate(acts):
        spec = sp.ACTIONS.get(a, {})
        if spec.get("kind") == "explain" and spec.get("after") not in acts[:i]:
            errs.append(f"'{a}' must come after '{spec.get('after')}'")
        if spec.get("kind") == "outro" and i != len(acts) - 1:
            errs.append(f"outro '{a}' must be the last beat")
    if len(set(acts)) != len(acts):
        errs.append("each action may be used once")
    return errs


def rules(set_id, words_per_second, budget) -> str:
    sp = sets.spec(set_id)
    order = _order(sp)
    explain = "; ".join(f"{k} after {v['after']}" for k, v in sp.ACTIONS.items() if v.get("kind") == "explain")
    outros = ", ".join(k for k, v in sp.ACTIONS.items() if v.get("kind") == "outro")
    lo, hi = budget
    return f"""STRUCTURE RULES (the renderer enforces them):
- No hook and no rewind. Beat 1 plays the first build action ({order[0] if order else 'the first step'}) and
  its narration starts with "If you" and says "you have a <thing>".
- Then these build actions exactly once each, in this order: {' → '.join(order)}.
- Optional explainer actions after their prerequisite: {explain or 'none'}.{(' Optional outro (last beat only): ' + outros + '.') if outros else ''}
- A beat plays ONE action, or a quick MONTAGE of 2-4 consecutive actions ("actions": ["rebar",
  "shotcrete"]) to race through steps that are not the point.
- A beat needs enough words for what it shows: at least (sum of its actions' minimum seconds) x
  {words_per_second} x 0.75 words. Beat 1 at most {OPEN_MAX_WORDS} words, every other beat at most {BEAT_MAX_WORDS}. 8-15 beats.
- Word budget: aim for {hi - 37}-{hi - 12} words and count before returning; the hard range is {lo}-{hi}.
- The last sentence of the last beat is "Congratulations, you've built a <thing>." No question anywhere
  at the end.
- overlay: optional 2D sticker. type "stat" = a REAL number that counts up (value "50 tons", text "of
  soil"); "label" = a short badge naming a part, no numbers. "none" on most beats, at most
  {MAX_STICKERS}, never on beat 1, never repeating a label the action already shows in the scene.
- Numbers must match the model facts: what is ON SCREEN is the model."""


def checks(script, set_id, words_per_second, budget) -> list:
    sp = sets.spec(set_id)
    beats = script.get("beats", [])
    problems = validate(sp, beats)
    for k, b in enumerate(beats):
        text = (b.get("text") or "").strip()
        n = len(text.split())
        if not text:
            problems.append(f"beat {k + 1} has no narration")
            continue
        acts = _beat_actions(sp, b)
        need = int(sum(sp.ACTIONS.get(a, {}).get("seconds", (0, 0))[0] for a in acts) * words_per_second * 0.75)
        if n < need:
            problems.append(f"beat {k + 1} {acts} has {n} words; it needs at least {need} to show its actions")
        cap = OPEN_MAX_WORDS if k == 0 else BEAT_MAX_WORDS
        if n > cap:
            problems.append(f"beat {k + 1} has {n} words; max {cap}")
        if HERO_NAMES.search(text):
            problems.append(f"beat {k + 1} names a character; build-up explainers have no characters")
    words = sum(len((b.get("text") or "").split()) for b in beats)
    lo, hi = budget
    if not lo <= words <= hi:
        problems.append(f"total narration is {words} words; it must be {lo}-{hi}")
    if beats:
        first = beats[0].get("text") or ""
        if not OPEN_RE.match(first):
            problems.append('beat 1 must start with "If you" (the crudest version that works)')
        opening = " ".join(re.split(r"(?<=[.!?])\s+", first.strip())[:2])
        if not HAVE_RE.search(opening):
            problems.append('the opening must say what you have: "..., you have a <thing>."')
        last = (beats[-1].get("text") or "").strip()
        if last.endswith("?"):
            problems.append("no closing question: the last sentence is \"Congratulations, you've built a <thing>.\"")
        elif not END_RE.search(last):
            problems.append("the script must end with \"Congratulations, you've built a <thing>.\"")
        if (beats[0].get("overlay") or {}).get("type", "none") != "none":
            problems.append("no sticker on beat 1")
    full = " ".join((b.get("text") or "") for b in beats)
    if len(NAME_RE.findall(full)) < 1:
        problems.append('name the real parts: at least one "This is a <part>." after a fix')
    if len(re.findall(r"\bbut\b", full, re.I)) < 3:
        problems.append('the chain needs at least 3 "But ..., so ..." problem/fix steps')
    stickers = sum(1 for b in beats if (b.get("overlay") or {}).get("type", "none") != "none")
    if stickers > MAX_STICKERS:
        problems.append(f"{stickers} stickers; max {MAX_STICKERS}")
    return problems


# Reference scripts in this format, written for our own sets (the writer matches the shape, never the
# lines). Sets without one get the pool example as a structure example.
EXAMPLES = {
    "pool": [
        ("dig", "If you dig a hole in your backyard and fill it with water, you have a pool. But dirt drinks "
                "water, so it needs a concrete shell."),
        ("layers", "Under the lawn: topsoil, clay, sand, and groundwater."),
        ("gravel", "But concrete on wet dirt cracks, so the floor gets a bed of gravel to drain it."),
        ("valve", "And rising groundwater can push an empty pool right out of the ground. So the floor gets a "
                  "valve that lets it in. This is a relief valve."),
        ("pipes", "But still water turns green, so pipes run from a drain and a skimmer to a pump."),
        ("rebar+shotcrete", "But concrete cracks when it's pulled, so a steel grid goes in first, and concrete "
                            "is fired onto it from a hose. This is shotcrete."),
        ("cure", "Then you keep it wet for days, because concrete doesn't dry, it cures."),
        ("finish", "But raw concrete scrapes skin, so it gets smooth plaster, tiles and a stone edge."),
        ("fill", "Now fill it: twenty thousand litres, about twenty tons of water."),
        ("flow", "A pump pushes it through a sand filter and back, the whole pool every six hours."),
        ("glamour", "Add a ladder and some sun. Congratulations, you've built a pool."),
    ],
}


def tone_example(set_id) -> str:
    lines = EXAMPLES.get(set_id)
    if lines:
        return "\n".join(f"[{a}] {t}" for a, t in lines)
    return ("(a build-up script for a DIFFERENT subject, a backyard pool: copy the structure, not the content)\n"
            + "\n".join(f"[{a}] {t}" for a, t in EXAMPLES["pool"]))


def film_extras() -> dict:
    """What a build-up film JSON carries on top of the showrunner's fields."""
    return {"format": FORMAT, "cta": None, "tail": 1.2}
