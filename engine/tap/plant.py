"""Station C, the drinking-water treatment plant, laid out along +x and cut on the section plane y = 0:
raw-water main -> rapid-mix tank (coagulant drips in, a fast impeller) -> flocculation basin (slow paddle wheels,
specks clump into floc) -> long sedimentation basin (floc sinks into a sludge layer, clear water over the outlet
weir) -> rapid gravity filter (anthracite, sand, gravel, underdrain) -> chlorine dosing into the filtered-water
main -> covered clearwell (over-under baffles, grass on its roof) -> pump house (three centrifugal pumps, the
discharge main leaves for the water tower at +x).

The water gets cleaner along the line: murky beige-green in the tanks, clearer above the filters, crystal blue
after them. Every tank's water is see-through (water_glass) so what happens inside reads; its parts sit a few mm
behind the cut, and the small things that must read (specks, floc, germs, the chlorine plume) hug the cut face."""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush.toilet import boolean

V = Vector
TOP, WL = 0.8, 0.45                  # tank wall tops, water level in the mix / floc / settling tanks
Y1, YB = 3.2, 3.5                    # tank inside depth (into the scene), back of the back wall
FLOOR = -3.2                         # top of the tank floor slabs
RM = (0.0, 3.0)                      # rapid-mix tank (inside x range)
FL = (3.3, 15.3)                     # flocculation basin
SED = (15.6, 33.6)                   # sedimentation basin (its outlet trough at the far end)
WEIR_X = 32.0                        # the weir plate (32.0 .. 32.2); the trough beyond it
PADDLES = (6.6, 12.0)                # paddle wheel shafts (x); z = PAD_Z
PAD_Z, PAD_R = -1.4, 1.15
FI = (36.0, 43.0)                    # rapid gravity filter
FI_TOP, FI_WL = 0.5, -0.25
# filter bed, bottom up: plenum, nozzle slab, coarse gravel, fine gravel, sand, anthracite
FI_PLENUM, FI_NOZ, FI_GRAV1, FI_GRAV2, FI_SAND, FI_ANTH = -2.75, -2.6, -2.3, -2.05, -1.35, -0.95
CW = (56.0, 70.0)                    # clearwell
CW_FLOOR, CW_ROOF, CW_WL = -5.0, -0.75, -1.1
PH = (73.0, 87.0)                    # pump house (outside of the walls)
PUMPS = (76.5, 80.0, 83.5)
PUMP_Z, PUMP_Y = 1.0, 0.3
INLET = [(-60.0, 0, -1.4), (0.25, 0, -1.4)]
FLUME = [(33.3, 0, 0.25), (36.25, 0, 0.25)]
CH_Z, CH_R = -0.8, 0.35             # the filtered-water main runs shallow under the chlorine skid
CH = [(42.8, 0, -2.95), (45.0, 0, -2.95), (45.0, 0, CH_Z), (54.6, 0, CH_Z), (54.6, 0, -1.6), (56.4, 0, -1.6)]
DOSE_X = 49.0
DOSE = [(DOSE_X, 0, 0.02), (DOSE_X, 0, CH_Z + CH_R - 0.02)]
SUC = [(69.5, 0, -4.2), (71.6, 0, -4.2), (71.6, 0, -0.9), (84.6, 0, -0.9)]
HEADER = [(PUMPS[0] + 0.3, 0, 3.0), (90.5, 0, 3.0), (90.5, 0, -1.0), (260.0, 0, -1.0)]

MURKY = ("#B5B08E", "#E6E1CC", "#7F7B5E")     # raw water: beige / grey-green
SETTLED = ("#A9D0D2", "#EEF7F6", "#5E9AA6")
FILTERED = ("#B0DDEA", "#F2FBFE", "#5DAFCF")


# ------------------------------------------------------------------ small helpers

def no_occ(*obs):
    """See-through things never hide an anchor from the compositor."""
    for ob in obs:
        ob["no_occlude"] = True
    return obs[0]


def glassy(name, color, alpha, swirl=0.0, foam=None):
    """Like P.water_glass, optionally with a swirling surface (the rapid-mix tank)."""
    if name in lib._mats:
        return lib._mats[name]
    if not swirl:
        return P.water_glass(name, color, alpha=alpha, foam=foam)
    mat = P.water(name, color, foam or color, foam_amount=0.25, coord="Object", swirl=swirl, density=0,
                  scale=(1.4, 1.4, 1.4))
    nt, bsdf = lib._bsdf(mat)
    if P.PATH_TRACED:
        for link in list(bsdf.inputs["Transmission Weight"].links):
            nt.links.remove(link)
        bsdf.inputs["Transmission Weight"].default_value = 0.0
    bsdf.inputs["Alpha"].default_value = alpha
    mat.surface_render_method = "BLENDED"
    if hasattr(mat, "use_transparency_overlap"):
        mat.use_transparency_overlap = False
    return mat


def grad_glass(name, c0, c1, x0, x1, alpha):
    """See-through water whose colour runs from c0 (at object x0) to c1 (x1): murky at the settling tank's
    inlet, clear at its outlet."""
    if name in lib._mats:
        return lib._mats[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf = lib._bsdf(mat)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = x0
    mr.inputs["From Max"].default_value = x1
    nt.links.new(sep.outputs["X"], mr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*lib.hexrgb(c0), 1)
    mix.inputs["B"].default_value = (*lib.hexrgb(c1), 1)
    nt.links.new(mr.outputs["Result"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.05
    bsdf.inputs["Coat Weight"].default_value = 0.5
    bsdf.inputs["Alpha"].default_value = alpha
    mat.surface_render_method = "BLENDED"
    if hasattr(mat, "use_transparency_overlap"):
        mat.use_transparency_overlap = False
    lib._mats[name] = mat
    return mat


def cyl_y(name, cx, cz, r, y0, y1, mat=None, parent=None, n=32):
    """A closed cylinder whose axis runs along y (pump casings, motors, shafts)."""
    bm = bmesh.new()
    rings = [[bm.verts.new((cx + r * math.cos(2 * math.pi * k / n), y, cz + r * math.sin(2 * math.pi * k / n)))
              for k in range(n)] for y in (y0, y1)]
    for k in range(n):
        f = bm.faces.new((rings[0][k], rings[0][(k + 1) % n], rings[1][(k + 1) % n], rings[1][k]))
        f.smooth = True
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return lib.mesh_from_bm(name, bm, mat, parent)


def ring_y(name, cx, cz, r_in, r_out, y0, y1, mat=None, parent=None, n=48):
    """An annulus extruded along y (the open pump volute's rim, flanges)."""
    bm = bmesh.new()
    loops = []
    for r, y in ((r_out, y0), (r_out, y1), (r_in, y1), (r_in, y0)):
        loops.append([bm.verts.new((cx + r * math.cos(2 * math.pi * k / n), y, cz + r * math.sin(2 * math.pi * k / n)))
                      for k in range(n)])
    for a, b in zip(loops, loops[1:] + loops[:1]):
        for k in range(n):
            f = bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return lib.mesh_from_bm(name, bm, mat, parent)


def spin(ob, axis, period, a0=0.0, sign=1):
    """Turn ob forever about one axis: a full turn every `period` frames (linear F-curve, Cycles modifier)."""
    rot = list(ob.rotation_euler)
    for f, a in ((0, a0), (period, a0 + sign * 2 * math.pi)):
        rot[axis] = a
        ob.rotation_euler = rot
        ob.keyframe_insert("rotation_euler", index=axis, frame=f)
    for fc in lib.fcurves(ob):
        if fc.data_path == "rotation_euler" and fc.array_index == axis:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            if not fc.modifiers:
                fc.modifiers.new("CYCLES")


def bob(ob, axis, amp, period, phase):
    """A gentle endless sway of one location axis (suspended specks)."""
    base = ob.location[axis]
    loc = list(ob.location)
    for f, v in ((0, base - amp), (period // 2, base + amp), (period, base - amp)):
        loc[axis] = v
        ob.location = loc
        ob.keyframe_insert("location", index=axis, frame=phase + f)
    for fc in lib.fcurves(ob):
        if fc.data_path == "location" and fc.array_index == axis and not fc.modifiers:
            fc.modifiers.new("CYCLES")


def area(name, loc, size, energy, parent, color=(1.0, 0.97, 0.92)):
    data = bpy.data.lights.new(name, "AREA")
    data.size = size
    data.energy = energy
    data.color = color
    ob = bpy.data.objects.new(name, data)
    lib.link(ob, parent)
    ob.location = loc
    return ob


def railing(name, x0, x1, y, z, parent, step=1.6):
    yellow = lib.flat("rail_yellow", lib.hexrgb("#E2B33C"), 0.4)
    n = max(1, int(round((x1 - x0) / step)))
    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n
        lib.tube(f"{name}_post{k}", [(x, y, z), (x, y, z + 1.05)], 0.025, yellow, parent)
    for h in (0.55, 1.05):
        lib.tube(f"{name}_rail{h}", [(x0, y, z + h), (x1, y, z + h)], 0.03, yellow, parent)


def pipe(self, name, pts, r, mat, cut, flow, flow_cut, R, bend, level=0.97, carve=()):
    """A pipe cut lengthwise, running full, with grooves carved for it in the solids it passes through."""
    for solid in carve:
        boolean(solid, P.solid_tube(f"{name}_groove_{solid.name}", pts, r + 0.006, solid.data.materials[0], R,
                                    bend=bend))
    P.half_pipe(name, pts, r, mat=mat, cut_mat=cut, parent=R, bend=bend)
    w = P.pipe_water(f"{name}_w", pts, r, level=level, mat=flow, section_mat=flow_cut, parent=R, bend=bend)
    return P.resample(P.rounded(pts, bend), 0.05), w


def ride_turn(ob, path, s, e, speed, offset=0.0, normal_offset=(0, -0.01, 0), step=2):
    """P.ride, but the arrow also turns to point along the path (it climbs risers and dives under baffles)."""
    path = [V(p) for p in path]
    L = sum((b - a).length for a, b in zip(path, path[1:]))
    lib.visible(ob, 1, False)
    lib.visible(ob, s, True)
    lib.visible(ob, e + 1, False)
    prev = None
    for f in range(s, e + 1, step):
        d = ((f - s) / 30.0 * speed + offset) % L
        p, t = path[-1], path[-1] - path[-2]
        for a, b in zip(path, path[1:]):
            seg = (b - a).length
            if seg > 1e-9 and d <= seg:
                p, t = a.lerp(b, d / seg), b - a
                break
            d -= seg
        rot = -math.atan2(t.z, t.x)
        if prev is not None:
            while rot - prev > math.pi:
                rot -= 2 * math.pi
            while rot - prev < -math.pi:
                rot += 2 * math.pi
        prev = rot
        lib.key(ob, "location", f, tuple(p + V(normal_offset)), interp="LINEAR")
        lib.key(ob, "rotation_euler", f, (0, rot, 0), interp="LINEAR")


def ride_all(arrows, path, s, e, speed, normal_offset=(0, -0.01, 0)):
    pts = [V(p) for p in path]
    L = sum((b - a).length for a, b in zip(pts, pts[1:]))
    for k, a in enumerate(arrows):
        ride_turn(a, path, s, e, speed, offset=k * L / len(arrows), normal_offset=normal_offset)


# ------------------------------------------------------------------ build

def build_plant(self):
    R = self.root("plant")
    rnd = random.Random(7)
    conc, conc_old = P.concrete(), P.concrete_old()
    di = lib.flat("di_pipe", lib.hexrgb("#3F5D78"), 0.4, metallic=0.4)
    di_cut = lib.flat("di_pipe_cut", lib.hexrgb("#A9B4BD"), 0.45, metallic=0.6)
    raw_flow = P.water("raw_flow", MURKY[0], MURKY[1], speed=0.9, foam_amount=0.4)
    raw_cut = P.water_section("raw_cut", MURKY[0], MURKY[2])
    clean_flow = P.water("tap_clean_flow", P.CLEAN[0], P.CLEAN[1], speed=0.9, foam_amount=0.3)
    clean_cut = P.water_section("tap_clean_cut", P.CLEAN[0], P.CLEAN[2])

    # ---------------- ground: soil around and under every structure, cut on y = 0; turf on top
    soil = {}
    def soil_box(key, x0, x1, z1, y1=YB):
        soil[key] = P.soil_block(f"pl_soil_{key}", x0, x1, 0, y1, -400.0, z1, R, deep_below=-6.0)
        return soil[key]
    soil_box("s1", -300, -0.3, -0.04)
    soil_box("uA", -0.3, 33.9, -3.5)
    soil_box("s2", 33.9, 35.7, -0.04)
    soil_box("uB", 35.7, 43.3, -3.5)
    soil_box("s3", 43.3, 55.7, -0.04)
    soil_box("uC", 55.7, 70.3, -5.3)
    soil_box("s4", 70.3, 72.8, -0.04)
    soil_box("uD", 72.8, 87.2, -0.3)
    soil_box("s5", 87.2, 300, -0.04)
    P.soil_block("pl_soil_back", -300, 300, YB, 400, -400.0, -0.04, R, deep_below=-6.0)
    # far below the cut, in front of it: a floor, so a camera looking down past the section never sees a void
    lib.box("pl_void_floor", -400, 400, -500, 0, -401.0, -400.0, P.soil_deep(), R)
    turf = P.grass_top()
    lib.box("pl_turf_back", -300, 300, YB, 400, -0.04, 0.0, turf, R)
    for k, (xa, xb) in enumerate(((-300, -0.3), (33.9, 35.7), (43.3, 55.7), (70.3, 72.8), (87.2, 300))):
        lib.box(f"pl_turf_front{k}", xa, xb, -0.03, YB, -0.04, 0.0, turf, R)
    for k, (xa, xb, ya, yb) in enumerate(((-16, -3.2, 0, 12), (-3.2, -0.4, 2.8, 12), (-0.3, 44, YB + 0.1, 9),
                                          (43.4, 47.2, 0, 9), (51.8, 55.6, 0, 9), (47.2, 51.8, 3.4, 9),
                                          (55.7, 72.7, 0, 9), (87.3, 104, 0, 10))):
        lawn = P.lawn(f"pl_lawn{k}", xa, xb, ya, yb, parent=R, density=150, seed=60 + k)
        lawn[0].hide_render = lawn[0].hide_viewport = True     # the turf boxes already cover this ground

    _mix_floc_settle(self, R, rnd, conc, conc_old, raw_flow, raw_cut, di, di_cut, soil)
    _filter(self, R, rnd, conc, conc_old)
    _chlorine(self, R, rnd, conc, di, di_cut, clean_flow, clean_cut, soil)
    _clearwell(self, R, conc, conc_old)
    _pump_house(self, R, conc, di, di_cut, clean_flow, clean_cut, soil)

    # ---- a backdrop: an office, trees, a fence line
    P.house("pl_office", (30.0, 24.0, 0.0), w=12.0, d=7.0, h=3.4, parent=R, wall_hex="#E6E2D8", shutter_hex="#3F6E8C")
    for k, (x, y) in enumerate(((-8, 14), (6, 22), (40, 15), (52, 24), (66, 14), (95, 18), (110, 26), (-20, 30))):
        P.tree(f"pl_tree{k}", (x, y, 0), h=rnd.uniform(5.0, 7.5), parent=R, seed=k + 71)
    return R


def _mix_floc_settle(self, R, rnd, conc, conc_old, raw_flow, raw_cut, di, di_cut, soil):
    # ---------------- the concrete: one floor slab, back wall, end walls and the walls between the tanks
    x0, x1 = RM[0] - 0.3, SED[1] + 0.3
    lib.box("tk_slab", x0, x1, 0, YB, FLOOR - 0.3, FLOOR, conc, R)
    lib.box("tk_back", x0, x1, Y1, YB, FLOOR, TOP, conc, R)
    left = lib.box("tk_left", x0, RM[0], 0, Y1, FLOOR, TOP, conc, R)
    end_wall = lib.box("tk_end", SED[1], x1, 0, Y1, FLOOR, TOP, conc, R)
    lib.box("tk_wall1_lo", RM[1], FL[0], 0, Y1, FLOOR, FLOOR + 0.05, conc, R)            # port under wall 1
    lib.box("tk_wall1", RM[1], FL[0], 0, Y1, -2.4, TOP, conc, R)
    lib.box("tk_wall2_lo", FL[1], SED[0], 0, Y1, FLOOR, -2.2, conc, R)                   # slotted wall 2
    lib.box("tk_wall2_hi", FL[1], SED[0], 0, Y1, -0.6, TOP, conc, R)
    for k in range(8):
        y = 0.0 + k * 0.42
        lib.box(f"tk_slot{k}", FL[1], SED[0], y, min(Y1, y + 0.16), -2.2, -0.6, conc, R)
    for k, (a, b) in enumerate(((x0, x1),)):
        railing(f"tk_rail{k}", a + 0.2, b - 0.2, Y1 + 0.15, TOP, R)

    # ---------------- raw water main arriving from the reservoir (-x), into the mix tank low down
    path, _ = pipe(self, "raw_main", INLET, 0.35, di, di_cut, raw_flow, raw_cut, R, bend=0.6, carve=(soil["s1"], left))
    self.raw_path = path
    self.raw_arrows = [P.arrow(f"raw_arrow{k}", (0, 0, 0), (1, 0, 0), size=0.22, parent=R) for k in range(5)]

    # ---------------- rapid-mix tank: swirling murky water, a fast impeller, coagulant dripping in
    cx, cy = (RM[0] + RM[1]) / 2, 1.6
    rm_mat = glassy("rm_water", MURKY[0], 0.55, swirl=3.0, foam=MURKY[1])
    rm = P.prism("rm_water", [(RM[0] + 0.005 - cx, FLOOR + 0.005), (RM[1] - 0.005 - cx, FLOOR + 0.005),
                              (RM[1] - 0.005 - cx, WL), (RM[0] + 0.005 - cx, WL)], -cy, Y1 - 0.005 - cy, rm_mat, R,
                 cut_mat=P.water_glass("rm_cut", MURKY[2], alpha=0.42))
    rm.location = (cx, cy, 0)
    no_occ(rm)
    lib.box("rm_bridge", x0, FL[0], 1.35, 1.85, TOP, TOP + 0.18, P.steel(), R)
    lib.box("rm_gearbox", cx - 0.28, cx + 0.28, cy - 0.25, cy + 0.25, TOP + 0.18, TOP + 0.6,
            lib.flat("drive_green", lib.hexrgb("#3F7F5F"), 0.4), R, bevel=0.02)
    lib.tube("rm_motor", [(cx, cy, TOP + 0.6), (cx, cy, TOP + 1.15)], 0.2, lib.flat("motor_blue", lib.hexrgb("#2E6FA8"),
             0.35, metallic=0.3), R)
    imp = lib.empty("rm_impeller", (cx, cy, -1.9), R)
    lib.tube("rm_shaft", [(cx, cy, -1.95), (cx, cy, TOP + 0.2)], 0.045, P.steel(), R)
    blade = lib.flat("blade_steel", lib.hexrgb("#9AA3A8"), 0.3, metallic=0.85)
    lib.blob("rm_hub", 0.1, blade, (0, 0, 0), parent=imp, lumpy=0.0)
    for k in range(4):
        b = lib.box(f"rm_blade{k}", 0.06, 0.62, -0.025, 0.025, -0.13, 0.13, blade, imp, bevel=0.01)
        b.rotation_euler = (math.radians(35), 0, math.radians(90 * k))
    spin(imp, 2, 24)
    self.rm_imp = imp
    # suspended dirt: specks swaying in the murky water
    speck = lib.flat("speck", lib.hexrgb("#6E5E42"), 0.8)
    for k in range(46):
        b = lib.blob(f"rm_speck{k}", rnd.uniform(0.022, 0.04), speck,
                     (rnd.uniform(RM[0] + 0.15, RM[1] - 0.15), rnd.uniform(0.02, 0.5), rnd.uniform(FLOOR + 0.3, WL - 0.1)),
                     squash=0.8, seed=200 + k, parent=R, lumpy=0.3, subdiv=1)
        b.visible_shadow = False
        bob(b, 2, rnd.uniform(0.08, 0.2), rnd.randint(30, 60), -rnd.randint(0, 60))
        bob(b, 0, rnd.uniform(0.08, 0.2), rnd.randint(36, 70), -rnd.randint(0, 70))
    # the coagulant: a chemical tank and dosing pump beside the tank, a dosing line over the wall, drops
    hdpe = lib.flat("hdpe_white", lib.hexrgb("#ECEBE3"), 0.45)
    lib.box("coag_pad", -3.0, -0.6, 0.3, 2.6, -0.04, 0.12, conc, R)
    P.cylinder("coag_tank", (-1.9, 1.5), 0.6, 0.12, 2.0, hdpe, R)
    lib.box("coag_band", -2.52, -1.28, 0.88, 2.12, 1.4, 1.52, lib.flat("band_blue", lib.hexrgb("#2F6EA6"), 0.4), R)
    lib.box("coag_pump", -1.15, -0.75, 0.55, 0.9, 0.12, 0.45, lib.flat("pump_blue", lib.hexrgb("#2F6EA6"), 0.35), R,
            bevel=0.02)
    nz = (1.0, 0.65, 1.12)
    line = [(-0.95, 0.72, 0.45), (-0.95, 0.72, 1.3), (nz[0], 0.72, 1.3), (nz[0], nz[1], 1.3), (nz[0], nz[1], nz[2])]
    lib.tube("coag_line", line, 0.022, lib.flat("dosing_line", lib.hexrgb("#F1EFE6"), 0.3), R)
    lib.tube("coag_feed", [(-1.3, 1.5, 0.3), (-1.3, 0.72, 0.3), (-1.15, 0.72, 0.3)], 0.022,
             lib.flat("dosing_line", lib.hexrgb("#F1EFE6"), 0.3), R)
    coag = lib.flat("coagulant", lib.hexrgb("#E2B86A"), 0.15, emission=0.15)
    self.coag_drops = []
    for k in range(5):
        d = lib.blob(f"coag_drop{k}", 0.028, coag, (nz[0], nz[1], nz[2]), squash=1.35, seed=300 + k, parent=R,
                     lumpy=0.0, subdiv=2)
        d.visible_shadow = False
        P.cycle_rise(d, nz[2] - 0.03, WL + 0.01, 16, -k * 16 // 5 * 1)
        self.coag_drops.append(d)
    # the coagulant mixing in: amber clouds turning with the flow around the impeller
    self.coag_swirl = lib.empty("coag_swirl", (cx, cy, -0.8), R)
    cloud = lib.flat("coag_cloud", lib.hexrgb("#F6E6BE"), 0.6, emission=0.35, alpha=0.6)
    for k in range(5):
        a = 2 * math.pi * k / 5
        c = lib.blob(f"coag_cloud{k}", rnd.uniform(0.28, 0.4), cloud,
                     (0.95 * math.cos(a), 0.95 * math.sin(a), rnd.uniform(-0.9, 0.9)), squash=0.6,
                     seed=320 + k, parent=self.coag_swirl, lumpy=0.45, subdiv=2)
        c.scale = (1.6, 0.9, 1.0)
        c.rotation_euler = (0, 0, a + math.pi / 2)
        c.visible_shadow = False
        no_occ(c)
    spin(self.coag_swirl, 2, 60)
    self.coag_swirl.scale = (0.01, 0.01, 0.01)
    lib.key(self.coag_swirl, "scale", 1, (0.01, 0.01, 0.01))
    for d in self.coag_drops:
        lib.visible(d, 1, False)
    self.anchor("plant", "coagulant", (nz[0], nz[1] - 0.05, nz[2] - 0.07))

    # ---------------- flocculation basin: slow paddle wheels, specks clumping into floc
    fl_mat = P.water_glass("fl_water", MURKY[0], alpha=0.38, foam=MURKY[1])
    fl = P.prism("fl_water", [(FL[0] + 0.005, FLOOR + 0.005), (FL[1] - 0.005, FLOOR + 0.005), (FL[1] - 0.005, WL),
                              (FL[0] + 0.005, WL)], 0.0, Y1 - 0.005, fl_mat, R,
                 cut_mat=P.water_glass("fl_cut", MURKY[2], alpha=0.36))
    no_occ(fl)
    board = lib.flat("paddle_wood", lib.hexrgb("#8C6A46"), 0.6)
    arm = lib.flat("paddle_arm", lib.hexrgb("#59636A"), 0.35, metallic=0.7)
    self.wheels = []
    for i, px in enumerate(PADDLES):
        cyl_y(f"fl_shaft{i}", px, PAD_Z, 0.07, 0.15, Y1, P.steel(), R)
        w = lib.empty(f"fl_wheel{i}", (px, 0, PAD_Z), R)
        for k in range(6):
            a = math.radians(60 * k)
            b = lib.box(f"fl_board{i}_{k}", PAD_R - 0.3, PAD_R, 0.22, 1.1, -0.05, 0.05, board, w, bevel=0.012)
            b.rotation_euler = (0, -a, 0)
            for y in (0.26, 1.05):
                b = lib.box(f"fl_arm{i}_{k}_{y:.2f}", 0.08, PAD_R - 0.05, y - 0.035, y + 0.035, -0.03, 0.03, arm, w)
                b.rotation_euler = (0, -a, 0)
        cyl_y(f"fl_hub{i}", 0, 0, 0.16, 0.18, 1.12, arm, w)
        lib.box(f"fl_chain{i}", px - 0.14, px + 0.14, Y1 - 0.16, Y1 - 0.005, PAD_Z, TOP + 0.05,
                lib.flat("guard_yellow", lib.hexrgb("#E2B33C"), 0.45), R)
        lib.box(f"fl_drive{i}", px - 0.3, px + 0.3, Y1 - 0.2, YB, TOP, TOP + 0.45,
                lib.flat("drive_green", lib.hexrgb("#3F7F5F"), 0.4), R, bevel=0.02)
        spin(w, 1, 300, a0=math.radians(25 * i), sign=-1)
        self.wheels.append(w)
    # floc: clusters of specks that drift together and grow into fluffy flakes during the floc shot
    self.flocs = []
    floc_mat = lib.flat("floc", lib.hexrgb("#E2CFA2"), 0.9, emission=0.08, alpha=0.72)
    spots = []
    tries = 0
    while len(spots) < 20 and tries < 5000:
        tries += 1
        p = (rnd.uniform(FL[0] + 0.35, FL[1] - 0.35), rnd.uniform(FLOOR + 0.45, WL - 0.3))
        if (all(math.hypot(p[0] - q[0], p[1] - q[1]) > 0.8 for q in spots)
                and all(abs(math.hypot(p[0] - px, p[1] - PAD_Z) - PAD_R) > 0.3 for px in PADDLES)):
            spots.append(p)
    for k, (x, z) in enumerate(spots):
        drift = lib.empty(f"floc_drift{k}", (x, 0.04, z), R)
        core = lib.blob(f"floc{k}", rnd.uniform(0.17, 0.24), floc_mat, (0, 0, 0), squash=0.7, seed=400 + k,
                        parent=drift, lumpy=0.6, subdiv=3)
        no_occ(core)
        core.visible_shadow = False
        bits = []
        for j in range(6):
            a = rnd.uniform(0, 2 * math.pi)
            r = rnd.uniform(0.18, 0.4)
            b = lib.blob(f"floc{k}_bit{j}", rnd.uniform(0.022, 0.034), speck, (r * math.cos(a), rnd.uniform(-0.02, 0.1),
                         r * math.sin(a)), squash=0.8, seed=500 + k * 7 + j, parent=drift, lumpy=0.3, subdiv=1)
            b.visible_shadow = False
            bits.append(b)
        self.flocs.append((drift, core, bits))
    bpy.context.view_layer.update()
    pk = min(range(len(spots)), key=lambda i: math.hypot(spots[i][0] - 8.7, spots[i][1] + 1.3))
    self.anchor("plant", "floc", (spots[pk][0], 0.0, spots[pk][1]), parent=self.flocs[pk][1])
    # the paddle label rides a board of the first wheel; floc() picks the board that is up-right at its callout
    self.paddle_anchor = self.anchor("plant", "paddle", (PADDLES[0], 0.18, PAD_Z), parent=self.wheels[0])
    for drift, core, bits in self.flocs:
        lib.key(core, "scale", 1, (0.25, 0.25, 0.25))

    # ---------------- sedimentation basin: floc sinks into sludge, clear water slides over the outlet weir
    sed_mat = grad_glass("sed_water", MURKY[0], SETTLED[0], SED[0] + 1, WEIR_X - 2, 0.45)
    sed = P.prism("sed_water", [(SED[0] + 0.005, FLOOR + 0.005), (WEIR_X - 0.005, FLOOR + 0.005), (WEIR_X - 0.005, WL),
                                (SED[0] + 0.005, WL)], 0.0, Y1 - 0.005, sed_mat, R,
                  cut_mat=grad_glass("sed_cut", MURKY[2], SETTLED[2], SED[0] + 1, WEIR_X - 2, 0.36))
    no_occ(sed)
    sludge = lib.material("Ground106", scale=1.0, tint=(0.36, 0.27, 0.17), rough=0.25, name="tap_sludge")
    # the sludge blanket: thick at the inlet end, thin toward the weir; it grows during the settle shot
    self.sludge = P.prism("sed_sludge", [(SED[0] + 0.01, 0.0), (WEIR_X - 0.01, 0.0), (WEIR_X - 0.01, 0.22),
                                         (SED[0] + 6.0, 0.62), (SED[0] + 0.01, 0.95)], -0.006, Y1 - 0.01, sludge, R)
    self.sludge.location.z = FLOOR + 0.004
    self.sludge.scale.z = 0.15
    lib.key(self.sludge, "scale", 1, (1, 1, 0.15))
    flake = lib.flat("sed_flake", lib.hexrgb("#D6C190"), 0.9, emission=0.05, alpha=0.8)
    for k in range(110):
        u = rnd.random() ** 1.8                      # more flakes near the inlet, fewer toward the weir
        x = SED[0] + 0.4 + u * (WEIR_X - SED[0] - 1.2)
        b = lib.blob(f"sed_flake{k}", rnd.uniform(0.08, 0.13), flake, (x, rnd.uniform(0.02, 0.3), WL - 0.2),
                     squash=0.6, seed=600 + k, parent=R, lumpy=0.6, subdiv=2)
        no_occ(b)
        b.visible_shadow = False
        bottom = FLOOR + 0.25 + max(0.0, 0.7 * (1 - (x - SED[0]) / 8.0))
        P.cycle_rise(b, WL - 0.15 - u * 0.6, bottom, rnd.randint(150, 230), -rnd.randint(0, 230))
    # outlet: the weir plate, a trough beyond it, a sheet of clear water spilling over
    lib.box("sed_weir", WEIR_X, WEIR_X + 0.2, 0, Y1, -0.05, WL - 0.05, P.steel(), R)
    lib.box("sed_trough_block", WEIR_X, SED[1], 0, Y1, FLOOR, -0.05, conc, R)
    trough = P.water("sed_trough_w", SETTLED[0], SETTLED[1], speed=0.4, coord="Object", foam_amount=0.35)
    P.prism("sed_trough_water", [(WEIR_X + 0.205, -0.045), (SED[1] - 0.005, -0.045), (SED[1] - 0.005, 0.2),
                                 (WEIR_X + 0.205, 0.2)], 0.0, Y1 - 0.005, trough, R,
            cut_mat=P.water_section("sed_trough_cut", SETTLED[0], SETTLED[2]))
    sheet = P.water("sed_sheet", "#9FD0DE", "#F2FBFF", speed=-0.9, coord="Object", foam_amount=0.45,
                    scale=(18.0, 18.0, 6.0), axis=2)
    lib.box("sed_spill", WEIR_X + 0.2, WEIR_X + 0.24, 0.02, Y1 - 0.02, 0.18, WL - 0.03, sheet, R)
    self.sed_arrows = [P.arrow(f"sed_arrow{k}", (0, 0, 0), (1, 0, 0), size=0.28, parent=R) for k in range(4)]
    self.sed_path = [(SED[0] + 0.6, 0, WL - 0.35), (WEIR_X - 0.5, 0, WL - 0.35), (WEIR_X + 0.1, 0, WL + 0.02)]
    self.anchor("plant", "sludge", (SED[0] + 3.6, -0.02, FLOOR + 0.2))

    # ---------------- the flume from the trough to the filter
    self.flume_path, _ = pipe(self, "flume", FLUME, 0.2, di, di_cut,
                              P.water("settled_flow", SETTLED[0], SETTLED[1], speed=1.0, foam_amount=0.35),
                              P.water_section("settled_cut", SETTLED[0], SETTLED[2]), R, bend=0.3, level=0.1,
                              carve=(end_wall,))


def _filter(self, R, rnd, conc, conc_old):
    x0, x1 = FI
    lib.box("fi_slab", x0 - 0.3, x1 + 0.3, 0, YB, FLOOR - 0.3, FLOOR, conc, R)
    lib.box("fi_back", x0 - 0.3, x1 + 0.3, Y1, YB, FLOOR, FI_TOP, conc, R)
    self.fi_left = lib.box("fi_left", x0 - 0.3, x0, 0, Y1, FLOOR, FI_TOP, conc, R)
    self.fi_right = lib.box("fi_right", x1, x1 + 0.3, 0, Y1, FLOOR, FI_TOP, conc, R)
    boolean(self.fi_left, P.solid_tube("fi_left_hole", FLUME, 0.206, conc, R, bend=0.3))
    railing("fi_rail", x0 - 0.2, x1 + 0.2, Y1 + 0.15, FI_TOP, R)
    # the bed: each layer a block whose cut face shows its grain
    anth = lib.material("Gravel023", scale=3.2, tint=(0.16, 0.16, 0.18), rough=0.35, name="anthracite")
    sand = lib.material("Ground054", scale=2.2, tint=(1.0, 0.9, 0.72), name="filter_sand")
    fine = lib.material("Gravel023", scale=2.4, tint=(0.95, 0.9, 0.82), name="gravel_fine")
    coarse = lib.material("Gravel023", scale=0.9, tint=(0.85, 0.82, 0.78), name="gravel_coarse")
    lib.box("fi_noz_slab", x0, x1, 0, Y1, FI_PLENUM, FI_NOZ, conc_old, R)
    lib.box("fi_grav1", x0, x1, 0, Y1, FI_NOZ, FI_GRAV1, coarse, R)
    lib.box("fi_grav2", x0, x1, 0, Y1, FI_GRAV1, FI_GRAV2, fine, R)
    lib.box("fi_sand", x0, x1, 0, Y1, FI_GRAV2, FI_SAND, sand, R)
    lib.box("fi_anth", x0, x1, 0, Y1, FI_SAND, FI_ANTH, anth, R)
    noz = lib.flat("nozzle", lib.hexrgb("#D9DCD8"), 0.4)
    for k in range(13):
        x = x0 + 0.3 + k * (x1 - x0 - 0.6) / 12
        P.revolve_half(f"fi_noz{k}", [(0.0, 0.0), (0.035, 0.0), (0.05, 0.13), (0.0, 0.13)],
                       (x, 0.2, FI_PLENUM - 0.13), noz, None, R, n=16, full=True)
    # water: on top of the bed (clearer than settled), and filtered water in the plenum under it
    top = P.water_glass("fi_water", FILTERED[0], alpha=0.42, foam=FILTERED[1])
    no_occ(P.prism("fi_water", [(x0 + 0.005, FI_ANTH + 0.003), (x1 - 0.005, FI_ANTH + 0.003), (x1 - 0.005, FI_WL),
                                (x0 + 0.005, FI_WL)], 0.0, Y1 - 0.005, top, R,
                   cut_mat=P.water_glass("fi_cut", FILTERED[2], alpha=0.34)))
    plen = P.water_glass("fi_plenum", P.CLEAN[0], alpha=0.4, foam=P.CLEAN[1])
    no_occ(P.prism("fi_plenum_w", [(x0 + 0.005, FLOOR + 0.005), (x1 - 0.005, FLOOR + 0.005),
                                   (x1 - 0.005, FI_PLENUM - 0.003), (x0 + 0.005, FI_PLENUM - 0.003)], 0.0, Y1 - 0.005,
                   plen, R, cut_mat=P.water_glass("fi_plenum_cut", P.CLEAN[2], alpha=0.32)))
    # settled water pours in from the flume
    tw = P.fall("fi_pour", SETTLED[0])
    P.stream("fi_pour", (x0 + 0.2, 0.12, FLUME[-1][2] - 0.05), (0.7, 0, 0), 0.32, radius=0.07, mat=tw, parent=R,
             flat=1.6)
    P.foam("fi_pour_foam", (x0 + 0.42, 0.12, FI_WL), 0.18, parent=R, seed=33)
    # specks: some already trapped in the anthracite and the top of the sand; more sink and stop during the shot
    speck = lib.flat("speck", lib.hexrgb("#6E5E42"), 0.8)
    for k in range(70):
        z = rnd.uniform(FI_SAND - 0.25, FI_ANTH - 0.05)
        b = lib.blob(f"fi_trapped{k}", rnd.uniform(0.016, 0.03), speck, (rnd.uniform(x0 + 0.1, x1 - 0.1), -0.008, z),
                     squash=0.8, seed=700 + k, parent=R, lumpy=0.3, subdiv=1)
        b.scale.y = 0.4
        b.visible_shadow = False
    self.fi_fallers = []
    for k in range(34):
        x = rnd.uniform(x0 + 0.2, x1 - 0.2)
        b = lib.blob(f"fi_fall{k}", rnd.uniform(0.024, 0.036), speck, (x, -0.012, FI_WL - 0.1), squash=0.8,
                     seed=760 + k, parent=R, lumpy=0.3, subdiv=1)
        b.scale.y = 0.45
        b.visible_shadow = False
        self.fi_fallers.append((b, x, rnd.uniform(FI_WL - 0.15, FI_ANTH + 0.25),
                                rnd.uniform(FI_SAND + 0.1, FI_ANTH - 0.02) if k % 3 else rnd.uniform(FI_SAND - 0.2, FI_SAND + 0.1),
                                rnd.random()))
    self.fi_arrows = [P.arrow(f"fi_arrow{k}", (0, 0, 0), (1, 0, 0), size=0.2, parent=R) for k in range(10)]
    self.anchor("plant", "sand", (x0 + 2.4, -0.02, (FI_GRAV2 + FI_SAND) / 2))
    self.anchor("plant", "gravel", (x0 + 4.6, -0.02, (FI_NOZ + FI_GRAV2) / 2))


def _chlorine(self, R, rnd, conc, di, di_cut, clean_flow, clean_cut, soil):
    # the filtered-water main: from the filter's plenum, under the chlorine skid, into the clearwell
    self.ch_path, ch_w = pipe(self, "fw_main", CH, CH_R, di, di_cut, clean_flow, clean_cut, R, bend=0.6,
                              carve=(self.fi_right, soil["s3"]))
    self.ch_arrows = [P.arrow(f"ch_arrow{k}", (0, 0, 0), (1, 0, 0), size=0.18, parent=R) for k in range(6)]
    # the chlorine skid on the lawn above the main: a hypochlorite tank, a dosing pump, the line down to the main
    lib.box("cl_pad", 47.4, 51.6, 0.25, 3.2, -0.04, 0.14, conc, R)
    P.cylinder("cl_tank", (50.4, 2.1), 0.55, 0.14, 1.35, lib.flat("cl_tank", lib.hexrgb("#E8E6A8"), 0.4), R)
    lib.box("cl_tank_band", 49.83, 50.97, 1.53, 2.67, 0.95, 1.06, lib.flat("band_black", lib.hexrgb("#2B2E30"), 0.5), R)
    lib.box("cl_pump", 48.4, 49.0, 0.7, 1.15, 0.14, 0.55, lib.flat("pump_blue", lib.hexrgb("#2F6EA6"), 0.35), R,
            bevel=0.02)
    line_mat = lib.flat("cl_line", lib.hexrgb("#D9DE8A"), 0.3)
    lib.tube("cl_feed", [(49.9, 2.1, 0.35), (49.0, 1.0, 0.35)], 0.025, line_mat, R)
    lib.tube("cl_line_up", [(48.7, 0.9, 0.55), (48.7, 0.9, 0.8), (DOSE_X, 0.9, 0.8), (DOSE_X, 0.03, 0.8),
                            (DOSE_X, 0.03, 0.02)], 0.028, line_mat, R)
    sign = lib.flat("hazard_yellow", lib.hexrgb("#F2C230"), 0.4)
    lib.box("cl_sign", 50.15, 50.65, 1.53, 1.55, 0.45, 0.75, sign, R)
    cl_sol = P.water("cl_solution", "#E3EC9A", "#FBFDE9", speed=0.5, foam_amount=0.2)
    P.half_pipe("cl_line_dn", DOSE, 0.035, mat=line_mat, cut_mat=lib.flat("cl_line_cut", lib.hexrgb("#EEF1C8"), 0.4),
                parent=R, bend=0.05)
    P.pipe_water("cl_line_dn_w", DOSE, 0.035, level=0.97, mat=cl_sol,
                 section_mat=P.water_section("cl_sol_cut", "#E3EC9A", "#B9C86A"), parent=R, bend=0.05)
    boolean(soil["s3"], P.solid_tube("cl_groove", DOSE, 0.041, soil["s3"].data.materials[0], R, bend=0.05))
    # the injection quill, and the plume of chlorine mixing into the flow (hugging the cut face)
    lib.tube("cl_quill", [(DOSE_X, 0.03, CH_Z + CH_R), (DOSE_X, 0.03, CH_Z + 0.12)], 0.026, P.steel(), R)
    plume = lib.flat("cl_plume", lib.hexrgb("#E6FF8A"), 0.6, emission=0.6, alpha=0.22)
    self.plume = lib.empty("cl_plume_root", (DOSE_X, -0.02, CH_Z + 0.1), R)
    prnd = random.Random(81)
    for k in range(14):
        t = k / 13
        r = 0.05 + 0.17 * t
        b = lib.blob(f"cl_plume{k}", r, plume, (0.08 + 1.5 * t + prnd.uniform(-0.05, 0.05), 0,
                     -0.02 - 0.12 * t + prnd.uniform(-0.04, 0.04)), squash=1.0, seed=800 + k, parent=self.plume,
                     lumpy=0.45, subdiv=2)
        b.scale = (1.7, 0.06, 1.0)
        b.visible_shadow = False
        no_occ(b)
    self.plume.scale = (0.001, 1, 1)
    lib.key(self.plume, "scale", 1, (0.001, 1, 1))
    # germs riding the flow, which vanish once they pass the chlorine
    germ = lib.flat("germ", lib.hexrgb("#3FA845"), 0.45, emission=0.5)
    self.germs = []
    for k in range(34):
        g = lib.blob(f"germ{k}", rnd.uniform(0.045, 0.06), germ, (0, 0, 0), squash=0.6, seed=850 + k, parent=R,
                     lumpy=0.35, subdiv=2)
        g.scale = (1.8, 0.25, 1.0)
        g.visible_shadow = False
        lib.visible(g, 1, False)
        self.germs.append((g, rnd.uniform(-0.2, 0.2), rnd.uniform(DOSE_X + 0.2, DOSE_X + 0.8), rnd.random()))
    self.anchor("plant", "chlorine", (DOSE_X + 0.06, -0.04, CH_Z + 0.14))


def _clearwell(self, R, conc, conc_old):
    x0, x1 = CW
    lib.box("cw_slab", x0 - 0.3, x1 + 0.3, 0, YB, CW_FLOOR - 0.3, CW_FLOOR, conc, R)
    lib.box("cw_back", x0 - 0.3, x1 + 0.3, Y1, YB, CW_FLOOR, CW_ROOF, conc, R)
    self.cw_left = lib.box("cw_left", x0 - 0.3, x0, 0, Y1, CW_FLOOR, CW_ROOF, conc, R)
    self.cw_right = lib.box("cw_right", x1, x1 + 0.3, 0, Y1, CW_FLOOR, CW_ROOF, conc, R)
    lib.box("cw_roof", x0 - 0.3, x1 + 0.3, 0, YB, CW_ROOF, -0.45, conc, R)
    P.soil_block("cw_cover", x0 - 0.3, x1 + 0.3, 0, YB, -0.45, -0.04, R)
    lib.box("cw_turf", x0 - 0.3, x1 + 0.3, -0.03, YB, -0.04, 0.0, P.grass_top(), R)
    # over-under baffles: the water snakes through, so every drop stays long enough for the chlorine to work
    boolean(self.cw_left, P.solid_tube("cw_left_hole", CH, CH_R + 0.006, conc, R, bend=0.6))
    self.baffles = [lib.box("cw_baffle1", 59.4, 59.6, -0.006, Y1, CW_FLOOR, -1.9, conc_old, R),
                    lib.box("cw_baffle2", 62.9, 63.1, -0.006, Y1, -3.9, CW_ROOF, conc_old, R),
                    lib.box("cw_baffle3", 66.4, 66.6, -0.006, Y1, CW_FLOOR, -1.9, conc_old, R)]
    w = P.water_glass("cw_water", "#8FD3F0", alpha=0.36, foam="#E6F7FF")
    no_occ(P.prism("cw_water", [(x0 + 0.005, CW_FLOOR + 0.005), (x1 - 0.005, CW_FLOOR + 0.005), (x1 - 0.005, CW_WL),
                                (x0 + 0.005, CW_WL)], 0.0, Y1 - 0.005, w, R,
                   cut_mat=P.water_glass("cw_cut", "#3E98C0", alpha=0.3)))
    self.cw_path = [(56.5, 0, -1.55), (59.5, 0, -1.5), (61.3, 0, -1.6), (61.3, 0, -4.4), (64.7, 0, -4.4),
                    (64.7, 0, -1.5), (68.3, 0, -1.5), (68.3, 0, -4.2), (69.6, 0, -4.2)]
    self.cw_path = P.resample(P.rounded(self.cw_path, 0.6), 0.05)
    self.cw_arrows = [P.arrow(f"cw_arrow{k}", (0, 0, 0), (1, 0, 0), size=0.3, parent=R) for k in range(9)]
    # on the grass roof: two mushroom vents and an access hatch
    vent = lib.flat("vent_white", lib.hexrgb("#E7E9E6"), 0.4)
    for k, x in enumerate((58.4, 67.6)):
        lib.tube(f"cw_vent{k}", [(x, 1.6, -0.05), (x, 1.6, 0.85)], 0.12, vent, R)
        lib.blob(f"cw_vent_cap{k}", 0.3, vent, (x, 1.6, 0.9), squash=0.45, parent=R, lumpy=0.0)
    lib.box("cw_hatch", 62.4, 63.6, 1.0, 2.2, -0.04, 0.18, conc, R)
    lib.box("cw_hatch_lid", 62.5, 63.5, 1.1, 2.1, 0.18, 0.24, lib.flat("hatch_steel", lib.hexrgb("#7D878C"), 0.35,
            metallic=0.8), R)
    area("cw_light", (63.0, 1.4, CW_ROOF - 0.15), 6.0, 2200, R)
    self.anchor("plant", "clearwell", (61.3, -0.02, -2.7))


def _pump_house(self, R, conc, di, di_cut, clean_flow, clean_cut, soil):
    x0, x1 = PH
    wall = lib.material("PaintedPlaster017", scale=0.8, tint=lib.hexrgb("#E4DED0"), name="ph_plaster")
    floor = lib.flat("ph_floor", lib.hexrgb("#7F9488"), 0.35, coat=0.3)
    slab = lib.box("ph_slab", x0 - 0.2, x1 + 0.2, 0, 5.2, -0.3, 0.12, conc, R)
    lib.box("ph_floor", x0 + 0.3, x1 - 0.3, -0.004, 4.9, 0.12, 0.15, floor, R)
    lib.box("ph_left", x0, x0 + 0.3, 0, 5.2, 0.15, 4.6, wall, R)
    right = lib.box("ph_right", x1 - 0.3, x1, 0, 5.2, 0.15, 4.6, wall, R)
    lib.box("ph_back", x0, x1, 4.9, 5.2, 0.15, 4.6, wall, R)
    lib.box("ph_roof", x0 - 0.3, x1 + 0.3, 0, 5.5, 4.6, 4.85, conc, R)
    lib.box("ph_parapet", x0 - 0.3, x1 + 0.3, 5.3, 5.5, 4.85, 5.15, conc, R)
    glass = lib.flat("window_glass", lib.hexrgb("#9DB8CC"), 0.05, coat=1.0)
    for k, x in enumerate((75.0, 80.0 - 0.9, 84.0 - 0.9)):
        lib.box(f"ph_win{k}", x, x + 1.8, 4.88, 4.9, 3.1, 4.1, glass, R)
    lib.box("ph_crane", x0 + 0.3, x1 - 0.3, 2.3, 2.6, 4.2, 4.45, lib.flat("crane_yellow", lib.hexrgb("#E2B33C"), 0.4), R)
    lib.box("ph_panel", 85.0, 86.3, 4.5, 4.9, 0.15, 2.2, lib.flat("panel_grey", lib.hexrgb("#C9CDCF"), 0.35), R,
            bevel=0.02)
    lib.box("ph_panel_lamp", 85.3, 85.5, 4.48, 4.5, 1.8, 1.9, lib.flat("lamp_green", lib.hexrgb("#38D16A"), 0.3,
            emission=4.0), R)
    area("ph_light", ((x0 + x1) / 2, 2.0, 4.4), 10.0, 2600, R)
    area("ph_fill", ((x0 + x1) / 2, -3.0, 2.5), 8.0, 500, R).rotation_euler = (math.radians(-80), 0, 0)
    # suction from the clearwell, under the floor, up into each pump
    self.suc_path, _ = pipe(self, "suction", SUC, 0.25, di, di_cut, clean_flow, clean_cut, R, bend=0.5,
                            carve=(self.cw_right, soil["s4"], soil["uD"]))
    casing = lib.flat("pump_casing", lib.hexrgb("#2F5D8A"), 0.35, metallic=0.3)
    motor = lib.flat("pump_motor", lib.hexrgb("#7E8B93"), 0.4, metallic=0.4)
    bronze = lib.flat("impeller_bronze", lib.hexrgb("#C08A4A"), 0.25, metallic=0.9)
    skid = P.dark_steel()
    self.pump_paths, self.impellers = [], []
    for i, px in enumerate(PUMPS):
        rise = [(px, 0, -0.9), (px, 0, PUMP_Z - 0.45)]
        pipe(self, f"suc_riser{i}", rise, 0.17, di, di_cut, clean_flow, clean_cut, R, bend=0.1,
             carve=(soil["uD"], slab))
        lib.box(f"pump_skid{i}", px - 0.85, px + 0.85, 0.05, 2.3, 0.15, 0.32, skid, R)
        lib.box(f"pump_foot{i}", px - 0.3, px + 0.3, 0.2, 0.5, 0.32, PUMP_Z - 0.4, casing, R)
        # the volute, open toward the camera: the impeller turning inside
        ring_y(f"pump_rim{i}", px, PUMP_Z, 0.5, 0.57, 0.12, 0.5, casing, R)
        cyl_y(f"pump_back{i}", px, PUMP_Z, 0.57, 0.5, 0.56, casing, R)
        cyl_y(f"pump_bearing{i}", px, PUMP_Z, 0.13, 0.56, 0.78, casing, R)
        imp = lib.empty(f"pump_imp{i}", (px, PUMP_Y, PUMP_Z), R)
        cyl_y(f"pump_hub{i}", 0, 0, 0.09, -0.1, 0.15, bronze, imp)
        cyl_y(f"pump_shroud{i}", 0, 0, 0.46, 0.15, 0.18, bronze, imp)
        for k in range(6):
            for j, (r0, r1, da) in enumerate(((0.08, 0.27, 0.0), (0.25, 0.45, 24.0))):
                v = lib.box(f"pump_vane{i}_{k}_{j}", r0, r1, -0.1, 0.15, -0.017, 0.017, bronze, imp)
                v.rotation_euler = (0, math.radians(60 * k + da), 0)
        # the coupling between pump and motor, turning with the shaft
        cyl_y(f"pump_coupling{i}", 0, 0, 0.16, 0.48, 0.53, P.steel(), imp)
        for k in range(4):
            a = math.radians(90 * k + 45)
            lib.blob(f"pump_bolt{i}_{k}", 0.025, skid, (0.12 * math.cos(a), 0.5, 0.12 * math.sin(a)), parent=imp,
                     lumpy=0.0, subdiv=1)
        spin(imp, 1, 36, a0=math.radians(20 * i), sign=-1)
        self.impellers.append(imp)
        # the motor
        cyl_y(f"pump_motor{i}", px, PUMP_Z, 0.42, 0.85, 1.95, motor, R)
        for k in range(7):
            ring_y(f"pump_fin{i}_{k}", px, PUMP_Z, 0.41, 0.45, 0.95 + k * 0.14, 0.99 + k * 0.14, motor, R, n=32)
        cyl_y(f"pump_fan{i}", px, PUMP_Z, 0.44, 1.95, 2.18, lib.flat("fan_cowl", lib.hexrgb("#5D686F"), 0.45), R)
        lib.box(f"pump_tbox{i}", px - 0.16, px + 0.16, 1.2, 1.5, PUMP_Z + 0.4, PUMP_Z + 0.62, motor, R, bevel=0.01)
        for sx in (-1, 1):
            lib.box(f"pump_mfoot{i}{sx}", px + sx * 0.38 - 0.08, px + sx * 0.38 + 0.08, 0.95, 1.85, 0.32,
                    PUMP_Z - 0.3, motor, R)
        # discharge: up out of the top of the volute to the header
        dis = [(px + 0.3, 0, PUMP_Z + 0.42), (px + 0.3, 0, 3.0)]
        pipe(self, f"discharge{i}", dis, 0.16, di, di_cut, clean_flow, clean_cut, R, bend=0.1)
        for z in (PUMP_Z + 0.75, 2.4):
            P.revolve_half(f"pump_flange{i}_{z:.1f}", [(0.16, -0.03), (0.23, -0.03), (0.23, 0.03), (0.16, 0.03)],
                           (px + 0.3, 0, z), skid, skid, R, n=24)
        lib.blob(f"pump_valve{i}", 0.2, skid, (px + 0.3, 0.2, 1.95), squash=1.2, parent=R, lumpy=0.0)
        self.pump_paths.append(P.resample([V(p) for p in dis], 0.05))
    self.header_path, _ = pipe(self, "header", HEADER, 0.24, di, di_cut, clean_flow, clean_cut, R, bend=0.7,
                               carve=(right, soil["s5"]))
    self.ph_arrows = [P.arrow(f"ph_arrow{k}", (0, 0, 0), (1, 0, 0), size=0.2, parent=R) for k in range(12)]
    self.anchor("plant", "pump", (PUMPS[1] - 0.36, -0.03, PUMP_Z + 0.45))


# ------------------------------------------------------------------ shots

def plant_arrive(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(17.0, 1.2, -0.8), width=11.0, yaw=-66, pitch=18, lens=30),
              dict(center=(19.0, 1.2, -0.8), width=10.0, yaw=-62, pitch=17, lens=30))
    ride_all(self.raw_arrows, self.raw_path, s, e, 1.6)
    ride_all(self.sed_arrows, self.sed_path, s, e, 0.6)
    events.add(s, "water_rush", duration=e - s, gain=0.5)
    events.add(s, "pour", duration=e - s, gain=0.4)


def coagulant(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(0.9, 0.6, -0.5), width=5.4, yaw=14, pitch=12, lens=32),
              dict(center=(1.2, 0.6, -0.6), width=4.6, yaw=8, pitch=10, lens=32))
    for d in self.coag_drops:
        lib.visible(d, s, True)
    lib.tween(self.coag_swirl, "scale", s, s + int((e - s) * 0.5), (0.4, 0.4, 0.4), (1, 1, 1), "out")
    ride_all(self.raw_arrows, self.raw_path, s, e, 1.6)
    events.add(s, "hum", duration=e - s, gain=0.5)
    events.add(s, "water_rush", duration=e - s, gain=0.6)
    for f in range(s + 4, e, 16):
        events.add(f, "splash", gain=0.15)


def floc(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(7.7, 0.3, -1.5), width=4.8, yaw=4, pitch=4, lens=50),
              dict(center=(8.1, 0.3, -1.5), width=4.0, yaw=6, pitch=4, lens=50))
    rnd = random.Random(11)
    n = e - s
    # wheel 0 turns by -2 pi every 300 frames from frame 0 (spin); a world angle phi sits at local phi + theta
    theta = -2 * math.pi * ((s + int(n * 0.1)) % 300) / 300
    phi = math.radians(40) + theta
    self.paddle_anchor.location = ((PAD_R - 0.15) * math.cos(phi), 0.18, (PAD_R - 0.15) * math.sin(phi))
    for drift, core, bits in self.flocs:
        x = drift.location.x
        lib.key(drift, "location", s, (x, 0.04, drift.location.z), interp="LINEAR")
        lib.key(drift, "location", e, (x + 0.35, 0.04, drift.location.z + 0.05), interp="LINEAR")
        f0 = s + int(n * rnd.uniform(0.05, 0.2))
        lib.tween(core, "scale", f0, e - int(n * 0.12), (0.25, 0.25, 0.25), (1, 1, 1), "smooth")
        for b in bits:
            t0 = s + int(n * rnd.uniform(0.0, 0.35))
            t1 = t0 + int(n * rnd.uniform(0.3, 0.5))
            lib.tween(b, "location", t0, t1, tuple(b.location), (0, b.location.y, 0), "in")
            lib.key(b, "scale", t1 - 4, (1, 1, 1))
            lib.key(b, "scale", t1, (0.01, 0.01, 0.01))
    events.add(s, "hum", duration=n, gain=0.35)
    events.add(s, "water_rush", duration=n, gain=0.3)


def settle(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(19.0, 0.3, -1.85), width=5.2, yaw=-8, pitch=6, lens=40),
              dict(center=(20.2, 0.3, -1.85), width=5.2, yaw=-4, pitch=6, lens=40))
    lib.tween(self.sludge, "scale", s, e, (1, 1, 0.15), (1, 1, 1.0), "linear")
    ride_all(self.sed_arrows, self.sed_path, s, e, 0.9)
    events.add(s, "water_rush", duration=e - s, gain=0.3)
    events.add(s + (e - s) // 2, "pour", duration=(e - s) // 2, gain=0.4)


def filter(self, s, e):    # noqa: A001 (the beat id)
    self.on_station("plant", s, e)
    x0, x1 = FI
    self.shot("plant", s, e, dict(center=(39.5, 0.3, -1.95), width=5.9, yaw=8, pitch=6, lens=35),
              dict(center=(39.6, 0.3, -2.0), width=5.4, yaw=4, pitch=5, lens=35))
    n = e - s
    for b, x, z0, z1, ph in self.fi_fallers:
        t0 = s + int(n * 0.75 * ph)
        t1 = t0 + int(n * 0.3)
        lib.visible(b, 1, False)
        lib.visible(b, t0, True)
        lib.key(b, "location", t0, (x, -0.012, z0), interp="CUBIC", easing="EASE_OUT")
        lib.key(b, "location", t1, (x + 0.05, -0.012, z1), interp="CONSTANT")
    cols = [x0 + 0.6 + k * (x1 - x0 - 1.2) / 4 for k in range(5)]
    for k, a in enumerate(self.fi_arrows):
        x = cols[k % 5]
        path = [(x, -0.01, FI_WL - 0.1), (x, -0.01, FLOOR + 0.12)]
        ride_turn(a, path, s, e, 0.45, offset=(k // 5) * 1.2 + (k % 5) * 0.37, normal_offset=(0, 0, 0))
    events.add(s, "pour", duration=n, gain=0.6)
    events.add(s, "water_rush", duration=n, gain=0.35)


def chlorine(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(DOSE_X + 0.42, 0.0, -0.62), width=1.5, yaw=6, pitch=4, lens=50),
              dict(center=(DOSE_X + 0.62, 0.0, -0.64), width=1.4, yaw=9, pitch=4, lens=50))
    n = e - s
    lib.tween(self.plume, "scale", s, s + int(n * 0.45), (0.15, 1, 1), (1, 1, 1), "out")
    ride_all(self.ch_arrows, self.ch_path, s, e, 0.8)
    # germs ride the main at 0.5 m/s; each pops out of existence a little after the chlorine reaches it
    speed = 0.5 / 30
    z = CH_Z
    span = (e + 10) - (s - 160)
    for k, (g, dz, x_die, _r) in enumerate(self.germs):
        born = s - 160 + int(span * k / len(self.germs))
        x_born = 45.6
        die = born + int((x_die - x_born) / speed)
        if die < s:
            continue
        lib.visible(g, max(1, born), True)
        lib.key(g, "location", born, (x_born, -0.016, z + dz), interp="LINEAR")
        lib.key(g, "location", die, (x_die, -0.016, z + dz), interp="LINEAR")
        lib.key(g, "scale", die - 5, (1.8, 0.25, 1.0))
        lib.key(g, "scale", die, (2.3, 0.3, 1.3), interp="CUBIC", easing="EASE_IN")
        lib.key(g, "scale", die + 5, (0.02, 0.02, 0.02))
        lib.visible(g, die + 6, False)
    events.add(s, "water_rush", duration=n, gain=0.45)
    events.add(s + 4, "bubbles", duration=n - 4, gain=0.35)
    events.add(s, "hum", duration=n, gain=0.25)


def clearwell(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(63.0, 0.5, -2.2), width=15.5, yaw=14, pitch=14, lens=30),
              dict(center=(63.6, 0.5, -2.3), width=14.0, yaw=18, pitch=12, lens=30))
    ride_all(self.cw_arrows, self.cw_path, s, e, 1.6)
    ride_all(self.ch_arrows, self.ch_path, s, e, 0.8)
    events.add(s, "water_rush", duration=e - s, gain=0.4)


def pumps(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(79.4, 0.6, 1.2), width=6.2, yaw=16, pitch=8, lens=30),
              dict(center=(80.6, 0.6, 1.5), width=6.6, yaw=22, pitch=10, lens=30))
    arrows = list(self.ph_arrows)
    paths = [self.header_path] * 4 + [p for p in self.pump_paths for _ in range(2)] + [self.suc_path] * 2
    groups = {}
    for a, p in zip(arrows, paths):
        groups.setdefault(id(p), (p, []))[1].append(a)
    for p, arr in groups.values():
        ride_all(arr, p, s, e, 1.8)
    events.add(s, "pump", duration=e - s, gain=0.9)
    events.add(s, "hum", duration=e - s, gain=0.6)
    events.add(s, "water_rush", duration=e - s, gain=0.4)


SHOTS = (build_plant, plant_arrive, coagulant, floc, settle, filter, chlorine, clearwell, pumps)
