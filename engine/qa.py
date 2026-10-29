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


# ------------------- production quality gates (the channel's standard) -------------------

HERO_MIN = 0.18          # Max's on-screen height (fraction of the frame) when he is the one acting...
HERO_SHARE = 0.35        # ...for at least this share of each beat (the rest may be wide/establishing)
STATIC_SECONDS = 2.5     # a camera that does not move for longer than this is "static"
FLAT_AREA = 0.03         # a flat (untextured) surface covering more than this share of the frame is flagged
FAR = 30.0               # ...unless it is background this far from the camera (soft in depth of field)
TEXT_MIN = 0.018         # a label's letters must be at least this share of the frame height
TEXT_MAX = 0.10          # ...and at most this share: bigger letters bury the shot (a camera inside the label)
_TEXTURE_NODES = {"TEX_NOISE", "TEX_VORONOI", "TEX_WAVE", "TEX_IMAGE", "TEX_MUSGRAVE", "TEX_GRADIENT",
                  "TEX_MAGIC", "TEX_CHECKER", "TEX_BRICK", "TEX_WHITE_NOISE", "BUMP", "ATTRIBUTE",
                  "NEW_GEOMETRY", "VALTORGB"}
_FX = re.compile(r"(label|lbl|arrow|glow|spark|puff|bubble|splash|drop|water|flow|spray|steam|smoke|ray|beam|"
                 r"cloud|sky|glass|window|screen|bulb|lamp|lantern|mark|_p\d+$|tuft|g_)", re.I)


def _screen_box(scene, cam, objs):
    """Projected bbox (x0, y0, x1, y1) in frame units of `objs`, or None when all are behind the camera."""
    pts = [world_to_camera_view(scene, cam, p) for o in objs for p in _corners(o)]
    pts = [p for p in pts if p.z > 0]
    if not pts:
        return None
    return (min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts))


def _on_screen(box):
    return box is not None and box[2] >= 0 and box[0] <= 1 and box[3] >= 0 and box[1] <= 1


def _is_flat(mat):
    """A material with no texture, bump or variation (one constant colour) that is not emissive/clear."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return True
    nodes = mat.node_tree.nodes
    if any(n.type in _TEXTURE_NODES for n in nodes):
        return False
    if any(n.type in ("VOLUME_ABSORPTION", "VOLUME_SCATTER", "EMISSION", "BSDF_GLASS") for n in nodes):
        return False
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        for key in ("Emission Strength", "Transmission Weight", "Alpha"):
            sock = bsdf.inputs.get(key)
            if sock is None or sock.is_linked:
                continue
            if (key == "Alpha" and sock.default_value < 0.95) or (key != "Alpha" and sock.default_value > 0.2):
                return False
    return True


def _coplanar_pairs(objs, dg, max_faces=250):
    """Pairs of objects with overlapping faces in the same plane facing the same way (z-fighting)."""
    import random as _r
    data = {}
    objs_by = {o.name: o for o in objs}
    for o in objs:
        ev = o.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        if me is None or not me.polygons:
            ev.to_mesh_clear()
            continue
        mw = ev.matrix_world
        rot = mw.to_3x3()
        verts = [mw @ v.co for v in me.vertices]
        polys = [p for p in me.polygons if p.area > 1e-4]
        sample = polys if len(polys) <= max_faces else _r.Random(len(o.name)).sample(polys, max_faces)
        centres = [(mw @ p.center, (rot @ p.normal).normalized()) for p in sample]
        tree = BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in me.polygons])
        lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
        hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
        data[o.name] = (tree, centres, (lo, hi))
        ev.to_mesh_clear()
    found = []
    names = list(data)
    same = {n: (objs_by[n].data.name, tuple(round(x, 4) for row in objs_by[n].matrix_world for x in row))
            for n in names}
    for i, a in enumerate(names):
        ta, ca, ba = data[a]
        for b in names[i + 1:]:
            tb, cb, bb = data[b]
            if not _boxes_touch(ba, bb, pad=0.01) or same[a] == same[b]:
                continue                                    # identical copies parked together render as one
            if (ba[1] - ba[0]).length < 0.05 or (bb[1] - bb[0]).length < 0.05:
                continue                                    # specks too small to show a flicker
            hits = 0
            for c, n in ca:
                loc, nb, _idx, dist = tb.find_nearest(c)
                if loc is not None and dist < 0.002 and nb.dot(n) > 0.995:
                    hits += 1
                    if hits >= 3:
                        found.append(" x ".join(sorted((a, b))))
                        break
    return found


def _support(scene, dg, origin, distance, own):
    """Is there a surface (not the character itself) within `distance` straight below `origin`?"""
    o, left = origin.copy(), distance
    for _ in range(8):
        hit, loc, _n, _i, obj, _m = scene.ray_cast(dg, o, Vector((0, 0, -1)), distance=left)
        if not hit or obj is None:
            return False
        if obj.name not in own:
            return True
        left -= (o.z - loc.z) + 0.002                      # passed through its own shoe: keep going
        o = Vector((loc.x, loc.y, loc.z - 0.002))
        if left <= 0:
            return False
    return False


def _painted(o):
    """Lettering fixed on an object (a boat's name, a machine tag) rather than a callout label. Callouts
    are named label_*/lbl* (engine label helpers) or float free (no parent)."""
    chain, p = [o], o.parent
    while p is not None:
        chain.append(p)
        p = p.parent
    if any(re.match(r"(label|lbl)", x.name, re.I) or "label" in x.name.lower() for x in chain):
        return False
    return o.parent is not None


def _longest_still(track, fps):
    """Longest stretch (frames) in which the camera neither moves 4 cm nor turns ~1 degree."""
    start, longest = 0, 0
    for k in range(1, len(track)):
        f, p, d = track[k]
        f0, p0, d0 = track[start]
        if (p - p0).length > 0.04 or d.angle(d0) > 0.018:
            start = k
        else:
            longest = max(longest, f - f0)
    return longest


MUST_MIN = 0.05          # a must-see thing has to span at least this share of the frame (width or height)
MUST_IN = 0.6            # ...with at least this share of its on-screen box inside the frame
MUST_FITS = 0.9          # a thing whose projection is larger than this (width or height) cannot fit: scenery
MUST_PART = 0.25         # ...such scenery must then fill at least this share of the frame width or height


def _named(scene, characters, name):
    """Visible renderable objects a spec's must_see `name` refers to: a character (by name prefix, so
    "Max" covers MaxPilot), or every object whose name starts with `name` (case-insensitive), with the
    children of a matching empty (labels are an empty + letters)."""
    key = name.lower()
    for cname, root in characters.items():
        if cname.lower().startswith(key):
            return [o for o in [root] + list(root.children_recursive) if o.type == "MESH" and _visible(o)]
    found = []
    for o in scene.objects:
        if not o.name.lower().startswith(key):
            continue
        for x in [o] + list(o.children_recursive):
            if x.type in ("MESH", "FONT", "CURVE") and _visible(x) and x not in found:
                found.append(x)
    return found


def must_see(scene, characters, beats, frame_map):
    """The beat's MUST-SEE things (spec ACTIONS[action]["must_see"]) at the middle and 7/8 of the beat,
    the moments the reviewer judges: each must be on screen, readable in size and mostly in frame.
    beats: [(label, f0, f1, [names])]. Returns {label: [{"frames", "issue"}]}."""
    cam = scene.camera
    issues = {}
    for label, b0, b1, names in beats:
        if not names:
            continue
        hits = []
        for part, f in (("middle", (b0 + b1) // 2), ("end", b1 - max(2, (b1 - b0) // 8))):
            scene.frame_set(frame_map(f))
            for name in names:
                objs = _named(scene, characters, name)
                if not objs:
                    hits.append((f, f"must_see: '{name}' is not visible at the {part} of the beat (no visible object "
                                    f"named '{name}*'; show it, or fix the name in the spec's must_see)"))
                    continue
                box = _screen_box(scene, cam, objs)
                if not _on_screen(box):
                    hits.append((f, f"must_see: '{name}' is out of frame at the {part} of the beat; frame it with "
                                    "studio.frame_all"))
                    continue
                w, h = box[2] - box[0], box[3] - box[1]
                cw = min(1.0, box[2]) - max(0.0, box[0])
                ch = min(1.0, box[3]) - max(0.0, box[1])
                fits = w <= MUST_FITS and h <= MUST_FITS
                if not fits:
                    # scenery bigger than the frame (a river, a 24 m levee): a close shot shows PART of it,
                    # which is right; it only has to fill a real part of the view
                    if max(cw, ch) < MUST_PART:
                        hits.append((f, f"must_see: '{name}' only grazes the frame at the {part} of the beat "
                                        f"({max(cw, ch):.0%} of it in view); turn the camera toward it"))
                elif w * h > 0 and (cw * ch) / (w * h) < MUST_IN:
                    hits.append((f, f"must_see: '{name}' is cut by the frame edge at the {part} of the beat "
                                    f"(only {cw * ch / (w * h):.0%} inside); frame it with studio.frame_all"))
                elif max(cw, ch) < MUST_MIN:
                    hits.append((f, f"must_see: '{name}' is too small at the {part} of the beat ({max(cw, ch):.0%} "
                                    f"of the frame, needs >= {MUST_MIN:.0%}); frame it closer (studio.frame_all)"))
        if hits:
            issues[label] = [{"frames": [f, f], "issue": m} for f, m in hits]
    return issues


def quality(scene, characters, hero, beats, frame_map, fps=30, step=5, out_path=None):
    """The channel's quality gates, per beat (pure geometry, no rendering):
      hero_small   Max (the hero) is under HERO_MIN of the frame height for most of the beat
      hero_absent  Max is not on screen in the beat at all
      static       the camera does not move for > STATIC_SECONDS
      flat         large surfaces in one flat colour (no texture): toy-like, unrecognisable
      text_small   a label's letters are too small to read on a phone
      floating     a character stands on nothing (no surface under the feet, not seated)
      coplanar     two surfaces in the same plane: they flicker (z-fighting)
      squashed     a bumped material on an object squashed > 12x (black/glossy artefacts)
      live_boolean a boolean modifier on/with an animated object (re-meshes every frame: flicker)
    characters: {name: root}; hero: the hero's name prefix (or None); beats: [(label, f0, f1)] timeline frames."""
    cam = scene.camera
    issues = {}
    char_objs = {name: [o for o in [root] + list(root.children_recursive) if o.type == "MESH"]
                 for name, root in characters.items()}
    char_names = {o.name for objs in char_objs.values() for o in objs}
    meshes = [o for o in scene.objects if o.type == "MESH" and o.name not in char_names]
    # ---- scene construction problems (independent of the frame) ----
    for o in meshes:
        chain, p = [o], o.parent
        while p is not None:
            chain.append(p)
            p = p.parent
        animated = any(x.animation_data is not None for x in chain)
        for m in o.modifiers:
            if m.type == "BOOLEAN" and m.show_render and m.object is not None and (
                    animated or m.object.animation_data is not None):
                issues.setdefault("all", []).append({"frames": [0, 0], "issue": (
                    f"live_boolean: {o.name} is cut by {m.object.name} while moving (re-meshes every frame and "
                    "flickers): apply the cut once (studio.carve) or cut in the shader (studio.section_clip)")})
        sc = o.matrix_world.to_scale()
        lo, hi = min(abs(sc.x), abs(sc.y), abs(sc.z)), max(abs(sc.x), abs(sc.y), abs(sc.z))
        if hi > 0 and lo / hi < 1 / 12 and any(
                m is not None and m.use_nodes and any(n.type == "BUMP" for n in m.node_tree.nodes)
                for m in getattr(o.data, "materials", [])):
            issues.setdefault("all", []).append({"frames": [0, 0], "issue": (
                f"squashed: {o.name} is scaled {hi / max(lo, 1e-6):.0f}x thinner on one axis and its material has "
                "bump (renders black/glossy): build it at its real size or use a material without bump")})
    for label, b0, b1 in beats:
        hits = []
        frames = list(range(b0, b1 + 1, step)) or [b0]
        hero_fracs, track, flat_seen, text_seen, float_frames = [], [], {}, {}, {}
        text_big = {}
        for f in frames:
            scene.frame_set(frame_map(f))
            dg = bpy.context.evaluated_depsgraph_get()
            cm = cam.matrix_world
            track.append((f, cm.translation.copy(), (cm.to_3x3() @ Vector((0, 0, -1))).normalized()))
            if hero is not None:                             # "Max" also covers "MaxBoat", "MaxPilot"...
                vis = [o for nm, objs in char_objs.items() if nm.startswith(hero) for o in objs if _visible(o)]
                box = _screen_box(scene, cam, vis) if vis else None
                hero_fracs.append(min(1.0, box[3]) - max(0.0, box[1]) if _on_screen(box) else 0.0)
            for o in meshes:
                if not _visible(o) or _FX.search(o.name):
                    continue
                mats = [m for m in getattr(o.data, "materials", []) if m is not None]
                if mats and not all(_is_flat(m) for m in mats):
                    continue
                box = _screen_box(scene, cam, [o])
                if not _on_screen(box):
                    continue
                centre = sum((Vector(c) for c in _corners(o)), Vector()) / 8
                if (centre - cm.translation).length > FAR:
                    continue
                area = (min(1.0, box[2]) - max(0.0, box[0])) * (min(1.0, box[3]) - max(0.0, box[1]))
                if area > FLAT_AREA:
                    flat_seen[o.name] = max(flat_seen.get(o.name, 0.0), area)
            for o in scene.objects:
                # labels pop in and out (cutaway._pop: ~8 frames): judge them at full size, not mid-pop
                if o.type != "FONT" or not _visible(o) or max(o.matrix_world.to_scale()) < 0.85 or _painted(o):
                    continue
                box = _screen_box(scene, cam, [o])
                if not _on_screen(box):
                    continue
                h = (box[3] - box[1]) / max(1, o.data.body.count("\n") + 1)
                key = o.data.body.strip().replace("\n", " ")[:40]
                if h < TEXT_MIN:
                    text_seen[key] = min(text_seen.get(key, 1.0), h)
                # a label the camera is almost inside: letters filling the frame, or running past both
                # edges (every corner outside the frame, so the crop check never saw it)
                if h > TEXT_MAX or box[0] < -0.02 and box[2] > 1.02:
                    text_big[key] = max(text_big.get(key, 0.0), h)
            for name, objs in char_objs.items():
                vis = [o for o in objs if _visible(o)]
                if not vis:
                    continue
                own = {o.name for o in objs}
                feet = [o for o in vis if re.search(r"shoe|foot|boot", o.name, re.I)] or vis
                low_pts = []
                for o in feet:                                      # real vertices, not rotated bounding boxes
                    ev = o.evaluated_get(dg)
                    me = ev.to_mesh()
                    if me is not None:
                        mw = ev.matrix_world
                        low_pts += [mw @ v.co for v in me.vertices]
                    ev.to_mesh_clear()
                if not low_pts:
                    continue
                low = min(p.z for p in low_pts)
                body = [p for o in vis for p in _corners(o)]
                top = max(p.z for p in body)
                cx, cy = sum(p.x for p in low_pts) / len(low_pts), sum(p.y for p in low_pts) / len(low_pts)
                supported = _support(scene, dg, Vector((cx, cy, low + 0.12)), 0.12 + 0.08, own) or any(
                    _support(scene, dg, Vector((cx + dx, cy + dy, low + 0.12)), 0.2, own)
                    for dx, dy in ((0.1, 0), (-0.1, 0), (0, 0.1), (0, -0.1)))
                if not supported:                                   # seated: something right under the hips
                    supported = _support(scene, dg, Vector((cx, cy, low + (top - low) * 0.42)), 0.6, own)
                if not supported:
                    float_frames.setdefault(name, []).append(f)
        if hero_fracs:
            if max(hero_fracs) == 0:
                hits.append((b0, "hero_absent: Max is never on screen in this beat"))
            elif sum(1 for v in hero_fracs if v >= HERO_MIN) / len(hero_fracs) < HERO_SHARE:
                hits.append((b0, f"hero_small: Max fills at most {max(hero_fracs):.0%} of the frame height (median "
                                 f"{sorted(hero_fracs)[len(hero_fracs) // 2]:.0%}); frame him at >= {HERO_MIN:.0%} "
                                 f"for at least {HERO_SHARE:.0%} of the beat (studio.close_on)"))
        still = _longest_still(track, fps)
        if still > STATIC_SECONDS * fps:
            hits.append((b0, f"static: the camera holds still for {still / fps:.1f} s; keep it moving "
                             "(studio.close_on swing, studio.orbit, push-ins)"))
        for nm, area in sorted(flat_seen.items(), key=lambda kv: -kv[1])[:6]:
            hits.append((b0, f"flat: {nm} is one flat colour over {area:.0%} of the frame; give it a real material "
                             "(engine.textures / engine.studio)"))
        for body, h in text_seen.items():
            hits.append((b0, f"text_small: label '{body}' letters are {h:.1%} of the frame height (need >= "
                             f"{TEXT_MIN:.1%}): enlarge it or bring the camera closer"))
        for body, h in text_big.items():
            hits.append((b0, f"text_big: label '{body}' letters are {h:.0%} of the frame height or run past both "
                             f"frame edges (max {TEXT_MAX:.0%}): size the label from the camera distance"))
        for name, fl in float_frames.items():
            if len(fl) * step >= 10 and len(fl) >= 0.4 * len(frames):        # a jump is fine, standing on air is not
                hits.append((fl[0], f"floating: {name} has no surface under the feet in {len(fl)} of "
                                    f"{len(frames)} sampled frames (from frame {fl[0]})"))
        if hits:
            issues[label] = [{"frames": [f, f], "issue": m} for f, m in hits]
    seen = set()
    for label, b0, b1 in beats:                              # z-fighting, at each beat's end frame
        scene.frame_set(frame_map(b1))
        dg = bpy.context.evaluated_depsgraph_get()
        objs = [o for o in meshes if _visible(o) and not SOFT.search(o.name) and not _FX.search(o.name)]
        for pair in _coplanar_pairs(objs, dg):
            if pair not in seen:
                seen.add(pair)
                issues.setdefault(label, []).append({"frames": [b1, b1], "issue": (
                    f"coplanar: {pair} share a plane and flicker (z-fighting): offset one by >= 5 mm")})
    report = {"beats": issues, "count": sum(len(v) for v in issues.values())}
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    return report
