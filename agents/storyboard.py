"""
Storyboards: the planner's whole design of a Max story, as DATA in the kit's vocabulary
(engine/kit/vocab.py). This module validates one and turns it into a normal set (a spec module and a
three-line builder that subclasses the kit), so the showrunner, make_film, scene review and the measured
QA all work on it unchanged. No Blender code is written per video, and nothing here calls an AI.

    problems = validate(storyboard)        # [] = renderable
    set_id = compile_set(storyboard)       # writes engine/sets/<set_id>_spec.py and <set_id>.py
"""
import json
import os
import re

from config.paths import PROJECT_ROOT
from engine.kit import vocab

_ID = re.compile(r"^[a-z][a-z0-9_]{2,30}$")

S = {"type": "string"}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["world", "subject", "title", "model_facts", "gag", "steps", "hooks"],
    "properties": {
        "world": {"type": "string", "enum": list(vocab.WORLDS)},
        "subject": S,
        "title": S,
        "model_facts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["name", "fact"],
            "properties": {"name": S, "fact": S}}},
        "gag": {"type": "string", "enum": list(vocab.GAGS)},
        "steps": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "kind", "change", "event", "weather", "label"],
            "properties": {"id": S, "kind": {"type": "string", "enum": list(vocab.STEP_KINDS)},
                           "change": {"type": "string", "enum": list(vocab.CHANGES)},
                           "event": {"type": "string", "enum": list(vocab.EVENTS)},
                           "weather": {"type": "string", "enum": list(vocab.WEATHER)},
                           "label": S}}},
        "hooks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "step"],
            "properties": {"id": S, "step": S}}},
    },
}


def validate(sb: dict) -> list:
    """Every reason this storyboard could not be filmed as written (empty list = renderable)."""
    p = []
    if sb.get("world") not in vocab.WORLDS:
        p.append(f"world must be one of {vocab.WORLDS}")
    steps = sb.get("steps") or []
    if not 5 <= len(steps) <= 11:
        p.append(f"{len(steps)} steps; a story has 5-11 (setup, fail/fix pairs, finale)")
    ids = [s.get("id", "") for s in steps] + [h.get("id", "") for h in sb.get("hooks") or []] + ["rewind"]
    bad = [i for i in ids if not _ID.match(i or "")]
    if bad:
        p.append(f"ids must be snake_case 3-31 characters: {bad}")
    if len(set(ids)) != len(ids):
        p.append("every step and hook id must be unique (and not 'rewind')")
    if steps and (steps[0].get("kind") != "setup" or steps[0].get("event") != "calm"):
        p.append("the first step must be kind 'setup' with event 'calm' (the promise on a calm day)")
    if steps and steps[-1].get("kind") != "finale":
        p.append("the last step must be the finale")
    built, first_done, shape = set(), False, "flat"
    for k, s in enumerate(steps):
        kind, change, event = s.get("kind"), s.get("change"), s.get("event")
        ev, ch = vocab.EVENTS.get(event), vocab.CHANGES.get(change)
        where = f"step {k + 1} '{s.get('id')}'"
        if ev is None or ch is None:
            p.append(f"{where}: unknown change '{change}' or event '{event}'")
            continue
        if ch.get("first"):
            if first_done:
                p.append(f"{where}: '{change}' builds the barrier and can only be the first build")
            first_done = True
        elif change != "none" and not first_done:
            p.append(f"{where}: '{change}' needs the barrier built first (sand_wall)")
        if change != "none" and change in built:
            p.append(f"{where}: '{change}' is already built")
        built.add(change)
        built.update(ch.get("adds", []))
        shape = ch.get("profile") or shape
        allowed = vocab.EVENT_PROFILES.get(event)
        if allowed and shape not in allowed:
            p.append(f"{where}: event '{event}' is built for a {' or '.join(allowed)} barrier, but it is {shape} here")
        shape = {"seep_slump": "slumped", "overtop_scour": "gouged"}.get(event, shape)
        missing = [n for n in ev.get("needs", []) if n not in built]
        if missing:
            p.append(f"{where}: event '{event}' needs {missing} built in this or an earlier step")
        if kind == "fail" and ev["outcome"] != "fail":
            p.append(f"{where}: a fail step needs a failing event, not '{event}'")
        if kind in ("fix", "finale") and ev["outcome"] != "hold":
            p.append(f"{where}: a {kind} step needs an event where the barrier holds, not '{event}'")
        if kind == "fix" and (k == 0 or steps[k - 1].get("kind") != "fail"):
            p.append(f"{where}: every fix answers the failure right before it")
        if kind == "fail" and (k + 1 >= len(steps) or steps[k + 1].get("kind") != "fix"):
            p.append(f"{where}: every failure is followed by the fix that answers it")
        if kind in ("fail", "fix") and event in ("calm", "storm_holds"):
            p.append(f"{where}: '{event}' only opens or closes the story")
        if event != "calm" and not first_done:
            p.append(f"{where}: nothing can happen to the barrier before it is built")
        label = s.get("label") or ""
        if len(label) > vocab.LABEL_MAX:
            p.append(f"{where}: label '{label}' is over {vocab.LABEL_MAX} characters")
        if kind in ("fail", "fix") and not label.strip():
            p.append(f"{where}: fail and fix steps name their idea in a short label")
    step_ids = {s.get("id"): s for s in steps}
    hooks = sb.get("hooks") or []
    if not 1 <= len(hooks) <= 2:
        p.append("give 1-2 hooks (a step replayed first, before the rewind)")
    for h in hooks:
        target = step_ids.get(h.get("step"))
        if target is None or target.get("kind") not in ("fail", "finale"):
            p.append(f"hook '{h.get('id')}' must replay a fail step or the finale")
    return p


def _names(sb):
    return [s["id"] for s in sb["steps"]]


def spec_source(sb: dict, set_id: str) -> str:
    """The spec module of a kit set: pure data derived from the storyboard and the kit's own knowledge of
    what each event shows (never the planner's guess)."""
    actions = {}
    steps = {s["id"]: s for s in sb["steps"]}
    gag = sb.get("gag") == "duck"
    for h in sb["hooks"]:
        s = steps[h["step"]]
        ev = vocab.EVENTS[s["event"]]
        actions[h["id"]] = {"kind": "hook", "shows": f"The payoff moment first: {ev['shows']}.",
                            "must_see": vocab.EVENT_MUST_SEE[s["event"]],
                            "extras": vocab.GAG_DOES[s["event"]] if gag else "",
                            "seconds": vocab.SECONDS["hook"], "replays": s["id"]}
    actions["rewind"] = {"kind": "rewind", "shows": "Freeze frame, record scratch, the story plays BACKWARDS (VHS look) "
                                                    "to the calm day where it starts."}
    for s in sb["steps"]:
        ev, ch = vocab.EVENTS[s["event"]], vocab.CHANGES[s["change"]]
        shows = (f"{ch['does'][0].upper()}{ch['does'][1:]}. Then " if s["change"] != "none" else "") + ev["shows"] + "."
        kind = {"setup": "story", "finale": "story"}.get(s["kind"], s["kind"])
        actions[s["id"]] = {"kind": kind, "shows": shows, "must_see": vocab.EVENT_MUST_SEE[s["event"]],
                            "extras": vocab.GAG_DOES[s["event"]] if gag else "",
                            "seconds": vocab.SECONDS[s["kind"]], "label": (s.get("label") or "").upper()}
    facts = {f["name"]: f["fact"] for f in sb.get("model_facts") or []}
    for s in sb["steps"]:
        if s.get("label"):
            facts[f"on-screen label in {s['id']}"] = s["label"].upper()
    return f'''"""
KIT SET {set_id} (generated by agents/storyboard.py from a storyboard; do not edit by hand).
{sb["title"]}
"""
from engine.kit.spec_rules import make_rules

SET_ID = {set_id!r}
KIT = {sb["world"]!r}
SUBJECT = {sb["subject"]!r}
HERO = "Max"
MODEL_FACTS = {json.dumps(facts, indent=4, ensure_ascii=False)}
STORY_ORDER = {json.dumps(_names(sb))}
ACTIONS = {json.dumps(actions, indent=4, ensure_ascii=False)}
for _a in ACTIONS.values():
    if "seconds" in _a:
        _a["seconds"] = tuple(_a["seconds"])

beat_actions, min_seconds, validate = make_rules(ACTIONS, STORY_ORDER)
'''


def builder_source(sb: dict, set_id: str) -> str:
    cls = "".join(w.capitalize() for w in set_id.split("_")) + "Set"
    return f'''"""KIT SET {set_id}: staged entirely by the kit from its storyboard (generated; do not edit by hand)."""
import json

from engine.kit.embankment import EmbankmentSet

STORYBOARD = json.loads({json.dumps(json.dumps(sb, ensure_ascii=False))})


class {cls}(EmbankmentSet):
    STORYBOARD = STORYBOARD
'''


def reference_film(sb: dict, set_id: str) -> dict:
    """A plain narration for previews and static checks (the showrunner writes the real script)."""
    steps = {s["id"]: s for s in sb["steps"]}
    hook = sb["hooks"][0]
    beats = [{"action": hook["id"], "text": "This is Max. His barrier just lost to the river.",
              "overlay": {"type": "none"}},
             {"action": "rewind", "text": "Let's rewind to a sunny day.", "overlay": {"type": "none"}}]
    for s in sb["steps"]:
        ev = vocab.EVENTS[s["event"]]
        if s["kind"] == "setup":
            text = "Max promised his kids a backyard that never floods. How hard could it be, really?"
        elif s["kind"] == "finale":
            text = "Now every fix works together, the river rises, and the yard stays dry. Which fix would you build?"
        elif s["kind"] == "fail":
            text = f"The river rose and it failed, because {ev['teaches']}."
        else:
            text = f"So Max fixed it, and it held, because {ev['teaches']}."
        words = text.split()
        beats.append({"action": s["id"], "text": " ".join(words[:30]), "overlay": {"type": "none"}})
    if not beats[-1]["text"].endswith("?"):
        beats[-1]["text"] += " Which fix would you build?"
    return {"title": sb["title"], "set": set_id, "voice": "energetic", "captions": "word", "music": "synth",
            "beats": beats, "cta": beats[-1]["text"].split(". ")[-1]}


def set_id_for(sb: dict) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (sb.get("title") or sb.get("subject") or "story").lower()).strip("_")
    return ("kit_" + base)[:40].rstrip("_") + "_story"


def compile_set(sb: dict, set_id: str = None, root: str = None) -> str:
    """Validate and write the set's two modules. Raises ValueError with every problem if not renderable."""
    problems = validate(sb)
    if problems:
        raise ValueError("storyboard is not renderable:\n- " + "\n- ".join(problems))
    set_id = set_id or set_id_for(sb)
    folder = os.path.join(root or PROJECT_ROOT, "engine", "sets")
    with open(os.path.join(folder, f"{set_id}_spec.py"), "w", encoding="utf-8") as fh:
        fh.write(spec_source(sb, set_id))
    with open(os.path.join(folder, f"{set_id}.py"), "w", encoding="utf-8") as fh:
        fh.write(builder_source(sb, set_id))
    films = os.path.join(root or PROJECT_ROOT, "engine", "films")
    with open(os.path.join(films, f"{set_id}.json"), "w", encoding="utf-8") as fh:
        json.dump(reference_film(sb, set_id), fh, indent=2, ensure_ascii=False)
    return set_id


# A reference storyboard (also the kit's regression film): the levee ladder.
LEVEE = {
    "world": "embankment", "gag": "duck",
    "title": "Max's Backyard Levee",
    "subject": "Max, a cheerful, overconfident DIY dad, builds an earthen levee between a river and his backyard so "
               "his kids' trampoline never floods; the riverbank is cut open so we see inside the ground",
    "model_facts": [
        {"name": "permeability", "fact": "water moves through sand about a million times faster than through clay"},
        {"name": "underseepage", "fact": "flood water travels under a levee through buried sand and pushes up the "
                                         "thin soil on the land side, which can erupt as a sand boil"},
        {"name": "freeboard", "fact": "FEMA's minimum for riverine levees is 3 ft above the 100-year flood"},
        {"name": "piping", "fact": "a burrow lets water flow through a levee; the flow carries soil out and widens "
                                   "the hole from the inside (piping)"},
    ],
    "steps": [
        {"id": "promise", "kind": "setup", "change": "none", "event": "calm", "weather": "sunny", "label": ""},
        {"id": "fail_sand", "kind": "fail", "change": "sand_wall", "event": "seep_slump", "weather": "rain",
         "label": "SAND LEAKS"},
        {"id": "fix_core", "kind": "fix", "change": "clay_core_widen", "event": "seep_blocked", "weather": "rain",
         "label": "CLAY CORE"},
        {"id": "fail_boil", "kind": "fail", "change": "none", "event": "underseep_boil", "weather": "storm",
         "label": "SAND BOIL"},
        {"id": "fix_berm", "kind": "fix", "change": "berm_wells", "event": "underseep_relieved", "weather": "storm",
         "label": "RELIEF WELLS"},
        {"id": "fail_overtop", "kind": "fail", "change": "none", "event": "overtop_scour", "weather": "storm",
         "label": "OVERTOPPING"},
        {"id": "fix_armor", "kind": "fix", "change": "raise_armor", "event": "freeboard_holds", "weather": "storm",
         "label": "FREEBOARD"},
        {"id": "fail_burrow", "kind": "fail", "change": "none", "event": "burrow_piping", "weather": "rain",
         "label": "PIPING"},
        {"id": "fix_maintain", "kind": "fix", "change": "fill_burrows", "event": "burrow_sealed", "weather": "sunny",
         "label": "INSPECT + FILL"},
        {"id": "finale", "kind": "finale", "change": "none", "event": "storm_holds", "weather": "storm", "label": ""},
    ],
    "hooks": [{"id": "burrow_hook", "step": "fail_burrow"}, {"id": "happy_hook", "step": "finale"}],
}
