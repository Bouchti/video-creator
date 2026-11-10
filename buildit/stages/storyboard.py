"""
Stage 6 - storyboard.json: the whole video in the machine kit's vocabulary, every event keyed to the word that
says it: the host machine, the parts that mount in its slots (and the props on the stage), the pipes between
them, appear / run / flow / heat / frost / highlight... events, camera shots, label pills and sound cues. Checked
in code (buildit/kit/check.py, which first repairs what needs no judgement); the model rewrites until it passes.
`revise(run, notes)` re-plans with notes from the preview stage's visual check.
"""
from __future__ import annotations

import json
import logging

from agents import llm

from .. import review
from ..kit import check, hosts, vocab
from ..runner import StageError
from .topic import STYLE

log = logging.getLogger("pipeline")

SCHEMA = {"type": "object", "properties": {
    "machine": {"type": "object", "properties": {
        "host": {"type": "string", "enum": list(hosts.HOSTS)}}, "required": ["host"]},
    "parts": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"}, "type": {"type": "string", "enum": list(vocab.PARTS)},
        "size": {"type": "string", "enum": list(vocab.SIZES)},
        "color": {"type": ["string", "null"], "enum": vocab.COLORS + [None]},
        "mount": {"type": ["string", "null"], "description": "host slot for a machine part (null for a prop)"},
        "stage": {"type": ["string", "null"], "enum": vocab.STAGES + [None],
                  "description": "stage spot for a prop (null for a mounted part)"}},
        "required": ["id", "type", "size", "color", "mount", "stage"]}},
    "connections": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"}, "kind": {"type": "string", "enum": vocab.CONNECT},
        "from": {"type": "string", "description": "part.port"}, "to": {"type": "string", "description": "part.port"}},
        "required": ["id", "kind", "from", "to"]}},
    "events": {"type": "array", "items": {"type": "object", "properties": {
        "word": {"type": "integer"}, "do": {"type": "string", "enum": list(vocab.EVENTS)},
        "target": {"type": "string", "description": "part id, part.anchor, a connection id, or 'machine'"},
        "how": {"type": ["string", "null"]}, "from": {"type": ["string", "null"]},
        "to": {"type": ["string", "null"], "description": "heat_flow only: a part id or 'room'"},
        "speed": {"type": ["string", "null"], "enum": ["slow", "normal", "fast", "stop", None]},
        "value": {"type": ["number", "null"]}, "squeeze": {"type": ["number", "null"]},
        "kind": {"type": ["string", "null"]}, "on": {"type": ["boolean", "null"]},
        "driver": {"type": ["string", "null"]}}, "required": ["word", "do", "target"]}},
    "shots": {"type": "array", "items": {"type": "object", "properties": {
        "start_word": {"type": "integer"}, "frame": {"type": "string", "enum": vocab.FRAMES},
        "on": {"type": "array", "items": {"type": "string"}}, "move": {"type": "string", "enum": vocab.MOVES},
        "side": {"type": ["string", "null"], "enum": ["front", "back", None],
                 "description": "machine shots: film the front or the back of the machine"}},
        "required": ["start_word", "frame", "on", "move", "side"]}},
    "labels": {"type": "array", "items": {"type": "object", "properties": {
        "word": {"type": "integer"}, "until_word": {"type": "integer"}, "text": {"type": "string"},
        "variant": {"type": "string", "enum": vocab.LABEL_VARIANTS}, "anchor": {"type": "string"},
        "fact_id": {"type": ["string", "null"]}}, "required": ["word", "until_word", "text", "variant", "anchor", "fact_id"]}},
    "sfx": {"type": "array", "items": {"type": "object", "properties": {
        "word": {"type": "integer"}, "cue": {"type": "string", "enum": vocab.SFX}}, "required": ["word", "cue"]}},
}, "required": ["machine", "parts", "connections", "events", "shots", "labels", "sfx"]}

RULES = """Storyboard rules:
- ONE host machine (machine.host) stands at the centre of a bright studio. It may be there from the start or
  appear (event appear, target "machine") right after the hook. Every real machine part MOUNTS in a host slot
  (part.mount = its REAL place: e.g. a fridge's evaporator coil inside_top, compressor back_bottom, condenser
  back_middle, capillary tube back_top, fan inside_middle, thermostat inside_middle). One part per slot at a
  time. A fridge's or air conditioner's expansion device is a capillary (thin coiled tube), not a nozzle.
- Props (the hook object and analogy objects) stand on a stage spot (front, left, right), never mounted. The
  hook prop is alone on screen first (prop shot). When an analogy turns into the real part, the part appears
  with from = the prop id: it flies out of the prop into its slot and the prop vanishes. Other props leave with
  a remove event once their beat is over.
- Build up: every mounted part appears (how attach) on the word that introduces it, never all at once.
- Connect the parts the way the real machine does (connections between ports, e.g. coil.out -> compressor.in);
  they are drawn along the machine. Then SHOW WHAT FLOWS: flow events on connections and on coils / radiators
  with the right kind (cold_gas blue, hot_gas red, hot_liquid orange, cold_liquid deep blue...), switched on
  when the narration explains them; a later flow event with another kind on the same target recolours it.
- Show the physics: run events for moving parts (compressor pump, fan spin), frost on cold parts, heat on hot
  ones (a glow, use 0.4-0.6), highlight (on) on the part the narration talks about when it is already on
  screen. A jet out of a port (flow on part.port) ONLY for a prop's spray the narration mentions (the hook
  can); a machine part never sprays into the air.
- SHOW WHERE THE HEAT GOES with heat_flow (warm waves): when the narration says the cold coil soaks up heat,
  heat_flow from machine.food to that coil; when it says the hot coil gives heat away, heat_flow from that coil
  to room; an analogy prop that warms up or cools down can show it too. Pipes and coils carry fluids (cold_gas,
  hot_gas, hot_liquid, cold_liquid); the coil inside a fridge always carries cold kinds.
- CLARITY FIRST, ONE THING AT A TIME: the viewer must understand each step before the next. Each beat shows
  one change; don't stack several events on the same words.
- Shots start on word indices in order (first at 0). Hold every shot 3.5-7 s (never shorter): the camera
  glides between views, it does not flash through them. frame: prop = one prop; part = ONE part fills the
  frame (use it once, while that part clicks in or acts); area = a part and what it connects to; machine =
  the whole machine, always from the same home view (code picks it so every part is visible), so the viewer
  always knows where things are. Pattern for each new part: part (it clicks in) -> machine or area (where it
  sits and what flows to and from it). move: push_in, pull_back, orbit (slow, best on machine / area), hold.
  Never two shots in a row on the same subject with the same framing: each new shot must show something new.
- A control part (thermostat, switch, valve handle) is WIRED to what it controls: a connection kind wire from
  it to that part, with an electricity flow while it powers it, so the viewer sees what the click switches.
  When it switches the machine off, stop the motor (run speed stop) and the flows; on again, restart them.
- The hook's surprise (frost, spray, spark...) starts on the first words, so it is seen within 2 s.
- Props are only on screen in their own shots (and while a part flies out of one); the machine shots show
  the machine alone. The outro ends on the whole machine with every flow running.
- Labels: one pill per new part or key number, on its word, anchored to part.anchor (or machine.top), gone
  2-3 s later (until_word); a number needs its fact_id. Use the script's label text.
- sfx: only extra accents (spray for a spray can, boil / bubbles for boiling, bang, power_up when the finished
  machine starts, ding). Clanks for parts clicking in, clicks for pipes, hums / whirrs for running motors and
  hisses for gas are added automatically from the events."""


def inputs(run):
    return [run.path("script.json"), run.path("words.json"), run.path("brief.json"), run.path("facts.json"),
            sorted(vocab.PARTS), sorted(hosts.HOSTS), RULES]


def _prompt(run) -> str:
    b, script, words = run.need("brief.json"), run.need("script.json"), run.need("words.json")
    facts = run.need("facts.json")
    W = words["words"]
    lines = []
    for wb, sb in zip(words["beats"], script["beats"]):
        ws = " ".join(f"[{i}]{W[i]['text']}" for i in range(wb["first_word"], wb["last_word"] + 1))
        lab = f" | label: {sb['label']['text']} ({sb['label']['variant']}, fact {sb['label'].get('fact_id')})" \
            if sb.get("label") else ""
        lines.append(f"{sb['id']} {sb['role']} ({wb['start']:.1f}-{wb['end']:.1f} s) adds: {sb['part_added'] or '-'}"
                     f"{lab} | visual: {sb['visual']}\n   {ws}")
    fl = "\n".join(f"- {f['id']}: {f['value']} {f['unit']} ({f['claim']})" for f in facts["facts"])
    added = {str(x.get("part_added") or "") for x in script["beats"] if x.get("role") == "fix"}     # kit types
    added |= {"nozzle"} if "capillary" in added else set()          # older briefs planned the capillary as a nozzle
    steps = [st for st in b.get("chain", []) if added & set(st.get("kit_parts", []))] or b.get("chain", [])
    chain = "\n".join(f"- {st['part_added']}: kit {', '.join(st['kit_parts'])} -> slot {st.get('slot') or '?'}"
                      for st in steps) + "\n(only these parts: the script adds no others)"
    return f"""{STYLE}

Storyboard "{b['title']}" ({words['duration']:.1f} s). Host machine: {b.get('host', 'machine')}.
Hook: {b['hook']}. Ends on: {b['machine']}.
Parts and where they mount (from the brief):
{chain}

Beats with their words (global word indices in brackets):
{chr(10).join(lines)}

Facts for numeric labels:
{fl}

{vocab.describe()}

{RULES}

{review.lessons_text(run, ["story", "look", "animation", "captions_labels", "pacing"])}"""


def hook_type(run) -> str | None:
    """The kit prop the script's hook is about (named in beat 1's narration or visual), if any."""
    b1 = run.need("script.json")["beats"][0]
    text = (b1.get("narration", "") + " " + b1.get("visual", "")).lower().replace("-", " ")
    named = [t for t in vocab.PROPS if t.replace("_", " ") in text]
    return max(named, key=len) if named else None


def plan(run, notes: str = "", current: dict | None = None) -> dict:
    words = run.need("words.json")
    facts = run.need("facts.json")
    base = _prompt(run)
    extra = ""
    if current is not None:
        cur = {k: v for k, v in current.items() if k != "errors"}
        extra = ("\n\nTHIS storyboard was rendered and reviewed. Edit it: make every change the notes ask for (in "
                 "the kit's terms), keep everything the notes do not mention exactly as it is, and return the whole "
                 f"storyboard.\n\nNotes from the review:\n{notes}\n\nThe reviewed storyboard:\n" + json.dumps(cur))
    elif notes:
        extra = f"\n\nNotes from the visual check of the last version (fix these):\n{notes}"
    errs, sb = [], {}
    for attempt in range(4):
        sb = llm.ask("You are a 3D motion designer who storyboards machine explainers in a fixed parts kit.",
                     base + extra, SCHEMA, effort="high", label="buildit_storyboard")
        sb.setdefault("machine", {}).setdefault("host", run.need("brief.json").get("host", "machine"))
        fixes = check.repair(sb, words["words"], words["duration"], facts, hook=hook_type(run))
        fixes += check.repair(sb, words["words"], words["duration"], facts, hook=hook_type(run))   # settle
        if fixes:
            log.info("[storyboard] repaired in code: %s", "; ".join(fixes[:8]))
        errs = check.check(sb, words["words"], words["duration"], facts)
        if not errs:
            break
        log.warning("[storyboard] attempt %d: %d problems: %s", attempt + 1, len(errs), "; ".join(errs[:5]))
        why = f"\n\nNotes from the review (still to do):\n{notes}" if notes else ""
        extra = (f"{why}\n\nYour previous storyboard broke these rules; fix every one and keep what worked:\n- " +
                 "\n- ".join(errs) + "\n\nPrevious storyboard:\n" + json.dumps(sb))
    sb["errors"] = errs
    return sb


def run(run):
    run.save("storyboard.json", plan(run))


def revise(run, notes: str):
    """Edit the reviewed storyboard with the review's notes (never a fresh plan: what already works stays)."""
    sb = plan(run, notes, current=run.need("storyboard.json"))
    if not sb["errors"]:
        run.save("storyboard.json", sb)
    return sb


def validate(run):
    sb = run.need("storyboard.json")
    words = run.need("words.json")
    errs = check.check(sb, words["words"], words["duration"], run.need("facts.json"))
    if errs:
        raise StageError("storyboard fails checks:\n- " + "\n- ".join(errs))
