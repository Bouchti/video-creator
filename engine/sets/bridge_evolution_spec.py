"""
BRIDGE EVOLUTION set — an "evolution" film: every bridge is the answer to the real limit of the
one before. Planks snap under a wagon of stone → the stone arch carries it; the railway must cross
the wide river downstream where tall ships sail, and arches there would put piers in their path →
the steel truss; the city must cross the bay at the river mouth, and a truss that long would sag under
its own weight → the suspension bridge; then summer heat → expansion joints, and wind → a stiffening
truss. Second-person narration ("You've built a bridge..."), no hero, no hook/rewind.

The river NEVER widens on screen: a longer bridge is always a new crossing further downstream, reached
by a hard cut, and an old bridge is never destroyed for no reason (it stays behind upstream).

Pure data (no Blender), read by agents/evolution_writer.py and enforced by
engine/sets/bridge_evolution.py.
"""

SET_ID = "bridge_evolution"
FORMAT = "evolution"
SUBJECT = ("The evolution of the bridge, told along one river seen from drone height: a thatched village by a "
           "6 m stream, then the 40 m river downstream where the railway must cross among tall ships, then the "
           "bay at the river mouth that the city must cross. Every new bridge fixes the real limit of the last")

MODEL_FACTS = {
    "the crossings": "the village stream is 6 m wide (planks, then the stone arch at the SAME spot); the railway "
                     "crossing downstream is about 40 m wide with tall sailing ships; the bay at the river mouth "
                     "is drawn scaled down: never quote its width, talk about crossing a whole bay",
    "never say": "the river never 'gets wider' and a bridge never falls down because the river moved. Each "
                 "problem is a NEW LOAD or a NEW NEED (a heavy wagon, a railway among tall ships, a whole bay, "
                 "summer heat, wind)",
    "plank bridge": "planks on log beams across the gap (a simple beam bridge). Fine for people and a hand cart. "
                    "Under a heavy load a beam bends: its top squeezes and its bottom stretches, and wood (and "
                    "stone) breaks when it is stretched, so it snaps from the bottom. Timber beams rarely span "
                    "more than about 10 m",
    "stone arch": "wedge-shaped stones (voussoirs) laid in a curve; the top stone is the keystone. An arch turns "
                  "the load into pure squeezing (compression), which stone handles brilliantly, so it carries "
                  "the same heavy wagon easily; Roman arches like the Pont du Gard still stand after 2,000 years. "
                  "The arch pushes outwards at its feet, so it needs solid ground on both sides",
    "why the arch stops": "a single stone arch has to rise higher the longer it spans, and stone is so heavy that "
                          "long crossings were built as a row of arches on piers standing in the river; at a "
                          "busy river those piers stand in the ships' path and the arches are lower than their "
                          "masts. Railways (from the 1830s) needed long, level crossings that could carry trains",
    "steel truss": "a frame of steel bars joined in triangles. A triangle cannot change shape without changing "
                   "the length of a side, while a square folds into a diamond (a parallelogram) under a push. "
                   "So every bar in a truss is only pulled or pushed along its length, and very little steel "
                   "carries a lot of load: one light, rigid span over the whole river. Railway truss bridges "
                   "span 50-150 m",
    "why the truss stops": "the longer a truss gets, the deeper and heavier it must be, and soon most of its "
                           "strength goes into holding up its own weight; for a crossing of a kilometre or more "
                           "a truss is far too heavy",
    "suspension": "two tall towers carry main cables that hang in a curve and are anchored into the ground at "
                  "both ends; vertical hangers drop from the cables and hold the road deck. The cables only "
                  "pull (tension), and steel wire is extremely strong in tension, so a light deck can hang across "
                  "a huge gap. The Golden Gate main span is 1,280 m; the 1915 Canakkale Bridge in Turkey (2022) "
                  "spans 2,023 m, the longest in the world",
    "heat": "steel grows about 1.2 mm per metre for every 100 C, so a 1 km steel deck gets about 40 cm "
            "longer between a winter night and a summer afternoon. Trapped between rigid ends it has nowhere "
            "to go and buckles",
    "expansion joint": "a gap in the deck bridged by interlocking steel fingers (or sliding plates) that lets "
                       "the deck grow and shrink freely; on long bridges these joints let the deck slide back "
                       "and forth by tens of centimetres every day",
    "wind": "wind flowing past a thin, flexible deck sheds swirling vortices that can push it into a growing "
            "twist (flutter). In 1940 the Tacoma Narrows Bridge twisted itself apart in a 64 km/h wind",
    "stiffening truss": "a deep truss built along and under the deck (or an aerodynamic box shape) makes the "
                        "deck very stiff against twisting and lets the wind slip past, so it stays calm",
    "wow facts": "the Golden Gate's two main cables hold about 129,000 km of steel wire, enough to wrap the "
                 "Earth three times; big suspension bridges are designed to move, swinging metres sideways "
                 "in a storm without harm; Roman stone arches still carry traffic today",
}

STAGE_ORDER = ["plank", "heavy_load", "arch", "railway", "truss", "wide_bay", "suspension",
               "heat", "expansion_joint", "wind", "stiffening", "finale"]

ACTIONS = {
    # stage = a new bridge (or fix) is built; problem = a new load or need it can't handle; outro = the ending
    "plank": {"kind": "stage", "shows": "Drone shot over a thatched village by a narrow stream in a forest. Wooden "
              "planks drop into place one by one on log beams across the 6 m stream; a light hand cart rolls "
              "across without trouble.", "seconds": (3.5, 6)},
    "heavy_load": {"kind": "problem", "shows": "The same 6 m stream. A wagon heaped with cut stone rolls onto the "
                   "planks; the deck bows deeper as it nears the middle (orange arrows: the top squeezes inwards, "
                   "the bottom stretches outwards), then snaps under it: both halves swing down from the banks "
                   "into the water and the wagon drops into the stream with a splash.", "seconds": (3.5, 6)},
    "arch": {"kind": "stage", "shows": "At the same stream, cut stones fly in one by one from both banks and lock "
             "into a curved stone arch; the keystone drops in last at the top with a thud, then the road on top "
             "fills in. Glowing orange arrows show the weight pushed down and out along the curve into the banks, "
             "while a second stone wagon rolls straight across.", "seconds": (4, 7)},
    "railway": {"kind": "problem", "shows": "Hard cut downstream: the river is now 40 m wide. A steam train rolls "
                "along the left bank and stops where its rails end at the water; a tall sailing ship glides up the "
                "river. A white sketch draws the row of stone arches this crossing would need, with orange piers "
                "standing in the river right in the ship's path; then it fades.", "seconds": (3.5, 6)},
    "truss": {"kind": "stage", "shows": "A red steel truss bridge assembles bar by bar across the 40 m river, all "
              "triangles, in one span with nothing in the water. A white line-drawing appears in the sky: a "
              "TRIANGLE stays rigid while a SQUARE is pushed and folds into a diamond. The waiting train crosses; "
              "the ship sails on.", "seconds": (4.5, 8)},
    "wide_bay": {"kind": "problem", "shows": "Hard cut to the river mouth: a whole bay, far wider. Cars queue at the "
                 "shore where the road ends. A white sketch draws a truss long enough to span the bay; it bows "
                 "deeper and deeper until it sags into the water under its own weight, then fades. The camera "
                 "pulls back high to show the whole gap.", "seconds": (3.5, 6)},
    "suspension": {"kind": "stage", "shows": "Two orange towers rise out of the water; the main cables draw "
                   "themselves from bank to tower to tower to bank in a big curve; vertical hangers drop down and "
                   "the road deck slides out from the towers until it joins in the middle. Cars start crossing.",
                   "seconds": (5, 9)},
    "heat": {"kind": "problem", "shows": "The sun blazes, the image warms up, the steel deck grows and, trapped "
             "between its ends, buckles up into a peak in the middle with puffs of dust; a car stops short.",
             "seconds": (3, 6)},
    "expansion_joint": {"kind": "stage", "shows": "Close-up on the deck: a gap with interlocking steel fingers "
                        "is outlined by a white line-drawn box; the deck slides in and out through it as it heats "
                        "and cools, and stays flat.", "seconds": (3.5, 6)},
    "wind": {"kind": "problem", "shows": "White wind streaks blow across the valley; the thin deck starts to sway "
                                         "and twist in a growing wave along its length, cables swinging.",
             "seconds": (3, 6)},
    "stiffening": {"kind": "stage", "shows": "A deep white-and-red stiffening truss builds itself along and under "
                   "the deck; the wind streaks keep blowing but the deck now stays dead calm.", "seconds": (3.5, 6)},
    "finale": {"kind": "outro", "shows": "Golden light, a slow drone pull-back: traffic flows across the finished "
               "suspension bridge, a ship sails beneath. Payoff and the closing question.", "seconds": (4.5, 8)},
}

# Stage/problem pairs: each problem is answered by the stage right after it.
ANSWERS = {"heavy_load": "arch", "railway": "truss", "wide_bay": "suspension",
           "heat": "expansion_joint", "wind": "stiffening"}

# Line-drawings (white strokes, the format's signature) the renderer draws itself, per action.
DRAWINGS = {"heavy_load": "squeeze/stretch arrows on the bending deck", "arch": "load arrows",
            "railway": "a row of stone arches with piers in the ships' path", "truss": "triangle vs square",
            "wide_bay": "a bay-long truss sagging under its own weight", "expansion_joint": "box around the joint",
            "wind": "wind streaks", "stiffening": "wind streaks"}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'2,023 m','text':'longest span'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Tension'} (names a part or idea, never a count)"}
WORDS_PER_SECOND = 2.4


def beat_actions(beat: dict) -> list:
    return list(beat.get("actions") or [beat.get("action")])


def min_seconds(beat: dict) -> float:
    return sum(ACTIONS.get(a, {}).get("seconds", (0, 0))[0] for a in beat_actions(beat))


def validate(beats: list) -> list:
    errs = []
    for k, b in enumerate(beats):
        acts_k = beat_actions(b)
        if not 1 <= len(acts_k) <= 2:
            errs.append(f"beat {k + 1} has {len(acts_k)} actions; 1-2 allowed")
        kinds = [ACTIONS.get(a, {}).get("kind") for a in acts_k]
        if len(acts_k) > 1 and kinds != ["problem", "stage"]:
            errs.append(f"beat {k + 1}: only a problem followed by its answer may share a beat")
    acts = [a for b in beats for a in beat_actions(b)]
    unknown = [a for a in acts if a not in ACTIONS]
    if unknown:
        errs.append(f"unknown actions: {unknown}")
    if acts != STAGE_ORDER:
        errs.append(f"actions must appear exactly once each, in order: {STAGE_ORDER} (got {acts})")
    return errs
