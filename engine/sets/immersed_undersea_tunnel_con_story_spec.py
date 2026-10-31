"""
IMMERSED UNDERSEA TUNNEL story set: ONE vertical cutaway of a narrow sea strait (beach with a dry dock on the
left, an island picnic on the right, the sea cut open like an aquarium over layered seabed). Max wants to DRIVE
his family car under the sea to his kids' picnic. Each naive attempt fails for a real physical reason and each
fix is how immersed-tube tunnels are really built. Pure data (no Blender), read by the showrunner and enforced
by engine/sets/immersed_undersea_tunnel_con_story.py.
"""

SET_ID = "immersed_undersea_tunnel_con_story"
SUBJECT = ("Max, a well-meaning, overconfident DIY dad (orange hard hat, big mustache), builds an immersed-tube "
           "road tunnel under a sea strait so he can drive his family car to his two kids' island picnic, shown "
           "as one 3D cutaway: water volume above sand and dark soaked clay, a dry dock on the beach")
HERO = "Max"

MODEL_FACTS = {
    "the strait": "a narrow sea strait about 40 m deep",
    "water pressure": "every 10 m of seawater adds about one atmosphere of pressure (about 1 bar); at 40 m the "
                      "water pushes about 4 atmospheres on top of the air above",
    "seabed": "soft, water-soaked sand on top of dark soaked clay with gravel lenses: not solid ground",
    "why the shovel tunnel failed": "soaked soil under the full weight of the sea is squeezed into any hole: "
                                    "mud and water squirt in and flood the bore",
    "the fix for digging": "do not burrow: a grab dredger scoops an open trench in the seabed, and the tunnel "
                           "is built dry, on land, in a dry dock",
    "the element": "a huge concrete box with two road bores, its ends sealed by temporary steel bulkheads",
    "why it floated": "a sealed hollow box pushes aside more water than it weighs, so it floats like a ship",
    "the fix for floating": "floating is the delivery method: tugboats tow it over the trench, valves let seawater "
                            "into ballast tanks inside until it is just heavier than the water, and winches "
                            "lower it slowly, guided to within millimetres",
    "why the joint leaked": "two huge concrete blocks never meet perfectly; the sea forces its way into any gap",
    "the fix for the joint": "a thick rubber gasket ring on the end of the new element; jacks pull it into contact, "
                             "pumps empty the small water-filled space between the two bulkheads, then the full "
                             "sea pressure on the FAR end shoves the element home and squashes the rubber shut: "
                             "the sea itself is the clamp. A second safety seal is clamped inside over the joint",
    "why the anchor cracked it": "a tube lying bare on the seabed can be hit by dragged ship anchors and pushed by "
                                 "currents",
    "the fix for anchors": "a stone-dumping vessel pours gravel along both sides to lock it in place, then backfill "
                           "and a rock-armour blanket bury the tunnel in its trench; anchors bounce off the rocks",
    "finish": "bulkheads are cut away inside, lights and road go in, cars drive through dry",
    "the giant version": "a real immersed tunnel can be a chain of 89 long blocks across an 18 km strait",
}

STORY_ORDER = ["goal", "fail_dig", "fix_trench", "fail_float", "fix_ballast", "fail_leak", "fix_seal",
               "fail_anchor", "fix_armor", "drive", "finale", "scale"]

ACTIONS = {
    # ---- hooks (staged after the finale, shown FIRST, before the rewind) ----
    "float_hook": {"kind": "hook", "seconds": (3, 4.5),
                   "shows": "Max stands on the roof of a sealed concrete tunnel block that floats out of the dry "
                            "dock across the sea.",
                   "must_see": ["S1_front", "S1_roof", "Max"],
                   "extras": "Max points, his jaw drops, then he shrugs with arms out while a seagull lands on "
                             "his hard hat."},
    "happy_hook": {"kind": "hook", "seconds": (3, 4.5),
                   "shows": "Payoff first: Max drives his family car through the lit, dry tunnel under the sea.",
                   "must_see": ["car", "tunnel_light", "Max"],
                   "extras": "The seagull rides on the dashboard; a ship's hull passes far above in the blue water."},
    "rewind": {"kind": "rewind", "seconds": (1.5, 2.5),
               "shows": "Freeze-frame, record scratch, the story plays backwards to the empty beach. Narration: a "
                        "one-line bridge."},
    # ---- the ladder ----
    "goal": {"kind": "story", "seconds": (4, 6),
             "shows": "Max stands on the beach beside his family car and points across the sea strait.",
             "must_see": ["Max", "car"],
             "extras": "A short insert of his two kids waving from the island picnic blanket; the seagull sits on "
                       "the car's dashboard."},
    "fail_dig": {"kind": "fail", "seconds": (6, 8),
                 "shows": "Max's shovel tunnel under the sea floods with mud as big blue sea-pressure arrows "
                          "squeeze the soaked clay in on it.",
                 "must_see": ["bore_flood", "arrow_press", "Max"],
                 "extras": "Mud squirts from the tunnel's end wall and drips from its roof; Max's jaw drops, then "
                           "he shrugs knee-deep in mud. Labels 'SEA PRESSURE 4 ATM' and 'SOAKED CLAY'."},
    "fix_trench": {"kind": "fix", "seconds": (5, 7),
                   "shows": "A grab dredger scoops the soft seabed out, opening a long trench.",
                   "must_see": ["grab", "dredger", "Max"],
                   "extras": "Max works the controls on the dredger's deck and cheers with both arms up; the "
                             "clamshell grab drops, bites out a block of seabed in a mud puff and lifts it with "
                             "its jaws shut, bite after bite along the trench."},
    "fail_float": {"kind": "fail", "seconds": (6, 8),
                   "shows": "As the dry dock floods, a sealed concrete box rises and floats away; a big blue "
                            "BUOYANCY arrow beats a small yellow WEIGHT arrow.",
                   "must_see": ["S1_front", "arrow_buoy", "Max"],
                   "extras": "Max rides on the roof, his jaw drops, and the seagull lands on his hat; steel "
                             "bulkheads close the box first, the dock gate sinks and water rushes in."},
    "fix_ballast": {"kind": "fix", "seconds": (6.5, 9),
                    "shows": "Inside the cut-open block, ballast tanks fill with blue seawater and winch cables "
                             "lower it slowly into the trench.",
                    "must_see": ["S1_tank", "S1_roof", "Max"],
                    "extras": "Two tugboats first tow it over the trench; Max rides on the roof and cheers as it "
                              "lands. Labels BALLAST TANKS and JUST HEAVIER, a yellow weight arrow beats the blue "
                              "buoyancy arrow."},
    "fail_leak": {"kind": "fail", "seconds": (5, 7),
                  "shows": "Block two lands with a dark gap; seawater jets through the gap into block one and "
                           "floods its floor.",
                  "must_see": ["leak_jet", "leak_pool", "Max"],
                  "extras": "Max is soaked, a fish lands on his hat, he shrugs; blue arrows push the sea into the "
                            "gap and a GAP! label."},
    "fix_seal": {"kind": "fix", "seconds": (6, 8.5),
                 "shows": "A black rubber gasket sits between the blocks; blue sea-pressure arrows shove block two "
                          "home and squash the rubber shut.",
                 "must_see": ["S2_gasket", "arrow_clamp", "Max"],
                 "extras": "Roof jacks pull first, then Max's pump drains the blue water between the two grey "
                           "bulkheads; an inner safety seal is clamped over the joint and Max cheers."},
    "fail_anchor": {"kind": "fail", "seconds": (5.5, 7.5),
                    "shows": "A ship's anchor drags along the seabed into the bare tunnel roof and cracks it.",
                    "must_see": ["anchor", "crack", "Max"],
                    "extras": "Max celebrated on the roof, then leaps behind a rock pile and peeks out; the chain "
                              "runs up to the ship at the surface."},
    "fix_armor": {"kind": "fix", "seconds": (6, 8.5),
                  "shows": "A rock-armour blanket covers the buried tunnel; the next dragged anchor bounces off "
                           "the rocks.",
                  "must_see": ["armour_hit", "anchor", "Max"],
                  "extras": "Max first rides the stone-dumping vessel whose fall pipe pours gravel, then watches "
                            "from the seabed; the big red anchor strikes in a puff of rock dust, a yellow arrow "
                            "shows the rebound, Max points and cheers. A TUNNEL label sits on the buried tube."},
    "drive": {"kind": "story", "seconds": (4.5, 6.5),
              "shows": "Bulkheads are gone, the tunnel lights glow, and Max drives his family car through the dry "
                       "tunnel.",
              "must_see": ["car", "tunnel_light", "Max"],
              "extras": "The seagull rides on the dashboard; a ship passes overhead in the cutaway sea."},
    "finale": {"kind": "story", "seconds": (4, 6),
               "shows": "The car climbs out onto the island; Max and his two kids cheer at the picnic blanket.",
               "must_see": ["car", "Kid1", "Max"],
               "extras": "The seagull sits on the dashboard (running gag payoff); the kids jump for joy."},
    "scale": {"kind": "story", "seconds": (3.5, 5),
              "shows": "Max points at a scale model: a chain of 89 tiny tunnel blocks across a long blue strait, "
                       "labels 89 BLOCKS and 18 km.",
              "must_see": ["scale_model", "Max"],
              "extras": "Max stands right behind the model table, smiling, the island's grass and trees behind "
                        "him."},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'4 atm','text':'at 40 m deep'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Rubber gasket'} (names a part, never a number)"}
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
        if ACTIONS.get(a, {}).get("kind") in ("hook", "rewind") and i > 1:
            errs.append(f"'{a}' can only open the film")
    if len(set(acts)) != len(acts):
        errs.append("each action may be used once")
    return errs
