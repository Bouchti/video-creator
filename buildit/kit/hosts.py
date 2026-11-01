"""
The host machine (pure Python, shared by the checker and the Blender builder): the real product the film is about
(a fridge, a washing machine, a water heater...), seen through clear walls, with named MOUNT SLOTS where the
story's parts attach. The planner says which part goes in which slot; code decides where that is, how big the
part may be, and which way it faces, so the machine is always one compact, connected object.

Props (the hook object, analogies) stand on STAGE spots in front of / beside the machine.

World: X right, Y away from the camera, Z up, floor z = 0; the machine stands at the origin, its front at -Y.
A placement is a dict {x, y, z, w, d, h, k, rot}: base-centre position, the box it fills, the uniform scale `k`
applied to the part, and its turn about Z in degrees (0 = faces the camera).
"""
from __future__ import annotations

import math

from .vocab import DIMS, SIZES

# slot: (centre x, y, z as fractions of the host's W, D, H; or "out" offsets), max box (fractions), facing deg
# facing: 0 = front (-Y), 180 = back (+Y), 90 = right (+X), -90 = left (-X)
_CAB = {
    "inside_top": ((0, 0, 0.80), (0.78, 0.70, 0.24), 0),
    "inside_middle": ((0, 0, 0.52), (0.78, 0.70, 0.24), 0),
    "inside_bottom": ((0, 0, 0.30), (0.78, 0.70, 0.20), 0),
    "back_top": ((0, "back", 0.80), (0.86, 0.32, 0.26), 180),
    "back_middle": ((0, "back", 0.50), (0.90, 0.30, 0.34), 180),
    "back_bottom": ((0, "back", 0.15), (0.80, 0.55, 0.26), 180),
    "top": ((0, 0, "top"), (0.80, 0.80, 0.30), 0),
    "front": ((0, "front", 0.62), (0.40, 0.14, 0.18), 0),
    "side_left": (("left", 0, 0.45), (0.40, 0.80, 0.40), -90),
    "side_right": (("right", 0, 0.45), (0.40, 0.80, 0.40), 90),
}
_TANK = {
    "inside_top": ((0, 0, 0.78), (0.70, 0.70, 0.22), 0),
    "inside_middle": ((0, 0, 0.50), (0.70, 0.70, 0.26), 0),
    "inside_bottom": ((0, 0, 0.18), (0.70, 0.70, 0.22), 0),
    "top": ((0, 0, "top"), (0.80, 0.80, 0.30), 0),
    "front": ((0, "front", 0.45), (0.50, 0.16, 0.22), 0),
    "side_left": (("left", 0, 0.30), (0.60, 0.80, 0.40), -90),
    "side_right": (("right", 0, 0.30), (0.60, 0.80, 0.40), 90),
    "back_bottom": ((0, "back", 0.12), (0.80, 0.55, 0.24), 180),
}
_FRAME = {     # an open machine frame: two decks inside, plus every outside face
    "inside_top": ((0, 0, 0.72), (0.84, 0.76, 0.40), 0),
    "inside_bottom": ((0, 0, 0.26), (0.84, 0.76, 0.40), 0),
    "top": ((0, 0, "top"), (0.84, 0.84, 0.40), 0),
    "front": ((0, "front", 0.50), (0.60, 0.20, 0.30), 0),
    "back_top": ((0, "back", 0.72), (0.90, 0.32, 0.36), 180),
    "back_bottom": ((0, "back", 0.22), (0.90, 0.40, 0.36), 180),
    "side_left": (("left", 0, 0.45), (0.50, 0.80, 0.50), -90),
    "side_right": (("right", 0, 0.45), (0.50, 0.80, 0.50), 90),
}
SHAPE_SLOTS = {"cabinet": _CAB, "tank": _TANK, "frame": _FRAME}

# host type: (shape, (W, D, H) metres, dressing, what it is, accent colour)
HOSTS = {
    "fridge": ("cabinet", (0.76, 0.68, 1.70), "fridge",
               "a kitchen fridge: white cabinet with clear walls, glass shelves, a milk bottle and food inside",
               "#36b4ff"),
    "freezer": ("cabinet", (0.76, 0.68, 1.30), "fridge", "a chest-height freezer cabinet with clear walls",
                "#36b4ff"),
    "washing_machine": ("cabinet", (0.62, 0.62, 0.86), "washer",
                        "a front-loading washing machine: round door window, drum inside", "#36b4ff"),
    "dishwasher": ("cabinet", (0.62, 0.62, 0.86), "box", "a dishwasher cabinet with racks", "#36b4ff"),
    "oven": ("cabinet", (0.62, 0.62, 0.90), "oven", "a kitchen oven with a window door", "#ff7a2e"),
    "air_conditioner": ("cabinet", (0.90, 0.40, 0.72), "ac", "an outdoor air-conditioner / heat-pump unit "
                        "with a big fan grille", "#36b4ff"),
    "water_heater": ("tank", (0.56, 0.56, 1.40), "heater", "a tall water-heater tank with clear walls",
                     "#ff7a2e"),
    "boiler": ("tank", (0.56, 0.56, 1.00), "heater", "a home boiler drum with clear walls", "#ff7a2e"),
    "pressure_cooker": ("tank", (0.50, 0.50, 0.42), "pot", "a pressure-cooker pot with a locked lid",
                        "#ff7a2e"),
    "machine": ("frame", (1.00, 0.70, 1.10), "frame", "a generic open machine frame with two decks "
                "(engines, pumps, generators, anything without a cabinet)", "#ffb21e"),
}

STAGE = {   # spots for props, as offsets from the machine (metres; front = -Y)
    "front": (0.0, -1.0, 0.0),
    "left": (-1.0, -1.0, 0.0),
    "right": (1.0, -1.0, 0.0),
}
FIT_MAX = 1.6           # a part may grow to fill its slot, up to this many times its kit size
FIT_MIN = 0.35


def host(sb: dict) -> tuple[str, tuple, str, str, str, dict]:
    """(type, dims, dressing, about, accent, slots) of the storyboard's machine."""
    m = sb.get("machine") or {}
    t = m.get("host") if m.get("host") in HOSTS else "machine"
    shape, dims, dressing, about, accent = HOSTS[t]
    return t, dims, dressing, about, accent, SHAPE_SLOTS[shape]


def slot_names(host_type: str) -> list[str]:
    return list(SHAPE_SLOTS[HOSTS[host_type][0]])


def _turned(w, d, rot):
    return (d, w) if abs(rot) % 180 == 90 else (w, d)


def slot_box(sb: dict, slot: str) -> tuple[tuple, tuple, float]:
    """(centre (x, y, z), max (w, d, h), facing) of a slot in world metres."""
    _t, (W, D, H), _dr, _ab, _ac, slots = host(sb)
    (fx, fy, fz), (mw, md, mh), rot = slots[slot]
    w, d, h = mw * W, md * D, mh * H
    if slot == "top":
        h = mh * min(H, 1.2)
    x = {"left": -W / 2 - w / 2 - 0.03, "right": W / 2 + w / 2 + 0.03}.get(fx, fx * W) \
        if isinstance(fx, str) else fx * W
    y = {"back": D / 2 + d / 2 + 0.03, "front": -D / 2 - d / 2 - 0.01}.get(fy, 0.0) if isinstance(fy, str) else fy * D
    z = H + h / 2 + 0.005 if fz == "top" else fz * H
    return (x, y, z), (w, d, h), rot           # (w, d) are world X / Y extents


def place_part(sb: dict, part: dict) -> dict:
    """Where a part stands: a mounted part fits its slot; a prop stands on its stage spot at kit size."""
    k0 = SIZES.get(part.get("size") or "medium", 1.0)
    w0, d0, h0 = (v * k0 for v in DIMS[part["type"]])
    slot = part.get("mount")
    if slot in host(sb)[5]:
        (cx, cy, cz), (mw, md, mh), rot = slot_box(sb, slot)
        pw, pd = _turned(w0, d0, rot)
        k = min(mw / pw, md / pd, mh / h0)
        k = max(FIT_MIN, min(FIT_MAX, k))
        w, d = _turned(w0 * k, d0 * k, rot)
        h = h0 * k
        z = cz - h / 2
        if slot == "top":
            z = host(sb)[1][2] + 0.005
        return {"x": cx, "y": cy, "z": max(0.0, z), "w": w, "d": d, "h": h, "k": k0 * k, "rot": rot,
                "slot": slot}
    # props stand on the side of the machine the home camera looks from, facing it: a prop and the slot its
    # part flies into are seen together, and nothing stands behind the machine
    W, D, _H = host(sb)[1]
    a = math.radians(home_azimuth(sb))
    cx_, cy_ = math.sin(a), -math.cos(a)                 # from the machine toward the home camera
    px_, py_ = math.cos(a), math.sin(a)                  # screen right in the home view
    r = 0.5 * math.hypot(W, D)
    stage = part.get("stage") or "front"
    if stage == "front":
        out, side = r + 0.3 + max(w0, d0) / 2, 0.0
    else:
        out, side = r * 0.5, (r + 0.5 + max(w0, d0) / 2) * (-1 if stage == "left" else 1)
    x, y = cx_ * out + px_ * side, cy_ * out + py_ * side
    rot = home_azimuth(sb)
    w, d = (abs(w0 * math.cos(a)) + abs(d0 * math.sin(a)), abs(w0 * math.sin(a)) + abs(d0 * math.cos(a)))
    return {"x": x, "y": y, "z": 0.0, "w": w, "d": d, "h": h0, "k": k0, "rot": rot, "slot": None, "stage": stage}


SLOT_VIEW = {"inside": -30.0, "back": -150.0, "front": -20.0, "side_left": -90.0, "side_right": 90.0}


def slot_view(sb: dict, slot: str) -> float:
    """The camera azimuth (degrees) for a close look at a part in `slot`, as an illustrator would draw it:
    inside parts through the open front-left, back parts from behind, side parts square on, top parts from
    the home view."""
    if slot in SLOT_VIEW:
        return SLOT_VIEW[slot]
    return SLOT_VIEW.get(str(slot).split("_")[0], home_azimuth(sb))


def home_azimuth(sb: dict) -> float:
    """The machine's home view (degrees; 0 = from the front, -90 = from the left): the one angle that shows every
    mounted part at once. Cabinets are cut away on the left, so a part on the back AND parts inside are both seen
    from the back-left; with nothing on the back, from the front-left. Every machine shot uses it, so the viewer
    always knows where things are."""
    slots = {p.get("mount") for p in sb.get("parts", []) if p.get("mount")}
    back = any(str(s).startswith("back") for s in slots)
    return -135.0 if back else -35.0


def machine_box(sb: dict) -> tuple:
    W, D, H = host(sb)[1]
    return (0.0, 0.0, 0.0, W, D, H)


def solve(sb: dict) -> dict[str, dict]:
    """{part id: placement} for every part of the storyboard."""
    from .vocab import PARTS
    return {p["id"]: place_part(sb, p) for p in sb.get("parts", []) if p.get("type") in PARTS}


def describe() -> str:
    lines = []
    for t, (shape, dims, _dr, about, _ac) in HOSTS.items():
        lines.append(f"- {t}: {about} ({dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f} m); slots: "
                     + ", ".join(SHAPE_SLOTS[shape]))
    return ("HOST MACHINES (the product the film is about; every machine part MOUNTS in one of its slots):\n"
            + "\n".join(lines) +
            "\nSlot meanings: inside_* = inside the clear body (seen through the walls); back_* = fixed on the "
            "outside of the back panel; top = on the roof; front = on the front panel (knobs, displays); "
            "side_left / side_right = on a side panel.\nPROP STAGE spots (hook and analogy objects, standing on "
            "the floor, on the camera's side of the machine): front, left, right.")
