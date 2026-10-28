"""
LEVEE STORY set — a riverbank cut open like a layer cake, played as a TRIAL-AND-ERROR comedy: Max builds an
earthen levee between the river and his backyard. Each attempt FAILS for a real geotechnical reason (seepage
through sand, underseepage + uplift, overtopping erosion, piping through an animal burrow) and each FIX is
the real-world answer. Running gag: the yellow rubber duck gets into the yard a new way every time.
Pure data (no Blender), read by the showrunner and enforced by engine/sets/levee_story_earthen_river_le_story.py.
"""

SET_ID = "levee_story_earthen_river_le_story"
SUBJECT = ("Max, a cheerful, overconfident DIY dad (hard hat, rain boots), builds an earthen levee between a river "
           "and his backyard so his two kids' trampoline never floods, shown as a vertical cutaway of the riverbank "
           "(topsoil blanket, a buried sand layer connected to the riverbed, bedrock)")
HERO = "Max"

MODEL_FACTS = {
    "the cutaway": "river channel on the left, the levee in the middle, Max's backyard (lawn, trampoline, house) on "
                   "the right; under it a thin topsoil blanket, a thick sand layer that runs under the levee and "
                   "connects to the riverbed, then bedrock",
    "permeability": "water flows easily through the big pores between sand grains; clay grains are so tiny that water "
                    "barely moves through clay (sand is roughly a million times more permeable)",
    "why the sand wall failed": "seepage soaked straight through the steep pure-sand wall; the wet land-side face lost "
                                "its strength and slumped",
    "fix 1": "a clay core inside the levee and wide, gentle slopes, so the levee is far wider than it is tall",
    "underseepage": "water travels UNDER the levee through the buried sand layer and pushes up on the thin topsoil "
                    "blanket in the yard (uplift pressure)",
    "sand boil": "when the uplift breaks through the blanket, a little volcano of muddy water and sand erupts; flood "
                 "fighters ring it with sandbags so the water inside rises and pushes back",
    "fix 2": "a seepage berm (a wide, low, heavy wedge of soil on the land side) whose weight holds the blanket down "
             "and lengthens the seepage path, plus relief wells at the toe that let the trapped pressure out safely "
             "into a ditch",
    "overtopping": "water pouring over the crest scours bare soil on the land-side slope; in Hurricane Katrina most "
                   "levee failures came from overtopping and land-side scour",
    "fix 3": "freeboard: the crest is raised well above the expected flood (FEMA's minimum for riverine levees is "
             "3 ft above the 100-year flood); thick grass on the slopes and rock riprap on the river side",
    "piping": "a ground squirrel burrow gives floodwater a shortcut; flowing water carries soil out, the hole widens "
              "from inside (internal erosion, piping) until it blows out",
    "burrow length": "the average California ground squirrel burrow is about 8.2 m long",
    "fix 4": "maintenance: keep vegetation short so holes are visible, inspect, fill and pack burrows, move the "
             "animals away from the levee",
    "scale": "the map line is labelled 3,787 MILES",
}

# The story is a ladder: these happen in this order, all required (the set's state depends on it).
STORY_ORDER = ["promise", "fail_sand", "fix_core", "fail_boil", "fix_berm", "fail_overtop", "fix_armor",
               "fail_burrow", "fix_maintain", "finale"]

ACTIONS = {
    # ---- hooks (staged on the finished set, shown FIRST, before the rewind) ----
    "burrow_hook": {"extras": "The squirrel, scaled up, hops beside the jet and then salutes, while Max points at the duck riding the jet and his jaw drops; mud drops and dust puffs splash onto the berm.", "must_see": ["jet_stream", "levee3_piped", "duck", "Max"], "kind": "hook", "shows": "A thick "
                    "brown jet of muddy water blasts out of a squirrel burrow in the levee's land side, and the "
                    "yellow rubber duck rides on top of the jet.",
                    "seconds": (3, 5)},
    "happy_hook": {"extras": "The squirrel salutes from its box on a post in the yard and the rain keeps falling.", "must_see": ["Max", "Kid1", "tramp_rim", "meter_green"], "kind": "hook", "shows": "Payoff first: storm on the river, but the yard is dry; Max cheers by the "
                   "green yard lamp while his two kids bounce on the trampoline. (Use when the hook teases the "
                   "ending: 'It took Max four floods to get here.')", "seconds": (3, 5)},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the story plays BACKWARDS (VHS look) to a "
               "sunny day with a low river. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "promise": {"extras": "The duck bobs slowly along the low river; the kids hop and smile, then turn to look at the river as Max talks and points.", "must_see": ["Max", "pile", "Kid1"], "kind": "story", "shows": "Sunny day, the river is low. Max "
                "with a shovel by a sand pile promises his two kids a dry backyard.",
                "seconds": (3, 6)},
    "fail_sand": {"extras": "The duck rides the rising river up toward the wall, then drops and tips as the river falls after the slump; sand puffs fly while Max shovels, and he shrugs at the end.", "must_see": ["levee1", "arrow_seep", "levee1_wet", "Max"], "kind": "fail", "shows": "Blue seepage "
                  "arrows run straight through Max's steep pure-sand wall (label SAND LEAKS) and the wall slumps "
                  "low. Red lamp.", "seconds": (5, 9)},
    "fix_core": {"extras": "The duck drifts on the high river; soil puffs rise as Max shapes the levee from its crest, and he cheers with both arms up.", "must_see": ["levee2", "core2", "arrow_clay", "Max"], "kind": "fix", "shows": "A seepage arrow "
                 "crosses the sand and a short arrow stops inside the dark brown clay core (label CLAY CORE). "
                 "Green lamp.", "seconds": (5, 9)},
    "fail_boil": {"extras": "The duck is thrown up out of the sand boil, mud spray flies, the sandbags pop up one by one around it, and Max cheers at first, then stares and shrugs.", "must_see": ["arrow_up", "boil_fountain", "bag_", "Max"], "kind": "fail", "shows": "Blue pressure arrows come under the levee through the buried sand and "
                  "push UP under the yard; a sand boil erupts there (label SAND BOIL). Max rings it with sandbags. "
                  "Red lamp.", "seconds": (5, 9)},
    "fix_berm": {"extras": "The duck drifts on the river; dust puffs rise as the berm grows, Max points and later cheers on it, and the relief wells pop in.", "must_see": ["berm", "well_", "arrow_upsmall", "arrow_weight"], "kind": "fix", "shows": "A wide "
                 "low seepage berm with yellow weight arrows (label SEEPAGE BERM) and relief wells at its toe; the "
                 "up-arrow under the yard shrinks. Green lamp.", "seconds": (5, 9)},
    "fail_overtop": {"extras": "The duck rides the rising river over the crest and slides down the land slope with the waterfall; water splashes and dirt puffs fly off the gouge, and Max looks up worried, then shrugs.", "must_see": ["falls", "gouge", "river", "Max"], "kind": "fail", "shows": "The river pours "
                     "over the crest (label OVERTOPPING) and the waterfall scours a growing gouge into the bare "
                     "land-side slope. Red lamp.", "seconds": (5, 9)},
    "fix_armor": {"extras": "Max rises with the crest as it grows and cheers twice, and the duck drifts on the flood-level river.", "must_see": ["levee3", "bar_flood", "dim_up", "riprap"], "kind": "fix", "shows": "The crest grows taller; red 100-year-flood line and a dimension arrow "
                  "(label 3 FT ABOVE 100-YEAR FLOOD), thick grass on the slopes, rock riprap on the river side "
                  "(label RIPRAP). Green lamp. (Narration: Katrina's failures were mostly overtopping.)",
                  "seconds": (5, 9)},
    "fail_burrow": {"extras": "Max cheers, then watches the squirrel vanish into its tunnel; when the jet blows out, the duck rides it onto the berm, the squirrel peeks out and salutes, and Max's jaw drops.", "must_see": ["squirrel", "levee3_piped", "jet_stream", "Max"], "kind": "fail", "shows": "A ground squirrel digs a tunnel into the land slope. The flood finds "
                    "the burrow and the widened hole (label PIPING) blasts a thick brown muddy jet out beside the "
                    "squirrel. Red lamp.",
                    "seconds": (5, 9)},
    "fix_maintain": {"extras": "Max hammers the hole shut with his shovel as dust puffs rise, turns and cheers, and in a short cutaway the squirrel salutes from its new box in the yard; the duck drifts on the low river.", "must_see": ["Max", "plug_burrow", "meter_port"], "kind": "fix", "shows": "Fresh tan soil "
                     "packs the burrow tunnel shut (label BURROW 8.2 m). Green lamp.",
                     "seconds": (5, 9)},
    "finale": {"extras": "The storm and rain clear, blue arrows press on the river side, the squirrel salutes from its box, and the duck floats on the high river.", "must_see": ["Max", "tramp_rim", "Kid1"], "kind": "story", "shows": "The rain stops and the yard "
               "stays dry: Max cheers by the green lamp while his two kids bounce on the trampoline. Closing "
               "question.", "seconds": (6, 10)},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'8.2 m','text':'average burrow'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Clay core'} (names a part, never a number)"}
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
        errs.append("beat 1 must be a hook action (burrow_hook or happy_hook)")
    if len(acts) < 2 or acts[1] != "rewind":
        errs.append("beat 2 must be 'rewind'")
    hooks = [a for a in acts if ACTIONS.get(a, {}).get("kind") == "hook"]
    if len(hooks) != 1:
        errs.append(f"exactly one hook action is allowed (got {hooks})")
    story = [a for a in acts if ACTIONS.get(a, {}).get("kind") in ("story", "fail", "fix")]
    if story != STORY_ORDER:
        errs.append(f"story actions must appear exactly once each, in order: {STORY_ORDER} (got {story})")
    for i, a in enumerate(acts):
        if ACTIONS.get(a, {}).get("kind") in ("hook", "rewind") and i > 1:
            errs.append(f"'{a}' can only open the film")
    if len(set(acts)) != len(acts):
        errs.append("each action may be used once")
    return errs
