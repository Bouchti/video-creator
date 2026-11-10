"""
The host machine body (runs inside Blender): the real product the film is about, as a clean, premium, see-through
model that the story's parts mount on (slots in buildit/kit/hosts.py). White gloss panels and rounded rails where a
real one is solid, clear glass where the viewer must see inside, a few details (handle, kick plate, door seams,
crisper drawer, interior light) so it reads at a glance as THAT machine.

    h = build("fridge")       # h.root (empty at the floor centre), h.meshes, h.anchors, h.dims, h.accent
"""
from __future__ import annotations

import math

import bpy

from buildit.kit import hosts as H
from cutaway.blender import geo

from . import materials as M
from .parts import ring, solid, tube

WHITE = "#eef0f2"


class Host:
    def __init__(self, htype):
        shape, dims, dressing, _about, accent = H.HOSTS[htype]
        self.type, self.shape, self.dims, self.dressing, self.accent = htype, shape, dims, dressing, accent
        self.root = bpy.data.objects.new("machine", None)
        bpy.context.scene.collection.objects.link(self.root)
        self.meshes: list = []
        self.anchors: dict = {}

    def add(self, obj, parent=None):
        obj.parent = parent or self.root
        for o in (obj, *obj.children_recursive):
            if o.type == "MESH":
                self.meshes.append(o)
                o["heat"] = 0.0
                o["frost"] = 0.0
                o["hl"] = 0.0
        return obj

    def anchor(self, name, loc):
        e = bpy.data.objects.new(f"machine_a_{name}", None)
        bpy.context.scene.collection.objects.link(e)
        e.parent = self.root
        e.location = loc
        self.anchors[name] = e
        return e


def _rail(h, name, size, center, mat, f=0.012):
    return h.add(geo.box(name, size, center, mat=mat, fillet=min(f, min(size) * 0.45), segments=3))


def _pane(h, name, size, center):
    o = h.add(geo.box(name, size, center, mat=M.clear_pane()))
    o.visible_shadow = False
    return o


def _cabinet(h, solid_right=True, glass_back=True, front_glass=True, glass_left=True):
    W, D, Ht = h.dims
    white = M.paint(WHITE, 0.22)
    t, base = 0.04, 0.075
    # kick plate and feet
    _rail(h, "kick", (W - 0.06, D - 0.08, base), (0, 0.01, base / 2), M.graphite("#2a2c30", 0.5), 0.01)
    for sx in (-1, 1):
        for sy in (-1, 1):
            h.add(geo.cylinder("foot", 0.022, 0.0, 0.02, 20, mat=M.chrome())).location = (sx * (W / 2 - 0.06),
                                                                                         sy * (D / 2 - 0.06), 0)
    # floor and roof slabs
    _rail(h, "floor", (W, D, t), (0, 0, base + t / 2), white, 0.015)
    _rail(h, "roof", (W, D, t), (0, 0, Ht - t / 2), white, 0.02)
    # corner posts and edge rails: the silhouette of the machine
    for sx in (-1, 1):
        for sy in (-1, 1):
            _rail(h, "post", (t, t, Ht - base), (sx * (W / 2 - t / 2), sy * (D / 2 - t / 2), base + (Ht - base) / 2),
                  white)
    for sy in (-1, 1):
        _rail(h, "rail_x", (W, t, t * 0.8), (0, sy * (D / 2 - t / 2), base + t), white)
    # walls: the right side is solid (a clean backdrop for what is inside), the rest is clear glass
    inner_h = Ht - base - 2 * t
    zc = base + t + inner_h / 2
    if solid_right:
        _rail(h, "side_r", (0.02, D - 2 * t, inner_h), (W / 2 - 0.012, 0, zc), white, 0.006)
        # a pale blue-grey liner inside, so white things in the machine stand out against it
        _rail(h, "liner_r", (0.006, D - 2 * t - 0.02, inner_h - 0.02), (W / 2 - 0.026, 0, zc),
              M.plastic("#b9c9d8", 0.5), 0.002)
    else:
        _pane(h, "glass_r", (0.008, D - 2 * t, inner_h), (W / 2 - 0.01, 0, zc))
    if glass_left:
        _pane(h, "glass_l", (0.008, D - 2 * t, inner_h), (-W / 2 + 0.01, 0, zc))
    if glass_back is None:                      # a cutaway: no back wall at all
        pass
    elif glass_back:
        _pane(h, "glass_b", (W - 2 * t, 0.008, inner_h), (0, D / 2 - 0.01, zc))
    else:
        _rail(h, "back", (W - 2 * t, 0.02, inner_h), (0, D / 2 - 0.012, zc), white, 0.006)
    if front_glass:
        _pane(h, "glass_f", (W - 2 * t, 0.008, inner_h), (0, -D / 2 + 0.01, zc))
    return white, base, t


def _door(h, name, z0, z1, angle, bins):
    """A fridge door hinged at the front right corner, swung open by `angle` degrees: white outside, a pale
    liner inside with door bins holding bottles."""
    W, D, _Ht = h.dims
    hinge = bpy.data.objects.new(f"machine_{name}_hinge", None)
    bpy.context.scene.collection.objects.link(hinge)
    hinge.parent = h.root
    hinge.location = (W / 2, -D / 2, 0)
    th = 0.055
    parts = [geo.box(f"{name}_skin", (W, th, z1 - z0), (-W / 2, -th / 2, (z0 + z1) / 2), mat=M.paint(WHITE, 0.2),
                     fillet=0.02),
             geo.box(f"{name}_liner", (W - 0.08, 0.02, z1 - z0 - 0.08), (-W / 2, 0.01, (z0 + z1) / 2),
                     mat=M.plastic("#dfe3e7", 0.45), fillet=0.008),
             geo.box(f"{name}_handle", (0.03, 0.035, (z1 - z0) * 0.5), (-W + 0.07, -th - 0.02, (z0 + z1) / 2),
                     mat=M.chrome(), fillet=0.012)]
    bottles = [("#f6f7f8", "#1f5bbf"), ("#f08a1c", "#f6f7f8"), ("#c8161d", "#f6f7f8"), ("#3f9b2c", "#e9e6e1")]
    for i, zb in enumerate(bins):
        parts.append(geo.box(f"{name}_bin{i}", (W - 0.12, 0.09, 0.05), (-W / 2, 0.065, zb + 0.025),
                             mat=M.frosted("#e9f2f8", 0.6), fillet=0.006))
        for j in range(3):
            body, cap = bottles[(i * 3 + j) % len(bottles)]
            hb = 0.16 if j != 1 else 0.2
            b = solid(f"{name}_bottle{i}{j}", 0.032, hb, 0.016, M.plastic(body, 0.3), z0=zb + 0.01, segments=24)
            b.location = (-W * 0.25 - j * W * 0.22, 0.065, 0)
            c = solid(f"{name}_cap{i}{j}", 0.016, 0.025, 0.006, M.plastic(cap, 0.3), z0=zb + 0.01 + hb, segments=16)
            c.location = b.location
            parts += [b, c]
    for o in parts:
        h.add(o, hinge)
    hinge.rotation_euler.z = math.radians(angle)
    return hinge


def _fridge(h):
    """A real fridge, cut away: solid white body and back (the condenser hangs on the back, as on a real one),
    closed doors with handles at the front, and the LEFT wall cut open, with foam-coloured cut edges, so the
    inside is seen from the left / back-left like a cutaway illustration."""
    W, D, Ht = h.dims
    white, base, t = _cabinet(h, front_glass=False, glass_left=False, glass_back=False)
    split = Ht * 0.68
    _door(h, "door_main", base + 0.005, split - 0.008, 0, [base + 0.18, base + 0.55, split - 0.33])
    _door(h, "door_freezer", split + 0.008, Ht - 0.005, 0, [])
    inner_h = Ht - base - 2 * t
    zc = base + t + inner_h / 2
    _rail(h, "liner_b", (W - 2 * t - 0.02, 0.006, inner_h - 0.02), (0, D / 2 - 0.028, zc),
          M.plastic("#b9c9d8", 0.5), 0.002)
    # the cut through the insulated walls: a broad foam-yellow band all round the open side, so it reads as a
    # cutaway of a solid fridge (not a glass cabinet)
    foam = M.plastic("#f2c75c", 0.6)
    x, bw = -W / 2 + 0.018, 0.055
    for y in (-D / 2 + bw / 2, D / 2 - bw / 2):
        _rail(h, "cut_v", (0.04, bw, Ht - base), (x, y, base + (Ht - base) / 2), foam, 0.003)
    for z in (base + bw / 2, Ht - bw / 2):
        _rail(h, "cut_h", (0.04, D - 2 * bw + 0.004, bw), (x, 0, z), foam, 0.003)
    # the back panel is the dark metal of a real fridge's back: the condenser and compressor are mounted on it
    _rail(h, "back_skin", (W - 0.01, 0.008, Ht - base - 0.01), (0, D / 2 + 0.004, base + (Ht - base) / 2),
          M.brushed("#9aa1a9", 0.35), 0.004)
    # inside: freezer floor, a glass shelf, the crisper drawer with produce, a cool interior light
    _rail(h, "freezer_floor", (W - 2 * t - 0.02, D - 2 * t - 0.02, 0.018), (0, 0, split - 0.02),
          M.plastic("#aebfd0", 0.45), 0.006)
    sh = h.add(geo.box("shelf", (W - 2 * t - 0.03, D - 2 * t - 0.04, 0.012), (0, 0, Ht * 0.42),
                       mat=M.frosted("#bcd3e6", 0.25)))
    sh.visible_shadow = False
    dz0, dz1 = base + t + 0.01, base + t + 0.20
    dr = h.add(geo.box("drawer", (W - 2 * t - 0.05, D - 2 * t - 0.08, dz1 - dz0), (0, -0.02, (dz0 + dz1) / 2),
                       mat=M.frosted("#f2f6f9", 0.5)))
    dr.visible_shadow = False
    produce = [("#d22a1e", 0.045, -0.18), ("#3f9b2c", 0.05, -0.05), ("#e2671b", 0.04, 0.08), ("#d22a1e", 0.04, 0.2)]
    for i, (c, r, x) in enumerate(produce):
        o = h.add(solid(f"produce{i}", r, r * 1.8, r * 0.9, M.plastic(c, 0.35), segments=24))
        o.location = (x * W, -0.04 + 0.05 * (i % 2), dz0 + 0.005)
    # a full fridge: a milk bottle, a jar and a juice carton on the glass shelf, a cake box above the drawer --
    # along the front and back edges, so they never stand between the cut-open side and a part mounted inside
    zs = Ht * 0.42 + 0.006
    edge = D / 2 - t - 0.06
    things = [("bottle_milk", 0.04, 0.24, "#f6f7f8", 0.28, -edge), ("jar", 0.05, 0.12, "#d9442b", -0.05, edge),
              ("bottle_juice", 0.035, 0.2, "#f08a1c", 0.25, edge)]
    for name, r, hh, c, x, y in things:
        o = h.add(solid(f"shelf_{name}", r, hh, r * 0.4, M.plastic(c, 0.3), z0=zs, segments=24))
        o.location = (x * W, y, 0)
    h.add(geo.box("cake_box", (W * 0.3, 0.12, 0.09), (0.12 * W, edge - 0.02, dz1 + 0.055),
                  mat=M.plastic("#7bc4e8", 0.4), fillet=0.01))
    lamp = h.add(geo.box("lamp", (W * 0.5, 0.05, 0.012), (0, -0.05, split - 0.04), mat=M.glow("#e9f6ff", 3.0)))
    lamp["glow"] = 1.0
    lamp.visible_shadow = False
    h.anchor("door", (0, -D / 2 - 0.02, Ht * 0.45))
    h.anchor("food", (-0.05 * W, -0.02, dz0 + 0.07))


def _washer(h):
    W, D, Ht = h.dims
    white, base, t = _cabinet(h, solid_right=True, glass_back=True)
    _rail(h, "panel", (W - 0.02, 0.03, 0.1), (0, -D / 2 - 0.005, Ht - 0.09), white, 0.01)
    k = h.add(solid("knob", 0.035, 0.03, 0.01, M.chrome()))
    k.rotation_euler.x = math.radians(90)
    k.location = (W * 0.28, -D / 2 - 0.02, Ht - 0.09)
    door = h.add(ring("door_ring", W * 0.3, 0.05, mat=M.chrome(), z=0.0))
    door.rotation_euler.x = math.radians(90)
    door.location = (0, -D / 2 - 0.02, Ht * 0.45)
    h.anchor("door", (0, -D / 2 - 0.02, Ht * 0.45))


def _oven(h):
    W, D, Ht = h.dims
    white, base, t = _cabinet(h, solid_right=True, glass_back=True)
    _rail(h, "panel", (W - 0.02, 0.04, 0.12), (0, -D / 2 - 0.01, Ht - 0.1), M.graphite("#1d1e21", 0.3), 0.01)
    for i, x in enumerate((-0.3, -0.12, 0.12, 0.3)):
        k = h.add(solid(f"knob{i}", 0.025, 0.03, 0.008, M.chrome()))
        k.rotation_euler.x = math.radians(90)
        k.location = (x * W, -D / 2 - 0.035, Ht - 0.1)
    _rail(h, "handle", (W * 0.7, 0.03, 0.03), (0, -D / 2 - 0.04, Ht - 0.2), M.chrome(), 0.012)
    h.anchor("door", (0, -D / 2 - 0.02, Ht * 0.45))


def _ac(h):
    W, D, Ht = h.dims
    white, base, t = _cabinet(h, solid_right=True, glass_back=True)
    g = h.add(ring("grille", min(W, Ht) * 0.3, 0.025, mat=M.graphite("#3a3c40", 0.4)))
    g.rotation_euler.x = math.radians(90)
    g.location = (W * 0.12, -D / 2 - 0.02, Ht * 0.5)
    h.anchor("door", (W * 0.12, -D / 2 - 0.02, Ht * 0.5))


def _tank(h):
    W, D, Ht = h.dims
    r = W / 2
    white = M.paint(WHITE, 0.22)
    h.add(solid("cap_bottom", r, 0.14, 0.05, white, segments=72))
    h.add(solid("cap_top", r, 0.12, 0.05, white, z0=Ht - 0.12, segments=72))
    g = h.add(tube("wall", r - 0.01, Ht - 0.24, 0.01, M.glass(), z0=0.12, segments=72))
    g.visible_shadow = False
    for x in (-0.3, 0.3):
        h.add(geo.cylinder("stub", 0.02, Ht, Ht + 0.12, 20, mat=M.chrome())).location.x = x * r
    for a in (45, 135, 225, 315):
        h.add(geo.cylinder("foot", 0.025, -0.0, 0.03, 16, mat=M.chrome())).location = (
            0.7 * r * math.cos(math.radians(a)), 0.7 * r * math.sin(math.radians(a)), 0)
    h.anchor("door", (0, -r, Ht * 0.45))


def _frame(h):
    W, D, Ht = h.dims
    al = M.brushed("#d3d6da", 0.3)
    t = 0.045
    _rail(h, "base", (W + 0.06, D + 0.06, 0.06), (0, 0, 0.03), M.graphite("#25272b", 0.45), 0.012)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _rail(h, "post", (t, t, Ht), (sx * (W / 2 - t / 2), sy * (D / 2 - t / 2), Ht / 2 + 0.03), al)
    for z in (Ht + 0.03 - t / 2, 0.06 + Ht * 0.5):
        for sy in (-1, 1):
            _rail(h, "rail_x", (W, t, t), (0, sy * (D / 2 - t / 2), z), al)
        for sx in (-1, 1):
            _rail(h, "rail_y", (t, D, t), (sx * (W / 2 - t / 2), 0, z), al)
    for z in (0.06 + 0.012, 0.06 + Ht * 0.5 - t / 2):
        _rail(h, "deck", (W - 2 * t, D - 2 * t, 0.02), (0, 0, z), M.graphite("#3a3c40", 0.4), 0.005)
    h.anchor("door", (0, -D / 2, Ht * 0.5))


DRESS = {"fridge": _fridge, "washer": _washer, "oven": _oven, "ac": _ac, "box": lambda h: _cabinet(h),
         "heater": _tank, "pot": _tank, "frame": _frame}


def build(htype: str) -> Host:
    h = Host(htype if htype in H.HOSTS else "machine")
    DRESS[h.dressing](h)
    W, D, Ht = h.dims
    h.anchor("center", (0, -D / 2, Ht * 0.5))
    h.anchor("top", (0, 0, Ht))
    h.anchor("back", (0, D / 2, Ht * 0.5))
    h.anchor("inside", (0, 0, Ht * 0.45))
    if "food" not in h.anchors:
        h.anchors["food"] = h.anchors["inside"]
    return h
