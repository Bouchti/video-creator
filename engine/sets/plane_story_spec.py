"""
PLANE STORY set — Max builds an airplane in his field by trial and error. Each naive attempt
fails for a real aerodynamic reason; each fix is the real solution. Pure data (no Blender),
read by the showrunner and enforced by engine/sets/plane_story.py.
"""

SET_ID = "plane_story"
SUBJECT = ("Max, a well-meaning, overconfident DIY dad (orange hard hat, big mustache), builds a small airplane "
           "in his field so he can fly, shown side-on like a 3D diorama with cutaway diagrams of the wing")
HERO = "Max"

MODEL_FACTS = {
    "the plane": "a small single-seat ultralight: about 5 m long, 8 m wingspan, light wood-and-fabric frame",
    "why flat wings failed": "a flat board held level barely deflects the air, so it makes almost no lift",
    "lift": "a curved wing (an airfoil), tilted slightly up, makes the air over the top flow faster: lower "
            "pressure above, higher below, and the wing is pushed UP",
    "why pushing failed": "lift grows with the square of speed: double the speed, four times the lift. A small "
                          "plane like this needs roughly 60 km/h before the wings can carry it; running gets ~15",
    "thrust": "an engine spins a propeller, which is itself a spinning wing that pulls the plane forward",
    "why it flipped": "with no tail nothing stops the nose from pitching up: it rears up, the wing stalls (the air "
                      "can't follow the top any more) and it falls",
    "stability": "a horizontal tail keeps the nose steady (like the feathers on a dart) and the vertical fin keeps "
                 "it pointing straight; the weight sits slightly ahead of the wing's lift",
    "why it hit the tree": "it could fly but not steer: no control surfaces",
    "controls": "ailerons on the wings roll it into a bank (that is how a plane turns), the elevator on the tail "
                "points the nose up or down, the rudder swings the nose left and right",
    "the four forces": "lift up, weight down, thrust forward, drag back; to climb, lift beats weight; to speed up, "
                       "thrust beats drag",
}

STORY_ORDER = ["build_flat", "fail_flat", "airfoil", "fail_thrust", "engine", "fail_flip", "tail", "fail_turn",
               "controls", "finale"]

ACTIONS = {
    # ---- hooks (staged after the finale, shown FIRST, before the rewind) ----
    "tree_hook": {"extras": "Max is hidden and the pilot Max sits in the cockpit with his brows shooting up, blinking three times, while the plane sinks a little deeper into the leaves and the camera slowly pushes in.", "kind": "hook", "shows": "Max's homemade plane is stuck nose-first in a big oak tree, leaves "
                  "raining down, Max blinking in the cockpit."},
    "fly_hook": {"extras": "The pilot Max smiles the whole time and waves near the end, the propeller spins, the plane comes out of a slight bank, and the kids smile big as they cheer.", "kind": "hook", "shows": "Payoff first: Max's plane swoops low over the field while his two kids "
                 "cheer and wave."},
    "rewind": {"kind": "rewind", "shows": "Freeze-frame, record scratch, the whole story plays BACKWARDS (VHS look) "
               "to an empty field. Narration: a one-line bridge into the story."},
    # ---- the ladder ----
    "build_flat": {"extras": "Max's hammer appears while he works and disappears before his thumbs up, and the plane parts pop in one after another (fuselage first, then the plank wings and struts).", "kind": "story", "shows": "In front of his barn Max hammers together a frame, wheels, a seat and "
                   "two FLAT wooden boards as wings. Proud thumbs up.", "seconds": (3.5, 6)},
    "fail_flat": {"extras": "Max leans over the tail with both arms pushing, then points ahead after letting go ('go on!'); the wheels turn, and the nose dips briefly when it bumps the hay.", "kind": "fail", "shows": "Max shoves it down the field at a run: it rolls and rolls, never lifts, "
                  "and bumps into a haystack. Max scratches his head.", "seconds": (4, 7)},
    "airfoil": {"extras": "A puff of dust hides the wing swap, the diagram sits on a dark blue card, and Max turns to the viewer and points up at it.", "kind": "fix", "shows": "The boards are swapped for curved wings. A big cutaway of the wing section "
                "appears: air streams race faster over the curved top, labels LOW PRESSURE / HIGH PRESSURE, a big "
                "LIFT arrow pushes up.", "seconds": (4, 7)},
    "fail_thrust": {"extras": "The wheels turn, the plane rolls on by itself after Max lets go, and Max crouches bent over with his mouth hanging open, panting.", "kind": "fail", "shows": "Max pushes it again, running as fast as he can: it hops a few "
                    "centimetres and stops. Max collapses, out of breath.", "seconds": (3.5, 6)},
    "engine": {"extras": "Max cheers beside the nose once the propeller starts, and puffs of dust blow out behind the plane.", "kind": "fix", "shows": "An engine and propeller are bolted to the nose; the prop spins up, grass "
               "flattens behind it, a THRUST arrow points forward.", "seconds": (3.5, 6)},
    "fail_flip": {"extras": "The propeller spins until the stall, the wheels turn on the takeoff roll, the pilot Max opens his mouth wide at the top, and the plane bounces when it slams back onto its wheels.", "kind": "fail", "shows": "Max takes off! The nose keeps rising, the plane rears up, stalls and "
                  "flops back down tail-first. Max's eyes go wide.", "seconds": (4, 7)},
    "tail": {"extras": "Max stands behind the tail hammering away, and his hammer disappears at the end.", "kind": "fix", "shows": "A horizontal tail and a vertical fin are added; a WEIGHT arrow and a LIFT "
             "arrow show the balance.", "seconds": (3, 6)},
    "fail_turn": {"extras": "The propeller spins until the crash, then the plane's nose tips down and it leans slightly as it sinks into the leaves, while the pilot Max's brows jump up and his mouth falls open.", "kind": "fail", "shows": "It flies straight and level... straight into the big oak tree, and "
                  "sticks there. Leaves rain down.", "seconds": (4, 7)},
    "controls": {"extras": "Max stands by the nose pointing up at the flaps while the three labels pop in one after another.", "kind": "fix", "shows": "Hinged flaps appear and wiggle: AILERONS on the wings, ELEVATOR and RUDDER "
                 "on the tail.", "seconds": (3.5, 7)},
    "finale": {"extras": "The lighting brightens, the propeller spins the whole time, and the pilot Max smiles, gives a thumbs up and then waves, while the kids cheer during the flight, then run over and turn to the camera, cheering and smiling.", "kind": "story", "shows": "Sunny. Max takes off smoothly, banks a full circle around the field, "
               "and LANDS gently right next to his kids; they run to the plane cheering and he waves from the "
               "cockpit. (The ending: it works, and he lands it.)", "seconds": (5, 8)},
    # ---- optional explainer ----
    "forces": {"extras": "Max stands beside the plane and points at the arrows as they pop in one by one.", "kind": "explain", "after": "engine", "shows": "The plane in flight with four arrows: LIFT up, "
               "WEIGHT down, THRUST forward, DRAG back.", "seconds": (3, 5)},
}

OVERLAY_TYPES = {"stat": "a number that counts up, e.g. {'type':'stat','value':'60 km/h','text':'to take off'}",
                 "label": "a short badge, e.g. {'type':'label','text':'Airfoil'} (names a part, never a number)"}
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
        errs.append("beat 1 must be a hook action (tree_hook or fly_hook)")
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
