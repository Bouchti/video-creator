"""
BOAT STORY set — Max builds a steel boat by trial and error. Each naive attempt fails for a real
physical reason; each fix is the real naval engineering. Pure data (no Blender), read by the
showrunner and enforced by engine/sets/boat_story.py.
"""

SET_ID = "boat_story"
SUBJECT = ("Max, a well-meaning, overconfident DIY dad (orange hard hat, big mustache), builds a steel boat to "
           "take his kids across the lake, shown side-on as a 3D cutaway diorama: the lake is sliced open so we "
           "see above AND below the waterline, and the hull is cut open to show inside it")
HERO = "Max"

MODEL_FACTS = {
    "the boat": "a small welded steel workboat, about 4.5 m long and 1.7 m wide",
    "why the slab sank": "steel is about eight times denser than water; a solid block of it weighs far more than "
                         "the water it pushes aside, so it sinks",
    "Archimedes": "anything in water is pushed up by a force equal to the weight of the water it pushes aside "
                  "(displaces). A hollow hull made of the same steel encloses lots of air, so it pushes aside "
                  "its own weight in water before it is fully under, and floats",
    "why it capsized": "a tall, heavy cabin and mast raise the centre of gravity; when the boat tilts, its weight "
                       "and the buoyancy twist it further over instead of back",
    "keel": "a heavy keel with a lead weight low under the hull keeps the centre of gravity low, so when it "
            "tilts, weight and buoyancy twist it back upright (that's why sailboats can lean so far)",
    "why the leak sank it": "one hole lets water flood the whole open hull; the boat gets heavier, sits lower, and "
                            "once water comes over the side it sinks",
    "bulkheads": "watertight walls (bulkheads) split the hull into compartments, so a leak floods only one of "
                 "them and the rest keeps it afloat; a bilge pump pushes the leaking water back out (the "
                 "Titanic had compartments too; it sank because too many flooded)",
    "why it drifted": "without an engine the boat has no way to push against the water, so wind and current "
                      "decide where it goes",
    "propeller and rudder": "a propeller is a spinning set of angled blades that throws water backwards; the "
                            "water pushes the boat forwards (action and reaction). The rudder deflects that flow "
                            "to one side to turn the boat",
    "the numbers on screen": "the slab: about 4.7 tonnes of steel, but it only pushes aside 0.6 tonnes of water, so "
                             "its weight beats the push-up 8 to 1. The finished boat weighs about 1.2 tonnes and "
                             "floats once it has pushed aside 1.2 tonnes of water (1.2 cubic metres)",
    "wow facts": "the biggest container ships weigh over 200,000 tonnes loaded and float for exactly the same "
                 "reason; an aircraft carrier is about 100,000 tonnes of mostly steel; the Titanic had 16 "
                 "watertight compartments and could float with 4 flooded, but 6 flooded; a boat's red bottom paint "
                 "(antifouling) stops barnacles and weed growing on the hull",
}

STORY_ORDER = ["build_slab", "fail_sink", "hull", "fail_capsize", "keel", "fail_leak", "bulkheads", "fail_drift",
               "propeller", "finale"]

ACTIONS = {
    # ---- hooks (staged after the finale, shown FIRST, before the rewind) ----
    "sink_hook": {"kind": "hook", "shows": "Max stands proudly on his solid steel 'boat' as it sinks straight down "
                  "under him, bubbles everywhere, until only his hard hat is above the water. He blinks."},
    "cruise_hook": {"kind": "hook", "shows": "Payoff first: Max's steel boat cruises across the lake with his two "
                    "kids aboard, waving and cheering."},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the whole story plays BACKWARDS (VHS "
               "look) to an empty dock. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "build_slab": {"kind": "story", "shows": "At his dock Max welds a big solid slab of steel (sparks flying), "
                   "pats it proudly: his boat.", "seconds": (3.5, 6)},
    "fail_sink": {"kind": "fail", "shows": "He shoves it off the dock: it sinks straight to the bottom like a "
                  "stone (the camera follows it down through the water) and thuds into the sand. Force arrows "
                  "appear on it: a HUGE orange WEIGHT arrow pointing down, a TINY blue BUOYANCY arrow pointing up "
                  "(the weight wins 8 to 1). Max stares at the bubbles.", "seconds": (4, 7)},
    "hull": {"kind": "fix", "shows": "The same steel welded into a hollow hull full of air: it floats. Now the "
             "WEIGHT and BUOYANCY arrows are the SAME size. Then the water the hull pushed aside rises out of the "
             "lake as a glowing blue block next to the boat, labelled with its weight, equal to the boat's "
             "weight (the aha: a boat sinks until it has pushed aside its own weight in water).",
             "seconds": (5, 8)},
    "fail_capsize": {"kind": "fail", "shows": "Max bolts a tall cabin and a mast on top and climbs onto the cabin "
                     "roof; a yellow-and-black CENTRE OF GRAVITY marker climbs up with him. The boat leans, leans "
                     "more, and flips over with a big splash. Max pops up in the water with a fish on his hard hat.",
                     "seconds": (4, 7)},
    "keel": {"kind": "fix", "shows": "A heavy keel with a lead bulb is welded under the hull and the CENTRE OF "
             "GRAVITY marker drops right down into it. A wave rolls the boat hard over and it swings back upright "
             "by itself, like a wobbly toy that always stands up.", "seconds": (4, 7)},
    "fail_leak": {"kind": "fail", "shows": "A rivet pops in the bottom: water sprays in, floods the whole hull, the "
                  "boat sinks lower and lower while Max bails frantically with a bucket.", "seconds": (4, 7)},
    "bulkheads": {"kind": "fix", "shows": "Watertight steel walls divide the hull into compartments; the same leak "
                  "now floods only the middle one, the boat stays up, and Max works a hand bilge pump that spits "
                  "the water back over the side. Labels: WATERTIGHT WALLS, BILGE PUMP.", "seconds": (4, 7)},
    "fail_drift": {"kind": "fail", "shows": "Out on the lake with no engine, the wind pushes the boat into the reeds "
                   "while Max paddles with his hands, getting nowhere, and a duck paddles past faster than him.",
                   "seconds": (3.5, 6)},
    "propeller": {"kind": "fix", "shows": "Close-up underwater: an engine turns a brass propeller; blue arrows show "
                  "the water thrown BACKWARDS and a yellow arrow shows the boat pushed FORWARDS (action and "
                  "reaction); the camera pulls back as the boat surges off, the rudder swinging to steer.",
                  "seconds": (4, 7)},
    "finale": {"kind": "story", "shows": "Sunny. Max's kids aboard, they cruise across the lake together, everyone "
               "waving; behind them a GIANT container ship glides by and sounds its horn, labelled with its "
               "200,000 tonnes (it floats by the very same trick). (The ending: Max's boat floats, stays up, "
               "stays dry and goes where he wants.)", "seconds": (6, 9)},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'8x','text':'denser than water'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Buoyancy'} (names a part or idea, never a count)"}
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
        errs.append("beat 1 must be a hook action (sink_hook or cruise_hook)")
    if len(acts) < 2 or acts[1] != "rewind":
        errs.append("beat 2 must be 'rewind'")
    story = [a for a in acts if ACTIONS.get(a, {}).get("kind") in ("story", "fail", "fix")]
    if story != STORY_ORDER:
        errs.append(f"story actions must appear exactly once each, in order: {STORY_ORDER} (got {story})")
    for i, a in enumerate(acts):
        spec = ACTIONS.get(a, {})
        if spec.get("kind") in ("hook", "rewind") and i > 1:
            errs.append(f"'{a}' can only open the film")
    if len(set(acts)) != len(acts):
        errs.append("each action may be used once")
    return errs
