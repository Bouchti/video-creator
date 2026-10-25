"""
Machines and props with moving parts: an articulated excavator (turntable,
boom, stick, bucket) with a fluid dig cycle, engine shake, rolling wheels,
exhaust smoke and dust; plus particle sprays and puffs, and small props.
Every mechanical action records a sound event (engine/events.py).
"""
import math
import random

import bpy
from mathutils import Vector

from engine import events, textures as tx, toy

R = math.radians

# Excavator arm geometry (local units, before the machine's scale).
BOOM_PIVOT = (0.55, 1.1)     # boom hinge: forward of the turntable centre, height above the ground
BOOM_SIDE = 0.25             # the boom sits right of the cab (turntable -Y)
BOOM_LEN, STICK_LEN = 2.3, 1.6
TEETH = (0.42, -0.3)         # bucket teeth relative to the bucket hinge (x along the bucket, z)
# Bucket attitude (world pitch, degrees, + = tipped down). The bucket's open side is its local +Z.
BUCKET_REACH, BUCKET_BITE, BUCKET_CARRY, BUCKET_DUMP = 20, 45, -15, 150


def _rot(obj, frame, deg):
    obj.rotation_euler = [R(a) for a in deg]
    obj.keyframe_insert("rotation_euler", frame=frame)


class Puffs:
    """Soft rising puffs (exhaust smoke, dust) that grow and vanish."""

    def __init__(self, name, color, count=14, size=0.18, seed=2):
        self.rnd = random.Random(seed)
        mat = toy.material(f"{name}_mat", toy.srgb(color), roughness=0.95)
        self.parts = [toy.sphere(f"{name}_{i}", size, (0, 0, -50), mat=mat, subdiv=1, segments=12, rings=8)
                      for i in range(count)]
        self.size = size

    def emit(self, frames, origin_fn, rise=0.9, life=22, drift=0.3):
        """frames: emission frames; origin_fn(frame) → world position at that frame."""
        free = list(self.parts)
        busy = []
        for f in frames:
            busy = [(p, end) for p, end in busy if end > f]
            if not free:
                free = [p for p in self.parts if p not in [b[0] for b in busy]]
                if not free:
                    continue
            p = free.pop()
            busy.append((p, f + life))
            o = Vector(origin_fn(f))
            d = Vector((self.rnd.uniform(-drift, drift), self.rnd.uniform(-drift, drift), rise))
            p.location = (0, 0, -50)
            p.scale = (0.01,) * 3
            p.keyframe_insert("location", frame=f - 1)
            p.keyframe_insert("scale", frame=f - 1)
            p.location = o
            p.keyframe_insert("location", frame=f)
            p.keyframe_insert("scale", frame=f)
            p.location = o + d * 0.6
            p.scale = (1.0,) * 3
            p.keyframe_insert("location", frame=f + life // 2)
            p.keyframe_insert("scale", frame=f + life // 2)
            p.location = o + d
            p.scale = (0.01,) * 3
            p.keyframe_insert("location", frame=f + life)
            p.keyframe_insert("scale", frame=f + life)
            p.location = (0, 0, -50)
            p.keyframe_insert("location", frame=f + life + 1)
            # (no free.append(p) here: a puff is reusable only once its life is over; refilled above
            # from the parts that are no longer busy. Appending it back made pop() reuse the same
            # single puff for every emission, so only one ever showed.)
        for p in self.parts:
            _constant_jumps(p)


class Excavator:
    """Faces local +X. Joints: turntable (Z yaw) → boom → stick → bucket (Y pitch)."""

    def __init__(self, location=(0, 0, 0), facing_deg=0.0, scale=0.9):
        yellow = tx.paint("cat_yellow", "#FFB400", 0.3, coat=0.7, seams=0.7, seam_axis="x")
        dark = tx.rubber("track_dark", "#2B2B2E", 0.7, tread=0)
        steel = tx.metal("bucket_steel", "#55585E", 0.35, along="x", metallic=0.8)
        glass = toy.material("cab_glass", toy.srgb("#7FC4E8"), roughness=0.05, coat=1.0)
        black = toy.material("decal_black", toy.srgb("#1A1A1A"), roughness=0.4)

        self.scale = scale
        self.root = toy.empty("exc_root", location)
        self.root.rotation_euler = (0, 0, R(facing_deg))
        self.root.scale = (scale,) * 3
        self.wheels = []
        for side in (-1, 1):
            toy.box(f"exc_track{side}", (2.2, 0.45, 0.5), (0, 0.6 * side, 0.25), mat=dark, parent=self.root,
                    bevel=0.18)
            for k in range(4):
                w = toy.cylinder(f"exc_wheel{side}_{k}", 0.16, 0.47, (-0.75 + k * 0.5, 0.6 * side, 0.25),
                                 rotation=(R(90), 0, 0), mat=steel, parent=self.root, bevel=0.02)
                for spoke in range(3):  # visible spokes so rolling reads on camera
                    toy.box(f"exc_spoke{side}_{k}_{spoke}", (0.3, 0.05, 0.49), (0, 0, 0), mat=dark, parent=w,
                            bevel=0.01, rotation=(0, R(60 * spoke), 0)).rotation_euler = (0, R(60 * spoke), 0)
                self.wheels.append(w)
        self.turn = toy.empty("exc_turn", (0, 0, 0.55), self.root)
        self.body = toy.empty("exc_body_shake", (0, 0, 0), self.turn)
        toy.add_noise(self.body, "location", 2, strength=0.012, scale=1.5, phase=3)
        toy.add_noise(self.body, "rotation_euler", 0, strength=0.006, scale=2.0, phase=9)
        toy.box("exc_body", (1.7, 1.35, 0.6), (-0.2, 0, 0.32), mat=yellow, parent=self.body, bevel=0.12)
        toy.box("exc_counterweight", (0.5, 1.35, 0.5), (-1.0, 0, 0.35), mat=yellow, parent=self.body, bevel=0.18)
        toy.box("exc_stripe", (1.72, 1.37, 0.06), (-0.2, 0, 0.12), mat=black, parent=self.body, bevel=0.02)
        toy.box("exc_cab", (0.8, 0.75, 0.85), (0.15, 0.3, 1.05), mat=yellow, parent=self.body, bevel=0.1)
        toy.box("exc_window", (0.6, 0.7, 0.55), (0.32, 0.3, 1.1), mat=glass, parent=self.body, bevel=0.06)
        toy.box("exc_roof_light", (0.12, 0.12, 0.08), (0.1, 0.3, 1.52),
                mat=toy.material("beacon", toy.srgb("#FF6A00"), roughness=0.2, coat=1.0), parent=self.body, bevel=0.03)
        self.exhaust = toy.cylinder("exc_exhaust", 0.05, 0.45, (-0.7, -0.45, 0.85), mat=dark, parent=self.body)

        self.boom = toy.empty("exc_boom", (BOOM_PIVOT[0], -BOOM_SIDE, BOOM_PIVOT[1] - 0.55), self.body)
        toy.box("exc_boom_arm", (BOOM_LEN, 0.22, 0.28), (BOOM_LEN / 2, 0, 0), mat=yellow, parent=self.boom,
                bevel=0.08)
        toy.cylinder("exc_boom_ram", 0.06, 1.1, (0.55, 0, -0.22), rotation=(0, R(80), 0), mat=steel,
                     parent=self.boom)
        self.stick = toy.empty("exc_stick", (BOOM_LEN, 0, 0), self.boom)
        toy.box("exc_stick_arm", (STICK_LEN, 0.18, 0.22), (STICK_LEN / 2, 0, 0), mat=yellow, parent=self.stick,
                bevel=0.07)
        self.bucket = toy.empty("exc_bucket", (STICK_LEN, 0, 0), self.stick)
        toy.box("exc_bucket_shell", (0.5, 0.55, 0.42), (0.18, 0, -0.12), mat=steel, parent=self.bucket,
                bevel=0.1)
        for k in range(4):
            toy.box(f"exc_tooth{k}", (0.12, 0.07, 0.07), (0.42, -0.2 + k * 0.133, -0.3), mat=steel,
                    parent=self.bucket, bevel=0.02)
        self.dirt = toy.sphere("exc_bucket_dirt", 0.22, (0.18, 0, -0.02), scale=(1.1, 1.1, 0.6),
                               mat=bpy.data.materials.get("dirt"), parent=self.bucket)
        self.smoke = Puffs("exhaust", "#8A8A8A", count=16, size=0.12, seed=5)
        # Separate pools: one emit() per Puffs, or reused puffs get overlapping keys and teleport.
        self.dust = Puffs("dust", "#A07A52", count=18, size=0.22, seed=8)
        self.dust_dump = Puffs("dust_dump", "#A07A52", count=12, size=0.2, seed=13)
        self.rest(1)

    # ------------------- POSES / MOTION -------------------

    def pose(self, frame, turn=0, boom=-25, stick=70, bucket=-20):
        _rot(self.turn, frame, (0, 0, turn))
        _rot(self.boom, frame, (0, boom, 0))
        _rot(self.stick, frame, (0, stick, 0))
        _rot(self.bucket, frame, (0, bucket, 0))

    def rest(self, frame):
        self.pose(frame, 0, -35, 95, 60)

    def drive(self, start: int, end: int, to):
        """Roll to `to`: wheels turn by the distance travelled; engine revs."""
        frm = Vector(toy.value_at(self.root, "location", start))
        to = Vector(to)
        toy.key_hold(self.root, "location", start)
        self.root.location = to
        self.root.keyframe_insert("location", frame=end)
        turns = (to - frm).length / (0.16 * self.scale)
        for w in self.wheels:
            toy.key_hold(w, "rotation_euler", start)
            w.rotation_euler.y += turns
            w.keyframe_insert("rotation_euler", frame=end)
        events.add(start, "engine_rev", duration=end - start)

    def run_engine(self, start: int, end: int):
        """Exhaust puffs + engine rumble sound for the frame range.
        Call AFTER all of the excavator's motion is keyed (puffs follow the exhaust)."""
        events.add(start, "engine", duration=end - start)
        self.smoke.emit(range(start, end, 7), lambda f: self._world_exhaust(f), rise=1.0, life=24, drift=0.25)

    def _world_exhaust(self, frame):
        bpy.context.scene.frame_set(frame)
        return self.exhaust.matrix_world @ Vector((0, 0, 0.3))

    def _dirt(self, frame, full):
        self.dirt.scale = (1.1, 1.1, 0.6) if full else (0.01, 0.01, 0.01)
        self.dirt.keyframe_insert("scale", frame=frame)

    def dig_cycle(self, start: int, end: int, dump_turn: float = 75):
        """Fluid reach → scoop → lift → swing → dump → return, filling the frame range."""
        cycle = 44
        f = start
        self._dirt(f, False)
        scoops, dumps = [], []
        while f + cycle <= end + 4:
            self.pose(f, 0, -18, 60, -30)               # reach out
            self.pose(f + 10, 0, 16, 88, -12)           # bucket bites the ground
            self.pose(f + 18, 0, 20, 108, 68)           # scoop (curl)
            self._dirt(f + 17, False)
            self._dirt(f + 19, True)
            scoops.append(f + 12)
            self.pose(f + 26, 0, -28, 88, 82)           # lift
            self.pose(f + 34, dump_turn, -28, 72, 82)   # swing to the pile
            self.pose(f + 40, dump_turn, -22, 66, -40)  # dump
            self._dirt(f + 39, True)
            self._dirt(f + 41, False)
            dumps.append(f + 40)
            f += cycle
        self.pose(end, 0, -25, 70, -20)
        for s in scoops:
            events.add(s, "scoop")
        for d in dumps:
            events.add(d, "dump")
        self.dust.emit([s + k for s in scoops for k in (0, 2, 4)], lambda fr: self._world_bucket(fr),
                       rise=0.5, life=26, drift=0.7)
        self.dust.emit([d + k for d in dumps for k in (1, 3)], lambda fr: self._world_bucket(fr),
                       rise=0.3, life=22, drift=0.6)
        return scoops, dumps

    def _world_bucket(self, frame):
        bpy.context.scene.frame_set(frame)
        return self.bucket.matrix_world @ Vector((0.3, 0, -0.3))

    # ------------------- IK DIGGING -------------------

    def solve(self, root, yaw_deg, teeth, pitch_deg):
        """Joint angles (turn, boom, stick, bucket in degrees) that put the bucket teeth at world
        point `teeth` with the bucket at world pitch `pitch_deg`, for the machine at `root`/`yaw_deg`.
        Unreachable points are clamped to the arm's reach (the arm stretches toward them)."""
        s = self.scale
        rel = Vector(teeth) - Vector(root)
        yaw = R(yaw_deg)
        lx = rel.x * math.cos(-yaw) - rel.y * math.sin(-yaw)
        ly = rel.x * math.sin(-yaw) + rel.y * math.cos(-yaw)
        rho = max(math.hypot(lx, ly), BOOM_SIDE * s + 0.05)
        alpha = math.atan2(ly, lx)
        turn = alpha + math.asin(BOOM_SIDE * s / rho)          # boom plane is offset from the centre
        fwd = math.sqrt(rho ** 2 - (BOOM_SIDE * s) ** 2) - BOOM_PIVOT[0] * s
        up = rel.z - BOOM_PIVOT[1] * s
        beta = R(pitch_deg)
        tx, tz = TEETH[0] * s, TEETH[1] * s                    # teeth offset rotated by the bucket pitch
        wx = fwd - (tx * math.cos(beta) + tz * math.sin(beta))
        wz = up - (-tx * math.sin(beta) + tz * math.cos(beta))
        lb, ls = BOOM_LEN * s, STICK_LEN * s
        d = min(max(math.hypot(wx, wz), abs(lb - ls) + 0.05), (lb + ls) * 0.985)
        phi = math.atan2(-wz, wx)                              # + = below the hinge
        t2 = math.acos(max(-1.0, min(1.0, (d * d - lb * lb - ls * ls) / (2 * lb * ls))))
        t1 = phi - math.atan2(ls * math.sin(t2), lb + ls * math.cos(t2))
        return (math.degrees(turn), math.degrees(t1), math.degrees(t2), math.degrees(beta - t1 - t2))

    def _ik_pose(self, frame, root, yaw_deg, teeth, pitch_deg):
        turn, boom, stick, bucket = self.solve(root, yaw_deg, teeth, pitch_deg)
        if self._last_turn is not None:                        # unwrap: never spin the long way round
            while turn - self._last_turn > 180:
                turn -= 360
            while turn - self._last_turn < -180:
                turn += 360
        self._last_turn = turn
        self.pose(frame, turn, boom, stick, bucket)

    def dig_sequence(self, start: int, bites: list, dump_at, yaw_deg: float, cycle: int = 48):
        """Dig with real reach: for each bite {"root": station, "target": surface point}, the arm
        reaches, bites the soil AT the target, curls, lifts, swings to `dump_at`, dumps, and swings
        back while the tracks crawl to the next station. Returns per-bite timing
        [{"bite", "curl", "dump"}] so the set (soil columns, spoil pile) can react in sync."""
        self._last_turn = None
        dump_at = Vector(dump_at)
        st = [int(round(cycle * k)) for k in (0, 0.17, 0.33, 0.46, 0.65, 0.75)]
        timing, f = [], start
        root_prev = Vector(self.root.location)
        for i, bite in enumerate(bites):
            root, tgt = Vector(bite["root"]), Vector(bite["target"])
            if (root - root_prev).length > 0.01:               # crawl during the swing back
                self._crawl(f - (cycle - st[5]) + 2, f - 1, root_prev, root)
            toward = (root - tgt)
            toward.z = 0
            toward = toward.normalized() if toward.length else Vector((0, 1, 0))
            self._ik_pose(f + st[0], root, yaw_deg, tgt + Vector((0, 0, 0.55)) - toward * 0.25, BUCKET_REACH)
            self._ik_pose(f + st[1], root, yaw_deg, tgt, BUCKET_BITE)
            curl_at = tgt + toward * 0.45 + Vector((0, 0, -0.08))
            self._ik_pose(f + st[2], root, yaw_deg, curl_at, BUCKET_CARRY)
            lift = Vector((curl_at.x, curl_at.y, 1.0))
            self._ik_pose(f + st[3], root, yaw_deg, lift, BUCKET_CARRY)
            over = dump_at + Vector((0, 0, 1.5))
            self._ik_pose(f + st[4], root, yaw_deg, over, BUCKET_CARRY)
            self._ik_pose(f + st[5], root, yaw_deg, over + Vector((0, 0, 0.15)), BUCKET_DUMP)
            self._dirt(f + st[1] + 1, False)
            self._dirt(f + st[2] - 1, True)
            self._dirt(f + st[5] - 1, True)
            self._dirt(f + st[5] + 2, False)
            timing.append({"bite": f + st[1], "curl": f + st[2], "dump": f + st[5]})
            events.add(f + st[1], "scoop")
            events.add(f + st[5], "dump")
            root_prev = root
            f += cycle
        ahead = Vector((math.cos(R(yaw_deg)), math.sin(R(yaw_deg)), 0))
        self._ik_pose(f, root_prev, yaw_deg, root_prev + ahead * 2.4 + Vector((0, 0, 0.9)), BUCKET_CARRY)
        self.dust.emit([t["bite"] + k for t in timing for k in (0, 2, 4)], lambda fr: self._world_bucket(fr),
                       rise=0.5, life=26, drift=0.7)
        self.dust_dump.emit([t["dump"] + k for t in timing for k in (1, 3)], lambda fr: self._world_bucket(fr),
                            rise=0.3, life=22, drift=0.6)
        return timing

    def _crawl(self, start, end, frm, to):
        self.root.location = frm
        self.root.keyframe_insert("location", frame=start)
        self.root.location = to
        self.root.keyframe_insert("location", frame=end)
        turns = (Vector(to) - Vector(frm)).length / (0.16 * self.scale)
        for w in self.wheels:
            toy.key_hold(w, "rotation_euler", start)
            w.rotation_euler.y += turns
            w.keyframe_insert("rotation_euler", frame=end)
        events.add(start, "engine_rev", duration=end - start, gain=0.6)


class Spray:
    """Particle stream from a nozzle toward a target area (concrete or water)."""

    def __init__(self, name, mat, count=36, radius=0.045, seed=3):
        self.rnd = random.Random(seed)
        self.parts = [toy.sphere(f"{name}_p{i}", radius * self.rnd.uniform(0.7, 1.3), (0, 0, -50),
                                 mat=mat, subdiv=0, segments=8, rings=6) for i in range(count)]

    def run(self, start: int, end: int, source, target, spread=0.6, arc=0.5, period=12, sound=None):
        """Each particle loops source → arc → target. It shrinks to nothing on landing and only
        then jumps back, so the respawn never shows (or smears under motion blur)."""
        source, target = Vector(source), Vector(target)
        if sound:
            events.add(start, sound, duration=end - start)
        full, tiny = Vector((1, 1, 1)), Vector((0.01, 0.01, 0.01))
        for i, p in enumerate(self.parts):
            offset = Vector((self.rnd.uniform(-spread, spread), self.rnd.uniform(-spread, spread),
                             self.rnd.uniform(-spread * 0.6, spread * 0.6)))
            phase = int(period * i / len(self.parts))
            f = start + phase
            p.location, p.scale = (0, 0, -50), tiny
            p.keyframe_insert("location", frame=start - 1)
            p.keyframe_insert("scale", frame=start - 1)
            while f < end:
                mid = (source + target + offset) / 2 + Vector((0, 0, arc))
                for t, pos, sc in ((f, source, tiny), (f + 2, source.lerp(mid, 0.3), full),
                                   (f + period // 2, mid, full), (f + period - 2, target + offset, full),
                                   (f + period - 1, target + offset, tiny)):
                    p.location, p.scale = pos, sc
                    p.keyframe_insert("location", frame=t)
                    p.keyframe_insert("scale", frame=t)
                f += period
            p.location, p.scale = (0, 0, -50), tiny
            p.keyframe_insert("location", frame=f + 1)
            p.keyframe_insert("scale", frame=f + 1)
            _constant_jumps(p)


def _constant_jumps(obj):
    """Make particles jump back to their source instead of flying backwards."""
    for fc in toy.fcurves(obj):
        pts = fc.keyframe_points
        for k in range(len(pts) - 1):
            if pts[k + 1].co.x - pts[k].co.x <= 1.01:
                toy.set_key_interpolation(obj, fc, pts[k], "CONSTANT")


def blueprint(name="blueprint"):
    """An open blueprint sheet the character can hold."""
    paper = toy.material("blueprint", toy.srgb("#1E5BB8"), roughness=0.6)
    lines = toy.material("blueprint_lines", toy.srgb("#E8F1FF"), roughness=0.6)
    sheet = toy.box(name, (0.55, 0.02, 0.4), (0, 0, 0), mat=paper, bevel=0.005)
    toy.box(f"{name}_rect", (0.32, 0.005, 0.2), (0, -0.012, 0.02), mat=lines, parent=sheet, bevel=0)
    toy.box(f"{name}_inner", (0.3, 0.006, 0.18), (0, -0.013, 0.02), mat=paper, parent=sheet, bevel=0)
    return sheet


def nozzle(name="nozzle"):
    steel = toy.material("nozzle_steel", toy.srgb("#3A3D42"), roughness=0.3, metallic=0.8)
    return toy.cylinder(name, 0.04, 0.45, (0, 0, 0), rotation=(R(90), 0, 0), mat=steel)


def hammer_prop(name="hammer"):
    wood = tx.wood("hammer_wood", "#A8743F", "#C9925A", along="z")
    steel = tx.metal("hammer_steel", "#5F6368", 0.3, along="x")
    handle = toy.cylinder(name, 0.02, 0.32, (0, 0, -0.12), mat=wood)
    toy.box(f"{name}_head", (0.16, 0.06, 0.06), (0, 0, -0.16), mat=steel, parent=handle, bevel=0.01)
    return handle


def stopwatch(name="watch"):
    """Big cartoon stopwatch shown during the curing time-lapse."""
    gold = toy.material("watch_gold", toy.srgb("#F2C14E"), roughness=0.25, metallic=0.6, coat=0.6)
    face = toy.material("watch_face", toy.srgb("#FFFFFF"), roughness=0.4)
    hand_m = toy.material("watch_hand", toy.srgb("#D8342C"), roughness=0.3)
    body = toy.cylinder(name, 0.35, 0.12, (0, 0, 0), rotation=(R(90), 0, 0), mat=gold, bevel=0.03)
    toy.cylinder(f"{name}_face", 0.3, 0.13, (0, 0, 0), mat=face, parent=body)
    toy.cylinder(f"{name}_crown", 0.06, 0.12, (0, 0.0, 0.0), mat=gold, parent=body).location = (0, 0.42, 0)
    pivot = toy.empty(f"{name}_pivot", (0, 0, 0.07), body)
    toy.box(f"{name}_hand", (0.03, 0.24, 0.02), (0, 0.11, 0), mat=hand_m, parent=pivot, bevel=0.005)
    return body, pivot


def spray_can(name="spray_can", color="#FFD400"):
    """Marking-paint can, held nozzle-down."""
    paint = toy.material(f"{name}_paint", toy.srgb(color), roughness=0.3, coat=0.6)
    cap = toy.material("can_cap", toy.srgb("#F4F4F0"), roughness=0.4)
    can = toy.cylinder(name, 0.045, 0.2, (0, 0, -0.1), mat=paint, bevel=0.01)
    toy.cylinder(f"{name}_cap", 0.03, 0.05, (0, 0, -0.12), mat=cap, parent=can)
    return can


def rake(name="rake"):
    """Garden rake: long handle (local -Z) with a toothed head at the far end."""
    wood = toy.material("rake_wood", toy.srgb("#C08A50"), roughness=0.6)
    steel = toy.material("rake_steel", toy.srgb("#5F6368"), roughness=0.3, metallic=0.9)
    handle = toy.cylinder(name, 0.018, 1.3, (0, 0, -0.55), mat=wood)
    head = toy.box(f"{name}_head", (0.42, 0.04, 0.04), (0, 0, -0.65), mat=steel, parent=handle, bevel=0.008)
    for k in range(8):
        toy.box(f"{name}_tine{k}", (0.012, 0.012, 0.07), (-0.19 + k * 0.054, -0.02, -0.04), mat=steel,
                parent=head, bevel=0)
    return handle


def trowel(name="trowel"):
    steel = toy.material("trowel_steel", toy.srgb("#B8BCC2"), roughness=0.2, metallic=0.9)
    wood = toy.material("hammer_wood", toy.srgb("#C08A50"), roughness=0.6)
    grip = toy.cylinder(name, 0.022, 0.12, (0, 0, -0.04), mat=wood)
    toy.box(f"{name}_blade", (0.32, 0.14, 0.01), (0, -0.06, -0.12), mat=steel, parent=grip, bevel=0.004)
    return grip


def survey_rod(name, location, height=2.0, band=0.2):
    """Red/white measuring rod: one band per `band` metres, so depth reads at a glance."""
    red = toy.material("rod_red", toy.srgb("#E8322A"), roughness=0.35, coat=0.5)
    white = toy.material("rod_white", toy.srgb("#F7F5EF"), roughness=0.35, coat=0.5)
    root = toy.empty(name, location)
    for k in range(int(round(height / band))):
        toy.box(f"{name}_{k}", (0.07, 0.07, band), (0, 0, band * (k + 0.5)), mat=red if k % 2 else white,
                parent=root, bevel=0.004)
    return root


def test_tube(name="test_tube"):
    glass = toy.material("tube_glass", toy.srgb("#E6F4FA"), roughness=0.05, coat=1.0)
    liquid = toy.material("tube_liquid", toy.srgb("#F25C8A"), roughness=0.2, coat=0.6)  # phenol-red pink
    tube = toy.cylinder(name, 0.022, 0.16, (0, 0, -0.08), mat=glass)
    toy.cylinder(f"{name}_liquid", 0.019, 0.08, (0, 0, -0.035), mat=liquid, parent=tube)
    return tube


def chlorinator(name="chlorinator"):
    """Rubber-duck chlorine floater (a real product, and funnier than a plain puck). Faces -Y."""
    yellow = toy.material("duck_yellow", toy.srgb("#FFD21F"), roughness=0.3, coat=0.8)
    orange = toy.material("duck_beak", toy.srgb("#FF7A1A"), roughness=0.3, coat=0.6)
    dark = toy.material("eye_dark", toy.srgb("#1A1A1A"), roughness=0.15, coat=1.0)
    body = toy.sphere(name, 0.17, (0, 0, 0.04), scale=(1.0, 1.25, 0.7), mat=yellow)
    toy.sphere(f"{name}_tail", 0.07, (0, 0.2, 0.08), scale=(1, 1, 1.3), mat=yellow, parent=body)
    head = toy.sphere(f"{name}_head", 0.1, (0, -0.13, 0.17), mat=yellow, parent=body)
    toy.sphere(f"{name}_beak", 0.05, (0, -0.1, -0.01), scale=(1.2, 1.1, 0.45), mat=orange, parent=head)
    for side in (-1, 1):
        toy.sphere(f"{name}_eye{side}", 0.017, (0.05 * side, -0.075, 0.035), mat=dark, parent=head, subdiv=1)
    return body
