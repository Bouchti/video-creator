"""Station E, the macro: bacteria drifting in a drop of wastewater, eating the dissolved specks.
Station F, the river: a concrete outfall in a grassy bank pours clean water into a calm river."""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from engine import events
from engine.director import lib
from engine.flush import parts as P

V = Vector


# ====================================================================== E: bacteria
def build_macro(self):
    R = self.root("macro")
    rnd = random.Random(7)
    # a murky backdrop around the drop (inside-facing sphere), lit softly
    back = bpy.data.materials.new("macro_back")
    nt, bsdf = lib._bsdf(back)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    em = nt.nodes.new("ShaderNodeEmission")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.2
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*lib.hexrgb("#1E2B22"), 1)
    ramp.color_ramp.elements[1].color = (*lib.hexrgb("#4F6347"), 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=4.0, location=(0, 0, 0))
    sph = bpy.context.active_object
    sph.name = "macro_backdrop"
    sph.data.materials.append(back)
    sph.parent = R
    sph.visible_shadow = False
    light = lib.link(bpy.data.objects.new("macro_key", bpy.data.lights.new("macro_key", "AREA")), R)
    light.data.energy = 60
    light.data.size = 1.5
    light.location = (-0.8, -1.2, 1.2)
    light.rotation_euler = (math.radians(50), 0, math.radians(-35))
    rod_mats = [lib.flat(f"bact_{c}", lib.hexrgb(c), 0.3, coat=0.6, emission=0.25)
                for c in ("#9FCF4A", "#C9D14F", "#7FBF6A", "#D6A64B")]
    floc = lib.flat("floc", lib.hexrgb("#6E5634"), 0.7)
    speck = lib.flat("speck", lib.hexrgb("#8A6A3E"), 0.6)
    self.macro_things = []
    for k in range(34):
        m = rod_mats[k % len(rod_mats)]
        loc = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.25, 0.6), rnd.uniform(-0.45, 0.45))
        if k % 3 == 0:
            ob = lib.blob(f"coccus{k}", rnd.uniform(0.018, 0.026), m, loc, seed=k, parent=R, lumpy=0.06)
        else:
            ob = lib.blob(f"rod{k}", 0.022, m, loc, seed=k, parent=R, lumpy=0.04)
            ob.scale = (rnd.uniform(2.2, 3.4), 1.0, 1.0)
        ob.rotation_euler = (rnd.uniform(0, 3), rnd.uniform(0, 3), rnd.uniform(0, 3))
        self.macro_things.append(ob)
    for k in range(7):
        loc = (rnd.uniform(-0.6, 0.6), rnd.uniform(0.0, 0.8), rnd.uniform(-0.5, 0.5))
        self.macro_things.append(lib.blob(f"floc{k}", rnd.uniform(0.05, 0.09), floc, loc, seed=40 + k, parent=R,
                                          lumpy=0.5))
    self.specks = []
    for k in range(120):
        loc = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.2, 0.7), rnd.uniform(-0.5, 0.5))
        sp = lib.blob(f"speck{k}", rnd.uniform(0.004, 0.009), speck, loc, seed=200 + k, parent=R, lumpy=0.3,
                      subdiv=1)
        sp.visible_shadow = False
        self.specks.append(sp)
    return R


def bacteria(self, s, e):
    self.on_station("macro", s, e)
    rnd = random.Random(3)
    for ob in self.macro_things:
        p = V(ob.location)
        d = V((rnd.uniform(-1, 1), rnd.uniform(-0.4, 0.4), rnd.uniform(-1, 1))) * 0.06
        lib.tween(ob, "location", s, e, tuple(p), tuple(p + d), "linear")
        r = V(ob.rotation_euler)
        lib.tween(ob, "rotation_euler", s, e, tuple(r), tuple(r + V((0.4, 0.6, rnd.uniform(-0.8, 0.8)))), "linear")
    # specks drift towards the nearest bacterium and vanish (eaten)
    rods = [o for o in self.macro_things if o.name.startswith(("rod", "coccus"))]
    for k, sp in enumerate(self.specks):
        p = V(sp.location)
        target = min(rods, key=lambda o: (V(o.location) - p).length)
        eat = s + int((e - s) * rnd.uniform(0.25, 0.95))
        if k % 2 == 0 and (V(target.location) - p).length < 0.3:
            lib.tween(sp, "location", s, eat, tuple(p), tuple(V(target.location)), "in")
            lib.tween(sp, "scale", eat - 4, eat, (1, 1, 1), (0.01, 0.01, 0.01), "in")
        else:
            lib.tween(sp, "location", s, e, tuple(p), tuple(p + V((0.03, 0, -0.02))), "linear")
    cam = self.cam
    cam.data.dof.aperture_fstop = 1.6
    cam.data.keyframe_insert("dof.aperture_fstop", frame=s)
    for fc in lib.fcurves(cam.data):
        if fc.data_path == "dof.aperture_fstop":
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    self.restore_fstop.append(e + 1)
    self.shot("macro", s, e, dict(center=(0, 0.15, 0.0), width=0.95, yaw=6, pitch=6, lens=50),
              dict(center=(0.06, 0.15, 0.02), width=0.8, yaw=12, pitch=8, lens=50))
    events.add(s, "bubbles", duration=e - s, gain=0.5)


# ====================================================================== F: the river
RIVER_Z = -1.2
PIPE_Z = -0.45
BANK_Y0, BANK_Y1, BANK_TOP = 2.8, 7.5, 0.5


def bank_z(x, y):
    if y <= BANK_Y0:
        return RIVER_Z - 0.6
    if y >= BANK_Y1:
        return BANK_TOP + 0.05 * math.sin(x * 0.4) * min(1.0, (y - BANK_Y1) / 3)
    t = (y - BANK_Y0) / (BANK_Y1 - BANK_Y0)
    t = t * t * (3 - 2 * t)
    return RIVER_Z - 0.6 + t * (BANK_TOP - RIVER_Z + 0.6) + 0.06 * math.sin(x * 1.3 + y * 2.1)


def build_river(self):
    R = self.root("river")
    bm = bmesh.new()
    nx, ny = 90, 60
    xs = [-30 + 60 * i / nx for i in range(nx + 1)]
    ys = [-25 + 70 * j / ny for j in range(ny + 1)]
    grid = [[bm.verts.new((x, y, bank_z(x, y))) for x in xs] for y in ys]
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            f.smooth = True
    ground = lib.mesh_from_bm("bank", bm, P.grass_top(), R)
    ground.data.materials.append(lib.material("Ground106", scale=0.8, tint=(0.8, 0.72, 0.62), name="bank_mud"))
    for poly in ground.data.polygons:
        if poly.center.z < RIVER_Z + 0.35:
            poly.material_index = 1
    P.lawn("river_lawn", -14, 14, BANK_Y1 + 0.2, 16, z=BANK_TOP - 0.02, parent=R, density=320, slab=0.001, seed=55)
    water = P.water("river_water", "#8FCBE0", "#F0FAFD", speed=0.35, coord="Object", foam_amount=0.12,
                    scale=(0.8, 0.8, 0.8), density=1.4)
    lib.box("river", -30, 30, -25, 4.2, RIVER_Z - 0.4, RIVER_Z, water, R)
    # the outfall: concrete headwall set into the bank, a round pipe mouth, clean water pouring out
    conc = P.concrete_old()
    lib.box("outfall_wall", -1.5, 1.5, 3.9, 4.6, RIVER_Z - 0.4, 0.35, conc, R, bevel=0.03)
    lib.box("outfall_apron", -1.5, 1.5, 2.6, 4.0, RIVER_Z - 0.45, RIVER_Z + 0.05, conc, R)
    lib.tube("outfall_pipe", [(0, 6.0, PIPE_Z), (0, 3.55, PIPE_Z)], 0.38, conc, R)
    lib.tube("outfall_dark", [(0, 6.0, PIPE_Z), (0, 3.53, PIPE_Z)], 0.31, lib.flat("pipe_dark", (0.02, 0.02, 0.02),
                                                                                     0.9), R)
    fall = P.fall("clean_fall", "#E2F5FB")
    P.stream("outfall_pour", (0, 3.5, PIPE_Z - 0.12), (0, -1.5, 0.15), 0.42, radius=0.16, parent=R, mat=fall,
             flat=1.5)
    P.foam("outfall_foam", (0, 2.75, RIVER_Z + 0.02), 0.4, parent=R, seed=91)
    self.ripples = []
    ring = lib.flat("ripple", lib.hexrgb("#E9F6FB"), 0.2)
    for k in range(0):                     # (painted-looking rings: the foam and the ripples carry it)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.5, minor_radius=0.018, location=(0, 2.75, RIVER_Z + 0.005))
        t = bpy.context.active_object
        t.name = f"ripple{k}"
        t.data.materials.append(ring)
        t.parent = R
        for f, sc in ((0, 0.6), (45, 2.6)):
            t.scale = (sc, sc * 0.7, 0.3)
            t.keyframe_insert("scale", frame=f + k * 15)
        for fc in lib.fcurves(t):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            fc.modifiers.new("CYCLES")
    rock = lib.material("Concrete031", scale=0.8, tint=(0.75, 0.72, 0.68), name="rock")
    rnd = random.Random(12)
    for k in range(14):
        x = rnd.uniform(-2.6, 2.6)
        y = rnd.uniform(2.4, 3.9)
        if abs(x) < 1.6 and y > 3.0:
            continue
        lib.blob(f"riprap{k}", rnd.uniform(0.15, 0.3), rock, (x, y, bank_z(x, y)), squash=0.6, seed=k, parent=R,
                 lumpy=0.3)
    for k, (x, y, h) in enumerate(((-6, 11, 6.5), (5, 12, 7.5), (11, 10, 5.5), (-12, 13, 7.0), (16, 14, 6.0))):
        P.tree(f"rv_tree{k}", (x, y, BANK_TOP), h=h, parent=R, seed=70 + k)
    reed = lib.flat("reed", lib.hexrgb("#6E8A3A"), 0.6)
    for k in range(40):
        x = rnd.uniform(-9, 9)
        if abs(x) < 2.2:
            continue
        y = rnd.uniform(2.9, 3.6)
        lib.tube(f"reed{k}", [(x, y, RIVER_Z - 0.1), (x + rnd.uniform(-0.1, 0.1), y, RIVER_Z + rnd.uniform(0.5, 1.0))],
                 0.012, reed, R)
    return R


def outfall(self, s, e):
    self.on_station("river", s, e)
    self.shot("river", s, e, dict(center=(0.2, 3.1, -0.75), width=2.6, yaw=26, pitch=10, lens=30),
              dict(center=(0.3, 3.6, -0.45), width=6.5, yaw=30, pitch=16, lens=30))
    events.add(s, "pour", duration=e - s + 20, gain=0.9)
    events.add(s, "lake", duration=e - s, gain=0.6)


def river(self, s, e):
    self.on_station("river", s, e)
    self.shot("river", s, e, dict(center=(0.4, 3.4, -0.5), width=7.5, yaw=28, pitch=14, lens=30),
              dict(center=(0.8, 4.0, -0.3), width=11.0, yaw=24, pitch=13, lens=30))
    events.add(s, "lake", duration=e - s, gain=0.7)
    events.add(s, "pour", duration=e - s, gain=0.5)


SHOTS = (build_macro, bacteria, build_river, outfall, river)
