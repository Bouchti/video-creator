"""
Motion-capture performances for the toy characters (engine/character.py), from the Quaternius Universal
Animation Library 1 + 2 (CC0, 86 clips on one 65-bone skeleton: idle, talk, walk, jog, sprint, jump, sit,
dance, yes / no, fold arms, push, pick up, kneel and fix, phone call, wave-like spell gestures, hit ...).

    from engine.mocap import Mocap
    mc = Mocap()                                    # loads the clip library once (assets/cc0/quaternius)
    mc.perform(max_char, [("Idle_Talking_Loop", 1, 90), ("Yes", 91, 130), ("Walk_Loop", 131, 220)])

How: each clip is evaluated straight from its curves (no scene updates, so it is fast); every bone's pose
is turned into a rotation DELTA from its rest pose in armature space, then made relative to the bone that
drives the toy joint's parent. The toy joints rest with identity rotation in the same axes (character facing
-Y, Z up), so that delta is exactly the joint's rotation. The pelvis height drives the hips (squats, jumps,
sitting), scaled by leg length. Clips cross-fade (quaternion slerp) for BLEND frames, and loops are wrapped,
so a performance never pops. Keys are written every frame as Euler with continuity (no 360-degree flips).
"""
import glob
import math
import os

try:                       # the clip vocabulary (CLIPS) is also read outside Blender, by the plan writer
    import bpy
    from mathutils import Matrix, Quaternion, Vector
except ImportError:        # pragma: no cover
    bpy = Matrix = Quaternion = Vector = None

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "cc0", "quaternius")
LIBS = ("universal-animation-library/**/Unreal-Godot/UAL1_Standard.glb",
        "universal-animation-library-2/**/Unreal-Godot/UAL2_Standard.glb")
BLEND = 8          # cross-fade frames between clips
FPS = 30

# toy joint -> (driving bone, bone of the toy joint's parent; None = the armature itself)
JOINTS = {
    "hips": ("pelvis", None),
    "spine": ("spine_03", "pelvis"),
    "neck": ("neck_01", "spine_03"),
    "head": ("Head", "neck_01"),
    "shoulderL": ("upperarm_l", "spine_03"), "elbowL": ("lowerarm_l", "upperarm_l"),
    "shoulderR": ("upperarm_r", "spine_03"), "elbowR": ("lowerarm_r", "upperarm_r"),
    "legL": ("thigh_l", "pelvis"), "kneeL": ("calf_l", "thigh_l"),
    "legR": ("thigh_r", "pelvis"), "kneeR": ("calf_r", "thigh_r"),
}
PARENT_JOINT = {"spine": "hips", "neck": "spine", "head": "neck", "shoulderL": "spine", "elbowL": "shoulderL",
                "shoulderR": "spine", "elbowR": "shoulderR", "legL": "hips", "kneeL": "legL", "legR": "hips",
                "kneeR": "legR"}
UP = {"spine", "neck", "head"}           # toy parts that rest pointing up (the limbs hang down)
# Every clip a story may use, by what it shows (names are the library's own). Only clips that read right
# with the character STANDING ON THE GROUND and nothing in its hands: climbing, sitting, driving, swimming
# and sliding need a ladder / seat / car / water under the body and played in thin air, so they are left out.
CLIPS = {
    "idle": "Idle_Loop", "talk": "Idle_Talking_Loop", "phone": "Idle_TalkingPhone_Loop",
    "fold_arms": "Idle_FoldArms_Loop", "yes": "Yes", "no": "Idle_No_Loop", "walk": "Walk_Loop",
    "walk_proud": "Walk_Formal_Loop", "jog": "Jog_Fwd_Loop", "run": "Sprint_Loop",
    "jump": "Jump_Start", "dance": "Dance_Loop",
    "crouch": "Crouch_Idle_Loop", "sneak": "Crouch_Fwd_Loop",
    "fix": "Fixing_Kneeling", "push": "Push_Loop", "pick_up": "PickUp_Table", "interact": "Interact",
    "throw": "OverhandThrow", "hit": "Hit_Chest", "knocked": "Hit_Knockback", "fall": "Death01",
    "get_up": "LayToIdle", "roll": "Roll", "water": "Farm_Watering", "plant": "Farm_PlantSeed",
    "harvest": "Farm_Harvest", "chop": "TreeChopping_Loop", "open_chest": "Chest_Open", "eat": "Consume",
    "call_out": "Idle_Rail_Call", "point": "Spell_Simple_Shoot", "punch": "Punch_Cross",
}


def _fcurves(action):
    legacy = getattr(action, "fcurves", None)
    if legacy is not None and len(legacy):
        return list(legacy)
    return [fc for layer in action.layers for strip in layer.strips for bag in strip.channelbags
            for fc in bag.fcurves]


class Clip:
    """One library action, evaluated per bone without touching the scene."""

    def __init__(self, action, rest):
        self.name = action.name
        self.f0, self.f1 = (float(v) for v in action.frame_range)
        self.loop = self.name.endswith("_Loop")
        self.rest = rest                       # bone -> (parent bone, rest matrix in armature space)
        curves = {}
        for fc in _fcurves(action):
            if not fc.data_path.startswith('pose.bones["'):
                continue
            bone = fc.data_path.split('"')[1]
            prop = fc.data_path.rsplit(".", 1)[1]
            curves.setdefault(bone, {}).setdefault(prop, {})[fc.array_index] = fc
        self.curves = curves

    @property
    def frames(self):
        return self.f1 - self.f0

    def _basis(self, bone, t):
        c = self.curves.get(bone, {})
        rq = c.get("rotation_quaternion")
        q = Quaternion([rq[i].evaluate(t) if i in rq else (1.0 if i == 0 else 0.0) for i in range(4)]) \
            if rq else Quaternion()
        q.normalize()
        lc = c.get("location")
        loc = Vector([lc[i].evaluate(t) if i in lc else 0.0 for i in range(3)]) if lc else Vector()
        return Matrix.Translation(loc) @ q.to_matrix().to_4x4()

    def pose(self, t, extra=()):
        """bone -> pose matrix in armature space at clip time t (forward kinematics)."""
        out = {}

        def solve(b):
            if b in out:
                return out[b]
            parent, rest = self.rest[b]
            if parent is None:
                m = rest @ self._basis(b, t)
            else:
                m = solve(parent) @ (self.rest[parent][1].inverted() @ rest) @ self._basis(b, t)
            out[b] = m
            return m

        for b in {b for pair in JOINTS.values() for b in pair if b} | set(extra):
            solve(b)
        return out

    def _facing_fix(self):
        """Every clip STARTS facing the toy's front (-Y). The second library's clips start turned 180 degrees,
        so a character told to face the camera showed its back; turns inside a clip are kept."""
        if not hasattr(self, "_fix"):
            self._fix = Quaternion()
            p = self.pose(self.f0)
            q = p["pelvis"].to_quaternion() @ self.rest["pelvis"][1].to_quaternion().inverted()
            fwd = q @ Vector((0, -1, 0))
            yaw = math.atan2(fwd.x, -fwd.y)
            if abs(yaw) > math.radians(20):
                self._fix = Quaternion((0, 0, 1), -yaw)
        return self._fix

    def _align(self, joint):
        """Rest-pose correction: the library rests in an A-pose (arms out), the toy with its limbs straight
        down / up. A_j turns the toy limb's rest direction onto the bone's, so world orientation
        T_j = delta_bone @ A_j points the toy limb exactly where the captured limb points."""
        cache = self.__dict__.setdefault("_aligned", {})
        if joint not in cache:
            bone = JOINTS[joint][0]
            if joint == "hips":
                cache[joint] = Quaternion()
            else:
                toy_dir = Vector((0, 0, 1)) if joint in UP else Vector((0, 0, -1))
                bone_dir = self.rest[bone][1].to_3x3() @ Vector((0, 1, 0))     # a bone points along its +Y
                cache[joint] = toy_dir.rotation_difference(bone_dir.normalized())
        return cache[joint]

    def sample(self, t):
        """toy joint -> rotation (Quaternion) and the pelvis height change (armature units) at clip time t."""
        p = self.pose(t)
        delta = {b: (m.to_quaternion() @ self.rest[b][1].to_quaternion().inverted()) for b, m in p.items()}
        fix = self._facing_fix()
        world = {j: delta[bone] @ self._align(j) for j, (bone, _parent) in JOINTS.items()}
        world["hips"] = fix @ world["hips"]       # only the root needs it: every other joint is relative
        rot = {}
        for joint, (bone, parent) in JOINTS.items():
            q = world[joint] if parent is None else world[PARENT_JOINT[joint]].inverted() @ world[joint]
            q.normalize()
            rot[joint] = q
        lift = p["pelvis"].translation - self.rest["pelvis"][1].translation
        return rot, lift


class Mocap:
    _shared = None

    def __new__(cls):
        if cls._shared is None:          # one library per Blender session
            cls._shared = super().__new__(cls)
            cls._shared._load()
        return cls._shared

    def _load(self):
        self.clips = {}
        self.pelvis_height = 1.0
        for pat in LIBS:
            hits = glob.glob(os.path.join(ROOT, pat), recursive=True)
            if not hits:
                continue
            before_obj, before_act = set(bpy.data.objects), set(bpy.data.actions)
            bpy.ops.import_scene.gltf(filepath=hits[0])
            new = [o for o in bpy.data.objects if o not in before_obj]
            arm = next(o for o in new if o.type == "ARMATURE")
            rest = {b.name: (b.parent.name if b.parent else None, b.matrix_local.copy()) for b in arm.data.bones}
            self.pelvis_height = rest["pelvis"][1].translation.z
            for a in bpy.data.actions:
                if a not in before_act:
                    a.use_fake_user = True
                    self.clips[a.name] = Clip(a, rest)
            for o in new:
                bpy.data.objects.remove(o, do_unlink=True)

    def available(self):
        return bool(self.clips)

    def clip(self, name):
        """Library name ('Walk_Loop') or meaning ('walk'); None if missing."""
        return self.clips.get(CLIPS.get(name, name))

    def ground_speed(self, name, height=1.0):
        """Walking speed (m/s) a looped locomotion clip implies for a character whose hips are `height` up:
        the stance foot slides back at the body's speed, so speed = foot travel / stance time."""
        c = self.clip(name)
        if c is None:
            return 0.0
        ys = []
        for k in range(24):
            p = c.pose(c.f0 + c.frames * k / 24, extra=("foot_l",))
            ys.append(p["foot_l"].translation.y)
        travel = max(ys) - min(ys)
        return travel / (0.55 * c.frames / FPS) * height / self.pelvis_height

    def perform(self, char, segments, speed=1.0, hips_height=0.56):
        """Key `char`'s joints from `segments` = [(clip, f0, f1) or (clip, f0, f1, clip_speed)], in order.
        Neighbouring segments cross-fade over BLEND frames; gaps hold the last pose."""
        if not self.clips:
            return False
        segs = []
        for s in segments:
            c = self.clip(s[0])
            if c is not None:
                segs.append((c, s[1], s[2], s[3] if len(s) > 3 else speed))
        if not segs:
            return False
        scale = hips_height / self.pelvis_height
        prev_euler = {j: char.j[j].rotation_euler.copy() for j in JOINTS if j in char.j}
        rest_hips = Vector(char.rest_loc["hips"])

        def at(seg, f):
            c, f0, _f1, sp = seg
            t = (f - f0) * sp
            t = (t % c.frames) if c.loop else min(t, c.frames)
            return c.sample(c.f0 + t)

        for k, seg in enumerate(segs):
            _c, f0, f1, _sp = seg
            nxt = segs[k + 1] if k + 1 < len(segs) else None
            for f in range(f0, f1 + 1):
                rot, lift = at(seg, f)
                if nxt is not None and f > f1 - BLEND and nxt[1] <= f1 + 1:
                    w = (f - (f1 - BLEND)) / BLEND
                    w = w * w * (3 - 2 * w)
                    r2, l2 = at(nxt, nxt[1])
                    rot = {j: rot[j].slerp(r2[j], w) for j in rot}
                    lift = lift.lerp(l2, w)
                for j, q in rot.items():
                    if j not in char.j:
                        continue
                    ob = char.j[j]
                    ob.rotation_mode = "XYZ"
                    e = q.to_euler("XYZ", prev_euler[j])
                    ob.rotation_euler = e
                    prev_euler[j] = e
                    ob.keyframe_insert("rotation_euler", frame=f)
                hips = char.j["hips"]
                hips.location = rest_hips + Vector((0, 0, lift.z * scale))
                hips.keyframe_insert("location", frame=f)
        return True
