"""
BACKYARD WATER TOWER set: a sunny backyard cutaway played as a TRIAL-AND-ERROR comedy. Max wants a
kids' water slide that gushes "like a real town", with no noisy pump running. He builds his own
backyard water tower: a 1,000 L tank (a 1.2 m cube) that has to be lifted, held up, kept from
overflowing and vented. Each attempt FAILS for one real physical reason and each FIX is the real
engineering answer. Pure data (no Blender), read by the showrunner and enforced by
engine/sets/s_backyard_water_tower_raise_story.py.
"""

SET_ID = "s_backyard_water_tower_raise_story"
SUBJECT = ("Max, a well-meaning, overconfident DIY dad (orange hard hat, big mustache), builds a backyard water "
           "tower to feed his kids' 3 m water slide, shown as a 3D cutaway of a sunny backyard (the ground sliced "
           "open to show the buried pipes, the well and the tower footings), with a pressure gauge at the bottom")
HERO = "Max"

MODEL_FACTS = {
    "the yard": "about 10 m wide: a small well pump, a buried supply pipe, the tank tower, a 3 m kids' water slide, "
                "a cutaway house wall with a garden tap",
    "the tank": "1,000 litres in a 1.2 m galvanised steel cube",
    "the weight": "1,000 litres of water weigh one tonne (1,000 kg)",
    "pressure from height": "every metre of water height adds about 0.1 bar at the bottom; 6 m gives about 0.6 bar",
    "why the tank on the grass failed": "water cannot rise above its own surface: the tank's surface was 1.2 m up, "
                                        "the slide top 3 m, so the water in the hose stopped at 1.2 m; gauge ~0",
    "the fix for no pressure": "lift the tank: its water surface must sit well above the slide top (6 m up)",
    "why the thin poles failed": "four thin wooden poles 6 m tall buckle under a tonne: long slender columns bow "
                                 "sideways and fold long before the wood is crushed",
    "the fix for the weight": "steel legs with diagonal cross-bracing (triangles do not change shape) bolted to "
                              "buried concrete footings, so the load goes straight down into the ground",
    "why it overflowed": "a pump with nothing to stop it keeps filling until the tank spills over the top",
    "the fix for overflow": "a float valve: a ball on an arm rises with the water and closes the inlet when full; "
                            "an overflow pipe takes any extra water safely down to the ground",
    "why the sealed tank crumpled": "an airtight lid lets nothing replace the water draining out: the pressure inside "
                                    "drops and the outside air (about 1 bar, roughly 10 tonnes per square metre) "
                                    "pushes the thin walls in",
    "the fix for vacuum": "a screened vent pipe on the lid lets air flow in as the water flows out, so inside and "
                          "outside pressure stay equal (the screen keeps birds and bugs out)",
    "real towns": "New York still has about 10,000 wooden rooftop tanks of about 10,000 gallons each, because old "
                  "city water pressure only reached about the sixth floor",
}

# The story is a ladder: these happen in this order, all required (the set's state depends on it).
STORY_ORDER = ["fail_ground", "raise_tank", "fail_poles", "steel_legs", "fail_overflow", "float_valve",
               "fail_vacuum", "fix_vent", "finale"]

ACTIONS = {
    # ---- hooks (staged after the story, shown FIRST, before the rewind) ----
    "crash_hook": {"kind": "hook", "seconds": (2.5, 4),
                   "shows": "Already falling at the first frame: the full one-tonne tank on four thin wooden poles "
                            "folds them and crashes into the flower bed with a giant splash.",
                   "must_see": ["tank_shell", "pole", "Max"],
                   "extras": "Max gasps, mouth wide open, beside the gauge post.",
                   "ambience": "outdoor"},
    "slide_hook": {"kind": "hook", "seconds": (2.5, 4),
                   "shows": "Sunny payoff already moving at frame 1: the two kids whoosh down the gushing water "
                            "slide under the finished tower.",
                   "must_see": ["slide_chute", "Kid1", "Max"],
                   "extras": "Max cheers with both arms up beside the slide.",
                   "ambience": "outdoor"},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the story plays BACKWARDS (VHS look) to the "
               "bare yard. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "fail_ground": {"kind": "fail", "seconds": (5, 8),
                    "shows": "The 1.2 m tank on the grass; in the clear hose up the 3 m slide the water stops at the "
                             "tank's own level (blue WATER LEVEL line); the gauge reads near zero.",
                    "must_see": ["tank_shell", "hose_up", "gauge_dial", "Max"],
                    "extras": "Max hauls the hose, then shrugs at the dry slide.",
                    "ambience": "outdoor"},
    "raise_tank": {"kind": "fix", "seconds": (5, 8),
                   "shows": "The tank rises to 6 m; the pressure arrow at the gauge grows longer with every metre "
                            "(+0.1 BAR PER METRE, then 0.6 BAR) and the slide starts to gush.",
                   "must_see": ["tank_shell", "gauge_dial", "press_arrow", "Max"],
                   "extras": "The tank goes up on four thin wooden poles; Max throws both arms up in a V.",
                   "ambience": "outdoor"},
    "fail_poles": {"kind": "fail", "seconds": (5, 8),
                   "shows": "Filled to the brim (1 TONNE), the four thin wooden poles bow, sway and fold, and the "
                            "tank crashes into the flower bed with a splash.",
                   "must_see": ["tank_shell", "pole", "Max"],
                   "extras": "Max gasps once, then shrugs; the owl flaps away from the splash; the broken poles "
                             "topple back onto the lawn.",
                   "ambience": "outdoor"},
    "steel_legs": {"kind": "fix", "seconds": (5, 8),
                   "shows": "Steel legs with diagonal cross-braces (triangles) on concrete footings seen in the "
                            "cutaway; yellow LOAD PATH arrows run down the legs into the ground.",
                   "must_see": ["steel_leg", "brace", "footing", "Max"],
                   "extras": "Max bolts the footings with a wrench; the tank is lowered onto the top frame.",
                   "ambience": "outdoor"},
    "fail_overflow": {"kind": "fail", "seconds": (5, 8),
                      "shows": "The fill pump runs, the tank fills to the brim and spills over the top, down the "
                               "tower onto Max's hard hat (NO SHUT-OFF).",
                      "must_see": ["tank_shell", "spill", "Max"],
                      "extras": "Max flips the pump switch, strolls off with a lemonade, gasps and jumps when the "
                                "water lands on him.",
                      "ambience": "outdoor"},
    "float_valve": {"kind": "fix", "seconds": (5, 8),
                    "shows": "Inside the cut-open tank a float ball on an arm rises with the water and shuts the "
                             "inlet stream (FLOAT VALVE); an overflow pipe leaves the top.",
                    "must_see": ["tank_shell", "float_ball", "Max"],
                    "extras": "Max stands on the tower balcony beside the tank, holds up the float, then cheers.",
                    "ambience": "outdoor"},
    "fail_vacuum": {"kind": "fail", "seconds": (5, 8),
                    "shows": "With an airtight lid bolted on, water drains out of the cut-open tank, red outside-air "
                             "arrows push in (VACUUM) and the tank walls crumple inward with a bang.",
                    "must_see": ["tank_shell", "vac_arrow", "Max"],
                    "extras": "Max bolts the lid to keep the owl out; the kids open the slide valve; Max gasps.",
                    "ambience": "outdoor"},
    "fix_vent": {"kind": "fix", "seconds": (5, 8),
                 "shows": "A screened vent pipe on the lid of a new tank: an AIR IN arrow flows into the vent as the "
                          "water level drops, and the tank stays square.",
                 "must_see": ["tank_shell", "vent", "air_in", "Max"],
                 "extras": "Max fits the vent on the balcony; the slide gushes below while the kids play.",
                 "ambience": "outdoor"},
    "finale": {"kind": "story", "seconds": (5, 9),
               "shows": "The working tower feeds a gushing slide; the two kids whoosh down one after the other; "
                        "Max cheers.",
               "must_see": ["slide_chute", "Kid1", "Max"],
               "extras": "Max checks the gauge at 0.6 bar first; the owl finally sits on the vent screen.",
               "ambience": "outdoor"},
    # ---- optional explainer ----
    "city_tanks": {"kind": "explain", "after": "fix_vent", "seconds": (4, 7),
                   "shows": "A tabletop New York skyline model with wooden rooftop water tanks (10,000 GAL); a blue "
                            "line marks the sixth floor, where old city pressure ran out.",
                   "must_see": ["city_model", "Max"],
                   "extras": "Max points at the little rooftop tanks.",
                   "ambience": "outdoor"},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'0.6 bar','text':'from 6 m'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Float valve'} (names a part, never a number)"}
WORDS_PER_SECOND = 2.4


def beat_actions(beat: dict) -> list:
    return list(beat.get("actions") or [beat.get("action")])


def min_seconds(beat: dict) -> float:
    return sum(ACTIONS.get(a, {}).get("seconds", (0, 0))[0] for a in beat_actions(beat))


def validate(beats: list) -> list:
    errs = []
    for k, b in enumerate(beats):
        acts_k = beat_actions(b)
        if not 1 <= len(acts_k) <= 3:
            errs.append(f"beat {k + 1} has {len(acts_k)} actions; 1-3 allowed")
        kinds = {ACTIONS.get(a, {}).get("kind") for a in acts_k}
        if len(acts_k) > 1 and kinds & {"hook", "rewind", "fail"}:
            errs.append(f"beat {k + 1}: hooks, the rewind and failures play as single-action beats")
    acts = [a for b in beats for a in beat_actions(b)]
    unknown = [a for a in acts if a not in ACTIONS]
    if unknown:
        errs.append(f"unknown actions: {unknown}")
    if not beats or ACTIONS.get(acts[0], {}).get("kind") != "hook":
        errs.append("beat 1 must be a hook action (crash_hook or slide_hook)")
    if len(acts) < 2 or acts[1] != "rewind":
        errs.append("beat 2 must be 'rewind'")
    story = [a for a in acts if ACTIONS.get(a, {}).get("kind") in ("story", "fail", "fix")]
    if story != STORY_ORDER:
        errs.append(f"story actions must appear exactly once each, in order: {STORY_ORDER} (got {story})")
    for i, a in enumerate(acts):
        spec = ACTIONS.get(a, {})
        if spec.get("kind") == "explain" and spec["after"] not in acts[:i]:
            errs.append(f"'{a}' must come after '{spec['after']}'")
        if spec.get("kind") in ("hook", "rewind") and i > 1:
            errs.append(f"'{a}' can only open the film")
    if len(set(acts)) != len(acts):
        errs.append("each action may be used once")
    return errs
