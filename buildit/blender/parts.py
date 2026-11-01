"""
Chunky, bevelled toy-engineering parts (runs inside Blender). Every generator returns a root object (with its
sub-parts parented to it, so one transform moves the whole part) and a dict of named anchor points (empties) for
labels. Units are metres; a typical machine is about 1 m tall.

Nothing is a bare primitive: profiles carry fillets, rims are rolled, edges are bevelled.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from cutaway.blender import geo

from . import materials as M


def _arc(cx, cz, r, a0, a1, steps=6):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
             cz + r * math.sin(math.radians(a0 + (a1 - a0) * i / steps))) for i in range(steps + 1)]


def rounded_profile(r: float, h: float, f: float, z0: float = 0.0):
    """(radius, z) profile of a solid cylinder with filleted top and bottom edges."""
    f = min(f, r * 0.5, h * 0.5)
    return ([(0.0, z0), (r - f, z0)] + _arc(r - f, z0 + f, f, -90, 0)[1:] +
            _arc(r - f, z0 + h - f, f, 0, 90)[1:] + [(0.0, z0 + h)])


def solid(name, r, h, f, mat, z0=0.0, segments=64):
    return geo.lathe(name, rounded_profile(r, h, f, z0), segments, mat=mat)


def ring(name, r, thick, mat=None, z=0.0, segments=64):
    """A rolled ring (torus-like, slightly flattened): rims and piston rings."""
    prof = [(r + thick * 0.5 * math.cos(math.radians(a)), z + thick * 0.42 * math.sin(math.radians(a)))
            for a in range(-90, 271, 20)]
    o = geo.lathe(name, prof, segments, mat=mat or M.chrome())
    return o


def tube(name, r, h, wall, mat, z0=0.0, segments=72):
    """An open-ended tube with rounded lips (a glass housing wall)."""
    ri = r - wall
    lip = wall * 0.5
    prof = [(ri, z0 + lip)] + _arc(ri + lip, z0 + lip, lip, 180, 360)[1:] + [(r, z0 + h - lip)] + \
        _arc(ri + lip, z0 + h - lip, lip, 0, 180)[1:] + [(ri, z0 + lip)]
    return geo.lathe(name, prof, segments, mat=mat)


def empty(name, loc, parent):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.empty_display_size = 0.02
    e.parent = parent
    e.location = loc
    return e


def _group(name, children, root_loc=(0, 0, 0)):
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    root.location = root_loc
    for c in children:
        c.parent = root
    return root


# ------------------------------------------------------------ parts

def plinth(name="plinth", w=1.2, d=0.8, h=0.12):
    o = geo.box(name, (w, d, h), (0, 0, h / 2), mat=M.plinth(), fillet=min(0.03, h * 0.3), segments=4)
    return _group(name + "_root", [o]), {"top": Vector((0, 0, h))}


def glass_tank(name="tank", r=0.2, h=0.62):
    """A clear glass cylinder between a brushed base and a brushed cap, rolled chrome rims at both ends,
    and an inlet port in the cap."""
    base_h, cap_h = 0.07, 0.07
    base = solid(f"{name}_base", r + 0.03, base_h, 0.018, M.brushed())
    wall = tube(f"{name}_glass", r, h, 0.008, M.glass(), z0=base_h)
    cap = solid(f"{name}_cap", r + 0.03, cap_h, 0.018, M.brushed(), z0=base_h + h)
    rim_lo = ring(f"{name}_rim_lo", r + 0.004, 0.022, z=base_h + 0.012)
    rim_hi = ring(f"{name}_rim_hi", r + 0.004, 0.022, z=base_h + h - 0.012)
    port = solid(f"{name}_port", 0.035, 0.06, 0.012, M.brushed("#b9bcc0"), z0=base_h + h + cap_h - 0.005)
    port.location.x = r * 0.45
    root = _group(name, [base, wall, cap, rim_lo, rim_hi, port])
    top = base_h + h + cap_h
    anchors = {"inside": Vector((0, 0, base_h + h * 0.5)), "top": Vector((0, 0, top)),
               "inlet": Vector((r * 0.45, 0, top + 0.055)), "valve_seat": Vector((-r * 0.35, 0, top))}
    return root, {"anchors": anchors, "inner_r": r - 0.012, "inner_z": (base_h + 0.01, base_h + h - 0.01),
                  "glass": wall}


def hand_pump(name="pump", h=0.72):
    """A bicycle-style floor pump: foot plate, brushed barrel, chrome rod, T-handle with rubber grips.
    The handle group moves along Z (pose with `stroke`), the rest stays."""
    foot = geo.box(f"{name}_foot", (0.30, 0.14, 0.045), (0, 0, 0.0225), mat=M.graphite(), fillet=0.016)
    barrel = solid(f"{name}_barrel", 0.062, h * 0.72, 0.018, M.brushed(), z0=0.045)
    collar = ring(f"{name}_collar", 0.063, 0.026, z=0.045 + h * 0.72 - 0.008)
    fixed = _group(name, [foot, barrel, collar])
    rod = geo.cylinder(f"{name}_rod", 0.016, 0.0, h * 0.62, 24, mat=M.chrome())
    bar = geo.lathe(f"{name}_bar", rounded_profile(0.026, 0.36, 0.012, -0.18), 32, mat=M.graphite())
    geo.transform_mesh(bar, Matrix.Rotation(math.radians(90), 4, "Y"))
    bar.location.z = h * 0.62
    grips = []
    for sx in (-1, 1):
        gp = geo.lathe(f"{name}_grip", rounded_profile(0.034, 0.10, 0.016, -0.05), 32, mat=M.rubber())
        geo.transform_mesh(gp, Matrix.Rotation(math.radians(90), 4, "Y"))
        gp.location = (sx * 0.13, 0, h * 0.62)
        grips.append(gp)
    handle = _group(f"{name}_handle", [rod, bar, *grips])
    handle.parent = fixed
    handle.location.z = 0.045 + h * 0.72 - 0.03 - h * 0.62 + 0.20       # rod mostly inside the barrel
    anchors = {"handle": Vector((0, 0, h * 0.62)), "outlet": Vector((0.062, 0, 0.09))}
    return fixed, {"anchors": anchors, "handle": handle, "travel": 0.16, "outlet_world": Vector((0.045, 0, 0.08))}


def hose(name, points, r=0.014):
    """A rubber hose along points (world space)."""
    return geo.sweep(name, points, r, mat=M.rubber("#222326"), segments=20)


def valve(name="valve", r=0.075):
    """A red handwheel valve: brushed body, chrome stem, glossy red wheel with spokes (the wheel spins)."""
    body = solid(f"{name}_body", 0.03, 0.07, 0.01, M.brushed())
    stem = geo.cylinder(f"{name}_stem", 0.008, 0.07, 0.11, 24, mat=M.chrome())
    rim = ring(f"{name}_rim", r, 0.024, mat=M.paint(), z=0.0)
    hub = solid(f"{name}_hub", 0.02, 0.026, 0.008, M.paint(), z0=-0.013)
    spokes = []
    for k in range(3):
        sp = geo.box(f"{name}_spoke", (r * 2 - 0.02, 0.014, 0.012), (0, 0, 0), mat=M.paint(), fillet=0.005)
        sp.rotation_euler.z = math.radians(60 * k)
        spokes.append(sp)
    wheel = _group(f"{name}_wheel", [rim, hub, *spokes])
    root = _group(name, [body, stem])
    wheel.parent = root
    wheel.location.z = 0.115
    return root, {"anchors": {"wheel": Vector((0, 0, 0.13))}, "wheel": wheel}
