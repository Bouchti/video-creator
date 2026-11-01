"""
The machine kit's builders (runs inside Blender): one function per part type of buildit/kit/vocab.py.

    part = build({"id": "tank", "type": "glass_tank", "size": "medium", "color": None})
    part.root                     # empty at the base centre; move it to place the part
    part.anchors["top"]           # empties for labels, camera focus, effects
    part.ports["inlet"]           # (empty, outward direction) for pipes and flows
    part.drive("spin", radians)   # drivers: spin, crank, pump, stroke, inflate, squeeze, tilt, turn, needle, press
    part.interior                 # where a fill lives: {"kind": "cyl"|"box", "r"|"half", "z0", "z1"}
    part.meshes                   # every mesh (heat / frost / visibility)

Every part is chunky and bevelled, sized to vocab.DIMS times the size preset, base on z = 0, facing -Y (the
camera side). Wheels, gears and fans turn in the XZ plane (axle along Y) so their motion reads on screen.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from cutaway.blender import geo

from . import materials as M
from .parts import _arc, ring, rounded_profile, solid, tube

PAINT = {"red": "#9e0b14", "orange": "#d4520e", "yellow": "#e3ac10", "green": "#2a8a3a", "blue": "#1f5bbf",
         "white": "#e7e4df", "black": "#1b1b1d"}
SIZES = {"small": 0.7, "medium": 1.0, "large": 1.35}


def finish(color: str | None, default: str = "red"):
    """The material a colour name means: paint, or a metal for steel / copper / brass."""
    c = color or default
    if c == "steel":
        return M.brushed()
    if c == "copper":
        return M.copper()
    if c == "brass":
        return M.brass()
    return M.paint(PAINT.get(c, PAINT["red"]))


class Part:
    def __init__(self, pid: str, ptype: str):
        self.id, self.type = pid, ptype
        self.root = bpy.data.objects.new(pid, None)
        bpy.context.scene.collection.objects.link(self.root)
        self.anchors: dict = {}
        self.ports: dict = {}
        self.drivers: dict = {}
        self.interior: dict | None = None
        self.meshes: list = []

    def add(self, obj, parent=None):
        obj.parent = parent or self.root
        for o in (obj, *obj.children_recursive):
            if o.type == "MESH" and o not in self.meshes:
                self.meshes.append(o)
                o["heat"] = 0.0
                o["frost"] = 0.0
        return obj

    def group(self, name, parent=None, loc=(0, 0, 0)):
        e = bpy.data.objects.new(f"{self.id}_{name}", None)
        bpy.context.scene.collection.objects.link(e)
        e.parent = parent or self.root
        e.location = loc
        return e

    def anchor(self, name, loc, parent=None):
        e = self.group(f"a_{name}", parent, loc)
        e.empty_display_size = 0.02
        self.anchors[name] = e
        return e

    def port(self, name, loc, direction, parent=None):
        e = self.group(f"p_{name}", parent, loc)
        self.ports[name] = (e, Vector(direction).normalized())
        if name not in self.anchors:
            self.anchors[name] = e
        return e

    def drive(self, name, value):
        fn = self.drivers.get(name)
        if fn:
            fn(value)


def _y_axis(obj):
    """Lay a part built around Z onto the Y axis (an axle pointing at the camera)."""
    geo.transform_mesh(obj, Matrix.Rotation(math.radians(90), 4, "X"))
    return obj


def _x_axis(obj):
    geo.transform_mesh(obj, Matrix.Rotation(math.radians(90), 4, "Y"))
    return obj


def _sphere(name, r, mat, segs=48):
    prof = [(r * math.sin(math.radians(a)), -r * math.cos(math.radians(a))) for a in range(0, 181, 10)]
    o = geo.lathe(name, prof, segs, mat=mat)
    return o


def _gear_mesh(name, r, teeth, width, mat, hole=0.0):
    """A spur gear: chunky trapezoid teeth (tooth 40 % of the pitch at the tip, 55 % at the root), extruded along
    Y, small bevel, flat-shaded flanks so the teeth read crisply."""
    pts = []
    root, pitch = r * 0.84, math.tau / teeth
    for i in range(teeth):
        a = i * pitch
        for frac, rr in ((-0.275, root), (-0.2, r), (0.2, r), (0.275, root)):
            pts.append((rr * math.cos(a + frac * pitch), rr * math.sin(a + frac * pitch)))
        for frac in (0.35, 0.5, 0.65):
            pts.append((root * math.cos(a + frac * pitch), root * math.sin(a + frac * pitch)))
    o = geo.prism(name, pts, -width / 2, width / 2, mat=mat)
    if hole:
        geo.boolean(o, geo.cylinder("gh", hole, -width, width, 32))
    geo.bevel(o, min(0.004, width * 0.08), 2, angle=30)
    return _y_axis(o)


# ------------------------------------------------------------ everyday objects

def b_can(p, k, color):
    r, h = 0.08 * k, 0.22 * k
    p.add(solid(f"{p.id}_body", r, h, 0.012 * k, M.brushed("#cfd1d3")))
    p.add(tube(f"{p.id}_label", r + 0.0015 * k, h * 0.72, 0.003 * k, finish(color, "orange"), z0=h * 0.14))
    p.add(tube(f"{p.id}_band", r + 0.0025 * k, h * 0.2, 0.003 * k, M.paint(PAINT["white"]), z0=h * 0.4))
    for z in (0.012 * k, h - 0.012 * k):
        p.add(ring(f"{p.id}_rim", r - 0.002 * k, 0.012 * k, mat=M.brushed("#dcdee0"), z=z))
    p.anchor("top", (0, 0, h)); p.anchor("center", (0, 0, h / 2)); p.anchor("bottom", (0, 0, 0))
    p.interior = {"kind": "cyl", "r": r * 0.85, "z0": 0.02 * k, "z1": h - 0.02 * k}


def b_spray_can(p, k, color):
    r, h = 0.06 * k, 0.30 * k
    prof = rounded_profile(r, h, 0.012 * k)[:-1] + _arc(0, h, r, 0, 90, 8)[1:] + [(0.0, h + r * 0.55)]
    prof = [(min(x, r), z) for x, z in prof]
    p.add(geo.lathe(f"{p.id}_body", [pt for pt in rounded_profile(r, h, 0.012 * k)], 48, mat=finish(color, "blue")))
    p.add(solid(f"{p.id}_dome", r * 0.92, 0.035 * k, 0.015 * k, M.brushed(), z0=h - 0.004 * k))
    p.add(solid(f"{p.id}_cap", 0.018 * k, 0.03 * k, 0.006 * k, M.plastic("#f2f0ec"), z0=h + 0.028 * k))
    p.anchor("center", (0, 0, h / 2))
    p.port("nozzle", (0, -0.02 * k, h + 0.048 * k), (0, -1, 0.25))
    p.interior = {"kind": "cyl", "r": r * 0.8, "z0": 0.02 * k, "z1": h - 0.02 * k}


def b_bottle(p, k, color):
    prof = [(0, 0), (0.06 * k, 0), (0.07 * k, 0.012 * k), (0.07 * k, 0.26 * k), (0.06 * k, 0.31 * k),
            (0.024 * k, 0.36 * k), (0.022 * k, 0.385 * k), (0, 0.385 * k)]
    milk = color == "white"                     # a milk bottle: opaque white body, blue cap
    p.add(geo.lathe(f"{p.id}_body", prof, 48, mat=M.plastic("#fbfbf8", 0.3) if milk else M.glass("#dff1ff")))
    p.add(solid(f"{p.id}_cap", 0.026 * k, 0.035 * k, 0.008 * k, finish(None if milk else color, "blue"),
                z0=0.383 * k))
    p.port("cap", (0, 0, 0.42 * k), (0, 0, 1))
    p.anchor("center", (0, 0, 0.18 * k))
    p.interior = {"kind": "cyl", "r": 0.055 * k, "z0": 0.015 * k, "z1": 0.3 * k}


def b_cup(p, k, color):
    prof = [(0, 0.012 * k), (0.07 * k, 0.0), (0.08 * k, 0.012 * k), (0.085 * k, 0.17 * k), (0.087 * k, 0.18 * k),
            (0.075 * k, 0.18 * k), (0.072 * k, 0.03 * k), (0, 0.03 * k)]
    p.add(geo.lathe(f"{p.id}_mug", prof, 48, mat=finish(color, "white")))
    drink = solid(f"{p.id}_drink", 0.072 * k, 0.01 * k, 0.003 * k, M.paint("#3b2414", 0.08), z0=0.14 * k)
    p.add(drink)
    h = geo.sweep(f"{p.id}_handle", [(0.08 * k, 0, 0.14 * k), (0.13 * k, 0, 0.13 * k), (0.135 * k, 0, 0.06 * k),
                                     (0.08 * k, 0, 0.05 * k)], 0.012 * k, mat=finish(color, "white"))
    p.add(h)
    p.port("top", (0, 0, 0.18 * k), (0, 0, 1))
    p.anchor("center", (0, 0, 0.09 * k))


def b_balloon(p, k, color):
    body = p.group("body", loc=(0, 0, 0.06 * k))
    prof = [(0, 0)] + [(0.2 * k * math.sin(math.radians(a)) * (1 - 0.18 * math.cos(math.radians(a))),
                        0.25 * k - 0.25 * k * math.cos(math.radians(a))) for a in range(10, 181, 10)]
    prof[-1] = (0, prof[-1][1])
    b = geo.lathe(f"{p.id}_rubber", prof, 48, mat=M.paint(PAINT.get(color or "red", PAINT["red"]), 0.12))
    p.add(b, body)
    p.add(solid(f"{p.id}_knot", 0.018 * k, 0.06 * k, 0.008 * k, M.paint(PAINT.get(color or "red", PAINT["red"]), 0.2)))
    p.anchor("center", (0, 0, 0.3 * k)); p.port("neck", (0, 0, 0.0), (0, 0, -1))

    def inflate(v):
        s = 0.3 + 0.7 * max(0.0, min(1.0, v))
        body.scale = (s, s, s)
    p.drivers["inflate"] = inflate
    p.interior = {"kind": "cyl", "r": 0.13 * k, "z0": 0.12 * k, "z1": 0.48 * k}


def b_candle(p, k, color):
    p.add(solid(f"{p.id}_wax", 0.045 * k, 0.22 * k, 0.01 * k, M.plastic("#f4ead6", 0.55)))
    p.add(geo.cylinder(f"{p.id}_wick", 0.003 * k, 0.21 * k, 0.24 * k, 8, mat=M.rubber()))
    fl = _sphere(f"{p.id}_flame", 0.016 * k, M.glow("#ffb347", 18.0))
    fl.scale = (1, 1, 2.0)
    fl.location = (0, 0, 0.265 * k)
    fl["glow"] = 1.0
    p.add(fl)
    ld = bpy.data.lights.new(f"{p.id}_light", "POINT")
    ld.energy, ld.color, ld.shadow_soft_size = 4.0 * k * k, (1.0, 0.7, 0.4), 0.02
    lo = bpy.data.objects.new(f"{p.id}_light", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.parent, lo.location = p.root, (0, 0, 0.27 * k)
    p.anchor("flame", (0, 0, 0.27 * k)); p.anchor("center", (0, 0, 0.12 * k))


def b_ice_cube(p, k, color):
    o = geo.box(f"{p.id}_ice", (0.14 * k,) * 3, (0, 0, 0.07 * k), mat=M.glass("#d8f0ff"), fillet=0.02 * k, segments=4)
    o["frost"] = 0.25
    p.add(o)
    o["frost"] = 0.25
    p.anchor("center", (0, 0, 0.07 * k))


def b_ball(p, k, color):
    b = _sphere(f"{p.id}_ball", 0.1 * k, finish(color, "red"))
    b.location.z = 0.1 * k
    p.add(b)
    p.anchor("center", (0, 0, 0.1 * k))


def b_firecracker(p, k, color):
    body = _x_axis(solid(f"{p.id}_tube", 0.032 * k, 0.2 * k, 0.008 * k, finish(color, "red"), z0=-0.1 * k))
    body.location.z = 0.034 * k
    p.add(body)
    for x in (-0.07, 0.07):
        b = _x_axis(tube(f"{p.id}_band", 0.0335 * k, 0.018 * k, 0.003 * k, M.brass(), z0=-0.009 * k))
        b.location = (x * k, 0, 0.034 * k)
        p.add(b)
    p.add(geo.sweep(f"{p.id}_fuse", [(0.1 * k, 0, 0.034 * k), (0.13 * k, 0, 0.045 * k), (0.15 * k, 0.0, 0.07 * k)],
                    0.003 * k, mat=M.paint("#3c8a2e")))
    p.anchor("fuse", (0.15 * k, 0, 0.07 * k)); p.anchor("center", (0, 0, 0.034 * k))


def b_matchbox(p, k, color):
    p.add(geo.box(f"{p.id}_box", (0.18 * k, 0.12 * k, 0.05 * k), (0, 0, 0.025 * k), mat=finish(color, "yellow"),
                  fillet=0.006 * k))
    st = geo.box(f"{p.id}_match", (0.11 * k, 0.007 * k, 0.007 * k), (0.0, -0.02 * k, 0.054 * k), mat=M.plastic("#d9b07a"))
    p.add(st)
    p.add(_sphere(f"{p.id}_head", 0.008 * k, M.paint("#7a1a12", 0.5))).location = (0.06 * k, -0.02 * k, 0.054 * k)
    fl = _sphere(f"{p.id}_flame", 0.012 * k, M.glow("#ffb347", 18.0))
    fl.scale = (1, 1, 1.8)
    fl.location = (0.07 * k, -0.02 * k, 0.075 * k)
    fl["glow"] = 1.0
    p.add(fl)
    p.anchor("flame", (0.07 * k, -0.02 * k, 0.08 * k)); p.anchor("center", (0, 0, 0.03 * k))


def b_kettle(p, k, color):
    prof = [(0, 0), (0.15 * k, 0), (0.17 * k, 0.03 * k), (0.17 * k, 0.15 * k), (0.12 * k, 0.24 * k),
            (0.05 * k, 0.27 * k), (0, 0.27 * k)]
    p.add(geo.lathe(f"{p.id}_body", prof, 56, mat=M.chrome()))
    p.add(solid(f"{p.id}_knob", 0.025 * k, 0.04 * k, 0.01 * k, M.plastic("#1b1b1d"), z0=0.265 * k))
    p.add(geo.sweep(f"{p.id}_spout", [(-0.14 * k, 0, 0.08 * k), (-0.2 * k, 0, 0.16 * k), (-0.23 * k, 0, 0.22 * k)],
                    0.022 * k, mat=M.chrome()))
    p.add(geo.sweep(f"{p.id}_handle", [(-0.06 * k, 0, 0.26 * k), (0, 0, 0.35 * k), (0.07 * k, 0, 0.26 * k)],
                    0.014 * k, mat=finish(color, "black")))
    p.port("spout", (-0.235 * k, 0, 0.225 * k), (-0.5, 0, 1))
    p.anchor("center", (0, 0, 0.13 * k))


def b_fan_desk(p, k, color):
    p.add(solid(f"{p.id}_base", 0.12 * k, 0.04 * k, 0.015 * k, finish(color, "white")))
    p.add(geo.cylinder(f"{p.id}_stand", 0.018 * k, 0.03 * k, 0.32 * k, 24, mat=M.chrome()))
    head = p.group("head", loc=(0, 0, 0.36 * k))
    p.add(_y_axis(solid(f"{p.id}_motor", 0.06 * k, 0.12 * k, 0.02 * k, finish(color, "white"), z0=-0.02 * k)), head)
    for r in (0.17, 0.12):
        p.add(_y_axis(ring(f"{p.id}_cage", r * k, 0.008 * k, mat=M.chrome(), z=0.0)), head).location.y = -0.05 * k
    rotor = p.group("rotor", head, (0, -0.06 * k, 0))
    p.add(_y_axis(solid(f"{p.id}_hub", 0.035 * k, 0.03 * k, 0.012 * k, M.chrome(), z0=-0.015 * k)), rotor)
    for i in range(3):
        bl = geo.box(f"{p.id}_blade", (0.07 * k, 0.012 * k, 0.15 * k), (0, 0, 0.085 * k), mat=M.plastic("#cfe9ff", 0.2),
                     fillet=0.01 * k)
        bl.rotation_euler = (0, math.radians(120 * i), 0)
        p.add(bl, rotor)
    p.drivers["spin"] = lambda a: setattr(rotor, "rotation_euler", (0, a, 0))
    p.anchor("center", (0, 0, 0.36 * k)); p.port("front", (0, -0.12 * k, 0.36 * k), (0, -1, 0))


def b_bicycle_wheel(p, k, color):
    hub_z = 0.42 * k
    wheel = p.group("wheel", loc=(0, 0, hub_z))
    p.add(_y_axis(ring(f"{p.id}_tyre", 0.36 * k, 0.05 * k, mat=M.rubber(), z=0.0)), wheel)
    p.add(_y_axis(ring(f"{p.id}_rim", 0.33 * k, 0.018 * k, mat=M.chrome(), z=0.0)), wheel)
    p.add(_y_axis(solid(f"{p.id}_hub", 0.03 * k, 0.07 * k, 0.01 * k, M.brushed(), z0=-0.035 * k)), wheel)
    for i in range(16):
        a = math.tau * i / 16
        sp = geo.sweep(f"{p.id}_spoke", [(0, 0, 0), (0.33 * k * math.cos(a), 0, 0.33 * k * math.sin(a))], 0.0025 * k,
                       mat=M.chrome(), segments=8)
        p.add(sp, wheel)
    arm = p.group("crank", wheel)
    p.add(geo.box(f"{p.id}_arm", (0.17 * k, 0.02 * k, 0.03 * k), (0.085 * k, -0.06 * k, 0), mat=M.graphite(),
                  fillet=0.008 * k), arm)
    p.add(geo.box(f"{p.id}_pedal", (0.05 * k, 0.09 * k, 0.025 * k), (0.17 * k, -0.11 * k, 0), mat=M.rubber(),
                  fillet=0.006 * k), arm)
    p.drivers["spin"] = lambda a: setattr(wheel, "rotation_euler", (0, a, 0))
    p.anchor("hub", (0, -0.05 * k, hub_z)); p.anchor("rim", (0, 0, hub_z + 0.37 * k))
    p.anchor("pedal", (0.17 * k, -0.11 * k, 0), arm)


def b_hand(p, k, color):
    hand = p.group("hand")
    mat = M.plastic("#f3f1ee", 0.5)
    p.add(geo.box(f"{p.id}_palm", (0.15 * k, 0.07 * k, 0.15 * k), (0, 0, 0.22 * k), mat=mat, fillet=0.03 * k), hand)
    for i, x in enumerate((-0.05, -0.017, 0.017, 0.05)):
        f = solid(f"{p.id}_finger", 0.017 * k, 0.11 * k, 0.016 * k, mat, z0=0.06 * k + 0.01 * k * (i % 2))
        f.location.x = x * k
        p.add(f, hand)
    th = solid(f"{p.id}_thumb", 0.02 * k, 0.09 * k, 0.018 * k, mat, z0=0.0)
    th.location = (0.085 * k, 0, 0.17 * k)
    th.rotation_euler.y = math.radians(-50)
    p.add(th, hand)
    p.add(solid(f"{p.id}_cuff", 0.065 * k, 0.07 * k, 0.02 * k, M.paint(PAINT["blue"]), z0=0.29 * k), hand)
    p.drivers["press"] = lambda v: setattr(hand, "location", (0, 0, -0.06 * k * v))
    p.anchor("finger", (-0.017 * k, 0, 0.06 * k), hand)


# ------------------------------------------------------------ housings

def b_glass_tube(p, k, color):
    r, h = 0.155 * k, 0.72 * k
    p.add(tube(f"{p.id}_glass", r, h, 0.007 * k, M.glass(), z0=0.02 * k))
    for z in (0.03 * k, h + 0.01 * k):
        p.add(ring(f"{p.id}_rim", r + 0.004 * k, 0.022 * k, z=z))
    p.anchor("top", (0, 0, h + 0.02 * k)); p.anchor("center", (0, 0, h / 2)); p.anchor("bottom", (0, 0, 0.02 * k))
    p.anchor("inside", (0, 0, h * 0.5))
    p.port("top", (0, 0, h + 0.03 * k), (0, 0, 1)); p.port("bottom", (0, 0, 0.0), (0, 0, -1))
    p.interior = {"kind": "cyl", "r": r * 0.9, "z0": 0.04 * k, "z1": h}


def b_glass_tank(p, k, color):
    from .parts import glass_tank
    root, tk = glass_tank(f"{p.id}_t", r=0.2 * k, h=0.62 * k)
    p.add(root)
    top = tk["anchors"]["top"].z
    p.anchor("top", (0, 0, top)); p.anchor("center", (0, 0, top / 2)); p.anchor("inside", tk["anchors"]["inside"])
    p.port("inlet", tk["anchors"]["inlet"], (0, 0, 1))
    p.port("outlet", (-0.2 * k * 0.45, 0, top + 0.05 * k), (0, 0, 1))
    p.add(solid(f"{p.id}_port2", 0.035 * k, 0.06 * k, 0.012 * k, M.brushed("#b9bcc0"), z0=top - 0.005 * k)).location.x = -0.09 * k
    p.interior = {"kind": "cyl", "r": tk["inner_r"] * 0.92, "z0": tk["inner_z"][0], "z1": tk["inner_z"][1]}


def b_glass_box(p, k, color):
    w, d, h = 0.8 * k, 0.6 * k, 1.0 * k
    t = 0.035 * k
    frame = finish(color, "white") if color and color != "steel" else M.brushed()
    p.add(geo.box(f"{p.id}_base", (w + 0.02 * k, d + 0.02 * k, 0.06 * k), (0, 0, 0.03 * k), mat=frame, fillet=0.015 * k))
    p.add(geo.box(f"{p.id}_lid", (w + 0.02 * k, d + 0.02 * k, 0.05 * k), (0, 0, h - 0.025 * k), mat=frame, fillet=0.015 * k))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.add(geo.box(f"{p.id}_post", (t, t, h - 0.1 * k), (sx * (w / 2 - t / 2), sy * (d / 2 - t / 2), h / 2),
                          mat=frame, fillet=0.01 * k))
    for name, size, loc in (("front", (w - t, 0.006 * k, h - 0.11 * k), (0, -d / 2 + t / 2, h / 2)),
                            ("back", (w - t, 0.006 * k, h - 0.11 * k), (0, d / 2 - t / 2, h / 2)),
                            ("left", (0.006 * k, d - t, h - 0.11 * k), (-w / 2 + t / 2, 0, h / 2)),
                            ("right", (0.006 * k, d - t, h - 0.11 * k), (w / 2 - t / 2, 0, h / 2))):
        p.add(geo.box(f"{p.id}_{name}", size, loc, mat=M.glass()))
    for z in (0.38, 0.66):
        p.add(geo.box(f"{p.id}_shelf", (w - 2 * t, d - 2 * t, 0.012 * k), (0, 0, z * h), mat=M.glass("#e6f2f7")))
    p.anchor("top", (0, 0, h)); p.anchor("center", (0, 0, h / 2)); p.anchor("inside", (0, 0, h * 0.5))
    p.anchor("back", (0, d / 2, h * 0.5))
    p.port("back_in", (w * 0.3, d / 2 + 0.01 * k, h * 0.82), (0, 1, 0))
    p.port("back_out", (-w * 0.3, d / 2 + 0.01 * k, h * 0.82), (0, 1, 0))
    p.interior = {"kind": "box", "half": (w / 2 - 2 * t, d / 2 - 2 * t), "z0": 0.08 * k, "z1": h - 0.08 * k}


def b_plinth(p, k, color):
    p.add(geo.box(f"{p.id}_slab", (1.4 * k, 0.8 * k, 0.12 * k), (0, 0, 0.06 * k), mat=M.plinth(), fillet=0.025 * k,
                  segments=4))
    p.anchor("top", (0, 0, 0.12 * k))


# ------------------------------------------------------------ mechanisms

def b_piston_cylinder(p, k, color):
    """Glass cylinder over an open crank: the piston slides, the rod swings, the crank turns (axle along Y)."""
    r_b, crank_z, throw, rod = 0.15 * k, 0.24 * k, 0.11 * k, 0.36 * k
    z_glass0, z_glass1 = 0.5 * k, 0.98 * k
    p.add(tube(f"{p.id}_glass", r_b + 0.01 * k, z_glass1 - z_glass0, 0.007 * k, M.glass(), z0=z_glass0))
    p.add(ring(f"{p.id}_rim_lo", r_b + 0.014 * k, 0.024 * k, z=z_glass0 + 0.01 * k))
    head = p.group("head", loc=(0, 0, z_glass1))
    p.add(geo.box(f"{p.id}_head", (0.42 * k, 0.36 * k, 0.07 * k), (0, 0, 0.035 * k), mat=M.brushed("#c3c6ca", 0.22),
                  fillet=0.02 * k, segments=4), head)
    p.add(geo.box(f"{p.id}_cover", (0.34 * k, 0.28 * k, 0.045 * k), (0, 0, 0.09 * k), mat=finish(color, "red"),
                  fillet=0.02 * k, segments=4), head)
    piston = p.group("piston")
    p.add(solid(f"{p.id}_piston", r_b, 0.13 * k, 0.012 * k, M.brushed()), piston)
    for z in (0.1, 0.075, 0.05):
        p.add(ring(f"{p.id}_pring", r_b + 0.001 * k, 0.008 * k, mat=M.chrome(), z=z * k), piston)
    crank = p.group("crank", loc=(0, 0, crank_z))
    web = _y_axis(geo.prism(f"{p.id}_web", geo.tangent_hull((0, 0), 0.1 * k, (0, throw), 0.045 * k, 24),
                            -0.025 * k, 0.025 * k, mat=M.graphite()))
    geo.bevel(web, 0.008 * k, 2)
    web.location.y = 0.05 * k
    p.add(web, crank)
    p.add(_y_axis(solid(f"{p.id}_pin", 0.03 * k, 0.1 * k, 0.006 * k, M.chrome(), z0=-0.05 * k)), crank).location.z = throw
    p.add(_y_axis(solid(f"{p.id}_shaft", 0.035 * k, 0.4 * k, 0.008 * k, M.chrome(), z0=-0.2 * k)), crank)
    rod_o = p.group("rod")
    p.add(geo.box(f"{p.id}_rod", (0.045 * k, 0.03 * k, rod), (0, 0, -rod / 2), mat=M.graphite(), fillet=0.012 * k), rod_o)
    p.add(_y_axis(solid(f"{p.id}_bigend", 0.045 * k, 0.04 * k, 0.01 * k, M.graphite(), z0=-0.02 * k)), rod_o).location.z = -rod
    stands = [geo.box(f"{p.id}_stand", (0.04 * k, 0.05 * k, crank_z), (sx * 0.17 * k, 0.12 * k, crank_z / 2),
                      mat=M.graphite(), fillet=0.01 * k) for sx in (-1, 1)]
    for s_ in stands:
        p.add(s_)

    def crank_to(a):
        crank.rotation_euler = (0, a, 0)
        px, pz = throw * math.sin(a), throw * math.cos(a)       # crank pin in XZ (y axis rotation)
        pin_z = crank_z + pz + math.sqrt(max(1e-9, rod * rod - px * px))
        piston.location = (0, 0, pin_z)
        rod_o.location = (0, 0, pin_z)
        rod_o.rotation_euler = (0, math.atan2(px, pin_z - (crank_z + pz)), 0)
    p.drivers["crank"] = crank_to
    crank_to(0.0)
    p.piston_top = lambda: piston.location.z + 0.13 * k
    p.anchor("piston", (0, 0, 0.13 * k), piston); p.anchor("top", (0, 0, 0.12 * k), head)
    p.anchor("inside", (0, 0, (z_glass0 + z_glass1) / 2 + 0.1 * k)); p.anchor("crank", (0, -0.05 * k, throw), crank)
    p.anchor("rod", (0, 0, -rod / 2), rod_o)
    p.port("top", (0, 0, 0.12 * k), (0, 0, 1), head)
    p.port("intake", (-0.21 * k, 0, 0.035 * k), (-1, 0, 0), head)
    p.port("exhaust", (0.21 * k, 0, 0.035 * k), (1, 0, 0), head)
    p.interior = {"kind": "cyl", "r": r_b * 0.92, "z0": "piston", "z1": z_glass1 - 0.01 * k}


def b_piston(p, k, color):
    body = p.group("body")
    p.add(solid(f"{p.id}_p", 0.15 * k, 0.2 * k, 0.015 * k, M.brushed()), body)
    for z in (0.17, 0.14, 0.11):
        p.add(ring(f"{p.id}_ring", 0.151 * k, 0.01 * k, mat=M.chrome(), z=z * k), body)
    p.drivers["stroke"] = lambda v: setattr(body, "location", (0, 0, 0.08 * k * v))
    p.anchor("top", (0, 0, 0.2 * k), body); p.anchor("center", (0, 0, 0.1 * k), body)


def _wheel_disc(p, name, r, width, mat, parent, holes=5):
    disc = _y_axis(solid(name, r, width, min(width * 0.3, 0.02), mat, z0=-width / 2))
    for i in range(holes):
        a = math.tau * i / holes
        h = _y_axis(geo.cylinder("hole", r * 0.18, -width, width, 24))
        h.location = (r * 0.55 * math.cos(a), 0, r * 0.55 * math.sin(a))
        geo.boolean(disc, h)
    p.add(disc, parent)
    return disc


def b_crank_wheel(p, k, color):
    hub = p.group("hub", loc=(0, 0, 0.3 * k))
    _wheel_disc(p, f"{p.id}_disc", 0.28 * k, 0.06 * k, M.brushed(), hub)
    p.add(_y_axis(ring(f"{p.id}_rim", 0.28 * k, 0.03 * k, mat=M.chrome(), z=0.0)), hub)
    p.add(_y_axis(solid(f"{p.id}_pin", 0.03 * k, 0.12 * k, 0.006 * k, M.chrome(), z0=-0.13 * k)), hub).location.z = 0.18 * k
    p.add(_y_axis(solid(f"{p.id}_axle", 0.035 * k, 0.24 * k, 0.008 * k, M.graphite(), z0=-0.04 * k)), hub)
    p.add(geo.box(f"{p.id}_stand", (0.08 * k, 0.06 * k, 0.3 * k), (0, 0.12 * k, 0.15 * k), mat=M.graphite(),
                  fillet=0.015 * k))
    p.drivers["spin"] = lambda a: setattr(hub, "rotation_euler", (0, a, 0))
    p.anchor("center", (0, -0.04 * k, 0.3 * k)); p.anchor("pin", (0, -0.12 * k, 0.18 * k), hub)
    p.anchor("rim", (0, -0.03 * k, 0.58 * k))


def b_flywheel(p, k, color):
    hub = p.group("hub", loc=(0, 0, 0.32 * k))
    _wheel_disc(p, f"{p.id}_disc", 0.29 * k, 0.1 * k, M.brushed("#b9bcc0"), hub, holes=6)
    p.add(_y_axis(ring(f"{p.id}_rim", 0.29 * k, 0.05 * k, mat=M.graphite(), z=0.0)), hub)
    p.add(_y_axis(solid(f"{p.id}_cap", 0.05 * k, 0.13 * k, 0.01 * k, M.chrome(), z0=-0.065 * k)), hub)
    p.add(geo.box(f"{p.id}_stand", (0.1 * k, 0.08 * k, 0.3 * k), (0, 0.1 * k, 0.15 * k), mat=M.graphite(), fillet=0.02 * k))
    p.drivers["spin"] = lambda a: setattr(hub, "rotation_euler", (0, a, 0))
    p.anchor("center", (0, -0.06 * k, 0.32 * k)); p.anchor("rim", (0, -0.05 * k, 0.61 * k))


def b_gear(p, k, color):
    hub = p.group("hub", loc=(0, 0, 0.2 * k))
    p.add(_gear_mesh(f"{p.id}_gear", 0.2 * k, 14, 0.07 * k, finish(color, "steel"), hole=0.03 * k), hub)
    p.add(_y_axis(solid(f"{p.id}_axle", 0.03 * k, 0.12 * k, 0.006 * k, M.chrome(), z0=-0.06 * k)), hub)
    p.drivers["spin"] = lambda a: setattr(hub, "rotation_euler", (0, a, 0))
    p.anchor("center", (0, -0.04 * k, 0.2 * k)); p.anchor("teeth", (0, -0.03 * k, 0.4 * k))


def b_gear_pair(p, k, color):
    small = p.group("small", loc=(-0.24 * k, 0, 0.25 * k))
    big = p.group("big", loc=(0.13 * k, 0, 0.25 * k))
    p.add(_gear_mesh(f"{p.id}_s", 0.13 * k, 9, 0.07 * k, M.brass(), hole=0.02 * k), small)
    p.add(_gear_mesh(f"{p.id}_b", 0.245 * k, 18, 0.07 * k, finish(color, "steel"), hole=0.03 * k), big)
    for g_ in (small, big):
        p.add(_y_axis(solid(f"{p.id}_axle", 0.025 * k, 0.12 * k, 0.006 * k, M.chrome(), z0=-0.06 * k)), g_)

    def spin(a):
        small.rotation_euler = (0, a, 0)
        big.rotation_euler = (0, -a * 0.5 + math.pi / 18, 0)
    p.drivers["spin"] = spin
    p.anchor("small", (-0.24 * k, -0.04 * k, 0.25 * k)); p.anchor("big", (0.13 * k, -0.04 * k, 0.25 * k))


def b_shaft(p, k, color):
    rot = p.group("rot", loc=(0, 0, 0.035 * k))
    p.add(_x_axis(solid(f"{p.id}_shaft", 0.03 * k, 1.0 * k, 0.008 * k, M.chrome(), z0=-0.5 * k)), rot)
    key = geo.box(f"{p.id}_key", (0.12 * k, 0.012 * k, 0.012 * k), (0.3 * k, 0, 0.03 * k), mat=M.paint(PAINT["red"]))
    p.add(key, rot)
    p.drivers["spin"] = lambda a: setattr(rot, "rotation_euler", (a, 0, 0))
    p.anchor("center", (0, -0.03 * k, 0.035 * k)); p.anchor("end", (0.5 * k, 0, 0.035 * k))


def b_wheel(p, k, color):
    hub = p.group("hub", loc=(0, 0, 0.36 * k))
    prof = [(0.2 * k, -0.12 * k), (0.3 * k, -0.13 * k)] + _arc(0.3 * k, -0.08 * k, 0.05 * k, -90, 90, 8)[1:] + \
        [(0.3 * k, 0.13 * k), (0.2 * k, 0.12 * k), (0.2 * k, -0.12 * k)]
    tyre = _y_axis(geo.lathe(f"{p.id}_tyre", prof, 64, mat=M.rubber("#18181a")))
    p.add(tyre, hub)
    _wheel_disc(p, f"{p.id}_rim", 0.2 * k, 0.18 * k, M.brushed("#c9ccd0", 0.2), hub, holes=5)
    p.add(_y_axis(solid(f"{p.id}_cap", 0.05 * k, 0.2 * k, 0.012 * k, M.chrome(), z0=-0.1 * k)), hub)
    p.drivers["spin"] = lambda a: setattr(hub, "rotation_euler", (0, a, 0))
    p.anchor("hub", (0, -0.1 * k, 0.36 * k)); p.anchor("center", (0, 0, 0.36 * k))


def b_belt_drive(p, k, color):
    a = p.group("a", loc=(-0.3 * k, 0, 0.23 * k))
    b = p.group("b", loc=(0.27 * k, 0, 0.23 * k))
    for g_, r in ((a, 0.08 * k), (b, 0.17 * k)):
        _wheel_disc(p, f"{p.id}_pulley", r, 0.05 * k, M.brushed(), g_, holes=4 if r > 0.1 else 0)
    pts = []
    for (cx, r) in ((-0.3 * k, 0.085 * k), (0.27 * k, 0.175 * k)):
        pts += [(cx + r * math.cos(t), r * math.sin(t)) for t in [math.tau * i / 48 for i in range(48)]]
    from cutaway.blender.assemblies.inline4 import convex_hull
    hull = convex_hull(pts)
    loop = [(x, -0.0, z + 0.23 * k) for x, z in hull] + [(hull[0][0], 0, hull[0][1] + 0.23 * k)]
    p.add(geo.sweep(f"{p.id}_belt", loop, 0.012 * k, mat=M.rubber("#202022"), segments=8))

    def spin(t):
        a.rotation_euler = (0, t, 0)
        b.rotation_euler = (0, t * 0.47, 0)
    p.drivers["spin"] = spin
    p.anchor("drive", (-0.3 * k, -0.04 * k, 0.23 * k)); p.anchor("driven", (0.27 * k, -0.04 * k, 0.23 * k))


def _blades(p, name, n, r0, r1, chord, pitch_deg, mat, parent):
    for i in range(n):
        bl = geo.box(name, (chord, 0.008, r1 - r0), (0, 0, (r0 + r1) / 2), mat=mat, fillet=min(0.006, chord * 0.2))
        holder = p.group(f"{name}_h{i}", parent)
        bl.rotation_euler = (0, 0, math.radians(pitch_deg))
        p.add(bl, holder)
        holder.rotation_euler = (0, math.tau * i / n, 0)


def b_fan(p, k, color):
    c = p.group("c", loc=(0, 0, 0.3 * k))
    p.add(_y_axis(tube(f"{p.id}_duct", 0.29 * k, 0.2 * k, 0.025 * k, M.brushed(), z0=-0.1 * k)), c)
    rotor = p.group("rotor", c)
    p.add(_y_axis(solid(f"{p.id}_hub", 0.06 * k, 0.12 * k, 0.025 * k, M.chrome(), z0=-0.08 * k)), rotor)
    _blades(p, f"{p.id}_blade", 7, 0.05 * k, 0.26 * k, 0.09 * k, 32, finish(color, "steel"), rotor)
    p.add(geo.box(f"{p.id}_foot", (0.3 * k, 0.2 * k, 0.03 * k), (0, 0, 0.015 * k), mat=M.graphite(), fillet=0.01 * k))
    p.drivers["spin"] = lambda a: setattr(rotor, "rotation_euler", (0, a, 0))
    p.anchor("center", (0, -0.1 * k, 0.3 * k))
    p.port("front", (0, -0.13 * k, 0.3 * k), (0, -1, 0)); p.port("back", (0, 0.13 * k, 0.3 * k), (0, 1, 0))


def b_turbine(p, k, color):
    c = p.group("c", loc=(0, 0, 0.28 * k))
    rotor = p.group("rotor", c)
    p.add(_y_axis(solid(f"{p.id}_disc", 0.12 * k, 0.08 * k, 0.02 * k, M.brushed(), z0=-0.04 * k)), rotor)
    _blades(p, f"{p.id}_blade", 24, 0.1 * k, 0.26 * k, 0.045 * k, 40, finish(color, "steel"), rotor)
    p.add(_y_axis(solid(f"{p.id}_shaft", 0.025 * k, 0.3 * k, 0.006 * k, M.chrome(), z0=-0.15 * k)), c)
    p.add(_y_axis(ring(f"{p.id}_shroud", 0.27 * k, 0.02 * k, mat=M.graphite(), z=0.0)), c)
    p.add(geo.box(f"{p.id}_foot", (0.08 * k, 0.12 * k, 0.03 * k), (0, 0.12 * k, 0.015 * k), mat=M.graphite()))
    p.drivers["spin"] = lambda a: setattr(rotor, "rotation_euler", (0, a, 0))
    p.anchor("center", (0, -0.06 * k, 0.28 * k)); p.anchor("blades", (0, -0.04 * k, 0.48 * k))
    p.port("front", (0, -0.16 * k, 0.28 * k), (0, -1, 0)); p.port("back", (0, 0.16 * k, 0.28 * k), (0, 1, 0))


def b_compressor(p, k, color):
    w, d, h = 0.42 * k, 0.32 * k, 0.36 * k
    p.add(geo.box(f"{p.id}_case", (w, d, h), (0, 0, h / 2), mat=finish(color, "black"), fillet=0.05 * k, segments=5))
    win = geo.box(f"{p.id}_window", (0.2 * k, 0.01 * k, 0.22 * k), (-0.05 * k, -d / 2 - 0.002 * k, h / 2),
                  mat=M.glass(), fillet=0.02 * k)
    p.add(win)
    p.add(geo.box(f"{p.id}_bezel", (0.23 * k, 0.006 * k, 0.25 * k), (-0.05 * k, -d / 2 + 0.002 * k, h / 2),
                  mat=M.graphite(), fillet=0.025 * k))
    inner = p.group("inner", loc=(-0.05 * k, -d / 2 + 0.03 * k, h / 2))
    p.add(solid(f"{p.id}_ipiston", 0.06 * k, 0.06 * k, 0.008 * k, M.brushed()), inner)
    motor = p.group("motor", loc=(w / 2 - 0.02 * k, 0, h * 0.45))
    p.add(_x_axis(solid(f"{p.id}_motor", 0.09 * k, 0.12 * k, 0.02 * k, M.paint(PAINT["black"], 0.35), z0=0.0)), motor)
    fanr = p.group("fanr", motor, (0.125 * k, 0, 0))
    for i in range(4):
        bl = geo.box(f"{p.id}_mf", (0.006 * k, 0.03 * k, 0.07 * k), (0, 0, 0.04 * k), mat=M.chrome())
        hold = p.group(f"mfh{i}", fanr)
        p.add(bl, hold)
        hold.rotation_euler = (math.tau * i / 4, 0, 0)
    for sx in (-1, 1):
        p.add(geo.box(f"{p.id}_foot", (0.06 * k, d * 0.8, 0.025 * k), (sx * 0.14 * k, 0, 0.0125 * k), mat=M.rubber()))

    def pump(a):
        inner.location.z = h / 2 - 0.03 * k + 0.05 * k * (0.5 + 0.5 * math.cos(a))
        fanr.rotation_euler = (a * 2, 0, 0)
    p.drivers["pump"] = pump
    p.anchor("center", (0, -d / 2, h / 2)); p.anchor("window", (-0.05 * k, -d / 2, h / 2))
    p.anchor("motor", (w / 2 + 0.06 * k, -0.05 * k, h * 0.45))
    for name, x in (("in", -0.12 * k), ("out", 0.1 * k)):
        p.add(solid(f"{p.id}_{name}", 0.03 * k, 0.05 * k, 0.01 * k, M.brass(), z0=h - 0.01 * k)).location.x = x
        p.port(name, (x, 0, h + 0.04 * k), (0, 0, 1))


def b_pump(p, k, color):
    from .parts import hand_pump
    root, pk = hand_pump(f"{p.id}_hp", h=0.72 * k)
    p.add(root)
    rest = pk["handle"].location.z
    p.drivers["stroke"] = lambda v: setattr(pk["handle"].location, "z", rest - pk["travel"] * v)
    p.anchor("handle", (0, 0, 0.45 * k), pk["handle"]); p.anchor("barrel", (0, -0.06 * k, 0.3 * k))
    p.port("outlet", (0.062 * k, 0, 0.09 * k), (1, 0, 0))


def b_motor(p, k, color):
    c = p.group("c", loc=(0, 0, 0.16 * k))
    p.add(_x_axis(solid(f"{p.id}_can", 0.12 * k, 0.28 * k, 0.025 * k, finish(color, "blue"), z0=-0.14 * k)), c)
    for x in (-0.08, 0.0, 0.08):
        p.add(_x_axis(ring(f"{p.id}_fin", 0.122 * k, 0.012 * k, mat=M.brushed(), z=0.0)), c).location.x = x * k
    rot = p.group("rot", c, (0.14 * k, 0, 0))
    p.add(_x_axis(solid(f"{p.id}_shaft", 0.018 * k, 0.12 * k, 0.004 * k, M.chrome(), z0=0.0)), rot)
    p.add(geo.box(f"{p.id}_flat", (0.1 * k, 0.006 * k, 0.012 * k), (0.07 * k, 0, 0.015 * k), mat=M.paint(PAINT["red"])), rot)
    for x in (-0.09, 0.09):
        p.add(geo.box(f"{p.id}_foot", (0.04 * k, 0.2 * k, 0.05 * k), (x * k, 0, 0.025 * k), mat=M.graphite(), fillet=0.008 * k))
    p.drivers["spin"] = lambda a: setattr(rot, "rotation_euler", (a, 0, 0))
    p.anchor("center", (0, -0.12 * k, 0.16 * k)); p.anchor("shaft", (0.22 * k, 0, 0.16 * k))


def b_spring(p, k, color):
    coil = p.group("coil", loc=(0, 0, 0.02 * k))
    pts = geo.helix(0.06 * k, 0.04 * k, 8.0)
    p.add(geo.sweep(f"{p.id}_coil", pts, 0.009 * k, mat=M.chrome(), segments=10), coil)
    for z in (0.0, 0.36):
        p.add(solid(f"{p.id}_plate", 0.075 * k, 0.02 * k, 0.006 * k, M.brushed(), z0=z * k))
    top = p.group("topplate", loc=(0, 0, 0.36 * k))

    def squeeze(v):
        s = 1 - 0.45 * max(0.0, min(1.0, v))
        coil.scale = (1, 1, s)
        top.location.z = 0.02 * k + 0.32 * k * s
    p.drivers["squeeze"] = squeeze
    p.anchor("top", (0, 0, 0.38 * k)); p.anchor("center", (0, -0.07 * k, 0.2 * k))


def b_lever(p, k, color):
    piv = _y_axis(geo.prism(f"{p.id}_pivot", [(-0.08 * k, 0.0), (0.08 * k, 0.0), (0.0, 0.14 * k)], -0.05 * k, 0.05 * k,
                            mat=finish(color, "red")))
    geo.bevel(piv, 0.008 * k, 2)
    p.add(piv)
    bar = p.group("bar", loc=(0, 0, 0.15 * k))
    p.add(geo.box(f"{p.id}_bar", (0.9 * k, 0.06 * k, 0.04 * k), (0, 0, 0.0), mat=M.brushed(), fillet=0.015 * k), bar)
    p.drivers["tilt"] = lambda v: setattr(bar, "rotation_euler", (0, math.radians(-14 + 28 * v), 0))
    p.anchor("pivot", (0, -0.05 * k, 0.13 * k)); p.anchor("end", (0.43 * k, 0, 0.0), bar)


def b_valve(p, k, color):
    from .parts import valve
    root, vk = valve(f"{p.id}_v", r=0.075 * k)
    root.scale = (k, k, k)
    p.add(root)
    p.drivers["turn"] = lambda a: setattr(vk["wheel"], "rotation_euler", (0, 0, -a))
    p.anchor("wheel", (0, 0, 0.13 * k))
    p.port("in", (-0.03 * k, 0, 0.035 * k), (-1, 0, 0)); p.port("out", (0.03 * k, 0, 0.035 * k), (1, 0, 0))


def b_nozzle(p, k, color):
    prof = [(0, 0), (0.09 * k, 0), (0.09 * k, 0.06 * k), (0.03 * k, 0.24 * k), (0.03 * k, 0.28 * k), (0, 0.28 * k)]
    n = geo.lathe(f"{p.id}_nozzle", prof, 48, mat=M.brass())
    geo.bevel(n, 0.006 * k, 2)
    n.rotation_euler.y = math.radians(90)
    n.location = (-0.14 * k, 0, 0.1 * k)
    p.add(n)
    p.anchor("tip", (0.14 * k, 0, 0.1 * k)); p.anchor("center", (0, -0.06 * k, 0.1 * k))
    p.port("in", (-0.15 * k, 0, 0.1 * k), (-1, 0, 0)); p.port("out", (0.15 * k, 0, 0.1 * k), (1, 0, 0))


def b_spark_plug(p, k, color):
    p.add(solid(f"{p.id}_thread", 0.012 * k, 0.04 * k, 0.003 * k, M.brushed()))
    p.add(geo.cylinder(f"{p.id}_hex", 0.022 * k, 0.04 * k, 0.065 * k, 6, mat=M.chrome()))
    p.add(solid(f"{p.id}_ceramic", 0.014 * k, 0.12 * k, 0.006 * k, M.plastic("#f4f2ee", 0.25), z0=0.065 * k))
    p.add(geo.cylinder(f"{p.id}_term", 0.005 * k, 0.185 * k, 0.2 * k, 12, mat=M.chrome()))
    p.anchor("tip", (0, 0, 0.0)); p.anchor("top", (0, 0, 0.2 * k))


def b_coil(p, k, color):
    pts, z, rows = [], 0.06 * k, 6
    w = 0.3 * k
    for i in range(rows):
        x0, x1 = (-w, w) if i % 2 == 0 else (w, -w)
        zz = z + i * 0.09 * k
        pts += [(x0, 0, zz), (x1, 0, zz)]
        if i < rows - 1:
            r = 0.045 * k
            cx = x1
            sgn = 1 if i % 2 == 0 else -1
            pts += [(cx + sgn * r * math.sin(math.radians(a)), 0, zz + r - r * math.cos(math.radians(a)))
                    for a in range(30, 151, 30)]
    pts = [(-w - 0.05 * k, 0, 0.06 * k)] + pts + [(pts[-1][0] + (0.05 * k if pts[-1][0] > 0 else -0.05 * k), 0, pts[-1][2])]
    mat = M.copper() if (color or "copper") == "copper" else finish(color)
    p.add(geo.sweep(f"{p.id}_pipe", pts, 0.016 * k, mat=mat, segments=14))
    for x in (-0.2, 0.2):
        p.add(geo.box(f"{p.id}_clip", (0.025 * k, 0.03 * k, 0.5 * k), (x * k, 0.02 * k, 0.27 * k), mat=M.graphite(),
                      fillet=0.008 * k))
    p.add(geo.box(f"{p.id}_foot", (0.66 * k, 0.08 * k, 0.025 * k), (0, 0.02 * k, 0.0125 * k), mat=M.graphite(),
                  fillet=0.01 * k))
    p.anchor("center", (0, -0.03 * k, 0.3 * k)); p.anchor("start", pts[0]); p.anchor("end", pts[-1])
    p.port("in", pts[0], (-1, 0, 0)); p.port("out", pts[-1], (1 if pts[-1][0] > 0 else -1, 0, 0))
    p.flow_path = pts


def b_radiator(p, k, color):
    for i in range(22):
        x = -0.32 * k + i * 0.0305 * k
        p.add(geo.box(f"{p.id}_fin", (0.008 * k, 0.16 * k, 0.48 * k), (x, 0, 0.29 * k), mat=M.brushed("#c3c6ca", 0.3)))
    for z in (0.04, 0.54):
        p.add(geo.box(f"{p.id}_tank", (0.7 * k, 0.18 * k, 0.04 * k), (0, 0, z * k), mat=M.graphite(), fillet=0.012 * k))
    pts = [(-0.38 * k, -0.0, 0.47 * k), (0.3 * k, 0, 0.47 * k), (0.3 * k, 0, 0.35 * k), (-0.3 * k, 0, 0.35 * k),
           (-0.3 * k, 0, 0.23 * k), (0.3 * k, 0, 0.23 * k), (0.3 * k, 0, 0.11 * k), (0.38 * k, 0, 0.11 * k)]
    p.add(geo.sweep(f"{p.id}_pipe", pts, 0.014 * k, mat=M.copper(), segments=12))
    p.anchor("center", (0, -0.09 * k, 0.29 * k)); p.anchor("front", (0, -0.09 * k, 0.29 * k))
    p.port("in", pts[0], (-1, 0, 0)); p.port("out", pts[-1], (1, 0, 0))
    p.flow_path = pts


def b_burner(p, k, color):
    p.add(solid(f"{p.id}_base", 0.15 * k, 0.05 * k, 0.012 * k, M.graphite()))
    p.add(ring(f"{p.id}_ring", 0.1 * k, 0.03 * k, mat=M.graphite("#3a3b3e"), z=0.065 * k))
    for i in range(16):
        a = math.tau * i / 16
        f = _sphere(f"{p.id}_flame", 0.012 * k, M.glow("#4f8dff", 14.0), segs=12)
        f.scale = (1, 1, 2.4)
        f.location = (0.1 * k * math.cos(a), 0.1 * k * math.sin(a), 0.1 * k)
        f["glow"] = 1.0
        p.add(f)
    p.anchor("flame", (0, 0, 0.11 * k)); p.anchor("center", (0, -0.15 * k, 0.05 * k))


def b_heater(p, k, color):
    for x in (-0.18, 0.18):
        p.add(geo.box(f"{p.id}_post", (0.03 * k, 0.06 * k, 0.24 * k), (x * k, 0, 0.12 * k), mat=M.plastic("#f0ede8", 0.3),
                      fillet=0.01 * k))
    pts = [(-0.18 * k + 0.36 * k * i / 120, 0.022 * k * math.cos(i * 0.6), 0.16 * k + 0.022 * k * math.sin(i * 0.6))
           for i in range(121)]
    wire = geo.sweep(f"{p.id}_wire", pts, 0.004 * k, mat=M.brushed("#8a8c90"), segments=6)
    p.add(wire)
    wire["heat"] = 0.0
    p.anchor("center", (0, -0.03 * k, 0.16 * k))


def b_battery(p, k, color):
    p.add(solid(f"{p.id}_cell", 0.09 * k, 0.36 * k, 0.015 * k, finish(color, "black")))
    p.add(tube(f"{p.id}_band", 0.0915 * k, 0.1 * k, 0.003 * k, M.copper(), z0=0.26 * k))
    p.add(solid(f"{p.id}_plus", 0.03 * k, 0.03 * k, 0.008 * k, M.chrome(), z0=0.357 * k))
    p.anchor("plus", (0, 0, 0.39 * k)); p.anchor("center", (0, -0.09 * k, 0.18 * k))


def b_bulb(p, k, color):
    p.add(solid(f"{p.id}_base", 0.035 * k, 0.07 * k, 0.008 * k, M.brass()))
    prof = [(0.035 * k, 0.07 * k), (0.03 * k, 0.1 * k)] + \
        [(0.075 * k * math.sin(math.radians(a)), 0.175 * k - 0.075 * k * math.cos(math.radians(a))) for a in range(40, 181, 10)]
    prof[-1] = (0, prof[-1][1])
    p.add(geo.lathe(f"{p.id}_glass", prof, 48, mat=M.glass("#fff8e8")))
    fil = geo.sweep(f"{p.id}_filament", [(-0.02 * k, 0, 0.12 * k), (-0.01 * k, 0, 0.17 * k), (0.01 * k, 0, 0.17 * k),
                                          (0.02 * k, 0, 0.12 * k)], 0.002 * k, mat=M.brushed("#9a9a9a"))
    p.add(fil)
    p.anchor("center", (0, -0.08 * k, 0.17 * k))


def b_gauge(p, k, color):
    c = p.group("c", loc=(0, 0, 0.17 * k))
    p.add(geo.box(f"{p.id}_post", (0.03 * k, 0.03 * k, 0.1 * k), (0, 0.02 * k, 0.05 * k), mat=M.graphite()))
    p.add(_y_axis(solid(f"{p.id}_face", 0.13 * k, 0.03 * k, 0.006 * k, M.plastic("#f5f3ef", 0.3), z0=-0.015 * k)), c)
    p.add(_y_axis(ring(f"{p.id}_bezel", 0.135 * k, 0.025 * k, mat=M.chrome(), z=0.0)), c)
    for i in range(11):
        a = math.radians(-120 + 24 * i)
        t = geo.box(f"{p.id}_tick", (0.006 * k, 0.004 * k, 0.025 * k), (0, 0, 0.0), mat=M.paint(PAINT["black"]))
        t.location = (0.105 * k * math.sin(a), -0.018 * k, 0.105 * k * math.cos(a))
        t.rotation_euler = (0, a, 0)
        p.add(t, c)
    red = geo.box(f"{p.id}_redzone", (0.006 * k, 0.004 * k, 0.03 * k), (0, 0, 0), mat=M.paint(PAINT["red"]))
    red.location = (0.105 * k * math.sin(math.radians(110)), -0.018 * k, 0.105 * k * math.cos(math.radians(110)))
    red.rotation_euler = (0, math.radians(110), 0)
    p.add(red, c)
    needle = p.group("needle", c, (0, -0.022 * k, 0))
    p.add(geo.box(f"{p.id}_needle", (0.008 * k, 0.004 * k, 0.1 * k), (0, 0, 0.045 * k), mat=M.paint(PAINT["red"])), needle)
    p.add(_y_axis(solid(f"{p.id}_pivot", 0.012 * k, 0.012 * k, 0.003 * k, M.chrome(), z0=-0.006 * k)), needle)
    p.drivers["needle"] = lambda v: setattr(needle, "rotation_euler", (0, math.radians(-120 + 240 * max(0, min(1, v))), 0))
    p.drive("needle", 0.0)
    p.anchor("needle", (0, -0.03 * k, 0.21 * k)); p.anchor("center", (0, -0.03 * k, 0.17 * k))


def b_thermostat(p, k, color):
    c = p.group("c", loc=(0, 0, 0.1 * k))
    p.add(_y_axis(solid(f"{p.id}_plate", 0.1 * k, 0.02 * k, 0.005 * k, M.plastic("#f2efea", 0.35), z0=0.0)), c)
    knob = p.group("knob", c, (0, -0.005 * k, 0))
    p.add(_y_axis(solid(f"{p.id}_knob", 0.065 * k, 0.04 * k, 0.012 * k, finish(color, "white"), z0=-0.04 * k)), knob)
    p.add(geo.box(f"{p.id}_mark", (0.008 * k, 0.004 * k, 0.04 * k), (0, -0.046 * k, 0.035 * k), mat=M.paint(PAINT["red"])), knob)
    for i in range(7):
        a = math.radians(-120 + 40 * i)
        t = geo.box(f"{p.id}_tick", (0.012 * k, 0.006 * k, 0.03 * k), (0, 0, 0), mat=M.paint("#3a6fd8" if i < 3 else PAINT["red"]))
        t.location = (0.085 * k * math.sin(a), -0.012 * k, 0.085 * k * math.cos(a))
        t.rotation_euler = (0, a, 0)
        p.add(t, c)
    p.add(geo.box(f"{p.id}_post", (0.03 * k, 0.03 * k, 0.05 * k), (0, 0.02 * k, 0.025 * k), mat=M.graphite()))
    p.drivers["turn"] = lambda a: setattr(knob, "rotation_euler", (0, a, 0))
    p.anchor("center", (0, -0.05 * k, 0.1 * k))


def b_magnet(p, k, color):
    pts = [(-0.1 * k, 0, 0.03 * k)] + [(-0.1 * k * math.cos(math.radians(a)), 0, 0.18 * k + 0.1 * k * math.sin(math.radians(a)))
                                       for a in range(0, 181, 15)] + [(0.1 * k, 0, 0.03 * k)]
    p.add(geo.sweep(f"{p.id}_arc", pts, 0.035 * k, mat=finish(color, "red"), segments=16))
    for x in (-0.1, 0.1):
        p.add(geo.box(f"{p.id}_tip", (0.075 * k, 0.075 * k, 0.04 * k), (x * k, 0, 0.02 * k), mat=M.brushed(), fillet=0.006 * k))
    p.anchor("poles", (0, -0.04 * k, 0.03 * k)); p.anchor("center", (0, -0.04 * k, 0.16 * k))


def b_key(p, k, color):
    blade = geo.box(f"{p.id}_blade", (0.12 * k, 0.006 * k, 0.025 * k), (0.06 * k, 0, 0.045 * k), mat=M.chrome(),
                    fillet=0.003 * k)
    p.add(blade)
    head = _y_axis(solid(f"{p.id}_head", 0.04 * k, 0.012 * k, 0.005 * k, M.plastic("#1b1b1d", 0.35), z0=-0.006 * k))
    head.location = (-0.03 * k, 0, 0.045 * k)
    p.add(head)
    p.add(_y_axis(ring(f"{p.id}_ring", 0.025 * k, 0.006 * k, mat=M.chrome(), z=0.0))).location = (-0.085 * k, 0, 0.045 * k)
    p.anchor("tip", (0.12 * k, 0, 0.045 * k)); p.anchor("head", (-0.03 * k, -0.01 * k, 0.045 * k))


BUILDERS = {name[2:]: fn for name, fn in globals().items() if name.startswith("b_") and callable(fn)}


def build(spec: dict, k: float | None = None) -> Part:
    """`k` overrides the size preset (a mounted part is scaled to fit its slot)."""
    p = Part(spec["id"], spec["type"])
    k = k or SIZES.get(spec.get("size") or "medium", 1.0)
    BUILDERS[spec["type"]](p, k, spec.get("color"))
    p.k = k
    if "center" not in p.anchors:
        from buildit.kit.vocab import DIMS
        p.anchor("center", (0, 0, DIMS[spec["type"]][2] * k / 2))
    return p
