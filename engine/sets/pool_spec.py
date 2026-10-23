"""
What the POOL cutaway set can show — pure data (no Blender), read by the script writer
(agents/showrunner.py) and enforced by the renderer (engine/sets/pool.py).

A film is a list of beats; every beat names one ACTION from this catalogue. The writer chooses
the angle, the narration and the order of the optional explainer actions; the set guarantees
the visuals. Facts listed here are what the 3D model actually shows (keep narration consistent
with them — e.g. the model's walls ARE 20 cm thick).
"""

SET_ID = "pool"
SUBJECT = "an in-ground concrete (shotcrete/gunite) backyard swimming pool, cut open lengthwise"

MODEL_FACTS = {
    "pool size": "6 m long x 3 m wide, 1.5 m deep inside (the cut shows half its width)",
    "excavation": "1.8 m deep hole; about 50 tons of soil removed",
    "layers under the lawn": "topsoil, clay, sand, then rock; groundwater at about 3.4 m (can rise)",
    "floor build-up": "10 cm gravel bed, 20 cm concrete shell, 3 cm plaster",
    "rebar": "steel bars on a ~25 cm grid in floor and walls",
    "walls": "20 cm thick sprayed concrete (shotcrete)",
    "water": "about 20,000 liters = about 20 tons",
    "plumbing": "main drain in the floor, skimmer at the waterline, return jets in the walls, "
                "pump + sand filter on a pad beside the pool",
    "relief valve": "hydrostatic relief valve in the floor (opens if groundwater pushes up)",
    "turnover": "the pump filters the whole volume about every 6 hours",
}

# Build steps happen in this order and are ALL required (the set's state depends on them).
BUILD_ORDER = ["dig", "gravel", "valve", "pipes", "rebar", "shotcrete", "cure", "finish", "fill"]

ACTIONS = {
    # ---- hooks (rendered from the finished pool, shown FIRST, before the rewind) ----
    "float_hook": {"kind": "hook", "shows": "A drained pool in a storm: groundwater rises in the soil and the whole "
                   "concrete pool lifts out of the ground. Rain, dark sky, up-arrows, GROUNDWATER label."},
    "flow_hook": {"kind": "hook", "shows": "The finished pool, full and sparkling, cut open: water visibly racing "
                  "through hidden clear pipes under the lawn to the pump and back. Caustics on the walls."},
    "reveal_hook": {"kind": "hook", "shows": "The finished pool on a sunny day; the camera pushes in from wide to "
                    "a close-up of the cut-open wall: plaster, 20 cm of concrete with rebar dots, gravel, soil "
                    "layers. A dimension line reads 20 cm."},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, then the whole build plays BACKWARDS at "
               "speed (VHS look) down to bare lawn. Narration: a one-line bridge into the build."},
    # ---- build (required, in BUILD_ORDER) ----
    "dig": {"kind": "build", "shows": "A mini excavator behind the cut bites the lawn; soil columns drop away in "
            "section; a spoil pile grows.", "seconds": (4.5, 7)},
    "gravel": {"kind": "build", "shows": "A gravel bed spreads across the floor of the hole (section view).",
               "seconds": (3, 5)},
    "valve": {"kind": "build", "shows": "Close-up: a brass hydrostatic relief valve set into the floor; blue arrows "
              "show groundwater pushing up through it. 3D label RELIEF VALVE.", "seconds": (4, 7)},
    "pipes": {"kind": "build", "shows": "Clear pipes appear in the section from the floor drain and skimmer, under the "
              "lawn, to the pump pad; return line to the wall jets. Labels MAIN DRAIN, SKIMMER.",
              "seconds": (4, 7)},
    "rebar": {"kind": "build", "shows": "A steel rebar grid builds bar by bar over floor and walls; a dimension line "
              "reads 25 cm.", "seconds": (3, 6)},
    "shotcrete": {"kind": "build", "shows": "Concrete sprays onto the walls; the shell grows over the rebar; a "
                  "dimension line shows the 20 cm wall in section.", "seconds": (4, 6)},
    "cure": {"kind": "build", "shows": "Day/night time-lapse over the cutaway (sun sweeps, night falls twice); a "
             "sprinkler mists the concrete each morning.", "seconds": (3, 6)},
    "finish": {"kind": "build", "shows": "Blue waterline tiles, stone coping, a smooth plaster layer (label PLASTER) "
               "and a stainless ladder appear.", "seconds": (3, 6)},
    "fill": {"kind": "build", "shows": "A hose fills the pool; water rises in section; caustics start dancing on "
             "the plaster.", "seconds": (4, 7)},
    # ---- explainers (optional, after their prerequisite) ----
    "layers": {"kind": "explain", "after": "dig", "shows": "The camera glides down the soil face; labels pop: "
               "TOPSOIL, CLAY, SAND, GROUNDWATER (blue, at the bottom).", "seconds": (3, 6)},
    "weight": {"kind": "explain", "after": "fill", "shows": "Yellow down-arrows on the water versus blue up-arrows "
               "from the groundwater; the down-arrows win.", "seconds": (3, 6)},
    "flow": {"kind": "explain", "after": "fill", "shows": "Water stripes race through the clear pipes: drain and "
             "skimmer, to the pump, through the filter, back out the jets. Labels PUMP, FILTER.",
             "seconds": (4, 8)},
    "cycle": {"kind": "explain", "after": "flow", "shows": "Wide pull-back over the whole working cutaway.",
              "seconds": (2, 5)},
    # ---- outros (optional, last) ----
    "storm": {"kind": "outro", "shows": "Storm rolls in: rain, the sky darkens, the groundwater rises toward the "
              "pool (sets up the float hook as a loop).", "seconds": (3, 6)},
    "glamour": {"kind": "outro", "shows": "Sunny wide shot of the finished pool, water shimmering, camera settling "
                "on the hook framing.", "seconds": (2, 5)},
}

# 2D sticker overlays the writer may put on ANY beat (drawn in post): a counting stat or a label.
OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'50 tons','text':'of soil'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Relief valve'}"}


WORDS_PER_SECOND = 2.6


def beat_actions(beat: dict) -> list:
    """A beat plays one action, or a quick montage of several (`actions`: up to 4)."""
    return list(beat.get("actions") or [beat.get("action")])


def min_seconds(beat: dict) -> float:
    return sum(ACTIONS.get(a, {}).get("seconds", (0, 0))[0] for a in beat_actions(beat))


def validate(beats: list) -> list:
    """Problems with a beat list (empty = renderable)."""
    errs = []
    for k, b in enumerate(beats):
        acts_k = beat_actions(b)
        if not 1 <= len(acts_k) <= 4:
            errs.append(f"beat {k + 1} has {len(acts_k)} actions; 1-4 allowed")
        kinds = {ACTIONS.get(a, {}).get("kind") for a in acts_k}
        if len(acts_k) > 1 and kinds & {"hook", "rewind"}:
            errs.append(f"beat {k + 1}: hook and rewind beats play a single action")
    acts = [a for b in beats for a in beat_actions(b)]
    unknown = [a for a in acts if a not in ACTIONS]
    if unknown:
        errs.append(f"unknown actions: {unknown}")
    if len(beats) < 2 or ACTIONS.get(acts[0], {}).get("kind") != "hook":
        errs.append("beat 1 must be a hook action (float_hook or flow_hook)")
    if len(beats) < 2 or acts[1] != "rewind":
        errs.append("beat 2 must be 'rewind'")
    build = [a for a in acts if ACTIONS.get(a, {}).get("kind") == "build"]
    if build != BUILD_ORDER:
        errs.append(f"build actions must appear exactly once each, in order: {BUILD_ORDER} (got {build})")
    for i, a in enumerate(acts):
        spec = ACTIONS.get(a, {})
        if spec.get("kind") == "explain":
            pre = spec["after"]
            if pre not in acts[:i]:
                errs.append(f"'{a}' must come after '{pre}'")
        if spec.get("kind") == "outro" and i != len(acts) - 1:
            errs.append(f"outro '{a}' must be the last beat")
        if spec.get("kind") in ("hook", "rewind") and i > 1:
            errs.append(f"'{a}' can only open the film")
    if len(set(acts)) != len(acts):
        errs.append("each action may be used once")
    return errs
