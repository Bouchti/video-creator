"""
PUMPED STORAGE STORY set — Max turns a mountain into a battery by trial and error, so the solar
power of the afternoon can run his kids' outdoor movie at night. Each naive attempt fails for a
real hydropower reason; each fix is the real engineering. Pure data (no Blender), read by the
showrunner and enforced by engine/sets/pumped_storage_mountain_batt_story.py.
"""

SET_ID = "pumped_storage_mountain_batt_story"
SUBJECT = ("Max, a well-meaning, overconfident DIY dad (orange hard hat, big mustache), builds a pumped-storage "
           "'mountain battery' so his afternoon solar power can run tonight's outdoor movie for his two kids, shown "
           "as one vertical 3D cutaway of a mountain: an upper reservoir on the summit, a pressure tunnel through "
           "the rock, a deep cylindrical powerhouse with turbines, a lower reservoir behind a concrete dam, a solar "
           "field and the family house in the valley")
HERO = "Max"

MODEL_FACTS = {
    "the idea": "pumped storage is a water battery: spare electricity pumps water up to a high reservoir; when power "
                "is needed the water falls back down through turbines that drive generators",
    "head": "the useful energy depends on HEAD, the height the water falls between the two water surfaces. Two "
            "reservoirs at nearly the same height have almost no head, so the water barely moves the turbine",
    "the real plant's head": "about 150 m between the reservoirs; it swings from roughly 175 m (top full, bottom "
                             "empty) to roughly 125 m (top empty, bottom full)",
    "why the thin pipe failed": "friction: water rubbing along a long, narrow, twisting pipe loses most of its "
                                "pressure (losses grow with length, with speed squared and with every bend), so "
                                "only a trickle arrives and the bulb flickers",
    "flow": "power = water flow x head (x gravity x efficiency): you need huge flow as well as height. A 7 m wide "
            "pressure tunnel about 1.3 km long carries roughly 200 cubic metres of water per second",
    "power check": "200 m3/s x 150 m x 9.81 x ~0.9 efficiency is about 265 MW, i.e. two 125 MW machines",
    "why it ran dry": "an ordinary turbine only works one way: once the top reservoir has drained it cannot send "
                      "the water back up, so the battery is empty",
    "pump-turbines": "a reversible pump-turbine runs backwards as a pump: its generator becomes a motor powered by "
                     "surplus daytime (solar) electricity and lifts the same water uphill. The machines sit deep, "
                     "below the lower reservoir, so the pump never sucks air or cavitates",
    "why it shuddered": "a fixed-speed machine (e.g. 300 rpm, locked to the grid's 50 Hz) is shaped for one head; as "
                        "the head drifts from 175 to 125 m it runs far off its best point: rough, vibrating, "
                        "inefficient",
    "variable speed": "variable-speed motor-generators (with power electronics) let the machines turn anywhere from "
                      "about 285 to 315 rpm, matching speed to the head so they stay efficient across the range",
    "response": "from standstill a pumped-storage plant can deliver power to the grid within about 90 seconds",
    "real-world scale": "a typical plant: 250 MW for six hours = 1,500 MWh of storage, about 75-80% of the "
                        "electricity comes back, and the concrete, tunnels and machines last about 80 years",
    "scene scale": "the diorama is a cartoon: about 1 scene metre = 11 real metres for the mountain, so Max stays "
                   "readable next to the machines",
}

# The story is a ladder: these happen in this order, all required (the set's state depends on it).
STORY_ORDER = ["setup", "fail_flat", "raise_head", "fail_pipe", "tunnel", "fail_empty", "pump_turbines",
               "fail_shudder", "variable_speed", "finale"]

ACTIONS = {
    # ---- hooks (staged on the finished set, shown FIRST, before the rewind) ----
    "empty_hook": {"kind": "hook", "shows": "Dusk on the summit: Max stands at the bottom of his drained upper "
                   "reservoir, only a puddle around his boots, looking around in disbelief, while his two kids stand "
                   "on the rim holding glowing camping lanterns."},
    "movie_hook": {"kind": "hook", "shows": "Payoff first: night in the valley, the outdoor movie screen glows, Max's "
                   "two kids sit on a bench watching it with their lanterns dark, Max cheering beside them."},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the whole story plays BACKWARDS (VHS look) "
               "to a sunny afternoon. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "setup": {"kind": "story", "shows": "Sunny afternoon in the valley: rows of solar panels gleam beside Max's "
              "house; his two kids already stand in the yard holding (unlit) camping lanterns for tonight's outdoor "
              "movie. Max points from the panels up to the mountain, grinning.", "seconds": (4, 7)},
    "fail_flat": {"kind": "fail", "shows": "Max's first battery: a concrete pond sunk beside the lower lake, both water "
                  "surfaces at nearly the same height (label TINY HEAD), a pipe to the turbine in the deep "
                  "powerhouse. He flips the switch: the turbine barely creeps round and his test bulb only glows "
                  "faintly. Dusk: the kids wait with lit lanterns.", "seconds": (4, 7)},
    "raise_head": {"kind": "fix", "shows": "The whole upper reservoir lifts out of its pit and rises up the mountain "
                   "to the summit (rumble), Max riding up on its wall crest, waving. Blue pressure arrows along the "
                   "rock face grow longer as it climbs; a yellow dimension line from the top water down to the lake "
                   "reads HEAD 150 m. On the summit Max gives a proud thumbs up.", "seconds": (4, 7)},
    "fail_pipe": {"kind": "fail", "shows": "Max connects the summit reservoir with a skinny red pipe that zigzags all "
                  "the way down the cliff to the turbine. Water sputters through it, red FRICTION arrows push back at "
                  "the bends, the turbine jerks and his test bulb flickers. Max facepalms; the kids raise their "
                  "lanterns at dusk.", "seconds": (4, 7)},
    "tunnel": {"kind": "fix", "shows": "The skinny pipe is gone: a boring machine chews a big pressure tunnel down "
               "through the rock section from the summit reservoir to the powerhouse (dust, rumble). The lined "
               "tunnel floods with fast-moving water (label 7 m TUNNEL, big blue arrows down), the turbine spins "
               "hard and the bulb blazes. Max cheers.", "seconds": (4.5, 8)},
    "fail_empty": {"kind": "fail", "shows": "The power runs... while the summit reservoir drains lower and lower until "
                   "it is empty, the lake below rises a little, the turbine winds down and the bulb dies. Max peers "
                   "into the empty basin, jaw dropping. Night: the kids sit in the dark with only their lanterns.",
                   "seconds": (4, 7)},
    "pump_turbines": {"kind": "fix", "shows": "Next morning in the deep cylindrical powerhouse: the old turbine is "
                      "lifted out and two blue reversible pump-turbines drop in (label PUMP-TURBINES, 2 x 125 MW). "
                      "Yellow solar arrows run down into the powerhouse, the machines spin BACKWARDS and blue arrows "
                      "point UP the tunnel as the water climbs back and the summit reservoir refills.",
                      "seconds": (4.5, 8)},
    "fail_shudder": {"kind": "fail", "shows": "Evening, generating: the summit reservoir drops and the yellow HEAD "
                     "dimension shrinks (HEAD 175 m, then HEAD 125 m). Down in the powerhouse the fixed-speed "
                     "machines start to shake and rattle (label FIXED SPEED), dust falls, lamps flicker, Max clutches "
                     "his hard hat. The kids wait with lanterns.", "seconds": (4, 7)},
    "variable_speed": {"kind": "fix", "shows": "Green variable-speed rings light up on both motor-generators, converter "
                       "cabinets and a big rpm dial appear (label 285-315 rpm); the dial's needle glides as the "
                       "reservoir falls and the machines run smooth and quiet. Max wipes his brow, thumbs up.",
                       "seconds": (4, 7)},
    "finale": {"kind": "story", "shows": "The full cycle: by day yellow solar arrows run down into the powerhouse and "
               "blue arrows push water UP the tunnel; at sunset the blue arrows flip DOWN, yellow electricity arrows "
               "race along the power line to the house, its windows light up and the movie projector starts. The "
               "two kids sit on a bench watching the glowing screen, lanterns dark, Max cheering beside them. "
               "(The ending: the mountain battery works.)", "seconds": (6, 10)},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'150 m','text':'of head'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Pump-turbines'} (names a part, never a number)"}
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
        errs.append("beat 1 must be a hook action (empty_hook or movie_hook)")
    if len(acts) < 2 or acts[1] != "rewind":
        errs.append("beat 2 must be 'rewind'")
    hooks = [a for a in acts if ACTIONS.get(a, {}).get("kind") == "hook"]
    if len(hooks) != 1:
        errs.append(f"exactly one hook action is allowed (got {hooks})")
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
