"""
Evolution writer: scripts for "evolution" films, the escalating problem → solution format
("You've built a bridge. But the river gets wider. So you curve it. Wider still?...").

    python -m agents.evolution_writer                    # pick angle → research → write → render
    python -m agents.evolution_writer --no-render        # stop after the script (review it first)
    python -m agents.evolution_writer --angle "why the Golden Gate needs joints"
    python -m agents.evolution_writer --set bridge_evolution --preview

It reuses the showrunner's plumbing (Claude backend: subscription `claude -p` or the API, the
research cache in output/facts/, the hard checks, the history file) with its own house style,
rules and editor rubric. The set's spec (engine/sets/<set>_spec.py) is the action catalogue: the
writer can only order those actions, so every line has a matching shot.
"""
import argparse
import datetime
import json
import logging
import os
import re

from agents import llm
from config.paths import slug
from agents import showrunner as sr
from engine import sets

log = logging.getLogger("pipeline")

OPEN_MAX_WORDS = 18

EVO_STYLE = """You write narration for 55-75 second vertical 3D "EVOLUTION" videos (TikTok, Reels, Shorts):
one continuous 3D world seen from drone height, where a thing has to keep getting smarter because
the world keeps raising the bar. The viewer is the builder, addressed as "you".

The format, beat by beat:
- THE OPENING (beat 1): the simplest version, already built, in one plain line in the second
  person ("You've built a bridge: a few planks over a stream."). Concrete, calm, no question, no
  "Did you know". It sets up the ladder.
- PROBLEM BEATS: a NEW LOAD OR NEED arrives in one short line ("Then a wagon of stone rolls on.",
  "Then the railway comes.", "But summer comes."), then the real physical reason the current design
  can't handle it, in plain words. Short. A little ominous. Vary the refrain; never the same opener
  twice in a row. Never invent a cause the model facts don't give (a river does not widen by itself).
- CAUSAL CHAIN: every fix must answer exactly the failure just shown, and its "why it works" line
  must name that link (the planks snapped because the bottom stretched; an arch only squeezes).
  A viewer who misses one beat must still see why each new bridge exists.
- SOLUTION BEATS start with "So you..." (or a close variation) and name the new design, then say
  WHY it works in ONE memorable, quotable sentence ("Push a square and it folds; a triangle
  can't."). Name what the viewer SEES on screen (stones, triangles, cables, the white drawings).
- RHYTHM: problem, fix, problem, fix: escalation. Each beat answers the last and sets up the next.
  Contractions, short sentences, punchy but full sentences (no telegram fragments as a default).
- CONCRETE: real numbers people can picture, only from the model facts or the fact sheet.
- PAYOFF: the last beat lands the most jaw-dropping real-world fact (the biggest one ever built,
  the famous failure) and ends with a short closing question to the viewer (at most 12 words,
  ends with "?"): an opinion or a guess they will want to answer. Never mention comments, likes,
  following or subscribing, and never a yes/no that kills the thread.
- SYNC: each beat's words describe what its action shows on screen.
- Spoken English only: no emojis, no markdown, no stage directions, digits are fine."""


def _rules(set_id):
    sp = sets.spec(set_id)
    lo, hi = sr.target_words()
    wps = sr.words_per_second()
    pairs = "; ".join(f"{p} then {s}" for p, s in getattr(sp, "ANSWERS", {}).items())
    return f"""STRUCTURE RULES (the renderer enforces them):
- The actions, exactly once each, in this order: {' → '.join(sp.STAGE_ORDER)}.
- One action per beat. A problem may share ONE beat with the fix that answers it ("actions":
  ["heat", "expansion_joint"]) when both lines are short. Problem/fix pairs: {pairs}.
- A beat needs enough words for what it shows: at least (sum of its actions' minimum seconds) x
  {wps} x 0.75 words. No beat over 32 words. Opening <= {OPEN_MAX_WORDS} words.
- Word budget: {lo}-{hi} words in total (~{wps} words/s).
- overlay: optional 2D sticker for that beat. type "stat" = a number that counts up (value like
  "120 m", text like "river width": a REAL measurement only); "label" = a short badge naming a real
  idea, no numbers (e.g. "Cables only pull"). Use "none" on most beats, at most 5 stickers, never
  on the opening.
- Numbers must match the model facts: what is ON SCREEN is the model."""


# ------------------- 1. angle -------------------

ANGLE_SCHEMA = sr._obj({
    "candidates": {"type": "array", "items": sr._obj({
        "title": sr.S, "angle": sr.S, "opening_line": sr.S, "payoff": sr.S,
        "curiosity": sr.I, "visual_fit": sr.I, "novelty": sr.I, "shareability": sr.I})},
    "best": sr.I,
})


def pick_angle(set_id, forced=None):
    used = [h.get("title", "") + " | " + h.get("angle", "") for h in sr._history() if h.get("set") == set_id][-30:]
    prompt = f"""Pick today's angle for this evolution video.

{sr._set_brief(set_id)}

Already published with this set (do NOT repeat these angles):
{chr(10).join('- ' + u for u in used) or '- (nothing yet)'}

{'The producer asked for this angle; develop it: ' + forced if forced else ''}

Brainstorm 6 distinct ANGLES for telling this same ladder: what the story is really about (why
every bridge looks different, the hidden fixes nobody notices, the famous failures behind each
rule...), a working title, the opening line (second person, at most {OPEN_MAX_WORDS} words), the
payoff, and honest 1-10 scores for curiosity, visual_fit, novelty and shareability. Set `best` to
the index of the strongest."""
    out = llm.ask(EVO_STYLE, prompt, ANGLE_SCHEMA, effort="medium")
    cands = out["candidates"]
    best = cands[max(0, min(out["best"], len(cands) - 1))]
    best["set"] = set_id
    best["hook_line"] = best["opening_line"]                  # research() verifies this line
    log.info(f"[evolution] angle: {best['title']} | opening: {best['opening_line']}")
    return best


# ------------------- 2. write, critique, revise -------------------

CRITIQUE_SCHEMA = sr._obj({
    "scores": sr._obj({"opening": sr.I, "clarity": sr.I, "escalation": sr.I, "problem_solution": sr.I,
                       "accuracy": sr.I, "pacing": sr.I, "visual_sync": sr.I, "learn": sr.I}),
    "problems": {"type": "array", "items": sr.S},
    "line_edits": {"type": "array", "items": sr.S},
    "verdict": {"type": "string", "enum": ["ship", "revise"]},
})


def write_script(topic, facts, previous=None, critique=None):
    set_id = topic["set"]
    prompt = f"""{sr._set_brief(set_id)}

{_rules(set_id)}

TITLE: {topic['title']}
ANGLE: {topic['angle']}
OPENING IDEA: {topic['opening_line']}
PAYOFF IDEA: {topic['payoff']}

FACT SHEET (verified research):
{facts}
"""
    if previous:
        prompt += f"""
YOUR PREVIOUS DRAFT:
{json.dumps(previous, ensure_ascii=False, indent=1)}

THE EDITOR'S NOTES (fix every one; keep what works):
{json.dumps(critique, ensure_ascii=False, indent=1)}

Write the improved script."""
    else:
        example = sr._tone_example(set_id)
        if example:
            prompt += ("\nTONE EXAMPLE: a reference script for this same set. Match its rhythm, do NOT reuse "
                       f"its lines; beat it.\n{example}\n")
        prompt += "\nWrite the script. Every beat must earn its place."
    return llm.ask(EVO_STYLE, prompt, sr.SCRIPT_SCHEMA, effort="high")


def critique(script, topic, facts, hard_problems):
    prompt = f"""You are the channel's head editor. Grade this evolution script ruthlessly (1-10 each):
opening (calm, concrete, makes you want the next step), clarity (a 12-year-old follows every beat),
escalation (each problem raises the stakes; refrains varied), problem_solution (each failure names
its REAL cause, a new load or need, never "the river gets wider", and the next fix answers exactly
that failure and says why it works; score 4 or less if any step's logic doesn't follow), accuracy (every claim
matches the fact sheet or model facts), pacing, visual_sync (words match what each action shows),
learn (would a curious adult say "I didn't know that!").

{sr._set_brief(topic['set'])}

FACT SHEET:
{facts}

SCRIPT:
{json.dumps(script, ensure_ascii=False, indent=1)}

Automatic checks found: {hard_problems or 'nothing'}

List concrete problems and line edits (quote the line, give the better line). verdict = "ship"
only if every score is {sr.PASS_SCORE}+ and there are no factual errors or rule breaks."""
    return llm.ask(EVO_STYLE, prompt, CRITIQUE_SCHEMA, effort="medium")


def hard_checks(script, set_id):
    """The showrunner's checks (actions, word budget, stickers, closing question), with the
    evolution opening rule instead of the 13-word hook rule."""
    problems = [p for p in sr.hard_checks(script, set_id) if not p.startswith("hook is ")]
    beats = script["beats"]
    if beats and len(beats[0]["text"].split()) > OPEN_MAX_WORDS:
        problems.append(f"opening is {len(beats[0]['text'].split())} words; max {OPEN_MAX_WORDS}")
    stickers = sum(1 for b in beats if (b.get("overlay") or {}).get("type", "none") != "none")
    if stickers > 5:
        problems.append(f"{stickers} stickers; max 5")
    return problems


def develop(topic, facts):
    script = write_script(topic, facts)
    problems = hard_checks(script, topic["set"])
    review = critique(script, topic, facts, problems)
    log.info(f"[evolution] draft: {json.dumps(review['scores'])} | hard problems: {len(problems)}")
    if not sr._ships(review, problems):
        fixed = write_script(topic, facts, previous=script, critique={"automatic_checks": problems, **review})
        fixed_problems = hard_checks(fixed, topic["set"])
        log.info(f"[evolution] revision: hard problems: {fixed_problems or 0}")
        if not fixed_problems or len(fixed_problems) < len(problems):
            script, problems = fixed, fixed_problems
    if problems:
        raise RuntimeError(f"no renderable script: {problems}")
    return script, review


# ------------------- 3. film JSON + run -------------------

def to_film(script, topic, facts, review=None):
    sp = sets.spec(topic["set"])
    beats = []
    for b in script["beats"]:
        acts = sp.beat_actions(b)
        beat = {"id": "+".join(acts), "action": acts[0], "text": b["text"].strip()}
        if len(acts) > 1:
            beat["actions"] = acts
        ov = b.get("overlay") or {}
        if ov.get("type") == "stat" and ov.get("value"):
            beat["overlay"] = {"type": "stat", "value": ov["value"], "text": ov.get("text", "")}
        elif ov.get("type") == "label" and ov.get("text") and not re.search(r"\d", ov["text"]):
            beat["overlay"] = {"type": "label", "text": ov["text"]}
        beats.append(beat)
    return {"title": script["title"], "set": topic["set"], "format": "evolution", "voice": "energetic",
            "captions": "phrase", "music": "synth", "beat_pause": 0.35, "tail": 1.5, "beats": beats,
            "cta": sr.closing_question(beats[-1]["text"]) if beats else None,
            "meta": {"angle": topic["angle"], "caption": script.get("caption", ""),
                     "hashtags": script.get("hashtags", []), "facts": facts, "review": review,
                     "created": datetime.datetime.now().isoformat(timespec="seconds"),
                     "model": llm.CODEX_MODEL if llm.active_backend() == "codex" else llm.CLI_MODEL}}


def run(angle=None, set_id=None, render=True, preview=False):
    set_id = set_id or sets.EVOLUTION[0]
    topic = pick_angle(set_id, forced=angle)
    facts = sr.research(topic)
    script, review = develop(topic, facts)
    film = to_film(script, topic, facts, review)
    os.makedirs(sr.FILMS_DIR, exist_ok=True)
    name = f"{datetime.date.today():%Y%m%d}_{slug(script['title'])}"
    path = os.path.join(sr.FILMS_DIR, f"{name}.json")
    json.dump(film, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    log.info(f"[evolution] script saved: {path}")
    for b in film["beats"]:
        log.info(f"   [{b['id']:>24}] {b['text']}")
    hist = sr._history()
    hist.append({"title": script["title"], "angle": topic["angle"], "hook": film["beats"][0]["text"],
                 "set": set_id, "film": path, "date": datetime.date.today().isoformat()})
    json.dump(hist, open(sr.HISTORY, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if not render:
        return path
    from engine.make_film import produce
    return produce(argparse.Namespace(film=path, reuse_voice=False, preview=preview, frames="", remix=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Write and render an evolution (problem → solution) film.")
    ap.add_argument("--angle", default=None, help="develop this angle instead of choosing one")
    ap.add_argument("--set", default=None, help=f"evolution set (default {sets.EVOLUTION[0]})")
    ap.add_argument("--no-render", action="store_true", help="stop after writing the script")
    ap.add_argument("--preview", action="store_true", help="render preview stills instead of the full film")
    a = ap.parse_args()
    print(run(angle=a.angle, set_id=a.set, render=not a.no_render, preview=a.preview))
