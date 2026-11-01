"""
"Where your toilet water goes": every station (diorama) and every shot of the film (runs inside Blender).

Stations sit far apart along world X, each under its own root empty (root y = 0, never rotated, so the
section plane y = 0 is shared). A beat's shot is a method named after the beat id; it gets the beat's
frame span (s, e) from the voiceover timings and stages the camera plus whatever moves in that shot.
Only the station on screen is rendered (the others are hidden per beat).
"""
import math

import bpy
from mathutils import Vector

from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush import toilet as WC
from engine.flush.toilet import boolean, cut_front

V = Vector

# 1 km apart: farther than the camera's clip distance, so no station's ground ever shows in another's shot
STATION_X = {"house": 0.0, "clog": 1000.0, "street": 2000.0, "lift": 3000.0, "plant": 4000.0, "macro": 5000.0,
             "river": 6000.0, "trench": 7000.0}

# station A (house): the toilet stands on the bathroom floor; the drain drops, bends and runs downhill
FLOOR_Z = 0.18
DRAIN_R = 0.1
DRAIN = [(0.25, 0, 0.06), (0.25, 0, -1.25), (0.62, 0, -1.3), (4.5, 0, -1.455), (18.5, 0, -2.015)]
SWAMP_X = 4.5


def carve(solid, pts, radius, cut_mat=None, bend=None):
    """Cut a pipe-shaped groove (radius) into a solid along pts, for a half pipe lying in the cut face."""
    t = P.solid_tube(f"{solid.name}_groove", pts, radius + 0.003, cut_mat or solid.data.materials[0],
                     solid.parent, bend=bend if bend is not None else radius * 3)
    return boolean(solid, t)


class Film:
    def __init__(self, scene, cam, total):
        self.scene, self.cam, self.total = scene, cam, total
        self.roots = {}
        self.on = {}            # station -> [(s, e)] spans it is on screen
        self.restore_fstop = []  # frames where a shallow-focus shot hands the default f-stop back

    # ------------------------------------------------------------------ helpers

    def root(self, key):
        r = lib.empty(f"ST_{key}", (STATION_X[key], 0, 0))
        self.roots[key] = r
        return r

    def W(self, key, x, y, z):
        """World position of a station-local point."""
        return (STATION_X[key] + x, y, z)

    def shot(self, key, s, e, a, b=None, cut=True, ease="smooth"):
        """Camera move inside station `key`: a/b are pose() dicts with station-local centres."""
        def world(p):
            p = dict(p)
            c = p["center"]
            p["center"] = self.W(key, *c)
            return p
        self.cam.shot(s, e, world(a), world(b) if b else None, cut=cut, ease=ease)

    # ------------------------------------------------------------------ station A: the house

    def build_house(self):
        R = self.root("house")
        conc, plaster = P.concrete(), lib.material("PaintedPlaster017", scale=0.8, tint=lib.hexrgb("#EFE7D6"),
                                                   name="plaster_in")
        outside = lib.material("PaintedPlaster017", scale=0.8, tint=lib.hexrgb("#EDE3CF"), name="plaster_out")
        tiles = P.tiles()
        cutface = lib.flat("wall_cut", lib.hexrgb("#D9D2C4"), 0.8)
        # ground: under the house, and the yard (two versions: the swamp groove only, and the full drain)
        under = P.soil_block("soil_under", -6.6, 1.0, 0, 6, -400.0, -0.2, R, deep_below=-2.4)
        carve(under, DRAIN[:4], DRAIN_R)
        yard_swamp = P.soil_block("soil_yard_swamp", 1.0, 19.5, 0, 6, -400.0, -0.04, R, deep_below=-2.4)
        carve(yard_swamp, DRAIN[1:4], DRAIN_R)
        yard_full = P.soil_block("soil_yard_full", 1.0, 19.5, 0, 6, -400.0, -0.04, R, deep_below=-2.4)
        carve(yard_full, DRAIN[1:], DRAIN_R)
        self.yard_swamp, self.yard_full = yard_swamp, yard_full
        slab = lib.box("slab", -6.6, 1.5, -0.006, 5.6, -0.2, FLOOR_Z - 0.03, conc, R)
        carve(slab, DRAIN[:2], DRAIN_R)
        footing = lib.box("footing", 1.0, 1.5, -0.006, 5.6, -0.9, -0.19, conc, R)
        floor = lib.box("bath_floor", -6.6, 1.2, -0.004, 5.4, FLOOR_Z - 0.03, FLOOR_Z, tiles, R)
        carve(floor, [(0.25, 0, 0.3), (0.25, 0, -0.1)], DRAIN_R)
        P.lawn("lawn", 1.5, 19.5, 0, 6, z=0.0, parent=R, density=380)
        # the house, cut through the middle: walls, ceiling, gable roof
        wall_h = 2.75
        lib.box("wall_right", 1.2, 1.5, 0, 5.6, FLOOR_Z, wall_h, outside, R)
        lib.box("wall_left", -6.6, -6.3, 0, 5.6, FLOOR_Z, wall_h, outside, R)
        lib.box("wall_back", -6.6, 1.5, 5.3, 5.6, FLOOR_Z, wall_h, outside, R)
        lib.box("wall_part", -1.35, -1.22, 0, 5.3, FLOOR_Z, wall_h, plaster, R)
        lib.box("bath_back", -1.22, 1.2, 2.1, 2.22, FLOOR_Z, wall_h, tiles, R)
        lib.box("ceiling", -6.6, 1.5, 0, 5.6, wall_h, wall_h + 0.18, plaster, R)
        lib.box("room_left_floor", -6.3, -1.35, 0.0, 5.3, FLOOR_Z, FLOOR_Z + 0.012,
                lib.flat("oak_floor", lib.hexrgb("#B88A5A"), 0.45), R)
        win = lib.flat("window_glass", lib.hexrgb("#9DB8CC"), 0.05, coat=1.0)
        lib.box("bath_window", 1.49, 1.52, 3.0, 4.2, 1.3, 2.2, win, R)
        lib.box("bath_window_frame", 1.5, 1.53, 2.92, 4.28, 1.22, 2.28, lib.flat("trim_white", (0.92, 0.92, 0.9), 0.4),
                R)
        roof = lib.material("RoofingTiles006", scale=0.9, tint=(1.0, 0.62, 0.48), name="roof_tiles")
        self._gable_roof(R, -7.0, 1.95, 0, 6.0, wall_h + 0.18, 1.6, roof, cutface)
        # bathroom details: the toilet, a towel rail, a mirror; the cut faces of the walls
        wc_root = lib.empty("wc_root", (0.0, 0, FLOOR_Z), R)
        self.wc = WC.build(wc_root)
        lib.box("towel_rail", -0.9, -0.4, 2.05, 2.08, 1.1, 1.13, P.steel(), R)
        lib.box("towel", -0.85, -0.45, 2.0, 2.05, 0.75, 1.12, lib.flat("towel", lib.hexrgb("#6FA8C9"), 0.9), R)
        lib.box("mirror", -0.2, 0.5, 2.08, 2.1, 1.3, 2.0, lib.flat("mirror", (0.8, 0.85, 0.9), 0.02, metallic=1.0), R)
        # the drain: house pipe, then (shot 5) the full run downhill to the street
        self.drain_in = P.half_pipe("drain_house", DRAIN[:4], DRAIN_R, parent=R)
        self.water_in = P.pipe_water("drain_house_w", DRAIN[1:4], DRAIN_R, level=-0.05, parent=R,
                                     mat=P.dirty_flow(0.9))
        self.drop_w = P.pipe_water("drain_drop_w", DRAIN[:2], DRAIN_R, level=0.6, parent=R,
                                   mat=P.dirty_flow(1.6, "dirty_drop"))
        self.drain_ext = P.half_pipe("drain_ext", DRAIN[3:], DRAIN_R, parent=R)
        self.water_ext = P.pipe_water("drain_ext_w", DRAIN[3:], DRAIN_R, level=-0.05, parent=R,
                                      mat=P.dirty_flow(0.9))
        # the swamp: water leaves the open pipe end, the soil darkens and a puddle spreads on the lawn
        mud = lib.material("Ground106", scale=0.7, tint=(0.36, 0.27, 0.2), rough=0.12, name="wet_mud")
        wet = lib.blob("wet_soil", 1.0, mud, (SWAMP_X + 0.35, 0, -1.3), squash=0.85, seed=4, parent=R,
                       lumpy=0.22)
        clip = lib.box("wet_clip", -60, 60, -60, 60, -0.06, 60, mud, R)
        boolean(wet, clip)
        cut_front(wet, mud, keep_y0=-0.004)
        self.wet = wet
        self.puddle = lib.blob("puddle", 1.0, P.water("puddle_w", "#5B5440", "#8A8166", speed=0.05,
                                                     foam_amount=0.2, coord="Object"),
                               (SWAMP_X + 0.9, 0.9, 0.05), squash=0.02, seed=9, parent=R, lumpy=0.25)
        cut_front(self.puddle, lib.flat("puddle_cut", lib.hexrgb("#4A4433"), 0.2), keep_y0=0.0)
        # flow arrows riding the water in the long run (shot 5)
        self.arrows = []
        for k in range(3):
            a = P.arrow(f"arrow_drain{k}", (0, -0.006, 0), (1, 0, 0), size=0.05, parent=R)
            self.arrows.append(a)
        return R

    def _gable_roof(self, parent, x0, x1, y0, y1, z0, rise, roof_mat, cut_mat):
        import bmesh
        xm = (x0 + x1) / 2
        th = 0.16
        bm = bmesh.new()
        prof = [(x0, z0), (xm, z0 + rise), (x1, z0), (x1 - th * 1.2, z0), (xm, z0 + rise - th * 1.3),
                (x0 + th * 1.2, z0)]
        front = [bm.verts.new((x, y0, z)) for x, z in prof]
        back = [bm.verts.new((x, y1, z)) for x, z in prof]
        n = len(prof)
        for k in range(n):
            f = bm.faces.new((front[k], front[(k + 1) % n], back[(k + 1) % n], back[k]))
            f.material_index = 0
        f = bm.faces.new(list(reversed(front)))
        f.material_index = 1
        f = bm.faces.new(back)
        f.material_index = 1
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        ob = lib.mesh_from_bm("roof", bm, None, parent)
        ob.data.materials.append(roof_mat)
        ob.data.materials.append(cut_mat)
        # the attic's back wall (gable) so the cut roof is not see-through
        bm = bmesh.new()
        vs = [bm.verts.new((x0 + 0.3, y1 - 0.4, z0)), bm.verts.new((x1 - 0.3, y1 - 0.4, z0)),
              bm.verts.new((xm, y1 - 0.4, z0 + rise - 0.25))]
        bm.faces.new(vs)
        lib.mesh_from_bm("attic_back", bm, lib.flat("attic", lib.hexrgb("#8C7A62"), 0.8), parent)
        return ob

    # ------------------------------------------------------------------ station A2: a clog in a flat pipe

    def build_clog(self):
        """A flat stretch of house line in an open trench, seen from above; a wad of paper is stuck in it."""
        R = self.root("clog")
        z = -0.3
        pts = [(-2.4, 0, z), (2.4, 0, z)]
        cutter = lambda: P.sweep_box_cutter("clog_trench", pts, 0.55, DRAIN_R + 0.12, 4.0, R)   # noqa: E731
        block = P.soil_block("clog_soil", -2.4, 2.4, -0.3, 1.8, -400, -0.04, R)
        boolean(block, cutter())
        turf = lib.box("clog_turf", -2.4, 2.4, -0.3, 1.8, -0.04, 0.0, P.grass_top(), R)
        boolean(turf, cutter())
        P.lawn("clog_lawn", -2.4, 2.4, 0.56, 1.8, parent=R, density=520, seed=7)[0].hide_render = True
        self.clog_pipe_root = lib.empty("clog_pivot", (0, 0, z), R)
        piv = self.clog_pipe_root
        P.half_pipe("clog_pipe", [(-2.4, 0, 0), (2.4, 0, 0)], DRAIN_R, mode="top", parent=piv)
        back = lib.empty("clog_back", (0, 0, -DRAIN_R), piv)       # scaled in z: the backed-up level rises
        self.clog_back = back
        P.pipe_water("clog_back_w", [(-2.4, 0, DRAIN_R), (-0.06, 0, DRAIN_R)], DRAIN_R, level=0.2, mode="top",
                     parent=back, mat=P.dirty_flow(0.1, "dirty_slow"))
        self.clog_front = P.pipe_water("clog_front_w", [(0.06, 0, 0), (2.4, 0, 0)], DRAIN_R, level=0.06,
                                       mode="top", parent=piv, mat=P.dirty_flow(0.9))
        paper = lib.flat("tissue", lib.hexrgb("#ECE9E0"), 0.85)
        self.clump = lib.empty("clump", (0, 0, -DRAIN_R + 0.035), piv)
        for k, (dx, dy, dz, r) in enumerate(((-0.02, 0.0, 0.0, 0.04), (0.025, 0.02, 0.006, 0.035),
                                            (0.0, -0.025, 0.03, 0.032), (0.04, -0.01, 0.03, 0.026),
                                            (-0.035, 0.02, 0.034, 0.026))):
            lib.blob(f"clump{k}", r, paper, (dx, dy, dz), squash=0.8, seed=11 + k, parent=self.clump, lumpy=0.35)
        return R

    # ------------------------------------------------------------------ shots 1-6

    def toilet(self, s, e):
        self.on_station("house", s, e)
        self.shot("house", s, e, dict(center=(0.02, 0, FLOOR_Z + 0.38), width=0.95, yaw=24, pitch=16, lens=40),
                  dict(center=(0.04, 0, FLOOR_Z + 0.3), width=0.78, yaw=20, pitch=14, lens=40), cut=True)
        events.add(s, "water_rush", duration=e - s + 30, gain=0.9)
        events.add(s + 2, "splash", gain=0.5)

    def drop(self, s, e):
        self.on_station("house", s, e)
        self.shot("house", s, e, dict(center=(0.04, 0, FLOOR_Z + 0.3), width=0.78, yaw=20, pitch=14, lens=40),
                  dict(center=(0.4, 0, -0.55), width=3.4, yaw=16, pitch=9, lens=32), cut=False, ease="out")
        events.add(s, "water_rush", duration=e - s, gain=0.7)

    def turn(self, s, e):
        self.on_station("house", s, e)
        self.shot("house", s, e, dict(center=(0.5, 0, -1.05), width=1.7, yaw=22, pitch=8, lens=30),
                  dict(center=(2.9, 0, -1.25), width=2.0, yaw=26, pitch=8, lens=30))
        events.add(s, "water_rush", duration=e - s, gain=0.6)

    def swamp(self, s, e):
        self.on_station("house", s, e)
        self.swamp_span = (s, e)
        self.shot("house", s, e, dict(center=(SWAMP_X + 0.4, 0, -0.75), width=3.8, yaw=30, pitch=20, lens=30),
                  dict(center=(SWAMP_X + 0.6, 0.3, -0.5), width=3.6, yaw=18, pitch=28, lens=30))
        n = e - s
        lib.tween(self.wet, "scale", s + 4, s + int(n * 0.85), (0.15, 0.15, 0.15), (0.95, 0.95, 0.95), "out")
        lib.tween(self.puddle, "scale", s + int(n * 0.35), e, (0.05, 0.05, 1.0), (1.3, 1.1, 1.0), "out")
        events.add(s, "pour", duration=n, gain=0.6)
        events.add(s + int(n * 0.4), "bubbles", duration=int(n * 0.6), gain=0.4)

    def keep_going(self, s, e):
        self.on_station("house", s, e)
        self.extend_from = s
        self.shot("house", s, e, dict(center=(4.6, 0, -1.25), width=3.2, yaw=24, pitch=10, lens=28),
                  dict(center=(11.5, 0, -1.55), width=4.2, yaw=22, pitch=10, lens=28), ease="smooth")
        # three arrows ride the water downhill
        path = P.resample(DRAIN[3:], 0.1)
        L = sum((b - a).length for a, b in zip(path, path[1:]))
        for k, a in enumerate(self.arrows):
            lib.visible(a, 1, False)
            lib.visible(a, s, True)
            lib.visible(a, e + 1, False)
            for f in range(s, e + 1, 3):
                d = ((f - s) / 30.0 * 0.9 + k * 1.6) % L
                p = _along(path, d)
                lib.key(a, "location", f, (p.x, -0.006, p.z + DRAIN_R * 0.05), interp="LINEAR")
        events.add(s, "water_rush", duration=e - s, gain=0.6)

    def clog(self, s, e):
        self.on_station("clog", s, e)
        n = e - s
        mid = s + int(n * 0.48)
        piv = self.clog_pipe_root
        lib.key(piv, "rotation_euler", s, (0, 0, 0))
        lib.tween(piv, "rotation_euler", mid, mid + 16, (0, 0, 0), (0, math.radians(3.0), 0), "smooth")
        lib.tween(self.clog_back, "scale", s, mid, (1, 1, 0.9), (1, 1, 1.9), "out")
        lib.tween(self.clog_back, "scale", mid + 6, e, (1, 1, 1.9), (1, 1, 0.9), "smooth")
        home = (0, 0, -DRAIN_R + 0.035)
        lib.key(self.clump, "location", mid + 6, home)
        lib.tween(self.clump, "location", mid + 8, e, home, (2.6, 0, home[2]), "in")
        self.shot("clog", s, e, dict(center=(-0.15, 0, -0.32), width=1.2, yaw=22, pitch=44, lens=40),
                  dict(center=(0.1, 0, -0.34), width=1.0, yaw=16, pitch=42, lens=40))
        events.add(s, "water_rush", duration=n, gain=0.35)
        events.add(mid + 8, "whoosh", gain=0.5)

    def finish_house(self):
        """State switches that depend on several shots: the swamp only exists in its own shot, the full drain
        from the next one on."""
        s4, e4 = getattr(self, "swamp_span", (0, -1))
        for ob in (self.drain_ext, self.water_ext, self.yard_full):
            lib.visible(ob, 1, True)
            if e4 >= s4:
                lib.visible(ob, s4, False)
                lib.visible(ob, e4 + 1, True)
        lib.visible(self.yard_swamp, 1, False)
        for ob in (self.wet, self.puddle):
            lib.visible(ob, 1, False)
        if e4 >= s4:
            lib.visible(self.yard_swamp, s4, True)
            lib.visible(self.yard_swamp, e4 + 1, False)
            for ob in (self.wet, self.puddle):
                lib.visible(ob, s4, True)
                lib.visible(ob, e4 + 1, False)

    def on_station(self, key, s, e):
        self.on.setdefault(key, []).append((s, e))


def _along(path, d):
    for a, b in zip(path, path[1:]):
        seg = (b - a).length
        if d <= seg:
            return a.lerp(b, d / seg)
        d -= seg
    return path[-1]


# The film's sound: soft water under the pipes, pours only where water falls, bubbles in the aeration tank, a low
# pump in the lift station. The loud loops (a rushing-water roar, traffic, hum) and one-shot accents read as
# noise under the narration, so they are dropped or traded for a quieter sound here, in one place.
SOUND = {"water_rush": ("pour", 0.4), "pour": ("pour", 0.6), "pump": ("pump", 0.6), "bubbles": ("bubbles", 0.7),
         "lake": ("lake", 0.8), "traffic": None, "hum": None, "creak": None, "whoosh": None, "splash": None}


def soften(log):
    out = []
    for ev in log:
        rule = SOUND.get(ev["kind"], (ev["kind"], 1.0))
        if rule is None:
            continue
        out.append(dict(ev, kind=rule[0], gain=round(ev.get("gain", 1.0) * rule[1], 3)))
    log[:] = out


def _finish(self):
    soften(events._events)
    if hasattr(self, "wet"):
        self.finish_house()
    data = self.cam.data
    for f in self.restore_fstop:
        data.dof.aperture_fstop = 4.0
        data.keyframe_insert("dof.aperture_fstop", frame=f)
    for fc in lib.fcurves(data):
        if fc.data_path == "dof.aperture_fstop":
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


Film.finish = _finish

from engine.flush import lift, nature, plant, street, trench  # noqa: E402

for _mod in (street, trench, lift, plant, nature):
    for _fn in _mod.SHOTS:
        setattr(Film, _fn.__name__, _fn)
