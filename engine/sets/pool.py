"""
POOL cutaway set — Blender builder. Executes a film's beats by ACTION name (see pool_spec.py)
inside the frame span the voiceover gave each beat. Runs inside Blender.

Usage (from engine/films/cutaway_film.py):
    ctx = PoolSet(scene, sun, fill, bg, total)
    ctx.run(beats, spans)          # beats: [{"action", ...}], spans: {index: (start, end)}
"""
import math

import bpy
from mathutils import Vector

from engine import events, toy
from engine.backyard import _hide
from engine.camera import CameraRig
from engine.cutaway import CutawayYard, CUT, POOL_L, POOL_HALF_W, HOLE, SHELL, GRAVEL, FLOOR_TOP, WATER_TABLE
from engine.machines import Excavator, Spray
from engine.sets.pool_spec import ACTIONS, beat_actions

V = Vector
HL = POOL_L / 2
BACK = CUT + POOL_HALF_W
PAD_X = 5.6
PUMP = (PAD_X - 0.45, 0.32)
FILTER = (PAD_X + 0.45, 0.2)
EXC_Y, EXC_YAW = BACK + 1.9, -90
PILE = V((5.6, BACK + 2.9, 0))
VALVE_X = -1.5
HOOK_CAM = dict(cam=(0, -6.4, -0.6), aim=(0, 0, -1.05))


class PoolSet:
    ACTIONS = ACTIONS                         # subclasses (story variants) swap in their catalogue

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.yard = CutawayYard()
        self.rig = CameraRig(blend=18)
        self.exc = Excavator(location=(10.0, EXC_Y, 0), facing_deg=EXC_YAW)
        toy.hide_tree(self.exc.root, 1, False)
        self.flow_on = False

    # ------------------- driver -------------------

    def run(self, beats, spans, epilogue_offset):
        """spans[i] = (start, end) frames of beat i. The hook beat (index 0) is staged in the
        epilogue (frames + epilogue_offset), after the finished build."""
        self.EPI = epilogue_offset
        # Flatten: a montage beat (several actions) shares its span, weighted by each action's
        # typical length; every action then runs in its own sub-span.
        self.acts, self.spans = [], []
        for i, b in enumerate(beats):
            acts = beat_actions(b)
            s, e = spans[i]
            weights = [sum(self.ACTIONS[a].get("seconds", (1, 1))) for a in acts]
            t = s
            for k, (a, w) in enumerate(zip(acts, weights)):
                end = e if k == len(acts) - 1 else t + int((e - s + 1) * w / sum(weights)) - 1
                self.acts.append(a)
                self.spans.append((t, end))
                t = end + 1
        for i, a in enumerate(self.acts):
            if self.ACTIONS[a]["kind"] in ("hook", "rewind"):
                continue
            getattr(self, f"a_{a}")(i, *self.spans[i])
        hook_b, hook_e = self.spans[0]
        getattr(self, f"a_{self.acts[0]}")(0, hook_b + epilogue_offset, hook_e + epilogue_offset)
        self.rig.build()

    def _next_is(self, i, action):
        return i + 1 < len(self.acts) and self.acts[i + 1] == action

    def light(self, f, sun_e, bg_v, fill_e, color=None):
        self.sun.data.energy = sun_e
        self.bg.default_value = bg_v
        self.fill.data.energy = fill_e
        self.sun.data.keyframe_insert("energy", frame=f)
        self.bg.keyframe_insert("default_value", frame=f)
        self.fill.data.keyframe_insert("energy", frame=f)
        if color:
            self.sun.data.color = color
            self.sun.data.keyframe_insert("color", frame=f)

    # ------------------- build actions -------------------

    def a_dig(self, i, b, e):
        yard, exc = self.yard, self.exc
        end = (self.spans[i + 1][1] if self._next_is(i, "layers") else e) - 10
        stations = [V((col["x"], EXC_Y, 0)) for col in yard.columns]
        start = b + 24
        span = end - start
        order = yard.dig_plan(2 if span >= 8 * 30 else 1)
        cycle = max(26, min(52, span // len(order)))
        exc.rest(b)
        exc.drive(b, start - 2, stations[order[0][0]])
        exc.rest(start - 2)
        tops = [col["top"] for col in yard.columns]
        bites = []
        for k, new_top in order:
            bites.append({"root": stations[k], "target": V((yard.columns[k]["x"], CUT + 0.55, tops[k]))})
            tops[k] = new_top
        timing = exc.dig_sequence(start, bites, dump_at=PILE + V((0, 0, 0.5)), yaw_deg=EXC_YAW, cycle=cycle)
        for (k, new_top), t in zip(order, timing):
            yard.bite(k, t["bite"], t["curl"], new_top)
        yard.spoil_pile(PILE, [t["dump"] for t in timing])
        self.dig_frames = (b, end)
        self.rig.shot(b, e, cam_from=(-0.6, -7.4, 0.6), cam_to=(0.5, -7.0, 0.4), aim_from=(0.2, 1.4, -0.8),
                      aim_to=(0.4, 1.2, -1.0), lens=20, fstop=8.0)

    def a_gravel(self, i, b, e):
        exc = self.exc
        exc.drive(b + 4, b + 60, V((12.0, EXC_Y, 0)))
        exc.run_engine(self.dig_frames[0] - 10, b + 60)
        toy.hide_tree(exc.root, b + 62, True)
        self.yard.gravel(b + 4, e - 10)
        self.rig.shot(b, e, cam_from=(0.6, -5.2, -0.4), cam_to=(0.3, -4.5, -0.8), aim_from=(0, 0.6, -1.6),
                      aim_to=(0, 0.6, -1.7), lens=28, fstop=8.0)

    def a_valve(self, i, b, e):
        yard = self.yard
        _hide(yard.pile, b, True)                     # spoil trucked away
        yard.relief_valve(VALVE_X, b + 6)
        yard.label3d("RELIEF VALVE", (VALVE_X + 0.15, -1.05), b + 12, e, size=0.13, tilt=-7)
        yard.arrows("gw_up", [(VALVE_X, -2.7), (VALVE_X, -2.25)], 1, b + int((e - b) * 0.45), e, size=0.2)
        self.rig.shot(b, e, cam_from=(VALVE_X + 0.4, -2.7, -1.25), cam_to=(VALVE_X + 0.2, -2.3, -1.45),
                      aim_from=(VALVE_X, 0, -1.75), aim_to=(VALVE_X, 0, -1.9), lens=30, fstop=8.0)

    def a_pipes(self, i, b, e):
        yard = self.yard
        for o in yard.equipment_pad(PAD_X):
            toy.hide_tree(o, 1, True)
            toy.hide_tree(o, b, False)
        dome = bpy.data.objects["filter_dome"]
        toy.hide_tree(dome, 1, True)
        toy.hide_tree(dome, b, False)
        z_main, z_ret = -2.25, -2.6
        q = max(6, (e - b - 12) // 4)
        yard.pipe("drain", [(0, FLOOR_TOP), (0, z_main), (PUMP[0], z_main), PUMP], b + 4, b + 4 + q)
        yard.pipe("skim", [(HL - SHELL - 0.1, -0.2), (HL + 0.35, -0.2), (HL + 0.35, z_main + 0.06)],
                  b + 4 + q, b + 4 + 2 * q)
        yard.pipe("link", [(PUMP[0] + 0.2, PUMP[1]), (FILTER[0] - 0.3, PUMP[1])], b + 4 + 2 * q, b + 6 + 2 * q)
        yard.pipe("ret", [(FILTER[0], 0.12), (FILTER[0], z_ret), (-HL - 0.4, z_ret), (-HL - 0.4, -0.6),
                          (-HL + SHELL + 0.08, -0.6)], b + 6 + 2 * q, b + 4 + 3 * q)
        grate = toy.box("drain_grate", (0.32, 0.06, 0.04), (0, CUT - 0.05, FLOOR_TOP + 0.03),
                        mat=toy.material("drain_grate", toy.srgb("#2D3238"), roughness=0.4, metallic=0.5),
                        bevel=0.005)
        toy.parent_keep(grate, yard.pool_root)
        toy.hide_tree(grate, 1, True)
        toy.hide_tree(grate, b + 4, False)
        yard.label3d("MAIN DRAIN", (0.0, -1.1), b + 8, b + int((e - b) * 0.55), size=0.18, tilt=-6)
        yard.label3d("SKIMMER", (HL - 0.5, 0.4), b + int((e - b) * 0.4), e, size=0.2, tilt=5)
        self.rig.shot(b, e, cam_from=(0.2, -4.0, -1.4), cam_to=(3.6, -5.2, -0.5), aim_from=(0, 0, -1.9),
                      aim_to=(4.4, 0, -0.6), lens=26, fstop=8.0)

    def a_rebar(self, i, b, e):
        bars = self.yard.rebar(b + 2, e - 8)
        xs = sorted({round(o.location.x, 3) for o in bars if o.name.startswith("rb_fy")})
        mid = len(xs) // 2
        zf = -HOLE + GRAVEL + SHELL / 2
        self.yard.dimension((xs[mid], zf + 0.28), (xs[mid + 1], zf + 0.28), "25 cm", b + int((e - b) * 0.5), e,
                            size=0.09)
        self.rig.shot(b, e, cam_from=(2.2, -3.4, -0.6), cam_to=(xs[mid] + 0.3, -2.2, -1.1),
                      aim_from=(1.0, 0.6, -1.4), aim_to=(xs[mid] + 0.1, 0.2, -1.5), lens=26, fstop=8.0)

    def a_shotcrete(self, i, b, e):
        self.yard.shotcrete(b + 4, e - 10)
        gun = Spray("shotcrete", toy.material("wet_concrete", toy.srgb("#6E6D69"), roughness=0.3), count=40,
                    radius=0.035)
        gun.run(b + 4, e - 8, source=(1.9, 0.8, 0.55), target=(HL - 0.35, 0.8, -0.8), spread=0.45, arc=0.15,
                sound="spray")
        self.yard.dimension((HL - SHELL, -0.75), (HL, -0.75), "20 cm", b + int((e - b) * 0.55), e, size=0.08)
        self.rig.shot(b, e, cam_from=(3.9, -3.6, -0.2), cam_to=(3.3, -2.3, -0.55), aim_from=(2.7, 0.3, -0.8),
                      aim_to=(HL - 0.1, 0.1, -0.8), lens=28, fstop=8.0)

    def a_cure(self, i, b, e):
        days = 2
        seg = (e - b) / (days * 4)
        for k in range(days * 4 + 1):
            f = b + int(seg * k)
            phase = k % 4
            self.light(f, (4.2, 1.2, 0.0, 1.2)[phase], (0.22, 0.07, 0.012, 0.07)[phase], (900, 350, 160, 350)[phase],
                       color=((1.0, 0.95, 0.86), (1.0, 0.55, 0.3), (0.4, 0.5, 1.0), (1.0, 0.6, 0.4))[phase])
            if phase == 0 and k < days * 4:
                mist = Spray(f"cure_mist{k}", self.yard.m["water"], count=18, radius=0.03, seed=20 + k)
                mist.run(f + 1, f + int(seg * 0.9), source=(-HL - 0.6, 0.7, 1.2), target=(0, 0.7, -1.2),
                         spread=1.4, arc=0.5, period=10, sound="pour")
        self.rig.shot(b, e, cam_from=(0, -7.4, 0.4), cam_to=(0, -7.1, 0.3), aim_from=(0, 0.8, -0.9), lens=20,
                      fstop=8.0)

    def a_finish(self, i, b, e):
        self.yard.finish(b + 2, e - 8)
        self.yard.ladder(b + int((e - b) * 0.6))
        self.yard.label3d("PLASTER", (-1.2, FLOOR_TOP + 0.3), b + int((e - b) * 0.6), e, size=0.17, tilt=-6)
        self.rig.shot(b, e, cam_from=(-2.6, -2.9, 0.35), cam_to=(1.6, -2.9, 0.1), aim_from=(-2.5, 0.6, -0.4),
                      aim_to=(-0.8, 0.4, -1.3), lens=26, fstop=8.0)

    def a_fill(self, i, b, e):
        self.yard.water(b + 4, e + 10)
        hose = Spray("fill_hose", self.yard.m["water"], count=30, radius=0.03, seed=9)
        hose.run(b + 4, e, source=(HL - 0.15, BACK - 0.3, 0.35), target=(HL - 1.2, BACK - 0.6, -0.9),
                 spread=0.18, arc=0.25, period=9)
        self.rig.shot(b, e, cam_from=(0, -6.8, -0.1), cam_to=(0, -6.0, -0.3), aim_from=(0, 0.6, -0.95), lens=20,
                      fstop=8.0)

    # ------------------- explainers -------------------

    def a_layers(self, i, b, e):
        lx = -HL - 1.3
        for k, (txt, z) in enumerate((("TOPSOIL", -0.22), ("CLAY", -1.15), ("SAND", -2.55), ("GROUNDWATER", -3.9))):
            self.yard.label3d(txt, (lx, z), b + 6 + k * int((e - b - 20) / 4), e, size=0.2, tilt=-5 + 4 * (k % 2))
        self.rig.shot(b, e, cam_from=(lx + 1.2, -4.6, 0.1), cam_to=(lx + 1.0, -4.4, -3.0), aim_from=(lx, 0, -0.5),
                      aim_to=(lx, 0, -3.4), lens=30, fstop=8.0)

    def a_weight(self, i, b, e):
        self.yard.arrows("weight_dn", [(-1.6, -0.75), (0, -0.75), (1.6, -0.75)], -1, b + 6, e, color="#FFD23F",
                         size=0.3)
        self.yard.arrows("gw_push", [(-1.6, -2.7), (0, -2.7), (1.6, -2.7)], 1, b + 22, e, color="#5EC8FF", size=0.24)
        self.rig.shot(b, e, cam_from=(0, -6.6, -1.0), cam_to=(0, -7.6, -1.2), aim_from=(0, 0, -1.6), lens=20,
                      fstop=8.0)

    def a_flow(self, i, b, e):
        self._start_flow(b + 4)
        self.yard.label3d("PUMP", (PUMP[0], 1.0), b + int((e - b) * 0.45), e, size=0.24, tilt=-6)
        self.yard.label3d("FILTER", (FILTER[0] + 0.1, 1.6), b + int((e - b) * 0.55), e, size=0.24, tilt=6)
        self.rig.shot(b, e, cam_from=(-0.3, -4.0, -1.5), cam_to=(4.6, -4.6, -0.2), aim_from=(0, 0, -2.0),
                      aim_to=(PAD_X, 0, 0.0), lens=26, fstop=8.0)

    def _start_flow(self, f):
        if not self.flow_on:
            self.yard.start_flow(f)
            events.add(f, "pump", duration=self.total - f)
            self.flow_on = True

    def a_cycle(self, i, b, e):
        self.rig.shot(b, e, cam_from=(1.6, -5.6, -0.3), cam_to=(0.6, -7.8, 0.0), aim_from=(1.4, 0.5, -1.0),
                      aim_to=(0.8, 0.5, -1.1), lens=20, fstop=8.0)

    # ------------------- outros -------------------

    def a_storm(self, i, b, e):
        self.yard.water_table(b, WATER_TABLE)
        self.yard.water_table(e, -2.0)
        self.light(b, 4.2, 0.22, 900)
        self.light(b + 30, 2.0, 0.09, 520)
        self.yard.rain(b + 10, e + 2, seed=5)
        self.rig.shot(b, e, cam_from=(0, -7.6, -0.7), cam_to=HOOK_CAM["cam"], aim_from=(0, 0, -1.3),
                      aim_to=HOOK_CAM["aim"], lens=20, fstop=8.0)

    def a_glamour(self, i, b, e):
        self._start_flow(b)
        self.rig.shot(b, e, cam_from=(0.8, -8.2, 0.2), cam_to=HOOK_CAM["cam"], aim_from=(0.4, 0.4, -0.8),
                      aim_to=HOOK_CAM["aim"], lens=20, fstop=8.0)

    # ------------------- hooks (staged in the epilogue) -------------------

    def a_float_hook(self, i, h0, h1):
        """Drained pool + storm + high groundwater → the whole pool lifts out of the ground."""
        yard = self.yard
        _hide(yard.water_obj, h0, True)
        _hide(yard.water_surf, h0, True)
        yard.caustics(h0 - 1, -0.15)
        yard.caustics(h0, -50)
        self.light(h0, 2.0, 0.09, 520)
        yard.water_table(h0, -2.0)
        yard.water_table(h1, -0.85)
        root = yard.pool_root
        root.location, root.rotation_euler = (0, 0, 0), (0, 0, 0)
        root.keyframe_insert("location", frame=h0)
        root.keyframe_insert("rotation_euler", frame=h0 + 6)
        root.location, root.rotation_euler = (0, 0, 0.5), (0, math.radians(-2.0), 0)
        root.keyframe_insert("location", frame=h1)
        root.keyframe_insert("rotation_euler", frame=h1)
        events.add(h0 + 8, "dump", gain=0.6)
        events.add(h0 + 30, "dump", gain=0.5)
        yard.rain(h0, h1 + 2, seed=6)
        yard.arrows("hook_up", [(-1.6, -2.5), (0, -2.5), (1.6, -2.5)], 1, h0 + 4, h1 + 2, size=0.3)
        yard.label3d("GROUNDWATER", (0, -3.0), h0 + 8, h1 + 2, size=0.42, tilt=-5)
        self.rig.shot(h0, h1, cam_from=(0, -7.2, -0.7), cam_to=HOOK_CAM["cam"], aim_from=(0, 0, -1.2),
                      aim_to=HOOK_CAM["aim"], lens=20, fstop=8.0, cut=True)

    def a_reveal_hook(self, i, h0, h1):
        """Sunny finished pool; push in from wide to the cut wall's layers (20 cm shell)."""
        self.light(h0, 4.2, 0.22, 900, color=(1.0, 0.95, 0.86))
        self.yard.water_table(h0, WATER_TABLE)
        self._start_flow(min(h0 - 30, self.total - 30))
        self.yard.dimension((HL - SHELL, -0.95), (HL, -0.95), "20 cm", h0 + int((h1 - h0) * 0.55), h1 + 2,
                            size=0.08)
        self.rig.shot(h0, h1, cam_from=(0.6, -7.0, -0.2), cam_to=(HL - 0.35, -1.7, -0.75),
                      aim_from=(0.4, 0, -0.9), aim_to=(HL - 0.1, 0, -0.85), lens=24, fstop=8.0, cut=True)

    def a_flow_hook(self, i, h0, h1):
        """The finished pool, cut open: water racing through the hidden pipes. Sunny."""
        self.light(h0, 4.2, 0.22, 900, color=(1.0, 0.95, 0.86))
        self.yard.water_table(h0, WATER_TABLE)
        self._start_flow(min(h0 - 30, self.total - 30))
        self.rig.shot(h0, h1, cam_from=(4.4, -4.4, -1.6), cam_to=(1.2, -6.2, -0.7), aim_from=(3.2, 0, -2.2),
                      aim_to=(0.4, 0, -1.2), lens=22, fstop=8.0, cut=True)
