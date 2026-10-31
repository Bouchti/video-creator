"""
FLOATING RIVERSIDE CABIN story set — an amphibious house played as a TRIAL-AND-ERROR comedy: Max builds a
riverside timber cabin that must stay dry when the river floods. Each attempt FAILS for a real physical reason
(water pours in, the house drifts off, the rigid utilities snap, the loaded house lists) and each FIX is the
real amphibious-house solution (a hollow concrete pontoon in a wet dock, vertical guide posts, flexible
service lines with slack, low centred ballast). Pure data (no Blender), read by the showrunner and enforced by
engine/sets/s_floating_riverside_cabin_a_story.py.
"""

SET_ID = "s_floating_riverside_cabin_a_story"
SUBJECT = ("Max, a well-meaning, overconfident DIY dad (orange hard hat, big mustache), builds a riverside "
           "timber cabin (6 x 4 m) that has to stay dry when the river floods, shown as a cutaway riverbank: "
           "the ground is sliced open in front so the concrete box under the cabin (first a plain slab, later "
           "a hollow pontoon in a concrete wet dock) and the rising flood water read in section, with a metre "
           "marker post beside the cabin")
HERO = "Max"

MODEL_FACTS = {
    "cabin": "single-storey timber cabin, about 6 m x 4 m, porch and front door on the river side",
    "why the slab house flooded": "a house on a slab stays where it is: the flood rises around it and pours in "
                                  "through the door gaps and wall joints; 1 m of water inside floats the furniture",
    "pontoon": "a hollow concrete box about 6.2 x 4.4 x 1.5 m under the cabin, sitting in a concrete 'wet dock' "
               "pit that fills from the river",
    "buoyancy": "1 cubic metre of water weighs about 1 tonne; a floating body sinks until it has pushed aside its "
                "own weight of water (Archimedes). House + pontoon of about 30 tonnes floats at about 1.15 m draft",
    "why it drifted": "a floating house has no grip on the ground: the current and wind push it sideways",
    "guide posts": "tall steel or concrete mooring posts at the corners with collars (rings) on the house: it can "
                   "only slide straight up and down",
    "why the utilities snapped": "rigid pipes and cables are anchored in the ground while the house moves up",
    "flexible lines": "coiled flexible 'elephant trunk' service lines with about 3 m of slack stretch as the house "
                      "rises",
    "why it leaned": "heavy things high up and on one side move the centre of gravity up and sideways: the house "
                     "lists and rubs on its posts",
    "stability fix": "heavy ballast placed low and centred in the pontoon plus a wide base keep the centre of "
                     "gravity low and in the middle: the house floats level",
    "finale flood": "the big flood rises about 2.7 m; the house rises with it, level, connected and lit",
    "real world": "Maasbommel (the Netherlands): 32 amphibious houses on the Meuse, allowed to rise up to 5.5 m",
}

STORY_ORDER = ["fail_slab", "fix_pontoon", "fail_drift", "fix_guides", "fail_snap", "fix_coils", "fail_lean",
               "fix_ballast", "finale"]

ACTIONS = {
    # ---- hooks (staged after the finale, shown FIRST, before the rewind) ----
    "drift_hook": {"kind": "hook", "seconds": (3, 5), "ambience": "water",
                   "shows": "Max's floating cabin, already out on the flooded river at frame 1, bobs and races "
                            "downstream with Max waving, then gasping, on its porch.",
                   "must_see": ["porch", "Max"],
                   "extras": "Flooded fence posts and a flooded willow slide by behind it; the duck paddles ahead."},
    "rise_hook": {"kind": "hook", "seconds": (3, 5), "ambience": "water",
                  "shows": "Happy payoff: the flood surges up and the cabin rises level on it, lit, with Max on the "
                           "porch and his two kids inside.",
                  "must_see": ["porch", "Kid", "Max"],
                  "extras": "Max throws both arms up; a little boat is tied at the porch."},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the story plays BACKWARDS to the dry "
                                          "riverbank. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "fail_slab": {"kind": "fail", "seconds": (6, 9), "ambience": "water",
                  "shows": "The flood rises around the cabin on its plain concrete slab and pours in under the door; "
                           "the marker post reads over 1 m; Max's sofa floats past the back window.",
                  "must_see": ["gauge", "cabin_glass_back", "Max"],
                  "extras": "Max first folds his arms on the porch (the river never gets this high), then watches "
                            "from his high bank beside the marker post, gasps and shrugs; the duck swims along the "
                            "front of the cabin."},
    "fix_pontoon": {"kind": "fix", "seconds": (6, 9), "ambience": "water",
                    "shows": "The hollow concrete pontoon in its concrete wet dock (seen in section) lifts the cabin "
                             "out of the dock as it fills; blue buoyancy up-arrows under it; label '1 m3 WATER = 1 "
                             "TONNE'.",
                    "must_see": ["pontoon", "buoy_arrow", "Max"],
                    "extras": "Max rides up on the porch and throws both arms up."},
    "fail_drift": {"kind": "fail", "seconds": (5, 8), "ambience": "water",
                   "shows": "Nothing holds the floating house: it drifts out of its dock and away across the open "
                            "river with Max on the porch.",
                   "must_see": ["porch", "Max"],
                   "extras": "Max waves from the porch; the duck paddles ahead of him; flooded fence posts slide by."},
    "fix_guides": {"kind": "fix", "seconds": (5, 8), "ambience": "water",
                   "shows": "Four tall steel guide posts with collars at the cabin corners; the house rises straight "
                            "up between them; label 'GUIDE POSTS'.",
                   "must_see": ["guide_postL", "collarL", "Max"],
                   "extras": "Max works on the posts, then rides up on the porch, arms up."},
    "fail_snap": {"kind": "fail", "seconds": (6, 9), "ambience": "water",
                  "shows": "As the house lifts, the rigid water pipe and power cable fixed in the ground snap: a "
                           "water gusher shoots up, sparks fly and the windows go dark; label 'FIXED TO THE GROUND'.",
                  "must_see": ["pipe_riser", "gusher", "Max"],
                  "extras": "Max gasps on the high bank, shakes his head and shrugs."},
    "fix_coils": {"kind": "fix", "seconds": (5, 8), "ambience": "water",
                  "shows": "Coiled flexible service lines stretch like springs as the house rises, the windows stay "
                           "lit; label '3 m SLACK'.",
                  "must_see": ["coil", "Max"],
                  "extras": "Max cheers with both arms up on the high bank."},
    "fail_lean": {"kind": "fail", "seconds": (5, 8), "ambience": "water",
                  "shows": "A bathtub, a piano and a bookcase all against the right wall; the floating house leans "
                           "to that side and scrapes its posts; red weight arrow, label 'TOP-HEAVY'.",
                  "must_see": ["cabin_wall_R", "heavy_arrow", "Max"],
                  "extras": "Max pushes the furniture in, then gasps and shrugs on the porch."},
    "fix_ballast": {"kind": "fix", "seconds": (5, 8), "ambience": "water",
                    "shows": "Heavy iron ballast blocks drop low and centred into the hollow pontoon (section); the "
                             "house rises perfectly level; label 'LOW BALLAST'.",
                    "must_see": ["ballast", "Max"],
                    "extras": "Max points down at the ballast from the porch, then throws both arms up."},
    "finale": {"kind": "story", "seconds": (6, 10), "ambience": "water",
               "shows": "The big flood rises 2.7 m and the cabin rises level with it, lit; the two kids eat cake "
                        "inside.",
               "must_see": ["porch", "Kid", "Max"],
               "extras": "Max waves and cheers on the porch; a small boat is tied at the porch; the duck paddles "
                         "nearby."},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'1 tonne','text':'per cubic metre'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Guide posts'} (names a part, never a number)"}
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
        errs.append("beat 1 must be a hook action (drift_hook or rise_hook)")
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
