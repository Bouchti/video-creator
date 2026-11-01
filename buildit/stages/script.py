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

from ..kit import vocab
from ..runner import StageError
from .topic import STYLE

log = logging.getLogger("pipeline")
WPM = (136, 152)     # an unhurried read: the viewer has time to look at each step
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


def check(script: dict, brief: dict, facts: dict) -> list[str]:
    errs = []
    beats = script.get("beats", [])
    by_id = {f["id"]: f for f in facts["facts"]}
    target = brief["target_seconds"]
    lo, hi = (target * w / 60 for w in WPM)
    total = sum(word_count(b["narration"]) for b in beats)
    if not lo * 0.95 <= total <= hi * 1.03:
        errs.append(f"narration must total {lo:.0f}-{hi:.0f} words for {target} s (got {total})")
    if not 10 <= len(beats) <= max(22, target // 3):
        errs.append(f"use 10-{max(22, target // 3)} beats (got {len(beats)})")
    if beats and beats[0]["role"] != "hook":
        errs.append("beat 1 is the hook: an everyday object doing something surprising")
    if beats and word_count(beats[0]["narration"]) > 16:
        errs.append("the hook beat must land in 2 s: at most 16 words")
    fixes = [b for b in beats if b["role"] == "fix"]
    if not 4 <= len(fixes) <= 8:
        errs.append(f"the chain needs 4-8 'fix' beats, one per added part (got {len(fixes)})")
    if beats and beats[-1]["role"] != "outro":
        errs.append("the last beat is the outro: the complete machine running, then a question to the viewer")
    if beats and not beats[-1]["narration"].strip().endswith("?"):
        errs.append("end the outro on a question to the viewer (it invites comments), ending with '?'")
    you = sum(1 for b in beats if re.search(r"\byou(r|'re|'ll|'d)?\b", b["narration"], re.I))
    if beats and you < 0.4 * len(beats):
        errs.append(f"talk to the viewer: say 'you' in at least 40% of beats (now {you}/{len(beats)})")
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


def run(run):
    b = run.need("brief.json")
    facts = run.need("facts.json")
    fact_lines = "\n".join(f"- {f['id']}: {f['claim']} [value: {f['value']} {f['unit']}]" for f in facts["facts"])
    chain = "\n".join(f"{i + 1}. analogy: {s['analogy']} | problem: {s['problem']} | add: {s['part_added']} "
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
- {lo:.0f}-{hi:.0f} words in total. 10-22 beats. Beat 1 (role hook) lands in 2 s: max 16 words.
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
- visual: what moves on screen, concretely (it becomes the storyboard)."""
    notes = ""
    for attempt in range(3):
        out = llm.ask("You write warm, playful narration for 3D machine explainers.", prompt + notes, SCHEMA,
                      effort="high", label="buildit_script")
        for i, beat in enumerate(out["beats"]):
            beat["id"] = f"b{i + 1:02d}"
        errs = check(out, b, facts)
        if not errs:
            break
        log.warning("[script] attempt %d: %s", attempt + 1, "; ".join(errs[:6]))
        notes = ("\n\nYour previous draft broke these rules; fix every one and keep what worked:\n- " +
                 "\n- ".join(errs) + "\n\nPrevious draft:\n" + json.dumps(out, indent=1))
    out["errors"] = errs
    out["words"] = sum(word_count(x["narration"]) for x in out["beats"])
    run.save("script.json", out)


def validate(run):
    s = run.need("script.json")
    errs = check(s, run.need("brief.json"), run.need("facts.json"))
    if errs:
        raise StageError("script fails hard checks:\n- " + "\n- ".join(errs))
