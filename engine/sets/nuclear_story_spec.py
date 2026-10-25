"""
NUCLEAR STORY set — Max builds a nuclear power station for his town by trial and error. Each
naive attempt fails for a real physical reason; each fix is the real engineering. Pure data
(no Blender), read by the showrunner and enforced by engine/sets/nuclear_story.py.
"""

SET_ID = "nuclear_story"
SUBJECT = ("Max, a well-meaning, overconfident DIY dad (orange hard hat, big mustache), builds a nuclear power "
           "station next to his town so everyone gets electricity, shown side-on as a 3D cutaway diorama: "
           "reactor core, steam turbine, generator, cooling tower and the town's houses")
HERO = "Max"

MODEL_FACTS = {
    "the station": "a pressurised-water reactor (the most common kind): a steel vessel of water with uranium "
                   "fuel rods inside, a steam turbine and generator, a condenser and a cooling tower",
    "fission": "when a uranium-235 atom absorbs a neutron it splits into two smaller atoms, releasing heat and "
               "2 or 3 new neutrons, which can split more atoms: a chain reaction",
    "fuel": "the fuel is ceramic uranium pellets about the size of a fingertip, stacked inside metal tubes "
            "(fuel rods); one pellet releases roughly as much energy as a tonne of coal",
    "why it ran away": "with nothing to soak up spare neutrons, each split triggers more splits and the power "
                       "climbs; real reactors are designed so this cannot happen unchecked",
    "control rods": "rods of neutron-absorbing material (boron, cadmium or hafnium) slide between the fuel "
                    "rods: push them in and the reaction slows, pull them out and it speeds up; dropping them "
                    "all the way in shuts the reactor down",
    "why no electricity": "a reactor only makes heat; heat is not electricity",
    "turbine and generator": "the heat boils water into high-pressure steam that spins a turbine; the turbine "
                             "turns a generator, where magnets spinning inside copper coils make electricity",
    "why it choked": "steam leaving the turbine has to be turned back into water, or pressure builds up "
                     "behind the turbine, it slows down, and the water supply runs out",
    "condenser and cooling tower": "a condenser cools the used steam back into water with cold water from a "
                                   "cooling tower or a river; the water goes round again. The cloud above a "
                                   "cooling tower is just water vapour, not smoke",
    "why the Geiger counter clicked": "the fuel gives off radiation; without shielding it is dangerous to be "
                                      "near the core",
    "containment": "the reactor sits inside a steel-lined, reinforced concrete containment building with walls "
                   "about a metre thick, and the water around the core also shields radiation",
}

STORY_ORDER = ["build_core", "fail_runaway", "control_rods", "fail_no_power", "turbine", "fail_pressure",
               "cooling", "fail_geiger", "containment", "finale"]

ACTIONS = {
    # ---- hooks (staged after the finale, shown FIRST, before the rewind) ----
    "boil_hook": {"kind": "hook", "shows": "Max's homemade reactor is boiling over: red alarm light spinning, "
                  "steam bursting out of the lid, Max peeking out from behind it with wide eyes."},
    "lights_hook": {"kind": "hook", "shows": "Payoff first: at night the whole town lights up house by house "
                    "from Max's station, the cooling tower puffs, his two kids cheer."},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the whole story plays BACKWARDS (VHS "
               "look) to an empty field. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "build_core": {"kind": "story", "shows": "In an empty field Max sets up a steel tank of water and lowers "
                   "uranium fuel rods into it (cutaway: the rods stand in the water). The water starts to glow "
                   "blue. Proud thumbs up.", "seconds": (4, 7)},
    "fail_runaway": {"kind": "fail", "shows": "The glow gets brighter and brighter, the water boils, steam "
                     "bursts from the top, a red alarm light spins. Max dives for cover.", "seconds": (4, 7)},
    "control_rods": {"kind": "fix", "shows": "A frame of dark control rods is lowered between the fuel rods; "
                     "the boiling calms, the glow settles to a steady blue. Labels: CONTROL RODS.",
                     "seconds": (4, 7)},
    "fail_no_power": {"kind": "fail", "shows": "Max holds a light bulb up to the hot reactor. Nothing. He "
                      "shakes it, taps it. Still dark. He scratches his head.", "seconds": (3.5, 6)},
    "turbine": {"kind": "fix", "shows": "A steam pipe runs from the reactor to a turbine and generator; steam "
                "flows, the turbine blades spin up, the generator hums and Max's bulb lights up. Labels: "
                "TURBINE, GENERATOR.", "seconds": (4, 7)},
    "fail_pressure": {"kind": "fail", "shows": "Used steam piles up behind the turbine with nowhere to go: the "
                      "pressure gauge needle swings into the red, steam hisses out of the joints, the turbine "
                      "slows to a stop. Max covers his ears.", "seconds": (3.5, 6)},
    "cooling": {"kind": "fix", "shows": "A condenser and a big cooling tower are added; the steam turns back "
                "into water and flows round again, the turbine spins steadily, a white cloud of water vapour "
                "rises from the tower. Labels: CONDENSER, COOLING TOWER.", "seconds": (4, 7)},
    "fail_geiger": {"kind": "fail", "shows": "Max walks up to the open reactor with a Geiger counter; it clicks "
                    "faster and faster as he gets closer, his mustache bristles, he backs away slowly.",
                    "seconds": (3.5, 6)},
    "containment": {"kind": "fix", "shows": "Thick concrete walls with a steel lining rise around the reactor "
                    "and close into a dome; the Geiger counter goes quiet. Label: CONTAINMENT.",
                    "seconds": (4, 7)},
    "finale": {"kind": "story", "shows": "Night. Max pulls a big lever, power runs along the lines and the "
               "town's houses light up one by one, the cooling tower puffs, his kids cheer next to him. (The "
               "ending: it works, safely.)", "seconds": (5, 8)},
    # ---- optional explainer ----
    "chain": {"kind": "explain", "after": "build_core", "shows": "A cutaway card: one neutron hits a uranium "
              "atom, it splits in two and releases heat and three new neutrons, which hit three more atoms: a "
              "chain reaction.", "seconds": (3, 5)},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'1 tonne','text':'of coal per pellet'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Control rods'} (names a part, never a number)"}
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
        errs.append("beat 1 must be a hook action (boil_hook or lights_hook)")
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
