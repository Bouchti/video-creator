"""
RECORD-CHASING GIANT PUMPKIN STORY set — Max grows a giant pumpkin by trial and error, shown as a
backyard pumpkin-patch cutaway (the ground sliced open on the front face, so we see the plant above
the soil and its roots below it). Each naive attempt fails for a real growing reason; each fix is
what real giant-pumpkin growers do. Pure data (no Blender), read by the showrunner and enforced by
engine/sets/record_chasing_giant_pumpkin_story.py.
"""

SET_ID = "record_chasing_giant_pumpkin_story"
SUBJECT = ("Max, a well-meaning, overconfident gardener dad (straw hat, dungarees, big mustache), grows a giant "
           "pumpkin big enough for his two kids to sit on at the town weigh-off, shown as a 3D cutaway diorama "
           "of his backyard pumpkin patch: the ground is sliced open on the front so we see the vine, leaves and "
           "pumpkin above the soil and the roots, soil layers and drip line below it. His kids wait at the fence "
           "with a little red wagon they are sure will carry the pumpkin")
HERO = "Max"

MODEL_FACTS = {
    "the patch": "one giant pumpkin plant: a long green vine with broad leaves, a small wooden fence, a garden "
                 "shed, brown topsoil over darker subsoil in the cut face, and a platform scale with a digital "
                 "display at the edge of the yard",
    "why it stayed small": "one root clump under the main stem can't supply a fast-growing giant pumpkin with "
                           "enough water and nutrients, so the fruit stays small and the leaves droop in the heat",
    "the fix for roots": "bury the vine under a thin layer of soil: every leaf joint can grow its own roots, so a "
                         "buried vine turns one root system into dozens of feeding points",
    "why it split": "watering in big irregular floods (dry days, then a huge soak) makes the inside swell faster "
                    "than the skin can stretch, so the pumpkin splits open along a rib",
    "the fix for splitting": "a buried drip line on a timer gives a small, steady amount of water every day: steady "
                             "water means steady growth, so the skin keeps up with the inside",
    "growth": "at peak growth a giant pumpkin can gain 20 kg or more in a single day",
    "why the stem cracked": "the fruit gets wider and taller every day, shoving the stem and vine out of line and "
                            "bending the stem until it tears",
    "the fix for the stem": "keep the stem at 90 degrees to the vine (and keep moving the vine as the pumpkin grows), "
                            "so the growing pumpkin rolls the stem instead of ripping it",
    "why the bottom rotted": "a pumpkin heavier than a car presses its skin into damp soil that never dries, so the "
                             "underside stays wet and starts to rot",
    "the fix for rot": "a bed of clean sand under the pumpkin drains fast and lets the pumpkin slide as it widens, "
                       "so the bottom stays dry",
    "why lifting failed": "the pumpkin weighs well over a tonne and is round, soft-skinned and slippery: no person, "
                          "plank or bare strap can grip it without crushing or dropping it",
    "the fix for lifting": "a growers' lifting ring: a ring on top with wide straps spread evenly down the sides and "
                           "under the pumpkin, lifted by a forklift onto a pallet; spreading the weight over many "
                           "wide straps means no single spot on the skin takes the whole load",
    "the record": "in October 2026 Ron Wallace of Warren, Rhode Island grew a pumpkin that weighed 3,156 pounds "
                  "(about 1,431 kg), heavier than many small cars: the first pumpkin ever over 3,000 pounds. It "
                  "was moved the same way, with a lifting ring and a forklift",
    "Max's result": "Max's pumpkin weighs well over a tonne on the scale: far below the record, but big enough "
                    "for both kids to sit on",
}

# The story is a ladder: these happen in this order, all required (the set's state depends on it).
STORY_ORDER = ["plant", "fail_roots", "bury_vine", "fail_split", "drip_line", "fail_stem", "fix_angle",
               "fail_rot", "sand_bed", "fail_lift", "lift_ring", "finale"]

ACTIONS = {
    # ---- hooks (staged after the finale, shown FIRST, before the rewind) ----
    "split_hook": {"extras": "A water puddle spreads over the bed and the cut face shows dark wet soil, and the kids and wagon are hidden.", "kind": "hook", "shows": "Max stands deadpan beside his giant pumpkin holding a garden hose; the "
                   "pumpkin swells and splits down one rib with a loud crack and a spray of water. He blinks."},
    "photo_hook": {"extras": "The empty red wagon is parked in the front of the shot beside the scale.", "kind": "hook", "shows": "Payoff first: the giant pumpkin sits on the weigh-off scale, the digits "
                   "show a big number, Max's two kids sit on top of it cheering and Max salutes."},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the whole story plays BACKWARDS (VHS look) "
               "to bare spring soil. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "plant": {"extras": "A tiny root grows down from the seed in the cut face, then Max points at the sprout with a big grin.", "kind": "story", "shows": "Spring. Max kneels and plants a single seed in the cutaway soil (the seed "
              "is visible in the cut face) and a tiny sprout pops up. His two kids pull their little red wagon up "
              "to the fence and park it, ready.", "seconds": (4, 7)},
    "fail_roots": {"extras": "The light turns a hot orange, and Max first faces the pumpkin, then turns to the camera with raised brows.", "kind": "fail", "shows": "Hot afternoon. The plant has a long vine but the pumpkin is tiny and the "
                   "big leaves droop. The cutaway shows ONE short root ball under the main stem while the rest of the "
                   "vine lies on top of the soil with no roots. Max scratches his head; the kids look at their wagon, "
                   "then at the tiny pumpkin.", "seconds": (4, 7)},
    "bury_vine": {"extras": "Brown dust puffs rise from each new mound, then Max points at the new roots with a big grin while the kids stand at the fence.", "kind": "fix", "shows": "Max kneels and covers the vine with little mounds of soil; in the cutaway "
                  "new pale roots grow down from every leaf joint, with small yellow arrows pointing down from each "
                  "joint. The leaves perk up and the pumpkin starts to grow.", "seconds": (4, 7)},
    "fail_split": {"extras": "During the dry spell the sun turns hot orange and the leaves wilt, then they recover at the second soak; Max slowly turns to the camera with flat brows and two slow blinks, and the kids look at the wagon, then at the pumpkin.", "kind": "fail", "shows": "Max waters with the hose in big floods: a puddle spreads and the soil "
                   "darkens, then it dries out, then another huge soak. The pumpkin swells in jerks until it splits "
                   "down one rib with a crack and water spurts out. Max stands deadpan with the hose; the kids look "
                   "at the wagon, then at the pumpkin.", "seconds": (4.5, 7)},
    "drip_line": {"extras": "The timer has a glowing green light, and Max then turns to watch the growing pumpkin while the kids stand at the fence.", "kind": "fix", "shows": "A thin black drip line is drawn through the cutaway soil next to the "
                  "roots, a small timer box pops onto the tap, and even blue droplets fall from the line. A new "
                  "pumpkin grows smoothly and steadily, bigger and bigger. Max points at the timer, grinning.",
                  "seconds": (4, 7)},
    "fail_stem": {"extras": "A red 'STEM TEARS!' label pops up as pale torn fibres show in the break, Max throws his arms out with raised brows, and the kids look at the wagon, then at the pumpkin.", "kind": "fail", "shows": "The pumpkin grows huge and its swelling side shoves the vine up and back: "
                  "an arrow shows the vine being pulled, the vine kinks and the stem bends until a dark crack opens "
                  "around it. Max's jaw drops.", "seconds": (4, 7)},
    "fix_angle": {"extras": "Max crouches and pats the vine into place, then gives a thumbs up with a big smile.", "kind": "fix", "shows": "Max gently curves the vine so it leaves the stem at a right angle and "
                  "keeps nudging it as the pumpkin grows; an orange right-angle marker labelled 90° appears at the "
                  "joint. The pumpkin keeps growing and the stem stays whole.", "seconds": (3.5, 6)},
    "fail_rot": {"extras": "Max raises his brows and glances down at the worm in the middle of his thumbs up, and the kids look at the wagon, then at the pumpkin.", "kind": "fail", "shows": "Above ground the giant pumpkin looks perfect, but the low cutaway view "
                 "shows its underside pressed into dark wet soil, a brown rot patch spreading on the skin and a "
                 "worm waving out of the mud. Max gives a brave thumbs up.", "seconds": (4, 7)},
    "sand_bed": {"extras": "The sand pile shrinks as Max rakes (the worm is gone), then he turns to the camera and points with a big grin.", "kind": "fix", "shows": "Max rakes clean sand from a pile under the pumpkin: a beige sand layer "
                 "builds up beneath it in the cutaway and the pumpkin rides up onto it, the wet soil dries and blue "
                 "arrows show the water draining down through the sand.", "seconds": (3.5, 6)},
    "fail_lift": {"extras": "Max crouches, strains and pants while hugging the pumpkin, the block and planks pop into place, and when the plank goes flat he raises his brows and his mouth shrinks to a small 'o'.", "kind": "fail", "shows": "Harvest day. Max and the kids push the tiny red wagon up to the giant "
                  "pumpkin. Max tries to lift it with his arms (nothing), then with a plank over a block: he pushes "
                  "down and the plank bends flat while the pumpkin doesn't budge. The kids look at the wagon, then at "
                  "the pumpkin.", "seconds": (5, 8)},
    "lift_ring": {"extras": "Max points as the forklift drives in, then he and the kids at the fence cheer when the pumpkin lands on the pallet.", "kind": "fix", "shows": "An orange lifting ring sits on top with wide straps running down around "
                  "the sides and under the pumpkin; a yellow forklift drives in, hooks the ring with chains and lifts "
                  "the pumpkin while yellow arrows on every strap show the load shared out; a pallet slides under "
                  "and the pumpkin is set down on it.", "seconds": (5, 8)},
    "finale": {"extras": "The kids cheer with their arms up as they ride, the forklift backs away from the scale, and the empty wagon is parked in the front of the shot for the photo.", "kind": "story", "shows": "The forklift carries the pumpkin on its pallet to the weigh-off scale with "
               "Max pulling the red wagon right behind it and both kids riding proudly in it. The pumpkin is "
               "lowered onto the scale and the digits roll up to a big number; the kids sit on top of the pumpkin, "
               "in one piece, cheering, and Max salutes.", "seconds": (6, 9)},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'20 kg','text':'in a single day'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Lifting ring'} (names a part, never a number)"}
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
        errs.append("beat 1 must be a hook action (split_hook or photo_hook)")
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
