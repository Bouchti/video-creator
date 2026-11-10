"""
Stage 3 - script.json: the analogy chain as narration beats (hook, then problem / fix / payoff loops, then the
finished machine), each with the part it adds, its label pill and how it is delivered. Hard checks in code; the
model rewrites until they pass (2 rewrites).
"""
from __future__ import annotations

import json
import logging
import re

from agents import llm
from cutaway.stages.script import _digits, _numbers, word_count

from .. import review as review_mod
from ..kit import vocab
from ..runner import StageError
from .topic import STYLE

log = logging.getLogger("pipeline")
VISUAL_WORDS = 18    # a beat's visual note: one line, one change (the storyboard plans the rest)
SCRIPT_REVIEWS = 3   # story-editor reviews of the text before a word is voiced
WPM = (140, 155)     # words a minute of FILM, not of speech: the read is brisk, the gaps let each step land
ROLES = ["hook", "problem", "fix", "payoff", "outro"]
# chatterbox (exaggeration, cfg_weight): high exaggeration + low cfg = an energetic, quick read (the calm
# LibriVox-style read was called "lazy"); nothing below 0.6 any more
DELIVERY = {"hook": (0.85, 0.3), "punchy": (0.8, 0.3), "lively": (0.72, 0.35), "calm": (0.62, 0.4),
            "question": (0.78, 0.32)}

SCHEMA = {"type": "object", "properties": {"beats": {"type": "array", "items": {"type": "object", "properties": {
    "role": {"type": "string", "enum": ROLES},
    "step": {"type": "integer", "description": "chain step this beat belongs to (0 = hook)"},
    "narration": {"type": "string"},
    "part_added": {"type": "string", "description": "kit part type this beat brings on screen, or ''",
                   "enum": [""] + list(vocab.PARTS)},
    "label": {"type": ["object", "null"], "properties": {
        "text": {"type": "string", "description": "pill text, 1-4 words, uppercase-able"},
        "variant": {"type": "string", "enum": vocab.LABEL_VARIANTS},
        "fact_id": {"type": ["string", "null"]}}, "required": ["text", "variant", "fact_id"]},
    "fact_ids": {"type": "array", "items": {"type": "string"}},
    "visual": {"type": "string", "description": "what visibly happens, concretely"},
    "delivery": {"type": "string", "enum": list(DELIVERY)},
}, "required": ["role", "step", "narration", "part_added", "label", "fact_ids", "visual", "delivery"]}}},
    "required": ["beats"]}


def inputs(run):
    return [run.path("brief.json"), run.path("facts.json")]


def max_beats(target_seconds: float) -> int:
    """Beats a film of this length can carry at an unhurried ~4.5 s each."""
    return max(9, round(target_seconds / 5.5))


def max_steps(target_seconds: float) -> int:
    """Problem -> fix cycles a film of this length can carry without cramming (one per ~15 s)."""
    return max(3, min(8, round(target_seconds / 15)))


def check(script: dict, brief: dict, facts: dict) -> list[str]:
    errs = []
    beats = script.get("beats", [])
    by_id = {f["id"]: f for f in facts["facts"]}
    target = brief["target_seconds"]
    lo, hi = (target * w / 60 for w in WPM)
    total = sum(word_count(b["narration"]) for b in beats)
    if not lo * 0.95 <= total <= hi * 1.03:
        errs.append(f"narration must total {lo:.0f}-{hi:.0f} words for {target} s (got {total})")
    if not 9 <= len(beats) <= max_beats(target):
        errs.append(f"use 9-{max_beats(target)} beats for a {target} s film (got {len(beats)}): fewer, fuller beats")
    if beats and beats[0]["role"] != "hook":
        errs.append("beat 1 is the hook: an everyday object doing something surprising")
    if beats and word_count(beats[0]["narration"]) > 16:
        errs.append("the hook beat must land in 2 s: at most 16 words")
    fixes = [b for b in beats if b["role"] == "fix"]
    for x in beats:
        if len(str(x.get("visual", "")).split()) > VISUAL_WORDS:
            errs.append(f"{x.get('id')}: the visual note is {len(str(x.get('visual', '')).split())} words; one line "
                        f"(max {VISUAL_WORDS}) naming the ONE thing that changes")
    last = str(beats[-1].get("narration", "")) if beats else ""
    q = last[last.rfind(".", 0, max(0, len(last) - 1)) + 1:] if "?" in last else ""
    if q and (len(q.split()) < 9 or re.search(r"what else|did you know|comment|can you think|guess what|any idea",
                                                q, re.I)):
        errs.append("the closing question is generic: make it a creative, counter-intuitive puzzle the film lets the "
                    "viewer answer (e.g. would an open fridge door cool the kitchen?)")
    added = {str(x.get("part_added") or "") for x in fixes}
    added |= {"nozzle"} if "capillary" in added else set()
    missing = [st["part_added"] for st in brief.get("chain", []) if not added & set(st.get("kit_parts", []))]
    if missing:
        errs.append(f"every chain step needs its fix beat; missing: {missing}")
    if not 3 <= len(fixes) <= 8:
        errs.append(f"the chain needs 3-8 'fix' beats, one per added part (got {len(fixes)})")
    if beats and beats[-1]["role"] != "outro":
        errs.append("the last beat is the outro: the complete machine running, then a question to the viewer")
    if beats and not beats[-1]["narration"].strip().endswith("?"):
        errs.append("end the outro on a question to the viewer (it invites comments), ending with '?'")
    you = sum(1 for b in beats if re.search(r"\byou(r|'re|'ll|'d)?\b", b["narration"], re.I))
    if beats and you < 0.3 * len(beats):
        errs.append(f"talk to the viewer: say 'you' in at least 30% of beats (now {you}/{len(beats)})")
    for b in beats:
        bid = b.get("id", "?")
        for sen in re.split(r"(?<=[.?!])\s+", b["narration"].strip()):
            if word_count(sen) > 16:
                errs.append(f"{bid}: '{sen[:40]}...' is long: max 16 words a sentence")
        used = [by_id[x] for x in b.get("fact_ids", []) if x in by_id]
        for x in b.get("fact_ids", []):
            if x not in by_id:
                errs.append(f"{bid}: unknown fact_id '{x}'")
        pool = " ".join(f"{f['value']} {f['claim']} {f['quote']}" for f in used).lower()
        for num in _numbers(b["narration"]):
            d = _digits(num)
            if d and d not in _digits(pool) and num.strip(".,") not in pool:
                errs.append(f"{bid}: the number '{num}' must come from a fact listed in fact_ids")
        lb = b.get("label")
        if lb:
            if len(lb["text"].split()) > 4:
                errs.append(f"{bid}: label '{lb['text']}' is too long (max 4 words)")
            if re.search(r"\d", lb["text"]) and lb.get("fact_id") not in by_id:
                errs.append(f"{bid}: label '{lb['text']}' shows a number without a valid fact_id")
    return errs


def run(run, review_notes: str = ""):
    """`review_notes`: fixes from the pre-render review, when the narration itself must change."""
    b = run.need("brief.json")
    facts = run.need("facts.json")
    fact_lines = "\n".join(f"- {f['id']}: {f['claim']} [value: {f['value']} {f['unit']}]" for f in facts["facts"])
    chain = "\n".join(f"{i + 1}. analogy: {s['analogy']} (shown by: {s.get('prop') or 'the machine'}) | problem: {s['problem']} | add: {s['part_added']} "
                      f"(kit: {', '.join(s['kit_parts'])}, mounts: {s.get('slot') or '-'}) | payoff: {s['payoff']}"
                      for i, s in enumerate(b["chain"]))
    lo, hi = (b["target_seconds"] * w / 60 for w in WPM)
    prompt = f"""{STYLE}

Write the narration for "{b['title']}" ({b['topic']}), {b['target_seconds']} s, English.
Hook: {b['hook']}
Through-line object: {b['through_line']}
Chain:
{chain}
Ends on: {b['machine']}

Verified facts (numbers only from here; cite them in fact_ids):
{fact_lines}

Rules:
- {lo:.0f}-{hi:.0f} words in total (leave room: the pictures need time too). 9-{max_beats(b['target_seconds'])} beats,
  about 4-5 s each; a payoff beat only where a change must be SEEN. Beat 1 (role hook) lands in 2 s: max 16 words.
  The ending gets room: the last fix, its payoff and the outro are not squeezed into the final seconds.
- Each chain step: a 'problem' beat (short, a mini cliffhanger: "But...", "Except..."), a 'fix' beat that adds one
  part (part_added = its kit part) which clicks into its real place on the {b.get('host', 'machine')}, and optionally a
  'payoff' beat where you SEE the effect (frost, heat, flow, spin). Last beat: role outro, the complete machine
  running, then ONE short question to the viewer that invites a comment (ends with "?").
- The hook's first sentence opens a curiosity gap in under 2 s (a surprising fact or sight, never "In this video").
- Talk to the viewer ("you"), short sentences (max 16 words), playful and concrete; name a part only when it
  appears; analogies simplify but are never wrong.
- label: the pill that names the new part or the key number of a beat (1-4 words, e.g. "COMPRESSOR",
  "+10", "-18 °C"), variant warn for danger/heat/force, air for air, cold for cold, done for the finished
  machine; a number on a label needs its fact_id. null when the beat needs no pill.
- delivery: hook for beat 1, punchy for problems, lively for fixes, calm for explanations, question for questions.
- visual: ONE line (max 18 words): the one thing that changes on screen in this beat, using ONLY what the 3D kit can show:
  its props ({', '.join(vocab.PROPS)}), the machine and its parts, and the kit's events (flows as coloured
  dashes, heat waves, frost, glow, parts running, labels). Every analogy is SHOWN by one of these props; never a
  person, a pool, a room, a wall, a meter or any object the kit does not have. If the chain's analogy cannot be
  shown that way, swap it for one with the same physics that can.
- EXPLAIN THE WHY, in plain words, at every step: what physically happens and why it works -- e.g. low
  pressure lets a liquid boil far below zero and boiling soaks up heat; squeezing a gas makes it hotter than the
  room so its heat can flow out; giving up that heat turns the gas back into liquid; a narrow tube drops the
  pressure so the liquid can boil cold again; a thermostat switches the motor off when it is cold enough. The
  viewer must finish the film able to explain the machine to a friend. Depth is the point, not a list of parts.
- The LAST line is a creative, counter-intuitive question the viewer can answer from the film but will want to
  argue about in the comments (e.g. "So if you leave the fridge door open on a hot day, does your kitchen get
  cooler -- or hotter?"). Never a generic one ("What else at home...?", "Did you know...?", "Comment below").
- ONE visible change per beat: a fix beat shows only its part flying in and clicking into place (its pipe joins
  as it lands); the flow starting, the motor running, frost or heat belong to the NEXT (payoff) beat. An analogy
  beat shows only its prop doing its one thing.
- Cover EVERY step of the chain (every part it adds, the control part such as a thermostat included): one fix
  beat per part, none dropped. One idea per beat; never pack an analogy, a new part and a flow change into one line.
- Numbers: say a fact's number only with its condition ("about minus twenty-three inside the coil", "around
  fifty degrees when the room is warm"), never as a universal value; no number beats a misleading one.
- Analogies are quick: ONE short sentence each (max 10 words), then straight back to the machine. The props
  are a flash of recognition, not a detour; most of the film is the machine.
- A change the viewer must SEE (a part switching off then on, frost forming, heat leaving) gets its own beat of
  at least 6 words, so it stays on screen long enough to read."""
    lessons = review_mod.lessons_text(run, review_mod.SCRIPT_ITEMS)
    if lessons:
        prompt += "\n\n" + lessons
    notes = ("\n\nThe review of the last version asked for these changes (keep what worked; previous draft:\n" +
             json.dumps(run.load("script.json", {}).get("beats", []), indent=1) + "):\n" + review_notes) \
        if review_notes else ""

    def write(notes):
        """A draft that passes the hard checks (the model rewrites up to twice)."""
        for attempt in range(3):
            out = llm.ask("You write warm, playful narration for 3D machine explainers.", prompt + notes, SCHEMA,
                          effort="high", label="buildit_script")
            for i, beat in enumerate(out["beats"]):
                beat["id"] = f"b{i + 1:02d}"
            errs = check(out, b, facts)
            if not errs:
                return out, errs
            log.warning("[script] attempt %d: %s", attempt + 1, "; ".join(errs[:6]))
            notes = ("\n\nYour previous draft broke these rules; fix every one and keep what worked:\n- " +
                     "\n- ".join(errs) + "\n\nPrevious draft:\n" + json.dumps(out, indent=1))
        return out, errs

    # then the story editor's panel reads it (hook, story, pacing, accuracy) BEFORE voice and render: below 4,
    # the draft is rewritten with the fixes; the best reviewed draft is kept
    out, errs = write(notes)
    best = None
    for rnd in range(SCRIPT_REVIEWS):
        if errs:
            break
        rv = review_mod.judge_script(run, out)
        out["review"] = rv
        sc = [s["score"] for s in rv["scores"].values()]
        if best is None or (min(sc), sum(sc)) >= best[0]:          # a tie goes to the later, more-fixed draft
            best = ((min(sc), sum(sc)), out)
        low = review_mod.low_items(rv["scores"])
        log.info("[script] review %d: %s", rnd + 1, {k: s["score"] for k, s in rv["scores"].items()})
        if not low:
            break
        review_mod.record_lessons(run, rv, "script")
        if rnd == SCRIPT_REVIEWS - 1:
            break
        fix = ("\n\nThe story editor scored your draft below the bar; rewrite it so every item reaches 4 "
               "(keep what works):\n" + "\n".join(f"- {k} {s}/5: {rv['scores'][k]['why']}" for k, s in low.items())
               + "\n" + "\n".join(f"- fix: {f}" for f in rv["fixes"]) +
               "\n\nYour draft:\n" + json.dumps({"beats": out["beats"]}, indent=1))
        out2, errs2 = write(fix)
        if not errs2:
            out, errs = out2, errs2
    if best is not None:
        out, errs = best[1], []
    out["errors"] = errs
    out["words"] = sum(word_count(x["narration"]) for x in out["beats"])
    run.save("script.json", out)


def validate(run):
    s = run.need("script.json")
    errs = check(s, run.need("brief.json"), run.need("facts.json"))
    if errs:
        raise StageError("script fails hard checks:\n- " + "\n- ".join(errs))
    low = review_mod.low_items(s.get("review", {}).get("scores", {}))
    if low:
        raise StageError(f"the story editor's panel still scores the script below 4 after {SCRIPT_REVIEWS} reviews: "
                         f"{low}\n" + "\n".join(f"- {k}: {s['review']['scores'][k]['why']}" for k in low))
