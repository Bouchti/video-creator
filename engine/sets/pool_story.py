"""
POOL STORY set — Blender builder for the trial-and-error comedy (see pool_story_spec.py).
Max builds a pool for his kids; every naive attempt fails on screen for a real reason and
every fix is the real engineering. Reuses the cutaway pool set (dig, rebar, shotcrete, cure,
finish, pipes) and adds the hero, the kids, the failures and the "undo" between attempts.
"""
import math
import random

import bpy
from mathutils import Vector

from engine import events, toy
from engine.backyard import _hide, _key
from engine.camera import facing_to
from engine.character import Character
from engine.cutaway import (CUT, HOLE, GRAVEL, SHELL, PLASTER, FLOOR_TOP, WATER_TOP, WATER_TABLE, POOL_L,
                            WaterBody, crack, muddy_water_material, key_node_value, _block)
from engine.machines import Spray, nozzle, chlorinator
from engine.sets.pool import PoolSet, HL, BACK, VALVE_X, PAD_X, PUMP, FILTER, HOOK_CAM, EXC_Y
from engine.sets.pool_story_spec import ACTIONS

V = Vector
EAST = V((HL + 0.42, CUT + 0.4, 0))           # Max's spot on the lawn, right at the cut edge
EAST_FAR = V((HL + 1.5, CUT + 0.9, 0))         # out of the way of close-ups
WEST = V((-HL - 0.42, CUT + 0.4, 0))
CAM_Y = -6.5
POOL_FLOOR = FLOOR_TOP + PLASTER


def _face_cam(spot):
    return facing_to(spot, (spot.x, CAM_Y, 0))


def _face_pool(spot):
    return facing_to(spot, (0, spot.y, 0))


class PoolStorySet(PoolSet):
    ACTIONS = ACTIONS

    def __init__(self, scene, sun, fill, bg, total):
        super().__init__(scene, sun, fill, bg, total)
        self.max = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
        self.kids = [
            Character("Kid1", {"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5",
                               "hair": "#5B3A1E", "scale": 0.6, "ponytail": True}),
            Character("Kid2", {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B",
                               "hair": "#2B1A10", "scale": 0.56}),
        ]
        for kid in self.kids:
            toy.hide_tree(kid.root, 1, True)
        self.max.place(1, WEST, _face_pool(WEST))
        self.hose = nozzle("hose_nozzle")
        self.max.hold(self.hose, "R")
        self.hose.rotation_euler = (math.radians(-30), 0, 0)
        toy.hide_tree(self.hose, 1, True)
        self.subsoil = _block("subsoil_fill", -HL, HL, CUT, BACK, -HOLE, -HOLE + GRAVEL, self.yard.m["strata"])
        toy.hide_tree(self.subsoil, 1, True)
        self.pool_water = None
        self.max.auto_blink(1, total + 400, seed=11)

    # ------------------- hero helpers -------------------

    def at(self, f, spot, facing=None):
        self.max.cut_place(f, spot, _face_cam(spot) if facing is None else facing)
        self.max.pose(f + 6)                                    # ease into it, never snap

    def walk_to(self, f0, f1, spot, face=None):
        """Walk (legs and all) to a new spot, then turn to `face` (deg)."""
        from engine import toy as _toy
        here = V(_toy.value_at(self.max.root, "location", f0))
        if (here - spot).length < 0.05:
            return
        self.max.walk(f0, f1, to=spot, facing_deg=facing_to(here, spot), step_frames=8)
        self.max.turn(f1 + 1, _face_cam(spot) if face is None else face, frames=6)

    def scratch_head(self, f0, f1):
        m = self.max
        m.pose(f0 + 4, shoulderR=(-25, 140, 0), head=(0, 14, 0))
        m.pose(f1 - 4, shoulderR=(-25, 150, 0), head=(0, 10, 0))
        m.brows(f0 + 4, 0.9)
        m.brows(f1, 0.0)
        m.pose(f1)

    def facepalm(self, f0, f1):
        m = self.max
        m.pose(f0 + 5, shoulderR=(-125, 20, 0), head=(28, 0, 0), spine=(12, 0, 0))
        m.pose(f1 - 4, shoulderR=(-125, 20, 0), head=(30, 0, 6), spine=(14, 0, 0))
        m.brows(f0 + 5, -0.6)
        m.brows(f1, 0.0)
        m.pose(f1)
        events.add(f0 + 5, "boing", gain=0.3)

    def jaw_drop(self, f0, f1):
        m = self.max
        m.pose(f0 + 4, shoulderL=(-10, -60, 0), shoulderR=(-10, 60, 0), head=(-10, 0, 0))
        m.pose(f1 - 2, shoulderL=(-10, -70, 0), shoulderR=(-10, 70, 0), head=(-12, 0, 0))
        m.key("mouth", f0 + 4, scale=(1.2, 0.6, 2.6))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f0 + 4, 1.0)
        m.brows(f1, 0.0)

    def hold_nose(self, f0, f1):
        m = self.max
        m.pose(f0 + 5, shoulderR=(-130, 10, 0), head=(-8, 0, 0))
        m.pose(f1 - 4, shoulderR=(-130, 10, 0), head=(-8, 0, 8))
        m.wave(f0 + 8, f1 - 6, hand="L")
        m.brows(f0 + 5, -0.4)
        m.brows(f1, 0.0)

    def proud(self, f0, f1):
        self.max.point(f0, f1, hand="L", up_deg=45, side_deg=10)
        self.max.smile(f0 + 4, big=True)

    def hose_on(self, f0, f1, target, name, mat=None, count=26):
        """Max sprays from the hose in his hand toward `target` (world point)."""
        toy.hide_tree(self.hose, f0, False)
        toy.hide_tree(self.hose, f1 + 2, True)
        m = self.max
        m.pose(f0, shoulderR=(-55, 0, 10))
        m.pose(f1, shoulderR=(-55, 0, 6))
        src = m.root.location + V((-0.3, -0.12, 0.9))
        jet = Spray(name, mat or self.yard.m["water"], count=count, radius=0.03, seed=len(name))
        jet.run(f0 + 2, f1, source=src, target=target, spread=0.22, arc=0.3, period=9, sound="pour")

    def zzz(self, f0, f1, spot):
        mat = toy.material("snore_z", (1, 1, 1), roughness=0.5)
        for k in range(3):
            zc = bpy.data.curves.new(f"z_{f0}_{k}", "FONT")
            zc.body = "Z"
            zc.size = 0.2 + 0.06 * k
            zc.extrude = 0.012
            zc.align_x, zc.align_y = "CENTER", "CENTER"
            z = bpy.data.objects.new(f"z_{f0}_{k}", zc)
            bpy.context.scene.collection.objects.link(z)
            z.data.materials.append(mat)
            z.rotation_euler = (math.radians(90), 0, 0)
            z.visible_shadow = False
            a = f0 + 6 + k * 6
            base = spot + V((0.2, -0.1, 1.9))
            for f, off, sc in ((a, V((0, 0, 0)), 0.2), (a + 10, V((0.15, 0, 0.3 + 0.2 * k)), 1.0),
                               (f1 - 4, V((0.35, 0, 0.6 + 0.25 * k)), 1.0), (f1 - 1, V((0.4, 0, 0.7 + 0.2 * k)), 0.01)):
                z.location, z.scale = base + off, (sc, sc, sc)
                z.keyframe_insert("location", frame=f)
                z.keyframe_insert("scale", frame=f)
            toy.hide_tree(z, 1, True)
            toy.hide_tree(z, a, False)
            toy.hide_tree(z, f1, True)
        events.add(f0 + 6, "snore", duration=max(10, f1 - f0 - 10), gain=0.7)

    def wet(self, f, radius):
        key_node_value(self.yard.m["strata"], "wet_radius", f, radius)

    def murk(self, f, amount):
        key_node_value(self.yard.m["water"], "murk", f, amount)

    # ------------------- the ladder -------------------

    def a_dig(self, i, b, e):
        super().a_dig(i, b, e)
        self.rig.shots.pop()                                     # re-frame with Max in shot
        self.rig.shot(b, e, cam_from=(0.6, -7.4, 0.6), cam_to=(1.2, -7.0, 0.4), aim_from=(0.9, 1.4, -0.8),
                      aim_to=(1.0, 1.2, -1.0), lens=20, fstop=8.0)
        self.at(b, EAST, _face_pool(EAST))
        self.proud(b + 20, e - 20)
        self.max.cheer(e - 18, e - 2)

    def a_fail_soak(self, i, b, e):
        L = e - b
        exc = self.exc                                          # the excavator leaves, the spoil goes
        exc.drive(b + 2, b + 50, V((12.0, EXC_Y, 0)))
        exc.run_engine(self.dig_frames[0] - 10, b + 50)
        toy.hide_tree(exc.root, b + 52, True)
        _hide(self.yard.pile, e, True)
        peak = b + int(L * 0.42)
        soak = WaterBody("soak_water", -HL + 0.02, HL - 0.02, BACK - 0.02, -HOLE, muddy_water_material())
        soak.show(b + 6)
        soak.level(b + 6, -HOLE + 0.01)
        soak.level(peak, -0.75)
        soak.level(e - 6, -HOLE + 0.04)
        soak.show(e, False)
        self.wet(b, 0.0)
        self.wet(peak - 4, 0.05)
        self.wet(e - 4, 1.25)
        self.at(b, EAST, _face_pool(EAST))
        self.hose_on(b + 4, peak, V((1.2, CUT + 0.7, -1.0)), "soak_hose", mat=muddy_water_material())
        self.scratch_head(peak + 4, e - 2)
        self.rig.shot(b, e, cam_from=(1.0, -6.8, -0.3), cam_to=(1.1, -6.2, -0.45), aim_from=(0.9, 0.6, -1.0),
                      aim_to=(1.0, 0.6, -1.1), lens=20, fstop=8.0)

    def a_plain_shell(self, i, b, e):
        toy.hide_tree(self.subsoil, b, False)
        plain = toy.noise_material("plain_concrete", toy.srgb("#A7A49D"), toy.srgb("#C3C0B8"), scale=60,
                                   roughness=0.9, bump=0.2)
        z0 = -HOLE + GRAVEL
        self.plain = [
            _block("plain_floor", -HL, HL, CUT, BACK, z0, z0 + SHELL, plain),
            _block("plain_west", -HL, -HL + SHELL, CUT, BACK - SHELL, z0 + SHELL, 0, plain),
            _block("plain_east", HL - SHELL, HL, CUT, BACK - SHELL, z0 + SHELL, 0, plain),
            _block("plain_back", -HL, HL, BACK - SHELL, BACK, z0 + SHELL, 0, plain),
        ]
        span = e - b - 10
        for k, p in enumerate(self.plain):
            f = b + 4 + int(span * k / len(self.plain))
            _hide(p, 0, True)
            _hide(p, f, False)
            _key(p, f, scale=V((1, 1, 0.05)) if p.name != "plain_floor" else V((0.05, 1, 1)))
            _key(p, f + max(6, span // 4), scale=V((1, 1, 1)))
        self.at(b, EAST, _face_pool(EAST))
        self.hose_on(b + 2, e - 8, V((HL - 0.35, CUT + 0.8, -0.9)), "plain_spray",
                     mat=toy.material("wet_concrete", toy.srgb("#6E6D69"), roughness=0.3))
        self.max.smile(e - 8, big=True)
        self.rig.shot(b, e, cam_from=(2.6, -4.6, -0.3), cam_to=(2.0, -4.0, -0.5), aim_from=(1.6, 0.4, -1.0),
                      aim_to=(1.4, 0.4, -1.1), lens=24, fstop=8.0)

    def a_fail_crack(self, i, b, e):
        L = e - b
        full, crk = b + int(L * 0.35), b + int(L * 0.4)
        self.crack_water = WaterBody("crack_water", -HL + SHELL, HL - SHELL, BACK - SHELL, FLOOR_TOP,
                                     self.yard.m["water"])
        cw = self.crack_water
        cw.show(b + 4)
        cw.level(b + 4, FLOOR_TOP + 0.01)
        cw.level(full, -0.4)
        cw.level(crk + 4, -0.42)
        cw.level(e - 4, FLOOR_TOP + 0.25)
        self.cracks = []
        leak_mat = self.yard.m["water"]
        for k, (x, zt, zb, out) in enumerate(((-HL + 0.1, -0.15, FLOOR_TOP, -1), (HL - 0.1, -0.25, FLOOR_TOP, 1),
                                              (1.1, FLOOR_TOP, -HOLE + GRAVEL, 0), (-0.9, FLOOR_TOP, -HOLE + GRAVEL, 0))):
            segs, pts = crack(f"crack{k}", x, zt, zb, crk + 3 * k, frames=10, seed=k + 3, width=0.055)
            self.cracks += segs
            events.add(crk + 3 * k, "hammer", gain=0.5)          # a sharp crack
            mid = pts[len(pts) // 2]
            tgt = (mid[0] + 0.7 * out, CUT - 0.06, mid[1] - (0.5 if out else 0.7))
            leak = Spray(f"leak{k}", leak_mat, count=18, radius=0.025, seed=40 + k)
            leak.run(crk + 3 * k + 4, e - 2, source=(mid[0], CUT - 0.06, mid[1]), target=tgt, spread=0.08, arc=0.1,
                     period=8)
        self.wet(crk, 0.0)
        self.wet(e - 2, 1.1)
        self.at(b, EAST, _face_pool(EAST))
        self.hose_on(b + 2, full, V((1.0, CUT + 0.7, -0.8)), "crack_hose")
        self.facepalm(crk + 6, e - 2)
        self.rig.shot(b, e, cam_from=(1.3, -5.4, -0.4), cam_to=(1.6, -4.7, -0.5), aim_from=(1.3, 0.5, -0.9),
                      aim_to=(1.6, 0.5, -0.95), lens=20, fstop=8.0)

    def a_rebar(self, i, b, e):
        # Jackhammered out: the water drains, the cracked walls crumble into the hole in a dust cloud.
        cw = self.crack_water
        cw.level(b, cw.cur)
        cw.level(b + 8, FLOOR_TOP + 0.01)
        cw.show(b + 9, False)
        for o in self.cracks:
            _hide(o, b + 6, True)
        for k, p in enumerate(self.plain):
            f = b + 2 + 2 * k
            _key(p, f, scale=V((1, 1, 1)), location=V(p.location))
            _key(p, f + 12, scale=V((1, 1, 0.04)) if p.name != "plain_floor" else V((1, 1, 0.3)),
                 location=V(p.location) + V((0, 0, -0.6 if p.name != "plain_floor" else -0.02)))
            _hide(p, f + 13, True)
        from engine.machines import Puffs
        dust = Puffs("demolish_dust", "#B9A88E", count=14, size=0.4, seed=12)
        dust.emit(range(b + 2, b + 16, 1), lambda f: (-2.2 + 0.32 * (f - b), CUT + 0.6, -0.9), rise=0.8, life=24,
                  drift=0.5)
        for k in range(4):
            events.add(b + 2 + 3 * k, "dump", gain=0.7)
        super().a_rebar(i, b + 10, e)
        # 2. close-up: Max steps back out of the camera's way while the steel goes in
        self.at(b, EAST, _face_pool(EAST))
        self.walk_to(b + 2, b + 22, EAST_FAR, _face_pool(EAST_FAR))
        self.max.hammer(b + 30, e - 6, hand="R")

    def a_shotcrete(self, i, b, e):
        super().a_shotcrete(i, b, e)
        self.at(b, EAST_FAR, _face_pool(EAST_FAR))
        self.max.pose(b + 4, shoulderR=(-60, 0, 10), spine=(10, 0, 0))
        self.max.pose(e - 4, shoulderR=(-60, 0, 4), spine=(10, 0, 0))
        self.max.smile(e - 10, big=True)

    def a_cure(self, i, b, e):
        self.wet(b, 0.0)                                        # the soil dries out over the weeks
        self.max.cut_place(b, EAST_FAR, _face_pool(EAST_FAR))
        self.walk_to(b + 2, b + 20, EAST)
        super().a_cure(i, b, e)
        self.rig.shots.pop()
        self.rig.shot(b, e, cam_from=(1.0, -7.2, 0.3), cam_to=(1.1, -6.9, 0.25), aim_from=(1.0, 0.8, -0.8),
                      lens=20, fstop=8.0)
        seg = (e - b) / 8
        for nk in (2, 6):
            n0, n1 = b + int(seg * (nk - 0.6)), b + int(seg * (nk + 1.2))
            self.max.pose(n0)
            self.max.pose(n0 + 8, spine=(22, 0, 8), head=(38, 0, 12), shoulderL=(-10, 0, 0))
            self.max.pose(n1 - 6, spine=(22, 0, 8), head=(38, 0, 12), shoulderL=(-10, 0, 0))
            self.max.pose(n1)
            self.max.brows(n1, 1.0)
            self.max.brows(n1 + 10, 0.0)
            self.zzz(n0, n1, EAST)

    def a_finish(self, i, b, e):
        super().a_finish(i, b, e)
        self.rig.shots.pop()
        self.rig.shot(b, e, cam_from=(2.4, -4.6, -0.1), cam_to=(1.6, -4.0, -0.35), aim_from=(1.2, 0.5, -0.8),
                      aim_to=(1.0, 0.5, -0.95), lens=22, fstop=8.0)
        self.at(b, EAST, _face_pool(EAST))
        self.proud(b + int((e - b) * 0.5), e - 2)

    def a_fill(self, i, b, e):
        self.pool_water = WaterBody("pool_water", -HL + SHELL + PLASTER, HL - SHELL - PLASTER,
                                    BACK - SHELL - PLASTER, POOL_FLOOR, self.yard.m["water"], parent=self.yard.pool_root)
        pw = self.pool_water
        pw.show(b + 4)
        pw.level(b + 4, POOL_FLOOR + 0.01)
        pw.level(e, WATER_TOP)
        self.yard.caustics(b + 3, -50)
        self.yard.caustics(b + 4, POOL_FLOOR + 0.02)
        self.yard.caustics(e, WATER_TOP)
        self.at(b, EAST, _face_pool(EAST))
        self.hose_on(b + 2, e - 6, V((1.2, CUT + 0.8, -0.9)), "fill_hose")
        self.max.smile(b + 10, big=True)
        self.rig.shot(b, e, cam_from=(1.0, -6.8, -0.1), cam_to=(1.0, -6.0, -0.3), aim_from=(1.0, 0.6, -0.95),
                      lens=20, fstop=8.0)

    def a_fail_float(self, i, b, e):
        L = e - b
        pw, root = self.pool_water, self.yard.pool_root
        self.light(b, 4.2, 0.22, 900)
        self.light(b + 20, 2.0, 0.09, 520)
        self.yard.rain(b + 6, e + 2, seed=7)
        drained = b + int(L * 0.35)
        pw.level(b + 4, WATER_TOP)
        pw.level(drained, POOL_FLOOR + 0.01)
        pw.show(drained + 1, False)
        self.yard.caustics(b + 4, WATER_TOP)
        self.yard.caustics(drained, -50)
        self.yard.water_table(b + 10, WATER_TABLE)
        self.yard.water_table(e - 4, -0.9)
        lift = b + int(L * 0.5)
        root.location, root.rotation_euler = (0, 0, 0), (0, 0, 0)
        root.keyframe_insert("location", frame=lift)
        root.keyframe_insert("rotation_euler", frame=lift)
        root.location, root.rotation_euler = (0, 0, 0.5), (0, math.radians(-2.0), 0)
        root.keyframe_insert("location", frame=e - 2)
        root.keyframe_insert("rotation_euler", frame=e - 2)
        events.add(lift + 4, "dump", gain=0.7)
        self.yard.arrows("float_up", [(-1.6, -2.4), (0, -2.4), (1.6, -2.4)], 1, lift - 6, e, size=0.28)
        self.at(b, EAST, _face_cam(EAST))
        self.jaw_drop(lift + 2, e)
        self.rig.shot(b, e, cam_from=(0.9, -7.0, -0.6), cam_to=(0.9, -6.3, -0.7), aim_from=(0.9, 0, -1.15),
                      aim_to=(0.9, 0, -1.05), lens=20, fstop=8.0)

    def a_fix_valve(self, i, b, e):
        L = e - b
        root = self.yard.pool_root
        root.location, root.rotation_euler = (0, 0, 0), (0, 0, 0)      # parent new parts at rest
        toy.hide_tree(self.subsoil, b + 2, True)
        self.yard.gravel(b + 2, b + int(L * 0.4))
        self.yard.relief_valve(VALVE_X, b + int(L * 0.42))
        self.yard.label3d("RELIEF VALVE", (VALVE_X + 0.2, -0.95), b + int(L * 0.45), e, size=0.14, tilt=-6)
        settle = b + int(L * 0.55)
        root.location, root.rotation_euler = (0, 0, 0.5), (0, math.radians(-2.0), 0)
        root.keyframe_insert("location", frame=settle)
        root.keyframe_insert("rotation_euler", frame=settle)
        root.location, root.rotation_euler = (0, 0, 0), (0, 0, 0)
        root.keyframe_insert("location", frame=e - 6)
        root.keyframe_insert("rotation_euler", frame=e - 6)
        events.add(e - 6, "dump", gain=0.5)
        self.yard.water_table(settle, -0.9)
        self.yard.water_table(e, WATER_TABLE)
        self.light(settle, 2.0, 0.09, 520)
        self.light(e - 4, 4.2, 0.22, 900, color=(1.0, 0.95, 0.86))
        self.at(b, EAST, _face_cam(EAST))
        self.max.pose(e - 14, shoulderR=(-120, 30, 0), head=(-6, 0, 0))   # wipes his brow
        self.max.pose(e - 2)
        self.rig.shot(b, e, cam_from=(VALVE_X + 0.8, -3.8, -1.2), cam_to=(VALVE_X + 0.5, -3.3, -1.4),
                      aim_from=(VALVE_X + 0.3, 0, -1.6), aim_to=(VALVE_X, 0, -1.75), lens=26, fstop=8.0)

    def a_fail_green(self, i, b, e):
        L = e - b
        pw = self.pool_water
        pw.show(b)
        pw.level(b, POOL_FLOOR + 0.01)
        full = b + int(L * 0.25)
        pw.level(full, WATER_TOP)
        self.yard.caustics(b, POOL_FLOOR + 0.02)
        self.yard.caustics(full, WATER_TOP)
        self.murk(full, 0.0)
        self.murk(e - 6, 1.0)
        self.yard.caustics(e - 8, WATER_TOP)
        self.yard.caustics(e - 2, -50)                            # murky water: no more sparkle
        rnd = random.Random(8)
        leaf = toy.material("algae", toy.srgb("#3E5F1E"), roughness=0.8)
        self.algae = []
        for k in range(9):
            x = rnd.uniform(-2.4, 2.4)
            blob = toy.sphere(f"algae{k}", rnd.uniform(0.05, 0.11), (x, CUT + rnd.uniform(0.05, 0.4), WATER_TOP + 0.005),
                              scale=(1.6, 1.2, 0.25), mat=leaf, subdiv=1)
            toy.parent_keep(blob, self.yard.pool_root)
            _hide(blob, 0, True)
            _hide(blob, full + int((e - full) * (0.3 + 0.5 * k / 9)), False)
            self.algae.append(blob)
        self.at(b, EAST, _face_cam(EAST))
        self.hold_nose(full + int((e - full) * 0.45), e - 2)
        self.rig.shot(b, e, cam_from=(1.2, -5.8, -0.2), cam_to=(1.2, -5.2, -0.3), aim_from=(1.1, 0.6, -0.8),
                      aim_to=(1.1, 0.6, -0.85), lens=20, fstop=8.0)

    def a_fix_filter(self, i, b, e):
        L = e - b
        mid = b + int(L * 0.5)
        super().a_pipes(i, b, mid)
        self.rig.shots.pop()                                     # pipes shot that passes under Max: re-framed
        self.rig.shot(b, mid, cam_from=(0.2, -4.6, -1.5), cam_to=(2.8, -5.6, -0.9), aim_from=(0, 0, -1.9),
                      aim_to=(3.6, 0, -0.9), lens=24, fstop=8.0)
        self._start_flow(mid)
        self.murk(mid, 1.0)
        self.murk(e - 6, 0.0)
        for k, blob in enumerate(getattr(self, "algae", [])):
            _hide(blob, mid + int((e - mid) * (0.3 + 0.5 * k / 9)), True)
        self.yard.caustics(mid + 6, -50)
        self.yard.caustics(mid + 8, WATER_TOP)
        self.yard.label3d("PUMP", (PUMP[0], 1.0), mid + 4, e, size=0.22, tilt=-6)
        self.yard.label3d("FILTER", (FILTER[0] + 0.1, 1.6), mid + 10, e, size=0.22, tilt=6)
        duck = chlorinator("chlorine_duck")
        duck.location = (-1.2, CUT + 0.45, WATER_TOP + 0.02)
        toy.add_noise(duck, "location", 2, strength=0.012, scale=12, phase=4)
        toy.add_noise(duck, "rotation_euler", 2, strength=0.15, scale=30, phase=2)
        toy.hide_tree(duck, 1, True)
        toy.hide_tree(duck, mid + 14, False)
        events.add(mid + 14, "pop", gain=0.5)
        self.at(b, EAST, _face_cam(EAST))
        self.max.point(mid + 4, e - 2, hand="L", up_deg=60, side_deg=0)
        self.max.smile(mid + 10, big=True)
        self.rig.shot(mid, e, cam_from=(4.4, -7.2, 0.0), cam_to=(1.0, -6.6, -0.3), aim_from=(PAD_X - 1.0, 0, -0.3),
                      aim_to=(1.0, 0.6, -0.9), lens=22, fstop=8.0)

    def _cannonball(self, who, f0, start_spot, entry_x, stand_z, sound=True):
        """Run to the edge, leap into a tuck, splash down at entry_x, end standing/floating."""
        face = facing_to(start_spot, (entry_x, start_spot.y, 0))
        who.cut_place(f0, start_spot, face)
        who.pose(f0)
        edge = V((HL + 0.15, start_spot.y, 0))
        t_jump = f0 + 12
        who.walk(f0 + 1, t_jump, to=edge, facing_deg=face, step_frames=5)
        apex = V(((edge.x + entry_x) / 2, start_spot.y + 0.1, 1.0))
        land = V((entry_x, start_spot.y + 0.15, stand_z))
        who.move(t_jump, t_jump + 8, apex)
        tuck = dict(shoulderL=(-70, 0, -35), shoulderR=(-70, 0, 35), legL=(-85, 0, 0), legR=(-85, 0, 0))
        who.pose(t_jump + 4, **tuck)
        who.move(t_jump + 8, t_jump + 15, land)
        who.pose(t_jump + 15, **tuck)
        who.pose(t_jump + 24)
        events.add(t_jump, "whoosh", gain=0.6)
        if sound:
            events.add(t_jump + 15, "splash")
        splash = Spray(f"splash_{who.name}_{f0}", self.yard.m["water"], count=30, radius=0.05, seed=f0 % 97)
        at = V((entry_x, CUT + 0.3, WATER_TOP))
        splash.run(t_jump + 15, t_jump + 30, source=at, target=at + V((0, 0, 0.1)), spread=0.9, arc=1.1, period=14)
        return t_jump + 24

    def _jumpers(self, f0, f1, cheer=True):
        """Max and the kids cannonball in one after another."""
        crew = [(self.kids[0], V((HL + 0.85, CUT + 0.5, 0)), HL - 1.0, WATER_TOP - 0.95),
                (self.kids[1], V((HL + 1.25, CUT + 0.32, 0)), HL - 1.9, WATER_TOP - 0.92),
                (self.max, V((HL + 0.42, CUT + 0.4, 0)), HL - 2.9, POOL_FLOOR)]
        gap = max(14, (f1 - f0 - 40) // 3)
        last = f0
        for k, (who, spot, x, z) in enumerate(crew):
            if who is not self.max:
                toy.hide_tree(who.root, f0, False)
                who.cut_place(f0, spot, _face_cam(spot))
                who.pose(f0)
                who.cheer(f0 + 2, f0 + 2 + gap * k)
            last = self._cannonball(who, f0 + 4 + gap * k, spot, x, z)
        if cheer:
            for who, *_ in crew:
                who.cheer(last + 2, f1)
                who.smile(last + 2, big=True)

    def a_finale(self, i, b, e):
        self.light(b, 4.4, 0.24, 950, color=(1.0, 0.95, 0.86))
        self._jumpers(b, e)
        for kid in self.kids:
            kid.auto_blink(b, self.total + 400, seed=len(kid.name))
        self.rig.shot(b, e, cam_from=(2.0, -5.6, 0.15), cam_to=(1.6, -6.2, 0.3), aim_from=(2.0, 0.5, -0.2),
                      aim_to=(1.5, 0.5, -0.35), lens=20, fstop=8.0)

    # ------------------- hooks (epilogue, after the finale) -------------------

    def a_float_hook(self, i, h0, h1):
        root, pw = self.yard.pool_root, self.pool_water
        for kid in self.kids:
            toy.hide_tree(kid.root, h0, True)
        pw.show(h0, False)
        self.yard.caustics(h0 - 1, WATER_TOP)
        self.yard.caustics(h0, -50)
        self.light(h0, 2.0, 0.09, 520)
        self.yard.water_table(h0, -2.0)
        self.yard.water_table(h1, -0.85)
        self.yard.rain(h0, h1 + 2, seed=6)
        stand = V((1.3, CUT + 0.55, POOL_FLOOR))
        self.max.cut_place(h0, stand, _face_cam(stand))
        self.max.pose(h0)
        root.location, root.rotation_euler = (0, 0, 0), (0, 0, 0)
        root.keyframe_insert("location", frame=h0)
        root.keyframe_insert("rotation_euler", frame=h0 + 6)
        root.location, root.rotation_euler = (0, 0, 0.5), (0, math.radians(-2.0), 0)
        root.keyframe_insert("location", frame=h1)
        root.keyframe_insert("rotation_euler", frame=h1)
        self.max.move(h0 + 1, h1, stand + V((0, 0, 0.5)))           # rides up with his pool
        self.jaw_drop(h0 + 6, h1 + 2)
        events.add(h0 + 8, "dump", gain=0.6)
        self.yard.arrows("hook_up", [(-1.6, -2.5), (0, -2.5), (1.6, -2.5)], 1, h0 + 4, h1 + 2, size=0.3)
        self.yard.label3d("GROUNDWATER", (0, -3.0), h0 + 8, h1 + 2, size=0.4, tilt=-5)
        self.rig.shot(h0, h1, cam_from=(0.4, -6.4, -0.5), cam_to=(0.6, -5.4, -0.45), aim_from=(0.4, 0, -1.0),
                      aim_to=(0.9, 0, -0.75), lens=20, fstop=8.0, cut=True)

    def a_happy_hook(self, i, h0, h1):
        self.light(h0, 4.4, 0.24, 950, color=(1.0, 0.95, 0.86))
        self._jumpers(h0, h1, cheer=False)
        self.rig.shot(h0, h1, cam_from=(1.8, -5.6, 0.1), cam_to=(1.4, -6.2, 0.3), aim_from=(1.8, 0.5, -0.2),
                      aim_to=(1.4, 0.5, -0.35), lens=20, fstop=8.0, cut=True)
