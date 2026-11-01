"""
Stage 6 - shotlist.json: 10-16 shots tied to word timestamps.

The model plans shots in the kit's vocabulary (cut presets, camera presets, anchors, events) and pins
everything to words by index. Code turns words into seconds, checks every name against the kit, and solves
the crank angle as a function of time so each event lands on its word (the spark fires on "fires") while the
mechanism runs at the speed the shot asked for. The last shot returns to the first view at the same crank
angle, so the video loops.
"""
from __future__ import annotations

import json
import logging
import math

from agents import llm

from .. import kits
from ..runner import StageError
from .script import JARGON

log = logging.getLogger("pipeline")
SPEEDS = {"stop": 0.0, "slow": 90.0, "explain": 180.0, "run": 540.0, "fast": 1440.0}    # crank deg/s on screen
CUT_LEAD = 0.12          # a cut lands this long before its word
STATES = ["closed", "peeling", "sectioned", "xray"]
MOVES = ["dolly", "orbit", "push_in", "pull_out", "crane", "rack_focus", "static"]
TRANSITIONS = ["cut", "match", "whip", "dip", "flash"]
SFX = ["whoosh", "click", "ignition", "hiss", "rumble", "clunk", "spark", "riser", "impact"]

SYSTEM = """You are the director of photography for a premium 3D engineering cutaway channel. You plan shots
that a fixed 3D kit can film: you may only use the kit's cut presets, camera presets, anchors and events.
Purposeful camera: one dive into the mechanism beats ten orbits. Every shot has visible change (a camera move,
the mechanism running, a cut opening). Text never covers the mechanism; callouts point at parts by anchor."""


def _schema(kit):
    key = {"type": "object", "properties": {
        "preset": {"type": "string", "enum": list(kit["cameras"])},
        "orbit": {"type": "number", "description": "degrees around the target, -40..40"},
        "dolly": {"type": "number", "description": "fraction toward the target, -0.4..0.5"},
        "rise": {"type": "number", "description": "metres up/down, -0.15..0.15"}}, "required": ["preset"]}
    at = {"type": "integer", "description": "word index inside the beat (0 = its first word)"}
    return {
        "type": "object",
        "properties": {"shots": {"type": "array", "items": {"type": "object", "properties": {
            "beat": {"type": "string"},
            "start_word": at,
            "cut": {"type": "object", "properties": {
                "state": {"type": "string", "enum": STATES},
                "preset": {"type": "string", "enum": [""] + list(kit["cuts"])}}, "required": ["state", "preset"]},
            "camera": {"type": "object", "properties": {
                "from": key, "to": key, "move": {"type": "string", "enum": MOVES},
                "focus": {"type": "string", "enum": list(kit["anchors"])}},
                "required": ["from", "to", "move", "focus"]},
            "crank": {"type": "string", "enum": list(SPEEDS)},
            "callouts": {"type": "array", "items": {"type": "object", "properties": {
                "anchor": {"type": "string", "enum": list(kit["anchors"])}, "text": {"type": "string"},
                "fact_id": {"type": ["string", "null"]}, "at_word": at}, "required": ["anchor", "text", "at_word"]}},
            "events": {"type": "array", "items": {"type": "object", "properties": {
                "type": {"type": "string", "enum": list(kit["events"])},
                "cylinder": {"type": "integer", "description": "the unit the event happens to (cylinder number; 1 "
                                                               "when the kit has a single one)"},
                "at_word": at}, "required": ["type", "cylinder", "at_word"]}},
            "sfx": {"type": "array", "items": {"type": "object", "properties": {
                "cue": {"type": "string", "enum": SFX}, "at_word": at}, "required": ["cue", "at_word"]}},
            "transition": {"type": "string", "enum": TRANSITIONS, "description": "how this shot begins"},
            "why": {"type": "string"},
        }, "required": ["beat", "start_word", "cut", "camera", "crank", "callouts", "events", "sfx", "transition"]}}},
        "required": ["shots"],
    }


def inputs(run):
    return [run.path("script.json"), run.path("words.json"), run.path("facts.json")]


# ------------------------------------------------------------ crank solver

def pinned(kit) -> bool:
    return kit.get("drive", "crank") == "crank"


def solve_crank(shots: list[dict], kit: dict, theta0: float = 200.0, loop_to: float | None = None):
    """Absolute crank-angle keys [(t, deg)]: each shot runs at its speed; each event pins its cylinder's cycle
    angle to the event angle at the event's time (choosing whole extra turns so the speed stays closest to
    what the shot asked for); the end matches theta0 modulo 720 when loop_to is set."""
    keys = [(0.0, theta0)]
    t_prev, th_prev = 0.0, theta0
    for s in shots:
        speed = SPEEDS[s["crank"]]
        pins = sorted((e["t"], kit["event_angles"][e["type"]] + kit["cycle_offsets"][e["cylinder"]])
                      for e in s.get("events_t", [])) if pinned(kit) else []
        for t_ev, target in pins:
            if t_ev <= t_prev + 1e-3:
                continue
            want = th_prev + max(speed, 60.0) * (t_ev - t_prev)       # an event needs the crank moving
            k = round((want - target) / 720.0)
            th = target + 720.0 * k
            while th <= th_prev + 20.0:
                th += 720.0
            keys.append((t_ev, th))
            t_prev, th_prev = t_ev, th
        th_end = th_prev + speed * (s["end"] - t_prev)
        keys.append((s["end"], th_end))
        t_prev, th_prev = s["end"], th_end
    if loop_to is not None and len(keys) > 1:
        t_end, th_end = keys[-1]
        th_fix = loop_to + 720.0 * round((th_end - loop_to) / 720.0)
        if th_fix < keys[-2][1]:
            th_fix += 720.0
        keys[-1] = (t_end, th_fix)
    # merge keys at identical times
    out = []
    for t, th in keys:
        if out and abs(out[-1][0] - t) < 1e-6:
            out[-1] = (t, th)
        else:
            out.append((round(t, 4), round(th, 3)))
    return out


def theta_at(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, a0), (t1, a1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            return a0 + (a1 - a0) * (t - t0) / max(1e-9, t1 - t0)
    return keys[-1][1]


def _event_feasibility(shots, kit) -> list[str]:
    """Pinned events must be physically possible in order: one engine, one crank. Two pins at one moment, or
    pins so close that the crank would have to whirl through an explanation shot, go back to the planner."""
    errs = []
    if not pinned(kit):
        return errs
    pins = sorted(((e["t"], e["type"], e["cylinder"], s) for s in shots for e in s["events_t"]),
                  key=lambda p: p[0])
    for (ta, ya, ca, sa), (tb, yb, cb, sb) in zip(pins, pins[1:]):
        dt = tb - ta
        a = kit["event_angles"][ya] + kit["cycle_offsets"][ca]
        b = kit["event_angles"][yb] + kit["cycle_offsets"][cb]
        adv = (b - a) % 720.0 or 720.0
        if dt < 0.12:
            errs.append(f"{sb['id']}: '{yb}' on cylinder {cb} at the same moment as '{ya}' on cylinder {ca}: "
                        "cylinders fire in turn, so give each its own word (or keep only one)")
            continue
        allowed = max(4 * max(SPEEDS[sa["crank"]], SPEEDS[sb["crank"]]), 900.0)
        if adv / dt > allowed:
            errs.append(f"{sb['id']}: '{ya}' (cyl {ca}) then '{yb}' (cyl {cb}) {dt:.2f} s apart makes the crank "
                        f"turn {adv:.0f} deg in that time ({adv / dt:.0f} deg/s, too fast for a "
                        f"'{sb['crank']}' shot): drop one, move it to a later word, or follow the cycle order "
                        "(intake_open, spark, exhaust_open)")
    return errs


# ------------------------------------------------------------ build and check

def _look(s) -> tuple:
    return s["camera"]["from"]["preset"], s["cut"]["state"], s["cut"]["preset"]


def _variety(shots) -> list[str]:
    """The first engine draft showed the same section from the same angle in 11 of 16 shots (user: "showing
    the same thing"). Back-to-back shots must look different, and no single view may dominate."""
    errs = []
    for a, b in zip(shots, shots[1:]):
        if _look(a) == _look(b) and a["camera"]["to"]["preset"] == b["camera"]["to"]["preset"]:
            errs.append(f"{b['id']} repeats {a['id']}'s view ({_look(b)[0]}, {_look(b)[1]}): change the camera "
                        "preset or the cut state, or merge the two shots")
    uses = {}
    for s in shots:
        uses[s["camera"]["from"]["preset"]] = uses.get(s["camera"]["from"]["preset"], 0) + 1
    for name, n in uses.items():
        if n > 3:
            errs.append(f"camera preset {name} opens {n} shots: use it at most 3 times and show other views")
    want = min(8, max(3, len(shots) // 2))
    if len(uses) < want:
        errs.append(f"only {len(uses)} different camera presets: use at least {want}")
    return errs


def build(plan: dict, words: dict, kit: dict, facts: dict, duration: float) -> tuple[dict, list[str]]:
    errs = []
    beats = {b["id"]: b for b in words["beats"]}
    W = words["words"]
    fact_ids = {f["id"] for f in facts["facts"]}

    def word_t(beat, idx, key="start"):
        b = beats[beat]
        i = max(b["first_word"], min(b["last_word"], b["first_word"] + int(idx)))
        return W[i][key]

    shots = []
    for k, p in enumerate(plan["shots"]):
        if p["beat"] not in beats:
            errs.append(f"shot {k + 1}: unknown beat {p['beat']}")
            continue
        start = 0.0 if not shots else max(0.0, word_t(p["beat"], p["start_word"]) - CUT_LEAD)
        s = {"id": f"s{len(shots) + 1:02d}", "beat": p["beat"], "start": round(start, 3), **p}
        s["events_t"] = [{**e, "t": word_t(p["beat"], e["at_word"])} for e in p.get("events", [])]
        s["callouts_t"] = [{**c, "t": word_t(p["beat"], c["at_word"])} for c in p.get("callouts", [])]
        s["sfx_t"] = [{**x, "t": word_t(p["beat"], x["at_word"])} for x in p.get("sfx", [])]
        shots.append(s)
    shots.sort(key=lambda s: s["start"])
    for a, b in zip(shots, shots[1:]):
        a["end"] = b["start"]
    if shots:
        shots[-1]["end"] = round(duration, 3)
    for i, s in enumerate(shots):
        s["id"] = f"s{i + 1:02d}"
        d = s["end"] - s["start"]
        if d < 0.9:
            errs.append(f"{s['id']} lasts {d:.2f} s: shots need at least 0.9 s (start it on a later word or merge)")
        if d > 8.0:
            errs.append(f"{s['id']} lasts {d:.1f} s: split it (max 8 s)")
        state, preset = s["cut"]["state"], s["cut"]["preset"]
        if state in ("peeling", "sectioned") and preset not in kit["cuts"]:
            errs.append(f"{s['id']}: cut state {state} needs a cut preset")
        for end in ("from", "to"):
            need = kit["cameras"][s["camera"][end]["preset"]][0]
            have = state if state in ("closed", "xray") else preset
            if have not in need and not (state == "peeling" and "closed" in need):
                errs.append(f"{s['id']}: camera {s['camera'][end]['preset']} is made for '{need}', not '{have}'")
        for c in s["callouts_t"]:
            if state == "closed" and c["anchor"] not in kit.get("exterior_anchors", kit["anchors"]):
                errs.append(f"{s['id']}: '{c['anchor']}' is inside the machine, invisible in a closed shot: "
                            f"anchor to one of {kit.get('exterior_anchors')} or open the cut first")
            if any(ch.isdigit() for ch in c["text"]) and c.get("fact_id") not in fact_ids:
                errs.append(f"{s['id']}: callout '{c['text']}' has a number but no valid fact_id")
            if len(c["text"].split()) > 4:
                errs.append(f"{s['id']}: callout '{c['text']}' is too long (max 4 words)")
            if JARGON.search(c["text"]):
                errs.append(f"{s['id']}: callout '{c['text']}' uses jargon a 12-year-old can't follow")
        for e in s["events_t"]:
            if e["cylinder"] not in kit.get("units", [1]):
                errs.append(f"{s['id']}: no unit {e['cylinder']} (use one of {kit.get('units', [1])})")
        moving = s["crank"] != "stop" or s["camera"]["move"] != "static" or state == "peeling"
        if not moving:
            errs.append(f"{s['id']}: nothing moves (static camera and stopped crank)")
    errs += _event_feasibility(shots, kit)
    errs += _variety(shots)
    n = len(shots)
    lo, hi = max(8, round(duration / 6.5)), max(12, round(duration / 4.4))
    if not lo <= n <= hi:
        errs.append(f"plan {lo}-{hi} shots for {duration:.0f} s (got {n})")
    if shots and (shots[-1]["cut"]["state"] != "closed" or
                  shots[-1]["camera"]["to"]["preset"] != shots[0]["camera"]["from"]["preset"]):
        errs.append("the last shot must end closed on the first shot's opening camera preset (seamless loop)")
    if shots and shots[0]["cut"]["state"] in ("sectioned", "xray"):
        errs.append("the first shot opens on the whole machine (closed or peeling), so the cut is a reveal")
    theta0 = 200.0
    crank = solve_crank(shots, kit, theta0, loop_to=theta0)
    for s in shots:
        s["camera_spec"] = {
            "keys": [{"t": s["start"], **s["camera"]["from"]}, {"t": s["end"], **s["camera"]["to"]}],
            "focus": s["camera"]["focus"], "handheld": 0.35,
        }
        if s["cut"]["state"] == "peeling":
            s["cut"]["peel"] = [s["start"] + 0.15, min(s["end"] - 0.2, s["start"] + 1.6)]
    for prev, s in zip(shots, shots[1:]):
        if s.get("transition") == "whip":
            whip(prev, s)
    events = sorted(({"t": round(e["t"], 3), "type": e["type"], "unit": e["cylinder"]}
                     for s in shots for e in s["events_t"]), key=lambda e: e["t"])
    return {"shots": shots, "crank": {"keys": crank}, "events": events, "duration": duration, "fps": 30}, errs


WHIP_DEG, WHIP_T = 34.0, 0.22


def whip(out_shot: dict, in_shot: dict):
    """A real camera whip across the cut: the outgoing camera accelerates into a fast orbit whose peak is past
    its last frame, the incoming one decelerates out of the opposite orbit; Cycles motion blur does the smear."""
    ko = out_shot["camera_spec"]["keys"]
    last = dict(ko[-1])
    ko[-1] = {**last, "t": round(out_shot["end"] - WHIP_T, 3)}
    ko.append({**last, "t": round(out_shot["end"] + 0.12, 3), "orbit": last.get("orbit", 0.0) + WHIP_DEG})
    ki = in_shot["camera_spec"]["keys"]
    first = dict(ki[0])
    ki[0] = {**first, "t": round(in_shot["start"] + WHIP_T, 3)}
    ki.insert(0, {**first, "t": round(in_shot["start"] - 0.12, 3), "orbit": first.get("orbit", 0.0) - WHIP_DEG})


def bad_callout(c, fact_ids) -> str | None:
    if any(ch.isdigit() for ch in c["text"]) and c.get("fact_id") not in fact_ids:
        return "a number without a valid fact_id"
    if len(c["text"].split()) > 4:
        return "longer than 4 words"
    if JARGON.search(c["text"]):
        return f"jargon ('{JARGON.search(c['text']).group(0)}')"
    return None


def repair_callouts(sl: dict, facts: dict) -> int:
    """Rewrite only the callouts that break the text rules (plain words, max 4, numbers from their fact),
    keeping every shot, anchor and timing. Returns how many were fixed."""
    by_id = {f["id"]: f for f in facts["facts"]}
    bad = []
    for s in sl["shots"]:
        for k, c in enumerate(s["callouts_t"]):
            why = bad_callout(c, by_id)
            if why:
                bad.append({"shot": s["id"], "k": k, "text": c["text"], "why": why,
                            "fact": by_id.get(c.get("fact_id"), {}).get("claim")})
    if not bad:
        return 0
    schema = {"type": "object", "properties": {"fixed": {"type": "array", "items": {"type": "object", "properties": {
        "shot": {"type": "string"}, "k": {"type": "integer"}, "text": {"type": "string"}},
        "required": ["shot", "k", "text"]}}}, "required": ["fixed"]}
    prompt = ("Rewrite these on-screen callouts for a 12-year-old: max 4 plain words, no jargon; keep the meaning "
              "and keep any number exactly as its fact states it (or drop the number).\n"
              + "\n".join(f"- {b['shot']}#{b['k']}: '{b['text']}' ({b['why']}; fact: {b['fact']})" for b in bad))
    out = llm.ask(SYSTEM, prompt, schema, effort="low", label="cutaway_callouts")
    shots = {s["id"]: s for s in sl["shots"]}
    n = 0
    for f in out["fixed"]:
        c = shots[f["shot"]]["callouts_t"][f["k"]]
        trial = {**c, "text": f["text"]}
        if not bad_callout(trial, by_id):
            c["text"] = f["text"]
            n += 1
    return n


def run(run):
    brief = run.need("brief.json")
    script = run.need("script.json")
    words = run.need("words.json")
    facts = run.need("facts.json")
    kit = kits.KITS[brief["kit"]]
    duration = words["duration"]
    W = words["words"]
    beat_lines = []
    for b, sb in zip(words["beats"], script["beats"]):
        ws = " ".join(f"[{i - b['first_word']}]{W[i]['text']}" for i in range(b["first_word"], b["last_word"] + 1))
        beat_lines.append(f"{b['id']} ({b['start']:.1f}-{b['end']:.1f} s, {sb['mechanism']}, shot type "
                          f"{sb['shot_type']}; visual: {sb['visual']}): {ws}")
    cams = "\n".join(f"- {k}: needs {v[0]}; {v[1]}" for k, v in kit["cameras"].items())
    cuts = "\n".join(f"- {k}: {v}" for k, v in kit["cuts"].items())
    anchors = "\n".join(f"- {k}: {v}" for k, v in kit["anchors"].items())
    events = "\n".join(f"- {k}: {v}" for k, v in kit["events"].items())
    fact_lines = "\n".join(f"- {f['id']}: {f['value']} {f['unit']} ({f['claim']})" for f in facts["facts"])
    lo, hi = max(8, round(duration / 6.5)), max(12, round(duration / 4.4))
    chapters = "\n".join(f"- {m}: cut {v['cut']}, cameras {', '.join(v['cameras'])}"
                          for m, v in kit["mechanisms"].items()
                          if m in {sb["mechanism"] for sb in script["beats"]})
    tr = kit.get("tracker")
    stroke_rule = (f"""
- {', '.join(tr['mechanisms'])}: film them on one cylinder ({tr['unit']}) in slow motion, crank "slow",
  and pin each stroke's start event (or the spark) to the word that names it, so the piston, the valves and
  the gas colour change exactly as the narrator says so (an on-screen tracker lights the stroke).""" if tr else "")
    prompt = f"""Plan the shots for "{brief['title']}" ({duration:.1f} s of narration).

Beats with their words (indices are per beat):
{chr(10).join(beat_lines)}

Kit: {kit['subject']}
Cut states: closed (the whole machine, solid), xray (the whole machine with see-through castings: every moving
part, and the gas and fluids flowing inside, in context), peeling (a cut preset opens during the shot),
sectioned (a cut preset, open).
Cut presets:
{cuts}
Suggested cut and cameras for each chapter of this script:
{chapters}
Camera presets (each made for a cut state):
{cams}
Anchors (callouts point at these):
{anchors}
Events (pin them to the word that names them):
{events}
Facts for numeric callouts:
{fact_lines}

Rules:
- {lo}-{hi} shots, each 0.9-8 s, in time order; a shot starts on a word (start_word). Shot 1 starts at word 0
  of the first beat and opens closed (or peeling) on the whole machine; the cut opening is a reveal.
- Something visibly changes at least every 1.5 s: camera moves (from -> to), the crank running, a cut peeling.
  A camera key can orbit (deg), dolly (fraction toward target) or rise (m) its preset. Prefer one purposeful
  dive (push_in to a close preset) over orbits.
- Variety: never two shots in a row from the same view; no camera preset opens more than 3 shots; use at
  least 8 different presets. Mix the states: xray for the air path, the fuel spray and the big picture,
  sections for one cylinder's strokes, closed for the hook and outro. Moves can be bold (orbit up to 40 deg,
  dolly up to 0.5, or travel from one preset to another inside a shot).
- crank: stop | slow | explain | run | fast. Slow it down where the narration explains a stroke; run or fast in
  the hook and the outro.{stroke_rule}
- Pin events to their words: the spark fires on the word that says so. Valves open on "opens"/"in" words.
- Callouts: 0-2 per shot, max 4 words, anchored to the part they name; a number needs its fact_id.
- sfx on visible actions only: whoosh for fast camera moves and cuts, ignition on the spark, hiss/clunk on
  valves, rumble when the engine runs. Few and exact.
- transition says how each shot begins: cut, match (match cut on motion), whip, dip, flash (on ignition).
- The last shot returns closed to shot 1's opening camera preset so the video loops seamlessly."""
    notes = ""
    for attempt in range(3):
        plan = llm.ask(SYSTEM, prompt + notes, _schema(kit), effort="high", label="cutaway_shotlist")
        out, errs = build(plan, words, kit, facts, duration)
        if not errs:
            break
        log.warning("[shotlist] attempt %d: %s", attempt + 1, "; ".join(errs[:6]))
        if all("callout '" in e for e in errs):
            repair_callouts(out, facts)
            out_, errs = build(plan, words, kit, facts, duration)
            for s, s2 in zip(out["shots"], out_["shots"]):
                s2["callouts_t"] = s["callouts_t"]
            out, errs = out_, [e for e in errs if "callout '" not in e]
            if not errs:
                break
        notes = ("\n\nYour previous plan broke these rules; fix every one:\n- " + "\n- ".join(errs)
                 + "\n\nPrevious plan:\n" + json.dumps(plan, indent=1))
    out["errors"] = errs
    out["kit"] = brief["kit"]
    run.save("shotlist.json", out)


def validate(run):
    sl = run.need("shotlist.json")
    if sl.get("errors"):
        raise StageError("shotlist fails checks:\n- " + "\n- ".join(sl["errors"]))
    kit = kits.KITS[sl["kit"]]
    for s in sl["shots"] if pinned(kit) else []:
        for e in s["events_t"]:
            th = theta_at(sl["crank"]["keys"], e["t"])
            c = (th - kit["cycle_offsets"][e["cylinder"]]) % 720.0
            want = kit["event_angles"][e["type"]] % 720.0
            if min(abs(c - want), 720 - abs(c - want)) > 1.0:
                raise StageError(f"{s['id']}: event {e['type']} misses its word (crank {c:.1f} vs {want})")
    if not math.isclose(sl["shots"][0]["start"], 0.0):
        raise StageError("the first shot must start at 0")
