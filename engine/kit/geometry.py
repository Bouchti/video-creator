"""
Embankment-world layout (pure math, no Blender: unit-tested). Every position the kit uses comes from
here, so framing, collisions and must-see visibility are decided by numbers, not by trial renders.

Coordinates: x right (river on the left, yard on the right), y into the picture (the cutaway face is
y = 0, the camera looks from -y), z up; ground level z = 0. Lengths in metres.
"""
H0 = 1.5                        # height of the first (sand) barrier: water levels are measured against it
BANK = -3.0                     # river bank edge (ground z = 0 to the right of it)
BED = -1.6                      # river bed
TOPSOIL = -0.45                 # topsoil / sand boundary
SAND_BOTTOM = -1.25             # sand / bedrock boundary
SAND_MID = (TOPSOIL + SAND_BOTTOM) / 2
DECAL_Y = (-0.006, -0.012, -0.018, -0.024)   # layers drawn on the cut face (>= 5 mm apart: no flicker)
STAND_Y = 0.7                   # where characters stand (just behind the cut face)
DUCK_Y = 0.9

# Barrier shapes: height, crest width, water-side and land-side slope (horizontal per vertical).
TRAPEZOIDS = {
    "flat": (0.04, 0.45, 0.4, 0.4),
    "steep": (1.5, 0.45, 0.4, 0.4),
    "wide": (1.5, 0.8, 1.25, 1.25),
    "raised": (1.95, 0.75, 1.05, 1.05),
}


def trapezoid(H, crest, ws, ls):
    """8-point outline (counter-clockwise from the water toe): every profile has the same vertex count, so
    the barrier can morph between them with shape keys."""
    xw, xl = -crest / 2 - ws * H, crest / 2 + ls * H
    return [(xw, 0.0), (xl, 0.0),
            (xl - ls * H / 3, H / 3), (xl - 2 * ls * H / 3, 2 * H / 3),
            (crest / 2, H), (-crest / 2, H),
            (-crest / 2 - ws * H / 3, 2 * H / 3), (-crest / 2 - 2 * ws * H / 3, H / 3)]


def profile(name):
    if name in TRAPEZOIDS:
        return trapezoid(*TRAPEZOIDS[name])
    if name == "slumped":                     # the steep sand wall after its yard side slumped
        s = trapezoid(*TRAPEZOIDS["steep"])
        return [s[0], (1.75, 0.0), (1.2, 0.3), (0.7, 0.62), (0.3, 0.92), (-0.25, 1.12), s[6], s[7]]
    if name == "gouged":                      # the wide barrier with a scour bite out of its yard slope
        w = trapezoid(*TRAPEZOIDS["wide"])
        return [w[0], w[1], (1.75, 0.22), (1.05, 0.62), (0.4, 1.38), w[5], w[6], w[7]]
    raise KeyError(name)


PROFILES = ("flat", "steep", "slumped", "wide", "gouged", "raised")


def crest_height(name):
    return max(z for _, z in profile(name))


def toes(name):
    p = profile(name)
    return p[0][0], p[1][0]


def face_x(name, z, side):
    """x of the water-side (side=-1) or yard-side (+1) face of a profile at height z."""
    p = profile(name)
    chain = [p[0], p[7], p[6], p[5]] if side < 0 else [p[1], p[2], p[3], p[4]]
    for (x0, z0), (x1, z1) in zip(chain, chain[1:]):
        if z0 <= z <= z1 and z1 > z0:
            return x0 + (x1 - x0) * (z - z0) / (z1 - z0)
    return chain[-1][0]


def level(name, shape):
    """Absolute water level (m) for a named level with the barrier currently in `shape`."""
    return {"low": -0.45, "normal": -0.1, "high": 0.8 * H0, "flood": 0.94 * H0,
            "overtop": crest_height(shape) + 0.22}[name]


# Components Max adds (outlines in x-z on the cut face, or positions).
def core_outline():
    return [(-0.55, 0.0), (0.55, 0.0), (0.22, 1.42), (-0.22, 1.42)]


def berm_outline():
    xl = toes("wide")[1]
    return [(xl - 0.6, 0.0), (xl + 2.1, 0.0), (xl + 1.9, 0.12), (xl - 0.1, 0.45), (xl - 0.6, 0.45)]


def berm_top(x):
    xl = toes("wide")[1]
    if x < xl - 0.1 or x > xl + 2.1:
        return 0.0
    return 0.45 if x < xl - 0.1 else max(0.0, 0.45 - (x - (xl - 0.1)) * 0.33 / 2.0)


WELLS_X = (toes("wide")[1] + 2.35, toes("wide")[1] + 2.85)
BOIL_X = toes("wide")[1] + 1.45
TUNNEL_Z = 0.75
NESTBOX = (3.9, 2.2)                        # on the berm, beside the burrow it replaces
TRAMPOLINE = (5.35, 3.3, 0.9)               # x, y, radius: deep in the yard, clear of the berm (x < 4.4)
HOUSE = (10.8, 6.5)
KIDS_SPOTS = ((5.05, 3.3), (5.65, 3.25))       # on the trampoline
KIDS_SETUP = ((-1.15, 1.0), (-0.6, 1.25))    # beside Max on the riverbank on promise day
SAND_PILE = (0.35, 1.5)


def tunnel_ends(shape="raised"):
    return face_x(shape, TUNNEL_Z, -1), face_x(shape, TUNNEL_Z, 1)


def max_spot(event, shape):
    """Where Max stands during an event's mechanism part (x, y, z)."""
    xl = toes(shape)[1]
    if event == "calm":
        return (-1.9, STAND_Y, 0.0)                         # on the bank, the river right behind him
    if event in ("burrow_piping", "burrow_sealed", "seep_blocked"):   # on the crest, above what happens below
        return (0.1, 0.55, crest_height(shape))
    if event in ("underseep_boil", "underseep_relieved"):
        x = BOIL_X - 1.0 if event == "underseep_boil" else toes("wide")[1] + 1.2
        return (x, STAND_Y + 0.4, berm_top(x) if event == "underseep_relieved" else 0.0)
    if event == "storm_holds":
        return (TRAMPOLINE[0] - 1.7, STAND_Y, 0.0)
    x = xl + 0.6
    return (x, STAND_Y, berm_top(x) if shape in ("wide", "gouged", "raised") and event != "seep_slump" else 0.0)


def focus(event, shape):
    """The region a mechanism shot must contain: (x0, x1, z0, z1) at the cut face. At most ~5 m wide, so
    Max stays readable in a vertical frame."""
    xw, xl = toes(shape)
    H = crest_height(shape)
    mx = max_spot(event, shape)[0]
    if event == "calm":
        return (BANK - 1.0, SAND_PILE[0] + 0.5, -0.6, 2.1)
    if event in ("seep_slump", "seep_blocked"):              # river face to the (dry or soaked) yard side
        return (face_x(shape, H * 0.45, -1) - 0.35, max(mx, xl) + 0.5, -0.3, max(H, max_spot(event, shape)[2])
                + 0.75)
    if event in ("underseep_boil", "underseep_relieved"):
        return (xl - 1.6, WELLS_X[1] + 0.5 if event == "underseep_relieved" else BOIL_X + 0.8,
                SAND_BOTTOM + 0.1, 2.0)
    if event in ("overtop_scour", "freeboard_holds"):
        return (xw * 0.55 - 0.6, mx + 0.5, -0.2, H + 0.85)
    if event == "burrow_piping":                             # the tunnel from the river to the jet's landing
        return (tunnel_ends(shape)[0] - 0.4, jet_arc(shape)[-1][0] + 0.4, -0.3, H + 2.05)
    if event == "burrow_sealed":                             # the packed exit and the squirrel's new box
        return (-0.9, NESTBOX[0] + 0.7, -0.3, H + 2.05)
    if event == "storm_holds":
        return (0.0, TRAMPOLINE[0] + 1.0, -0.3, H + 0.8)
    raise KeyError(event)


def result_focus(event, shape):
    """The closer RESULT shot that ends every beat: Max reacting beside the part of the event that reaches
    him, so he is big while the mechanism is still on screen at 7/8 (x0, x1, z0, z1)."""
    xw, xl = toes(shape)
    H = crest_height(shape)
    mx, _my, mz = max_spot(event, shape)
    top = max(H, mz) + 2.05
    if event == "calm":
        return (BANK - 0.4, KIDS_SETUP[1][0] + 0.5, -0.3, 2.1)       # the river stays in view
    if event == "seep_slump":
        return (-0.1, mx + 0.55, -0.3, top - 0.1)
    if event == "seep_blocked":                              # the arrows stopping at the core, Max above
        return (face_x(shape, H * 0.22, -1) - 0.5, 0.9, -0.3, top)
    if event == "underseep_boil":
        return (mx - 0.7, BOIL_X + 0.75, TOPSOIL - 0.1, top)
    if event == "underseep_relieved":
        return (mx - 0.7, WELLS_X[1] + 0.5, SAND_MID - 0.1, top)
    if event == "overtop_scour":
        return (0.2, mx + 0.55, -0.3, top)
    if event == "freeboard_holds":
        return (face_x(shape, level("flood", shape), -1) - 0.6, mx + 0.5, -0.2, top)
    if event == "burrow_piping":
        return (-0.6, jet_arc(shape)[-1][0] + 0.4, -0.2, top)
    if event == "burrow_sealed":
        return (-0.6, NESTBOX[0] + 0.5, -0.2, top)
    if event == "storm_holds":
        return (1.4, TRAMPOLINE[0] + 1.0, -0.3, H + 1.0)
    raise KeyError(event)


def underseep_path():
    return [(BANK - 0.5, SAND_MID), (BOIL_X, SAND_MID), (BOIL_X, TOPSOIL + 0.1), (BOIL_X, 0.05)]


def seep_paths(shape, stop_at_core=False):
    H = crest_height(shape)
    paths = []
    for frac in (0.22, 0.45, 0.66):
        z = H * frac
        x0 = face_x(shape, z, -1) - 0.35
        x1 = -0.6 if stop_at_core else face_x(shape, z, 1) + 0.25
        paths.append([(x0, z), (x1, z)])
    return paths


def jet_arc(shape="raised", land=None):
    """Points of the burrow's water jet: out of the yard face, arcing down to the lawn."""
    x0 = tunnel_ends(shape)[1]
    x1 = land or x0 + 1.6
    return [(x0 + (x1 - x0) * t, TUNNEL_Z + 0.55 * 4 * t * (1 - t) - TUNNEL_Z * t * t) for t in
            (0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.0)]


def sheet_path(shape="wide"):
    """The overtopping sheet: across the crest and down the yard-side slope (x, z on the surface)."""
    p = profile(shape)
    return [p[5], p[4], p[3], p[2], p[1]]
