"""
The golden septic world (runs inside Blender): "Flushy vs the septic tank".

A vertical cutaway of a back yard: house, sewer pipe, a half-cut concrete tank (sludge / water / scum), the
outlet tee (the bouncer, with sunglasses), a gravel drainfield and the water table. The actors have faces:
Flushy (the hero), the heavy gang, the greasy guys, angry germs and hungry microbes.

Rules every beat follows (docs/REDESIGN.md):
  - one action at a time: anticipation -> action -> hold, and the camera frames the ACTOR, not the world
  - every action is registered in self.actions so the visibility gate can measure it on screen
  - the world keeps its state: a burst leaves a crater, a flown lid stays where it lands
  - no two transparent surfaces overlap and no faces are coplanar (both strobe)

World axes: X runs house -> tank -> drainfield, Y goes into the ground behind the section plane (y = 0),
Z is up, the lawn is z = 0. The camera looks +Y at the cut face.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from engine.director import lib

# ------------------------------------------------------------------ layout (metres)
TANK = dict(x0=-2.0, x1=1.6, z0=-2.3, z1=-0.5, depth=1.6, wall=0.12)
LIQ_TOP, SCUM_T, SLUDGE_T = -1.0, 0.16, 0.34
FLOOR = TANK["z0"] + TANK["wall"]
INLET_X, OUTLET_X = -1.72, 1.32
PIPE_R = 0.2
INLET = [(-8.4, 0.0, -0.42), (-2.3, 0.0, -0.78), (INLET_X, 0.0, -0.8)]
OUTLET = [(OUTLET_X, 0.0, -1.0), (TANK["x1"] + 0.3, 0.0, -1.0), (5.0, 0.0, -1.06)]
FIELD = dict(x0=5.4, x1=15.5, z0=-1.55, z1=-0.55, pipe_z=-0.92)
WATER_NORMAL, WATER_FLOOD = -3.3, -0.25
BREACH = 1.3            # how far the empty tank shoves up: it ends half out of the lawn, never in mid-air
ACT_Y = 0.04            # actors sit just behind the section plane: inside the tank, unblurred, readable
PARK = (0.0, 30.0, -25.0)

PALETTE = {  # saturated, art-directed: the story's actors are the most colourful things in frame
    "flushy": "#9A5223", "heavy": "#5E3414", "greasy": "#FFC928", "water": "#1FB7A0", "germ": "#7BE01F",
    "microbe": "#B05CFF", "drop": "#4FC3FF", "wipe": "#F4F4EE", "stink": "#A6E22E", "arrow": "#FFB000",
    "lid": "#2F7D4F", "puddle": "#3B2A16", "groundwater": "#1E86FF",
}


class Face:
    """Cartoon eyes (+ an optional mouth) on a round actor, with expressions keyed on frames."""

    def __init__(self, parent, radius, mouth=True, name="face"):
        white = lib.flat("eye_white", (0.97, 0.97, 0.97), 0.15)
        black = lib.flat("pupil", (0.01, 0.01, 0.01), 0.1, coat=1.0)
        r = radius
        self.eyes, self.pupils = [], []
        for sx in (-0.38, 0.38):
            eye = lib.blob(f"{name}_eye{sx}", r * 0.34, white, (sx * r, -0.82 * r, 0.3 * r), lumpy=0.0, subdiv=2,
                           parent=parent)
            pupil = lib.blob(f"{name}_pupil{sx}", r * 0.17, black, (0, -0.24 * r, 0.0), lumpy=0.0, subdiv=2,
                             parent=eye)
            self.eyes.append(eye)
            self.pupils.append(pupil)
        self.mouth = None
        if mouth:
            self.mouth = lib.blob(f"{name}_mouth", r * 0.22, black, (0, -0.9 * r, -0.22 * r), lumpy=0.0, subdiv=2,
                                  parent=parent)
            self.mouth.scale = (1.4, 0.5, 0.35)
        self.r = r

    def look(self, f, dx=0.0, dz=0.0):
        for p in self.pupils:
            lib.key(p, "location", f, (dx * self.r * 0.12, -0.24 * self.r, dz * self.r * 0.12))

    def surprised(self, f0, f1=None):
        for e in self.eyes:
            lib.tween(e, "scale", f0, f0 + 5, (1, 1, 1), (1.6, 1.6, 1.6), "pop")
        if self.mouth:
            lib.tween(self.mouth, "scale", f0, f0 + 5, (1.4, 0.5, 0.35), (1.0, 0.6, 1.8), "pop")
        if f1:
            self.calm(f1)

    def happy(self, f):
        for e in self.eyes:
            lib.tween(e, "scale", f, f + 5, (1, 1, 1), (1, 1, 0.75), "pop")
        if self.mouth:
            lib.tween(self.mouth, "scale", f, f + 5, (1.4, 0.5, 0.35), (1.9, 0.5, 0.45), "pop")

    def calm(self, f):
        for e in self.eyes:
            lib.key(e, "scale", f, (1, 1, 1))
        if self.mouth:
            lib.key(self.mouth, "scale", f, (1.4, 0.5, 0.35))

    def blink(self, f):
        for e in self.eyes:
            lib.key(e, "scale", f - 1, (1, 1, 1))
            lib.key(e, "scale", f + 1, (1, 1, 0.08))
            lib.key(e, "scale", f + 4, (1, 1, 1))


class SepticWorld:
    def __init__(self, timing, preview=False):
        """timing: {"fps", "total", "beats": [{"id", "f0", "f1", "cues": {word: frame}}]}"""
        self.t = timing
        self.beats = {b["id"]: b for b in timing["beats"]}
        self.scene = lib.reset(timing.get("fps", 30), preview, look=timing.get("look", "vivid"))
        self.scene.frame_start, self.scene.frame_end = 1, timing["total"]
        self.rnd = random.Random(7)
        self.anchors = lib.Anchors()
        self.actions = []
        self.cam = lib.Camera(lens=32, fstop=2.2)
        self._look()
        self._ground()
        self._yard()
        self._tank()
        self._pipes()
        self._field()
        self._cast()
        self._props()

    # -------------------------------------------------------------- registry
    def act(self, name, ob, f0, f1, min_share=0.05):
        """An action the viewer must SEE: the visibility gate measures `ob` on screen from f0 to f1."""
        self.actions.append({"name": name, "obj": ob.name, "f0": int(f0), "f1": int(f1), "min_share": min_share})

    # -------------------------------------------------------------- build
    def _look(self):
        self.sky = lib.hdri_world(lib.hdri("kloofendal_48d_partly_cloudy_puresky"), strength=1.1, rotation_deg=40)
        self.sun = lib.sun(rotation=(50, 0, 30), strength=3.4)
        fill = bpy.data.lights.new("CutFill", "AREA")
        fill.shape = "RECTANGLE"
        fill.size, fill.size_y = 40.0, 14.0
        fill.energy = 5000
        fill.color = (1.0, 0.97, 0.92)
        ob = lib.link(bpy.data.objects.new("CutFill", fill))
        ob.location = (3.0, -9.0, -1.5)
        ob.rotation_euler = (math.radians(90), 0, 0)
        ob.visible_camera = False

    def _strata(self):
        """Soil section: topsoil / loam / deep loam by depth with wavy boundaries, saturated blue below the water
        table (a keyed value), so the groundwater visibly rises in the flood."""
        mat = bpy.data.materials.new("strata")
        nt, bsdf = lib._bsdf(mat)
        top = lib.tex_nodes(nt, "Ground048", 0.7)
        mid = lib.tex_nodes(nt, "Ground085", 0.45)
        deep = lib.tex_nodes(nt, "Ground085", 0.3)
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 0.35
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        wob = nt.nodes.new("ShaderNodeMath")
        wob.operation = "MULTIPLY_ADD"
        nt.links.new(noise.outputs["Fac"], wob.inputs[0])
        wob.inputs[1].default_value = 0.35
        nt.links.new(sep.outputs["Z"], wob.inputs[2])

        def band(lo, hi):
            m = nt.nodes.new("ShaderNodeMapRange")
            m.inputs["From Min"].default_value = lo
            m.inputs["From Max"].default_value = hi
            nt.links.new(wob.outputs[0], m.inputs["Value"])
            return m.outputs["Result"]

        def mix(kind, a, b, fac):
            m = nt.nodes.new("ShaderNodeMix")
            m.data_type = kind
            nt.links.new(fac, m.inputs["Factor"])
            nt.links.new(a, m.inputs[6 if kind == "RGBA" else (4 if kind == "VECTOR" else 2)])
            nt.links.new(b, m.inputs[7 if kind == "RGBA" else (5 if kind == "VECTOR" else 3)])
            return m.outputs[2 if kind == "RGBA" else (1 if kind == "VECTOR" else 0)]

        def tinted(col, rgb):
            m = nt.nodes.new("ShaderNodeMix")
            m.data_type = "RGBA"
            m.blend_type = "MULTIPLY"
            m.inputs["Factor"].default_value = 1.0
            nt.links.new(col, m.inputs[6])
            m.inputs[7].default_value = (*rgb, 1)
            return m.outputs[2]

        f_top = band(-0.62, -0.45)
        f_mid = band(-2.65, -2.45)
        col = mix("RGBA", mix("RGBA", tinted(deep["Color"], (0.78, 0.58, 0.42)), tinted(mid["Color"], (1.0, 0.78, 0.58)),
                              f_mid), tinted(top["Color"], (0.95, 0.78, 0.62)), f_top)
        nrm = mix("VECTOR", mix("VECTOR", deep["Normal"], mid["Normal"], f_mid), top["Normal"], f_top)
        rough = mix("FLOAT", mix("FLOAT", deep["Roughness"], mid["Roughness"], f_mid), top["Roughness"], f_top)
        level = nt.nodes.new("ShaderNodeValue")
        level.outputs[0].default_value = WATER_NORMAL
        self.water_level = level.outputs[0]
        rel = nt.nodes.new("ShaderNodeMath")
        rel.operation = "SUBTRACT"
        nt.links.new(sep.outputs["Z"], rel.inputs[0])
        nt.links.new(level.outputs[0], rel.inputs[1])
        wet = nt.nodes.new("ShaderNodeMapRange")
        wet.inputs["From Min"].default_value = 0.04
        wet.inputs["From Max"].default_value = -0.04
        nt.links.new(rel.outputs[0], wet.inputs["Value"])
        fac = nt.nodes.new("ShaderNodeMath")
        fac.operation = "MULTIPLY"
        nt.links.new(wet.outputs["Result"], fac.inputs[0])
        fac.inputs[1].default_value = 0.66
        tint = nt.nodes.new("ShaderNodeMix")
        tint.data_type = "RGBA"
        nt.links.new(fac.outputs[0], tint.inputs["Factor"])
        nt.links.new(col, tint.inputs[6])
        tint.inputs[7].default_value = (*lib.hexrgb(PALETTE["groundwater"]), 1)
        nt.links.new(tint.outputs[2], bsdf.inputs["Base Color"])
        r_w = nt.nodes.new("ShaderNodeMix")
        r_w.data_type = "FLOAT"
        nt.links.new(wet.outputs["Result"], r_w.inputs["Factor"])
        nt.links.new(rough, r_w.inputs[2])
        r_w.inputs[3].default_value = 0.5
        nt.links.new(r_w.outputs[0], bsdf.inputs["Roughness"])
        nt.links.new(nrm, bsdf.inputs["Normal"])
        return mat

    def _ground(self):
        self.soil = lib.box("soil", -60, 80, 0.0, 70, -60, -0.03, self._strata())
        self.lawn = lib.box("lawn", -60, 80, 0.0, 70, -0.03, 0.0, lib.material("Grass006", 0.6, tint=(0.9, 1.05, 0.8)))
        self.front = lib.empty("front_ground")
        lib.box("front_lawn", -60, 80, -60, -0.002, -0.03, 0.0, lib.material("Grass006", 0.6, tint=(0.9, 1.05, 0.8)),
                self.front)
        lib.box("front_soil", -60, 80, -60, -0.002, -4.0, -0.03, lib.material("Ground048", 0.7), self.front)
        lib.box("far", -400, 400, 70, 600, -0.4, -0.03, lib.material("Grass004", 0.08))
        self.anchors.add("groundwater", (-0.2, 0.0, -1.9))
        self.anchors.add("soil", (8.2, 0.0, -2.0))

    def _yard(self):
        house = lib.import_model(lib.kenney("suburban", "building-type-c"), "house")
        self._fit(house, width=9.0)
        house.location = (-10.5, 7.0, 0.0)
        house.rotation_euler = (0, 0, math.radians(180))
        for i in range(9):
            fence = lib.import_model(lib.kenney("suburban", "fence"), f"fence{i}")
            self._fit(fence, width=2.2)
            fence.location = (-4.0 + i * 2.2, 16.0, 0)
        self._scatter()

    def _fit(self, root, width=None, height=None):
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in root.children_recursive if o.type == "MESH" for c in o.bound_box]
        if not pts:
            return 1.0
        w = max(p.x for p in pts) - min(p.x for p in pts)
        h = max(p.z for p in pts) - min(p.z for p in pts)
        k = (width / w) if width else (height / h)
        root.scale = (k, k, k)
        return k

    def _collection(self, path, name):
        coll = bpy.data.collections.get(name)
        if coll:
            return coll
        coll = bpy.data.collections.new(name)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        for ob in [o for o in bpy.data.objects if o not in before]:
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            coll.objects.link(ob)
        return coll

    def _instance(self, coll, loc, scale=1.0, rot=0.0):
        ob = bpy.data.objects.new(f"{coll.name}_i", None)
        ob.instance_type = "COLLECTION"
        ob.instance_collection = coll
        ob.location, ob.scale = loc, (scale,) * 3
        ob.rotation_euler = (0, 0, rot)
        return lib.link(ob)

    def _scatter(self):
        """Set dressing tuned for temporal stability: trees far back (the shallow focus blurs them), chunky
        lawn plants only (thin blades shimmer under a moving camera)."""
        nat = lambda n: lib.find_asset("quaternius/stylized-nature-megakit", n)  # noqa: E731
        trees = [self._collection(nat(f"CommonTree_{i}.gltf"), f"tree{i}") for i in (1, 2, 3, 4)]
        bushes = [self._collection(nat(n), n) for n in ("Bush_Common.gltf", "Bush_Common_Flowers.gltf")]
        plants = [self._collection(nat(n), n) for n in ("Clover_1.gltf", "Clover_2.gltf", "Grass_Common_Short.gltf")]
        flowers = self._collection(nat("Flower_3_Group.gltf"), "flowers")
        r = self.rnd
        for _ in range(22):
            self._instance(r.choice(trees), (r.uniform(-30, 40), r.uniform(26, 55), 0), r.uniform(1.8, 2.6),
                           r.uniform(0, 6.3))
        for _ in range(26):
            self._instance(r.choice(bushes), (r.uniform(-22, 30), r.uniform(11, 18), 0), r.uniform(1.0, 1.5),
                           r.uniform(0, 6.3))
        for _ in range(260):
            x, y = r.uniform(-20, 26), r.uniform(0.6, 12) ** 1.1
            if TANK["x0"] - 0.4 < x < TANK["x1"] + 0.4 and y < 2.2:
                continue
            self._instance(r.choice(plants), (x, y, 0), r.uniform(0.3, 0.45), r.uniform(0, 6.3))
        # the flower bed over the drainfield: it wilts when the field fails
        self.flowers = [self._instance(flowers, (8.6 + i * 0.55 + r.uniform(-0.1, 0.1), r.uniform(0.9, 2.2), 0),
                                       r.uniform(0.32, 0.42), r.uniform(0, 6.3)) for i in range(8)]

    def _tank(self):
        t = TANK
        concrete = lib.material("Concrete031", 0.9, tint=(1.0, 0.98, 0.95))
        self.tank = lib.empty("tank", (0, 0, 0))
        w, d = t["wall"], t["depth"]
        parts = [
            (t["x0"], t["x1"], 0, d, t["z0"], t["z0"] + w),
            (t["x0"], t["x1"], 0, d, t["z1"] - w, t["z1"]),
            (t["x0"], t["x0"] + w, 0, d, t["z0"], t["z1"]),
            (t["x1"] - w, t["x1"], 0, d, t["z0"], t["z1"]),
            (t["x0"], t["x1"], d - w, d, t["z0"], t["z1"]),
        ]
        for i, (x0, x1, y0, y1, z0, z1) in enumerate(parts):
            lib.box(f"tank_{i}", x0, x1, y0, y1, z0, z1, concrete, self.tank, bevel=0.02)
        lib.box("riser", -0.4, 0.2, 0.25, 0.85, t["z1"], 0.04, concrete, self.tank, bevel=0.02)
        # the lid is its own object: it flies off in the burst and stays where it lands
        self.lid = lib.box("lid", -0.45, 0.25, 0.2, 0.9, 0.04, 0.1, lib.flat("lid", lib.hexrgb(PALETTE["lid"]), 0.5),
                           bevel=0.015)
        self._origin_to(self.lid, Vector((-0.1, 0.55, 0.07)))
        x0, x1, y1 = t["x0"] + w, t["x1"] - w, d - w
        # liquids are OPAQUE and never share a face (overlapping transparency strobes)
        self.sludge = lib.box("sludge", x0 + 0.002, x1 - 0.002, 0.006, y1, FLOOR + 0.002, FLOOR + SLUDGE_T,
                              lib.material("Ground048", 2.0, tint=(0.42, 0.26, 0.12), rough=0.2), self.tank)
        self.water = lib.box("water", x0 + 0.002, x1 - 0.002, 0.012, y1, FLOOR + SLUDGE_T + 0.004,
                             LIQ_TOP - SCUM_T - 0.004, lib.flat("effluent", lib.hexrgb(PALETTE["water"]), rough=0.06,
                                                                 emission=0.12), self.tank)
        self.scum = lib.box("scum", x0 + 0.002, x1 - 0.002, 0.006, y1, LIQ_TOP - SCUM_T, LIQ_TOP,
                            lib.material("Ground054", 2.5, tint=(1.0, 0.75, 0.25), rough=0.22), self.tank)
        for ob, z in ((self.sludge, FLOOR), (self.water, FLOOR + SLUDGE_T), (self.scum, LIQ_TOP - SCUM_T)):
            self._origin_z(ob, z)
        self.layer_base = {"sludge": FLOOR, "water": FLOOR + SLUDGE_T, "scum": LIQ_TOP - SCUM_T}
        pvc = lib.material("Plastic010", 2.0, tint=(0.97, 0.97, 0.95), rough=0.3)
        bright = lib.flat("bouncer_pvc", (0.92, 0.94, 0.96), rough=0.25, emission=0.08)
        for x, top, bottom in ((INLET_X, -0.74, -1.45), (OUTLET_X, -0.86, -1.58)):
            tee = lib.tube(f"tee{x}", [(x, 0.0, top), (x, 0.0, bottom)], PIPE_R, bright if x == OUTLET_X else pvc,
                           self.tank)
            lib.section(tee)
        # the bouncer: the outlet tee gets a face (big eyes, a frown) and a solid visor it slides down at the
        # start of its beat. Built big and high-contrast: thin grey bars read as nothing at phone size.
        self.bouncer = lib.empty("bouncer", (OUTLET_X, -0.035, -1.34), self.tank)      # on the teal: max contrast
        self.bouncer.scale = (1.4, 1.4, 1.4)
        white = lib.flat("eye_white", (0.97, 0.97, 0.97), 0.15)
        black = lib.flat("pupil", (0.01, 0.01, 0.01), 0.1, coat=1.0)
        for sx in (-0.085, 0.085):
            eye = lib.blob(f"tee_eye{sx}", 0.075, white, (sx, 0, 0.1), lumpy=0.0, subdiv=2, parent=self.bouncer)
            lib.blob(f"tee_pupil{sx}", 0.035, black, (0.0, -0.05, -0.01), lumpy=0.0, subdiv=2, parent=eye)
        lib.box("tee_frown", -0.1, 0.1, -0.04, 0.0, -0.11, -0.075, black, self.bouncer, bevel=0.012)
        self.visor = lib.empty("visor", (0, 0, 0.45), self.bouncer)          # parked above, slides down
        visor = lib.flat("visor", (0.005, 0.005, 0.01), 0.04, coat=1.0)
        lib.box("visor_glass", -0.2, 0.2, -0.09, -0.04, 0.045, 0.155, visor, self.visor, bevel=0.03)
        lib.box("visor_shine", -0.16, -0.06, -0.095, -0.09, 0.115, 0.135,
                lib.flat("shine", (1, 1, 1), 0.1, emission=4.0), self.visor)
        # the half-cut tank is only for straight-on cutaway shots. Above ground (the burst) it would show
        # as a hollow half-box, so a CLOSED tank takes its place from the burst on.
        self.half_parts = [o for o in self.tank.children_recursive if o.type == "MESH" and o.name != "riser"]
        self.tank_full = lib.empty("tank_full", (0, 0, 0), self.tank)
        lib.box("tank_closed", t["x0"], t["x1"], 0.0, d, t["z0"], t["z1"], concrete, self.tank_full, bevel=0.03)
        # static cavity: the hole stays where the tank was, whatever the tank does
        cavity = lib.box("cavity", t["x0"] - 0.03, t["x1"] + 0.03, -1.0, d + 0.03, t["z0"] - 0.03, t["z1"] + 0.03)
        lib.boolean(self.soil, cavity)
        riser_cut = lib.box("riser_cut", -0.42, 0.22, 0.23, 0.87, -0.6, 0.2)
        lib.boolean(self.lawn, riser_cut)
        lib.boolean(self.soil, riser_cut)
        # the breach: soil + lawn above the tank are torn open only from the burst on
        breach = lib.box("breach", t["x0"] - 0.05, t["x1"] + 0.05, -1.0, d + 0.05, t["z1"] - 0.05, 0.3)
        self.breach_mods = [lib.boolean(self.soil, breach), lib.boolean(self.lawn, breach)]
        self.anchors.add("sludge", (-1.1, 0.0, FLOOR + SLUDGE_T * 0.5), self.tank)
        self.anchors.add("scum", (0.5, 0.0, LIQ_TOP - SCUM_T * 0.5), self.tank)
        self.anchors.add("tee", (OUTLET_X, 0.0, -1.32), self.tank)

    def solid(self, f, on):
        """Swap the half-cut tank for the closed one (on) or back (off) at frame f."""
        for ob in self.half_parts:
            lib.visible(ob, f, not on, children=False)
        lib.visible(self.tank_full, f, on)

    def surface(self, f, on):
        """The ground in FRONT of the section plane: on for above-ground shots, so they show a lawn instead
        of the cut face (the cutaway convention only works straight-on and below ground)."""
        lib.visible(self.front, f, on)

    def breach(self, f, on):
        for mod in self.breach_mods:
            mod.show_render = on
            mod.show_viewport = on
            mod.id_data.keyframe_insert(f'modifiers["{mod.name}"].show_render', frame=f)
            mod.id_data.keyframe_insert(f'modifiers["{mod.name}"].show_viewport', frame=f)
        for fc in lib.fcurves(self.soil) + lib.fcurves(self.lawn):
            if "show_" in fc.data_path:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"

    @staticmethod
    def _origin_z(ob, z):
        for v in ob.data.vertices:
            v.co.z -= z
        ob.location.z += z

    @staticmethod
    def _origin_to(ob, p):
        for v in ob.data.vertices:
            v.co -= p
        ob.location += p

    def _pipes(self):
        pvc = lib.material("Plastic010", 2.0, tint=(0.97, 0.97, 0.95), rough=0.3)
        self.inlet = lib.tube("inlet", INLET, PIPE_R, pvc)
        self.outlet = lib.tube("outlet", OUTLET, PIPE_R, pvc)
        for p, pts in ((self.inlet, INLET), (self.outlet, OUTLET)):
            lib.section(p)
            lib.boolean(self.soil, lib.tube(f"{p.name}_cut", pts, PIPE_R + 0.03))
        stack = lib.tube("stack", [(INLET[0][0], 0.0, INLET[0][2]), (INLET[0][0], 0.0, 0.6)], PIPE_R, pvc)
        lib.section(stack)              # cut open like every pipe, or Flushy's eyes poke through its wall
        dbox = lib.box("dbox", 4.75, 5.4, 0.0, 0.7, -1.4, -0.7, lib.material("Concrete031", 1.0), bevel=0.02)
        lib.section(dbox)
        self.anchors.add("pipe", (-5.2, 0.0, -0.6))

    def _field(self):
        f = FIELD
        self.gravel_mat = lib.material("Gravel023", 0.45, tint=(0.62, 0.58, 0.52))
        self.trench = lib.box("trench", f["x0"], f["x1"], 0.0, 2.2, f["z0"], f["z1"], self.gravel_mat)
        lib.boolean(self.soil, lib.box("trench_cut", f["x0"] - 0.02, f["x1"] + 0.02, -1, 2.22, f["z0"] - 0.02,
                                       f["z1"] + 0.02))
        nt = self.gravel_mat.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        src = bsdf.inputs["Base Color"].links[0].from_socket
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 0.0
        nt.links.new(src, mix.inputs[6])
        mix.inputs[7].default_value = (0.06, 0.05, 0.03, 1)
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        self.clog = mix.inputs["Factor"]
        pvc = lib.material("Plastic010", 2.0, tint=(0.97, 0.97, 0.95), rough=0.3)
        lateral = lib.tube("lateral", [(5.4, 0.0, f["pipe_z"]), (f["x1"] - 0.2, 0.0, f["pipe_z"])], PIPE_R, pvc)
        lib.section(lateral)
        lib.boolean(self.trench, lib.tube("lateral_cut", [(5.3, 0.0, f["pipe_z"]), (f["x1"], 0.0, f["pipe_z"])],
                                          PIPE_R + 0.02))
        self.holes = [5.9 + i * 0.75 for i in range(13) if 5.9 + i * 0.75 < f["x1"] - 0.3]
        dark = lib.flat("hole", (0.02, 0.02, 0.02), 0.9)
        for x in self.holes:
            lib.box(f"hole{x}", x - 0.04, x + 0.04, 0.0, 0.06, f["pipe_z"] - PIPE_R - 0.005,
                    f["pipe_z"] - PIPE_R + 0.025, dark)
        self.puddle = lib.blob("puddle", 1.0, lib.flat("puddle", lib.hexrgb(PALETTE["puddle"]), rough=0.05),
                               (10.3, 1.6, 0.012), squash=0.02, seed=3, lumpy=0.25)
        self.puddle.scale = (0.01, 0.01, 1)

    def _actor(self, name, radius, color, mouth=False, seed=0, coat=0.5, emission=0.0, lumpy=0.12):
        root = lib.empty(name, PARK)
        lib.blob(f"{name}_body", radius, lib.flat(f"{name}_mat_{color}", lib.hexrgb(color), 0.3, coat=coat,
                                                  emission=emission), (0, 0, 0), squash=0.9, seed=seed, lumpy=lumpy,
                 parent=root)
        return root, Face(root, radius, mouth, name)

    def _pacman(self, name, r, color):
        """A Pac-Man microbe facing +X: two hemisphere jaws hinged at the centre with a dark mouth inside, so
        a chomp is a wedge opening and shutting that reads at any size. Eyes on top, toward the camera."""
        root = lib.empty(name, PARK)
        body = lib.flat(f"{name}_mat", lib.hexrgb(color), 0.3, coat=0.6, emission=0.5)
        mouth = lib.flat("mouth_inside", lib.hexrgb("#5A0F1E"), 0.5)
        jaws = []
        for upper in (True, False):
            hinge = lib.empty(f"{name}_{'up' if upper else 'down'}", (0, 0, 0), root)
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            cut = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, 0), plane_no=(0, 0, 1),
                                         clear_inner=upper, clear_outer=not upper)
            edges = [e for e in cut["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
            fill = bmesh.ops.holes_fill(bm, edges=edges)
            for f in fill["faces"]:
                f.material_index = 1
            ob = lib.mesh_from_bm(f"{name}_jaw{int(upper)}", bm, body, hinge, smooth=True)
            ob.data.materials.append(mouth)
            jaws.append(hinge)
        top = jaws[0]
        white = lib.flat("eye_white", (0.97, 0.97, 0.97), 0.15)
        black = lib.flat("pupil", (0.01, 0.01, 0.01), 0.1, coat=1.0)
        for sx in (-0.03, 0.05):
            eye = lib.blob(f"{name}_eye{sx}", r * 0.3, white, (sx, -0.7 * r, 0.62 * r), lumpy=0.0, subdiv=2, parent=top)
            lib.blob(f"{name}_pupil{sx}", r * 0.15, black, (0.02, -0.22 * r, 0.0), lumpy=0.0, subdiv=2, parent=eye)
        return root, jaws

    def chomp(self, jaws, f, opens=5, period=6, angle=38):
        """Mouth opens and shuts `opens` times from frame f (a wedge toward +X)."""
        up, down = jaws
        for k in range(opens):
            a = f + k * period
            lib.key(up, "rotation_euler", a, (0, 0, 0))
            lib.key(down, "rotation_euler", a, (0, 0, 0))
            lib.key(up, "rotation_euler", a + period // 2, (0, math.radians(-angle), 0))
            lib.key(down, "rotation_euler", a + period // 2, (0, math.radians(angle), 0))
        lib.key(up, "rotation_euler", f + opens * period, (0, 0, 0))
        lib.key(down, "rotation_euler", f + opens * period, (0, 0, 0))

    def _arms(self, root, r, color):
        """Stubby cartoon arms on Flushy: shoulder pivots at his sides; rotate them for wheee / ta-da."""
        skin = lib.flat(f"arm_{color}", lib.hexrgb(color), 0.3, coat=0.8)
        arms = []
        for side in (-1, 1):
            shoulder = lib.empty(f"shoulder{side}", (side * 0.88 * r, -0.05, -0.05), root)
            lib.tube(f"arm{side}", [(0, 0, 0), (side * 0.05, 0, -0.12)], 0.038, skin, shoulder)
            lib.blob(f"hand{side}", 0.05, skin, (side * 0.055, 0, -0.14), lumpy=0.0, subdiv=2, parent=shoulder)
            arms.append((side, shoulder))
        return arms

    def arms_pose(self, f, pose, ease="pop"):
        """down: hanging; up: a V over the head (wheee / ta-da); wave: one up."""
        angles = {"down": (0, 0), "up": (150, 150), "wave": (0, 150)}[pose]
        for (side, shoulder), a in zip(self.arms, angles):
            lib.tween(shoulder, "rotation_euler", f, f + 6, shoulder.rotation_euler.copy(),
                      (0, math.radians(-side * a), 0), ease)

    def _cast(self):
        self.flushy, self.flushy_face = self._actor("flushy", 0.21, PALETTE["flushy"], mouth=True, seed=5, coat=0.8,
                                                    lumpy=0.05)
        self.heavy = [self._actor(f"heavy{i}", 0.12 + 0.02 * (i % 2), "#5E3414", seed=20 + i)[0] for i in range(4)]
        self.greasy = [self._actor(f"greasy{i}", 0.11 + 0.02 * (i % 2), PALETTE["greasy"], seed=30 + i, coat=1.0,
                                   lumpy=0.06)[0] for i in range(3)]
        self.germs = []
        for i in range(5):
            root, face = self._actor(f"germ{i}", 0.15, PALETTE["germ"], seed=60 + i, emission=0.8, lumpy=0.45)
            for e in face.eyes:          # angry: eyes squashed flat on top
                e.scale = (1.1, 1, 0.6)
            self.germs.append(root)
        self.microbes, self.jaws = [], []
        for i in range(5):
            root, jaws = self._pacman(f"microbe{i}", 0.15, PALETTE["microbe"])
            self.microbes.append(root)
            self.jaws.append(jaws)
        self.arms = self._arms(self.flushy, 0.21, PALETTE["flushy"])

    def _props(self):
        self.truck = lib.import_model(lib.kenney("car-kit", "truck"), "truck")
        self._fit(self.truck, width=4.6)
        self.truck_home, self.truck_parked = (40, 10.0, 0), (4.2, 9.5, 0)
        self.truck.location = self.truck_home
        self.truck.rotation_euler = (0, 0, math.radians(90))
        self.hose = lib.tube("hose", [(-0.1, 0.55, 0.12), (0.4, 3.0, 0.4), (3.6, 8.2, 0.9)], 0.07,
                             lib.flat("hose", lib.hexrgb("#222222"), 0.5))
        glow = lib.flat("arrow", lib.hexrgb(PALETTE["arrow"]), rough=0.3, emission=2.5)
        self.arrows = []
        for i, x in enumerate((-1.4, -0.2, 1.0)):
            a = lib.empty(f"arrow{i}", (x, -0.3, TANK["z0"] - 0.6))
            lib.tube(f"arrow_shaft{i}", [(0, 0, -0.5), (0, 0, 0.05)], 0.08, glow, a)
            me = bpy.data.meshes.new(f"cone{i}")
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.2, radius2=0.0, depth=0.32)
            bm.to_mesh(me)
            bm.free()
            head = lib.link(bpy.data.objects.new(f"arrow_head{i}", me), a)
            head.location.z = 0.2
            me.materials.append(glow)
            self.arrows.append(a)
        turf = lib.material("Grass006", 0.8, tint=(0.9, 1.05, 0.8))
        stone = lib.material("Rock030", 1.2, tint=(0.95, 0.92, 0.88))
        self.chunks = [lib.blob(f"chunk{i}", self.rnd.uniform(0.16, 0.28), turf if i % 3 else stone, PARK, seed=i,
                                lumpy=0.3, subdiv=2) for i in range(12)]
        stink = lib.flat("stink", lib.hexrgb(PALETTE["stink"]), rough=0.5, emission=1.5)
        self.stink = [lib.tube(f"stink{i}", [(9.6 + i * 0.4 + 0.12 * math.sin(k * 1.3), 1.0, 0.1 + k * 0.2)
                                             for k in range(9)], 0.035, stink) for i in range(5)]
        white = lib.flat("wipe", lib.hexrgb(PALETTE["wipe"]), 0.7)
        self.wipes = []
        for i in range(5):
            wpe = lib.box(f"wipe{i}", -0.14, 0.14, -0.004, 0.004, -0.14, 0.14, white)
            wpe.location = PARK
            self.wipes.append(wpe)
        blue = lib.flat("drop", lib.hexrgb(PALETTE["drop"]), 0.1, emission=1.4)
        self.drops = [lib.blob(f"drop{i}", 0.07, blue, PARK, lumpy=0.05, subdiv=2) for i in range(16)]

    # -------------------------------------------------------------- state
    def snap(self, ob, path, f, value):
        lib.key(ob, path, f, value)
        for fc in lib.fcurves(ob):
            if fc.data_path != path:
                continue
            prev = [kp for kp in fc.keyframe_points if kp.co.x < f - 0.5]
            if prev:
                max(prev, key=lambda k: k.co.x).interpolation = "CONSTANT"

    def snap_node(self, socket, f, value):
        lib.node_key(socket, f, value)
        path = socket.path_from_id("default_value")
        for fc in lib.fcurves(socket.id_data):
            if fc.data_path == path:
                prev = [kp for kp in fc.keyframe_points if kp.co.x < f - 0.5]
                if prev:
                    max(prev, key=lambda k: k.co.x).interpolation = "CONSTANT"

    def park(self, ob, f):
        self.snap(ob, "location", f, PARK)

    def normal_state(self, f):
        """The healthy system (each beat that is not a continuation starts here)."""
        self.snap(self.tank, "location", f, (0, 0, 0))
        self.snap(self.tank, "rotation_euler", f, (0, 0, 0))
        self.snap(self.lid, "location", f, (-0.1, 0.55, 0.07))
        self.snap(self.lid, "rotation_euler", f, (0, 0, 0))
        self.breach(f, False)
        self.solid(f, False)
        self.surface(f, False)
        for name in ("sludge", "water", "scum"):
            ob = getattr(self, name)
            self.snap(ob, "scale", f, (1, 1, 1))
            self.snap(ob, "location", f, (0, 0, self.layer_base[name]))
        self.snap_node(self.water_level, f, WATER_NORMAL)
        self.snap_node(self.clog, f, 0.0)
        self.snap(self.puddle, "scale", f, (0.01, 0.01, 1))
        self.snap(self.truck, "location", f, self.truck_home)
        self.snap(self.hose, "location", f, (0, 0, -30))
        for a in self.arrows:
            self.snap(a, "scale", f, (0.001, 0.001, 0.001))
            self.snap(a, "location", f, (a.location.x, -0.3, TANK["z0"] - 0.6))
        for ob in self.chunks + self.wipes + self.drops + self.heavy + self.greasy + self.germs + self.microbes:
            self.park(ob, f)
            self.snap(ob, "scale", f, (1, 1, 1))
        for s in self.stink:
            self.snap(s, "location", f, (0, 0, -30))
        for fl in self.flowers:
            self.snap(fl, "rotation_euler", f, (0, 0, fl.rotation_euler.z))
        self.park(self.flushy, f)
        for _side, shoulder in self.arms:
            self.snap(shoulder, "rotation_euler", f, (0, 0, 0))
        self.snap(self.visor, "location", f, (0, 0, 0.45))
        self.snap(self.bouncer, "rotation_euler", f, (0, 0, 0))
        self.snap(self.flushy, "rotation_euler", f, (0, 0, 0))
        self.snap(self.flushy, "scale", f, (1, 1, 1))
        self.flushy_face.calm(f)

    def cue(self, beat, word, share=0.3):
        b = self.beats[beat]
        for w, fr in b.get("cues", {}).items():
            if w.lower().strip(".,:?!") == word.lower():
                return fr
        return b["f0"] + int((b["f1"] - b["f0"]) * share)

    def squash(self, ob, f, k=0.35):
        lib.key(ob, "scale", f - 1, (1, 1, 1))
        lib.key(ob, "scale", f + 1, (1 + k, 1 + k, 1 - k))
        lib.tween(ob, "scale", f + 2, f + 14, (1 + k, 1 + k, 1 - k), (1, 1, 1), "elastic")

    @staticmethod
    def _x_at(ob, f):
        bpy.context.scene.frame_set(f)
        return ob.matrix_world.translation.x

    @staticmethod
    def in_tank(x, z):
        return Vector((x, ACT_Y, z))

    # -------------------------------------------------------------- the burst (hook + launch)
    def burst(self, f0, pop, f1, seed=1, launch=True):
        """Flooded soil + empty tank: arrows push, the tank trembles, breaches the lawn (leaving a crater), the
        lid flies off and Flushy is launched out of the riser."""
        for name in ("sludge", "water", "scum"):
            ob = getattr(self, name)
            self.snap(ob, "scale", f0, (1, 1, 0.03))
            self.snap(ob, "location", f0, (0, 0, FLOOR + 0.002))
        for a in self.arrows:
            lib.tween(a, "scale", f0, f0 + 8, (0.001, 0.001, 0.001), (1, 1, 1), "pop")
            lib.tween(a, "location", f0 + 8, pop, a.location.copy(), a.location + Vector((0, 0, 0.35)), "in")
        lib.key(self.tank, "location", f0, (0, 0, 0))
        span = max(1, pop - f0 - 6)
        for k in range(f0 + 6, pop):        # a building shiver on a 6-frame sine (a +-2 cm jump every 2 frames strobed)
            u = (k - f0 - 6) / span
            lib.key(self.tank, "location", k, (0.018 * u * math.sin(2 * math.pi * k / 6), 0, 0.1 * u * u), "LINEAR")
        # a breach, not a flight: it shoves up until the buoyancy balances and sticks out of the lawn, tilted
        lib.tween(self.tank, "location", pop, pop + 9, (0, 0, 0.12), (0, 0, BREACH), "pop", back=1.4)
        lib.tween(self.tank, "rotation_euler", pop, pop + 14, (0, 0, 0), (math.radians(-5), math.radians(13), 0), "out")
        lib.key(self.tank, "location", f1, (0, 0, BREACH + 0.04))
        self.breach(pop, True)
        self.solid(pop + 1, True)       # on the CUT frame: a frame early showed the closed box in the close-up
        for a in self.arrows:
            lib.tween(a, "scale", pop + 4, pop + 10, (1, 1, 1), (0.001, 0.001, 0.001), "in")
        # the lid: off like a bottle cap, lands on the lawn, stays
        lid0, land = Vector((-0.1, 0.55, BREACH + 0.1)), Vector((3.2, 1.6, 0.07))
        lib.key(self.lid, "location", pop + 3, (-0.1, 0.55, 0.07))
        for k in range(0, 31, 3):
            tt = k / 30
            lib.key(self.lid, "location", pop + 4 + k, lid0.lerp(land, tt) + Vector((0, 0, 3.2 * math.sin(math.pi * tt))),
                    "LINEAR")
        lib.key(self.lid, "rotation_euler", pop + 4, (0, 0, 0))
        lib.key(self.lid, "rotation_euler", pop + 34, (math.radians(720), math.radians(25), 0))
        r = random.Random(seed)
        for c in self.chunks:     # dirt flies and STAYS as a ring around the crater
            side = r.choice((-1, 1))
            start = Vector((TANK["x0"] - 0.1 if side < 0 else TANK["x1"] + 0.1, r.uniform(0.2, 1.4), 0.02))
            vel = Vector((side * r.uniform(0.8, 3.0), r.uniform(-0.3, 2.0), r.uniform(3.5, 6)))
            lib.key(c, "location", pop - 1, PARK, "CONSTANT")
            for k in range(0, 64, 3):     # until it LANDS (it hung in the air when this stopped at 1.1 s)
                tt = k / 30
                p = start + vel * tt + Vector((0, 0, -4.9 * tt * tt))
                if p.z <= 0.08:
                    p.z = 0.08
                    lib.key(c, "location", pop + k, p, "LINEAR")
                    break
                lib.key(c, "location", pop + k, p, "LINEAR")
        self.cam.shake(pop, pop + 20, amp=0.06, seed=seed)
        self.act("tank bursts", self.tank, pop - 6, pop + 12, 0.12)
        apex = Vector((-0.9, -0.6, 5.6))
        if launch:
            start = Vector((-0.1, ACT_Y, -1.9))
            self.snap(self.flushy, "location", f0, start)
            lib.key(self.flushy, "location", pop + 2, start + Vector((0, 0, BREACH + 0.6)))
            self.flushy_face.surprised(pop)
            self.arms_pose(pop + 1, "up")
            for k in range(3, 25, 3):
                tt = k / 24
                p = (start + Vector((0, 0, BREACH + 0.7))).lerp(apex, tt) +                     Vector((0, 0, 1.2 * math.sin(math.pi * tt / 2)))
                lib.key(self.flushy, "location", pop + 2 + k, p)
            lib.key(self.flushy, "rotation_euler", pop + 2, (0, 0, 0))
            lib.key(self.flushy, "rotation_euler", pop + 40, (math.radians(-540), 0, math.radians(90)))
        return apex

    # -------------------------------------------------------------- beats
    def hook(self, b):
        f0, f1 = b["f0"], b["f1"]
        self.normal_state(f0)
        self.snap_node(self.water_level, f0, WATER_FLOOD)
        pop = f0 + int((f1 - f0) * 0.3)
        apex = self.burst(f0, pop, f1, seed=2)
        lib.key(self.flushy, "location", f1, apex + Vector((0.3, 0, 0.9)))     # still flying when we rewind
        self.flushy_face.look(pop + 10, 0, 1)
        self.act("Flushy launched", self.flushy, pop + 2, min(f1, pop + 30), 0.04)
        # 1) close on the trembling empty tank in the flooded ground
        self.cam.shot(f0, pop, dict(center=(-0.2, 0, -1.0), width=4.2, yaw=-12, pitch=7),
                      dict(center=(-0.2, 0, -0.8), width=3.9, yaw=-9, pitch=6))
        # 2) HOLD a medium-wide on the breach: crater, flying lid, Flushy shot out (the money shot)
        hold = min(f1 - 12, pop + 36)
        self.cam.shot(pop + 1, hold, dict(center=(-0.3, 0, 1.8), width=7.6, yaw=-14, pitch=12),
                      dict(center=(-0.3, 0, 2.2), width=7.2, yaw=-12, pitch=10))
        # 3) cut to Flushy in the sky
        self.cam.shot(hold + 1, f1, dict(center=apex + Vector((0.1, 0, 0.2)), width=2.4, yaw=-16, pitch=-6),
                      dict(center=apex + Vector((0.3, 0, 0.8)), width=2.2, yaw=-20, pitch=-8))

    def follow(self, b):
        """Static framings, never a fast track: a pan faster than 1.5 % of the frame per frame stutters."""
        f0, f1 = b["f0"], b["f1"]
        self.normal_state(f0)
        go = f0 + 20                 # the first ~0.7 s is the compositor's VHS rewind of the hook
        p0, p1, p2 = (Vector(p) for p in INLET)
        ride = lambda p: p + Vector((0, 0.03, 0.02))  # noqa: E731
        lib.key(self.flushy, "location", go - 2, ride(p0) + Vector((0, 0, 0.9)))
        lib.tween(self.flushy, "location", go, go + 8, ride(p0) + Vector((0, 0, 0.9)), ride(p0), "in")
        self.squash(self.flushy, go + 8, 0.45)
        self.flushy_face.surprised(go + 6)
        arrive = f1 - 16
        lib.tween(self.flushy, "location", go + 12, arrive, ride(p0), ride(p2) + Vector((0, 0, -0.02)), "in")
        for k, f in enumerate(range(go + 12, arrive, 10)):   # swaying down the slide (faster flips read as jitter)
            lib.key(self.flushy, "rotation_euler", f, (0, math.radians(18 * (-1) ** k), math.radians(10 * (-1) ** k)))
        lib.key(self.flushy, "rotation_euler", arrive, (0, 0, 0))
        self.flushy_face.happy(go + 20)
        self.arms_pose(go + 16, "up")
        self.arms_pose(arrive - 2, "down")
        self.squash(self.flushy, arrive, 0.3)
        self.act("Flushy drops in", self.flushy, go - 4, go + 14, 0.08)
        self.act("Flushy slides", self.flushy, arrive - 22, arrive, 0.06)
        # 1) close on the drain: he drops in; 2) wide static on the whole slope: he zooms across;
        # 3) close at the tank inlet: he arrives
        self.cam.shot(f0, go + 13, dict(center=ride(p0) + Vector((0.3, 0, 0.3)), width=2.0, yaw=10, pitch=8),
                      dict(center=ride(p0) + Vector((0.3, 0, 0.2)), width=1.9, yaw=8, pitch=8))
        stretch = p1 + Vector((-1.0, 0, 0.1))
        enter = next((k for k in range(go + 14, arrive) if self._x_at(self.flushy, k) > stretch.x - 1.5), arrive - 12)
        self.cam.shot(go + 14, enter - 1, dict(center=ride(p0) + Vector((0.6, 0, 0.15)), width=2.2, yaw=6, pitch=8),
                      dict(center=ride(p0) + Vector((0.7, 0, 0.12)), width=2.1, yaw=4, pitch=8))
        self.cam.shot(enter, arrive - 1, dict(center=stretch, width=2.9, yaw=4, pitch=8),
                      dict(center=stretch + Vector((0.2, 0, 0)), width=2.75, yaw=2, pitch=8))
        self.cam.shot(arrive, f1, dict(center=ride(p2) + Vector((-0.4, 0, 0.1)), width=2.2, yaw=6, pitch=7),
                      dict(center=ride(p2) + Vector((-0.3, 0, 0.05)), width=2.0, yaw=4, pitch=7))

    def sort(self, b):
        f0, f1 = b["f0"], b["f1"]
        self.normal_state(f0)
        heavy_cue, greasy_cue = self.cue("sort", "heavy", 0.4), self.cue("sort", "greasy", 0.7)
        drop = self.in_tank(INLET_X + 0.05, -1.25)
        lib.key(self.flushy, "location", f0, self.in_tank(INLET_X, -0.85))
        lib.tween(self.flushy, "location", f0 + 3, f0 + 12, self.in_tank(INLET_X, -0.85), drop, "in")
        self.squash(self.flushy, f0 + 12, 0.3)
        self.flushy_face.look(f0 + 16, 1, -0.5)
        import random as _r
        rs = _r.Random(8)
        for d in self.drops[8:16]:        # SPLASH: drops burst out of the entry point and fall back
            v = Vector((rs.uniform(-0.6, 0.6), 0, rs.uniform(1.2, 2.2)))
            lib.key(d, "location", f0 + 11, PARK, "CONSTANT")
            for k in range(0, 19, 3):
                tt = k / 30
                lib.key(d, "location", f0 + 12 + k, drop + Vector((0, -0.01, 0.1)) + v * tt + Vector((0, 0, -4.9 * tt * tt)),
                        "LINEAR")
            lib.key(d, "location", f0 + 31, PARK, "CONSTANT")
        self.act("splash", self.drops[8], f0 + 12, f0 + 30, 0.02)
        ends = [-1.5, -0.95, -0.4, 0.15]
        for i, ob in enumerate(self.heavy):
            start = self.in_tank(INLET_X + 0.25 + 0.18 * i, -1.3 + 0.06 * (i % 2))
            lib.key(ob, "location", f0 + 8 + i * 2, start)
            lib.tween(ob, "scale", f0 + 8 + i * 2, f0 + 14 + i * 2, (0.01, 0.01, 0.01), (1, 1, 1), "pop")
            t0 = heavy_cue + i * 4
            lib.key(ob, "location", t0, start)
            lib.tween(ob, "location", t0, t0 + 26, start, self.in_tank(ends[i], FLOOR + SLUDGE_T + 0.08), "bounce")
            self.act(f"heavy guy {i} sinks", ob, t0, t0 + 26, 0.035)
        # Flushy is heavy too: he sinks with them and lands in the sludge
        lib.key(self.flushy, "location", heavy_cue + 2, drop)
        lib.tween(self.flushy, "location", heavy_cue + 2, heavy_cue + 30, drop,
                  self.in_tank(-1.2, FLOOR + SLUDGE_T + 0.1), "bounce")
        self.flushy_face.surprised(heavy_cue + 4, heavy_cue + 34)
        self.flushy_face.look(heavy_cue + 36, -1, 0)
        self.flushy_face.blink(heavy_cue + 44)
        self.act("Flushy sinks", self.flushy, heavy_cue + 2, heavy_cue + 30, 0.05)
        for i, ob in enumerate(self.greasy):
            start = self.in_tank(-0.6 + 0.45 * i, -1.6)
            end = self.in_tank(-0.5 + 0.55 * i, LIQ_TOP - SCUM_T * 0.45)
            t0 = greasy_cue + i * 5
            lib.key(ob, "location", t0 - 6, start)
            lib.tween(ob, "scale", t0 - 6, t0, (0.01, 0.01, 0.01), (1, 1, 1), "pop")
            lib.tween(ob, "location", t0, t0 + 24, start, end, "elastic")
            self.act(f"greasy guy {i} floats", ob, t0, t0 + 24, 0.035)
        self.cam.shot(f0, heavy_cue - 4, dict(center=(-0.2, 0, -1.35), width=4.4, yaw=0, pitch=7),
                      dict(center=(-0.2, 0, -1.4), width=4.2, yaw=0, pitch=7))          # the whole tank first
        self.cam.shot(heavy_cue - 3, greasy_cue - 8, dict(center=(-0.75, 0, -1.6), width=2.7, yaw=-4, pitch=6),
                      dict(center=(-0.75, 0, -1.65), width=2.55, yaw=0, pitch=5))
        self.cam.shot(greasy_cue - 7, f1, dict(center=(-0.2, 0, -1.4), width=2.9, yaw=2, pitch=6),
                      dict(center=(-0.1, 0, -1.25), width=2.6, yaw=6, pitch=5), cut=False)

    def _inside_state(self, f):
        """Flushy + the gang as the sort left them (continuity for the beats inside the tank)."""
        self.snap(self.flushy, "location", f, self.in_tank(-1.2, FLOOR + SLUDGE_T + 0.1))
        for i, ob in enumerate(self.heavy):
            self.snap(ob, "location", f, self.in_tank([-1.5, -0.95, -0.4, 0.15][i], FLOOR + SLUDGE_T + 0.08))
        for i, ob in enumerate(self.greasy[:2]):
            self.snap(ob, "location", f, self.in_tank(-0.5 + 0.55 * i, LIQ_TOP - SCUM_T * 0.45))

    def baffle(self, b):
        """The bouncer: the visor slides down ("cool"), drops pass under the scum and up the tee, a greasy guy
        marches up, is squashed against the bouncer's face and bounced back; the bouncer shakes its head."""
        f0, f1 = b["f0"], b["f1"]
        self.normal_state(f0)
        self._inside_state(f0)
        hit = self.cue("baffle", "tonight", 0.8) - 6
        lib.tween(self.visor, "location", f0 + 6, f0 + 14, (0, 0, 0.45), (0, 0, 0), "bounce")
        self.act("the bouncer puts on its shades", self.visor.children[0], f0 + 4, f0 + 24, 0.03)
        path = [self.in_tank(0.7, -1.45), self.in_tank(OUTLET_X, -1.62), self.in_tank(OUTLET_X, -1.0),
                Vector((TANK["x1"] + 0.7, ACT_Y, -1.0))]
        for i, d in enumerate(self.drops[:6]):
            t0 = f0 + 18 + i * max(4, (hit - f0 - 40) // 6)
            lib.key(d, "location", t0 - 1, PARK, "CONSTANT")
            for k, p in enumerate(path):
                lib.key(d, "location", t0 + k * 10, p, "LINEAR")
            lib.key(d, "location", t0 + len(path) * 10, PARK, "CONSTANT")
        self.act("water passes the bouncer", self.drops[0], f0 + 18, f0 + 48, 0.03)
        g = self.greasy[2]
        start, door = self.in_tank(0.5, LIQ_TOP - 0.1), self.in_tank(OUTLET_X - 0.27, LIQ_TOP - 0.1)
        lib.key(g, "location", f0, start)
        lib.tween(g, "location", hit - 24, hit, start, door, "in")
        self.squash(g, hit, 0.55)
        lib.tween(g, "location", hit + 2, hit + 28, door, self.in_tank(0.35, LIQ_TOP - 0.1), "bounce")
        for k in range(4):            # "nope": the bouncer shakes its head
            lib.key(self.bouncer, "rotation_euler", hit + 2 + k * 4, (0, 0, math.radians(14 * (-1) ** k)))
        lib.key(self.bouncer, "rotation_euler", hit + 18, (0, 0, 0))
        self.act("greasy guy bounced", g, hit - 20, hit + 26, 0.06)
        # wider for the water passing, then TIGHT on the bouncer for the bounce
        self.cam.shot(f0, hit - 26, dict(center=(1.0, 0, -1.25), width=1.9, yaw=8, pitch=6),
                      dict(center=(1.05, 0, -1.22), width=1.7, yaw=4, pitch=6))
        self.cam.shot(hit - 25, f1, dict(center=(1.05, 0, -1.2), width=1.3, yaw=2, pitch=5),
                      dict(center=(1.1, 0, -1.2), width=1.2, yaw=-4, pitch=5))

    def field(self, b):
        """Drops seep from the holes; angry germs sink into the soil; Pac-Man microbes chomp them."""
        f0, f1 = b["f0"], b["f1"]
        self.normal_state(f0)
        seep, eat = self.cue("field", "seeps", 0.2), self.cue("field", "microbes", 0.5)
        holes = [x for x in self.holes if 6.8 < x < 9.6][:3]
        for i, x in enumerate(holes):
            d = self.drops[i]
            top = Vector((x, ACT_Y, FIELD["pipe_z"] - PIPE_R))
            t0 = seep + i * 5
            lib.key(d, "location", t0 - 1, PARK, "CONSTANT")
            lib.key(d, "location", t0, top, "LINEAR")
            lib.key(d, "location", t0 + 40, top + Vector((0, 0, -0.6)), "LINEAR")
            lib.key(d, "location", t0 + 41, PARK, "CONSTANT")
            germ, mic = self.germs[i], self.microbes[i]
            g0 = Vector((x + 0.05, ACT_Y, FIELD["z0"] - 0.15))
            g1 = g0 + Vector((0, 0, -0.35))
            lib.key(germ, "location", t0 + 20, g0)
            lib.tween(germ, "scale", t0 + 20, t0 + 26, (0.01, 0.01, 0.01), (1, 1, 1), "pop")
            lib.tween(germ, "location", t0 + 26, eat + 8 * i, g0, g1, "smooth")
            # Pac-Man comes in from the left, mouth working, and swallows the germ
            m0 = g1 + Vector((-0.6, 0, 0))
            bite = g1 + Vector((-0.17, 0, 0))
            t1 = eat - 6 + 8 * i
            lib.key(mic, "location", t1, m0)
            lib.tween(mic, "scale", t1, t1 + 6, (0.01, 0.01, 0.01), (1, 1, 1), "pop")
            lib.tween(mic, "location", t1 + 6, t1 + 20, m0, bite, "smooth")
            self.chomp(self.jaws[i], t1 + 6, opens=6, period=6)
            lib.tween(germ, "location", t1 + 20, t1 + 30, g1, bite + Vector((0.05, 0, 0)), "in")
            lib.tween(germ, "scale", t1 + 20, t1 + 30, (1, 1, 1), (0.001, 0.001, 0.001), "in")
            lib.tween(mic, "scale", t1 + 30, t1 + 38, (1, 1, 1), (1.25, 1.25, 1.25), "pop")   # gulp: a bit fatter
            self.act(f"Pac-Man microbe eats germ {i}", mic, t1 + 6, t1 + 38, 0.04)
            self.act(f"germ {i}", germ, t0 + 26, t1 + 20, 0.03)
        self.cam.shot(f0, eat - 8, dict(center=(7.9, 0, -1.4), width=2.5, yaw=2, pitch=7),
                      dict(center=(8.0, 0, -1.55), width=2.35, yaw=0, pitch=6))
        self.cam.shot(eat - 7, f1, dict(center=(8.1, 0, -1.95), width=2.1, yaw=0, pitch=5),
                      dict(center=(8.2, 0, -1.95), width=1.95, yaw=-4, pitch=5))

    def die(self, b):
        f0, f1 = b["f0"], b["f1"]
        self.normal_state(f0)
        self._inside_state(f0)
        w_cue, grow, esc, swamp = (self.cue("die", "wipes", 0.1), self.cue("die", "grows", 0.4),
                                   self.cue("die", "escapes", 0.55), self.cue("die", "swamp", 0.85))
        for i, wpe in enumerate(self.wipes):
            a, z = self.in_tank(INLET_X + 0.05, -0.9), self.in_tank(-1.3 + i * 0.5, LIQ_TOP - 0.05)
            lib.key(wpe, "location", w_cue - 1, PARK, "CONSTANT")
            lib.tween(wpe, "location", w_cue + i * 4, w_cue + i * 4 + 18, a, z, "bounce")
            lib.key(wpe, "rotation_euler", w_cue + i * 4, (0.2, 0.3 * i, 0.5))
            lib.key(wpe, "rotation_euler", w_cue + i * 4 + 18, (0.1, 0.1 * i, 0.2))
        self.act("wipes pile up", self.wipes[2], w_cue + 8, w_cue + 30, 0.04)
        self.flushy_face.surprised(w_cue + 10)
        for name, k in (("scum", 3.4), ("sludge", 2.8)):
            lib.tween(getattr(self, name), "scale", grow, esc, (1, 1, 1), (1, 1, k), "smooth")
        lib.tween(self.scum, "location", grow, esc, (0, 0, self.layer_base["scum"]), (0, 0, LIQ_TOP - SCUM_T * 2.8),
                  "smooth")
        lib.tween(self.water, "location", grow, esc, (0, 0, self.layer_base["water"]),
                  (0, 0, FLOOR + SLUDGE_T * 2.3 + 0.004), "smooth")
        lib.tween(self.water, "scale", grow, esc, (1, 1, 1), (1, 1, 0.3), "smooth")
        lib.tween(self.flushy, "location", grow, esc, self.in_tank(-1.2, FLOOR + SLUDGE_T + 0.1),
                  self.in_tank(-1.2, FLOOR + SLUDGE_T * 2.3 + 0.1), "smooth")
        for i, ob in enumerate(self.heavy[:2]):      # the gang rides the rising sludge
            p = self.in_tank([-1.5, -0.95][i], FLOOR + SLUDGE_T + 0.08)
            lib.tween(ob, "location", grow, esc, p, p + Vector((0, 0, SLUDGE_T * 1.3)), "smooth")
        path = [self.in_tank(OUTLET_X, -1.0)] + [Vector(p) + Vector((0, ACT_Y, 0)) for p in OUTLET[1:]] + \
               [Vector((8.2, ACT_Y, FIELD["pipe_z"]))]
        for i, ob in enumerate(self.heavy[2:]):     # two of the gang escape down the outlet into the field
            t0 = esc + i * 6
            lib.key(ob, "location", t0, self.in_tank([-0.4, 0.15][i], FLOOR + SLUDGE_T + 0.08))
            for k, p in enumerate(path):
                lib.key(ob, "location", t0 + 6 + k * 9, p, "LINEAR")
            self.act(f"gunk escapes {i}", ob, t0 + 6, t0 + 6 + 3 * 9, 0.03)
        gravel = esc + 14
        lib.node_key(self.clog, gravel + 4, 0.0)
        lib.node_key(self.clog, swamp - 16, 0.92, "SINE", "EASE_IN_OUT")
        lib.tween(self.puddle, "scale", swamp - 14, swamp + 20, (0.01, 0.01, 1), (2.4, 1.2, 1), "out")
        self.act("the lawn turns to swamp", self.puddle, swamp - 6, f1, 0.06)
        for i, s in enumerate(self.stink):
            lib.key(s, "location", swamp - 2 + i * 3, (0, 0, -0.25))
            lib.tween(s, "location", swamp - 1 + i * 3, f1, (0, 0, -0.25), (0, 0, 0.6), "linear")
        for i, fl in enumerate(self.flowers):     # the flower bed wilts
            t0 = swamp + i * 2
            lib.key(fl, "rotation_euler", t0, (0, 0, fl.rotation_euler.z))
            lib.tween(fl, "rotation_euler", t0, t0 + 16, (0, 0, fl.rotation_euler.z),
                      (math.radians(70 + 10 * (i % 3)), 0, fl.rotation_euler.z), "bounce")
        self.cam.shot(f0, gravel, dict(center=(-0.2, 0, -1.4), width=4.4, yaw=0, pitch=7),
                      dict(center=(-0.1, 0, -1.35), width=4.2, yaw=0, pitch=7))
        self.cam.shot(gravel + 1, swamp - 14, dict(center=(8.1, 0, -1.05), width=2.8, yaw=4, pitch=8),
                      dict(center=(8.2, 0, -1.0), width=2.5, yaw=0, pitch=8))
        self.cam.shot(swamp - 13, f1, dict(center=(10.3, 0, 0.25), width=4.0, yaw=-10, pitch=22),
                      dict(center=(10.4, 0, 0.3), width=3.6, yaw=-14, pitch=25))

    def float(self, b):
        f0, f1 = b["f0"], b["f1"]
        self.normal_state(f0)
        self._inside_state(f0)
        pump, flood, boat = (self.cue("float", "pumps", 0.1), self.cue("float", "flood", 0.3),
                             self.cue("float", "boat", 0.6))
        shove = self.cue("float", "shoves", 0.78)
        lib.tween(self.truck, "location", f0, pump, self.truck_home, self.truck_parked, "out")
        self.act("the pump truck arrives", self.truck.children[0], pump - 15, pump + 10, 0.05)
        self.snap(self.hose, "location", pump, (0, 0, 0))
        for name in ("sludge", "water", "scum"):    # the pump takes everything... except Flushy
            ob = getattr(self, name)
            lib.tween(ob, "scale", pump + 4, flood, (1, 1, 1), (1, 1, 0.03), "smooth")
            lib.tween(ob, "location", pump + 4, flood, (0, 0, self.layer_base[name]), (0, 0, FLOOR + 0.002), "smooth")
        for ob in self.heavy + self.greasy[:2]:
            lib.tween(ob, "scale", pump + 4, pump + 24, (1, 1, 1), (0.001, 0.001, 0.001), "in")
        lib.tween(self.flushy, "location", pump + 4, flood, self.in_tank(-1.2, FLOOR + SLUDGE_T + 0.1),
                  self.in_tank(-0.1, -1.9), "smooth")
        self.flushy_face.surprised(pump + 6)
        lib.node_key(self.water_level, flood - 2, WATER_NORMAL)
        lib.node_key(self.water_level, boat, WATER_FLOOD, "SINE", "EASE_IN_OUT")
        self.act("the groundwater rises", self.tank, flood, boat, 0.12)
        self.snap(self.hose, "location", boat, (0, 0, -30))
        pop = shove + 8
        self.burst(boat + 2, pop, f1, seed=4)
        self.cam.shot(f0, flood, dict(center=(1.2, 0, -0.5), width=6.0, yaw=-10, pitch=12),
                      dict(center=(0.2, 0, -1.0), width=5.0, yaw=-4, pitch=10))
        self.cam.shot(flood + 1, pop, dict(center=(-0.2, 0, -1.4), width=4.8, yaw=0, pitch=8),
                      dict(center=(-0.2, 0, -0.9), width=4.4, yaw=-6, pitch=6), cut=False)
        self.cam.shot(pop + 1, f1, dict(center=(-0.3, 0, 1.4), width=5.4, yaw=-14, pitch=4),
                      dict(center=(-0.6, -0.3, 3.4), width=4.6, yaw=-18, pitch=-2), cut=False, ease="out")

    def land(self, b):
        """Continuation of the launch: no reset. Flushy falls onto the lawn beside the crater, squashes flat,
        pops back, and lands the gymnast's TA-DA: arms up, big smile, held."""
        f0, f1 = b["f0"], b["f1"]
        spot = Vector((-3.2, 0.45, 0.2))      # ON the lawn, behind the cut edge
        self.surface(f0, True)                 # above ground: a lawn, never the cut face
        land = self.cue("land", "lands", 0.15) + 4
        lib.key(self.flushy, "location", f0, Vector((-2.4, 0.2, 4.5)))
        lib.tween(self.flushy, "location", f0 + 1, land, Vector((-2.4, 0.2, 4.5)), spot, "in")
        lib.key(self.flushy, "rotation_euler", land - 1, (math.radians(-540), 0, math.radians(90)))
        lib.key(self.flushy, "rotation_euler", land, (0, 0, 0))
        self.arms_pose(land - 8, "up")
        self.squash(self.flushy, land, 0.6)
        self.arms_pose(land + 1, "down")
        self.flushy_face.surprised(land + 1)
        self.flushy_face.calm(land + 14)
        self.flushy_face.blink(land + 18)
        tada = self.cue("land", "ta-da", 0.45)
        lib.tween(self.flushy, "location", tada - 2, tada + 6, spot, spot + Vector((0, 0, 0.4)), "out")
        lib.tween(self.flushy, "location", tada + 6, tada + 14, spot + Vector((0, 0, 0.4)), spot, "bounce")
        self.arms_pose(tada, "up")
        self.flushy_face.happy(tada)
        self.act("Flushy lands", self.flushy, land - 6, land + 16, 0.1)
        self.act("Flushy: ta-da", self.flushy, tada - 2, tada + 30, 0.1)
        # close at lawn level: he lands, then the TA-DA fills the frame
        self.cam.shot(f0, land + 10, dict(center=spot + Vector((0.5, 0, 0.7)), width=3.0, yaw=-22, pitch=6),
                      dict(center=spot + Vector((0.3, 0, 0.3)), width=2.2, yaw=-20, pitch=5))
        self.cam.shot(land + 11, f1, dict(center=spot + Vector((0.1, 0, 0.3)), width=1.7, yaw=-16, pitch=5),
                      dict(center=spot + Vector((0.1, 0, 0.34)), width=1.6, yaw=-20, pitch=6))

    def film(self):
        for b in self.t["beats"]:
            getattr(self, b["id"])(b)
        return self
