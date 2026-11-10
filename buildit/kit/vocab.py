"""
The machine kit's vocabulary (pure Python, no Blender): every part the storyboard may place, how parts are
placed and connected, the events a beat may trigger, camera framings, label pills and sound cues.
buildit/blender/kit.py builds and animates exactly these; buildit/kit/check.py rejects anything else.

A subject the kit cannot show is not filmed: the topic stage skips it and logs the missing parts.
"""
from __future__ import annotations

# size presets scale a part's base dimensions (a "large" tank is 1.35x a "medium" one)
SIZES = {"small": 0.7, "medium": 1.0, "large": 1.35}
COLORS = ["red", "orange", "yellow", "green", "blue", "white", "black", "steel", "copper", "brass"]

# type: (what it is, anchors for labels/camera, ports for connections, drivers it can run)
PARTS = {
    # --- everyday objects for hooks and analogies
    "can": ("a food tin can with a coloured label", ["top", "center", "bottom"], [], []),
    "spray_can": ("an aerosol spray can with a nozzle cap (sprays a mist, frosts when emptied fast)",
                  ["nozzle", "center"], ["nozzle"], []),
    "bottle": ("a plastic drink bottle with a cap", ["cap", "center"], ["cap"], []),
    "cup": ("a mug of hot drink (steam can rise from it)", ["top", "center"], ["top"], []),
    "balloon": ("a rubber party balloon on a short neck (inflates, deflates, zooms off)",
                ["center", "neck"], ["neck"], ["inflate"]),
    "candle": ("a candle with a small flame", ["flame", "center"], [], []),
    "ice_cube": ("a clear ice cube (can melt)", ["center"], [], []),
    "ball": ("a rubber ball", ["center"], [], []),
    "firecracker": ("a small red firecracker with a fuse (sparks, then a flash)", ["fuse", "center"], [], []),
    "matchbox": ("a matchbox with a lit match", ["flame", "center"], [], []),
    "kettle": ("a stovetop kettle (steam jet from the spout)", ["spout", "center"], ["spout"], []),
    "fan_desk": ("a small desk fan (spins, blows air)", ["center", "front"], ["front"], ["spin"]),
    "bicycle_wheel": ("a bicycle wheel with pedal crank (spins)", ["hub", "rim", "pedal"], [], ["spin"]),
    # --- housings and containers
    "glass_tube": ("an open clear glass tube with chrome rims", ["top", "center", "bottom", "inside"],
                   ["top", "bottom"], []),
    "glass_tank": ("a sealed clear glass cylinder tank with a brushed base and cap",
                   ["top", "center", "inside", "inlet"], ["inlet", "outlet"], []),
    "glass_box": ("a clear glass cabinet with a brushed frame (a fridge body, an oven, a room)",
                  ["top", "center", "inside", "back"], ["back_in", "back_out"], []),
    "plinth": ("a matte black base plate that machines stand on", ["top"], [], []),
    # --- mechanisms
    "piston_cylinder": ("a clear glass cylinder with a brushed piston, connecting rod and crank below "
                        "(the piston slides; the crank turns)", ["piston", "top", "inside", "crank", "rod"],
                        ["top", "intake", "exhaust"], ["crank"]),
    "piston": ("a brushed aluminium piston with chrome rings", ["top", "center"], [], ["stroke"]),
    "crank_wheel": ("a crankshaft throw with a heavy wheel (turns round)", ["pin", "center", "rim"], [], ["spin"]),
    "flywheel": ("a heavy brushed flywheel disc", ["center", "rim"], [], ["spin"]),
    "gear": ("a brushed spur gear", ["center", "teeth"], [], ["spin"]),
    "gear_pair": ("two meshing gears, small driving big", ["small", "big"], [], ["spin"]),
    "shaft": ("a polished steel shaft (horizontal)", ["center", "end"], [], ["spin"]),
    "wheel": ("a car wheel with a chunky tyre", ["hub", "center"], [], ["spin"]),
    "belt_drive": ("two pulleys linked by a rubber belt", ["drive", "driven"], [], ["spin"]),
    "fan": ("a fan rotor with blades inside a ring duct", ["center", "front"], ["front", "back"], ["spin"]),
    "turbine": ("a bladed turbine disc on a shaft (spun by flowing gas)", ["center", "blades"], ["front", "back"],
                ["spin"]),
    "compressor": ("a squat black compressor with its side cut open: a chrome piston pumps up and down inside "
                   "its cylinder while it runs (squeezes gas)", ["center", "window", "motor"], ["in", "out"],
                   ["pump"]),
    "pump": ("a hand floor pump (handle pushes down)", ["handle", "barrel"], ["outlet"], ["stroke"]),
    "motor": ("an electric motor with a spinning shaft", ["center", "shaft"], [], ["spin"]),
    "spring": ("a chrome coil spring (compresses)", ["top", "center"], [], ["squeeze"]),
    "lever": ("a lever bar on a pivot (tilts)", ["pivot", "end"], [], ["tilt"]),
    "valve": ("a red handwheel valve (turns open or shut)", ["wheel"], ["in", "out"], ["turn"]),
    "nozzle": ("a narrowing brass nozzle (gas speeds up / pressure drops through it)", ["tip", "center"],
               ["in", "out"], []),
    "spark_plug": ("a spark plug (sparks)", ["tip", "top"], [], []),
    "capillary": ("a long, very thin copper tube wound into a tight coil (the expansion device of a fridge or an "
                  "air conditioner: the liquid squeezes through it and its pressure drops)", ["center", "start", "end"],
                  ["in", "out"], []),
    "coil": ("a long copper pipe bent into a flat zig-zag coil (gives off or soaks up heat)",
             ["center", "start", "end"], ["in", "out"], []),
    "radiator": ("a block of thin metal fins with a pipe through it", ["center", "front"], ["in", "out"], []),
    "burner": ("a gas burner ring with a blue flame", ["flame", "center"], [], []),
    "heater": ("a glowing coiled heating element", ["center"], [], []),
    "battery": ("a big battery cell", ["plus", "center"], [], []),
    "bulb": ("a light bulb (glows)", ["center"], [], []),
    "gauge": ("a round dial gauge with a needle (shows a value)", ["needle", "center"], [], ["needle"]),
    "thermostat": ("a round thermostat knob with a temperature scale", ["center"], [], ["turn"]),
    "magnet": ("a red and steel horseshoe magnet", ["poles", "center"], [], []),
    "key": ("a car key", ["tip", "head"], [], []),
}
# (width x, depth y, height z) in metres at size "medium"; the Blender builders respect these
DIMS = {
    "can": (0.16, 0.16, 0.22), "spray_can": (0.13, 0.13, 0.36), "bottle": (0.14, 0.14, 0.42),
    "cup": (0.22, 0.16, 0.18), "balloon": (0.40, 0.40, 0.55), "candle": (0.10, 0.10, 0.30),
    "ice_cube": (0.14, 0.14, 0.14), "ball": (0.20, 0.20, 0.20), "firecracker": (0.26, 0.07, 0.07),
    "matchbox": (0.18, 0.12, 0.06), "kettle": (0.40, 0.26, 0.36), "fan_desk": (0.40, 0.26, 0.56),
    "bicycle_wheel": (0.80, 0.14, 0.80),
    "glass_tube": (0.34, 0.34, 0.76), "glass_tank": (0.46, 0.46, 0.76), "glass_box": (0.80, 0.60, 1.00),
    "plinth": (1.40, 0.80, 0.12), "piston_cylinder": (0.42, 0.42, 1.10), "piston": (0.30, 0.30, 0.30),
    "crank_wheel": (0.60, 0.26, 0.60), "flywheel": (0.60, 0.16, 0.60), "gear": (0.40, 0.09, 0.40),
    "gear_pair": (0.76, 0.09, 0.50), "shaft": (1.00, 0.07, 0.07), "wheel": (0.70, 0.30, 0.70),
    "belt_drive": (0.90, 0.10, 0.46), "fan": (0.60, 0.26, 0.60), "turbine": (0.56, 0.30, 0.56),
    "compressor": (0.50, 0.40, 0.42), "pump": (0.36, 0.14, 0.76), "motor": (0.32, 0.40, 0.30),
    "spring": (0.16, 0.16, 0.40), "lever": (0.90, 0.12, 0.30), "valve": (0.16, 0.16, 0.15),
    "nozzle": (0.20, 0.20, 0.30), "capillary": (0.30, 0.10, 0.30), "spark_plug": (0.06, 0.06, 0.20), "coil": (0.70, 0.08, 0.60),
    "radiator": (0.70, 0.18, 0.56), "burner": (0.30, 0.30, 0.12), "heater": (0.40, 0.10, 0.26),
    "battery": (0.20, 0.20, 0.40), "bulb": (0.16, 0.16, 0.28), "gauge": (0.30, 0.10, 0.30),
    "thermostat": (0.20, 0.08, 0.20), "magnet": (0.30, 0.10, 0.32), "key": (0.22, 0.05, 0.09),
}
assert set(DIMS) == set(PARTS)

# everyday objects that can SHOW an analogy on screen (a person, a pool, a room cannot be filmed in the kit)
PROPS = ["can", "spray_can", "bottle", "cup", "balloon", "candle", "ice_cube", "ball", "firecracker", "matchbox",
         "kettle", "fan_desk", "bicycle_wheel", "pump", "hand", "spring", "magnet", "key", "battery", "bulb"]

# parts a container fill / flow can live inside
CONTAINERS = {"glass_tube", "glass_tank", "glass_box", "piston_cylinder", "balloon", "bottle", "spray_can"}

STAGES = ["front", "left", "right"]                 # prop spots (buildit/kit/hosts.py)
CONNECT = ["pipe", "hose", "wire", "belt"]          # drawn between two ports (or anchors) of two parts

# what moves through a connection, a coil or out of a port; pipes light up with moving dashes in this colour,
# so the viewer SEES the state change (cold blue gas -> hot red gas -> warm orange liquid -> blue again)
FLOWS = {
    "air": "white dashes", "fuel": "yellow dashes", "hot_gas": "red dashes (hot gas)",
    "cold_gas": "light-blue dashes (cold gas)", "hot_liquid": "orange dashes (warm liquid)",
    "cold_liquid": "deep-blue dashes (cold liquid)", "water": "cyan dashes", "steam": "white dashes",
    "exhaust": "grey dashes", "electricity": "yellow-white dashes", "oil": "amber dashes",
}
HEAT_ENDS = ["room"]        # heat_flow can end in the air around the machine; sources may be machine.food
FLOW_COLORS = {
    "air": "#f4f8ff", "fuel": "#ffd23a", "hot_gas": "#ff3b1f", "cold_gas": "#9fe6ff", "hot_liquid": "#ff8a1a",
    "cold_liquid": "#1e40ff", "water": "#28c8ff", "steam": "#ffffff", "exhaust": "#9a948c",
    "electricity": "#fff36b", "heat": "#ff6a1a", "oil": "#e0a030",
}

EVENTS = {
    "appear": "the part arrives: mounted parts default to how = attach (fly in and click into the slot); props "
              "use drop | slide | pop. from = a prop id: the part flies out of that prop into its slot (the "
              "analogy BECOMES the part) and the prop vanishes. target 'machine' makes the machine appear.",
    "remove": "the part leaves: how = fly_up | fly_away | fade | shrink",
    "highlight": "a part glows at its edges to show the viewer where to look (on true/false)",
    "run": "a driver starts at speed slow | normal | fast (spin, crank, pump, stroke, turn...), or stop",
    "set": "a driver goes to a position 0..1 (squeeze a spring, open a valve, inflate a balloon, needle)",
    "flow": "particles stream through a connection or out of a port: on/off, kind from FLOWS",
    "fill": "particles fill a container to a level 0..1 (kind from FLOWS); squeeze 0..1 packs them tighter",
    "flash": "a warm explosion flash at an anchor (bang)",
    "spark": "a small electric spark at an anchor",
    "heat": "a part glows hot (level 0..1)",
    "heat_flow": "HEAT MOVING, shown as warm glowing waves drifting from target to `to`: target = where the heat "
                 "comes from (machine.food = the food inside, a part, part.anchor), to = where it goes (a part id, "
                 "or 'room' = out into the air around the machine); on true/false. Use it to show what a cooling "
                 "or heating machine really does: food -> the cold coil, the hot coil -> room.",
    "frost": "a part frosts cold, pale blue-white (level 0..1)",
    "shake": "a part rattles for a moment",
    "rings": "translucent sound rings pulse out of an anchor",
    "smoke": "a puff of light smoke from an anchor",
    "wash": "the studio wall washes warm (heat, energy) or cold",
}
SPEEDS = {"slow": 0.4, "normal": 1.0, "fast": 2.6}       # turns per second for spin drivers

# machine: the whole machine; area: some parts and what they connect to; part: ONE part fills the frame;
# prop: a prop on its stage spot
FRAMES = ["machine", "area", "part", "prop"]
MOVES = ["hold", "push_in", "pull_back", "orbit"]
LABEL_VARIANTS = ["neutral", "warn", "air", "cold", "done", "chip"]
# extra sound cues (attach clanks, pipe clicks, motor hums, hisses... are added from the events by code)
SFX = ["power_up", "bang", "boil", "bubbles"]


def describe() -> str:
    """The vocabulary as text for the planner prompts."""
    from .hosts import describe as hosts
    parts = "\n".join(f"- {k}: {v[0]}; anchors {', '.join(v[1])}" + (f"; ports {', '.join(v[2])}" if v[2] else "")
                      + (f"; drivers {', '.join(v[3])}" if v[3] else "") for k, v in PARTS.items())
    flows = ", ".join(f"{k} ({v})" for k, v in FLOWS.items())
    events = "\n".join(f"- {k}: {v}" for k, v in EVENTS.items())
    return (f"{hosts()}\n\nPARTS (type: description; anchors; ports; drivers):\n{parts}\n\n"
            f"SIZES: {', '.join(SIZES)}. COLORS: {', '.join(COLORS)}.\n"
            f"CONNECTIONS: {', '.join(CONNECT)} between ports of two mounted parts (routed along the machine).\n"
            f"FLOWS: {flows}.\n\nEVENTS:\n{events}\n\n"
            f"CAMERA: frame {', '.join(FRAMES)}; move {', '.join(MOVES)}.\n"
            f"LABELS: pill variants {', '.join(LABEL_VARIANTS)}, anchored to part.anchor.\n"
            f"SFX: {', '.join(SFX)}.")
