"""Vocabulary of the inline-4 kit (cutaway/blender/assemblies/inline4.py builds and animates it)."""

KIT = {
    "assembly": "inline4",
    "subject": "a car engine: DOHC 16-valve inline-4 petrol engine (2.0 L class, 86 x 86 mm bore and stroke)",
    "topics": ["how a car engine works", "four-stroke engine", "internal combustion engine", "inline-4",
               "petrol engine", "gasoline engine", "how pistons work", "engine cylinder"],
    # the A-to-Z story: a full explainer covers every chapter, in this order
    "story": ["air_fuel", "intake_stroke", "compression_stroke", "power_stroke", "exhaust_stroke", "crank",
              "valvetrain", "firing_order", "output"],
    "mechanisms": {
        "air_fuel": {"explains": "air is pulled in through the throttle and the intake manifold; an injector sprays "
                                 "a fine mist of fuel into it at the intake valves",
                     "cut": "xray", "cameras": ["intake_side", "injector_close", "hero_34"],
                     "anchors": ["throttle_body", "intake_manifold", "injector_1", "intake_port_1"]},
        "intake_stroke": {"explains": "the piston slides down, the intake valve opens and the air-fuel mix rushes "
                                      "into the cylinder",
                          "cut": "transverse_1", "cameras": ["stroke_close", "section_front", "chamber_close"],
                          "anchors": ["piston_1", "intake_valve_1", "intake_port_1", "combustion_chamber_1"]},
        "compression_stroke": {"explains": "both valves shut and the piston rises, squeezing the mix into a tiny "
                                           "space at the top",
                               "cut": "transverse_1", "cameras": ["stroke_close", "chamber_close"],
                               "anchors": ["piston_1", "combustion_chamber_1", "intake_valve_1"]},
        "power_stroke": {"explains": "the spark plug fires, a flame races through the mix and the hot gas slams "
                                     "the piston down: the only stroke that makes power",
                         "cut": "transverse_1", "cameras": ["chamber_close", "stroke_close"],
                         "anchors": ["spark_plug_tip_1", "combustion_chamber_1", "piston_1"]},
        "exhaust_stroke": {"explains": "the exhaust valve opens and the rising piston pushes the burnt gas out "
                                       "through the exhaust manifold",
                           "cut": "transverse_1", "cameras": ["stroke_close", "exhaust_close", "chamber_close"],
                           "anchors": ["exhaust_valve_1", "exhaust_port_1", "exhaust_manifold", "piston_1"]},
        "crank": {"explains": "the connecting rod and crankshaft turn the piston's up-and-down push into spinning",
                  "cut": "transverse_1", "cameras": ["crank_close", "section_front", "quarter_hero"],
                  "anchors": ["conrod_1", "crank_pin_1", "crankshaft"]},
        "valvetrain": {"explains": "camshafts on top, turned by the crank at half its speed, push the valves open "
                                   "with egg-shaped lobes; springs snap them shut",
                       "cut": "transverse_1", "cameras": ["valvetrain_close", "chamber_close"],
                       "anchors": ["camshaft_intake", "camshaft_exhaust", "intake_valve_1", "valve_spring_in_1"]},
        "firing_order": {"explains": "the four cylinders take turns firing (1-3-4-2) so the crank always gets a push",
                         "cut": "longitudinal", "cameras": ["longitudinal_side", "longitudinal_close", "hero_34"],
                         "anchors": ["piston_1", "piston_2", "piston_3", "piston_4", "crankshaft"]},
        "output": {"explains": "the heavy flywheel on the end of the crank smooths the pushes and passes the spin "
                               "to the gearbox and on to the wheels",
                   "cut": "xray", "cameras": ["flywheel_close", "hero_low", "hero_34"],
                   "anchors": ["flywheel", "crankshaft"]},
        "cooling": {"explains": "coolant flows through passages around the cylinders to carry heat away",
                    "cut": "transverse_1", "cameras": ["section_front", "section_wide"],
                    "anchors": ["water_jacket", "combustion_chamber_1"]},
    },
    "anchors": {
        "piston_1": "crown of piston 1 (moves up and down)",
        "piston_2": "crown of piston 2", "piston_3": "crown of piston 3", "piston_4": "crown of piston 4",
        "combustion_chamber_1": "the space above piston 1 where the mixture burns",
        "spark_plug_tip_1": "spark plug electrode of cylinder 1",
        "intake_valve_1": "an intake valve of cylinder 1", "exhaust_valve_1": "an exhaust valve of cylinder 1",
        "valve_spring_in_1": "intake valve spring of cylinder 1",
        "camshaft_intake": "intake camshaft", "camshaft_exhaust": "exhaust camshaft",
        "intake_port_1": "intake port (air-fuel in)", "injector_1": "fuel injector of cylinder 1 (sprays fuel)",
        "exhaust_port_1": "exhaust port (burnt gas out)",
        "conrod_1": "connecting rod of cylinder 1", "crank_pin_1": "crank pin of cylinder 1 (moves in a circle)",
        "crankshaft": "crankshaft", "flywheel": "flywheel", "water_jacket": "coolant passages",
        "oil_pan": "oil pan / sump", "throttle_body": "throttle body (air in)",
        "intake_manifold": "intake manifold", "exhaust_manifold": "exhaust manifold",
        "cylinder_head": "cylinder head", "engine_block": "engine block",
    },
    # anchors a camera can see on the closed engine; every other anchor needs a cut (or X-ray) to be visible
    "exterior_anchors": ["throttle_body", "intake_manifold", "exhaust_manifold", "cylinder_head", "engine_block",
                         "oil_pan", "flywheel", "injector_1"],
    "cuts": {
        "transverse_1": "sliced across through cylinder 1: one cylinder's full cycle, valves, plug, ports, crank",
        "longitudinal": "sliced lengthwise along the crank: all four pistons and the crankshaft side by side",
        "quarter_1": "front-left quarter removed: the outside and the inside in one 3/4 view",
    },
    # besides the cuts there are two whole-engine states: "closed" (solid) and "xray" (see-through castings:
    # every moving part, the air, fuel, flame and exhaust visible in context)
    "cameras": {
        "hero_34": ("closed or quarter_1 or xray", "the whole engine from the front-left, three-quarter, wide"),
        "hero_low": ("closed or xray", "low dramatic angle on the whole engine"),
        "exhaust_side": ("closed or xray", "the exhaust side, headers in view"),
        "intake_side": ("closed or xray", "the intake side: throttle, manifold runners into the head (in X-ray: "
                                          "the air streaming in)"),
        "injector_close": ("xray", "close on an injector spraying fuel into the air at the intake valves"),
        "exhaust_close": ("xray", "close on the exhaust port and manifold, burnt gas streaming out"),
        "flywheel_close": ("closed or xray", "the flywheel at the back of the crank, where the spin leaves for "
                                             "the gearbox"),
        "section_front": ("transverse_1", "face-on to the cut: the whole cylinder 1 section, head to crank"),
        "section_wide": ("transverse_1", "wider 3/4 of the cut engine"),
        "stroke_close": ("transverse_1", "tight on cylinder 1 from the valves to the crank pin: one cylinder's "
                                         "strokes, the gas colour showing each one"),
        "chamber_close": ("transverse_1", "close on the combustion chamber, valves and spark plug"),
        "valvetrain_close": ("transverse_1", "close on the camshafts, buckets, springs and valves"),
        "crank_close": ("transverse_1", "close on the connecting rod big end and crank"),
        "quarter_hero": ("quarter_1", "3/4 view into the quarter cut"),
        "longitudinal_side": ("longitudinal or xray", "side-on: all four cylinders"),
        "longitudinal_close": ("longitudinal or xray", "closer on cylinders 1-2 side-on"),
    },
    "events": {
        "intake_start": "a cylinder's piston starts down on its intake stroke",
        "compression_start": "a cylinder's piston starts up with both valves shut (compression)",
        "exhaust_start": "a cylinder's piston starts up pushing the burnt gas out (exhaust)",
        "spark": "the spark plug of a cylinder fires (lock it to a word)",
        "intake_open": "intake valves of a cylinder start to open",
        "exhaust_open": "exhaust valves of a cylinder start to open",
        "tdc_firing": "a piston at top dead centre at the moment of firing",
    },
    # crank angles (deg, 0..720 cycle) at which each event happens for cylinder 1; other cylinders are offset
    "event_angles": {"spark": 348.0, "intake_open": 712.0, "exhaust_open": 492.0, "tdc_firing": 360.0,
                     "intake_start": 0.0, "compression_start": 180.0, "exhaust_start": 540.0},
    "cycle_offsets": {1: 0.0, 2: 540.0, 3: 180.0, 4: 360.0},
    "drive": "crank",                          # events are pinned to crank angles (see stages/shotlist.py)
    "units": [1, 2, 3, 4],                     # what an event's "unit" numbers: the cylinder
    "event_sfx": {"spark": "spark"},           # automatic sound for an event in a visible (cut) shot
    "bed": ["engine idle", "car engine idle", "engine running"],   # recorded loop, varispeeded to the crank
    "research_scope": "true for a typical modern petrol (gasoline) car engine or for the four-stroke principle",
    # on-screen stroke tracker: the unit's cycle angle picks the lit chip (span degrees each)
    "tracker": {"unit": 1, "span": 180.0, "labels": ["INTAKE", "COMPRESSION", "POWER", "EXHAUST"],
                "mechanisms": ["intake_stroke", "compression_stroke", "power_stroke", "exhaust_stroke"]},
    "loop_hint": "open and close on the same closed hero_34 view with the crank at the same angle",
}
