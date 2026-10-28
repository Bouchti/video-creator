"""
The kit's vocabulary (pure data, no Blender): everything a storyboard may ask for. The planner can
only combine these; the kit (engine/kit/embankment.py) implements and has been tested on each one.

EMBANKMENT world: a cutaway riverbank seen from the front. Water on the left, Max's barrier in the
middle, the protected yard (house, trampoline, kids) on the right, with a buried sand layer under it all.
Fits levees, dikes, sea walls, flood berms and embankment dams.
"""

WORLDS = ("embankment",)

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

# What HAPPENS in a step's mechanism part. outcome: fail | hold. needs: changes that must already exist.
EVENTS = {
    "calm": {"outcome": "hold", "level": "low", "shows": "a sunny day, a low river, the empty bank where the barrier "
                                                         "will stand",
             "focus": "site"},
    "seep_slump": {"outcome": "fail", "level": "high",
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
    "overtop_scour": {"outcome": "fail", "level": "overtop",
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

# Seconds an action needs on screen (min, max): setup part + mechanism part.
SECONDS = {"setup": (3, 6), "fail": (5, 9), "fix": (5, 9), "finale": (4, 7), "hook": (3, 5)}
