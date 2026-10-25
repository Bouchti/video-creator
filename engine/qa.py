"""
Automated scene QA (runs inside Blender after a set has staged the film, before rendering).

For sampled frames of every beat it reports:
  collision   a character's mesh intersects the plane/props/another character (exact BVH test)
  ground      a moving part dips below the ground
  cropped     a visible character is cut by the frame edge (partly in, partly out)
  label_crop  a callout label is cut by the frame edge
  occluded    a visible, in-frame character's head is hidden behind something

Issues are grouped into frame ranges so the report stays short. Pure geometry: no rendering.
"""
import json
import re

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# meshes that are allowed to touch (seated pilot inside the cockpit; held tools)
ALLOWED = {("MaxPilot", "fuselage"), ("MaxPilot", "seat"), ("MaxPilot", "fus_stripe")}
# volumes and effects a character may legitimately be inside (swimming, rain, splashes, dust)
SOFT = re.compile(r"(pool_water|lake_water|_carver|flood|water_surface|rain|splash|bubble|_p\d+$|puff|spray|dust)", re.I)
# a shoe resting on a floor/edge is standing, not a collision
FLOORS = re.compile(r"(floor|turf|coping|slab|deck|dock|ground|strip|step|apron|pad)", re.I)
SKIP_PREFIX = ("field", "airstrip", "g_", "grass", "lawn", "hill", "cloud", "label_", "lbl", "air_", "cutaway_card", "wing_section",
               "Rig", "Cam", "Aim", "ground", "lawn", "sky")


def _root(obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj


def _visible(obj):
    o = obj
    while o is not None:
        if o.hide_render:
            return False
        o = o.parent
    return True


def _mesh_tree(obj, dg):
    ev = obj.evaluated_get(dg)
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return None, None
    if me is None or not me.polygons:
        ev.to_mesh_clear()
        return None, None
    mw = ev.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    return BVHTree.FromPolygons(verts, polys), (lo, hi)


def _boxes_touch(a, b, pad=0.0):
    return all(a[0][i] - pad <= b[1][i] and b[0][i] - pad <= a[1][i] for i in range(3))


def _corners(obj):
    return [obj.matrix_world @ Vector(c) for c in obj.bound_box]


def _group(frames, step):
    """[(f, msg)...] → [(f0, f1, msg)] merging consecutive samples of the same message."""
    out = []
    for f, msg in sorted(frames, key=lambda x: (x[1], x[0])):
        if out and out[-1][2] == msg and f - out[-1][1] <= step:
            out[-1][1] = f
        else:
            out.append([f, f, msg])
    return sorted(out)


def run(scene, characters, mover_root, beats, frame_map, step=3, out_path=None):
    """characters: {name: root_obj}; mover_root: the main moving object's root (plane) whose parts
    must stay above ground; beats: [(label, f0, f1)] in TIMELINE frames; frame_map(f) → scene frame
    actually rendered for f (hooks are staged in the epilogue)."""
    cam = scene.camera
    char_of = {}
    for name, root in characters.items():
        for o in [root] + list(root.children_recursive):
            char_of[o.name] = name
    mover = {o.name for o in mover_root.children_recursive} if mover_root else set()
    meshes = [o for o in scene.objects if o.type == "MESH" and not o.name.startswith(SKIP_PREFIX)]
    issues = {}
    for label, b0, b1 in beats:
        hits = []
        for f in range(b0, b1 + 1, step):
            scene.frame_set(frame_map(f))
            dg = bpy.context.evaluated_depsgraph_get()
            vis = [o for o in meshes if _visible(o)]
            trees = {}

            def tree(o):
                if o.name not in trees:
                    trees[o.name] = _mesh_tree(o, dg)
                return trees[o.name]

            chars = [o for o in vis if o.name in char_of]
            others = [o for o in vis if o.name not in char_of]
            # ---- collisions ----
            seen = set()
            for c in chars:
                tc, bc = tree(c)
                if tc is None:
                    continue
                for o in others + chars:
                    if o is c or char_of.get(o.name) == char_of[c.name]:
                        continue
                    key = tuple(sorted((char_of[c.name], char_of.get(o.name, o.name))))
                    if key in seen or (char_of[c.name], o.name) in ALLOWED or SOFT.search(o.name):
                        continue
                    if FLOORS.search(o.name) and re.search(r"shoe|foot|pantleg", c.name):
                        continue
                    to, bo = tree(o)
                    if to is None or not _boxes_touch(bc, bo):
                        continue
                    if tc.overlap(to):
                        seen.add(key)
                        hits.append((f, f"collision: {key[0]} x {key[1]} ({c.name} / {o.name})"))
            # ---- ground penetration of the moving object ----
            for o in others:
                if o.name in mover:
                    t, bb = tree(o)
                    if t is not None and bb[0].z < -0.06:
                        hits.append((f, f"ground: {o.name} {bb[0].z:.2f} m below the grass"))
            # ---- framing ----
            if mover_root is not None and any(_visible(o) for o in others if o.name in mover):
                body = next(iter(mover_root.children), mover_root)
                c = world_to_camera_view(scene, cam, body.matrix_world @ Vector((-0.3, 0, 1.0)))
                if c.z <= 0 or not (0.04 <= c.x <= 0.96 and 0.04 <= c.y <= 0.96):
                    hits.append((f, f"lost: {mover_root.name} centre out of frame (camera not following)"))
            for name, root in characters.items():
                if not _visible(root):
                    continue
                pts = [world_to_camera_view(scene, cam, p) for o in [root] + list(root.children_recursive)
                       if o.type == "MESH" and _visible(o) for p in _corners(o)]
                pts = [p for p in pts if p.z > 0]
                if not pts:
                    continue
                inside = [0.0 <= p.x <= 1.0 and 0.0 <= p.y <= 1.0 for p in pts]
                if any(inside) and not all(inside):
                    xs, ys = [p.x for p in pts], [p.y for p in pts]
                    if min(xs) < -0.02 or max(xs) > 1.02 or min(ys) < -0.02 or max(ys) > 1.02:
                        hits.append((f, f"cropped: {name} cut by the frame edge"))
                if all(inside):
                    head = next((o for o in root.children_recursive if o.name.endswith("_skull")), None)
                    if head is not None:
                        target = head.matrix_world.translation
                        origin = cam.matrix_world.translation
                        d = target - origin
                        hit, loc, _n, _i, obj, _m = scene.ray_cast(dg, origin, d.normalized(), distance=d.length - 0.35)
                        if (hit and obj is not None and obj.name not in char_of and not obj.hide_render
                                and not SOFT.search(obj.name) and not obj.name.startswith(("g_", "label_"))):
                            hits.append((f, f"occluded: {name}'s head hidden behind {obj.name}"))
            for o in scene.objects:
                if o.type == "EMPTY" and o.name.startswith("label_") and _visible(o) and o.children:
                    pts = [world_to_camera_view(scene, cam, p) for ch in o.children for p in _corners(ch)]
                    s = max(ch.scale.length for ch in o.children) if o.children else 1
                    if s > 0.01 and o.scale.length > 0.3 and pts and any(
                            not (0.0 <= p.x <= 1.0 and 0.0 <= p.y <= 1.0) for p in pts) and any(
                            0.0 <= p.x <= 1.0 and 0.0 <= p.y <= 1.0 for p in pts):
                        hits.append((f, f"label_crop: {o.name.split('_')[1]} cut by the frame edge"))
        if hits:
            issues[label] = [{"frames": [a, b], "issue": m} for a, b, m in _group(hits, step)]
    report = {"step": step, "beats": issues, "count": sum(len(v) for v in issues.values())}
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    return report


def run_objects(scene, frames, allow=None, skip=None):
    """Object-vs-object intersections (pipes through posts, houses inside each other...) at the given
    frames. `allow`: regex of "a x b" pairs that touch by design (a pipe entering a vessel);
    `skip`: regex of object names to ignore (ground, particles, characters)."""
    allow_re = re.compile(allow) if allow else None
    skip_re = re.compile(skip or r"^(field|g_|hill|cloud|label_|lbl|Rig|leaf|trunk)|_p\d+$")
    found = {}
    for f in frames:
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        objs = [o for o in scene.objects if o.type == "MESH" and _visible(o) and not skip_re.search(o.name)]
        trees = {o.name: _mesh_tree(o, dg) for o in objs}
        for i, a in enumerate(objs):
            ta, ba = trees[a.name]
            if ta is None:
                continue
            for b in objs[i + 1:]:
                if _root(a) is _root(b):
                    continue
                pair = " x ".join(sorted((a.name, b.name)))
                if pair in found or (allow_re and allow_re.search(pair)):
                    continue
                tb, bb = trees[b.name]
                if tb is not None and _boxes_touch(ba, bb) and ta.overlap(tb):
                    found[pair] = f
    return found
