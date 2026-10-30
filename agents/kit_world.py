"""
New KIT WORLDS: when a video's topic needs a world the kit does not have (a septic tank, a bridge, a
pool...), the world is prepared ONCE, before any video is rendered in it, then reused by every later
storyboard. Three stages, each verified before the next starts:

  1. design   one researched call returns the world as DATA (agents/kit_world.WORLD_SCHEMA): every object
              with its real size and look, what can be built (changes), what can happen (events), and a
              reference storyboard. Written as engine/kit/worlds/<world>_vocab.py (no code).
  2. objects  a coding agent writes engine/kit/worlds/<world>_objects.py, one build_<name>() per object.
              engine/kit/object_check.py builds each object ALONE and measures it (geometry, real size,
              materials, no flat colours); one vision look checks each still is recognisable. Only the
              failing objects go back to the agent, in small turns.
  3. staging  the agent writes engine/kit/worlds/<world>.py, the class that films any valid storyboard of
              the world from the tested objects. It is verified like every kit set: the reference
              storyboard (with Max and without a hero) is compiled, previewed and measured.

Only then is the world added to engine/kit/worlds REGISTERED, and the planners can use it.

    world = world_for("how a septic tank works")          # an existing world, or None
    status = build_world("how a septic tank works")        # {"accepted": True, "world": "septic_tank", ...}

  SHOWRUNNER_AUTO_BUILD_WORLDS=0   never build a world automatically (a topic no world fits stops the run)
  KIT_WORLD_ROUNDS=4               repair rounds per stage
"""
import json
import logging
import os
import pprint
import re

from config.paths import PROJECT_ROOT
from engine.kit import vocab

log = logging.getLogger("pipeline")

WORLDS_DIR = os.path.join(PROJECT_ROOT, "engine", "kit", "worlds")
_ID = re.compile(r"^[a-z][a-z0-9_]{2,24}$")
S = {"type": "string"}
_LIST = {"type": "array", "items": S}
WORLD_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["world", "fits", "thing", "news", "description", "description_no_hero", "objects", "changes",
                 "events", "calm_event", "finale_event", "first_build", "reference_storyboard"],
    "properties": {
        "world": S, "fits": S, "thing": S, "news": S, "description": S, "description_no_hero": S,
        "objects": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["name", "what", "look", "size_m"],
            "properties": {"name": S, "what": S, "look": S, "size_m": {
                "type": "object", "additionalProperties": False, "required": ["x", "y", "z"],
                "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}}}}},
        "changes": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "does", "built", "adds", "first"],
            "properties": {"id": S, "does": S, "built": S, "adds": _LIST, "first": {"type": "boolean"}}}},
        "events": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "outcome", "shows", "teaches", "needs", "must_see"],
            "properties": {"id": S, "outcome": {"type": "string", "enum": ["fail", "hold"]}, "shows": S,
                           "teaches": S, "needs": _LIST, "must_see": _LIST}}},
        "calm_event": S, "finale_event": S, "first_build": S,
        "reference_storyboard": {"type": "object", "additionalProperties": False,
                                 "required": ["title", "subject", "model_facts", "steps", "hooks"],
                                 "properties": {
                                     "title": S, "subject": S,
                                     "model_facts": {"type": "array", "items": {
                                         "type": "object", "additionalProperties": False,
                                         "required": ["name", "fact"], "properties": {"name": S, "fact": S}}},
                                     "steps": {"type": "array", "items": {
                                         "type": "object", "additionalProperties": False,
                                         "required": ["id", "kind", "change", "event", "weather", "label"],
                                         "properties": {"id": S, "kind": S, "change": S, "event": S,
                                                        "weather": S, "label": S}}},
                                     "hooks": {"type": "array", "items": {
                                         "type": "object", "additionalProperties": False,
                                         "required": ["id", "step"], "properties": {"id": S, "step": S}}}}},
    },
}


class WorldNotBuilt(RuntimeError):
    """A new world could not be prepared; nothing was rendered in it."""


def auto_build() -> bool:
    return os.getenv("SHOWRUNNER_AUTO_BUILD_WORLDS", "1").lower() not in ("0", "false", "no")


def _class_name(world):
    return "".join(w.capitalize() for w in world.split("_")) + "World"


# ------------------- which world films this topic? -------------------

MATCH_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["world", "reason"],
                "properties": {"world": S, "reason": S}}


def world_for(topic: str, call=None):
    """The registered world that can honestly film `topic`, or None when it needs a new world."""
    from agents import llm
    call = call or llm.ask
    worlds = vocab.worlds()
    briefs = "\n".join(f"- {w}: {vocab.for_world(w).FITS}" for w in worlds)
    out = call("You match a video topic to the 3D world that can film it.", f"""A video is planned about:
{topic}

The pre-built 3D worlds (each films only what it fits):
{briefs}

Return `world` = the id of the ONE world this video is genuinely about, or "none" when it needs a different
world (a riverbank levee world cannot film a septic tank, a bridge or a swimming pool). One-line reason.""",
               MATCH_SCHEMA, effort="low")
    choice = str(out.get("world", "")).strip()
    log.info(f"[kit world] topic -> world: {choice or 'none'} ({out.get('reason', '')})")
    return choice if choice in worlds else None


def pick_world(history=None) -> str:
    """For a run with no topic: the registered world with the fewest videos so far (the embankment on a tie)."""
    from engine import sets
    if history is None:
        from agents.showrunner import _history
        history = _history()
    counts = {w: 0 for w in vocab.worlds()}
    for item in history:
        try:
            kit = getattr(sets.spec(item.get("set")), "KIT", None)
        except Exception:                              # noqa: BLE001  a removed set
            kit = None
        if kit in counts:
            counts[kit] += 1
    return min(counts, key=lambda w: (counts[w], w != vocab.WORLD))


# ------------------- 1. design -------------------

def plan_world(topic: str, call=None) -> dict:
    """Research the topic and design its world as data. Raises WorldNotBuilt if the design breaks the rules
    even after one cheap correction."""
    from agents import llm, showrunner as sr
    call = call or llm.ask
    taken = ", ".join(vocab.worlds())
    prompt = f"""Design a new pre-built 3D WORLD for cutaway videos about: {topic}

The world is ONE cut-open diorama (the ground or the structure sliced open so the hidden parts show) in
which many different videos are filmed. A video is a LADDER: the crudest version is built, it FAILS on
screen for a real physical reason, the real engineering FIX is built and holds, the next problem appears...
until a finale where everything works. Design what the world can build and what can happen in it so that
real, research-backed ladders fit. Search the web to get the real engineering, dimensions and failure modes.

Return:
- world: a snake_case id (3-25 characters, not one of: {taken})
- fits: the topics this world can film (comma-separated), thing: one word for what the ladder builds
- news: the kind of news that makes a timely video in this world
- description (with Max, a cheerful, overconfident DIY dad, building), description_no_hero (nobody on
  screen: each part builds itself and the camera follows the mechanism); 3-4 sentences each, saying where
  everything is in the frame (left, middle, right, underground)
- objects: 6-16 physical objects the videos need (the ground/terrain with its cut face counts as one), each
  with a snake_case name that starts with "{{world}}_"... use the world id as prefix, what it is, the look that
  makes it recognisable at a glance, and its real size in metres (x = left-right, y = depth, z = height)
- changes: what can be built, preferably 6-8 real additive parts: id, does (Max ...), built (the same
  with nobody building), adds
  (state flags it creates, e.g. "valve"), first (true for exactly one: the crudest version, built first)
- events: 6-12 entries: id, outcome fail|hold, shows (what is visibly on screen: arrows, water, flow),
  teaches (the physical reason, one plain clause), needs (flags that must be built before it), must_see
  (the object names that show it). Include one calm opening event (calm_event, outcome hold, nothing goes
  wrong yet) and one finale event (finale_event, outcome hold: everything works). Every change after
  first_build should add a flag used by at least one HOLD event that visibly demonstrates that component
  working; a linear explainer must omit a change that has only failure events.
- first_build: the id of the change with first=true
- reference_storyboard: a valid ladder in this world: title, subject, model_facts (name, fact with a
  number, from research), steps, hooks. The validator enforces, exactly:
  * step 1 = {{"kind":"setup","change":"none","event":"<calm_event>"}}; the calm event needs NOTHING (it
    happens before anything is built), so its "needs" is [];
  * step 2 = the first "fail" step and its change IS first_build (the crudest version is built there);
    nothing else can be built or happen before it;
  * then fail -> fix pairs: every fix builds the change that answers the failure right before it, and an
    event's needs are built in that step or earlier; then one "finale" step with the finale event;
  * 5-11 steps; weather sunny|rain|storm; a label of at most 18 characters on every fail/fix step;
  * ids snake_case, 3-31 characters, unique, descriptive (promise, fail_pit, fix_tank, finale);
  * hooks: 1-2, each {{"id": "<name>_hook", "step": "<a fail step id or the finale id>"}}.
No brands, logos or text in the world."""
    design = call(sr.STYLE, prompt, WORLD_SCHEMA, effort="medium", web=True)
    problems = validate_design(design)
    for _ in range(2):                      # cheap structured corrections; the researched design is kept
        if not problems:
            break
        log.warning(f"[kit world] the design needs a correction: {problems}")
        design = call("You correct a 3D world design so it follows its rules.",
                      f"This world design breaks these rules:\n{json.dumps(problems, indent=1)}\n\nDESIGN:\n"
                      f"{json.dumps(design, indent=1)}\n\nReturn the corrected design: the smallest changes that "
                      "fix every rule (step 2 is the first fail step and builds first_build; the calm event "
                      "needs nothing; ids are descriptive snake_case of 3-31 characters).",
                      WORLD_SCHEMA, effort="low")
        problems = validate_design(design)
    if problems:
        raise WorldNotBuilt("the world design is not buildable: " + "; ".join(problems))
    log.info(f"[kit world] designed '{design['world']}': {len(design['objects'])} objects, "
             f"{len(design['changes'])} changes, {len(design['events'])} events")
    return design


def validate_design(d: dict) -> list:
    """Every reason this design could not become a world (empty = buildable). The reference storyboard is
    checked with the storyboard validator itself once the vocabulary is written (stage 1)."""
    p = []
    world = d.get("world", "")
    if not _ID.match(world) or world in vocab.worlds():
        p.append(f"world id '{world}' must be new snake_case, 3-25 characters")
    names = [o.get("name", "") for o in d.get("objects") or []]
    if not 6 <= len(names) <= 16:
        p.append(f"{len(names)} objects; 6-16")
    bad = [n for n in names if not re.match(r"^[a-z][a-z0-9_]{2,40}$", n or "") or not n.startswith(world)]
    if bad:
        p.append(f"object names must be snake_case and start with the world id '{world}': {bad}")
    if len(set(names)) != len(names):
        p.append("object names must be unique")
    for o in d.get("objects") or []:
        if any(float(o.get("size_m", {}).get(k, 0)) <= 0 for k in "xyz"):
            p.append(f"object '{o.get('name')}' needs a real size on every axis")
    changes = {c.get("id"): c for c in d.get("changes") or []}
    events = {e.get("id"): e for e in d.get("events") or []}
    if not 4 <= len(changes) <= 8 or "none" in changes:
        p.append("4-8 changes (never one named 'none')")
    if not 6 <= len(events) <= 12:
        p.append("6-12 events")
    firsts = [k for k, c in changes.items() if c.get("first")]
    if firsts != [d.get("first_build")]:
        p.append("exactly one change has first=true and it is first_build")
    flags = {f for c in changes.values() for f in c.get("adds") or []}
    for k, e in events.items():
        missing = [n for n in e.get("needs") or [] if n not in flags]
        if missing:
            p.append(f"event '{k}' needs {missing}, which no change adds")
        unknown = [n for n in e.get("must_see") or [] if n not in names and n != "Max"]
        if unknown or not e.get("must_see"):
            p.append(f"event '{k}' must_see names objects of this world ({unknown or 'none given'})")
    for key in ("calm_event", "finale_event"):
        if (events.get(d.get(key)) or {}).get("outcome") != "hold":
            p.append(f"{key} must be an event with outcome hold")
    if (events.get(d.get("calm_event")) or {}).get("needs"):
        p.append(f"calm_event '{d.get('calm_event')}' happens before anything is built: its needs must be []")
    ids = list(changes) + list(events) + names
    if any(not _ID.match(i or "") and i not in names for i in ids):
        p.append("change and event ids must be snake_case")
    if not p:
        p += [f"reference_storyboard: {x}" for x in _storyboard_problems(d)]
    return p


def _storyboard_problems(d: dict) -> list:
    """The storyboard validator's verdict on the world's Max reference storyboard. Linear no-hero
    explainers have a different 9-13-step contract and are planned later from the same vocabulary."""
    import sys
    import types

    from agents import storyboard as sbm
    from engine.kit import worlds
    world = d["world"]
    name = f"engine.kit.worlds.{world}_vocab"
    module = types.ModuleType(name)
    try:
        exec(compile(vocab_source(d), name, "exec"), module.__dict__)
    except Exception as exc:                              # noqa: BLE001  a design that cannot become data
        return [f"the design does not form a vocabulary: {exc}"]
    previous = sys.modules.get(name)
    sys.modules[name] = module
    worlds.REGISTERED.append(world)
    try:
        ref = module.REFERENCE_STORYBOARD
        return sbm.validate(ref)
    finally:
        worlds.REGISTERED.remove(world)
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous


def vocab_source(d: dict) -> str:
    """The world's vocabulary module (pure data, generated from the design)."""
    world = d["world"]
    changes = {"none": {"does": "nothing new is built"}}
    built = {"none": "nothing new is built"}
    for c in d["changes"]:
        changes[c["id"]] = {"does": c["does"], "adds": list(c.get("adds") or [])}
        if c.get("first"):
            changes[c["id"]]["first"] = True
        built[c["id"]] = c["built"]
    events = {e["id"]: {"outcome": e["outcome"], "shows": e["shows"], "teaches": e["teaches"],
                        "needs": list(e.get("needs") or [])} for e in d["events"]}
    must_see = {e["id"]: list(e["must_see"]) for e in d["events"]}
    ref = dict(d["reference_storyboard"], world=world, gag="none")
    j = lambda value: pprint.pformat(value, width=110, sort_dicts=False)     # noqa: E731  Python literals
    return f'''"""
KIT WORLD {world} (generated by agents/kit_world.py from its design; do not edit by hand).
The vocabulary storyboards in this world may use; engine/kit/worlds/{world}.py stages it.
"""
WORLD = {world!r}
WORLD_CLASS = ("engine.kit.worlds.{world}", {_class_name(world)!r})
FIRST_BUILD = {d["first_build"]!r}
THING = {d["thing"]!r}
CALM = {d["calm_event"]!r}
FINALE_EVENTS = ({d["finale_event"]!r},)
DESCRIPTION = {d["description"]!r}
DESCRIPTION_NO_HERO = {d["description_no_hero"]!r}
NEWS = {d["news"]!r}
FITS = {d["fits"]!r}
REFERENCE_LINES = {{
    "hook_hero": "This is Max. It just went wrong.",
    "hook": "This just went wrong.",
    "setup_hero": "Max had a plan. How hard could it be, really?",
    "setup": "Here is where it starts, before anything is built.",
    "fail": "It failed, because",
    "finale": "Now every fix works together, and it holds. Which fix would you build?",
}}
OBJECTS = {j(d["objects"])}
CHANGES = {j(changes)}
BUILT = {j(built)}
EVENTS = {j(events)}
EVENT_MUST_SEE = {j(must_see)}
WEATHER = ("sunny", "rain", "storm")
GAGS = ("none",)
GAG_DOES = {{}}
EVENT_PROFILES = {{}}
STEP_KINDS = ("setup", "fail", "fix", "finale")
REACTIONS = {{"fail": "shrug", "fix": "cheer", "setup": "point", "finale": "cheer"}}
LABEL_MAX = 18
SECONDS = {{"setup": (3, 6), "fail": (5, 9), "fix": (5, 9), "finale": (4, 7), "hook": (3, 5)}}
REFERENCE_STORYBOARD = {j(ref)}
'''


def write_vocab(d: dict) -> list:
    """Write the vocabulary and check the reference storyboard with the storyboard validator itself (the
    world is not registered yet, so it is checked under a temporary registration)."""
    from agents import storyboard as sbm
    from engine.kit import worlds
    world = d["world"]
    path = os.path.join(WORLDS_DIR, f"{world}_vocab.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(vocab_source(d))
    import importlib
    import sys
    sys.modules.pop(f"engine.kit.worlds.{world}_vocab", None)
    importlib.invalidate_caches()
    worlds.REGISTERED.append(world)
    try:
        ref = vocab.for_world(world).REFERENCE_STORYBOARD
        return sbm.validate(ref)
    finally:
        worlds.REGISTERED.remove(world)


# ------------------- 2. objects -------------------

OBJECTS_GUIDE = """HOW KIT WORLD OBJECTS WORK. Write engine/kit/worlds/{world}_objects.py: one function per object,
build_<name>() -> the object's root (a bpy object; parent every part to it), built at the world origin with
its base centred on (0, 0, 0), at its REAL size in metres (x = left-right, y = depth, z = height), visible.
The staging class places, hides and animates them later; each function only builds.
- Use the production kit: engine/studio.py (terrain with carved cutaways, concrete, water, pipes, pumps,
  houses, labels...), engine/toy.py (primitives, materials, parenting, hide_tree), engine/textures.py
  (real surfaces). Grep for the helper you need and read only its lines; never read a whole module.
- No flat colours on big surfaces (studio / textures materials), every mesh has a material, no text,
  logos or brands. Recognisable at a glance: give each object the detail its "look" names.
- Deterministic: seed any random generator. Blender 5.2 Python. No scene setup, cameras or lights.
- Name every part with the object's name as prefix (e.g. {world}_tank_wall): the measured gates find
  objects by these prefixes.
The pipeline builds each object ALONE and measures it (geometry, size within 0.6x-1.6x of the design,
materials, flat colours), then a reviewer looks at one still of each. Only failing objects come back."""


def objects_prompt(d: dict, problems: dict = None) -> str:
    from agents.set_builder import api_digest
    world = d["world"]
    items = "\n".join(f"- {o['name']}: {o['what']}. Look: {o['look']}. Size (m): x {o['size_m']['x']}, "
                      f"y {o['size_m']['y']}, z {o['size_m']['z']}" for o in d["objects"]
                      if not problems or o["name"] in problems)
    head = (f"Create engine/kit/worlds/{world}_objects.py for the new kit world '{world}' ({d['fits']}).\n"
            if not problems else
            f"Fix ONLY these objects in engine/kit/worlds/{world}_objects.py (every other build function "
            "passed and must stay exactly as it is):\n" + "\n".join(
                f"- {n}: " + "; ".join(issues) for n, issues in problems.items()) + "\n\n")
    return (f"{head}\nTHE OBJECTS:\n{items}\n\nWORLD: {d['description_no_hero']}\n\n"
            f"{OBJECTS_GUIDE.format(world=world)}\n\nAPI REFERENCE (generated from the code):\n{api_digest()}")


LOOK_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["objects"], "properties": {
    "objects": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["name", "recognisable", "problem"],
        "properties": {"name": S, "recognisable": {"type": "boolean"}, "problem": S}}}}}


def check_objects(d: dict, work: str, look_fatal: bool = True) -> dict:
    """{object_name: [issue, ...]} for the objects that fail: measured in Blender, then one vision look.
    With look_fatal=False the look's notes are only logged (the measured checks decide)."""
    from agents import llm
    from engine.make_film import BLENDER, _run_blender
    out = os.path.join(work, "objects")
    os.makedirs(out, exist_ok=True)
    script = os.path.join(PROJECT_ROOT, "engine", "kit", "object_check.py")
    try:
        _run_blender([BLENDER, "--background", "--factory-startup", "--python", script, "--", d["world"], out])
        report = json.load(open(os.path.join(out, "objects.json"), encoding="utf-8"))
    except (RuntimeError, OSError, ValueError) as exc:
        text = str(exc)
        text = text[text.rfind("Traceback"):] if "Traceback" in text else text[-1500:]
        return {"(module)": [f"the objects module failed to load or build: {text[:2500]}"]}
    problems = {n: list(items) for n, items in report["objects"].items() if items}
    stills = [(o["name"], os.path.join(out, f"{o['name']}.png")) for o in d["objects"]
              if o["name"] not in problems and os.path.exists(os.path.join(out, f"{o['name']}.png"))]
    if stills and os.getenv("KIT_WORLD_LOOK", "1") == "1":
        what = "\n".join(f"- {o['name']}: {o['what']} ({o['look']})" for o in d["objects"])
        try:
            look = llm.ask("You check 3D models for an explainer channel.",
                                 f"Each image is one 3D object built for a cutaway diorama, rendered ALONE with a "
                                 f"quick low-quality preview (no scene around it, no final lighting):\n{what}\n\n"
                                 "For each image, say whether a viewer would recognise it as what it is meant to be. "
                                 "Mark recognisable=false only when it reads as something else or as nothing; "
                                 "colour, layer or styling preferences are not failures. If false, give the one "
                                 "concrete thing to change.", LOOK_SCHEMA, images=stills)
            for row in look.get("objects") or []:
                if row.get("name") in dict(stills) and not row.get("recognisable"):
                    note = f"look: {row.get('problem') or 'not recognisable'}"
                    if look_fatal:
                        problems.setdefault(row["name"], []).append(note)
                    else:
                        log.info(f"[kit world] look note (advisory) {row['name']}: {note[6:200]}")
        except Exception as exc:                          # noqa: BLE001  the look is the only advisory part
            from agents.llm import BudgetExceeded, UsageLimit
            if isinstance(exc, (BudgetExceeded, UsageLimit)):
                raise
            log.warning(f"[kit world] object look check unavailable: {exc}")
    return problems


# ------------------- 3. staging -------------------

STAGING_GUIDE = """HOW A KIT WORLD IS STAGED. Write engine/kit/worlds/{world}.py with ONE class {cls} that films ANY
valid storyboard of this world (the planners combine its changes and events freely; no per-video code).
The finished example is engine/kit/embankment.py (EmbankmentSet): grep its methods by name and read only
those ranges (run, _stage_step, _plan, _apply, _setup, _build, _mechanism, _frame, _aim_for, _ev_*).
Mirror its structure:
- class attributes STORYBOARD = None and QA_ALLOW = None; __init__(self, scene, sun, fill, bg, total)
  builds every object with engine/kit/worlds/{world}_objects.py (the tested build_<name>() functions:
  never rebuild an object yourself), positions it in the diorama, hides what is not built yet, owns
  self.rig = CameraRig(), and sets self.hero = self.STORYBOARD.get("hero", True) is not False.
- With a hero, Max = engine.character.Character("Max", look) builds each change on screen and reacts
  (shrug on a fail, cheer on a hold); WITHOUT a hero nobody appears: each part builds itself, framed big.
- run(self, beats, spans, epilogue_offset): exactly like EmbankmentSet.run: every beat names a step or a
  hook; a step plays SETUP (the first 40%: the change being built, or the calm scene) then MECHANISM
  (the event, framed with engine.studio.frame_all around what it shows, its label from
  engine.sets.plane_story.label above the action); a hook replays its step's mechanism on the finished
  state at start + epilogue_offset; then self.rig.build(). A film with no hook beat (build-up explainers)
  just plays its steps.
- A _plan() of the world state before / after the change / after the event for every step (from the
  storyboard alone), and an _apply(state, frame) that cuts the world into a state.
- Every change of the vocabulary is implemented in the build, and every event as _ev_<event>(m0, e, t).
  Its must_see objects (by name prefix) are on screen at the beat's middle and at 7/8, a change is still
  happening at the middle and finished by 7/8, the camera always moves, labels >= 1.8% of the frame height.
- The cut face shows the inside clearly; motivated sounds only (engine.events.add); deterministic.
The pipeline compiles the world's Max reference storyboard and a separate linear no-hero build,
renders previews and MEASURES them (collisions, floating, Max's size, camera motion, flat surfaces,
labels, must_see). Whatever fails comes back to you."""


def staging_prompt(d: dict, problems: str = None) -> str:
    from agents.set_builder import api_digest
    world = d["world"]
    v = vocab.for_world(world)
    changes = "\n".join(f"- {k}: {c['does']} / no hero: {v.BUILT[k]}" for k, c in v.CHANGES.items())
    events = "\n".join(f"- {k} [{e['outcome']}]: {e['shows']} (must_see: {', '.join(v.EVENT_MUST_SEE[k])})"
                       for k, e in v.EVENTS.items())
    head = (f"Write the staging class of the new kit world '{world}'." if not problems else
            f"Fix the staging class of kit world '{world}' (engine/kit/worlds/{world}.py) so these measured "
            f"problems are gone; change nothing that works:\n{problems}")
    return (f"{head}\n\nWORLD (with Max): {v.DESCRIPTION}\nWORLD (no hero): {v.DESCRIPTION_NO_HERO}\n\n"
            f"CHANGES:\n{changes}\n\nEVENTS:\n{events}\n\nREFERENCE STORYBOARD:\n"
            f"{json.dumps(v.REFERENCE_STORYBOARD, indent=1)}\n\n"
            f"{STAGING_GUIDE.format(world=world, cls=_class_name(world))}\n\n"
            f"API REFERENCE (generated from the code):\n{api_digest()}")


def check_staging(world: str) -> str:
    """Compile the Max reference and a 9-step linear construction explainer, preview and measure both.
    Returns the problems as text ("" = verified). These sets are unregistered regression films."""
    from agents import set_builder as sb
    from agents import storyboard as sbm
    from agents.kit_planner import _linear_example
    ref = vocab.for_world(world).REFERENCE_STORYBOARD
    linear = dict(_linear_example(world), hero=False)
    found = []
    for hero, storyboard, set_id in ((True, ref, f"kitw_{world}_ref_story"),
                                     (False, linear, f"kitw_{world}_ref_explainer")):
        set_id = sbm.compile_set(storyboard, set_id)
        work = os.path.join(PROJECT_ROOT, "output", "sets", set_id)
        os.makedirs(work, exist_ok=True)
        who = "with Max" if hero else "no hero"
        err = sb.preview_render(set_id, work)
        if err:
            found.append(f"{who}: Blender failed:\n{err[-2500:]}")
            continue
        try:
            measured = sb.qa_check(set_id, work, strict=True)
        except sb.KitDefect as exc:
            found.append(f"{who}: {exc}")
            continue
        fatal = [f"beat {b}: {x}" for b, items in sorted(measured.items()) for x in items if not sb._advisory(x)]
        if fatal:
            found.append(f"{who}: " + "; ".join(fatal[:12]))
            continue
        # composition, readability and whether the beat shows its story are judged by eye: the measured
        # gates passed a world whose labels filled the frame and whose objects were out of view
        rejected = [r for r in sb.review_preview(set_id, work) if not r.get("valid")]
        if rejected:
            found.append(f"{who}: the reviewer rejected " + "; ".join(
                f"beat {r['beat']} [{r['action']}]: {'; '.join((r.get('fatal_problems') or r.get('problems') or [])[:2])}"
                for r in rejected[:8]))
    return "\n".join(found)


def register_world(world: str) -> None:
    path = os.path.join(WORLDS_DIR, "__init__.py")
    src = open(path, encoding="utf-8").read()
    m = re.search(r"REGISTERED = \[([^\]]*)\]", src)
    names = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    if world not in names:
        names.append(world)
        src = src.replace(m.group(0), "REGISTERED = [" + ", ".join(f'"{n}"' for n in names) + "]")
        open(path, "w", encoding="utf-8").write(src)
    from engine.kit import worlds
    if world not in worlds.REGISTERED:
        worlds.REGISTERED.append(world)


# ------------------- the whole preparation -------------------

def _unfinished_design(topic):
    """The design of a world started earlier for this same topic and not registered yet (a resumed run
    continues its objects and staging instead of designing and paying for a new world)."""
    root = os.path.join(PROJECT_ROOT, "output", "worlds")
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        try:
            design = json.load(open(os.path.join(root, name, "design.json"), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if design.get("topic") == topic and design.get("world") not in vocab.worlds():
            if validate_design(design):                  # a design that broke the rules is designed again
                continue
            log.info(f"[kit world] continuing the world '{design['world']}' started for this topic")
            return design
    return None


def build_world(topic: str, design: dict = None, rounds: int = None, call=None) -> dict:
    """Design, build and verify a new world for `topic`; register it. Resumable: a stage whose files exist
    and pass is not redone. Returns {"accepted", "world", "work", "stage"}."""
    from agents.set_builder import claude_agent
    rounds = rounds or int(os.getenv("KIT_WORLD_ROUNDS") or 4)
    design = design or _unfinished_design(topic) or dict(plan_world(topic, call=call), topic=topic)
    world = design["world"]
    work = os.path.join(PROJECT_ROOT, "output", "worlds", world)
    os.makedirs(work, exist_ok=True)
    json.dump(design, open(os.path.join(work, "design.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    status = {"accepted": False, "world": world, "work": work, "stage": "design"}
    problems = write_vocab(design)
    if problems:
        raise WorldNotBuilt(f"the reference storyboard of '{world}' is not valid: " + "; ".join(problems))
    from engine.kit import worlds
    worlds.REGISTERED.append(world)                    # visible to this process while it is built and checked
    try:
        objects_file = f"engine/kit/worlds/{world}_objects.py"
        status["stage"] = "objects"
        bad = None
        # the vision look gets ONE repair round per world (remembered across resumes); after it the look is
        # advisory: taste on quick isolated stills must not burn the budget the staging needs
        looked = os.path.join(work, "look_repaired")
        for rnd in range(1, rounds + 1):
            if not os.path.exists(os.path.join(PROJECT_ROOT, objects_file)):
                log.info(f"[kit world] '{world}': writing the {len(design['objects'])} objects")
                claude_agent(objects_prompt(design), [objects_file], allow_edit=False, measure=False)
            elif bad:
                log.info(f"[kit world] '{world}' round {rnd}: fixing {len(bad)} object(s): {', '.join(bad)}")
                claude_agent(objects_prompt(design, bad), [objects_file], allow_edit=False, measure=False)
                if any(x.startswith("look:") for items in bad.values() for x in items):
                    open(looked, "w").close()
            bad = check_objects(design, work, look_fatal=not os.path.exists(looked))
            if not bad:
                log.info(f"[kit world] '{world}': every object passed on its own")
                break
            log.info(f"[kit world] '{world}' round {rnd}: {len(bad)} object(s) failed: {json.dumps(bad)[:600]}")
        if bad:
            return status
        staging_file = f"engine/kit/worlds/{world}.py"
        status["stage"] = "staging"
        problems = None
        for rnd in range(1, rounds + 1):
            if not os.path.exists(os.path.join(PROJECT_ROOT, staging_file)):
                log.info(f"[kit world] '{world}': writing the staging class")
                claude_agent(staging_prompt(design), [staging_file], allow_edit=False, measure=False)
            elif problems:
                log.info(f"[kit world] '{world}' round {rnd}: repairing the staging")
                claude_agent(staging_prompt(design, problems), [staging_file, objects_file], measure=False)
            problems = check_staging(world)
            if not problems:
                break
            log.info(f"[kit world] '{world}' round {rnd}: staging problems: {problems[:600]}")
        if problems:
            return status
    finally:
        worlds.REGISTERED.remove(world)
    register_world(world)
    status.update(accepted=True, stage="registered")
    log.info(f"[kit world] '{world}' verified and registered: storyboards can now be filmed in it")
    return status


def ensure_world(topic: str, run_event=None) -> str:
    """The world for a topic: an existing one, or a new one built and verified now. Raises WorldNotBuilt."""
    world = world_for(topic)
    if world:
        return world
    if not auto_build():
        raise WorldNotBuilt(f"no kit world can film '{topic}' and SHOWRUNNER_AUTO_BUILD_WORLDS=0")
    if run_event:
        run_event("set", "no kit world fits this topic; preparing a new world before any video", detail=topic[:200])
    status = build_world(topic)
    if not status["accepted"]:
        raise WorldNotBuilt(f"the new world '{status['world']}' did not pass its {status['stage']} checks; "
                            f"see {status['work']} (run again to continue)")
    return status["world"]
