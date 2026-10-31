"""
Parametric toy-figurine characters with a joint rig and an animation library.

A character is built from rounded parts parented to joint empties (hips, spine,
neck, head, shoulders, legs). Identity is fixed by its `look` (colours, hat,
hair, mustache), so the same character is identical in every shot. Animation is
keyframed joint rotation: walk, wave, cheer, point, dig, hammer, talk, blink,
look-around, and idle breathing.
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Vector

from engine import events, textures as tx, toy

DEFAULT_LOOK = {
    "skin": "#F2B48C",
    "shirt": "#F5C542",
    "overalls": "#2F6FD6",
    "shoes": "#5A3A22",
    "hat": "#FF7A00",        # None for no hat
    "hair": "#5B3A1E",
    "mustache": True,
    "eyes": "#3B2412",
    "scale": 1.0,
}

R = math.radians


def _arc(name, radius, thickness, mat, parent, location, upper=False, span=1.0):
    """A curved stroke (half a torus): a "U" smile, or with upper=True an arched brow. Straight capsules read
    as a frown or a shout on a small face; curves read as a smile / friendly brows."""
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=thickness, major_segments=32,
                                     minor_segments=10, rotation=(math.pi / 2, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    bpy.ops.object.transform_apply(rotation=True)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    cut = radius * (1 - span) - 1e-4
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.co.z < -cut if upper else v.co.z > cut)],
                     context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.location = location
    return toy._finish(obj, mat, subdiv=1, parent=parent)


def _hair_shell(name, radius, mat, parent, location, front=0.19, side=0.02, back=-0.16):
    """Hair that HUGS the head: a sphere just bigger than the skull, cut by a slanted hairline (high at the
    forehead so it shows, low at the nape), covering the crown and the sides. A hair cap slid back to free
    the forehead stood out from the head."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=96, ring_count=48)   # fine: a smooth hairline
    obj = bpy.context.active_object
    obj.name = name
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    def line(v):
        # hairline height (local z) by DIRECTION around the head: front high, sides low, back lowest.
        # (By y/radius the line barely moved: the sphere narrows toward the top.)
        k = v.co.y / max(1e-6, math.hypot(v.co.x, v.co.y))
        return side + (front - side) * max(0.0, -k) ** 0.7 + (back - side) * max(0.0, k)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < line(v)], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.location = location
    sol = obj.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.025
    return toy._finish(obj, mat, subdiv=2, parent=parent)


def _smile(name, mat, tongue_mat, parent, location, width=0.06):
    """A filled cartoon smile: a dark half-moon (flat top, round bottom) with a little pink tongue. Thin
    strokes on a small face read as a line or a ring."""
    import bmesh as _bm
    bpy.ops.mesh.primitive_cylinder_add(radius=width, depth=0.03, vertices=40, rotation=(math.pi / 2, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    bpy.ops.object.transform_apply(rotation=True)
    bm = _bm.new()
    bm.from_mesh(obj.data)
    _bm.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 0, 1),
                         clear_outer=True)
    _bm.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bm.to_mesh(obj.data)
    bm.free()
    obj.location = location
    obj.scale = (1.15, 1.0, 0.85)
    mouth = toy._finish(obj, mat, subdiv=1, parent=parent)
    tongue = toy.sphere(f"{name}_tongue", width * 0.45, (0, -0.006, -width * 0.55), scale=(1.3, 0.5, 0.7),
                        mat=tongue_mat, parent=mouth, subdiv=1)
    tongue.name = f"{name}_tongue"
    return mouth


def _half_sphere(name, radius, mat, parent, location, scale=(1, 1, 1)):
    """Dome (top half of a sphere) — hard hats, hair caps."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=32, ring_count=16)
    obj = bpy.context.active_object
    obj.name = name
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -1e-4], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.location = location
    obj.scale = scale
    sol = obj.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.03
    return toy._finish(obj, mat, subdiv=2, parent=parent)


HAND_MARGIN = 6       # frames a motion-capture clip keeps away from a hand-keyed joint (it blends in and out)
HAND_GAP = 24         # hand keys closer than this on one joint are one gesture (the clip stays out in between)
LIMB_CHILD = {"elbowL": "shoulderL", "elbowR": "shoulderR", "kneeL": "legL", "kneeR": "legR"}


LOW_CLIPS = {"fix", "crouch", "sneak", "push", "pick_up", "plant", "harvest", "water", "open_chest", "roll"}
CLOSE_FRAC = 0.33     # a character this tall on screen (share of the frame height) is in a close shot
HEIGHT = 1.9          # a scale-1 character's height (m)


def _camera_at(scene, f):
    """(camera position, unit view direction, vertical field of view) at frame f, from the animation curves (no
    frame_set). The view direction follows a TRACK_TO target (engine/camera.CameraRig aims through one)."""
    cam = scene.camera
    pos = toy.world_location_at(cam, f)
    target = next((c.target for c in cam.constraints if c.type == "TRACK_TO" and c.target and not c.mute), None)
    if target is not None:
        view = toy.world_location_at(target, f) - pos
    else:
        view = toy.world_matrix_at(cam, f).to_3x3() @ Vector((0, 0, -1))
    lens = next((fc.evaluate(f) for fc in toy.fcurves(cam.data) if fc.data_path == "lens"), cam.data.lens)
    r = scene.render
    tall = r.resolution_y >= r.resolution_x               # sensor_fit AUTO: the sensor spans the longer side
    span = cam.data.sensor_width * (1.0 if tall else r.resolution_y / max(1, r.resolution_x))
    return pos, view.normalized() if view.length > 1e-6 else Vector((0, 1, 0)), 2 * math.atan(span / (2 * lens))


def screen_share(scene, ch, f):
    """How tall `ch` stands on screen at frame f (share of the frame height), 0 when off screen."""
    pos, view, fov = _camera_at(scene, f)
    h = HEIGHT * ch.look["scale"]
    head = toy.world_location_at(ch.root, f) + Vector((0, 0, 0.75 * h))
    d = head - pos
    depth = d.dot(view)
    if depth <= 0.05:
        return 0.0
    right = view.cross(Vector((0, 0, 1)))
    right = right.normalized() if right.length > 1e-6 else Vector((1, 0, 0))
    up = right.cross(view)
    r = bpy.context.scene.render
    half_y = math.tan(fov / 2)
    half_x = half_y * r.resolution_x / max(1, r.resolution_y)
    if abs(d.dot(right) / depth) > half_x * 1.1 or abs(d.dot(up) / depth) > half_y * 1.1:
        return 0.0
    return h / depth / (2 * half_y)


def upright_close_ups(scene=None, log=print, step=2, gap=8, pad=4):
    """A kneeling / bending clip in a close shot of that character films the top of his hat from centimetres away
    (the flood-house film opened four beats on a giant orange hat: the close camera aims at standing head height
    while 'fix' kneels him toward it; the water-tower film laid Max flat over a footing with 'crouch'). Before the
    clips play, the frames of such a clip where the camera is close on its character get the upright talk clip
    instead (later calls win the frames they share). Returns {character: frames swapped}."""
    scene = scene or bpy.context.scene
    if scene.camera is None:
        return {}
    done = {}
    for ch in Character.cast:
        add = []
        for clip, a, b, _sp, _fb, _walk in list(ch._queue):
            if clip not in LOW_CLIPS or b <= a:
                continue
            close = [f for f in range(a, b + 1, step) if screen_share(scene, ch, f) >= CLOSE_FRAC]
            runs = []
            for f in close:
                if runs and f - runs[-1][1] <= gap:
                    runs[-1][1] = f
                else:
                    runs.append([f, f])
            add += [(max(a, r0 - pad), min(b, r1 + pad)) for r0, r1 in runs]
        for r0, r1 in add:
            ch._queue.append(("talk", r0, r1, 1.0, None, None))
        if add:
            done[ch.name] = sum(r1 - r0 + 1 for r0, r1 in add)
    if done:
        log("close shots: kneeling/bending clips swapped for an upright one while the camera is close: "
            + ", ".join(f"{k} ({v} f)" for k, v in sorted(done.items())))
    return done


def perform_queued():
    """Play every character's queued motion capture (act / idle / talk / walk), once the whole scene is keyed:
    engine/films/cutaway_film.py calls it after the set has animated every beat (and built its camera)."""
    if os.getenv("CLOSE_UPRIGHT", "1") == "1":
        try:
            upright_close_ups()
        except Exception as exc:                           # noqa: BLE001  a guard, never a crash
            print(f"close shots: upright guard skipped ({exc})")
    for ch in Character.cast:
        ch._perform_queue()
    Character.cast.clear()


class Character:
    cast = []         # every character built in this Blender session (perform_queued plays their clips)

    def __init__(self, name: str, look: dict = None, location=(0, 0, 0), facing_deg=0.0):
        self.name = name
        self.look = {**DEFAULT_LOOK, **(look or {})}
        self.j = {}
        self._build()
        self.root.location = location
        self.root.rotation_euler = (0, 0, R(facing_deg))
        self.root.scale = (self.look["scale"],) * 3
        self.held = None
        self._queue = []
        Character.cast.append(self)

    # ------------------- MOTION CAPTURE -------------------

    def act(self, clip: str, start: int, end: int, speed: float = 1.0, fallback=None, _walk=None):
        """The whole body plays a motion-capture clip (engine/mocap.py, Quaternius CC0) from start to end: a
        meaning from mocap.CLIPS ("idle", "talk", "yes", "no", "fold_arms", "jump", "dance", "knocked", "fall",
        "get_up", "push", "pick_up", "interact", "throw", "fix", "crouch", "walk", "jog", "run") or a library
        clip name. Real motion instead of hand-keyed poses (the tunnel film's raw pose keys read as stiff).
        Work clips (pick_up, water, interact, fix, plant, throw) REPEAT over a range longer than the clip (scooping
        again and again); reactions (yes, no, fall, knocked, jump) play once and hold their end pose.
        Queued and played after the whole scene is keyed: hand keys on a joint (a point, a hammer stroke, a
        look_at) keep that joint, and the clip blends around them. Later calls win the frames they share with
        earlier ones. fallback() keys the old hand animation when the library or the clip is missing."""
        self._queue.append((clip, int(start), int(end), speed, fallback, _walk))

    def _hand_keyed(self):
        """{joint: [(f0, f1)]}: frames keyed by hand on each joint (any key, however it was made)."""
        from engine.mocap import JOINTS, _fcurves
        out = {}
        for j in JOINTS:
            ob = self.j.get(j)
            ad = ob.animation_data if ob is not None else None
            if ad is None or ad.action is None:
                continue
            frames = sorted({int(round(kp.co.x)) for fc in _fcurves(ad.action)
                             if fc.data_path in ("rotation_euler", "location") for kp in fc.keyframe_points})
            spans = []
            for f in frames:
                if spans and f - spans[-1][1] <= HAND_GAP:
                    spans[-1][1] = f
                else:
                    spans.append([f, f])
            out[j] = [(a - HAND_MARGIN, b + HAND_MARGIN) for a, b in spans]
        return out

    def _perform_queue(self):
        if not self._queue:
            return
        try:
            from engine.mocap import Mocap
            mc = Mocap() if os.getenv("CUT_MOCAP", "1") != "0" else None     # CUT_MOCAP=0: hand animation only
            ok = mc is not None and mc.available()
        except Exception:                                  # noqa: BLE001  no library: the hand animation plays
            mc, ok = None, False
        hand = self._hand_keyed() if ok else {}
        segs = []
        for clip, a, b, speed, fallback, walk in self._queue:
            if ok and mc.clip(clip) is not None and b > a:
                if walk:                                   # the clip's own stride at this root speed: no sliding
                    natural = mc.ground_speed(clip, 0.56 * self.look["scale"])
                    if natural > 0:
                        speed = min(2.0, max(0.5, walk / ((b - a) / 30) / natural))
                segs.append((clip, a, b, speed))
            elif fallback is not None:
                fallback()
        self._queue = []
        if not segs:
            return
        lo, hi = min(s[1] for s in segs), max(s[2] for s in segs)
        owner = [-1] * (hi - lo + 1)
        for i, (_c, a, b, _sp) in enumerate(segs):         # a later call wins the frames it shares
            owner[a - lo:b - lo + 1] = [i] * (b - a + 1)
        runs, f = [], lo
        while f <= hi:
            i, g = owner[f - lo], f
            while g + 1 <= hi and owner[g + 1 - lo] == i:
                g += 1
            if i >= 0:
                clip, a, _b, sp = segs[i]
                runs.append((clip, f, g, sp, a))           # (the clip keeps its phase across an interruption)
            f = g + 1

        # A hand-keyed shoulder (or hip) is a straight-limb pose: the clip must not bend the elbow (or knee) under
        # it. With the idle clip folding the elbow under a hand-raised arm, the sandcastle's bucket ended up in
        # front of Max's face instead of over the tower. The child joint rests straight through the gesture.
        straight = {}
        for child, parent in LIMB_CHILD.items():
            if parent in hand and child in self.j:
                own = hand.get(child, [])
                spans = [(a, b) for a, b in hand[parent] if not any(x <= b and a <= y for x, y in own)]
                if spans:
                    hand[child] = own + spans
                    straight[child] = spans

        def skip(joint, frame):
            return any(a <= frame <= b for a, b in hand.get(joint, ()))

        # Outside its frames a clip must leave no trace: its last key would otherwise hold for the rest of the
        # film (the tunnel's Max carried the end of a talk gesture, right foot forward and down, into every
        # later beat, through roofs and hulls). Key each joint's own pose BLEND frames before and after every
        # clip, so the clip blends in and out of whatever the scene had there.
        from engine.mocap import BLEND, JOINTS
        scene = bpy.context.scene
        now = scene.frame_current
        covered = [(a, b) for _c, a, b, _s, _o in runs]
        edges = sorted({f for a, b in covered for f in (a - BLEND, b + BLEND)
                        if f >= 0 and not any(x <= f <= y for x, y in covered)})
        held = {}
        for f in edges:
            scene.frame_set(f)
            held[f] = {j: (self.j[j].rotation_euler.copy(), self.j[j].location.copy()) for j in JOINTS if j in self.j}
        scene.frame_set(now)
        mc.perform(self, runs, hips_height=0.56, skip=skip)
        for child, spans in straight.items():           # straight through the gesture (blends at its margins)
            ob = self.j[child]
            for a, b in spans:
                for f in (a + HAND_MARGIN, b - HAND_MARGIN):
                    ob.rotation_euler = self.rest[child]
                    ob.keyframe_insert("rotation_euler", frame=f)
        for f, pose in held.items():
            for j, (rot, loc) in pose.items():
                ob = self.j[j]
                ob.rotation_euler = rot
                ob.keyframe_insert("rotation_euler", frame=f)
                if j == "hips":
                    ob.location = loc
                    ob.keyframe_insert("location", frame=f)

    # ------------------- BUILD -------------------

    def _mat(self, key, hex_color, **kw):
        return toy.material(f"{self.name}_{key}", toy.srgb(hex_color), **kw)

    def _build(self):
        L = self.look
        skin = self._mat("skin", L["skin"], roughness=0.5, subsurface=0.15)
        shirt = tx.cloth(f"{self.name}_shirt", L["shirt"], rough=0.78)
        overalls = tx.cloth(f"{self.name}_overalls", L["overalls"], rough=0.72)
        shoes = self._mat("shoes", L["shoes"], roughness=0.5, coat=0.3)
        hair = self._mat("hair", L["hair"], roughness=0.6)
        dark = toy.material("eye_dark", toy.srgb(L["eyes"]), roughness=0.15, coat=1.0)
        white = toy.material("eye_white", (0.92, 0.92, 0.9), roughness=0.35, coat=0.25)
        mouth_mat = toy.material("mouth", toy.srgb("#5C1F1F"), roughness=0.4)

        n = self.name
        self.root = toy.empty(f"{n}_root")
        hips = self.j["hips"] = toy.empty(f"{n}_hips", (0, 0, 0.56), self.root)
        # Secondary-motion layers: noise-driven sway that runs underneath every action,
        # so a character is never frozen and actions never fight the idle motion.
        sway = toy.empty(f"{n}_sway", (0, 0, 0), hips)
        spine = self.j["spine"] = toy.empty(f"{n}_spine", (0, 0, 0.02), sway)

        # Torso: shirt body + overall bib + straps + belt line.
        toy.capsule(f"{n}_torso", 0.24, 0.22, (0, 0, 0.3), mat=shirt, parent=spine).scale = (1.0, 0.82, 1.0)
        toy.capsule(f"{n}_pants_top", 0.245, 0.06, (0, 0, 0.1), mat=overalls, parent=spine).scale = (1.0, 0.84, 0.9)
        toy.box(f"{n}_bib", (0.26, 0.06, 0.24), (0, -0.19, 0.27), mat=overalls, parent=spine, bevel=0.03)
        for side in (-1, 1):
            toy.box(f"{n}_strap{side}", (0.05, 0.03, 0.3), (0.09 * side, -0.17, 0.42),
                    mat=overalls, parent=spine, bevel=0.012,
                    rotation=(R(-12), 0, 0))
            toy.sphere(f"{n}_button{side}", 0.022, (0.09 * side, -0.225, 0.37),
                       mat=toy.material("brass", toy.srgb("#E8C35A"), roughness=0.25, metallic=1.0),
                       parent=spine, subdiv=1)

        # Head.
        nsway = toy.empty(f"{n}_nsway", (0, 0, 0.56), spine)
        neck = self.j["neck"] = toy.empty(f"{n}_neck", (0, 0, 0.0), nsway)
        head = self.j["head"] = toy.empty(f"{n}_head", (0, 0, 0.0), neck)
        hc = (0, 0, 0.3)
        # Slightly pear-shaped head: full cheeks, narrower crown.
        toy.sphere(f"{n}_skull", 0.31, hc, scale=(1.0, 0.95, 0.98), mat=skin, parent=head)
        for side in (-1, 1):
            toy.sphere(f"{n}_cheek{side}", 0.15, (0.13 * side, -0.14, 0.2), mat=skin, parent=head)
        iris = toy.material(f"{n}_iris", toy.srgb(L.get("iris", "#7A4A1C")), roughness=0.2, coat=1.0)
        for side in (-1, 1):
            toy.sphere(f"{n}_ear{side}", 0.07, (0.3 * side, 0.0, 0.29), scale=(0.5, 0.8, 1.0),
                       mat=skin, parent=head)
            # Big, slightly tall Pixar-style eyes: white, coloured iris, pupil, two glints.
            es = L.get("eye_scale", 1.0)          # kids: bigger eyes (blinks key the scale, not the radius)
            eye = toy.sphere(f"{n}_eye{side}", 0.1 * es, ((0.125 + 0.03 * (es - 1)) * side, -0.235, 0.35),
                             scale=(0.95, 0.6, 1.12), mat=white, parent=head, segments=32, rings=16)
            self.j[f"eye{side}"] = eye
            kid = bool(L.get("hair_style"))
            # the iris keeps its size in a bigger kid eye: more white around it reads young, not goggly
            ir = toy.sphere(f"{n}_iris{side}", 0.062, (-0.008 * side, -0.086 * es, -0.005),
                            scale=(1.0, 0.45, 1.05), mat=iris, parent=eye, subdiv=1)
            pupil = toy.sphere(f"{n}_pupil{side}", 0.034, (0, -0.02, 0), scale=(1.0, 0.6, 1.05),
                               mat=dark, parent=ir, subdiv=1)
            glint = toy.material("glint", (1, 1, 1), roughness=0.0)
            g = 1.35 if kid else 1.0
            toy.sphere(f"{n}_glint{side}", 0.016 * g, (0.022, -0.028, 0.03), mat=glint, parent=pupil, subdiv=0)
            toy.sphere(f"{n}_glint2{side}", 0.008 * g, (-0.02, -0.028, -0.025), mat=glint, parent=pupil, subdiv=0)
            brow_z = 0.495 + 0.112 * (es - 1)            # above the eye, however big it is
            if kid:      # an arched brow: a straight bar read as a frown at any angle
                brow = _arc(f"{n}_brow{side}", 0.05, 0.011, hair, head, (0.135 * side, -0.262, 0.35 + 0.112 * es + 0.005),
                            upper=True, span=0.55)
            else:
                brow = toy.capsule(f"{n}_brow{side}", 0.03, 0.11, (0.13 * side, -0.25, brow_z),
                                   rotation=(0, R(90 + 14 * side), 0), mat=hair, parent=head)
                brow.scale = (0.8, 0.7, 1.0)
            self.j[f"brow{side}"] = brow
        toy.sphere(f"{n}_nose", 0.072 * L.get("nose", 1.0), (0, -0.315, 0.255), scale=(1.0, 0.9, 0.85),
                   mat=self._mat("nose", L["skin"], roughness=0.45, subsurface=0.2), parent=head)
        if L.get("hair_style"):   # a kid smiles: a filled half-moon (a capsule read as a line or a scream)
            tongue = toy.material(f"{n}_tongue", toy.srgb("#FF7F8A"), roughness=0.45)
            mouth = _smile(f"{n}_mouth", mouth_mat, tongue, head, (0, -0.272, 0.175))
        else:
            mouth = toy.capsule(f"{n}_mouth", 0.03, 0.07, (0, -0.27, 0.14), rotation=(0, R(90), 0),
                                mat=mouth_mat, parent=head)
            mouth.scale = (0.7, 0.6, 1.0)
        self.j["mouth"] = mouth
        if L["mustache"]:
            for side in (-1, 1):
                toy.capsule(f"{n}_stache{side}", 0.045, 0.1, (0.075 * side, -0.3, 0.2),
                            rotation=(R(10), R(90 + 22 * side), 0), mat=hair, parent=head)
        if L["hat"]:
            hat = self._mat("hat", L["hat"], roughness=0.25, coat=0.8)
            # Hard hat: dome sitting high on the head, a wide brim with a longer front peak.
            _half_sphere(f"{n}_hat", 0.335, hat, head, (0, 0.01, 0.47), scale=(1.0, 1.05, 0.85))
            brim = toy.cylinder(f"{n}_brim", 0.37, 0.03, (0, -0.035, 0.475), mat=hat, parent=head,
                                vertices=48, bevel=0.012)
            brim.scale = (1.0, 1.13, 1.0)  # longer at the front, like a real hard hat
            for side in (-1, 1):
                toy.sphere(f"{n}_sideburn{side}", 0.06, (0.285 * side, -0.02, 0.4),
                           scale=(0.5, 0.9, 1.0), mat=hair, parent=head)
        elif L.get("hair_style"):   # kids: hair that hugs the skull, hairline above the brows (a forehead)
            _hair_shell(f"{n}_hair", 0.33, hair, head, hc, front=0.27, side=0.03, back=-0.17)
        else:
            _half_sphere(f"{n}_hair", 0.325, hair, head, (0, 0.02, 0.32), scale=(1.0, 1.0, 1.0))
        if L.get("ponytail"):
            toy.sphere(f"{n}_ponytail", 0.11, (0, 0.33, 0.3), scale=(0.8, 1.0, 1.4), mat=hair, parent=head)
        self._kid_features(head, hair)

        # Arms: shoulder + elbow joints (motion capture bends both; at rest the arm is the same straight
        # limb as before), sleeve + upper arm, forearm + hand.
        for side, key in ((-1, "R"), (1, "L")):
            sh = self.j[f"shoulder{key}"] = toy.empty(f"{n}_shoulder{key}", (0.27 * side, 0, 0.47), spine)
            toy.sphere(f"{n}_sleeve{key}", 0.085, (0, 0, -0.02), mat=shirt, parent=sh)
            toy.capsule(f"{n}_arm{key}", 0.068, 0.12, (0, 0, -0.1), mat=skin, parent=sh)
            el = self.j[f"elbow{key}"] = toy.empty(f"{n}_elbow{key}", (0, 0, -0.17), sh)
            toy.capsule(f"{n}_forearm{key}", 0.066, 0.12, (0, 0, -0.07), mat=skin, parent=el)
            hand = toy.sphere(f"{n}_hand{key}", 0.085, (0, -0.01, -0.19), scale=(0.9, 0.8, 1.0),
                              mat=skin, parent=el)
            toy.capsule(f"{n}_thumb{key}", 0.03, 0.05, (-0.055 * side, -0.05, -0.16),
                        rotation=(R(-30), R(-35 * side), 0), mat=skin, parent=el)
            self.j[f"hand{key}"] = toy.empty(f"{n}_grip{key}", (0, -0.03, -0.21), el)
            hand.name = f"{n}_handmesh{key}"

        # Legs: hip + knee joints, pant leg (thigh, shin) + shoe.
        for side, key in ((-1, "R"), (1, "L")):
            hp = self.j[f"leg{key}"] = toy.empty(f"{n}_leg{key}", (0.115 * side, 0, 0.0), hips)
            toy.capsule(f"{n}_pantleg{key}", 0.1, 0.14, (0, 0, -0.15), mat=overalls, parent=hp)
            kn = self.j[f"knee{key}"] = toy.empty(f"{n}_knee{key}", (0, 0, -0.27), hp)
            toy.capsule(f"{n}_shin{key}", 0.095, 0.12, (0, 0, -0.08), mat=overalls, parent=kn)
            toy.box(f"{n}_shoe{key}", (0.19, 0.27, 0.12), (0, -0.04, -0.23), mat=shoes, parent=kn,
                    bevel=0.05)
        seed = sum(map(ord, n))
        toy.add_noise(sway, "rotation_euler", 0, strength=0.035, scale=55, phase=seed)
        toy.add_noise(sway, "rotation_euler", 1, strength=0.025, scale=70, phase=seed + 3)
        toy.add_noise(nsway, "rotation_euler", 0, strength=0.06, scale=45, phase=seed + 7)
        toy.add_noise(nsway, "rotation_euler", 2, strength=0.09, scale=60, phase=seed + 11)
        self.rest = {k: tuple(o.rotation_euler) for k, o in self.j.items()}
        self.rest_loc = {k: tuple(o.location) for k, o in self.j.items()}

    def _kid_features(self, head, hair):
        """Optional look keys that make a child read as a child, not a small Max (the defaults change nothing):
        head_scale  rounder, bigger head      blush  rosy cheeks
        hair_style  "pigtails" (two bunches with ties) | "tuft" (messy cowlick); also arched brows, a "U"
                    smile and bigger glints (see _build)"""
        L, n = self.look, self.name
        if L.get("head_scale", 1.0) != 1.0:
            head.scale = (L["head_scale"],) * 3
        if L.get("blush"):
            pink = toy.material(f"{n}_blush", toy.srgb("#FF8C9E"), roughness=0.6)
            for side in (-1, 1):
                toy.sphere(f"{n}_blush{side}", 0.055, (0.175 * side, -0.25, 0.215), scale=(1.0, 0.35, 0.62),
                           mat=pink, parent=head, subdiv=1)
        style = L.get("hair_style")     # (no fringe: on the round cap it read as a hat ridge or a visor)
        if style == "pigtails":
            tie = toy.material(f"{n}_tie", toy.srgb(L.get("tie", "#FFD23F")), roughness=0.35, coat=0.5)
            for side in (-1, 1):
                toy.sphere(f"{n}_bunch{side}", 0.12, (0.36 * side, 0.08, 0.36), scale=(0.75, 0.8, 1.15),
                           mat=hair, parent=head)
                toy.sphere(f"{n}_tie{side}", 0.045, (0.3 * side, 0.06, 0.42), mat=tie, parent=head, subdiv=1)
        elif style == "tuft":
            for k, (x, tilt) in enumerate(((-0.05, -25), (0.04, 15), (0.0, -5))):
                toy.capsule(f"{n}_tuft{k}", 0.035, 0.12, (x, 0.03, 0.65), rotation=(R(-20), R(tilt), 0),
                            mat=hair, parent=head)

    # ------------------- KEYFRAME HELPERS -------------------

    def key(self, joint: str, frame: int, rot_deg=None, loc=None, scale=None):
        o = self.j[joint] if joint != "root" else self.root
        if rot_deg is not None:
            o.rotation_euler = [R(a) for a in rot_deg]
            o.keyframe_insert("rotation_euler", frame=frame)
        if loc is not None:
            o.location = loc
            o.keyframe_insert("location", frame=frame)
        if scale is not None:
            o.scale = scale
            o.keyframe_insert("scale", frame=frame)

    def pose(self, frame: int, **joints):
        """pose(f, shoulderL=(x,y,z), legR=(...), ...) — rotations in degrees; missing joints = rest."""
        for name in ("hips", "spine", "neck", "head", "shoulderL", "shoulderR", "legL", "legR"):
            rot = joints.get(name, tuple(math.degrees(a) for a in self.rest[name]))
            self.key(name, frame, rot_deg=rot)

    def turn(self, start: int, facing_deg: float, frames: int = 8):
        """Smoothly rotate to a new facing (no snapping)."""
        toy.key_hold(self.root, "rotation_euler", start)
        self.root.rotation_euler = (0, 0, R(facing_deg))
        self.root.keyframe_insert("rotation_euler", frame=start + frames)

    def move(self, start: int, end: int, to):
        """Glide the root (e.g. a slide or jump arc segment) with eased timing."""
        toy.key_hold(self.root, "location", start)
        self.root.location = to
        self.root.keyframe_insert("location", frame=end)

    def lipsync(self, start: int, end: int, envelope: list):
        """Mouth opens with the voice loudness (envelope = per-frame 0..1 from the voiceover)."""
        for f in range(start, end + 1, 2):
            v = envelope[f - 1] if 0 <= f - 1 < len(envelope) else 0.0
            self.key("mouth", f, scale=(0.85 + 0.35 * v, 0.6, 1.0 + 1.9 * v))
        self.key("mouth", end + 2, scale=(0.7, 0.6, 1.0))

    def brows(self, frame: int, up: float = 0.0):
        """Raise (+) or furrow (-) the eyebrows — surprise, emphasis."""
        for side in (-1, 1):
            b = self.j[f"brow{side}"]
            b.location.z = 0.495 + 0.04 * up
            b.keyframe_insert("location", index=2, frame=frame)

    def cut_place(self, frame: int, location, facing_deg: float):
        """Reposition at a camera cut: hold the old spot until the cut, then jump (no drift)."""
        toy.key_hold(self.root, "location", frame - 1, "CONSTANT")
        toy.key_hold(self.root, "rotation_euler", frame - 1, "CONSTANT")
        self.place(frame, location, facing_deg)

    def sit(self, start: int, end: int, frames: int = 10):
        """Sit down (on a box or bucket), stay seated, stand back up."""
        self.key("hips", start, loc=(0, 0, 0.56))
        self.key("hips", start + frames, loc=(0, 0, 0.34))
        self.key("hips", end - frames, loc=(0, 0, 0.34))
        self.key("hips", end, loc=(0, 0, 0.56))
        for leg in ("legL", "legR"):
            self.key(leg, start, rot_deg=(0, 0, 0))
            self.key(leg, start + frames, rot_deg=(-85, 0, 0))
            self.key(leg, end - frames, rot_deg=(-85, 0, 0))
            self.key(leg, end, rot_deg=(0, 0, 0))

    def place(self, frame: int, location, facing_deg: float):
        self.root.location = location
        self.root.rotation_euler = (0, 0, R(facing_deg))
        self.root.keyframe_insert("location", frame=frame)
        self.root.keyframe_insert("rotation_euler", frame=frame)

    # ------------------- ACTIONS -------------------

    def idle(self, start: int, end: int, seed: int = 0):
        """Standing, alive: motion-captured idle (breathing, weight shifts), so a character is never frozen."""
        def by_hand():
            rnd = random.Random(seed)
            f = start
            while f <= end:
                k = (f - start) / 20
                self.key("spine", f, rot_deg=(2 * math.sin(k), 0, 1.5 * math.sin(k * 0.6)))
                self.key("head", f, rot_deg=(3 * math.sin(k * 0.8 + 1), 0, rnd.uniform(-6, 6)))
                f += 12
        self.act("idle", start, end, fallback=by_hand)

    def walk(self, start: int, end: int, to, facing_deg: float, step_frames: int = 9, hold_arm=None,
             hold_rot=(-40, 0, 0)):
        """Walk from the current root position to `to` with swinging limbs and bob.
        hold_arm="R"/"L" keeps that arm out (carrying / spraying) instead of swinging."""
        frm = Vector(toy.value_at(self.root, "location", start))
        to = Vector(to)
        self.turn(start - 8, facing_deg, frames=8)
        self.root.location = frm
        self.root.keyframe_insert("location", frame=start)
        self.root.location = to
        self.root.keyframe_insert("location", frame=end)
        toy.set_interpolation(self.root, "location", (start, end), "LINEAR")  # constant speed: no foot sliding
        for f in range(start, end + 1, step_frames):
            events.add(f, "step", gain=0.6)

        def by_hand():
            f, phase = start, 0
            while f <= end:
                s = 1 if phase % 2 == 0 else -1
                self.key("legL", f, rot_deg=(28 * s, 0, 0))
                self.key("legR", f, rot_deg=(-28 * s, 0, 0))
                self.key("shoulderL", f, rot_deg=hold_rot if hold_arm == "L" else (-30 * s, 0, 4))
                self.key("shoulderR", f, rot_deg=hold_rot if hold_arm == "R" else (30 * s, 0, -4))
                self.key("hips", f, loc=(0, 0, 0.56))
                self.key("hips", f + step_frames // 2, loc=(0, 0, 0.6))
                self.key("spine", f, rot_deg=(6, 0, 4 * s))
                f += step_frames
                phase += 1
            self.pose(end + 4)
        # carrying: the library's carry walk (arms out in front), else the plain walk; the stride follows the
        # root's real speed (world metres per second)
        self.act("Walk_Carry_Loop" if hold_arm else "walk", start, end, fallback=by_hand,
                 _walk=max(0.01, (to - frm).length))

    def wave(self, start: int, end: int, hand: str = "R"):
        sign = -1 if hand == "R" else 1
        self.key(f"shoulder{hand}", start, rot_deg=(0, 0, 0))
        f, up = start + 6, True
        while f < end - 4:
            self.key(f"shoulder{hand}", f, rot_deg=(0, -150 * sign + (15 if up else -15) * sign, 0))
            up = not up
            f += 7
        self.key(f"shoulder{hand}", end, rot_deg=(0, 0, 0))

    def cheer(self, start: int, end: int):
        """Both arms up, little jumps, big smile."""
        self.key("shoulderL", start, rot_deg=(0, 0, 0))
        self.key("shoulderR", start, rot_deg=(0, 0, 0))
        self.key("mouth", start, scale=(0.7, 0.6, 1.0))
        f, n = start + 5, 0
        while f < end:
            lift = 0.12 if n % 2 == 0 else 0.0
            self.key("hips", f, loc=(0, 0, 0.56 + lift))
            self.key("shoulderL", f, rot_deg=(0, -155 - (10 if n % 2 else 0), 0))
            self.key("shoulderR", f, rot_deg=(0, 155 + (10 if n % 2 else 0), 0))
            self.key("legL", f, rot_deg=(-12 if lift else 0, 0, 0))
            self.key("legR", f, rot_deg=(-12 if lift else 0, 0, 0))
            f += 7
            n += 1
        self.key("mouth", start + 4, scale=(1.4, 0.6, 2.2))
        self.key("mouth", end, scale=(1.4, 0.6, 2.2))
        self.key("hips", end, loc=(0, 0, 0.56))

    def point(self, start: int, end: int, hand: str = "R", up_deg: float = 70, side_deg: float = 0):
        """Arm raised toward something (e.g. the pit), held, then lowered.
        Forward is -Y in the rig, so raising an arm forward is a negative X rotation."""
        sign = -1 if hand == "R" else 1
        self.key(f"shoulder{hand}", start, rot_deg=(0, 0, 0))
        self.key(f"shoulder{hand}", start + 3, rot_deg=(8, 0, 0))                          # anticipation
        self.key(f"shoulder{hand}", start + 9, rot_deg=(-up_deg - 12, 0, side_deg * sign))  # overshoot
        self.key(f"shoulder{hand}", start + 14, rot_deg=(-up_deg, 0, side_deg * sign))      # settle
        self.key(f"shoulder{hand}", end - 6, rot_deg=(-up_deg + 4, 0, side_deg * sign))
        self.key(f"shoulder{hand}", end, rot_deg=(0, 0, 0))

    def hammer(self, start: int, end: int, hand: str = "R"):
        """Kneel-ish lean and repeated hammer strokes (for stakes)."""
        self.key("spine", start, rot_deg=(0, 0, 0))
        self.key("spine", start + 6, rot_deg=(35, 0, 0))
        f, up = start + 6, True
        while f < end - 6:
            self.key(f"shoulder{hand}", f, rot_deg=((-110 if up else -30), 0, 0))
            if not up:
                events.add(f, "hammer")
            up = not up
            f += 6
        self.key("spine", end, rot_deg=(0, 0, 0))
        self.key(f"shoulder{hand}", end, rot_deg=(0, 0, 0))

    def talk(self, start: int, end: int):
        """'Explaining' while the narrator speaks: head nods + one gesturing arm, the mouth SHUT. A flapping
        mouth under a third-person narrator read as Max saying the narration (the tunnel film)."""
        self.key("mouth", start, scale=(0.7, 0.6, 1.0))
        self.key("mouth", end, scale=(0.7, 0.6, 1.0))

        def by_hand():
            f, n = start, 0
            while f < end:
                self.key("head", f, rot_deg=(4 if n % 3 == 0 else -2, 0, 6 * math.sin(n)))
                f += 5
                n += 1
            self.key("shoulderL", start, rot_deg=(0, 0, 0))
            self.key("shoulderL", start + 10, rot_deg=(-55, 0, 20))
            self.key("shoulderL", end - 8, rot_deg=(-45, 0, 30))
            self.key("shoulderL", end, rot_deg=(0, 0, 0))
        self.act("talk", start, end, fallback=by_hand)    # motion-captured explaining gestures (mouth shut)

    def look(self, frame: int, yaw_deg: float, pitch_deg: float = 0):
        self.key("head", frame, rot_deg=(pitch_deg, 0, yaw_deg))

    def look_at(self, frame: int, target, hold: int = 0):
        """Turn the head toward a world point (clamped to a natural range), optionally held."""
        bpy.context.scene.frame_set(frame)
        eye = self.j["head"].matrix_world.translation + Vector((0, 0, 0.35 * self.look["scale"]))
        d = Vector(target) - eye
        facing = math.degrees(self.root.rotation_euler.z)
        yaw = math.degrees(math.atan2(d.x, -d.y)) - facing
        yaw = (yaw + 180) % 360 - 180
        pitch = math.degrees(math.atan2(-d.z, math.hypot(d.x, d.y)))
        rot = (max(-30, min(35, pitch)), 0, max(-60, min(60, yaw)))
        self.key("head", frame, rot_deg=rot)
        if hold:
            self.key("head", frame + hold, rot_deg=rot)

    def crouch(self, start: int, end: int, frames: int = 8, lean: float = 30):
        """Kneel down to work at ground level, hold, stand up. The legs have no knees, so they
        sweep BACK under the lowered hips (reads as kneeling; forward legs read as sitting on air)."""
        for f, z, leg, sp in ((start, 0.56, 0, 0), (start + frames, 0.4, 45, lean),
                              (end - frames, 0.4, 45, lean), (end, 0.56, 0, 0)):
            self.key("hips", f, loc=(0, 0, z))
            self.key("legL", f, rot_deg=(leg, 0, 4))
            self.key("legR", f, rot_deg=(leg * 0.9, 0, -4))
            self.key("spine", f, rot_deg=(sp, 0, 0))

    def hop(self, start: int, end: int, height: float = 0.28, period: int = 16, sound: str = "boing"):
        """Little jumps on the spot (crouch → spring → land), e.g. to peek over a ledge."""
        f = start
        while f + period <= end:
            self.key("hips", f, loc=(0, 0, 0.56))
            self.key("hips", f + 3, loc=(0, 0, 0.48))                 # anticipation squat
            self.key("hips", f + period // 2, loc=(0, 0, 0.56 + height))
            self.key("hips", f + period - 2, loc=(0, 0, 0.5))        # landing squash
            self.key("legL", f + 3, rot_deg=(-25, 0, 0))
            self.key("legR", f + 3, rot_deg=(-25, 0, 0))
            self.key("legL", f + period // 2, rot_deg=(6, 0, 0))
            self.key("legR", f + period // 2, rot_deg=(6, 0, 0))
            events.add(f + 3, sound, gain=0.5)
            f += period
        self.key("hips", f, loc=(0, 0, 0.56))
        self.key("legL", f, rot_deg=(0, 0, 0))
        self.key("legR", f, rot_deg=(0, 0, 0))

    def rake(self, start: int, end: int, stroke: int = 14):
        """Two-handed push/pull strokes (rake, broom): torso rocks, hips shift with each pull."""
        f, n = start, 0
        while f < end - 4:
            push = n % 2 == 0
            self.key("spine", f, rot_deg=(32 if push else 18, 0, 0))
            self.key("shoulderR", f, rot_deg=(-75 if push else -45, 0, -10))
            self.key("shoulderL", f, rot_deg=(-65 if push else -35, 0, 10))
            self.key("hips", f, loc=(0, -0.06 if push else 0.06, 0.54))
            if not push:
                events.add(f, "scoop", gain=0.25)
            f += stroke // 2
            n += 1
        self.pose(end)
        self.key("hips", end, loc=(0, 0, 0.56))

    def sweep(self, start: int, end: int, hand: str = "R", stroke: int = 10):
        """Side-to-side arm sweeps at chest height (troweling, wiping, painting)."""
        f, k = start + 4, 0
        while f < end - 4:
            self.key(f"shoulder{hand}", f, rot_deg=(-80, 0, 30 if k % 2 else -30))
            self.key("spine", f, rot_deg=(10, 0, 6 if k % 2 else -6))
            f += stroke
            k += 1
        self.key(f"shoulder{hand}", end, rot_deg=(0, 0, 0))
        self.key("spine", end, rot_deg=(0, 0, 0))

    def blink(self, frames):
        for f in frames:
            for side in (-1, 1):
                eye = f"eye{side}"
                self.key(eye, f - 2, scale=(0.95, 0.6, 1.12))
                self.key(eye, f, scale=(0.95, 0.6, 0.1))
                self.key(eye, f + 2, scale=(0.95, 0.6, 1.12))

    def auto_blink(self, start: int, end: int, seed: int = 1):
        rnd = random.Random(seed)
        f, frames = start + rnd.randint(10, 40), []
        while f < end - 3:
            frames.append(f)
            f += rnd.randint(55, 110)
        self.blink(frames)

    def smile(self, frame: int, big: bool = False):
        if self.look.get("hair_style"):
            # a kid's "U" smile gets wider and deeper, never an open oval (that read as a scream)
            self.key("mouth", frame, scale=(1.3, 1.0, 1.15) if big else (1.0, 1.0, 1.0))
            return
        self.key("mouth", frame, scale=(1.3, 0.6, 1.8) if big else (0.7, 0.6, 1.0))

    def hold(self, obj, hand: str = "R"):
        """Attach a prop to a hand so it follows the arm."""
        obj.parent = self.j[f"hand{hand}"]
        obj.location = (0, 0, 0)
        self.held = obj
