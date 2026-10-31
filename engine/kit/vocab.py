"""
The kit's vocabulary (pure data, no Blender): everything a storyboard may ask for. The planner can
only combine these; the kit (engine/kit/embankment.py) implements and has been tested on each one.

Every world has a vocabulary module with these same names (for_world below); generated worlds keep theirs
in engine/kit/worlds/<world>_vocab.py.

EMBANKMENT world: a cutaway riverbank seen from the front. Water on the left, Max's barrier in the
middle, the protected yard (house, trampoline, kids) on the right, with a buried sand layer under it all.
Fits levees, dikes, sea walls, flood berms and embankment dams.
"""

import importlib

WORLD = "embankment"
WORLD_CLASS = ("engine.kit.embankment", "EmbankmentSet")   # (module, class) that stages this world's storyboards
FIRST_BUILD = "sand_wall"                                 # the change every ladder starts from
THING = "barrier"                                         # what the ladder builds, in validator messages
CALM = "calm"                                             # the event of the setup step (nothing happens yet)
FINALE_EVENTS = ("storm_holds",)                          # events that only close the story
# What the planner is told about the world (with Max / with no hero) and which news fits it.
DESCRIPTION = """A cutaway riverbank seen from the front: a river on the left, the barrier Max builds in the middle, his
yard (house, trampoline, two kids) on the right, and a buried sand layer under it all. It fits levees,
dikes, flood walls, sea walls, flood berms and embankment dams. Max is a cheerful, overconfident DIY dad."""
DESCRIPTION_NO_HERO = """A cutaway riverbank seen from the front: a river on the left, the barrier in the middle, a yard (house,
trampoline, two kids for scale) on the right, and a buried sand layer under it all. It fits levees,
dikes, flood walls, sea walls, flood berms and embankment dams. There is NO hero: nobody builds on
screen, each part builds itself in physical order and the camera follows the mechanism."""
NEWS = ("flood barriers (levees, dikes, flood walls, sea walls, embankment dams, flood season, a failure, an "
        "audit, a record flood)")
FITS = "levees, dikes, flood walls, sea walls, flood berms and embankment dams"
# The plain narration of a world's reference film (previews and static checks only; "fail" is followed by
# the event's "teaches").
REFERENCE_LINES = {
    "hook_hero": "This is Max. His barrier just lost to the river.",
    "hook": "This barrier just lost to the river.",
    "setup_hero": "Max promised his kids a backyard that never floods. How hard could it be, really?",
    "setup": "A river, a backyard, and one job: keep the yard dry when the water rises.",
    "fail": "The river rose and it failed, because",
    "finale": "Now every fix works together, the river rises, and the yard stays dry. Which fix would you build?",
}

# Zero-cost preview narration: short, plain sentences that exercise every beat while staying inside the
# production 65-second budget. New worlds may provide their own mapping; storyboard.reference_film has a
# concise generic fallback.
REFERENCE_BEATS = {
    "calm": "Max promised his kids the yard would stay dry forever.",
    "seep_slump": "Sand has wide gaps, so river water leaked through and collapsed it.",
    "seep_blocked": "A packed clay core closed those gaps and stopped the leak.",
    "underseep_boil": "Then buried sand carried pressure underneath, bursting through the lawn.",
    "underseep_relieved": "A heavy berm and relief wells released that hidden pressure safely.",
    "overtop_scour": "Next, water crossed the low crest and gouged the bare slope.",
    "freeboard_holds": "Max raised the crest, then added grass and protective rock.",
    "burrow_piping": "One squirrel tunnel became a muddy jet that carried soil away.",
    "burrow_sealed": "Packed repairs and regular checks stopped small holes becoming breaches.",
    "storm_holds": "Now every fix holds, and the trampoline stays dry. Which mistake surprised you?",
}


def worlds() -> tuple:
    """Every world the kit can film: the embankment and each verified world in engine/kit/worlds."""
    from engine.kit.worlds import REGISTERED
    return (WORLD,) + tuple(w for w in REGISTERED if w != WORLD)


def for_world(name: str):
    """The vocabulary module of a world (this module for the embankment)."""
    if name == WORLD:
        return importlib.import_module(__name__)
    return importlib.import_module(f"engine.kit.worlds.{name}_vocab")


WORLDS = (WORLD,)                    # the hand-built worlds; worlds() adds the generated ones

# Water levels (engine/kit/geometry.level): low/normal sit in the river bed, high/flood against the first wall's
# height, "overtop" just above the barrier's CURRENT crest.
LEVELS = {"low": 0.25, "normal": 0.5, "high": 0.8, "flood": 0.94, "overtop": 1.22}

WEATHER = ("sunny", "rain", "storm")

# What Max BUILDS in a step's setup part (persistent from then on). "profile" names the barrier shape.
CHANGES = {
    "none": {"does": "nothing new is built", "profile": None},
    "sand_wall": {"does": "Max shovels up a tall, steep wall of pure sand between the river and the yard",
                  "profile": "steep", "first": True},
    "clay_core_widen": {"does": "Max builds a dark clay core inside the barrier and makes it wide with gentle slopes",
                        "profile": "wide", "adds": ["core"]},
    "berm_wells": {"does": "Max adds a wide, low soil berm on the yard side and relief wells at its toe",
                   "adds": ["berm", "wells"]},
    "raise_armor": {"does": "Max raises the crest well above the flood line, plants grass on the slopes and lays rock "
                            "riprap on the river side", "profile": "raised", "adds": ["cover", "riprap"]},
    "fill_burrows": {"does": "Max packs the burrow shut and moves the squirrel to a nest box far from the barrier",
                     "adds": ["patch", "nestbox"]},
}

# The same changes in a no-hero explainer (storyboard "hero": false): the build happens with nobody building it.
BUILT = {
    "none": "nothing new is built",
    "sand_wall": "a tall, steep wall of pure sand rises between the river and the yard",
    "clay_core_widen": "a dark clay core grows inside the barrier and the barrier widens to gentle slopes",
    "berm_wells": "a wide, low soil berm spreads on the yard side and relief wells drop in at its toe",
    "raise_armor": "the crest rises well above the flood line, grass covers the slopes and rock riprap lines the "
                   "river side",
    "fill_burrows": "the burrow is packed shut and a nest box for the squirrel appears far from the barrier",
}

# What HAPPENS in a step's mechanism part. outcome: fail | hold. needs: changes that must already exist.
EVENTS = {
    "calm": {"outcome": "hold", "level": "low", "shows": "a sunny day, a low river, the empty bank where the barrier "
                                                         "will stand",
             "focus": "site"},
    "seep_slump": {"outcome": "fail", "level": "high", "leaves": "slumped",
                   "shows": "the river rises; blue flow arrows pass straight through the sand body; the yard-side "
                            "face darkens with water and slumps down",
                   "focus": "body", "teaches": "water flows easily through the big gaps between sand grains"},
    "seep_blocked": {"outcome": "hold", "level": "high", "needs": ["core"],
                     "shows": "the river rises; the flow arrows stop at the clay core; the yard side stays dry",
                     "focus": "body", "teaches": "clay's tiny grains barely let water through"},
    "underseep_boil": {"outcome": "fail", "level": "flood",
                       "shows": "flow arrows travel UNDER the barrier through the buried sand layer and push up "
                                "under the yard; a muddy sand boil erupts on the lawn",
                       "focus": "under", "teaches": "water under pressure travels through buried sand and pushes "
                                                      "up the thin soil on the other side"},
    "underseep_relieved": {"outcome": "hold", "level": "flood", "needs": ["berm", "wells"],
                           "shows": "flow arrows still travel under, but the heavy berm presses the ground down and "
                                    "the relief wells let the water out calmly into a ditch",
                           "focus": "under", "teaches": "weight holds the ground down and wells release the pressure"},
    "overtop_scour": {"outcome": "fail", "level": "overtop", "leaves": "gouged",
                      "shows": "the river rises over the crest; a sheet of water pours down the yard-side slope and "
                               "scours a deep gouge into the bare soil",
                      "focus": "crest", "teaches": "water pouring over the top erodes bare soil from the back"},
    "freeboard_holds": {"outcome": "hold", "level": "flood", "needs": ["riprap"],
                        "shows": "the flood rises to its highest line and stops well below the raised crest; a "
                                 "measuring arrow shows the gap; grass and rocks protect the slopes",
                        "focus": "crest", "teaches": "freeboard: a safety margin above the highest expected flood"},
    "burrow_piping": {"outcome": "fail", "level": "high",
                      "shows": "a squirrel digs a tunnel into the barrier; the river finds it; water rushes through "
                               "the tunnel and blasts out of the yard side as a muddy jet",
                      "focus": "body", "teaches": "water flowing through a hole carries soil away and widens it "
                                                  "(piping)"},
    "burrow_sealed": {"outcome": "hold", "level": "high", "needs": ["patch"],
                      "shows": "the packed burrow stays shut under the high river; the squirrel sits in its new nest "
                               "box away from the barrier",
                      "focus": "body", "teaches": "inspection and maintenance keep small holes from becoming breaches"},
    "storm_holds": {"outcome": "hold", "level": "flood",
                    "shows": "a full storm: the river presses on the barrier and nothing gets through; the yard "
                             "stays dry and the kids bounce on the trampoline",
                    "focus": "wide", "teaches": "every fix working together"},
}

# Scene objects that SHOW each event (object-name prefixes the kit really uses): the measured must_see
# gate checks them at every beat's middle and 7/8.
EVENT_MUST_SEE = {
    "calm": ["Max", "kb_river"],
    "seep_slump": ["kb_barrier", "kb_flow", "Max"],
    "seep_blocked": ["kb_barrier", "kb_core", "kb_flow"],
    "underseep_boil": ["kb_flow", "kb_boil", "Max"],
    "underseep_relieved": ["kb_berm", "kb_well", "kb_flow"],
    "overtop_scour": ["kb_sheet", "kb_gouge", "Max"],
    "freeboard_holds": ["kb_barrier", "kb_marker", "kb_riprap"],
    "burrow_piping": ["kb_tunnel", "kb_jet", "Max"],
    "burrow_sealed": ["kb_patch", "kb_nestbox", "Max"],
    "storm_holds": ["kb_barrier", "Max", "Kid1"],
}

# What the running gag (the rubber duck) visibly does in each event: the writer may joke about it.
GAG_DOES = {
    "calm": "the rubber duck bobs on the low river",
    "seep_slump": "the rubber duck rides the rising river up to the wall",
    "seep_blocked": "the rubber duck bobs on the high river, stuck on the river side",
    "underseep_boil": "the rubber duck pops up out of the sand boil in the yard",
    "underseep_relieved": "the rubber duck floats on the flooded river",
    "overtop_scour": "the rubber duck surfs over the crest and down the waterfall",
    "freeboard_holds": "the rubber duck floats at the flood line, well below the crest",
    "burrow_piping": "the rubber duck rides the muddy jet out onto the lawn",
    "burrow_sealed": "the rubber duck floats on the river",
    "storm_holds": "the rubber duck floats on the storm-high river and stays there",
}

# Barrier shapes each event is built for (the kit refuses other combinations instead of improvising).
EVENT_PROFILES = {
    "seep_slump": ("steep",), "seep_blocked": ("wide",), "overtop_scour": ("wide",),
    "freeboard_holds": ("raised",), "burrow_piping": ("raised",), "burrow_sealed": ("raised",),
}

STEP_KINDS = ("setup", "fail", "fix", "finale")
REACTIONS = {"fail": "shrug", "fix": "cheer", "setup": "point", "finale": "cheer"}
GAGS = ("duck", "none")
LABEL_MAX = 18                     # characters in a beat's 3D label
# Every Max-story failure ends on the same readable disaster payoff. The storyboard compiler adds these
# names to fail-beat must_see gates, so a kit regression cannot silently lose one of them.
HERO_FAILURE_MUST_SEE = ("kb_fail_flood", "kb_duck", "kb_drench")

# Seconds an action needs on screen (min, max): setup part + mechanism part.
SECONDS = {"setup": (3, 6), "fail": (5, 9), "fix": (5, 9), "finale": (4, 7), "hook": (3, 5)}
