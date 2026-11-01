"""
Section cuts with capped faces (runs inside Blender).

A cutter is an axis-aligned box (a half-space, a quarter, any slab). Every casting it touches gets an EXACT
boolean whose material mode is TRANSFER, so the faces the cut creates take the cutter's material: matte
red-orange engineering paint with a hatch. The cut is solid, never a hollow shell (the problem with clipping
planes). Moving parts stay whole unless asked; liquids and gas keep their own material on the cut.

States: closed (no cutter), sectioned (cutter in place: castings baked once), peeling (cutter slides in: live
booleans, and whole moving parts vanish the frame the cutter has swallowed them).
"""
from __future__ import annotations

import bpy
from mathutils import Vector

from . import geo
from . import materials as M

BIG = 4.0


def cutter(bounds, name: str = "section_cutter"):
    """bounds = ((xmin, xmax), (ymin, ymax), (zmin, zmax)); None means unbounded on that side.
    E.g. remove everything in front of cylinder 1: ((None, x1), (None, None), (None, None));
    a quarter cut: ((None, x1), (None, 0.0), (None, None))."""
    lo = [b[0] if b[0] is not None else -BIG for b in bounds]
    hi = [b[1] if b[1] is not None else BIG for b in bounds]
    size = [h - l for l, h in zip(lo, hi)]
    center = [(l + h) / 2 for l, h in zip(lo, hi)]
    box = geo.box(name, size, (0, 0, 0), mat=M.section_cap())
    box.location = center
    box.hide_render = True
    box.display_type = "WIRE"
    return box


def _world_bounds(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def side_of(obj, box, margin: float = 0.0):
    """'removed' if the part lies wholly inside the cutter, 'kept' if it does not touch it, else 'cut'.
    `margin` grows the part's box (for parts that move during the shot)."""
    lo, hi = _world_bounds(obj)
    clo, chi = _world_bounds(box)
    lo = lo - Vector((margin,) * 3)
    hi = hi + Vector((margin,) * 3)
    if any(hi[i] <= clo[i] or lo[i] >= chi[i] for i in range(3)):
        return "kept"
    if all(lo[i] >= clo[i] and hi[i] <= chi[i] for i in range(3)):
        return "removed"
    return "cut"


def _centre_inside(obj, box) -> bool:
    lo, hi = _world_bounds(obj)
    c = (lo + hi) / 2
    clo, chi = _world_bounds(box)
    return all(clo[i] <= c[i] <= chi[i] for i in range(3))


def _with_children(objs):
    seen, out = set(), []
    for o in objs:
        for x in (o, *o.children_recursive):
            if x.name not in seen:
                seen.add(x.name)
                out.append(x)
    return out


def _boolean(o, box, own):
    m = o.modifiers.new("section", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = box
    m.material_mode = "INDEX" if own else "TRANSFER"
    m.use_hole_tolerant = True
    return m


def apply(static, moving, box, travel: float = 0.0, cut_moving=(), own_cap=()):
    """Sectioned state: cut the castings the cutter touches (baked once); hide parts wholly inside it.
    Moving parts stay whole unless named in `cut_moving` (they keep a live boolean). Objects in `own_cap`
    (liquids, gas volumes) show their own material on the cut. `travel` widens moving parts' test boxes.
    Returns {'cut': [...], 'removed': [...]}."""
    own = {o.name for o in own_cap}
    cut_names = {o.name for o in cut_moving}
    report = {"cut": [], "removed": []}
    bpy.context.view_layer.update()
    for objs, is_moving in ((static, False), (moving, True)):
        for o in _with_children(objs):
            if o.type != "MESH":
                continue
            whole = is_moving and o.name not in cut_names and (o.parent is None or o.parent.name not in cut_names)
            if whole:                                  # whole moving parts: inside the cutter by their centre = gone
                where = "removed" if _centre_inside(o, box) else "kept"
            else:
                where = side_of(o, box, margin=travel if is_moving else 0.0)
            if where == "kept":
                continue
            if where == "removed":
                o.hide_render = True
                o.hide_viewport = True
                report["removed"].append(o.name)
                continue
            if is_moving and o.name not in cut_names and (o.parent is None or o.parent.name not in cut_names):
                continue
            _boolean(o, box, o.name in own)
            if is_moving:
                if hasattr(o, "cycles"):
                    o.cycles.use_deform_motion = False   # topology changes per frame under a live cut
            else:
                geo.bake(o)
            report["cut"].append(o.name)
    return report


def peel(static, moving, box, axis: int, distance: float, frames: tuple[int, int], cut_moving=(), own_cap=(),
         ease=lambda u: u * u * (3 - 2 * u)):
    """Peeling state: the cutter starts `distance` metres back along `axis` (outside the object) and slides
    to its place between frames[0] and frames[1]. Castings it crosses get live booleans; whole moving parts
    disappear (hide_render keyed) on the frame the cutter has fully swallowed them."""
    own = {o.name for o in own_cap}
    cut_names = {o.name for o in cut_moving}
    home = box.location[axis]
    distance = -abs(distance) if home < 0 else abs(distance)    # start further out on the removed side
    f0, f1 = frames
    for f in range(f0, f1 + 1):
        u = 0.0 if f1 == f0 else (f - f0) / (f1 - f0)
        box.location[axis] = home + distance * (1.0 - ease(u))
        box.keyframe_insert("location", index=axis, frame=f)
    box.location[axis] = home
    bpy.context.view_layer.update()
    report = {"cut": [], "removed": []}
    for objs, is_moving in ((static, False), (moving, True)):
        for o in _with_children(objs):
            if o.type != "MESH":
                continue
            if side_of(o, box) == "kept":
                continue
            whole = is_moving and o.name not in cut_names and (o.parent is None or o.parent.name not in cut_names)
            if whole:
                gone = _swallow_frame(o, box, axis, distance, f0, f1, ease)
                if gone is not None:
                    o.hide_render = False
                    o.keyframe_insert("hide_render", frame=f0 - 1)
                    o.hide_render = True
                    o.keyframe_insert("hide_render", frame=gone)
                    report["removed"].append(o.name)
                continue
            _boolean(o, box, o.name in own)
            if hasattr(o, "cycles"):
                o.cycles.use_deform_motion = False
            report["cut"].append(o.name)
    return report


def _swallow_frame(o, box, axis, distance, f0, f1, ease):
    """First frame on which the moving cutter wholly contains `o` (None if it never does)."""
    home = box.location[axis]
    try:
        for f in range(f0, f1 + 1):
            u = 0.0 if f1 == f0 else (f - f0) / (f1 - f0)
            box.location[axis] = home + distance * (1.0 - ease(u))
            bpy.context.view_layer.update()
            if side_of(o, box) == "removed":
                return f
        return None
    finally:
        box.location[axis] = home
        bpy.context.view_layer.update()
