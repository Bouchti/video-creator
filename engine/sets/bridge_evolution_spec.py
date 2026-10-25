"""
BRIDGE EVOLUTION set — an "evolution" film: one river valley, and every time the river gets
wider (or the world throws a new problem at it) the bridge has to become a smarter kind of
bridge. Plank beam → stone arch → steel truss → suspension bridge → expansion joints → a
stiffening truss against the wind. Second-person narration ("You've built a bridge..."), no hero,
no hook/rewind: the film starts at the beginning and escalates.

Pure data (no Blender), read by agents/evolution_writer.py and enforced by
engine/sets/bridge_evolution.py.
"""

SET_ID = "bridge_evolution"
FORMAT = "evolution"
SUBJECT = ("The evolution of the bridge, told in one continuous 3D river valley seen from drone height: a "
           "thatched village by a narrow river, a forest all around, and a river that keeps getting wider, "
           "so each bridge is replaced by the next, smarter kind of bridge")

MODEL_FACTS = {
    "the river": "a 6 m stream at the start, then about 15 m, then about 40 m, then about 120 m wide",
    "plank bridge": "logs or planks laid across the gap (a simple beam bridge). A beam bends under load: the "
                    "top squeezes and the bottom stretches, and the longer the span the more it sags. Timber "
                    "beams rarely span more than about 10 m",
    "stone arch": "wedge-shaped stones (voussoirs) laid in a curve over a wooden frame (centring); the top "
                  "stone is the keystone. An arch turns the load into pure squeezing (compression), which "
                  "stone handles brilliantly; Roman arches like the Pont du Gard still stand after 2,000 "
                  "years. The arch pushes outwards at its feet, so it needs solid ground on both sides",
    "why the arch stops": "a single stone arch has to get taller as it gets longer, and a very wide river "
                          "would need many piers in the water, blocking ships",
    "steel truss": "a frame of steel bars joined in triangles. A triangle cannot change shape without changing "
                   "the length of a side, while a square folds into a diamond (a parallelogram) under a push. "
                   "So every bar in a truss is only pulled or pushed along its length, and very little steel "
                   "carries a lot of load. Railway truss bridges span 50-150 m",
    "suspension": "two tall towers carry main cables that hang in a curve and are anchored into the ground at "
                  "both ends; vertical hangers drop from the cables and hold the road deck. The cables only "
                  "pull (tension), and steel wire is extremely strong in tension. The Golden Gate main span is "
                  "1,280 m; the 1915 Canakkale Bridge in Turkey (2022) spans 2,023 m, the longest in the world",
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

STAGE_ORDER = ["plank", "widen_arch", "arch", "widen_truss", "truss", "widen_suspension", "suspension",
               "heat", "expansion_joint", "wind", "stiffening", "finale"]

ACTIONS = {
    # stage = a new bridge (or fix) is built; problem = the world raises the bar; outro = the ending
    "plank": {"kind": "stage", "shows": "Drone shot over a thatched village by a narrow river in a forest. Wooden "
              "planks drop into place one by one on log beams across the 6 m stream; a little cart rolls "
              "across.", "seconds": (3.5, 6)},
    "widen_arch": {"kind": "problem", "shows": "The banks slide apart: the river gets wider (about 15 m). The "
                   "planks sag in the middle, crack and drop into the water with a splash.", "seconds": (2.5, 5)},
    "arch": {"kind": "stage", "shows": "Big cut stones fly in one by one from both banks and lock into a curved "
             "stone arch; the keystone drops in last at the top with a thud, then the road on top fills in. "
             "Glowing arrows show the weight being pushed down and out along the curve into the banks.",
             "seconds": (4, 7)},
    "widen_truss": {"kind": "problem", "shows": "The river widens again (about 40 m) and a sailing ship glides "
                    "towards the bridge; the stone arch crumbles into the river, stone by stone.",
                    "seconds": (2.5, 5)},
    "truss": {"kind": "stage", "shows": "A red steel truss bridge assembles bar by bar across the river, all "
              "triangles. A white line-drawing appears in the sky: a TRIANGLE stays rigid while a SQUARE is "
              "pushed and folds into a diamond. A train of carts crosses; the ship passes underneath.",
              "seconds": (4.5, 8)},
    "widen_suspension": {"kind": "problem", "shows": "Wider still (about 120 m): the banks race apart, the truss "
                         "tips and falls into the river with a huge splash. Pull back to see the enormous gap.",
                         "seconds": (2.5, 5)},
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
               "suspension bridge, a ship sails beneath, the old village on the bank below. Payoff and the "
               "closing question.", "seconds": (4.5, 8)},
}

# Stage/problem pairs: each problem is answered by the stage right after it.
ANSWERS = {"widen_arch": "arch", "widen_truss": "truss", "widen_suspension": "suspension",
           "heat": "expansion_joint", "wind": "stiffening"}

# Line-drawings (white strokes, the format's signature) the renderer draws itself, per action.
DRAWINGS = {"truss": "triangle vs square", "expansion_joint": "box around the joint",
            "wind": "wind streaks", "stiffening": "wind streaks", "arch": "load arrows"}

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
