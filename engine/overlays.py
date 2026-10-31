"""
Floating explanation objects (3D callout labels, magnifier insets) after a set has staged its film, before
any frame renders. Runs inside Blender (engine/films/cutaway_film.py).

  fix_cut(scene, frames)        hides a label / inset on the frames where the camera cuts it at the frame edge
                                (the sandcastle film: the grain inset sliced by the top edge in six close-ups;
                                the oil film: DRILL BIT cut at the right edge). Hidden beats cut, every time.
  unblock(scene, frames)        a label hidden behind scene geometry is pulled in front of it, along the camera ray
                                (same place and size on screen; the water-tower film's LOAD PATH sat behind the legs)
  text_boxes(scene, frames)     where each visible label / inset sits on screen, frame by frame: make_film keeps
                                its 2D stickers off them (the sandcastle film stacked "2 m" on DRY SAND).

A label is a `label_*` empty with its letters parented (engine/sets/plane_story.label, studio.label); an inset
is an `inset_*` empty with its contents parented (studio.Inset). Pure geometry: nothing is rendered.
"""
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from engine import qa, toy

PREFIXES = ("label_", "inset_")
EDGE = 0.01                  # a corner further than this outside the frame = cut
MIN_HIDE = 8                 # frames: shorter hidden runs are stretched, shorter visible gaps between them filled
SWALLOW = 0.6                # cut for more than this share of its visible window: hidden for the whole window


def _roots(scene):
    return [o for o in scene.objects if o.type == "EMPTY" and o.name.startswith(PREFIXES) and o.children]


def _tree(root):
    return [root] + list(root.children_recursive)


def _shown(o):
    """Rendered now: neither it nor a parent is hidden, and it is not popped down to nothing."""
    while o is not None:
        if o.hide_render:
            return False
        o = o.parent
    return True


def _box(scene, cam, root):
    """(x0, y0, x1, y1) in camera-view units (y up) of the root's visible geometry, or None."""
    pts = []
    for o in root.children_recursive:
        if o.type in ("MESH", "FONT", "CURVE") and _shown(o):
            pts += [world_to_camera_view(scene, cam, o.matrix_world @ Vector(c)) for c in o.bound_box]
    pts = [p for p in pts if p.z > 0]
    if not pts:
        return None
    return (min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts))


def _popped(root):
    """A label popping in or out (scale near zero) is not readable text yet."""
    s = root.matrix_world.to_scale()
    return max(abs(s.x), abs(s.y), abs(s.z)) < 0.25


def _cut(box):
    if box is None:
        return False
    x0, y0, x1, y1 = box
    inside = x1 > 0 and x0 < 1 and y1 > 0 and y0 < 1
    outside = x0 < -EDGE or y0 < -EDGE or x1 > 1 + EDGE or y1 > 1 + EDGE
    return inside and outside


def _runs(flags):
    """[(first_index, last_index)] of the True runs in a list of booleans."""
    out, start = [], None
    for i, v in enumerate(flags + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def _smooth(cut, visible):
    """No flicker: fill short visible gaps between hidden runs, stretch short hidden runs, and hide a label
    for its whole window when it would be cut for most of it (never popping in halfway through a beat)."""
    n = len(cut)
    cut = list(cut)
    for a, b in _runs(visible):
        if sum(cut[a:b + 1]) > SWALLOW * (b - a + 1):
            cut[a:b + 1] = [True] * (b - a + 1)
    runs = _runs(cut)
    for (a0, b0), (a1, _b1) in zip(runs, runs[1:]):
        if a1 - b0 - 1 < MIN_HIDE:
            cut[b0 + 1:a1] = [True] * (a1 - b0 - 1)
    for a, b in _runs(cut):
        if b - a + 1 < MIN_HIDE:
            pad = (MIN_HIDE - (b - a + 1) + 1) // 2
            for i in range(max(0, a - pad), min(n, b + pad + 1)):
                cut[i] = True
    return [c and v for c, v in zip(cut, visible)]


def _hide_keys(o, frames, hide):
    """Rewrite o's render/viewport visibility so it is ALSO hidden where hide[i] is True (frames[i]); every
    frame keeps the set's own visibility otherwise. Keys only where the value changes (constant curves)."""
    curves = {fc.data_path: fc for fc in toy.fcurves(o) if fc.data_path in ("hide_render", "hide_viewport")}
    base = [bool(round(curves["hide_render"].evaluate(f))) if "hide_render" in curves else o.hide_render
            for f in frames]
    want = [b or h for b, h in zip(base, hide)]
    if want == base:
        return False
    # the set's own keys outside the sampled frames (an epilogue, frames not rendered here) must survive
    outside = sorted({int(round(kp.co.x)) for fc in curves.values() for kp in fc.keyframe_points}
                     - set(frames))
    keep = {f: bool(round(curves["hide_render"].evaluate(f))) if "hide_render" in curves else o.hide_render
            for f in outside}
    for path in ("hide_render", "hide_viewport"):
        if path in curves:
            for kp in list(curves[path].keyframe_points)[::-1]:
                curves[path].keyframe_points.remove(kp)
    keys = dict(keep)
    prev, last = None, None
    for f, v in zip(frames, want):
        # a key of the set's own between the last sampled frame and this one changes what holds here: key it again
        between = last is not None and any(last < k < f for k in outside)
        if v != prev or between:
            keys[f] = v
            prev = v
        last = f
    for f in sorted(keys):
        o.hide_render = o.hide_viewport = keys[f]
        o.keyframe_insert("hide_render", frame=f)
        o.keyframe_insert("hide_viewport", frame=f)
    for fc in toy.fcurves(o):
        if fc.data_path in ("hide_render", "hide_viewport"):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    return True


def _segments(frames):
    """Split a sorted frame list into contiguous runs (the build, the epilogue hook): smoothing never bridges
    a jump between two parts of the timeline."""
    out, cur = [], []
    for f in frames:
        if cur and f != cur[-1] + 1:
            out.append(cur)
            cur = []
        cur.append(f)
    if cur:
        out.append(cur)
    return out


def _image_box(b):
    """Camera-view box (y up) -> image units (y down), clipped to what is on screen; None when off screen."""
    if not b or b[2] <= 0 or b[0] >= 1 or b[3] <= 0 or b[1] >= 1:
        return None
    return [round(max(0.0, b[0]), 3), round(max(0.0, 1 - b[3]), 3), round(min(1.0, b[2]), 3),
            round(min(1.0, 1 - b[1]), 3)]


UNBLOCK = True               # labels hidden behind scene geometry: pulled in front (static) or hidden (moving)
BLOCKED = 0.3                # this share of a label's letters behind scene geometry = hidden by it
CLEAR = 0.3                  # a pulled label stops this far (m) in front of what blocked it


def _letters(root):
    return [o for o in root.children_recursive if o.type in ("FONT", "MESH", "CURVE") and _shown(o)]


def _blocked(scene, depsgraph, cam_pos, root):
    """(share of the label's letters hidden behind other geometry, nearest blocking distance or None)."""
    mine = set(_tree(root))
    letters = _letters(root)
    hits, near = 0, None
    for o in letters:
        p = o.matrix_world @ (sum((Vector(c) for c in o.bound_box), Vector()) / 8)
        d = p - cam_pos
        dist = d.length
        if dist < 1e-3:
            continue
        origin = cam_pos
        for _ in range(4):                                   # skip the label's own letters and see-through parts
            ok, loc, _n, _i, ob, _m = scene.ray_cast(depsgraph, origin, d.normalized(), distance=dist - 0.02
                                                     - (origin - cam_pos).length)
            if not ok:
                break
            ob = getattr(ob, "original", ob)
            if ob in mine or qa._see_through(ob):          # water, glass, cutaway clips: the label reads through
                origin = loc + d.normalized() * 0.01
                continue
            hits += 1
            h = (loc - cam_pos).length
            near = h if near is None else min(near, h)
            break
    return (hits / len(letters) if letters else 0.0), near


def _pull(root, cam_pos, near, log):
    """Bring a static label in front of what blocks it: along the camera ray, scaled by the same ratio, so it keeps
    its place and size on screen (the water-tower film's LOAD PATH sat behind the tower's legs and arrows)."""
    if any(fc.data_path == "location" for fc in toy.fcurves(root)):
        return False
    loc = root.matrix_world.to_translation()
    dist = (loc - cam_pos).length
    k = max(0.2, (near - CLEAR) / dist) if dist > 1e-3 else 1.0
    if k >= 0.98:
        return False
    world = cam_pos + (loc - cam_pos) * k
    root.location = (root.parent.matrix_world.inverted() @ world) if root.parent else world
    scales = [fc for fc in toy.fcurves(root) if fc.data_path == "scale"]
    if scales:
        for fc in scales:
            for kp in fc.keyframe_points:
                kp.co.y *= k
                kp.handle_left.y *= k
                kp.handle_right.y *= k
    else:
        root.scale = tuple(s * k for s in root.scale)
    log(f"overlays: pulled {root.name} {dist - dist * k:.1f} m toward the camera, in front of what hid it")
    return True


def unblock(scene, frames, step=6, log=print):
    """Labels / insets that scene geometry hides (BLOCKED share of their letters behind it on the frames they show):
    a static one is pulled in front; a moving one is hidden on those frames like a cut one. Returns
    {root name: frames hidden} for the moving ones (settle() hides them)."""
    roots = _roots(scene)
    if not roots or not frames:
        return {}
    frames = sorted(set(frames))
    worst = {}
    for f in frames[::step]:
        scene.frame_set(f)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        cam_pos = scene.camera.matrix_world.to_translation()
        for r in roots:
            if not _shown(r) or _popped(r):
                continue
            box = _box(scene, scene.camera, r)
            if box is None or box[2] <= 0 or box[0] >= 1 or box[3] <= 0 or box[1] >= 1:
                continue
            share, near = _blocked(scene, depsgraph, cam_pos, r)
            if share >= BLOCKED and near is not None:
                w = worst.setdefault(r.name, {"frames": [], "near": near, "cam": cam_pos.copy()})
                w["frames"].append(f)
                if near < w["near"]:
                    w["near"], w["cam"] = near, cam_pos.copy()
    moving = {}
    for name, w in worst.items():
        r = scene.objects[name]
        if not _pull(r, w["cam"], w["near"], log):
            moving[name] = w["frames"]
    return moving


def settle(scene, frames, step=2, log=print):
    """Hide every label / inset on the frames where it is cut by the frame edge, and measure where the readable
    ones sit. frames: the SCENE frames that will be rendered. Returns ({root name: hidden frame count},
    {scene frame: [[x0, y0, x1, y1] image units, ...]} for the measured frames)."""
    roots = _roots(scene)
    if not roots or not frames:
        return {}, {}
    frames = sorted(set(frames))
    blocked = unblock(scene, frames, log=log) if UNBLOCK else {}
    cam = scene.camera
    cut = {r.name: [] for r in roots}
    vis = {r.name: [] for r in roots}
    boxes = {r.name: [] for r in roots}
    measured = []
    last = {}
    for k, f in enumerate(frames):
        # every `step`-th frame is measured (frame_set is the cost); the frames between hold that answer
        if k % step == 0 or k == len(frames) - 1 or frames[k - 1] != f - 1:
            scene.frame_set(f)
            measured.append(k)
            last = {}
            for r in roots:
                on = _shown(r) and not _popped(r)
                b = _box(scene, cam, r) if on else None
                last[r.name] = (on, on and _cut(b), _image_box(b) if on else None)
        for r in roots:
            hid = any(abs(f - g) <= 3 for g in blocked.get(r.name, ()))    # (unblock samples every 6th frame)
            vis[r.name].append(last[r.name][0])
            cut[r.name].append(last[r.name][1] or (last[r.name][0] and hid))
            boxes[r.name].append(last[r.name][2])
    done, hidden = {}, {}
    for r in roots:
        hide = []
        i = 0
        for seg in _segments(frames):
            n = len(seg)
            hide += _smooth(cut[r.name][i:i + n], vis[r.name][i:i + n])
            i += n
        hidden[r.name] = hide
        if not any(hide):
            continue
        for o in _tree(r):
            _hide_keys(o, frames, hide)
        done[r.name] = sum(hide)
    if done:
        log(f"overlays: hid {len(done)} label(s)/inset(s) where the camera cuts them at the frame edge: "
            + ", ".join(f"{k} ({v} f)" for k, v in sorted(done.items())))
    out = {}
    for k in measured:
        here = [boxes[r.name][k] for r in roots
                if vis[r.name][k] and not hidden[r.name][k] and boxes[r.name][k]]
        if here:
            out[frames[k]] = here
    return done, out
