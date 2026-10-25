"""
Parametric toy-figurine characters with a joint rig and an animation library.

A character is built from rounded parts parented to joint empties (hips, spine,
neck, head, shoulders, legs). Identity is fixed by its `look` (colours, hat,
hair, mustache), so the same character is identical in every shot. Animation is
keyframed joint rotation: walk, wave, cheer, point, dig, hammer, talk, blink,
look-around, and idle breathing.
"""
import math
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


class Character:
    def __init__(self, name: str, look: dict = None, location=(0, 0, 0), facing_deg=0.0):
        self.name = name
        self.look = {**DEFAULT_LOOK, **(look or {})}
        self.j = {}
        self._build()
        self.root.location = location
        self.root.rotation_euler = (0, 0, R(facing_deg))
        self.root.scale = (self.look["scale"],) * 3
        self.held = None

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
            eye = toy.sphere(f"{n}_eye{side}", 0.1, (0.125 * side, -0.235, 0.35),
                             scale=(0.95, 0.6, 1.12), mat=white, parent=head, segments=32, rings=16)
            self.j[f"eye{side}"] = eye
            ir = toy.sphere(f"{n}_iris{side}", 0.062, (-0.008 * side, -0.086, -0.005),
                            scale=(1.0, 0.45, 1.05), mat=iris, parent=eye, subdiv=1)
            pupil = toy.sphere(f"{n}_pupil{side}", 0.034, (0, -0.02, 0), scale=(1.0, 0.6, 1.05),
                               mat=dark, parent=ir, subdiv=1)
            glint = toy.material("glint", (1, 1, 1), roughness=0.0)
            toy.sphere(f"{n}_glint{side}", 0.016, (0.022, -0.028, 0.03), mat=glint, parent=pupil, subdiv=0)
            toy.sphere(f"{n}_glint2{side}", 0.008, (-0.02, -0.028, -0.025), mat=glint, parent=pupil, subdiv=0)
            brow = toy.capsule(f"{n}_brow{side}", 0.03, 0.11, (0.13 * side, -0.25, 0.495),
                               rotation=(0, R(90 + 14 * side), 0), mat=hair, parent=head)
            brow.scale = (0.8, 0.7, 1.0)
            self.j[f"brow{side}"] = brow
        toy.sphere(f"{n}_nose", 0.072, (0, -0.315, 0.255), scale=(1.0, 0.9, 0.85),
                   mat=self._mat("nose", L["skin"], roughness=0.45, subsurface=0.2), parent=head)
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
        else:
            _half_sphere(f"{n}_hair", 0.325, hair, head, (0, 0.02, 0.32), scale=(1.0, 1.0, 1.0))
        if L.get("ponytail"):
            toy.sphere(f"{n}_ponytail", 0.11, (0, 0.33, 0.3), scale=(0.8, 1.0, 1.4), mat=hair, parent=head)

        # Arms: shoulder joints, sleeve + arm + hand.
        for side, key in ((-1, "R"), (1, "L")):
            sh = self.j[f"shoulder{key}"] = toy.empty(f"{n}_shoulder{key}", (0.27 * side, 0, 0.47), spine)
            toy.sphere(f"{n}_sleeve{key}", 0.085, (0, 0, -0.02), mat=shirt, parent=sh)
            toy.capsule(f"{n}_arm{key}", 0.068, 0.26, (0, 0, -0.17), mat=skin, parent=sh)
            hand = toy.sphere(f"{n}_hand{key}", 0.085, (0, -0.01, -0.36), scale=(0.9, 0.8, 1.0),
                              mat=skin, parent=sh)
            toy.capsule(f"{n}_thumb{key}", 0.03, 0.05, (-0.055 * side, -0.05, -0.33),
                        rotation=(R(-30), R(-35 * side), 0), mat=skin, parent=sh)
            self.j[f"hand{key}"] = toy.empty(f"{n}_grip{key}", (0, -0.03, -0.38), sh)
            hand.name = f"{n}_handmesh{key}"

        # Legs: hip joints, pant leg + shoe.
        for side, key in ((-1, "R"), (1, "L")):
            hp = self.j[f"leg{key}"] = toy.empty(f"{n}_leg{key}", (0.115 * side, 0, 0.0), hips)
            toy.capsule(f"{n}_pantleg{key}", 0.1, 0.3, (0, 0, -0.25), mat=overalls, parent=hp)
            toy.box(f"{n}_shoe{key}", (0.19, 0.27, 0.12), (0, -0.04, -0.5), mat=shoes, parent=hp,
                    bevel=0.05)
        seed = sum(map(ord, n))
        toy.add_noise(sway, "rotation_euler", 0, strength=0.035, scale=55, phase=seed)
        toy.add_noise(sway, "rotation_euler", 1, strength=0.025, scale=70, phase=seed + 3)
        toy.add_noise(nsway, "rotation_euler", 0, strength=0.06, scale=45, phase=seed + 7)
        toy.add_noise(nsway, "rotation_euler", 2, strength=0.09, scale=60, phase=seed + 11)
        self.rest = {k: tuple(o.rotation_euler) for k, o in self.j.items()}
        self.rest_loc = {k: tuple(o.location) for k, o in self.j.items()}

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
        """Breathing + small weight shifts so a standing character is never frozen."""
        rnd = random.Random(seed)
        f = start
        while f <= end:
            k = (f - start) / 20
            self.key("spine", f, rot_deg=(2 * math.sin(k), 0, 1.5 * math.sin(k * 0.6)))
            self.key("head", f, rot_deg=(3 * math.sin(k * 0.8 + 1), 0, rnd.uniform(-6, 6)))
            f += 12

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
        f, phase = start, 0
        while f <= end:
            s = 1 if phase % 2 == 0 else -1
            events.add(f, "step", gain=0.6)
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
        """Mouth flaps + head nods + one gesturing arm."""
        f, n = start, 0
        while f < end:
            self.key("mouth", f, scale=(0.9, 0.6, 1.0 + (1.2 if n % 2 == 0 else 0.0)))
            self.key("head", f, rot_deg=(4 if n % 3 == 0 else -2, 0, 6 * math.sin(n)))
            f += 5
            n += 1
        self.key("mouth", end, scale=(0.7, 0.6, 1.0))
        self.key("shoulderL", start, rot_deg=(0, 0, 0))
        self.key("shoulderL", start + 10, rot_deg=(-55, 0, 20))
        self.key("shoulderL", end - 8, rot_deg=(-45, 0, 30))
        self.key("shoulderL", end, rot_deg=(0, 0, 0))

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
        self.key("mouth", frame, scale=(1.3, 0.6, 1.8) if big else (0.7, 0.6, 1.0))

    def hold(self, obj, hand: str = "R"):
        """Attach a prop to a hand so it follows the arm."""
        obj.parent = self.j[f"hand{hand}"]
        obj.location = (0, 0, 0)
        self.held = obj
