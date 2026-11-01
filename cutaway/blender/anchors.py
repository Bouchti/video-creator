"""
The Blender -> HyperFrames bridge (runs inside Blender): per-frame screen positions of named empties.

anchors.json = {"fps": 30, "width": 1080, "height": 1920, "frames": {"<frame>": {"<anchor>": [x, y, vis]}}}
x, y are pixels in the 1080x1920 master (origin top-left); vis is 1 when the point is in frame and not hidden
behind geometry, else 0. HyperFrames callouts read this so labels and leader lines stick to moving parts.
"""
from __future__ import annotations

import os

import bpy
from bpy_extras.object_utils import world_to_camera_view

OCCLUSION_SLACK = 0.015          # metres: an anchor sits on a surface, so the ray may hit that surface first


def _occluded(sc, dg, origin, p, own=()) -> bool:
    """True if a rendered solid sits between the camera and p. Cutters, hidden parts and volumes
    (objects flagged no_occlude) are skipped by continuing the ray past them."""
    d = p - origin
    dist = d.length
    direction = d.normalized()
    start = origin.copy()
    travelled = 0.0
    for _ in range(12):
        hit, loc, _n, _i, obj, _m = sc.ray_cast(dg, start, direction, distance=dist - travelled)
        if not hit:
            return False
        travelled = (loc - origin).length
        if travelled >= dist - OCCLUSION_SLACK:
            return False
        src = obj.original if obj is not None else None
        if src is not None and (src.hide_render or src.get("no_occlude") or src.name in own):
            start = loc + direction * 1e-4
            continue
        if os.getenv("CUTAWAY_DEBUG_OCCLUSION"):
            print("OCCLUDED_BY", obj.name if obj else None, round(travelled, 3), round(dist, 3), flush=True)
        return True
    return False


def sample(names, anchors: dict, width: int = 1080, height: int = 1920) -> dict:
    sc = bpy.context.scene
    cam = sc.camera
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    cam_pos = cam.matrix_world.translation
    for n in names:
        e = anchors.get(n)
        if e is None:
            continue
        p = e.matrix_world.translation
        v = world_to_camera_view(sc, cam, p)
        x, y = v.x * width, (1.0 - v.y) * height
        vis = 0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0
        if vis:
            own = set()
            if e.parent is not None:                  # the part an anchor sits on never hides it
                own = {e.parent.name, *(c.name for c in e.parent.children_recursive)}
            vis = not _occluded(sc, dg, cam_pos, p, own)
        out[n] = [round(x, 1), round(y, 1), 1 if vis else 0]
    return out
