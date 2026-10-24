"""
POOL STORY set — the backyard-pool cutaway played as a TRIAL-AND-ERROR comedy: our hero Max
builds a pool for his kids the naive way, each attempt FAILS for a real engineering reason, and
each FIX is the real solution. Pure data (no Blender), read by the showrunner and enforced by
engine/sets/pool_story.py.
"""

SET_ID = "pool_story"
SUBJECT = ("Max, a well-meaning, overconfident DIY dad (orange hard hat, big mustache), builds a backyard "
           "swimming pool for his two kids, shown as a 3D cutaway (the ground sliced open lengthwise)")
HERO = "Max"

MODEL_FACTS = {
    "pool size": "6 m long x 3 m wide, 1.5 m deep inside",
    "excavation": "1.8 m deep hole, about 50 tons of soil",
    "soil": "topsoil, clay, then sand that drains water away; groundwater around 3.4 m down, rises after rain",
    "why the bare hole failed": "soil and sand are porous: water simply soaks into the ground",
    "why plain concrete failed": "concrete is strong when squeezed but weak when pulled: 20 tons of water and the "
                                 "soil pushing on unreinforced walls crack them, and the water leaks out",
    "the fix for cracks": "a steel rebar cage on a ~25 cm grid takes the pulling forces; concrete is sprayed on "
                          "(shotcrete), 20 cm thick",
    "curing": "concrete must stay damp while it cures (about 28 days) or it shrinks and cracks",
    "finish": "plaster makes the shell watertight and smooth; tiles at the waterline, stone coping on the edge",
    "why the empty pool floated": "after heavy rain, groundwater pushes up on an EMPTY pool like a boat; the 20 tons "
                                  "of water were what held it down",
    "the fix for floating": "a gravel bed lets groundwater drain under the floor, and a hydrostatic relief valve "
                            "opens to let groundwater in instead of lifting the pool (and: never drain it after rain)",
    "why the water turned green": "still water + sunlight + no circulation = algae in days",
    "the fix for green water": "a pump pulls water through the skimmer and main drain, pushes it through a sand "
                               "filter and back out the jets (the whole pool about every 6 hours), plus chlorine",
    "water": "about 20,000 litres = about 20 tons",
}

# The story is a ladder: these happen in this order, all required (the set's state depends on it).
STORY_ORDER = ["dig", "fail_soak", "plain_shell", "fail_crack", "rebar", "shotcrete", "cure", "finish", "fill",
               "fail_float", "fix_valve", "fail_green", "fix_filter", "finale"]

ACTIONS = {
    # ---- hooks (staged on the finished pool, shown FIRST, before the rewind) ----
    "float_hook": {"kind": "hook", "shows": "Storm. Max stands inside his drained pool as the whole concrete pool lifts "
                   "OUT of the ground on rising groundwater. His jaw drops. Rain, up-arrows."},
    "happy_hook": {"kind": "hook", "shows": "Sunny payoff: the finished pool, Max and his two kids cannonball in, "
                   "splash. (Use when the hook line teases the ending: 'It took Max five disasters to get here.')"},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the whole story plays BACKWARDS (VHS look) "
               "to bare lawn. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "dig": {"kind": "story", "shows": "An excavator digs the hole behind the cut; soil drops away in section; a spoil "
            "pile grows. Max points proudly.", "seconds": (4.5, 7)},
    "fail_soak": {"kind": "fail", "shows": "Max fills the bare hole with a hose. The muddy water rises... then sinks "
                  "away while a dark wet patch spreads through the soil. Max scratches his head.", "seconds": (4, 7)},
    "plain_shell": {"kind": "story", "shows": "Max sprays plain concrete walls into the hole (no steel). Looks solid.",
                    "seconds": (2.5, 5)},
    "fail_crack": {"kind": "fail", "shows": "He fills it again: jagged cracks race down the walls, water squirts out "
                   "through them into the soil and the level drops. Max facepalms.", "seconds": (4, 7)},
    "rebar": {"kind": "fix", "shows": "The cracked walls are gone; a steel rebar grid builds bar by bar; dimension "
              "line 25 cm.", "seconds": (3, 6)},
    "shotcrete": {"kind": "fix", "shows": "Concrete sprayed onto the steel cage; the shell grows; dimension line "
                  "20 cm.", "seconds": (3, 6)},
    "cure": {"kind": "fix", "shows": "Day/night time-lapse: a sprinkler mists the shell every morning while Max "
             "dozes off at night (Zzz) and startles awake.", "seconds": (3, 6)},
    "finish": {"kind": "story", "shows": "Plaster (label PLASTER), blue waterline tiles, stone coping and a ladder "
               "appear.", "seconds": (3, 6)},
    "fill": {"kind": "story", "shows": "Max fills the real pool: clear blue water rises, light ripples dance on the "
             "walls. Max grins.", "seconds": (3, 6)},
    "fail_float": {"kind": "fail", "shows": "A storm rolls in. Max drains the pool to clean it; groundwater (blue) "
                   "rises in the soil and the empty pool LIFTS out of the ground. Max's jaw drops.",
                   "seconds": (4, 7)},
    "fix_valve": {"kind": "fix", "shows": "Under the lifted pool a gravel bed spreads, a brass relief valve "
                  "(label RELIEF VALVE) goes in the floor, the pool settles back down, the storm clears.",
                  "seconds": (4, 7)},
    "fail_green": {"kind": "fail", "shows": "Refilled. Days pass. The water turns murky green. Max holds his nose.",
                   "seconds": (3, 6)},
    "fix_filter": {"kind": "fix", "shows": "Clear pipes appear from the drain and skimmer to a pump and sand filter "
                   "(labels PUMP, FILTER); water races through them, the green clears to sparkling blue, a rubber-duck "
                   "chlorine floater bobs in.", "seconds": (4, 8)},
    "finale": {"kind": "story", "shows": "Sunny. Max and his two kids line up at the edge and cannonball in one after "
               "another: three big splashes, everyone cheering.", "seconds": (3, 6)},
    # ---- optional explainers ----
    "layers": {"kind": "explain", "after": "dig", "shows": "Camera glides down the soil face; labels TOPSOIL, CLAY, "
               "SAND, GROUNDWATER.", "seconds": (3, 5)},
    "weight": {"kind": "explain", "after": "fix_valve", "shows": "Yellow down-arrows (water weight) beat blue up-arrows "
               "(groundwater).", "seconds": (2.5, 5)},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'50 tons','text':'of soil'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Fail #2'}"}
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
        errs.append("beat 1 must be a hook action (float_hook or happy_hook)")
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
