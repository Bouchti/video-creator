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
    "burrow_hook": {"kind": "hook", "shows": "Storm. Muddy water blasts out of a squirrel burrow in the levee's land "
                    "side; the yellow rubber duck rides the jet onto the lawn, the squirrel salutes, Max's jaw drops.",
                    "seconds": (3, 5)},
    "happy_hook": {"kind": "hook", "shows": "Payoff first: storm on the river, but the yard is dry; Max cheers by the "
                   "green yard lamp while his two kids bounce on the trampoline. (Use when the hook teases the "
                   "ending: 'It took Max four floods to get here.')", "seconds": (3, 5)},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the story plays BACKWARDS (VHS look) to a "
               "sunny day with a low river. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "promise": {"kind": "story", "shows": "Sunny day, the river is low, the duck bobs on it. Max with a shovel by a "
                "sand pile promises his two kids a backyard that never floods and points at the river.",
                "seconds": (3, 6)},
    "fail_sand": {"kind": "fail", "shows": "Max piles a tall steep wall of pure sand. Rain; the river rises; blue "
                  "seepage arrows run straight through the sand (label SAND LEAKS), the land side turns dark and "
                  "wet, the face slumps like porridge and the duck oozes over the mush into the yard. Red yard lamp, "
                  "Max shrugs.", "seconds": (5, 9)},
    "fix_core": {"kind": "fix", "shows": "Max on the crest of a new wide, gentle levee (label WIDER THAN TALL) with a "
                 "dark brown clay core. A seepage arrow crosses the sand shell (label SAND) and a short arrow fades "
                 "out inside the clay (label CLAY CORE). Green lamp, Max cheers.", "seconds": (5, 9)},
    "fail_boil": {"kind": "fail", "shows": "The levee holds, but long blue pressure arrows run under it through the "
                  "buried sand and push up on the topsoil blanket in the yard; a sand boil erupts (label SAND BOIL) "
                  "with the duck bobbing on its fountain. Max rings it with sandbags. Red lamp.", "seconds": (5, 9)},
    "fix_berm": {"kind": "fix", "shows": "A wide low seepage berm rises on the land side (label SEEPAGE BERM, yellow "
                 "weight arrows), relief wells at the toe (label RELIEF WELLS) vent the pressure into a ditch; the "
                 "up-arrow under the yard shrinks. Green lamp.", "seconds": (5, 9)},
    "fail_overtop": {"kind": "fail", "shows": "A huge storm: the river pours over the crest (label OVERTOPPING); the "
                     "waterfall scours a growing gouge into the bare land-side slope and the duck surfs down it. Red "
                     "lamp, Max shrugs.", "seconds": (5, 9)},
    "fix_armor": {"kind": "fix", "shows": "The crest grows taller; red 100-year-flood line and a dimension arrow "
                  "(label 3 FT ABOVE 100-YEAR FLOOD), thick grass on the slopes, rock riprap on the river side "
                  "(label RIPRAP). Green lamp. (Narration: Katrina's failures were mostly overtopping.)",
                  "seconds": (5, 9)},
    "fail_burrow": {"kind": "fail", "shows": "Everything perfect, until a ground squirrel digs a tunnel into the land "
                    "slope (cutaway groove). The flood rises, finds the burrow, the hole widens as water carries "
                    "soil out (label PIPING) and a jet blasts out: the hook moment. Red lamp, jaw drop.",
                    "seconds": (5, 9)},
    "fix_maintain": {"kind": "fix", "shows": "Grass mowed short, Max inspects and packs the burrow shut with his "
                     "shovel (label 8.2 m along the tunnel), the hole is gone; the squirrel gets a box in the yard. "
                     "Green lamp.", "seconds": (5, 9)},
    "finale": {"kind": "story", "shows": "Full storm: every blue arrow stays on the river side of the levee. The kids "
               "bounce on the dry trampoline, the squirrel salutes from its box, the duck floats away down the river. "
               "The storm clears and the camera pulls out to a long map line along the levee labelled 3,787 MILES. "
               "Closing question.", "seconds": (6, 10)},
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
