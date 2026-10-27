"""
PUMPED STORAGE STORY set — Blender builder (see pumped_storage_mountain_batt_story_spec.py).
Max turns a mountain into a battery so the afternoon's solar power can run his kids' outdoor movie at
night: two ponds at the same height (no head), a reservoir lifted to the summit (head), a skinny pipe
(friction), a big pressure tunnel (flow), an empty top reservoir (an ordinary turbine cannot pump),
reversible pump-turbines (pumping), shuddering fixed-speed machines (changing head) and variable-speed
motor-generators. One vertical cutaway: the mountain is sliced at y = 0 and the camera looks in from -y.

ASSET PLAN (real object -> real shape & proportions -> what makes it read at a glance -> how it is built)
- Mountain: a broad massif ~150 m tall (cartoon scale ~1 scene m = 11 m), rock on the steep flanks, grass on
  gentle ground, a flat summit plateau, banded strata on the cut face -> st.terrain_fn peaks/ridges/flats +
  st.terrain (rock_grass top, section_rock cut face), st.world_floor around it, st.scatter_on grass, pines.
- Upper reservoir: a concrete-lined basin (ring-dam reservoir) ~4 x 3.5 m, open on the section side so the
  water shows -> st.prism U-section (floor + side walls) + back wall in st.concrete, asphalt coping on the
  wall crests, st.Reservoir water with a keyable level (drains / refills). It can fly (cartoon lift).
- Lower reservoir: a lake in the valley held by a concrete gravity dam (vertical upstream face, sloped
  downstream face, crest road, lamp posts) -> terrain basin + st.Reservoir + st.dam.
- Pressure tunnel: a 7 m wide lined tunnel cut through the rock from the summit intake to the powerhouse,
  seen in section as a half tube -> st.carve(st.tube_cutter) + st.pipe (concrete lining, flowing water core,
  section-clipped). Before it is bored, rock "plug" slabs (section_rock, same texture space as the cut face)
  hide the groove; a boring machine (cutter head with teeth + yellow body) eats them away.
- Tailrace: the same construction from the powerhouse floor up into the lake bed.
- Deep cylindrical powerhouse: a vertical shaft ~9 m across and ~9 m deep inside the mountain foot, seen
  cut in half: concrete lining ring with its wall thickness on the section, a floor slab, a yellow bridge
  crane, wall lamps -> st.carve(cylinder) + half-ring / half-disk meshes.
- Ordinary turbine (olive) and two reversible pump-turbines (blue): Francis units with a snail-shaped spiral
  casing, wicket gates, a bronze runner that visibly spins (forwards = generating, backwards = pumping),
  a big ribbed motor-generator -> st.PumpTurbine cut open through its axis with st.section_clip.
- Variable-speed kit: converter cabinets with LED strips, glowing rings on the generators, a big rpm dial
  with a sweeping needle (285-315 rpm) -> boxes, torus, discs.
- Narrow twisting pipe: a skinny red pipe zigzagging down the rock face -> st.pipe (flowing core).
- First-try connector: a plain pipe from the valley pond to the powerhouse -> st.pipe.
- Valley: Max's family house (siding, shingled gable, glowing windows, porch light) -> st.House; a solar
  field of tilted blue panels on legs -> st.solar_array; wooden power poles + sagging cables to the house;
  a transformer; Max's test lamp (post, switch box, big bulb) whose glow tells the power.
- Outdoor movie: a white screen on two posts, a projector on a stool with a soft light beam, a low bench.
- Kids' camping lanterns (the running gag) -> st.lantern in their hands with keyable glow + point lights.
- Fact arrows / labels: blue water arrows, yellow power arrows, red friction arrows, a yellow HEAD dimension,
  short labels (TINY HEAD, HEAD 150 m, FRICTION, 7 m TUNNEL, PUMP-TURBINES, FIXED SPEED, 285-315 rpm).
"""
import bisect
import math
import random

import bmesh
import bpy
from mathutils import Vector

from engine import events, studio as st, textures as tx, toy
from engine.camera import CameraRig, facing_to
from engine.character import Character
from engine.cutaway import _node_curves, flow_material, key_node_value
from engine.machines import Puffs
from engine.sets.pumped_storage_mountain_batt_story_spec import ACTIONS, beat_actions

V = Vector
R = math.radians

# ------------------- layout (scene metres; the section face is y = 0, the camera looks from -y) -------------------
MTN_X = -4.6
PLAT_X0, PLAT_X1, PLAT_Z = -7.8, -0.9, 12.0       # summit plateau
SHAFT_X, SHAFT_R, LINE_T = 1.2, 3.0, 0.25          # powerhouse shaft (inner face of the lining)
SHAFT_BOT, SHAFT_TOP = -9.6, -1.2
FLOOR_Z = -8.5                                     # powerhouse floor (slab top)
PIT_X0, PIT_X1, PIT_Z = 5.2, 9.0, -1.3             # pit of the first (flat) pond
BASIN_X0, BASIN_X1, BASIN_Y1, BASIN_Z = 11.4, 16.0, 6.5, -2.6
LOW_X0, LOW_X1, LOW_Y1 = 10.25, 16.4, 7.8          # lower lake water box
DAM_X = 16.9                                       # dam crest centre (upstream face x = 16.4)
DOWN_Z = -1.6
LOW_LEVEL = -0.35
TANK_HW, TANK_Y0, TANK_Y1, TANK_FL, TANK_TOP, TANK_T = 1.9, 0.12, 3.6, 0.3, 1.6, 0.22
TANK_FULL = 1.42                                   # tank-local water level
TANK_DRY = 0.42                                    # a puddle
TANK_LOW = V((7.1, 0, -1.4))                       # sunk in the valley pit, beside the lake
TANK_HIGH = V((-4.25, 0, 11.95))                   # on the summit
S = 0.6                                            # pump-turbine size
UNIT_Y, UNIT_Z = 0.75, FLOOR_Z + 0.006
A_X, B_X = -0.2, 2.9
ZC = UNIT_Z + 0.9 * S                              # runner / inlet height
RT, RTR = 0.55, 0.42                               # tunnel and tailrace radii
T_PTS = [(-3.3, 0, 12.3), (-3.3, 0, 9.8), (-2.95, 0, 4.0), (-2.75, 0, -3.5), (-2.6, 0, -6.6), (-2.25, 0, -7.8),
         (-1.95, 0, -7.954)]
TR_PTS = [(4.25, 0, -9.05), (6.2, 0, -8.7), (8.9, 0, -6.1), (10.9, 0, -3.5), (11.7, 0, -2.25)]
CONN_PTS = [(5.75, 0.5, -0.95), (5.0, 0.45, -0.85), (4.6, -0.25, -0.7), (2.0, -0.25, -0.7), (-2.35, -0.25, -0.75),
            (-2.35, -0.25, -7.3), (-2.05, -0.05, -7.954), (-1.85, 0.05, -7.954)]
# people
VAL = V((9.5, 0.8, 0))                             # Max's test-lamp spot in the valley
TOP = V((-7.05, 1.1, PLAT_Z))                     # Max on the summit, left of the reservoir
PH = V((1.2, 1.25, FLOOR_Z))                       # Max on the powerhouse floor, between the machines
YARD_MAX = V((10.4, 8.8, 0))
KID_SPOTS = [V((11.25, 9.25, 0)), V((11.85, 9.1, 0))]
MOVIE_MAX = V((14.9, 9.2, 0))
BENCH = V((15.7, 9.6, 0))
BENCH_YAW = -20.0
SCREEN = V((16.6, 12.0, 0))
HOOK_MAX = V((-3.75, 1.5, TANK_HIGH.z + TANK_FL))
HOOK_KIDS = [V((-1.95, 1.0, PLAT_Z)), V((-1.4, 1.45, PLAT_Z))]
# valley power line
TRAFO = V((4.3, 1.0, 0))
POLES = [V((5.0, 5.2, 0)), V((8.4, 7.6, 0)), V((10.4, 10.2, 0))]
HOUSE = V((12.6, 12.8, 0))
HOUSE_PT = V((10.55, 11.3, 2.1))
SOLAR_PT = V((9.9, 10.0, 1.3))

# sun energy, sun colour, sky strength, fill energy, SKY SUN ELEVATION (deg): the sky model's own sun sets too,
# otherwise dusk and night keep a bright blue daytime sky
LIGHTS = {"day": (4.2, (1.0, 0.95, 0.86), 0.22, 900.0, 42.0),
          "afternoon": (3.8, (1.0, 0.85, 0.66), 0.18, 800.0, 22.0),
          "dusk": (1.6, (1.0, 0.56, 0.33), 0.2, 430.0, 1.2),
          "night": (0.55, (0.5, 0.6, 1.0), 0.5, 320.0, -5.5)}
LANTERN_GLOW, LANTERN_LIGHT = 9.0, 70.0
BLUE, YELLOW, RED = "#3FA9F5", "#FFD23F", "#FF4A3A"


def _mat(name, hexc, rough=0.5, **kw):
    return toy.material(name, toy.srgb(hexc), roughness=rough, **kw)


def _recalc(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def half_ring(name, cx, cy, r_in, r_out, z0, z1, mat, n=72):
    """The back half (y >= cy) of a thick cylinder wall: its two cut ends show the wall thickness."""
    verts, faces = [], []
    for k in range(n + 1):
        a = math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        for r in (r_in, r_out):
            for z in (z0, z1):
                verts.append((cx + r * c, cy + r * s, z))
    for k in range(n):
        a, b = 4 * k, 4 * (k + 1)
        faces += [(a + 2, b + 2, b + 3, a + 3), (a, a + 1, b + 1, b), (a + 1, a + 3, b + 3, b + 1),
                  (a, b, b + 2, a + 2)]
    faces += [(0, 2, 3, 1), (4 * n, 4 * n + 1, 4 * n + 3, 4 * n + 2)]
    return _recalc(st.mesh_obj(name, verts, faces, (mat,), smooth=False))


def half_disk(name, cx, cy, r, z0, z1, mat, n=72):
    """A half-disc slab (y >= cy) between z0 and z1."""
    ring = [(cx + r * math.cos(math.pi * k / n), cy + r * math.sin(math.pi * k / n)) for k in range(n + 1)]
    m = len(ring)
    verts = [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
    faces = [tuple(range(m - 1, -1, -1)), tuple(range(m, 2 * m))]
    faces += [(k, (k + 1) % m, m + (k + 1) % m, m + k) for k in range(m)]
    return _recalc(st.mesh_obj(name, verts, faces, (mat,), smooth=False))


def _cone(name, radius, depth, loc, mat, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=radius, depth=depth, vertices=16, location=loc, rotation=rot)
    c = bpy.context.active_object
    c.name = name
    toy._finish(c, mat, subdiv=0, smooth=False, parent=parent)
    return c


class _Flow:
    """The moving stripes inside a water core, with a speed that ramps, stops and REVERSES (generating vs
    pumping). sign = +1 if generating water moves toward +Z along this conduit, -1 if it moves down."""

    def __init__(self, core, sign):
        self.mat = core.data.materials[0]
        self.mat.node_tree.animation_data_clear()             # our own keys only (the copy shared an action)
        self.mp = next(n for n in self.mat.node_tree.nodes if n.type == "MAPPING")
        self.sign = sign
        self.pts = {1: 0.0}

    def speed(self, f, v):
        """Reach speed v (m/s, + = generating direction) at frame f (linear ramps between calls)."""
        self.pts[int(f)] = float(v)

    def on(self, f, v):
        key_node_value(self.mat, "flow_on", f, v)

    def build(self, last):
        ks = sorted(self.pts.items())
        fs = [k for k, _ in ks]

        def v_at(f):
            j = bisect.bisect_right(fs, f) - 1
            if j < 0:
                return ks[0][1]
            if j >= len(ks) - 1:
                return ks[-1][1]
            (f0, v0), (f1, v1) = ks[j], ks[j + 1]
            return v0 + (v1 - v0) * (f - f0) / max(1, f1 - f0)

        sock = self.mp.inputs["Location"]
        s, prev = 0.0, v_at(1)
        for f in range(1, last + 1):
            cur = v_at(f)
            s += 0.5 * (prev + cur) / 30.0
            prev = cur
            if f % 3 == 1 or f == last:
                sock.default_value = (0, 0, -self.sign * s)
                sock.keyframe_insert("default_value", index=2, frame=f)
        for fc in _node_curves(self.mat):
            if self.mp.name in fc.data_path:
                for kp in fc.keyframe_points:
                    toy.set_key_interpolation(self.mat.node_tree, fc, kp, "LINEAR")


class PumpedStorageMountainBattStorySet:
    ACTIONS = ACTIONS
    QA_ALLOW = (r"ground_|plug|upres|lake_water|water_surface|ph_|turb0|unit[AB]|tunnel|tailrace|narrow_pipe"
                r"|connector_pipe|dam|pine|pole|cable|trafo|house|solar|movie|bench|projector|lantern|testlamp"
                r"|tbm|headdim|press_|arrow|puff|vs_|gauge|cabinet|g_mtn|puddle")

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self.rnd = random.Random(11)
        self.sec = toy.empty("section_cut", (0, 0, 0))              # static cut plane at the section face
        self.usec = toy.empty("unit_section", (0, UNIT_Y, 0))      # cuts the machines through their axis
        self.flows = []
        self.sky = next((n for n in scene.world.node_tree.nodes if n.type == "TEX_SKY"), None)
        self._light_state = LIGHTS["afternoon"]
        self._lan_on = False
        self._world()
        self._powerhouse()
        self._conduits()
        self._tank()
        self._valley()
        self._people()
        self._key_light(1, LIGHTS["afternoon"])

    # ------------------- world -------------------

    def _world(self):
        self.hf = st.terrain_fn(
            peaks=[(MTN_X, 1.2, 16.0, 7.5), (-17.0, 15.0, 12.0, 8.0), (26.0, 24.0, 11.0, 9.0)],
            ridges=[(-30.0, 27.0, 34.0, 31.0, 14.0, 8.0), (-8.0, 12.0, -2.0, 22.0, 10.0, 5.0)],
            flats=[(3.8, 40.0, -2.0, 18.0, 0.0, 2.2),                         # valley floor
                   (PIT_X0, PIT_X1, -2.0, 4.0, PIT_Z, 0.5),                    # the first pond's pit
                   (BASIN_X0, BASIN_X1, -2.0, BASIN_Y1, BASIN_Z, 1.4),         # lower lake bed
                   (17.2, 40.0, -2.0, 9.0, DOWN_Z, 1.0),                       # valley below the dam
                   (PLAT_X0, PLAT_X1, -2.0, 4.6, PLAT_Z, 1.4)],                # summit plateau
            detail=0.35, seed=3)
        self.ground = st.terrain("ground_mtn", -30.0, 40.0, 0.0, 40.0, self.hf, floor=-80.0, res=0.5)
        st.world_floor(0.0, around=(-30.0, 40.0, 40.0))
        st.scatter_on("g_mtn", self.ground, density=2.5, max_slope_deg=26, size=1.2, seed=4)
        bpy.ops.mesh.primitive_cylinder_add(radius=SHAFT_R + LINE_T + 0.01, depth=SHAFT_TOP - SHAFT_BOT, vertices=72,
                                            location=(SHAFT_X, 0, (SHAFT_TOP + SHAFT_BOT) / 2))
        st.carve(self.ground, bpy.context.active_object)
        st.carve(self.ground, st.tube_cutter(T_PTS, RT + 0.09, extend=0.5))
        st.carve(self.ground, st.tube_cutter(TR_PTS, RTR + 0.08, extend=0.3))
        bark = tx.wood("pine_bark", "#5A4632", "#74604A", along="z")
        needles = toy.noise_material("pine_needles", toy.srgb("#2F5A2A"), toy.srgb("#46783A"), scale=7, bump=0.5)
        for k, (x, y, s) in enumerate(((-12.0, 8.0, 1.2), (-9.5, 12.5, 1.0), (2.5, 14.0, 1.1), (5.0, 17.0, 1.3),
                                       (19.0, 14.0, 1.0), (21.5, 12.0, 1.2), (-0.5, 10.0, 0.9), (8.0, 16.5, 1.0),
                                       (16.0, 16.5, 1.1), (23.0, 16.0, 1.3), (-14.5, 5.0, 1.1))):
            z = self.hf(x, y) - 0.15
            toy.cylinder(f"pine_trunk{k}", 0.13 * s, 1.2 * s, (x, y, z + 0.6 * s), mat=bark, vertices=10)
            for j, (r, h, dz) in enumerate(((0.9, 1.5, 1.4), (0.7, 1.3, 2.2), (0.45, 1.1, 2.9))):
                _cone(f"pine_cone{k}_{j}", r * s, h * s, (x, y, z + dz * s), needles)

    def _powerhouse(self):
        conc = st.concrete("ph_concrete", "#BDB8AE", lift=1.0, panel=1.5)
        self.lining = half_ring("ph_lining", SHAFT_X, 0.012, SHAFT_R, SHAFT_R + LINE_T, SHAFT_BOT + 0.05,
                                SHAFT_TOP - 0.06, conc)
        half_disk("ph_floor_slab", SHAFT_X, 0.01, SHAFT_R - 0.005, SHAFT_BOT + 0.05, FLOOR_Z,
                  st.concrete("ph_slab", "#A39D92", lift=0.35, panel=0.9))
        yellow = tx.paint("ph_crane_paint", "#E8B320", 0.4, coat=0.4)
        steel = tx.metal("ph_steel", "#5F656B", 0.35)
        toy.box("ph_crane_beam", (5.0, 0.35, 0.45), (SHAFT_X, 1.6, -2.5), mat=yellow, bevel=0.02)
        toy.box("ph_crane_trolley", (0.6, 0.55, 0.3), (SHAFT_X + 0.9, 1.6, -2.85), mat=steel, bevel=0.02)
        toy.cylinder("ph_crane_rope", 0.02, 1.0, (SHAFT_X + 0.9, 1.6, -3.5), mat=steel, vertices=8)
        toy.box("ph_crane_hook", (0.22, 0.12, 0.3), (SHAFT_X + 0.9, 1.6, -4.1), mat=steel, bevel=0.02)
        self.ph_lamp_mat = st.glow_mat("ph_lamp_glow", "#FFE2A8", 3.0)
        for k, a in enumerate((35, 90, 145)):
            c, s_ = math.cos(R(a)), math.sin(R(a))
            lamp = toy.box(f"ph_lamp{k}", (0.42, 0.1, 0.14), (SHAFT_X + 2.93 * c, 0.012 + 2.93 * s_, -3.6),
                           mat=self.ph_lamp_mat, bevel=0.01)
            lamp.rotation_euler = (0, 0, R(a - 90))
        ld = bpy.data.lights.new("ph_light", "AREA")
        ld.energy, ld.size, ld.color = 750.0, 8.0, (1.0, 0.93, 0.82)
        lo = bpy.data.objects.new("ph_light", ld)
        self.scene.collection.objects.link(lo)
        lo.location = (SHAFT_X, -6.0, -4.2)
        lo.rotation_euler = (V((SHAFT_X, 1.4, -8.0)) - V(lo.location)).to_track_quat("-Z", "Y").to_euler()
        # the machines: an ordinary turbine first, two reversible pump-turbines later
        self.turb0 = self._unit("turb0", A_X, "#6E8A4F", "#A9AEB4")
        toy.hide_tree(self.turb0.root, 0, False)       # on stage from the start (it is hidden later, when replaced)
        self.unitA = self._unit("unitA", A_X, "#3D6E9E", "#D9A531")
        self.unitB = self._unit("unitB", B_X, "#3D6E9E", "#D9A531")
        self.feedB = toy.cylinder("unitB_feed", 0.25, 0.8, (B_X - 0.63, 2.62, ZC), rotation=(R(90), 0, 0),
                                  mat=tx.paint("st_casing_#3D6E9E", "#3D6E9E", 0.32, coat=0.55), vertices=24)
        for o in (self.unitA.root, self.unitB.root, self.feedB):
            toy.hide_tree(o, 0, True)
        # variable-speed kit (hidden until it is installed)
        cab = tx.paint("cabinet_paint", "#D9DEE3", 0.4, coat=0.3)
        self.led = st.glow_mat("vs_led_glow", "#3DFF7A", 0.0)
        self.cabinets = []
        for k, x in enumerate((0.25, 1.6)):
            c = toy.box(f"cabinet{k}", (0.62, 0.36, 1.25), (x, 2.42, FLOOR_Z + 0.63), mat=cab, bevel=0.02)
            for j in range(3):
                toy.box(f"cabinet{k}_led{j}", (0.42, 0.02, 0.05), (0, -0.19, 0.35 - 0.12 * j), mat=self.led, bevel=0,
                        parent=c)
            self.cabinets.append(c)
        self.rings = []
        for u in (self.unitA, self.unitB):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.66, minor_radius=0.045, major_segments=48, minor_segments=8,
                                             location=(u.root.location.x, UNIT_Y, UNIT_Z + 1.8))
            ring = bpy.context.active_object
            ring.name = f"vs_ring_{u.name}_glow"
            ring.data.materials.append(self.led)
            self.rings.append(ring)
        face = tx.paint("gauge_face_paint", "#F4F1EA", 0.4, coat=0.5)
        self.gauge = toy.empty("gauge", (SHAFT_X, 2.88, -5.6))
        toy.cylinder("gauge_rim", 0.5, 0.08, (0, 0, 0), rotation=(R(90), 0, 0), mat=steel, parent=self.gauge,
                     vertices=48)
        toy.cylinder("gauge_face", 0.44, 0.04, (0, -0.03, 0), rotation=(R(90), 0, 0), mat=face, parent=self.gauge,
                     vertices=48)
        band = _mat("gauge_band", "#2FB65A", 0.5)
        for k, a in enumerate(range(-55, 56, 11)):
            t = toy.box(f"gauge_tick{k}", (0.03, 0.02, 0.09), (0.36 * math.sin(R(a)), -0.055, 0.36 * math.cos(R(a))),
                        mat=band if abs(a) <= 55 else steel, bevel=0, parent=self.gauge)
            t.rotation_euler = (0, R(a), 0)
        self.needle = toy.empty("gauge_needle_pivot", (0, -0.07, 0), self.gauge)
        toy.box("gauge_needle", (0.035, 0.015, 0.34), (0, 0, 0.15), mat=_mat("gauge_red", "#D8342C", 0.4), bevel=0,
                parent=self.needle)
        toy.sphere("gauge_hub", 0.04, (0, -0.075, 0), mat=steel, parent=self.gauge, subdiv=0)
        for o in self.cabinets + self.rings + [self.gauge]:
            toy.hide_tree(o, 0, True)

    def _unit(self, name, x, casing, gen):
        u = st.PumpTurbine(name, (x, UNIT_Y, UNIT_Z), size=S, casing=casing, gen=gen, facing_deg=-90)
        bpy.data.objects.remove(u.draft, do_unlink=True)          # under the floor slab
        for o in list(u.root.children):
            if any(t in o.name for t in ("_spiral", "_stayring", "_generator", "_gencap", "_rib", "_wicket")):
                st.section_clip(o, self.usec)                       # cut open through the axis: runner shows
        return u

    def _pipe(self, name, pts, radius, mat, sign, section=True, flange=2.0, wall=0.05):
        fm = flow_material(f"{name}_flowmat", 1.0, 1.0, base="#2F8FE0", stripe="#CFEFFF")
        root = st.pipe(name, pts, radius, mat=mat, wall=wall, flange_every=flange, flow=fm,
                       section=self.sec if section else None)
        core = bpy.data.objects[root["water"]]
        if section:
            st.section_clip(core, self.sec)
        flow = _Flow(core, sign)
        self.flows.append(flow)
        return root, flow

    def _slope_x(self, z):
        """x on the mountain's right flank (cut face) where the surface is at height z."""
        lo, hi = -0.9, 6.0
        for _ in range(30):
            mid = (lo + hi) / 2
            if self.hf(mid, 0.0) > z:
                lo = mid
            else:
                hi = mid
        return lo

    def _conduits(self):
        lining = st.concrete("tunnel_lining", "#A3A6A8", lift=0.6, panel=1.0)
        self.tunnel, self.f_tun = self._pipe("tunnel", T_PTS, RT, lining, -1, flange=1.6)
        self.tailrace, self.f_tail = self._pipe("tailrace", TR_PTS, RTR, lining, +1, flange=1.6)
        toy.hide_tree(self.tunnel, 0, True)
        # the skinny twisting pipe: out of the summit reservoir's wall, zigzagging down the rock face
        pts = [(-2.9, 0.5, 12.6), (-2.1, 0.5, 12.55), (-1.75, -0.25, 12.3)]
        self.zig = []
        for k in range(9):
            z = 11.4 - 1.45 * k
            x = -2.75 if k % 2 else min(1.4, self._slope_x(z) - 0.55)
            pts.append((x, -0.25, z))
            self.zig.append(V((x, -0.25, z)))
        pts += [(-2.35, -0.25, -1.4), (-2.35, -0.25, -7.3), (-2.05, -0.05, -7.954), (-1.85, 0.05, -7.954)]
        self.narrow, self.f_narrow = self._pipe("narrow_pipe", pts, 0.085, tx.paint("narrow_red", "#C8402C", 0.35, coat=0.5),
                                                -1, section=False, flange=0.9, wall=0.025)
        self.conn, self.f_conn = self._pipe("connector_pipe", CONN_PTS, 0.14, tx.paint("conn_paint", "#5E7A8C", 0.35),
                                            -1, section=False, flange=1.4, wall=0.03)
        for o in (self.narrow, self.conn):
            toy.hide_tree(o, 0, True)
        # rock plugs over the tunnel groove until it is bored, and the boring machine
        P = st._spline_pts(T_PTS, 0.25)
        cum = [0.0]
        for a, b in zip(P, P[1:]):
            cum.append(cum[-1] + (b - a).length)
        self.tpath, self.tcum = P, cum
        rock = st.section_rock()
        self.plugs = []
        Q = [p for p in st._spline_pts(T_PTS, 0.7) if p.z <= 11.85 and p.x <= -2.15]
        r = RT + 0.2
        for k, (a, b) in enumerate(zip(Q, Q[1:])):
            d = V((b.x - a.x, 0, b.z - a.z)).normalized()
            n = V((-d.z, 0, d.x))
            a2, b2 = a - d * 0.08, b + d * 0.08
            quad = [a2 + n * r, a2 - n * r, b2 - n * r, b2 + n * r]
            ob = st.prism(f"plug{k}", [(p.x, p.z) for p in quad], -0.006 - 0.006 * (k % 2), r + 0.1, rock)
            ob.visible_shadow = False
            self.plugs.append((ob, self._arc_of((a + b) / 2)))
        self.tbm = toy.empty("tbm", (0, 0, 0))
        yellow = tx.paint("tbm_paint", "#E8B320", 0.35, coat=0.5)
        steel = tx.metal("tbm_steel", "#6F757B", 0.3)
        parts = [toy.cylinder("tbm_head", RT - 0.04, 0.22, (0, 0, 0.1), mat=steel, parent=self.tbm, vertices=32),
                 toy.cylinder("tbm_body", RT - 0.08, 1.3, (0, 0, -0.75), mat=yellow, parent=self.tbm, vertices=32)]
        for k in range(10):
            a = 2 * math.pi * k / 10
            parts.append(toy.box(f"tbm_tooth{k}", (0.08, 0.08, 0.1), (0.32 * math.cos(a), 0.32 * math.sin(a), 0.25),
                                 mat=steel, bevel=0.01, parent=self.tbm))
        for o in parts:
            st.section_clip(o, self.sec)
        toy.hide_tree(self.tbm, 0, True)

    def _arc_of(self, p):
        j = min(range(len(self.tpath)), key=lambda k: (self.tpath[k] - p).length)
        return self.tcum[j] / self.tcum[-1]

    def _tun_at(self, t):
        """Point and downhill tangent at arc fraction t of the tunnel."""
        s = max(0.0, min(1.0, t)) * self.tcum[-1]
        j = max(0, min(len(self.tpath) - 2, bisect.bisect_right(self.tcum, s) - 1))
        a, b = self.tpath[j], self.tpath[j + 1]
        seg = max(1e-6, self.tcum[j + 1] - self.tcum[j])
        return a.lerp(b, (s - self.tcum[j]) / seg), (b - a).normalized()

    def _tank(self):
        self.tank = toy.empty("upres", TANK_LOW)
        conc = st.concrete("upres_concrete", "#B9B4A8", lift=0.5, panel=1.2)
        hw, t, fl, top = TANK_HW, TANK_T, TANK_FL, TANK_TOP
        u = [(-hw, 0), (hw, 0), (hw, top), (hw - t, top), (hw - t, fl), (-hw + t, fl), (-hw + t, top), (-hw, top)]
        body = st.prism("upres_floor", u, TANK_Y0, TANK_Y1, conc)
        body.parent = self.tank
        toy.box("upres_back", (2 * (hw - t), t, top - fl), (0, TANK_Y1 - t / 2 - 0.006, fl + (top - fl) / 2), mat=conc,
                bevel=0, parent=self.tank)
        road = st.asphalt()
        for k, x in enumerate((-hw + t / 2, hw - t / 2)):
            toy.box(f"upres_coping{k}", (t + 0.06, TANK_Y1 - TANK_Y0, 0.06), (x, (TANK_Y0 + TANK_Y1) / 2, top + 0.036),
                    mat=road, bevel=0, parent=self.tank)
        toy.box("upres_grate", (0.7, 0.5, 0.05), (0.95, 0.75, fl + 0.031), mat=tx.metal("grate", "#3E4246", 0.4),
                bevel=0, parent=self.tank)
        self.up = st.Reservoir("upper_lake", -hw + t + 0.012, hw - t - 0.012, TANK_Y0 + 0.012, TANK_Y1 - t - 0.012,
                               bottom=fl + 0.006, level=TANK_FULL)
        for o in (self.up.vol, self.up.surf):
            o.parent = self.tank
        # the drained basin: water hidden, a dark wet puddle left on the floor (one irregular mesh, no bump)
        rnd = random.Random(7)
        ring = []
        for k in range(24):
            a = 2 * math.pi * k / 24
            r = 0.55 * (1 + 0.28 * math.sin(3 * a + 0.7) + 0.12 * rnd.uniform(-1, 1))
            ring.append((0.25 + 1.35 * r * math.cos(a), 1.75 + r * math.sin(a), fl + 0.012))
        pud = bpy.data.materials.new("upres_puddle")
        bsdf = toy._principled(pud)
        toy._set(bsdf, "Base Color", (*toy.srgb("#2E5E7A"), 1))
        toy._set(bsdf, "Roughness", 0.05)
        toy._set(bsdf, "Coat Weight", 1.0)
        self.puddle = st.mesh_obj("upres_puddle", ring, [tuple(range(24))], (pud,), smooth=False)
        self.puddle.parent = self.tank
        self.puddle.visible_shadow = False
        stain = st.concrete("upres_wet", "#7C786F", lift=0.5, panel=1.2)
        self.wet = toy.box("upres_wetfloor", (2 * (hw - t) - 0.02, TANK_Y1 - TANK_Y0 - t - 0.02, 0.004),
                           (0, (TANK_Y0 + TANK_Y1 - t) / 2, fl + 0.003), mat=stain, bevel=0, parent=self.tank)
        for o in (self.puddle, self.wet):
            toy.hide_tree(o, 0, True)
        toy.hide_tree(self.tank, 0, True)
        self.low = st.Reservoir("lower_lake", LOW_X0, LOW_X1, 0.03, LOW_Y1, bottom=BASIN_Z - 0.06, level=LOW_LEVEL)
        st.dam("dam", DAM_X, 0.02, 11.0, BASIN_Z - 0.1, 3.4, crest=1.0, facing=1)
        self._lvl = {"up": TANK_FULL, "low": LOW_LEVEL}

    def _valley(self):
        self.house = st.House("house", HOUSE)
        st.solar_array("solar", (7.6, 10.0, 0), rows=2, cols=4, panel=(1.0, 1.6), tilt=25)
        wood = tx.wood("pole_wood", "#6B5038", "#8A6A4A", along="z")
        steel = tx.metal("cable_metal", "#2B2E31", 0.5)
        tops = []
        for k, p in enumerate(POLES):
            toy.cylinder(f"pole{k}", 0.09, 3.3, (p.x, p.y, 1.65), mat=wood, vertices=12)
            toy.box(f"pole{k}_arm", (1.0, 0.1, 0.1), (p.x, p.y, 3.05), mat=wood, bevel=0.01)
            tops.append(V((p.x, p.y, 3.05)))
        trafo = tx.paint("trafo_paint", "#7D8A7F", 0.45, coat=0.2)
        toy.box("trafo_body", (0.8, 0.7, 1.0), (TRAFO.x, TRAFO.y, 0.5), mat=trafo, bevel=0.03)
        for k in range(4):
            toy.box(f"trafo_fin{k}", (0.2, 0.04, 0.75), (TRAFO.x + 0.5, TRAFO.y - 0.24 + 0.16 * k, 0.5), mat=trafo,
                    bevel=0)
        toy.cylinder("trafo_bushing", 0.06, 0.4, (TRAFO.x, TRAFO.y, 1.2), mat=_mat("porcelain", "#7A3B2E", 0.3))
        self.line_nodes = [V((TRAFO.x, TRAFO.y, 1.35))] + tops + [HOUSE_PT]
        for k, (a, b) in enumerate(zip(self.line_nodes, self.line_nodes[1:])):
            mid = (a + b) / 2 - V((0, 0, 0.35))
            cab = st._curve_obj(f"cable{k}", st._spline_pts([a, mid, b], 0.2), 0.022, caps=True)
            cab.data.materials.append(steel)
        sol = st._curve_obj("cable_solar", st._spline_pts([SOLAR_PT, (SOLAR_PT + tops[2]) / 2 - V((0, 0, 0.3)),
                                                            tops[2]], 0.2), 0.022)
        sol.data.materials.append(steel)
        # Max's test lamp: post, switch box, big bulb
        metal = tx.metal("testlamp_metal", "#6B7077", 0.35)
        lamp_x, lamp_y = VAL.x + 0.5, VAL.y + 0.8
        toy.cylinder("testlamp_post", 0.04, 1.75, (lamp_x, lamp_y, 0.875), mat=metal, vertices=12)
        toy.box("testlamp_switch", (0.16, 0.12, 0.22), (lamp_x - 0.08, lamp_y - 0.05, 1.05),
                mat=tx.paint("switch_paint", "#C9452E", 0.4), bevel=0.01)
        toy.cylinder("testlamp_socket", 0.07, 0.12, (lamp_x, lamp_y, 1.8), mat=metal, vertices=16)
        self.bulb_mat = st.glow_mat("testlamp_bulb_glow", "#FFE7A3", 0.0)
        toy.sphere("testlamp_bulb", 0.14, (lamp_x, lamp_y, 1.98), scale=(1, 1, 1.2), mat=self.bulb_mat, subdiv=1)
        bd = bpy.data.lights.new("testlamp_light", "POINT")
        bd.energy, bd.color, bd.shadow_soft_size = 0.0, (1.0, 0.85, 0.55), 0.15
        self.bulb_light = bpy.data.objects.new("testlamp_light", bd)
        self.scene.collection.objects.link(self.bulb_light)
        self.bulb_light.location = (lamp_x, lamp_y - 0.35, 1.98)
        # outdoor cinema: screen, projector + beam, a low bench, parked lanterns
        frame_wood = tx.wood("movie_wood", "#7A5A3C", "#96714C", along="z")
        self.screen_root = toy.empty("movie", SCREEN, rotation=(0, 0, R(-20)))
        for k, x in enumerate((-1.35, 1.35)):
            toy.cylinder(f"movie_post{k}", 0.06, 2.5, (x, 0.05, 1.25), mat=frame_wood, parent=self.screen_root,
                         vertices=12)
        toy.box("movie_frame", (2.75, 0.06, 1.7), (0, 0.05, 1.55), mat=frame_wood, bevel=0.01, parent=self.screen_root)
        self.screen_mat = self._movie_material()
        toy.box("movie_screen", (2.5, 0.02, 1.5), (0, 0.008, 1.55), mat=self.screen_mat, bevel=0, parent=self.screen_root)
        stool = V((16.1, 10.6, 0))
        toy.box("projector_stool", (0.42, 0.42, 0.55), (stool.x, stool.y, 0.275), mat=frame_wood, bevel=0.02)
        toy.box("projector_body", (0.36, 0.3, 0.2), (stool.x, stool.y, 0.656), mat=tx.paint("proj_paint", "#2E3440", 0.4),
                bevel=0.02)
        lens = stool + V((0.06, 0.17, 0.66))
        toy.cylinder("projector_lens", 0.05, 0.08, tuple(lens), rotation=(R(-90), 0, 0), mat=steel, vertices=16)
        mw = toy.empty("tmp_screen_m", SCREEN, rotation=(0, 0, R(-20)))
        bpy.context.view_layer.update()
        corners = [mw.matrix_world @ V((sx * 1.2, -0.01, 1.55 + sz * 0.72)) for sx, sz in ((-1, -1), (1, -1), (1, 1),
                                                                                              (-1, 1))]
        bpy.data.objects.remove(mw, do_unlink=True)
        beam_mat = bpy.data.materials.new("projector_beam_mat")
        bsdf = toy._principled(beam_mat)
        toy._set(bsdf, "Base Color", (1, 0.97, 0.88, 1))
        toy._set(bsdf, "Emission Color", (1, 0.96, 0.85, 1))
        toy._set(bsdf, "Emission Strength", 1.2)
        toy._set(bsdf, "Alpha", 0.12)
        if hasattr(beam_mat, "surface_render_method"):
            beam_mat.surface_render_method = "BLENDED"
        self.beam = st.mesh_obj("projector_beam", [tuple(lens + V((0, 0.05, 0)))] + [tuple(c) for c in corners],
                                [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1)], (beam_mat,), smooth=False)
        self.beam.visible_shadow = False
        toy.hide_tree(self.beam, 0, True)
        planks = tx.planks("bench_planks", "#9C7450", "#B0865C", width=0.15, across="y", along="x")
        self.bench = toy.empty("bench", BENCH, rotation=(0, 0, R(BENCH_YAW)))
        toy.box("bench_deck", (1.5, 0.45, 0.04), (0, 0, 0.08), mat=planks, bevel=0.005, parent=self.bench)
        for k, x in enumerate((-0.6, 0.6)):
            toy.box(f"bench_leg{k}", (0.12, 0.4, 0.055), (x, 0, 0.0275), mat=planks, bevel=0.005, parent=self.bench)
        self.parked = []
        for k, p in enumerate((V((15.2, 10.3, 0)), V((15.5, 10.45, 0)))):
            ln = st.lantern(f"parked_lantern{k}")
            ln.location = p
            ln.scale = (1.3, 1.3, 1.3)
            toy.hide_tree(ln, 0, True)
            self.parked.append(ln)
        yl = bpy.data.lights.new("yard_light", "AREA")
        yl.energy, yl.size, yl.color = 0.0, 6.0, (0.75, 0.82, 1.0)
        self.yard_light = bpy.data.objects.new("yard_light", yl)
        self.scene.collection.objects.link(self.yard_light)
        self.yard_light.location = (13.4, 4.2, 4.2)
        self.yard_light.rotation_euler = (V((15.0, 9.4, 1.0)) - V((13.4, 4.2, 4.2))).to_track_quat("-Z", "Y").to_euler()

    def _movie_material(self):
        """The outdoor-movie picture: a cartoon landscape (sunset sky, rolling hills, a sun that crosses the
        screen as the film plays). Emission is keyed with st.key_glow; the sun's x with key_node_value."""
        from engine.cutaway import _mat_node_value
        t = tx._Tree("movie_screen_glow")
        x, z = t.xyz["x"], t.xyz["z"]
        sky = t.ramp(t.math("DIVIDE", t.math("ADD", z, 0.75), 1.5),
                     [(0.0, "#FFB36B"), (0.45, "#FF8FB1"), (0.7, "#8FC8F2"), (1.0, "#3E6FD0")])
        sun_x = _mat_node_value(t.mat, "sun_x", -0.8).outputs[0]
        dx, dz = t.math("SUBTRACT", x, sun_x), t.math("SUBTRACT", z, 0.3)
        dist = t.math("SQRT", t.math("ADD", t.math("MULTIPLY", dx, dx), t.math("MULTIPLY", dz, dz)))
        sun = t.math("LESS_THAN", dist, 0.17)
        ridge = t.math("SUBTRACT", t.math("MULTIPLY", t.math("SINE", t.math("ADD", t.math("MULTIPLY", x, 4.0), 1.0)),
                                           0.1), 0.24)
        hills = t.math("LESS_THAN", z, ridge)
        near = t.math("LESS_THAN", z, t.math("SUBTRACT", t.math("MULTIPLY", t.math("SINE", t.math("MULTIPLY", x, 2.3)),
                                                                0.07), 0.5))
        col = st._mix_color(t, sun, sky, toy.srgb("#FFE45C") + (1,))
        col = st._mix_color(t, hills, col, toy.srgb("#3FA34D") + (1,))
        col = st._mix_color(t, near, col, toy.srgb("#2E7D32") + (1,))
        t.finish((0.02, 0.02, 0.02, 1.0), 0.9)
        t.nt.links.new(col, t.bsdf.inputs["Emission Color"])
        toy._set(t.bsdf, "Emission Strength", 0.0)
        return t.mat

    def _people(self):
        self.max = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
        self.max.place(1, YARD_MAX, 0)
        self.max.key("hips", 1, loc=(0, 0, 0.56))         # anchor: later jumps must not leak backwards
        self.max.auto_blink(1, self.total + 400, seed=11)
        self.kids = [Character("Kid1", {"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5",
                                        "hair": "#5B3A1E", "scale": 0.6, "ponytail": True}),
                     Character("Kid2", {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B",
                                        "hair": "#2B1A10", "scale": 0.56})]
        self.lanterns, self.lantern_mats, self.lantern_lights = [], [], []
        for k, kid in enumerate(self.kids):
            kid.place(1, KID_SPOTS[k], 0)
            kid.key("hips", 1, loc=(0, 0, 0.56))
            kid.auto_blink(1, self.total + 400, seed=k + 3)
            ln = st.lantern(f"{kid.name}_lantern")
            kid.hold(ln, "R")
            ln.location = (-0.12, -0.03, -0.52)
            ln.scale = (1.6, 1.6, 1.6)
            self.lanterns.append(ln)
            self.lantern_mats.append(bpy.data.materials[ln["glow"]])
            ld = bpy.data.lights.new(f"{kid.name}_lantern_light", "POINT")
            ld.energy, ld.color, ld.shadow_soft_size = 0.0, (1.0, 0.72, 0.38), 0.08
            lo = bpy.data.objects.new(f"{kid.name}_lantern_light", ld)
            self.scene.collection.objects.link(lo)
            lo.parent = ln
            lo.location = (0, 0, 0.12)
            self.lantern_lights.append(ld)
        for m in self.lantern_mats + [b for ln in self.parked for b in [bpy.data.materials[ln["glow"]]]]:
            st.key_glow(m, 1, 0.0)
        self.kids_on(1, True)              # first visibility key = visible (a later hide must not hold backwards)

    # ------------------- driver -------------------

    def run(self, beats, spans, epilogue_offset):
        self.EPI = epilogue_offset
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
        hb, he = self.spans[0]
        getattr(self, f"a_{self.acts[0]}")(0, hb + epilogue_offset, he + epilogue_offset)
        for fl in self.flows:
            fl.build(self.total + 400)
        self.rig.build()

    # ------------------- helpers: light, power, water -------------------

    def _key_light(self, f, preset):
        sun_e, color, bg_v, fill_e, elev = preset
        if self.sky is not None:
            self.sky.sun_elevation = R(elev)
            self.sky.keyframe_insert("sun_elevation", frame=f)
        self.sun.data.energy, self.sun.data.color = sun_e, color
        self.sun.data.keyframe_insert("energy", frame=f)
        self.sun.data.keyframe_insert("color", frame=f)
        self.fill.data.energy = fill_e
        self.fill.data.keyframe_insert("energy", frame=f)
        self.bg.default_value = bg_v
        self.bg.keyframe_insert("default_value", frame=f)

    def light(self, f, name, ramp=1):
        """Hold the current light until f - ramp, then change to the preset by frame f (ramp=1: a cut)."""
        self._key_light(f - ramp, self._light_state)
        self._light_state = LIGHTS[name]
        self._key_light(f, self._light_state)

    def yard(self, f, energy):
        d = self.yard_light.data
        d.energy = energy
        d.keyframe_insert("energy", frame=f)

    def bulb(self, f, s, constant=False):
        st.key_glow(self.bulb_mat, f, s, constant=constant)
        d = self.bulb_light.data
        d.energy = 18.0 * s
        d.keyframe_insert("energy", frame=f)
        if constant:
            toy.set_interpolation(d, "energy", (f,), "CONSTANT")

    def flicker(self, f0, f1, lo, hi, seed, period=3):
        rnd = random.Random(seed)
        for f in range(f0, f1, period):
            self.bulb(f, rnd.choice((lo, hi, rnd.uniform(lo, hi))), constant=True)

    def lanterns_glow(self, f, on, ramp=8):
        if on == self._lan_on:
            return
        self._lan_on = on
        for m, ld in zip(self.lantern_mats, self.lantern_lights):
            st.key_glow(m, f, 0.0 if on else LANTERN_GLOW)
            st.key_glow(m, f + ramp, LANTERN_GLOW if on else 0.0)
            for ff, v in ((f, 0.0 if on else LANTERN_LIGHT), (f + ramp, LANTERN_LIGHT if on else 0.0)):
                ld.energy = v
                ld.keyframe_insert("energy", frame=ff)

    def dry(self, f, is_dry=True):
        """The summit basin is empty from f (water gone, wet floor + puddle) or full of water again."""
        for o in (self.up.vol, self.up.surf):
            toy.hide_tree(o, f, is_dry)
        for o in (self.puddle, self.wet):
            toy.hide_tree(o, f, not is_dry)

    def conduits_empty(self, f, empty=True):
        """Hide (or show) the water inside the tunnel and tailrace (an empty battery has dry pipes)."""
        for root in (self.tunnel, self.tailrace):
            toy.hide_tree(bpy.data.objects[root["water"]], f, empty)

    def level(self, which, f, lv, hold_from=None):
        """Key a reservoir level at f (hold_from: keep the previous level until that frame)."""
        res = self.up if which == "up" else self.low
        if hold_from is not None:
            res.key_level(hold_from, self._lvl[which])
        res.key_level(f, lv)
        self._lvl[which] = lv

    def label(self, text, loc, f0, f1, size=0.35, tilt=-5, color="#FF7A1A", outline="#3A0A00"):
        """A callout that is full size for its whole window (readable in every sampled frame)."""
        root = st.label(text, loc, f0, f1, size=size, tilt=tilt, color=color, outline=outline)
        for f in (f0, f0 + 5, f0 + 8, f1 - 5, f1):
            root.scale = (1, 1, 1)
            root.keyframe_insert("scale", frame=f)
        return root

    def show(self, obj, f, visible=True):
        toy.hide_tree(obj, f, not visible)

    def kids_on(self, f, visible=True):
        """The kids (and their lanterns) are on stage only in their own shots."""
        for kid in self.kids:
            toy.hide_tree(kid.root, f, not visible)

    def pop_in(self, root, f, frames=10, drop=0.0):
        """Visible from f, growing from nothing (and dropping `drop` metres into place)."""
        self.show(root, f)
        base = V(root.location)
        root.scale = (0.01, 0.01, 0.01)
        root.location = base + V((0, 0, drop))
        root.keyframe_insert("scale", frame=f)
        root.keyframe_insert("location", frame=f)
        root.scale = (1, 1, 1)
        root.location = base
        root.keyframe_insert("scale", frame=f + frames)
        root.keyframe_insert("location", frame=f + frames)
        events.add(f, "pop", gain=0.35)

    def arrows_tunnel(self, tag, f0, f1, down=True, fracs=(0.14, 0.38, 0.62, 0.84), dx=1.05, length=1.8):
        for k, t in enumerate(fracs):
            p, tan = self._tun_at(t)
            d = tan if down else -tan
            base = p + V((dx, -0.9, 0)) - d * length / 2
            st.arrow(f"{tag}{k}", base, d * length, f0 + 3 * k, f1, color=BLUE, width=0.17)

    def arrows_face(self, tag, f0, f1, down=True):
        for k, z in enumerate((0.3, -1.9, -4.1)):
            d = V((0, 0, -1.5 if down else 1.5))
            st.arrow(f"{tag}{k}", V((5.0, -0.9, z)) - d / 2, d, f0 + 3 * k, f1, color=YELLOW, width=0.16)

    def arrows_line(self, tag, f0, f1, to_house=True):
        nodes = self.line_nodes if to_house else [SOLAR_PT] + self.line_nodes[-2:0:-1] + [self.line_nodes[0]]
        for k, (a, b) in enumerate(zip(nodes, nodes[1:])):
            d = (b - a).normalized()
            L = min(1.5, (b - a).length * 0.5)
            mid = (a + b) / 2 - V((0, 0, 0.75))
            st.arrow(f"{tag}{k}", mid - d * L / 2, d * L, f0 + 4 * k, f1, color=YELLOW, width=0.14)

    def head_dim(self, tag, x, f0, f1, keys, top_lead=None, low_lead=None):
        """A yellow HEAD dimension at x: keys = [(frame, z_top, z_low)]; visible f0..f1. top_lead / low_lead:
        x where a thin leader line from the top / bottom tick ends (to the water surfaces it measures)."""
        mat = _mat("headdim_yellow", YELLOW, 0.4)
        toy._set(mat.node_tree.nodes.get("Principled BSDF"), "Emission Color", (*toy.srgb(YELLOW), 1))
        toy._set(mat.node_tree.nodes.get("Principled BSDF"), "Emission Strength", 1.4)
        y = -0.95
        bar = toy.cylinder(f"{tag}_bar", 0.05, 1.0, (0, 0, 0), mat=mat, vertices=12)
        for v in bar.data.vertices:
            v.co.z += 0.5
        top = toy.empty(f"{tag}_top", (x, y, 0))
        low = toy.empty(f"{tag}_low", (x, y, 0))
        _cone(f"{tag}_cone_top", 0.17, 0.4, (0, 0, -0.2), mat, parent=top)
        _cone(f"{tag}_cone_low", 0.17, 0.4, (0, 0, 0.2), mat, parent=low, rot=(R(180), 0, 0))
        toy.box(f"{tag}_tick_top", (1.3, 0.06, 0.06), (0, 0, 0), mat=mat, bevel=0, parent=top)
        toy.box(f"{tag}_tick_low", (1.3, 0.06, 0.06), (0, 0, 0), mat=mat, bevel=0, parent=low)
        for end, lead in ((top, top_lead), (low, low_lead)):
            if lead is not None:
                d = lead - x
                toy.box(f"{end.name}_lead", (abs(d), 0.035, 0.035), (d / 2, 0, 0.012), mat=mat, bevel=0, parent=end)
        for f, zt, zl in keys:
            bar.location = (x, y, zl + 0.2)
            bar.scale = (1, 1, max(0.05, zt - zl - 0.4))
            bar.keyframe_insert("location", frame=f)
            bar.keyframe_insert("scale", frame=f)
            top.location = (x, y, zt)
            low.location = (x, y, zl)
            top.keyframe_insert("location", frame=f)
            low.keyframe_insert("location", frame=f)
        st.no_shadow(bar, top, low)
        for o in (bar, top, low):
            toy.hide_tree(o, 0, True)
            toy.hide_tree(o, f0, False)
            toy.hide_tree(o, f1, True)

    def tank_level_world(self, f):
        return toy.value_at(self.tank, "location", f)[2] + toy.value_at(self.up.surf, "location", f)[2]

    # ------------------- helpers: people and camera -------------------

    def at(self, f, spot, face=0.0):
        self.max.cut_place(f, spot, face)
        self.max.pose(f + 6)

    def close(self, f0, f1, who=None, frac=0.4, angle=-90.0, swing=16.0, offset=(0, 0, 0), lens=32.0, rise=0.25,
              look=0.62):
        who = who or self.max
        st.close_on(self.rig, f0, f1, who, frac=frac, angle=angle, swing=swing, rise=rise, lens=lens, look=look,
                    offset=offset, cut=True, fstop=5.6, height=1.9 if who is self.max else 1.12)

    def wide(self, f0, f1, cam0, cam1, aim0, aim1=None, lens=24.0):
        self.rig.shot(f0, f1, cam_from=cam0, cam_to=cam1, aim_from=aim0, aim_to=aim1 or aim0, lens=lens, fstop=8.0,
                      cut=True)

    def kids_shot(self, f0, f1, mood):
        k1, k2 = self.kids
        for kid in self.kids:
            kid.pose(f0)
        if mood == "sigh":
            k1.pose(f0 + 10, head=(22, 0, 8), spine=(8, 0, 0))
            k1.pose(f1 - 4, head=(26, 0, -6), spine=(10, 0, 0))
            k2.key("mouth", f0 + 14, scale=(1.0, 0.6, 2.6))
            k2.pose(f0 + 14, head=(-18, 0, 0))
            k2.key("mouth", f1 - 6, scale=(0.7, 0.6, 1.0))
            k2.pose(f1 - 6)
        elif mood == "peer":
            k2.hop(f0 + 6, f1 - 6, height=0.1, period=14, sound="step")
            k1.point(f0 + 8, f1 - 4, hand="L", up_deg=60, side_deg=10)
            k1.brows(f0 + 8, 0.8)
        elif mood == "yawn":
            k1.key("mouth", f0 + 8, scale=(1.0, 0.6, 2.8))
            k1.pose(f0 + 8, head=(-20, 0, 0), shoulderL=(-20, -150, 0))
            k1.key("mouth", f1 - 8, scale=(0.7, 0.6, 1.0))
            k1.pose(f1 - 8)
            k2.pose(f0 + 12, head=(28, 0, 10), spine=(10, 0, 0))
        else:                                                # "cover": shaking ground far away, hands on ears
            for kid in self.kids:
                kid.pose(f0 + 8, shoulderL=(0, -130, 0), head=(6, 0, 0))
                kid.pose(f1 - 4, shoulderL=(0, -135, 0), head=(4, 0, 0))
                kid.brows(f0 + 8, 1.0)
        for kid in self.kids:
            kid.pose(f1)
            kid.brows(f1, 0.0)
        self.close(f0, f1, k1, frac=0.34, offset=(0.35, 0, 0), swing=12)

    def cheer(self, who, f0, f1):
        who.key("hips", f0, loc=(0, 0, 0.56))           # jumps start from the ground, never before
        who.cheer(f0, f1)

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

    def thumbs_up(self, f0, f1):
        """Arm punched up and out to the side (reads from the front; a forward arm is foreshortened)."""
        self.max.pose(f0, shoulderL=(-30, -128, 0), head=(-6, 0, 0))
        self.max.pose(f1 - 4, shoulderL=(-32, -134, 0), head=(-8, 0, 0))
        self.max.smile(f0, big=True)
        self.max.pose(f1)

    def shiver(self, f0, f1):
        """Max on a shaking floor: clutching his hard hat, bouncing on the spot."""
        m = self.max
        f, k = f0, 0
        while f < f1 - 3:
            m.pose(f, shoulderL=(-20, -158 + 6 * (k % 2), 0), shoulderR=(-20, 158 - 6 * (k % 2), 0),
                   spine=(6, 0, 4 if k % 2 else -4), head=(4, 0, -5 if k % 2 else 5))
            m.key("hips", f, loc=(0, 0, 0.56 if k % 2 else 0.53))
            f += 3
            k += 1
        m.key("hips", f1, loc=(0, 0, 0.56))
        m.pose(f1)
        m.brows(f0, 1.0)
        m.brows(f1, 0.0)
        m.key("mouth", f0 + 2, scale=(1.1, 0.6, 2.4))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))

    # ------------------- the ladder -------------------

    def a_setup(self, i, b, e):
        L = e - b
        m = b + int(L * 0.32)
        self.light(b, "afternoon")
        self.at(b, YARD_MAX, 0)
        for kid in self.kids:
            kid.hop(b + 8, m + 30, height=0.12, period=16, sound="step")
            kid.smile(b + 8, big=True)
        self.max.point(m + 2, b + int(L * 0.6), hand="R", up_deg=35, side_deg=70)      # the panels (screen left)
        self.max.smile(m + 2, big=True)
        self.max.point(b + int(L * 0.62), e - 4, hand="R", up_deg=95, side_deg=40)    # up to the mountain
        self.max.brows(b + int(L * 0.62), 0.8)
        events.add(b + 10, "kids_cheer", gain=0.35)
        st.orbit(self.rig, b, m, center=(9.4, 7.5, 2.0), radius=15.5, ang0=-106, ang1=-86, z0=5.0, z1=3.8, lens=24,
                 cut=True)
        self.close(m, e, frac=0.3, offset=(0.75, 0, -0.1), angle=-92)

    def a_fail_flat(self, i, b, e):
        L = e - b
        m1, m2 = b + int(L * 0.45), b + int(L * 0.76)
        self.light(b, "afternoon")
        self.light(m2, "dusk")
        self.show(self.tank, b)
        self.dry(b, False)                       # showing the tank showed its puddle too: full of water
        self.show(self.conn, b)
        Puffs("pond_puff", "#C9B79A", count=8, size=0.35, seed=4).emit(range(b + 1, b + 9), lambda f: (7.1, -0.4, 0.3),
                                                                        rise=0.6)
        self.at(b, VAL, 0)
        self.max.point(b + 8, b + 24, hand="L", up_deg=25, side_deg=30)       # flips the switch
        events.add(b + 16, "switch")
        self.f_conn.speed(b + 16, 0.0)
        self.f_conn.speed(b + 40, 0.22)
        self.f_conn.on(b + 16, 0.0)
        self.f_conn.on(b + 30, 0.7)
        self.f_conn.speed(e, 0.22)
        self.level("up", e, TANK_FULL - 0.04, hold_from=b + 16)
        self.turb0.spin(b + 26, e, rps=0.1)
        self.bulb(b + 18, 0.0)
        self.bulb(b + 34, 0.8)                   # a faint, sad glow
        self.bulb(e, 0.6)
        events.add(b + 18, "pour", duration=L - 20, gain=0.2)
        self.max.point(b + 40, b + int(L * 0.3), hand="L", up_deg=80, side_deg=30)   # taps the dim bulb
        self.scratch_head(b + int(L * 0.3), m1 + 10)
        self.label("TINY HEAD", (6.0, -0.9, 1.35), m1 + 4, m2, size=0.7, tilt=-4)
        st.arrow("flat_flow", (3.4, -0.75, -0.42), (-0.6, 0, 0), m1 + 6, m2, color=BLUE, width=0.09)
        self.lanterns_glow(m2, True, ramp=6)
        self.kids_on(b, False)
        self.kids_on(m2, True)
        self.close(b, m1, frac=0.35, offset=(0.2, 0, 0))
        self.wide(m1, m2, (5.1, -12.6, -2.4), (4.9, -12.2, -2.8), (4.8, 0.5, -4.2), (4.8, 0.5, -4.5), lens=21)
        self.kids_shot(m2, e, "sigh")

    def a_raise_head(self, i, b, e):
        L = e - b
        lift0, land, m = b + int(L * 0.06), b + int(L * 0.36), b + int(L * 0.55)
        self.light(b, "day")
        self.lanterns_glow(b, False, ramp=1)
        self.bulb(b, 0.0, constant=True)
        self.show(self.conn, b, False)
        self.kids_on(b, False)
        self.f_conn.speed(b, 0.0)
        self.f_conn.on(b, 0.0)
        # the whole reservoir lifts out of its pit and flies up onto the summit
        path = ((0.0, TANK_LOW), (0.14, V((7.1, 0, 1.2))), (0.38, V((4.8, 0, 7.2))), (0.62, V((1.0, 0, 13.6))),
                (0.82, V((-2.6, 0, 14.8))), (0.94, V((-4.25, 0, 13.0))), (1.0, TANK_HIGH))
        ride = V((TANK_HW - TANK_T / 2, 1.9, TANK_TOP + 0.066))       # Max rides up on the wall crest
        self.at(b, TANK_LOW + ride, 0)
        toy.key_hold(self.tank, "location", lift0 - 1)
        toy.key_hold(self.max.root, "location", lift0 - 1)
        for t, p in path:
            f = lift0 + int((land - lift0) * t)
            self.tank.location = p
            self.tank.keyframe_insert("location", frame=f)
            self.max.root.location = p + ride
            self.max.root.keyframe_insert("location", frame=f)
        flight = [lift0 + int((land - lift0) * t) for t, _ in path]
        for ob in (self.tank, self.max.root):              # final curve BEFORE the camera samples it (the film
            toy.set_interpolation(ob, "location", flight, "BEZIER")   # runner normalizes inherited holds later)
        self.max.wave(lift0 + 6, land - 4, hand="R")
        self.max.smile(lift0 + 6, big=True)
        events.add(lift0, "rumble", duration=land - lift0, gain=0.7)
        events.add(lift0, "creak", gain=0.5)
        events.add(land, "stone_thud", gain=0.8)
        Puffs("land_puff", "#C9B79A", count=10, size=0.4, seed=6).emit(
            range(land, land + 10), lambda f: (-4.25 + (f % 3 - 1) * 1.6, -0.3, 12.2), rise=0.7, life=20)
        # pressure arrows along the rock face grow as it climbs; a HEAD dimension follows the water
        for k, (x, z) in enumerate(((-0.9, 9.4), (-0.1, 6.3), (0.7, 3.2), (1.5, 0.1))):
            g = toy.empty(f"press_grow{k}", (x, -0.85, z))
            st.arrow(f"press_arrow{k}", (0, 0, 0), V((0.5, 0, -2.2)), lift0 + 6 + 2 * k, m, color=BLUE, width=0.17,
                     parent=g)
            for f, sc in ((lift0 + 6, 0.25), (land, 1.0)):
                g.scale = (sc, sc, sc)
                g.keyframe_insert("scale", frame=f)
        keys = [(f, self.tank_level_world(f), LOW_LEVEL) for f in range(lift0, land + 1, 4)] + [(m, TANK_HIGH.z + TANK_FULL,
                                                                                               LOW_LEVEL)]
        self.head_dim("headdim_rise", 9.0, land - 2, m, keys, top_lead=-2.2, low_lead=10.8)
        self.label("HEAD 150 m", (6.0, -1.0, 7.0), land - 4, m, size=1.0, tilt=-4, color=YELLOW, outline="#3A2A00")
        self.thumbs_up(m + 6, b + int(L * 0.8))
        self.max.point(b + int(L * 0.8), e - 2, hand="L", up_deg=20, side_deg=40)    # down to the valley
        # ride along with Max (close, he waves) ... then the whole drop he just created, measured
        self.close(b, land, frac=0.21, swing=22, offset=(0.4, 0, -0.9), lens=28)
        self.wide(land, m, (2.6, -29.0, 6.9), (2.4, -28.0, 6.6), (2.6, 0.5, 6.4), (2.5, 0.5, 6.3))
        self.close(m, e, frac=0.36, offset=(-0.5, 0, 0))

    def a_fail_pipe(self, i, b, e):
        L = e - b
        m1, m2 = b + int(L * 0.33), b + int(L * 0.78)
        self.light(b, "day")
        self.light(m2, "dusk")
        self.show(self.narrow, b)
        self.f_narrow.speed(b + 6, 0.0)
        self.f_narrow.speed(b + 20, 0.35)
        self.f_narrow.speed(e, 0.3)
        rnd = random.Random(5)
        for f in range(b + 8, e, 6):                                   # sputtering
            self.f_narrow.on(f, rnd.choice((1.0, 0.15, 0.6)))
        self.level("up", e, TANK_FULL - 0.06, hold_from=b + 8)
        f, k = b + 12, 0
        while f < e - 9:                                               # the turbine jerks
            self.turb0.spin(f, f + 9, rps=0.55 if k % 2 else 0.06)
            f += 9
            k += 1
        self.flicker(b + 14, e, 0.0, 1.8, seed=8)
        events.add(b + 10, "pour", duration=L - 12, gain=0.3)
        events.add(b + 20, "creak", gain=0.4)
        for k, j in enumerate((1, 3, 5)):                              # friction pushes back at the bends
            p, prev = self.zig[j], self.zig[j - 1]
            d = (prev - p).normalized() * 1.6
            st.arrow(f"friction{k}", p + V((0, -0.7, 0)) - d * 0.25, d, b + 3 + 3 * k, m1, color=RED, width=0.24)
        self.label("FRICTION", (1.6, -1.0, 3.2), b + 6, m1, size=0.7, tilt=-5, color=RED, outline="#3A0505")
        self.at(b, VAL, 0)
        self.max.point(m1 + 6, m1 + 40, hand="L", up_deg=80, side_deg=30)
        self.max.brows(m1 + 10, -0.5)
        self.facepalm(m1 + 44, m2)
        self.lanterns_glow(m2, True, ramp=6)
        self.kids_on(m2, True)
        self.wide(b, m1, (-0.6, -11.5, 12.5), (-0.4, -12.5, 1.0), (-0.8, 0.5, 9.0), (-0.6, 0.5, -2.4))
        self.close(m1, m2, frac=0.38, offset=(0.3, 0, 0))
        self.kids_shot(m2, e, "peer")

    def a_tunnel(self, i, b, e):
        L = e - b
        bore0, bore1, m = b + int(L * 0.03), b + int(L * 0.32), b + int(L * 0.62)
        flood = bore1 + 4
        self.light(b, "day")
        self.lanterns_glow(b, False, ramp=1)
        self.bulb(b, 0.0, constant=True)
        self.show(self.narrow, b, False)
        self.kids_on(b, False)
        self.f_narrow.speed(b, 0.0)
        self.f_narrow.on(b, 0.0)
        # the boring machine eats the rock plug from the summit intake down to the powerhouse
        t0 = self.plugs[0][1] - 0.02
        t1 = min(1.0, self.plugs[-1][1] + 0.03)

        def bore_t(f):
            return t0 + (t1 - t0) * max(0.0, min(1.0, (f - bore0) / max(1, bore1 - bore0)))
        self.show(self.tbm, bore0)
        self.show(self.tbm, bore1 + 2, False)
        for f in range(bore0, bore1 + 3, 2):
            p, tan = self._tun_at(bore_t(f))
            self.tbm.location = p
            self.tbm.rotation_euler = tan.to_track_quat("Z", "Y").to_euler()
            self.tbm.keyframe_insert("location", frame=f)
            self.tbm.keyframe_insert("rotation_euler", frame=f)
        for ob, t in self.plugs:
            f = bore0 + int((bore1 - bore0) * max(0.0, min(1.0, (t - t0) / (t1 - t0))))
            self.show(ob, max(bore0 + 1, f), False)
        Puffs("tbm_puff", "#B8A88E", count=16, size=0.35, seed=9).emit(
            range(bore0 + 2, bore1, 3), lambda f: self._tun_at(bore_t(f))[0] + V((0, -0.7, 0)), rise=0.5, life=16,
            drift=0.4)
        events.add(bore0, "engine_rev", duration=bore1 - bore0, gain=0.6)
        events.add(bore0, "rumble", duration=bore1 - bore0, gain=0.6)
        # it floods: fast water down the tunnel, the turbine spins hard, the bulb blazes
        self.show(self.tunnel, bore1)
        self.f_tun.on(bore1, 0.0)
        self.f_tun.on(flood + 10, 1.0)
        self.f_tun.speed(flood, 0.0)
        self.f_tun.speed(flood + 16, 1.4)
        self.f_tail.on(flood + 10, 0.0)
        self.f_tail.on(flood + 18, 1.0)
        self.f_tail.speed(flood + 8, 0.0)
        self.f_tail.speed(flood + 22, 1.0)
        self.turb0.spin(flood + 10, flood + 30, rps=0.6)
        self.turb0.spin(flood + 30, e, rps=1.5)
        self.bulb(flood + 14, 0.0)
        self.bulb(flood + 22, 6.0)
        self.level("up", e, TANK_FULL - 0.3, hold_from=flood)
        self.level("low", e, LOW_LEVEL + 0.04, hold_from=flood)
        events.add(flood, "water_rush", duration=e - flood, gain=0.7)
        events.add(flood + 22, "power_up", gain=0.6)
        self.arrows_tunnel("tun_down", flood + 6, m)
        self.label("7 m TUNNEL", (-0.4, -1.0, -2.6), flood + 4, m, size=0.62, tilt=-4, color=BLUE, outline="#06263A")
        self.at(b, VAL, 0)
        self.cheer(self.max, m + 8, e - 4)
        self.max.smile(m + 4, big=True)
        keys = []
        for f in list(range(b, m, 3)) + [m]:
            z = max(-4.6, min(10.5, self._tun_at(bore_t(f))[0].z))
            drift = 0.02 * (f - b)
            aim = V((-1.0, 0.5, z))
            keys.append((f, aim + V((0.6 + drift * 0.3, -12.0 + drift, 1.2)), aim))
        self.rig.track(b, m, keys, lens=24, fstop=8.0, cut=True)
        self.close(m, e, frac=0.38, offset=(0.3, 0, 0))

    def a_fail_empty(self, i, b, e):
        L = e - b
        m1, m2 = b + int(L * 0.4), b + int(L * 0.82)
        dry, stop = b + int(L * 0.37), b + int(L * 0.5)
        self.light(b, "day")
        self.light(b + int(L * 0.34), "dusk", ramp=24)
        self.light(m2, "night")
        self.f_tun.speed(dry - 10, 1.4)
        self.f_tun.speed(stop, 0.0)
        self.f_tun.on(stop - 6, 1.0)
        self.f_tun.on(stop, 0.25)
        self.f_tail.speed(dry - 6, 1.0)
        self.f_tail.speed(stop + 4, 0.0)
        self.f_tail.on(stop + 4, 0.25)
        self.level("up", dry, TANK_DRY, hold_from=b)
        self.level("low", dry, LOW_LEVEL + 0.2, hold_from=b)
        self.dry(dry + 2)                                    # the last water is gone: wet floor, one puddle
        self.conduits_empty(stop + 4)
        self.turb0.spin(b, dry, rps=1.5)
        self.turb0.spin(dry, stop, rps=0.45)
        self.bulb(dry - 2, 6.0)
        self.flicker(dry, stop, 0.0, 2.5, seed=13)
        self.bulb(stop, 0.0, constant=True)
        events.add(b, "water_rush", duration=dry - b, gain=0.5)
        events.add(dry, "bubbles", gain=0.6)
        self.arrows_tunnel("empty_down", b + 4, m1)
        self.at(b, TOP, 90)
        self.max.pose(m1 + 2, spine=(14, 0, 0), head=(24, 0, 0))          # peers over the rim into the basin
        self.max.pose(m1 + 22, spine=(16, 0, 0), head=(26, 0, 0))
        self.max.turn(m1 + 24, 0, frames=8)
        self.jaw_drop(m1 + 30, m2)
        events.add(m1 + 32, "boing", gain=0.3)
        self.lanterns_glow(m2, True, ramp=6)
        self.kids_on(m2, True)
        self.wide(b, m1, (1.2, -17.0, 6.5), (0.8, -15.5, 6.0), (-0.5, 0.5, 5.5), (-1.0, 0.5, 5.0))
        self.close(m1, m2, frac=0.34, offset=(0.8, 0, 0), angle=-88)
        self.kids_shot(m2, e, "yawn")

    def a_pump_turbines(self, i, b, e):
        L = e - b
        out, in_a, in_b = b + int(L * 0.05), b + int(L * 0.13), b + int(L * 0.21)
        pump0, m = b + int(L * 0.4), b + int(L * 0.54)
        self.light(b, "day")
        self.lanterns_glow(b, False, ramp=1)
        self.level("up", b, TANK_DRY)
        self.level("low", b, LOW_LEVEL + 0.2)
        self.kids_on(b, False)
        # the old one-way turbine is hoisted out, two reversible pump-turbines drop in
        r0 = self.turb0.root
        toy.key_hold(r0, "location", out)
        r0.keyframe_insert("scale", frame=out)
        r0.location = V(r0.location) + V((0, 0, 2.2))
        r0.scale = (0.01, 0.01, 0.01)
        r0.keyframe_insert("location", frame=out + 10)
        r0.keyframe_insert("scale", frame=out + 10)
        r0.location = V(r0.location) - V((0, 0, 2.2))
        r0.scale = (1, 1, 1)
        self.show(r0, out + 11, False)
        events.add(out, "steel_clank", gain=0.6)
        self.pop_in(self.unitA.root, in_a, frames=12, drop=1.6)
        self.pop_in(self.unitB.root, in_b, frames=12, drop=1.6)
        self.show(self.feedB, in_b + 6)
        events.add(in_a + 12, "steel_clank", gain=0.8)
        events.add(in_b + 12, "steel_clank", gain=0.8)
        self.label("PUMP-TURBINES", (SHAFT_X, 0.2, -4.5), in_b + 8, m, size=0.24, tilt=-3)
        self.label("2 x 125 MW", (SHAFT_X, 0.2, -4.98), in_b + 14, m, size=0.22, tilt=3, color=YELLOW, outline="#3A2A00")
        # spare solar power runs them BACKWARDS: the same water is pumped uphill
        self.unitA.spin(pump0, e, rps=-1.25)
        self.unitB.spin(pump0 + 4, e, rps=-1.25)
        self.f_tun.speed(pump0, 0.0)
        self.f_tun.speed(pump0 + 20, -1.2)
        self.f_tun.on(pump0, 0.25)
        self.f_tun.on(pump0 + 14, 1.0)
        self.f_tail.speed(pump0, 0.0)
        self.f_tail.speed(pump0 + 20, -0.9)
        self.f_tail.on(pump0, 0.25)
        self.f_tail.on(pump0 + 14, 1.0)
        self.level("up", e, TANK_FULL, hold_from=pump0 + 10)
        self.level("low", e, LOW_LEVEL, hold_from=pump0 + 10)
        self.conduits_empty(pump0, False)                    # pumped water fills the tunnel again...
        self.dry(pump0 + 10, False)                          # ...and the summit basin
        events.add(pump0, "power_up", gain=0.6)
        events.add(pump0 + 6, "pump", duration=e - pump0 - 6, gain=0.6)
        self.arrows_face("solar_in", pump0 + 2, e)
        self.arrows_tunnel("pump_up", pump0 + 12, e, down=False)
        self.at(b, PH, 0)
        self.max.point(in_a + 4, in_a + 34, hand="R", up_deg=40, side_deg=40)
        self.max.point(in_b + 14, pump0, hand="L", up_deg=40, side_deg=40)
        self.cheer(self.max, pump0 + 4, m - 2)
        self.close(b, m, frac=0.27, offset=(0, 0, 0.5), lens=28)
        self.wide(m, e, (1.0, -12.5, -3.5), (0.2, -17.5, 5.5), (0.8, 0.5, -5.0), (-1.2, 0.5, 5.0))

    def a_fail_shudder(self, i, b, e):
        L = e - b
        m1, m2 = b + int(L * 0.45), b + int(L * 0.8)
        shake0 = b + int(L * 0.3)
        self.light(b, "dusk")
        self.lanterns_glow(b, True, ramp=1)
        self.unitA.spin(b, e, rps=1.25)                       # fixed speed: locked to the grid
        self.unitB.spin(b, e, rps=1.25)
        self.f_tun.speed(b, 0.0)
        self.f_tun.speed(b + 12, 1.3)
        self.f_tail.speed(b, 0.0)
        self.f_tail.speed(b + 12, 0.9)
        self.level("up", m1, 0.78, hold_from=b + 2)
        self.level("up", e, 0.66)
        self.level("low", m1, LOW_LEVEL + 0.15, hold_from=b + 2)
        self.level("low", e, LOW_LEVEL + 0.18)
        keys = [(f, TANK_HIGH.z + TANK_FULL + (0.78 - TANK_FULL) * st.smooth((f - b - 2) / max(1, m1 - b - 2)),
                 LOW_LEVEL + 0.15 * st.smooth((f - b - 2) / max(1, m1 - b - 2))) for f in range(b, m1 + 1, 4)]
        self.head_dim("headdim_shudder", 0.4, b + 2, m1, keys, top_lead=-2.2, low_lead=4.0)
        mid = b + int(L * 0.22)
        self.label("HEAD 175 m", (2.5, -1.0, 9.0), b + 3, mid, size=0.85, tilt=-4, color=YELLOW, outline="#3A2A00")
        self.label("HEAD 125 m", (2.5, -1.0, 9.0), mid + 1, m1, size=0.85, tilt=4, color=YELLOW, outline="#3A2A00")
        self.unitA.shudder(shake0, e, amp=0.035)
        self.unitB.shudder(shake0 + 4, e, amp=0.035)
        rnd = random.Random(21)
        Puffs("ph_puff", "#9C9284", count=14, size=0.22, seed=21).emit(
            range(m1, m2, 4), lambda f: (rnd.uniform(-0.8, 3.2), rnd.uniform(0.6, 2.2), -2.2), rise=-1.6, life=22,
            drift=0.3)
        for f in range(m1, m2, 4):
            st.key_glow(self.ph_lamp_mat, f, rnd.choice((0.6, 3.0, 1.5)), constant=True)
        st.key_glow(self.ph_lamp_mat, m2, 3.0, constant=True)
        events.add(shake0, "rumble", duration=e - shake0, gain=0.8)
        events.add(m1 + 6, "alarm", duration=m2 - m1 - 6, gain=0.45)
        for f in range(m1 + 4, m2, 18):
            events.add(f, "steel_clank", gain=0.4)
        self.label("FIXED SPEED", (SHAFT_X, 0.2, -4.5), m1 + 8, m2, size=0.24, tilt=-3, color=RED, outline="#3A0505")
        self.at(b, PH, 0)
        self.shiver(m1, m2 - 2)
        self.kids_on(m2, True)
        self.wide(b, m1, (-0.3, -17.5, 5.6), (-0.6, -16.6, 5.3), (-0.5, 0.5, 5.0), (-0.7, 0.5, 4.8))
        self.close(m1, m2, frac=0.27, offset=(0, 0, 0.5), lens=28)
        self.kids_shot(m2, e, "cover")

    def a_variable_speed(self, i, b, e):
        L = e - b
        c0, m = b + int(L * 0.06), b + int(L * 0.5)
        self.light(b, "dusk")
        self.lanterns_glow(b, False, ramp=1)
        self.kids_on(b, False)
        for k, (t0, t1, rps) in enumerate(((0.0, 0.25, 1.35), (0.25, 0.5, 1.3), (0.5, 0.75, 1.24), (0.75, 1.0, 1.18))):
            f0, f1 = b + int(L * t0), b + int(L * t1)
            self.unitA.spin(f0, f1, rps=rps)
            self.unitB.spin(f0, f1, rps=rps)
        self.f_tun.speed(e, 1.2)
        self.level("up", e, 0.5, hold_from=b)
        self.level("low", e, LOW_LEVEL + 0.22, hold_from=b)
        for k, c in enumerate(self.cabinets):
            self.pop_in(c, c0 + 6 * k, frames=10)
        for k, r in enumerate(self.rings):
            self.show(r, c0 + 10 + 4 * k)
        st.key_glow(self.led, c0 + 9, 0.0)
        st.key_glow(self.led, c0 + 16, 4.0)
        self.pop_in(self.gauge, c0 + 14, frames=10)
        for f, a in ((c0 + 24, 55.0), (e - 6, -55.0)):                # 315 rpm down to 285 rpm as the head falls
            self.needle.rotation_euler = (0, R(a), 0)
            self.needle.keyframe_insert("rotation_euler", frame=f)
        events.add(c0 + 10, "power_up", gain=0.6)
        events.add(c0 + 16, "hum", duration=e - c0 - 16, gain=0.4)
        self.label("VARIABLE SPEED", (SHAFT_X, 0.2, -4.5), c0 + 18, m, size=0.24, tilt=-3, color="#3DDC6E",
                 outline="#06301A")
        self.label("285-315 rpm", (SHAFT_X, 0.2, -4.98), c0 + 24, e, size=0.24, tilt=3, color="#3DDC6E",
                 outline="#06301A")
        self.at(b, PH, 0)
        w0 = m + 4                                             # wipes his brow (hand to forehead) ...
        self.max.pose(w0, shoulderR=(-28, 150, 0), head=(10, 0, 6))
        self.max.pose(w0 + 12, shoulderR=(-28, 140, 0), head=(6, 0, -6))
        self.max.pose(w0 + 18)
        self.max.brows(w0, -0.4)
        self.max.brows(w0 + 18, 0.0)
        self.thumbs_up(w0 + 20, e - 2)                         # ... and punches the air: it works
        self.max.smile(w0 + 20, big=True)
        self.wide(b, m, (2.3, -4.7, -6.0), (1.9, -4.1, -6.2), (1.4, 1.6, -6.4), (1.3, 1.6, -6.5), lens=26)
        self.close(m, e, frac=0.3, offset=(0, 0, 0.35), lens=28)

    def movie(self, f0, f1):
        st.key_glow(self.screen_mat, f0 - 1, 0.0)
        st.key_glow(self.screen_mat, f0 + 4, 2.2)
        key_node_value(self.screen_mat, "sun_x", f0, -0.8)        # the film plays: its sun crosses the sky
        key_node_value(self.screen_mat, "sun_x", f0 + 600, 0.8)
        self.show(self.beam, f0)
        events.add(f0, "switch", gain=0.5)

    def seat_kids(self, f, f_end):
        face = facing_to((0, 0, 0), (math.sin(R(-BENCH_YAW)), math.cos(R(-BENCH_YAW)), 0))
        ax = V((math.cos(R(BENCH_YAW)), math.sin(R(BENCH_YAW)), 0))
        for k, kid in enumerate(self.kids):
            kid.cut_place(f, BENCH + ax * (-0.28 if k == 0 else 0.28), face)
            kid.pose(f)
            kid.sit(f, f_end, frames=1)
            self.show(self.lanterns[k], f, False)
        for ln in self.parked:
            self.show(ln, f)

    def a_finale(self, i, b, e):
        L = e - b
        s1, s2 = b + int(L * 0.22), b + int(L * 0.4)
        sA, cl = b + int(L * 0.3), b + int(L * 0.46)          # valley shot from sA, the close family shot from cl
        mv, m = s2 + 8, cl
        self.light(b, "day")
        self.lanterns_glow(b, False, ramp=1)
        st.key_glow(self.led, b, 4.0)
        # by day: solar power pumps the water back up
        self.unitA.spin(b, s1, rps=-1.25)
        self.unitB.spin(b, s1, rps=-1.25)
        self.f_tun.speed(b, -1.2)
        self.f_tail.speed(b, -0.9)
        self.level("up", s1, TANK_FULL, hold_from=b)
        self.level("low", s1, LOW_LEVEL, hold_from=b)
        events.add(b, "pump", duration=s1 - b, gain=0.5)
        self.arrows_face("day_solar", b + 4, s1)
        self.arrows_tunnel("day_up", b + 8, s1, down=False)
        # after sunset the flow reverses: the same water falls back through them
        self.light(s1 + 22, "dusk", ramp=22)
        self.light(s2, "night", ramp=10)
        self.f_tun.speed(s1 + 2, 0.0)
        self.f_tun.speed(s1 + 18, 1.3)
        self.f_tail.speed(s1 + 2, 0.0)
        self.f_tail.speed(s1 + 18, 0.9)
        self.unitA.spin(s1, s1 + 14, rps=0.0)
        self.unitB.spin(s1, s1 + 14, rps=0.0)
        self.unitA.spin(s1 + 14, e, rps=1.25)
        self.unitB.spin(s1 + 14, e, rps=1.25)
        self.level("up", e, 0.95, hold_from=s1 + 16)
        self.level("low", e, LOW_LEVEL + 0.12, hold_from=s1 + 16)
        events.add(s1 + 14, "water_rush", duration=e - s1 - 14, gain=0.4)
        self.arrows_tunnel("night_down", s1 + 14, s2)
        self.arrows_face("night_out", s1 + 18, s2, down=False)
        # power reaches the house: lights, projector, movie; lanterns off
        self.arrows_line("to_house", sA + 2, cl)
        self.house.lights(sA + 18, True)
        events.add(sA + 18, "power_up", gain=0.5)
        self.yard(s2 - 1, 0.0)
        self.yard(s2 + 8, 900.0)
        self.movie(mv, self.total + 400)
        self.kids_on(s2, True)
        self.seat_kids(s2, e + 2)
        self.max.cut_place(b, MOVIE_MAX, -25)                  # faces us; the kids and the screen behind him
        self.max.pose(b + 4)
        self.max.point(cl + 4, cl + int((e - cl) * 0.4), hand="L", up_deg=60, side_deg=55)   # look, the movie!
        self.cheer(self.max, cl + int((e - cl) * 0.45), e - 4)
        self.max.smile(cl + 2, big=True)
        for k, kid in enumerate(self.kids):                    # outer arms up (they sit side by side)
            joint, sgn = ("shoulderL", -1) if k == 0 else ("shoulderR", 1)
            for f, a in ((m + 30 + 6 * k, 0), (m + 40 + 6 * k, 150), (m + 70 + 6 * k, 160), (m + 82 + 6 * k, 0)):
                kid.key(joint, f, rot_deg=(0, sgn * a, 0))
            kid.smile(m + 30, big=True)
        events.add(m + 40, "kids_cheer", gain=0.7)
        self.wide(b, sA, (1.6, -18.0, 4.0), (0.6, -19.5, 5.6), (-0.2, 0.5, 3.0), (-0.6, 0.5, 4.0))
        self.wide(sA, cl, (6.4, -2.2, 4.6), (7.4, -1.0, 4.0), (10.6, 9.6, 1.6), (11.6, 10.2, 1.4))
        self.close(cl, e, frac=0.3, angle=-100, swing=14, offset=(0.9, 0, 0.25))

    # ------------------- hooks (epilogue, after the finale) -------------------

    def a_empty_hook(self, i, h0, h1):
        self.light(h0, "dusk")
        self.yard(h0, 0.0)
        self.house.lights(h0, False)
        st.key_glow(self.screen_mat, h0, 0.0, constant=True)
        self.show(self.beam, h0, False)
        self.level("up", h0, TANK_DRY, hold_from=h0 - 1)
        self.level("low", h0, LOW_LEVEL + 0.2, hold_from=h0 - 1)
        for fl in (self.f_tun, self.f_tail):
            fl.speed(h0 - 1, 0.0)
            fl.on(h0, 0.2)
        self.dry(h0)                                          # drained: wet floor and a puddle at his boots
        self.conduits_empty(h0)
        for ln in self.parked:
            self.show(ln, h0, False)
        self.kids_on(h0, True)
        for k, kid in enumerate(self.kids):
            kid.cut_place(h0, HOOK_KIDS[k], -20 if k == 0 else 10)
            kid.pose(h0)
            self.show(self.lanterns[k], h0)
        self.lanterns_glow(h0, True, ramp=1)
        self.kids[0].pose(h0 + 30, head=(10, 0, 18))
        self.kids[1].pose(h0 + 40, head=(-8, 0, -12))
        self.max.cut_place(h0, HOOK_MAX, 0)
        self.max.pose(h0)
        self.max.key("head", h0 + 10, rot_deg=(20, 0, -40))
        self.max.key("head", h0 + 40, rot_deg=(20, 0, 40))
        self.max.key("head", h0 + 64, rot_deg=(0, 0, 0))
        self.jaw_drop(h0 + 70, h1)
        events.add(h0 + 72, "boing", gain=0.3)
        events.add(h0 + 4, "bubbles", gain=0.3)
        self.close(h0, h1, frac=0.28, offset=(0.9, 0, -0.1), swing=14)

    def a_movie_hook(self, i, h0, h1):
        self.light(h0, "night")
        self.yard(h0, 450.0)
        self.kids_on(h0, True)
        self.seat_kids(h0, h1 + 2)
        self.max.cut_place(h0, MOVIE_MAX, 0)
        self.max.pose(h0)
        self.cheer(self.max, h0 + 10, h1 - 4)
        events.add(h0 + 10, "kids_cheer", gain=0.6)
        self.close(h0, h1, frac=0.34, angle=-95, swing=14, offset=(0.9, 0, 0))
