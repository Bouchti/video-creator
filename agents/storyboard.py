"""
Storyboards: the planner's whole design of a Max story, as DATA in the kit's vocabulary
(engine/kit/vocab.py). This module validates one and turns it into a normal set (a spec module and a
three-line builder that subclasses the kit), so the showrunner, make_film, scene review and the measured
QA all work on it unchanged. No Blender code is written per video, and nothing here calls an AI.

    problems = validate(storyboard)        # [] = renderable
    set_id = compile_set(storyboard)       # writes engine/sets/<set_id>_spec.py and <set_id>.py

A storyboard with "hero": false is a no-hero explainer (agents/explainer.py): the same ladder filmed
with nobody in it, compiled into an explainer spec (FORMAT "explainer", no HERO) that the explainer
writer and its build-up voice use.
"""
import json
import os
import re

from config.paths import PROJECT_ROOT
from engine.kit import vocab

_ID = re.compile(r"^[a-z][a-z0-9_]{2,30}$")

S = {"type": "string"}


def schema(world: str = vocab.WORLD) -> dict:
    """The storyboard schema for one world: its changes, events and weather are the only choices."""
    v = vocab.for_world(world)
    return {
        "type": "object", "additionalProperties": False,
        "required": ["world", "subject", "title", "model_facts", "gag", "steps", "hooks"],
        "properties": {
            "world": {"type": "string", "enum": [world]},
            "subject": S,
            "title": S,
            "model_facts": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["name", "fact"],
                "properties": {"name": S, "fact": S}}},
            "gag": {"type": "string", "enum": list(v.GAGS)},
            "steps": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["id", "kind", "change", "event", "weather", "label"],
                "properties": {"id": S, "kind": {"type": "string", "enum": list(v.STEP_KINDS)},
                               "change": {"type": "string", "enum": list(v.CHANGES)},
                               "event": {"type": "string", "enum": list(v.EVENTS)},
                               "weather": {"type": "string", "enum": list(v.WEATHER)},
                               "label": S}}},
            "hooks": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["id", "step"],
                "properties": {"id": S, "step": S}}},
        },
    }


SCHEMA = schema()                       # the embankment's


def has_hero(sb: dict) -> bool:
    return sb.get("hero", True) is not False


def world_vocab(sb: dict):
    """The vocabulary of the storyboard's world, or None when the kit has no such world."""
    if sb.get("world") not in vocab.worlds():
        return None
    try:
        return vocab.for_world(sb["world"])
    except ImportError:
        return None


def validate(sb: dict) -> list:
    """Every reason this storyboard could not be filmed as written (empty list = renderable)."""
    p = []
    if sb.get("hero", True) not in (True, False):
        p.append("hero must be true (a Max story) or false (a no-hero explainer)")
    v = world_vocab(sb)
    if v is None:
        return p + [f"world must be one of {vocab.worlds()}"]
    calm, thing = v.CALM, v.THING
    steps = sb.get("steps") or []
    if not 5 <= len(steps) <= 11:
        p.append(f"{len(steps)} steps; a story has 5-11 (setup, fail/fix pairs, finale)")
    ids = [s.get("id", "") for s in steps] + [h.get("id", "") for h in sb.get("hooks") or []] + ["rewind"]
    bad = [i for i in ids if not _ID.match(i or "")]
    if bad:
        p.append(f"ids must be snake_case 3-31 characters: {bad}")
    if len(set(ids)) != len(ids):
        p.append("every step and hook id must be unique (and not 'rewind')")
    if has_hero(sb):
        if steps and (steps[0].get("kind") != "setup" or steps[0].get("event") != calm):
            p.append(f"the first step must be kind 'setup' with event '{calm}' (the promise on a calm day)")
    elif steps and steps[0].get("kind") not in ("setup", "fail") or \
            steps and steps[0].get("kind") == "setup" and steps[0].get("event") != calm:
        # an explainer may open on the crudest build itself ("If you pile sand ..., you have a levee")
        p.append(f"the first step must be the first fail (the crudest build) or a 'setup' with event '{calm}'")
    if any(s.get("kind") == "setup" for s in steps[1:]):
        p.append("only the first step can be a setup")
    if steps and steps[-1].get("kind") != "finale":
        p.append("the last step must be the finale")
    built, first_done, shape = set(), False, "flat"
    for k, s in enumerate(steps):
        kind, change, event = s.get("kind"), s.get("change"), s.get("event")
        ev, ch = v.EVENTS.get(event), v.CHANGES.get(change)
        where = f"step {k + 1} '{s.get('id')}'"
        if ev is None or ch is None:
            p.append(f"{where}: unknown change '{change}' or event '{event}'")
            continue
        if ch.get("first"):
            if first_done:
                p.append(f"{where}: '{change}' builds the {thing} and can only be the first build")
            first_done = True
        elif change != "none" and not first_done:
            p.append(f"{where}: '{change}' needs the {thing} built first ({v.FIRST_BUILD})")
        if change != "none" and change in built:
            p.append(f"{where}: '{change}' is already built")
        built.add(change)
        built.update(ch.get("adds", []))
        shape = ch.get("profile") or shape
        allowed = v.EVENT_PROFILES.get(event)
        if allowed and shape not in allowed:
            p.append(f"{where}: event '{event}' is built for a {' or '.join(allowed)} {thing}, but it is {shape} here")
        shape = ev.get("leaves") or shape
        missing = [n for n in ev.get("needs", []) if n not in built]
        if missing:
            p.append(f"{where}: event '{event}' needs {missing} built in this or an earlier step")
        if kind == "fail" and ev["outcome"] != "fail":
            p.append(f"{where}: a fail step needs a failing event, not '{event}'")
        if kind in ("fix", "finale") and ev["outcome"] != "hold":
            p.append(f"{where}: a {kind} step needs an event where the {thing} holds, not '{event}'")
        if kind == "fix" and (k == 0 or steps[k - 1].get("kind") != "fail"):
            p.append(f"{where}: every fix answers the failure right before it")
        if kind == "fail" and (k + 1 >= len(steps) or steps[k + 1].get("kind") != "fix"):
            p.append(f"{where}: every failure is followed by the fix that answers it")
        if kind in ("fail", "fix") and event in (calm, *v.FINALE_EVENTS):
            p.append(f"{where}: '{event}' only opens or closes the story")
        if event != calm and not first_done:
            p.append(f"{where}: nothing can happen to the {thing} before it is built")
        label = s.get("label") or ""
        if len(label) > v.LABEL_MAX:
            p.append(f"{where}: label '{label}' is over {v.LABEL_MAX} characters")
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
    gag = sb.get("gag") not in (None, "none")
    hero = has_hero(sb)
    v = world_vocab(sb)

    def must_see(event):                       # nobody to see in a no-hero explainer
        return [n for n in v.EVENT_MUST_SEE[event] if hero or n != "Max"]

    for h in sb["hooks"]:
        s = steps[h["step"]]
        ev = v.EVENTS[s["event"]]
        actions[h["id"]] = {"kind": "hook", "shows": f"The payoff moment first: {ev['shows']}.",
                            "must_see": must_see(s["event"]),
                            "extras": v.GAG_DOES.get(s["event"], "") if gag else "",
                            "seconds": v.SECONDS["hook"], "replays": s["id"]}
    actions["rewind"] = {"kind": "rewind", "shows": "Freeze frame, record scratch, the story plays BACKWARDS (VHS look) "
                                                    "to the calm day where it starts."}
    for s in sb["steps"]:
        ev = v.EVENTS[s["event"]]
        does = v.CHANGES[s["change"]]["does"] if hero else v.BUILT[s["change"]]
        shows = (f"{does[0].upper()}{does[1:]}. Then " if s["change"] != "none" else "") + ev["shows"] + "."
        kind = {"setup": "story", "finale": "story"}.get(s["kind"], s["kind"])
        actions[s["id"]] = {"kind": kind, "shows": shows, "must_see": must_see(s["event"]),
                            "extras": v.GAG_DOES.get(s["event"], "") if gag else "",
                            "seconds": v.SECONDS[s["kind"]], "label": (s.get("label") or "").upper()}
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
{'HERO = "Max"' if hero else 'FORMAT = "explainer"'}
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
    module, world_cls = world_vocab(sb).WORLD_CLASS
    return f'''"""KIT SET {set_id}: staged entirely by the kit from its storyboard (generated; do not edit by hand)."""
import json

from {module} import {world_cls}

STORYBOARD = json.loads({json.dumps(json.dumps(sb, ensure_ascii=False))})


class {cls}({world_cls}):
    STORYBOARD = STORYBOARD
'''


def reference_film(sb: dict, set_id: str) -> dict:
    """A plain narration for previews and static checks (the showrunner writes the real script)."""
    hero = has_hero(sb)
    v = world_vocab(sb)
    lines = v.REFERENCE_LINES
    hook = sb["hooks"][0]
    beats = [{"action": hook["id"], "text": lines["hook_hero" if hero else "hook"], "overlay": {"type": "none"}},
             {"action": "rewind", "text": "Let's rewind to the start.", "overlay": {"type": "none"}}]
    for s in sb["steps"]:
        ev = v.EVENTS[s["event"]]
        if s["kind"] == "setup":
            text = lines["setup_hero" if hero else "setup"]
        elif s["kind"] == "finale":
            text = lines["finale"]
        elif s["kind"] == "fail":
            text = f"{lines['fail']} {ev['teaches']}."
        else:
            text = f"So {'Max fixed it' if hero else 'the fix went in'}, and it held, because {ev['teaches']}."
        words = text.split()
        beats.append({"action": s["id"], "text": " ".join(words[:30]), "overlay": {"type": "none"}})
    if not beats[-1]["text"].endswith("?"):
        beats[-1]["text"] += " Which fix would you build?"
    return {"title": sb["title"], "set": set_id, "voice": "energetic", "captions": "word", "music": "synth",
            "beats": beats, "cta": beats[-1]["text"].split(". ")[-1]}


def set_id_for(sb: dict) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (sb.get("title") or sb.get("subject") or "story").lower()).strip("_")
    return ("kit_" + base)[:40].rstrip("_") + ("_story" if has_hero(sb) else "_explainer")


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
