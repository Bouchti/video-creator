"""
BACTERIA-CEMENTED SANDCASTLE story set: one sunny 8 m slice of Max's beach (dry sand and a striped towel on
the left, wet sand in the middle, the sea on the right), cut open in front to show the sand layers and the
water table rising with the tide, plus a magnified grain-scale INSET window floating beside the castle.
Max wants a 2 m sandcastle with a tower his two kids can sit in, and that survives high tide. Each attempt
FAILS for a real physical reason (angle of repose, too much water, saturation, bacteria without food) and
each FIX is the real answer, ending with microbially induced calcite precipitation (biocement).
Running gag: a crab moves into every version, is flattened (unhurt), and finally lives on the stone tower.
Pure data (no Blender), read by the showrunner and enforced by engine/sets/s_bacteria_cemented_backyard_story.py.
"""

SET_ID = "s_bacteria_cemented_backyard_story"
SUBJECT = ("Max, a well-meaning, overconfident DIY dad (orange hat, big mustache), builds a 2 m sandcastle on "
           "his beach that his two kids can sit inside and that must survive high tide; the beach is cut open "
           "in front (sand layers, water table) with a magnified grain-scale inset window beside the castle")
HERO = "Max"

MODEL_FACTS = {
    "goal": "a 2 m sandcastle with a tower two kids can sit in, surviving high tide and waves",
    "dry sand": "dry grains have nothing pulling them together; a dry pile only stands as steep as friction "
                "allows: the angle of repose, about 34 degrees",
    "moist sand": "about 1% water by volume forms tiny capillary water bridges between grains; their surface "
                  "tension pulls the grains together, so wet sand holds 45 degrees and even vertical walls",
    "too much water": "when the pores fill, the separate bridges merge, surface tension stops pulling, and the "
                      "heavy wet sand slides under its own weight to 15-30 degrees (mud)",
    "packing": "packed hard (researchers thumped moist sand 70 times in a tube), the grains touch at more points, "
               "more bridges form and a tall tower stands",
    "tide": "the tide raises the water table; water fills every pore, the bridges vanish and the castle melts; "
            "a moat only fills first",
    "biocement bacteria": "Sporosarcina pasteurii breaks down urea into carbonate; with calcium it precipitates "
                          "calcite (calcium carbonate): microbially induced calcite precipitation (MICP)",
    "why bacteria alone failed": "without urea and calcium the bacteria have nothing to make crystals from",
    "the treatment": "soak in a urea + calcium chloride bath for three days, then air-dry two days; calcite "
                     "crystals grow at every grain contact and glue the sand like natural sandstone",
    "safety": "the reaction releases ammonium: wear gloves and neutralise the used bath water",
    "real test": "a full-size dune in an Oregon wave flume, bio-cemented by spraying, survived 19 trials of "
                 "about 300 waves each",
}

STORY_ORDER = ["dry_tower", "fail_pour", "mist", "fail_flood", "pack", "fail_tide", "spray_bacteria",
               "fail_wave", "cement_bath", "finale"]

_W = "water"

ACTIONS = {
    # ---- hooks (staged after the story, on the finished set; shown FIRST, before the rewind) ----
    "wave_hook": {"kind": "hook", "seconds": (3, 5), "ambience": _W,
                  "shows": "A big wave rolls at Max's pale stone sandcastle while his two kids sit in its tower.",
                  "must_see": ["c5_tower", "wave", "Kid1", "Max"],
                  "extras": "The crab sits on the tower rim; Max gasps beside the castle."},
    "melt_hook": {"kind": "hook", "seconds": (3, 5), "ambience": _W,
                  "shows": "The rising tide floods Max's packed sandcastle and it melts into a slump.",
                  "must_see": ["c3_tower", "Max"],
                  "extras": "Max shrugs at the slump."},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the story plays backwards to bare sand.",
               "seconds": (1.5, 3), "ambience": _W},
    # ---- the ladder ----
    "dry_tower": {"kind": "story", "seconds": (4, 7), "ambience": _W,
                  "shows": "Max tips buckets of dry sand into a tall tower (label DRY SAND).",
                  "must_see": ["c1_tower", "Max"],
                  "extras": "A crab pops onto the top of the tower; Max's striped towel, beach umbrella and "
                            "cooler sit on the dry sand behind him."},
    "fail_pour": {"kind": "fail", "seconds": (4.5, 7), "ambience": _W,
                  "shows": "The dry tower pours down into a cone; the protractor beside it reads 34 degrees; in "
                           "the inset the dry grains drift apart (label NO GLUE).",
                  "must_see": ["c1_cone", "inset_ring", "prot_disk", "Max"],
                  "extras": "The crab rides the sand down and is flattened (unhurt); Max shrugs."},
    "mist": {"kind": "fix", "seconds": (4.5, 7), "ambience": _W,
             "shows": "Max mists water from a sprayer; in the inset blue water bridges grow between the grains "
                      "(label 1% WATER); a tall wet tower stands and the protractor at its base reads 45 degrees.",
             "must_see": ["c2_tower", "inset_ring", "prot_disk", "Max"],
             "extras": "The crab moves onto the new tower top; Max throws both arms up."},
    "fail_flood": {"kind": "fail", "seconds": (4.5, 7), "ambience": _W,
                   "shows": "Max floods the tower with a hose; in the inset water fills every pore and the bridges "
                            "vanish (label PORES FULL); the tower sags into a mud mound, protractor 15-30 degrees.",
                   "must_see": ["c2_mud", "inset_ring", "prot_disk", "Max"],
                   "extras": "The crab sinks with the mud and is flattened again; Max gasps."},
    "pack": {"kind": "fix", "seconds": (4, 7), "ambience": _W,
             "shows": "Back at 1% water, Max pounds the sand hard (label 70 THUMPS) and a tall castle with a "
                      "big tower rises; the inset grains squeeze together with bridges at every contact.",
             "must_see": ["c3_tower", "inset_ring", "Max"],
             "extras": "The crab moves into the tower rim; Max throws both arms up."},
    "fail_tide": {"kind": "fail", "seconds": (4.5, 7), "ambience": _W,
                  "shows": "The tide comes in: the moat fills first, the water table rises in the cut, the inset "
                           "pores fill (label PORES FULL) and the castle melts into the sea.",
                  "must_see": ["c3_tower", "moat_water", "inset_ring", "Max"],
                  "extras": "Max points proudly at his moat first, then shrugs; the crab is flattened."},
    "spray_bacteria": {"kind": "fix", "seconds": (3.5, 6), "ambience": _W,
                       "shows": "Max sprays a pink bacteria mix from a spray bottle onto a rebuilt castle; tiny pink "
                                "bacteria appear on the grains in the inset (label S. PASTEURII).",
                       "must_see": ["c4_tower", "inset_ring", "Max"],
                       "extras": "The crab climbs onto the new tower; Max nods, very pleased."},
    "fail_wave": {"kind": "fail", "seconds": (4.5, 7), "ambience": _W,
                  "shows": "A wave hits the sprayed castle and it melts anyway; the inset shows bacteria but no "
                           "crystals (labels NO UREA, NO CALCIUM).",
                  "must_see": ["c4_tower", "inset_ring", "Max"],
                  "extras": "Max's jaw drops at the splash, then he shrugs; the crab is flattened."},
    "cement_bath": {"kind": "fix", "seconds": (7, 11), "ambience": _W,
                    "shows": "The castle soaks in a big tub of urea and calcium chloride while a calendar flips "
                             "three days; white calcite crystals grow at every grain contact in the inset (label "
                             "CALCITE); the tub drains and the castle dries pale and stone-like.",
                    "must_see": ["tub_", "inset_ring", "calendar", "Max"],
                    "extras": "Max wears yellow gloves (ammonium) and folds his arms while the days pass; the crab "
                              "waits on the sand."},
    "finale": {"kind": "story", "seconds": (6, 9), "ambience": _W,
               "shows": "A wave breaks on the stone castle and it stands; the two kids sit in the tower; a big "
                        "sign shows the Oregon wave-flume dune (19 x 300 WAVES).",
               "must_see": ["c5_tower", "Kid1", "scale_card", "Max"],
               "extras": "The crab sits on the tower rim at last; the kids wave; Max throws both arms up as the "
                         "water drains back."},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'34°','text':'angle of repose'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Calcite'} (names a part, never a number)"}
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
        errs.append("beat 1 must be a hook action (wave_hook or melt_hook)")
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
