"""
LEVEE STORY set (Blender side) — a riverbank sliced open: river on the left, Max's earthen levee in the middle,
his backyard on the right, three soil layers under it all. Spec: levee_story_earthen_river_le_story_spec.py.

ASSET PLAN (real object -> real shape / recognizable detail -> pieces that build it)
- Riverbank cutaway: one vertical section face at y = 0, everything extruded 120 m back along +y. Layers as
  stacked slabs: thin brown topsoil "blanket" (0.6 m), thick pale-yellow sand (2.4 m) that runs under the levee
  and forms the riverbed, grey bedrock below -> st.prism slabs with noise soil materials, st.section_rock;
  st.world_floor laid around the block so no void shows.
- River: a channel cut into the sand, blue translucent water whose level rises and falls -> st.Reservoir.
- Rubber duck: the classic bath duck (fat body, round head, orange flat beak, black eyes) -> toy.sphere parts.
- Levee: an extruded trapezoid seen in section. v1 = a steep pure-sand wall (3.4 m base, 3 m tall);
  v2 = wide gentle levee (12.4 m base, 2.2 m tall, sand shell) with a dark-brown clay core; v3 = same footprint
  raised to 3.1 m with a clay core, a thick green grass shell (+ tufts) and grey riprap boulders on the river
  slope -> st.prism, band() shells, one baked mesh of icospheres, st.scatter_on tufts.
- Seepage berm: a wide, low wedge of soil on the land side -> st.prism. Relief wells: thin steel pipes in a row
  at its toe venting into a drainage ditch (a notch in the topsoil with water) -> toy.cylinder, prism slot.
- Sand boil: a small sand volcano with a muddy fountain and a ring of burlap sandbags -> cone, Spray, capsules.
- Overtopping: a thin waterfall sheet over the crest and land slope, a dark scour gouge growing in the
  slope -> band() prism, scaled gouge prism.
- Ground squirrel + burrow: a brown squirrel (bushy tail, ears) digging a tunnel that is CARVED once into
  copies of the levee (half-tube groove in the section face), a wider "piped" copy with water in it, and a jet
  out of the land side -> st.carve + st.tube_cutter, curve tube, Spray. Squirrel box on a post in the yard.
- Backyard: flat lawn slab, a house with porch (st.House + deck/posts/roof), a trampoline (torus rim + disc on
  legs), Max's yard lamp meter (post with a RED and a GREEN lamp: the recurring result meter).
- Freeboard marker: red 100-year-flood bar, green crest bar, yellow dimension arrows + label.
- Rain: a real Blender particle system of thin streaks. Map line: a long orange tube along the levee.
- Max (hard hat, yellow rain boots) and two kids -> engine.character.Character. Shovel -> wood + metal.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from engine import events, studio as st, textures as tx, toy
from engine.camera import CameraRig, facing_to
from engine.character import Character
from engine.machines import Puffs, Spray
from engine.sets.levee_story_earthen_river_le_story_spec import ACTIONS, beat_actions

V = Vector
R = math.radians

# ------------------- layout (scene metres; the section face is y = 0, the camera looks from -y) -------------------
D = 120.0                                            # depth of the riverbank block behind the cut
LZ = 0.06                                            # lawn top
LOW, HIGH, OVER, FLOOD100 = -1.0, 2.0, 2.45, 2.2     # river levels
CREST2, CREST3 = 2.2, 3.1
V1 = [(-1.7, 0.02), (1.7, 0.02), (0.6, 3.0), (-0.6, 3.0)]
V1_WET = [(-1.65, 0.03), (1.67, 0.03), (1.385, 0.83), (-0.95, 1.96)]     # soaked wedge under the seepage line
V2 = [(-6.2, 0.02), (6.2, 0.02), (0.7, CREST2), (-0.7, CREST2)]
CORE2 = [(-0.9, 0.02), (0.9, 0.02), (0.3, 2.05), (-0.3, 2.05)]
V3 = [(-6.2, 0.02), (6.2, 0.02), (0.5, CREST3), (-0.5, CREST3)]
CORE3 = [(-1.3, 0.02), (1.3, 0.02), (0.3, 2.95), (-0.3, 2.95)]
BERM = [(3.0, 0.02), (9.6, 0.02), (9.6, 0.12), (3.0, 1.05)]
GRASS3 = [(-0.5, CREST3), (0.5, CREST3), (4.75, 0.803), (9.6, 0.12)]
BURROW = [(4.55, 0.0, 1.15), (2.6, 0.0, 1.3), (0.0, 0.0, 1.48), (-2.7, 0.0, 1.6)]
PIPED = [(4.55, 0.0, 1.15), (2.6, 0.0, 1.3), (0.0, 0.0, 1.48), (-2.9, 0.0, 1.6), (-4.0, 0.0, 1.65)]
# overtopping sheet on v2: over the crest, down the land slope, spreading onto the lawn
FALLS2 = [(-0.7, CREST2), (0.7, CREST2), (3.45, 1.11), (6.2, 0.02), (7.4, LZ)]


def berm_z(x):
    return 1.05 - 0.1409 * (x - 3.0)


def grass_z(x):
    """Standing height on v3's grass shell where it covers the berm (0.14 m shell + room for a sloped stance)."""
    return berm_z(x) + 0.155


def slope2(x):
    return 2.2 - (x - 0.7) * 0.39636


def scour(d):
    """v2's land slope with an erosion bite `d` m deep, listed from x = 3.5 back up to x = 1.4 (it stays above
    the buried berm)."""
    return [(3.5, slope2(3.5)), (3.2, slope2(3.2) - 0.2 * d), (2.8, slope2(2.8) - 0.6 * d),
            (2.3, slope2(2.3) - d), (1.8, slope2(1.8) - 0.6 * d), (1.4, slope2(1.4))]


BOIL = V((8.0, 1.4, LZ))
YARD = V((11.55, 1.3, LZ))
METER = V((12.55, 0.75, LZ))
DUCK_YARD = V((13.05, 1.05, LZ + 0.012))
PROMISE_MAX = V((3.7, 1.3, LZ))
PROMISE_KIDS = [V((5.1, 1.1, LZ)), V((5.75, 1.5, LZ))]
WALL_MAX = V((4.7, 1.3, LZ))
CREST2_MAX = V((0.0, 2.6, CREST2 + 0.012))
CREST3_MAX = V((-0.2, 2.4, CREST3 + 0.012))
BAG_MAX = V((9.85, 1.4, LZ))
BUR_MAX = V((5.9, 1.6, berm_z(5.76) + 0.006))     # on the berm, side-on to the burrow (feet along y)
BUR_FACE = facing_to(BUR_MAX, V((4.5, 1.6, BUR_MAX.z)))     # side-on, toward the burrow entrance
FIN_MAX = V((12.95, 1.6, LZ))
TRAMP = V((15.6, 3.2, LZ))
TRAMP_TOP = 0.935
KIDS_TRAMP = [V((15.25, 3.0, TRAMP_TOP + 0.02)), V((16.0, 3.35, TRAMP_TOP + 0.02))]
SBOX = V((14.05, 0.95, LZ))
SBOX_TOP = LZ + 1.3 + 0.42 + 0.045
SQ_HOOK = V((8.3, 1.4, berm_z(8.3) + 0.005))
DUCK_LAND = V((9.0, 0.9, berm_z(9.0) + 0.01))
JET_SRC = V((4.6, 0.12, 1.12))
HOUSE = V((22.5, 6.5, LZ - 0.02))
# per-beat spots: Max, and the portable result lamp just behind him, inside the same cutaway frame
PROMISE_LOOK = [V((2.95, 0.7, LZ)), V((2.35, 0.55, LZ))]
SAND_MAX, SAND_LAMP = V((3.05, 0.8, LZ + 0.012)), V((3.45, 2.4, LZ))
CORE_MAX, CORE_LAMP = V((0.0, 1.1, CREST2 + 0.012)), V((-0.42, 2.3, CREST2 + 0.005))
BOIL_MAX, BOIL_LAMP = V((9.6, 0.9, LZ)), V((9.25, 2.6, LZ))
BERM_MAX, BERM_LAMP = V((5.75, 0.9, berm_z(5.75) + 0.035)), V((6.15, 2.4, berm_z(6.15) + 0.005))
OVER_MAX, OVER_LAMP = V((4.4, 1.0, berm_z(4.4) + 0.03)), V((5.0, 2.4, berm_z(5.0) + 0.005))
BUR_MAX2, BUR_LAMP = V((7.0, 1.2, grass_z(7.0))), V((5.3, 2.9, berm_z(5.3) + 0.12))
MAINT_MAX, MAINT_LAMP = V((5.45, 1.0, grass_z(5.45) + 0.01)), V((4.9, 2.6, berm_z(4.9) + 0.12))
JET_ARC = [(4.4, 0.14, 1.14), (5.05, 0.2, 1.62), (5.5, 0.25, 1.76), (5.95, 0.32, 1.5), (6.3, 0.38, 0.92)]
JET_HIT2 = V((6.3, 0.4, berm_z(6.3) + 0.16))
DUCK_JET = V((5.5, 0.25, 1.72))                    # riding on top of the muddy jet
SQ_SIDE = V((5.15, 1.0, berm_z(5.15) + 0.17))      # beside the burrow, behind the jet
HOOK_MAX2 = V((7.0, 1.3, grass_z(7.0)))
FIN_CREST, FIN_LAMP2 = V((-0.25, 1.6, CREST3 + 0.152)), V((0.05, 2.9, CREST3 + 0.12))
HOOK_MAX, HOOK_LAMP = V((6.3, 1.4, berm_z(6.3) + 0.006)), V((6.75, 3.0, berm_z(6.75) + 0.12))
FIN_LAMP = V((12.6, 2.6, LZ))
SQ_PEEK = V((5.35, 0.45, berm_z(5.35) + 0.13))
JET_HIT = V((6.6, 0.5, berm_z(6.6) + 0.05))

LIGHTS = {"day": (4.0, (1.0, 0.95, 0.86), 0.2, 900.0, 40.0),
          "storm": (0.9, (0.66, 0.74, 0.9), 0.03, 650.0, 12.0),
          "squall": (2.8, (0.86, 0.9, 0.98), 0.12, 850.0, 22.0)}
BLUE, YELLOW, RED, GREEN = "#3FA9F5", "#FFD23F", "#FF4A3A", "#3CCB5A"


def fr(b, e, t):
    return b + int(round((e - b) * t))


def band(pts, t, lift=0.008):
    """Closed x-z outline of a shell of thickness t lying on the polyline `pts` (left -> right along a top)."""
    segn = []
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, z1 - z0)
        segn.append((-(z1 - z0) / L, (x1 - x0) / L))
    nrm = []
    for k in range(len(pts)):
        if k == 0:
            nrm.append(segn[0])
        elif k == len(pts) - 1:
            nrm.append(segn[-1])
        else:
            nx, nz = segn[k - 1][0] + segn[k][0], segn[k - 1][1] + segn[k][1]
            L = math.hypot(nx, nz)
            nrm.append((nx / L, nz / L))
    inner = [(x + nx * lift, z + nz * lift) for (x, z), (nx, nz) in zip(pts, nrm)]
    outer = [(x + nx * t, z + nz * t) for (x, z), (nx, nz) in zip(pts, nrm)]
    return inner + outer[::-1]


def noise(name, a, b, scale=8.0, rough=0.85, bump=0.0):
    return toy.noise_material(name, toy.srgb(a), toy.srgb(b), scale=scale, roughness=rough, bump=bump)


def tube(name, pts, radius, mat):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for k, p in enumerate(pts):
        sp.points[k].co = (*p, 1.0)
    sp.order_u = 3
    sp.use_endpoint_u = True
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    cu.materials.append(mat)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    return ob


class LeveeStoryEarthenRiverLeStorySet:
    ACTIONS = ACTIONS
    QA_ALLOW = (r"lawn|topsoil|sandlayer|bedrock|river|water|levee|core|grass|tuft|riprap|berm|well|ditch|duck"
                r"|boil|bag|crack|gouge|falls|pipewater|squirrel|sbox|tramp|meter|house|porch|pile|shovel|map"
                r"|arrow|label|puff|spray|jet|splash|rain|ground_|wet|puddle|dim|bar_")

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self.rnd = random.Random(23)
        self.sky = next((n for n in scene.world.node_tree.nodes if n.type == "TEX_SKY"), None)
        self._light_state = LIGHTS["day"]
        self.groups = {}
        self.rl = LOW
        self._materials()
        self._ground()
        self._levees()
        self._yard()
        self._props()
        self._people()
        self._key_light(1, LIGHTS["day"])
        self.stage(1, set())
        self.meter(1, "off")
        self.lamp(1, None)

    # ------------------- build -------------------

    def _materials(self):
        self.m_sand = noise("lv_sand", "#E6CF8E", "#CDB06C", scale=40, bump=0.25)
        self.m_sand_flat = noise("lv_sand_flat", "#E6CF8E", "#CBAE6A", scale=30)
        self.m_wet = noise("lv_wet_sand", "#8A6E40", "#6A532E", scale=22, rough=0.35)
        self.m_top = noise("lv_topsoil", "#6E4B2E", "#4F3420", scale=18, bump=0.2)
        self.m_clay = noise("lv_clay", "#5A3A26", "#46291A", scale=9, rough=0.7)
        self.m_fill3 = noise("lv_fill", "#A4825A", "#8A6A46", scale=14)
        self.m_berm = noise("lv_berm", "#93714A", "#7A5C3A", scale=12)
        self.m_mud = noise("lv_mud", "#4A3220", "#33210F", scale=16, rough=0.3)
        self.m_burrow = noise("lv_burrow", "#3B2717", "#2A1A0E", scale=20)
        self.m_bags = noise("lv_burlap", "#B99C68", "#9A7E50", scale=60)
        self.m_rock = noise("lv_riprap", "#8E8C86", "#5C5A55", scale=6, bump=0.3)
        self.m_bed = st.section_rock("lv_bedrock", "#8C8B88", "#6F6E6B")
        self.m_lawn = st.rock_grass("lv_lawn", grass_above=-1.0)
        self.m_grass = st.rock_grass("lv_grass", grass="#4E9A34", grass_dark="#3A7A26", grass_above=-1.0)
        self.m_falls = tx.paint("lv_falls", "#5FB8E8", rough=0.06, coat=1.0)
        self.m_steel = tx.metal("lv_steel", "#9AA3AA")
        self.m_wood = tx.wood("lv_wood", "#8A5F38", "#A87A4C")

    def _ground(self):
        st.prism("bedrock", [(-24, -40), (30, -40), (30, -3.005), (-24, -3.005)], 0.0, D, self.m_bed)
        st.prism("sandlayer", [(-24, -3.0), (30, -3.0), (30, -0.6), (-6.2, -0.6), (-6.8, -1.6), (-14.4, -1.6),
                               (-15.0, -0.6), (-24, -0.6)], 0.0, D, self.m_sand)
        st.prism("topsoil_l", [(-24, -0.595), (-15.0, -0.595), (-15.0, 0.0), (-24, 0.0)], 0.0, D, self.m_top)
        st.prism("topsoil_r", [(-6.2, -0.595), (30, -0.595), (30, 0.0), (11.0, 0.0), (11.0, -0.35), (10.2, -0.35),
                               (10.2, 0.0), (-6.2, 0.0)], 0.0, D, self.m_top)
        for nm, x0, x1 in (("lawn_l", -24.0, -15.0), ("lawn_a", -6.2, 10.2), ("lawn_b", 11.0, 30.0)):
            toy.box(nm, (x1 - x0, D - 0.01, LZ - 0.005), ((x0 + x1) / 2, (D + 0.01) / 2, (LZ + 0.005) / 2),
                    mat=self.m_lawn, bevel=0)
        st.world_floor(z=0.0, around=(-24.0, 30.0, D))
        self.res = st.Reservoir("river", -24.0, -0.6, 0.05, D, bottom=-1.6, level=LOW)
        self.res.key_level(1, LOW)

    def _grp(self, name, *objs):
        self.groups.setdefault(name, []).extend(objs)

    def _levees(self):
        # v1: the steep pure-sand wall (it slumps: no bump on its material)
        self.v1 = st.prism("levee1", V1, 0.0, D, self.m_sand_flat)
        wet = st.prism("levee1_wet", V1_WET, -0.006, 0.4, self.m_wet)
        wet.parent = self.v1
        self.wet_wall = wet
        self.wet_lawn = toy.box("wet_lawn", (2.2, 6.0, 0.006), (2.8, 3.02, LZ + 0.004), mat=self.m_wet, bevel=0)
        self._grp("v1", self.v1)
        self._grp("wet", wet, self.wet_lawn)
        # v2: wide, gentle, sand shell + clay core
        self.v2 = [st.prism("levee2", V2, 0.0, D, self.m_sand_flat),
                   st.prism("core2", CORE2, -0.012, D, self.m_clay)]
        self._grp("v2", *self.v2)
        # v3: taller, clay core, grass shell, riprap; plus burrowed and piped copies (carved once each)
        self.v3 = self._make_v3("")
        self.v3b = self._make_v3("_burrow", BURROW, 0.2)
        self.v3p = self._make_v3("_piped", PIPED, 0.34)
        self._grp("v3", *self.v3)
        self._grp("v3b", *self.v3b)
        self._grp("v3p", *self.v3p)
        back = st.prism("grass3_back", band(GRASS3, 0.14), -0.016 + 14.02, D, self.m_grass)
        self._grp("grass", back)
        # tall grass only on the land slope (not the crest or berm where Max stands): scatter on a temporary shell
        tmp = st.prism("tufts_ground", band([(0.95, 2.857), (4.7, 0.83)], 0.14), -0.016, 14.0, self.m_grass)
        self.tufts = st.scatter_on("tufts", tmp, density=5.0, max_slope_deg=34, seed=5)
        self.tufts.parent = None
        bpy.data.objects.remove(tmp, do_unlink=True)
        self._grp("tufts", self.tufts)
        self._riprap()
        # seepage berm, relief wells, ditch water
        self.berm = st.prism("berm", BERM, -0.008, D, self.m_berm)
        self._grp("berm", self.berm)
        well = st.prism("well_section", [(9.8, -2.4), (10.0, -2.4), (10.0, 0.45), (9.8, 0.45)], -0.01, 0.14,
                        self.m_steel)
        core = st.prism("well_water", [(9.85, -2.3), (9.95, -2.3), (9.95, 0.4), (9.85, 0.4)], -0.014, 0.1,
                        st.water_volume("lv_wellwater", "#2B86C9", 2.0))
        cap = toy.cylinder("well_cap0", 0.13, 0.05, (9.9, 0.07, 0.47), mat=self.m_steel)
        self._grp("wells", well, core, cap)
        for k, y in enumerate((1.8, 3.6, 5.4)):
            self._grp("wells", toy.cylinder(f"well_{k}", 0.1, 0.85, (9.9, y, 0.025), mat=self.m_steel, vertices=16),
                      toy.cylinder(f"well_cap{k + 1}", 0.13, 0.05, (9.9, y, 0.47), mat=self.m_steel))
        self._grp("wells", toy.box("ditch_water", (0.76, D - 0.03, 0.23), (10.6, (D + 0.03) / 2, -0.215),
                                   mat=st.water_volume("lv_ditch", "#2B86C9", 1.2), bevel=0))
        # overtopping: waterfall sheet + scour gouge on v2's land slope
        self.falls = st.prism("falls", band(FALLS2, 0.12), 0.02, D, self.m_falls)
        self._grp("falls", self.falls)
        cx, cz = 2.8, 1.15
        pts = [(1.7, 1.79), (2.25, 1.57), (2.8, 1.36), (3.35, 1.14), (3.9, 0.92), (3.6, 0.62), (2.9, 0.55),
               (2.2, 0.85), (1.85, 1.35)]
        self.gouge = st.prism("gouge", [(x - cx, z - cz) for x, z in pts], -0.013, 0.6, self.m_mud)
        self.gouge.location = (cx, 0, cz)
        self._grp("gouge", self.gouge)
        # freeboard marker
        glow_r, glow_g = st.glow_mat("lv_bar_red", RED, 1.2), st.glow_mat("lv_bar_green", GREEN, 1.2)
        self._grp("marker", toy.box("bar_flood", (7.4, 0.04, 0.07), (-2.6, -0.045, FLOOD100), mat=glow_r, bevel=0),
                  toy.box("bar_crest", (1.8, 0.04, 0.07), (0.4, -0.045, CREST3 + 0.04), mat=glow_g, bevel=0))
        # the piped burrow's water and the land-side jet
        self.pipewater = tube("pipewater", [(x, 0.1, z - 0.04) for x, _, z in PIPED], 0.22,
                              tx.paint("lv_pipewater", "#4AA8E0", rough=0.05, coat=1.0))
        self._grp("pipewater", self.pipewater)

    def _make_v3(self, tag, path=None, radius=0.0):
        objs = [st.prism(f"levee3{tag}", V3, 0.0, D, self.m_fill3),
                st.prism(f"core3{tag}", CORE3, -0.012, D, self.m_clay),
                st.prism(f"grass3{tag}", band(GRASS3, 0.14), -0.016, 14.0, self.m_grass)]
        if path:
            for k, ob in enumerate(objs):              # staggered radii: the tunnel walls never share a surface
                st.carve(ob, st.tube_cutter(path, radius + 0.012 * k), mat=self.m_burrow)
        return objs

    def _riprap(self):
        bm = bmesh.new()
        rnd = random.Random(9)
        nx, nz = -0.475, 0.88
        z = 0.3
        while z < 3.0:
            x = -6.2 + (z - 0.02) * 5.7 / 3.08
            y = 0.35
            while y < 12.0:
                r = rnd.uniform(0.15, 0.23)
                c = V((x + nx * r * 0.35, y + rnd.uniform(-0.08, 0.08), z + nz * r * 0.35))
                m = (Matrix.Translation(c) @ Matrix.Rotation(rnd.uniform(0, 6.28), 4, "Z")
                     @ Matrix.Diagonal((1.0, rnd.uniform(0.8, 1.1), 0.62, 1.0)))
                bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r, matrix=m)
                y += rnd.uniform(0.38, 0.5)
            z += 0.3
        me = bpy.data.meshes.new("riprap")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new("riprap", me)
        self.scene.collection.objects.link(ob)
        me.materials.append(self.m_rock)
        self._grp("riprap", ob)

    def _yard(self):
        self.house = st.House("house", HOUSE, w=4.2, d=3.6, h=2.6)
        planks = tx.planks("lv_deck", "#9C7146", "#87603B", width=0.14, across="x", along="y")
        py = HOUSE.y - 1.8 - 0.66
        toy.box("porch_deck", (3.0, 1.3, 0.16), (HOUSE.x, py, LZ + 0.07), mat=planks, bevel=0.01)
        for sx in (-1.35, 1.35):
            toy.cylinder(f"porch_post{sx}", 0.06, 2.2, (HOUSE.x + sx, py - 0.5, LZ + 1.25), mat=self.m_wood)
        toy.box("porch_roof", (3.3, 1.5, 0.1), (HOUSE.x, py + 0.05, LZ + 2.38),
                mat=tx.shingles("lv_porchroof", "#A8402F", "#5E2318"), bevel=0.01)
        # trampoline: legs, padded torus rim, black mat
        pad = tx.paint("lv_tramp_pad", "#2F7FD6", rough=0.5, coat=0.3)
        for k in range(6):
            a = 2 * math.pi * k / 6 + 0.3
            toy.cylinder(f"tramp_leg{k}", 0.035, 0.9, (TRAMP.x + 1.45 * math.cos(a), TRAMP.y + 1.45 * math.sin(a),
                                                       LZ + 0.42), mat=self.m_steel, vertices=10)
        bpy.ops.mesh.primitive_torus_add(major_radius=1.5, minor_radius=0.08, location=(TRAMP.x, TRAMP.y, 0.88))
        rim = bpy.context.active_object
        rim.name = "tramp_rim"
        rim.data.materials.append(pad)
        toy.cylinder("tramp_mat", 1.42, 0.02, (TRAMP.x, TRAMP.y, 0.9), mat=tx.rubber("lv_tramp_mat", "#1C1C1F"),
                     vertices=48)
        # Max's yard lamp: the recurring RESULT meter (red = flooded, green = dry)
        self.lamp_red = st.glow_mat("lv_lamp_red", "#FF3B2F", 0.0)
        self.lamp_green = st.glow_mat("lv_lamp_green", "#3CFF6A", 0.0)
        self.yard_meter = [
            toy.cylinder("meter_post", 0.05, 2.3, (METER.x, METER.y, LZ + 1.13), mat=self.m_steel, vertices=16),
            toy.box("meter_head", (0.42, 0.2, 0.85), (METER.x, METER.y, LZ + 2.5), mat=tx.paint("lv_meter",
                                                                                             "#2C3036", 0.4), bevel=0.03),
            toy.sphere("meter_red", 0.15, (METER.x, METER.y - 0.1, LZ + 2.72), mat=self.lamp_red),
            toy.sphere("meter_green", 0.15, (METER.x, METER.y - 0.1, LZ + 2.3), mat=self.lamp_green)]
        # the portable result lamp (every beat but fix_armor): ONE globe that is grey, red or green
        self.plamp = toy.empty("meter_port", (0, 0, -40))
        head = tx.paint("lv_plamp_head", "#2C3036", 0.4)
        for nm, ob, loc in (("post", toy.cylinder("meter_port_post", 0.045, 2.15, (0, 0, 0), mat=self.m_steel,
                                                  vertices=12), (0, 0, 1.075)),
                            ("head", toy.box("meter_port_head", (0.36, 0.24, 0.42), (0, 0, 0), mat=head, bevel=0.03),
                             (0, 0, 2.365)),
                            ("hood", toy.box("meter_port_hood", (0.46, 0.34, 0.05), (0, 0, 0), mat=head, bevel=0.01),
                             (0, 0, 2.605))):
            ob.parent, ob.location = self.plamp, loc
        self.globes = {}
        for state, m in (("off", toy.material("lv_plamp_off", toy.srgb("#59606A"), roughness=0.25, coat=0.8)),
                         ("red", st.glow_mat("lv_plamp_red", "#FF3B2F", 9.0)),
                         ("green", st.glow_mat("lv_plamp_green", "#3CFF6A", 9.0))):
            g = toy.sphere(f"meter_port_{state}", 0.17, (0, 0, 0), mat=m)
            g.parent, g.location = self.plamp, (0, -0.2, 2.36)
            self.globes[state] = g
        # squirrel box on a post
        toy.cylinder("sbox_post", 0.05, 1.3, (SBOX.x, SBOX.y, LZ + 0.64), mat=self.m_wood, vertices=12)
        sb = [toy.box("sbox_body", (0.42, 0.38, 0.42), (SBOX.x, SBOX.y, LZ + 1.3 + 0.21), mat=self.m_wood),
              toy.box("sbox_roof", (0.5, 0.46, 0.04), (SBOX.x, SBOX.y, LZ + 1.3 + 0.42 + 0.025),
                      mat=tx.paint("lv_sbox_roof", "#A8402F", 0.5)),
              toy.cylinder("sbox_hole", 0.08, 0.012, (SBOX.x, SBOX.y - 0.195, LZ + 1.55), rotation=(R(90), 0, 0),
                           mat=self.m_burrow)]
        self._grp("sbox", *sb)
        # yard flood puddle (shown after every failure)
        ring = []
        for k in range(28):
            a = 2 * math.pi * k / 28
            r = 1 + 0.16 * math.sin(3 * a + 0.4) + 0.08 * math.sin(5 * a)
            ring.append((12.9 + 0.85 * r * math.cos(a), 1.0 + 0.55 * r * math.sin(a), LZ + 0.008))
        self.puddle = st.mesh_obj("yard_puddle", ring, [tuple(range(28))], (st.water_surface("lv_puddle"),),
                                  smooth=False)
        st.no_shadow(self.puddle)
        self._grp("puddle", self.puddle)
        # sand pile (promise)
        bpy.ops.mesh.primitive_cone_add(radius1=1.3, radius2=0.05, depth=1.1, vertices=40,
                                        location=(1.6, 2.2, LZ - 0.01 + 0.55))
        pile = bpy.context.active_object
        pile.name = "pile"
        pile.data.materials.append(self.m_sand)
        self._grp("pile", pile)
        # sand boil: cone, crater, fountain column, crack through the blanket, ring of sandbags
        bpy.ops.mesh.primitive_cone_add(radius1=0.75, radius2=0.2, depth=0.32, vertices=32,
                                        location=(BOIL.x, BOIL.y, LZ - 0.01 + 0.16))
        cone = bpy.context.active_object
        cone.name = "boil_cone"
        cone.data.materials.append(self.m_wet)
        bpy.ops.mesh.primitive_cone_add(radius1=0.17, radius2=0.06, depth=0.8, vertices=16,
                                        location=(BOIL.x, BOIL.y, LZ + 0.29 + 0.4))
        self.fountain = bpy.context.active_object
        self.fountain.name = "boil_fountain"
        self.fountain.data.materials.append(self.m_mud)
        crack = st.prism("crack", [(7.92, -0.6), (8.06, -0.6), (8.12, -0.3), (8.04, 0.0), (7.9, 0.0), (7.98, -0.3)],
                         -0.007, 0.3, self.m_mud)
        self._grp("boil", cone, self.fountain, crack)
        self.bags = []
        for layer, (n, rad, z) in enumerate(((11, 0.98, LZ + 0.072), (9, 0.92, LZ + 0.2))):
            for k in range(n):
                a = 2 * math.pi * (k + 0.5 * layer) / n
                bag = toy.capsule(f"bag_{layer}_{k}", 0.11, 0.32, (BOIL.x + rad * math.cos(a), BOIL.y + rad * math.sin(a),
                                                                    z), rotation=(0, R(90), a + R(90)), mat=self.m_bags)
                bag.scale = (0.6, 1.0, 1.0)
                self.bags.append(bag)
        self._grp("bags", *self.bags)

    def _props(self):
        # rubber duck
        yel = noise("lv_duck_yellow", "#FFD21F", "#F2B90C", scale=10, rough=0.25)
        ora = toy.material("lv_duck_beak", toy.srgb("#FF8A1A"), roughness=0.3, coat=0.4)
        blk = toy.material("lv_eye", toy.srgb("#111111"), roughness=0.15, coat=1.0)
        self.duck = toy.empty("duck", (-9.5, 0.6, LOW - 0.03))
        for nm, r, loc, sc, m in (("body", 0.16, (0, 0, 0.1), (1.35, 1.0, 0.8), yel),
                                  ("tail", 0.07, (-0.2, 0, 0.17), (1.2, 0.8, 0.8), yel),
                                  ("head", 0.105, (0.13, 0, 0.27), (1, 1, 1), yel),
                                  ("beak", 0.055, (0.235, 0, 0.25), (1.4, 1.0, 0.45), ora),
                                  ("eyeL", 0.022, (0.18, -0.075, 0.31), (1, 1, 1), blk),
                                  ("eyeR", 0.022, (0.18, 0.075, 0.31), (1, 1, 1), blk)):
            p = toy.sphere(f"duck_{nm}", r, (0, 0, 0), scale=sc, mat=m)
            p.parent = self.duck
            p.location = loc
        self.duck.scale = (1.6, 1.6, 1.6)
        self.duck.keyframe_insert("location", frame=1)
        self.duck.keyframe_insert("rotation_euler", frame=1)
        toy.add_noise(self.duck, "location", 2, strength=0.025, scale=14, phase=3)
        toy.add_noise(self.duck, "rotation_euler", 0, strength=0.06, scale=18, phase=7)
        # ground squirrel
        fur = tx.cloth("lv_fur", "#9C6A3E", rough=0.85)
        belly = tx.cloth("lv_fur_belly", "#E6CDA0", rough=0.85)
        self.squirrel = toy.empty("squirrel", (0, 0, -30))
        for nm, r, loc, sc, m in (("body", 0.12, (0, 0, 0.13), (1.0, 0.9, 1.25), fur),
                                  ("belly", 0.08, (0, -0.075, 0.115), (0.95, 0.55, 1.15), belly),
                                  ("head", 0.085, (0, -0.02, 0.32), (1, 1, 1), fur),
                                  ("earL", 0.03, (-0.05, 0.0, 0.4), (1, 0.6, 1.2), fur),
                                  ("earR", 0.03, (0.05, 0.0, 0.4), (1, 0.6, 1.2), fur),
                                  ("eyeL", 0.016, (-0.033, -0.095, 0.34), (1, 1, 1), blk),
                                  ("eyeR", 0.016, (0.033, -0.095, 0.34), (1, 1, 1), blk),
                                  ("nose", 0.014, (0, -0.105, 0.31), (1, 1, 1), blk),
                                  ("tail", 0.09, (0, 0.15, 0.26), (0.8, 0.7, 2.0), fur)):
            p = toy.sphere(f"squirrel_{nm}", r, (0, 0, 0), scale=sc, mat=m)
            p.parent = self.squirrel
            p.location = loc
        self.sq_arm = toy.empty("squirrel_shoulder", (0, 0, 0))
        self.sq_arm.parent = self.squirrel
        self.sq_arm.location = (0.1, -0.04, 0.22)
        arm = toy.capsule("squirrel_arm", 0.026, 0.11, (0, 0, 0), mat=fur)
        arm.parent = self.sq_arm
        arm.location = (0, 0, -0.07)
        self._grp("squirrel", self.squirrel)
        # Max's shovel
        self.shovel = toy.empty("shovel", (0, 0, 0))
        h = toy.cylinder("shovel_handle", 0.022, 0.8, (0, 0, 0), mat=self.m_wood, vertices=10)
        h.parent, h.location = self.shovel, (0, 0, -0.2)
        bl = toy.box("shovel_blade", (0.2, 0.03, 0.24), (0, 0, 0), mat=self.m_steel, bevel=0.01)
        bl.parent, bl.location = self.shovel, (0, 0, -0.7)
        self._grp("shovel", self.shovel)
        # rain: a real particle system of thin streaks
        drop = toy.cylinder("rain_drop", 0.017, 0.6, (0, 0, -300), mat=st.glow_mat("lv_drop", "#D6E8FF", 1.4),
                            vertices=6)
        bpy.ops.mesh.primitive_plane_add(size=1, location=(4.0, 2.5, 40.0))
        em = bpy.context.active_object
        em.name = "rain_emitter"
        em.scale = (36, 13, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        em.data.materials.append(tx.paint("lv_rain_cloud", "#9AA4AE", rough=0.8, coat=0.0))
        mod = em.modifiers.new("rain", "PARTICLE_SYSTEM")
        ps = mod.particle_system
        ps.seed = 7
        s = ps.settings
        s.count = int(70 * (self.total + 400))
        s.frame_start, s.frame_end, s.lifetime = 1, self.total + 400, 34
        s.emit_from = "FACE"
        s.normal_factor = 0.0
        s.object_align_factor = (0.0, 0.0, -34.0)
        s.render_type = "OBJECT"
        s.instance_object = drop
        s.particle_size, s.size_random = 1.0, 0.4
        em.show_instancer_for_render = False
        em.show_instancer_for_viewport = False
        self._grp("rain", em)
        # a dark storm deck in the sky (shown with the rain, gone when the storm clears)
        cloud = noise("lv_cloud", "#5A6068", "#3A3F46", scale=1.5, rough=1.0)
        rc = random.Random(31)
        for k in range(16):
            c = toy.sphere(f"rain_cloud{k}", rc.uniform(7.0, 12.0), (rc.uniform(-40, 50), rc.uniform(25, 80),
                                                                     rc.uniform(13, 21)), scale=(1.6, 1.0, 0.32),
                           mat=cloud)
            st.no_shadow(c)
            self._grp("rain", c)
        # the map line along the levee, far into the distance
        pts = [(0, 0.5, CREST3 + 0.45), (0, D - 1, CREST3 + 0.45), (2, D + 6, 0.6), (10, 170, 0.6), (-12, 230, 0.6),
               (6, 300, 0.6), (-6, 380, 0.6), (4, 440, 0.6)]
        self._grp("map", tube("map_line", pts, 0.45, st.glow_mat("lv_map", "#FF7A1A", 2.0)))
        self.jet = Spray("jet_spray", tx.paint("lv_jet", "#6C8FA8", rough=0.1, coat=0.8), count=34, radius=0.06, seed=4)
        self.mud_jet = Spray("jet_mud", self.m_mud, count=44, radius=0.1, seed=8)
        self.squirrel.scale = (1.5, 1.5, 1.5)
        self.boil_spray = Spray("boil_spray", self.m_mud, count=28, radius=0.05, seed=5)
        self.splash = Spray("splash_spray", self.m_falls, count=24, radius=0.05, seed=6)

    def _people(self):
        self.max = Character("Max", {"hat": "#FF7A00", "shirt": "#E8492F", "shoes": "#F2C230", "iris": "#7A4A1C"})
        self.max.place(1, YARD, 0)
        self.max.key("hips", 1, loc=(0, 0, 0.56))
        self.max.auto_blink(1, self.total + 400, seed=11)
        self.max.hold(self.shovel, "R")
        self.shovel.location = (0, -0.04, 0.28)
        self.kids = [Character("Kid1", {"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5",
                                        "shoes": "#F2C230", "hair": "#5B3A1E", "scale": 0.6, "ponytail": True}),
                     Character("Kid2", {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B",
                                        "shoes": "#3A7BD5", "hair": "#2B1A10", "scale": 0.56})]
        for k, kid in enumerate(self.kids):
            kid.place(1, KIDS_TRAMP[k], 0)
            kid.key("hips", 1, loc=(0, 0, 0.56))
            kid.auto_blink(1, self.total + 400, seed=k + 3)
            self._grp("kids", kid.root)

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
            self._lamps_at(self.spans[i][0], a == "fix_armor")
            getattr(self, f"a_{a}")(i, *self.spans[i])
        hb, he = self.spans[0]
        self._lamps_at(hb + epilogue_offset, False)
        getattr(self, f"a_{self.acts[0]}")(0, hb + epilogue_offset, he + epilogue_offset)
        self.rig.build()

    # ------------------- helpers -------------------

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
        self._key_light(f - ramp, self._light_state)
        self._light_state = LIGHTS[name]
        self._key_light(f, self._light_state)

    def weather(self, f, storm):
        self.light(f, "storm" if storm else "day")
        self.vis(f, "rain", storm)

    def show(self, obj, f, visible=True):
        toy.hide_tree(obj, f, not visible)

    def vis(self, f, group, visible=True):
        for o in self.groups[group]:
            self.show(o, f, visible)

    def stage(self, f, names):
        """At a cut: exactly these optional groups are on stage."""
        for g in self.groups:
            self.vis(f, g, g in names)

    def label(self, text, loc, f0, f1, size=0.32, tilt=-4):
        root = st.label(text, loc, f0, f1, size=size, tilt=tilt)
        for f in (f0, f0 + 5, f0 + 8, f1 - 5, f1):
            root.scale = (1, 1, 1)
            root.keyframe_insert("scale", frame=f)
        return root

    def meter(self, f, state):
        st.key_glow(self.lamp_red, f, 6.0 if state == "red" else 0.0, constant=True)
        st.key_glow(self.lamp_green, f, 6.0 if state == "green" else 0.0, constant=True)
        if state in ("red", "green"):
            events.add(f, "switch", gain=0.3)

    def river(self, f, level, f_from=None):
        """River reaches `level` at f (from the current level held at f_from, or a cut at f)."""
        self.res.key_level(f_from if f_from is not None else f - 1, self.rl)
        self.res.key_level(f, level)
        self.rl = level

    def duck_key(self, f, pos, rot=(0, 0, 0)):
        self.duck.location = pos
        self.duck.rotation_euler = rot
        self.duck.keyframe_insert("location", frame=f)
        self.duck.keyframe_insert("rotation_euler", frame=f)

    def duck_cut(self, f, pos, rot=(0, 0, 0)):
        toy.key_hold(self.duck, "location", f - 1)
        toy.key_hold(self.duck, "rotation_euler", f - 1)
        self.duck_key(f, pos, rot)

    def duck_river(self, f, x, level=None):
        self.duck_cut(f, (x, 0.6, (self.rl if level is None else level) - 0.03))

    def sq_cut(self, f, pos, yaw=0.0):
        """The squirrel jumps to a new spot at a cut (it never drifts between scenes)."""
        toy.key_hold(self.squirrel, "location", f - 1)
        toy.key_hold(self.squirrel, "rotation_euler", f - 1)
        self.sq_key(f, pos, yaw)

    def sq_key(self, f, pos, yaw=0.0):
        self.squirrel.location = pos
        self.squirrel.rotation_euler = (0, 0, R(yaw))
        self.squirrel.keyframe_insert("location", frame=f)
        self.squirrel.keyframe_insert("rotation_euler", frame=f)

    def salute(self, f0, f1):
        for f, rot in ((f0, (0, 0, 0)), (f0 + 6, (R(-20), R(150), 0)), (f1 - 6, (R(-20), R(150), 0)), (f1, (0, 0, 0))):
            self.sq_arm.rotation_euler = rot
            self.sq_arm.keyframe_insert("rotation_euler", frame=f)

    def at(self, f, spot, face=0.0):
        self.max.cut_place(f, spot, face)
        self.max.pose(f + 6)

    def close(self, f0, f1, who=None, frac=0.36, angle=-92.0, swing=16.0, offset=(0, 0, 0), lens=32.0, rise=0.25):
        who = who or self.max
        st.close_on(self.rig, f0, f1, who, frac=frac, angle=angle, swing=swing, rise=rise, lens=lens, look=0.62,
                    offset=offset, cut=True, fstop=5.6, height=1.9 if who is self.max else 1.12)

    def shot(self, f0, f1, cam0, cam1, aim0, aim1=None, lens=24.0):
        self.rig.shot(f0, f1, cam_from=cam0, cam_to=cam1, aim_from=aim0, aim_to=aim1 or aim0, lens=lens, fstop=8.0,
                      cut=True)

    def pan(self, f0, f1, stops, lens=24.0):
        """A tracking shot through (t, cam, aim) stops (t in 0..1 of the shot), eased between stops."""
        keys = []
        for f in list(range(f0, f1, 3)) + [f1]:
            t = (f - f0) / max(1, f1 - f0)
            for (ta, ca, aa), (tb, cb, ab) in zip(stops, stops[1:]):
                if ta <= t <= tb:
                    u = st.smooth((t - ta) / max(1e-6, tb - ta))
                    keys.append((f, V(ca).lerp(V(cb), u), V(aa).lerp(V(ab), u)))
                    break
        self.rig.track(f0, f1, keys, lens=lens, fstop=8.0, cut=True)

    def v_arms(self, f0, f1):
        m = self.max
        m.pose(f0)
        m.pose(f0 + 6, shoulderL=(0, -150, 0), shoulderR=(0, 150, 0), head=(-8, 0, 0))
        m.pose(f1 - 6, shoulderL=(0, -156, 0), shoulderR=(0, 156, 0), head=(-10, 0, 0))
        m.pose(f1)
        m.smile(f0 + 6, big=True)
        m.brows(f0 + 6, 0.6)
        m.brows(f1, 0.0)

    def shrug(self, f0, f1):
        """Arms low and forward-out, head tilted, brows up: 'oh well' (never a T or a cheer)."""
        m = self.max
        m.pose(f0)
        m.pose(f0 + 5, shoulderL=(-32, -40, 0), shoulderR=(-32, 40, 0), head=(-4, 0, 16))
        m.pose(f1 - 4, shoulderL=(-36, -44, 0), shoulderR=(-36, 44, 0), head=(-4, 0, 18))
        m.brows(f0 + 5, 0.9)
        m.key("mouth", f0 + 5, scale=(1.3, 0.6, 0.7))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f1, 0.0)
        m.pose(f1)
        events.add(f0 + 5, "boing", gain=0.3)

    def jaw_drop(self, f0, f1):
        """Hands flung up beside the head, mouth wide open, brows high, leaning back."""
        m = self.max
        m.pose(f0)
        m.pose(f0 + 4, shoulderL=(-35, -118, 0), shoulderR=(-35, 118, 0), head=(-16, 0, 0))
        m.pose(f1 - 2, shoulderL=(-38, -124, 0), shoulderR=(-38, 124, 0), head=(-18, 0, 0))
        m.key("mouth", f0 + 4, scale=(1.3, 0.6, 3.4))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f0 + 4, 1.0)
        m.brows(f1, 0.0)

    def lamp(self, f, state, pos=None):
        """The portable result lamp: moved to `pos` at a cut, its ONE globe grey / red / green (None = hidden)."""
        if pos is not None:
            toy.key_hold(self.plamp, "location", f - 1)
            self.plamp.location = pos
            self.plamp.keyframe_insert("location", frame=f)
        toy.hide_tree(self.plamp, f, state is None)
        for s, g in self.globes.items():
            toy.hide_tree(g, f, s != state)
        if state in ("red", "green"):
            events.add(f, "switch", gain=0.3)

    def _lamps_at(self, f, yard):
        """Each beat starts with the portable lamp put away; the old two-globe yard lamp only in fix_armor."""
        self.lamp(f, None)
        for o in self.yard_meter:
            self.show(o, f, yard)

    def view(self, f0, f1, cx, cz, h, lens=30.0, push=0.06, sway=0.9, yc=0.6):
        """A cutaway shot framing `h` metres (at depth yc) centred on (cx, cz): the camera sways sideways and
        pushes in a little while the aim stays put, so the frame never sits still and nothing leaves it."""
        d = h * lens / 36.0
        aim = V((cx, yc, cz))
        keys = []
        for f in list(range(f0, f1, 3)) + [f1]:
            t = st.smooth((f - f0) / max(1, f1 - f0))
            keys.append((f, V((cx + sway * (t - 0.5), yc - d * (1.0 - push * t), cz + 0.45)), aim))
        self.rig.track(f0, f1, keys, lens=lens, fstop=8.0, cut=True)

    def travel(self, f0, f1, stops, lens=30.0, yc=0.6):
        """Follow the water along the section: stops = (t, cx, cz, h) eased between (same framing as view)."""
        keys = []
        for f in list(range(f0, f1, 3)) + [f1]:
            t = (f - f0) / max(1, f1 - f0)
            for (ta, *pa), (tb, *pb) in zip(stops, stops[1:]):
                if ta <= t <= tb:
                    u = st.smooth((t - ta) / max(1e-6, tb - ta))
                    cx, cz, h = (p + (q - p) * u for p, q in zip(pa, pb))
                    break
            d = h * lens / 36.0
            keys.append((f, V((cx, yc - d, cz + 0.45)), V((cx, yc, cz))))
        self.rig.track(f0, f1, keys, lens=lens, fstop=8.0, cut=True)

    def result(self, f0, f1, ok):
        """The recurring RESULT: Max beside his yard lamp (green = dry yard, red = flooded, duck in the puddle)."""
        self.at(f0, YARD, 0)
        self.meter(f0, "green" if ok else "red")
        if ok:
            self.v_arms(f0 + 4, f1 - 2)
        else:
            self.vis(f0, "puddle", True)
            self.duck_cut(f0, DUCK_YARD, (0, 0, R(-20)))
            self.shrug(f0 + 2, f1 - 2)
        self.close(f0, f1, frac=0.3, offset=(0.35, 0, -0.1), angle=-93, swing=12)

    def fill_puffs(self, name, frames, pts, color="#8A6A44"):
        pts, frames = [V(p) for p in pts], list(frames)
        if not frames:
            return
        f0, span = frames[0], frames[-1] - frames[0] + 1
        Puffs(name, color, count=12, size=0.22, seed=len(name)).emit(
            frames, lambda f: pts[min(len(pts) - 1, int((f - f0) / span * len(pts)))] + V((0, -0.2, 0)),
            rise=0.5, life=18)

    # ------------------- the ladder -------------------

    def a_promise(self, i, b, e):
        m = fr(b, e, 0.5)
        self.stage(b, {"pile", "kids", "shovel"})
        self.weather(b, False)
        self.river(b, LOW)
        self.duck_river(b, -9.5)
        self.duck_key(e, (-8.4, 0.6, LOW - 0.03))
        self.meter(b, "off")
        self.at(b, PROMISE_MAX, 0)
        for k, kid in enumerate(self.kids):
            kid.cut_place(b, PROMISE_KIDS[k], facing_to(PROMISE_KIDS[k], PROMISE_MAX))
            kid.pose(b + 2)
            kid.hop(b + 8, m - 2, height=0.12, period=16, sound="step")
            kid.smile(b + 8, big=True)
        self.max.talk(b + 8, m - 4)
        self.max.smile(b + 8, big=True)
        self.max.point(m + 2, e - 4, hand="R", up_deg=35, side_deg=70)
        self.max.brows(m + 2, 0.8)
        events.add(b + 10, "kids_cheer", gain=0.35)
        self.close(b, m, frac=0.34, offset=(0.75, 0, 0), angle=-92)
        # he points at the river: seen from the front-right, the low river and the duck fill the background
        for k, kid in enumerate(self.kids):
            kid.cut_place(m, PROMISE_LOOK[k], facing_to(PROMISE_LOOK[k], V((-8.0, 6.0, 0))))
            kid.pose(m + 2)
            kid.look_at(m + 4, (-8.0, 6.0, -0.5))
        self.close(m, e, frac=0.3, offset=(-0.5, 0, -0.1), angle=-52, swing=12)

    def a_fail_sand(self, i, b, e):
        m1 = fr(b, e, 0.37)
        s = fr(m1, e, 0.3)
        self.stage(b, {"v1", "shovel"})
        self.weather(b + 10, True)
        self.river(b, LOW)
        self.river(m1 - 2, HIGH, f_from=b + 8)
        self.duck_river(b, -5.0, LOW)
        self.duck_key(m1 - 2, (-1.55, 0.4, HIGH - 0.03))
        events.add(b + 8, "water_rush", duration=m1 - b - 8, gain=0.4)
        self.lamp(b, "off", SAND_LAMP)
        # CHANGE: Max shovels up a tall, steep wall of pure sand
        self.at(b, SAND_MAX, 0)
        self.max.sweep(b + 6, m1 - 8, hand="R")
        self.fill_puffs("puff_wall", range(b + 6, m1 - 8, 5), [(0.95, 0.5, 2.2), (1.25, 0.5, 1.4), (1.5, 0.5, 0.7)])
        self.max.look_at(m1 - 6, (-1.0, 0, 2.2), hold=10)
        self.close(b, m1, frac=0.36, offset=(-0.8, 0, 0.1), angle=-96)
        # WHY + RESULT in one cutaway: water runs through the grains, the land side soaks, the face slumps,
        # the duck oozes over the mush, the lamp behind Max turns red and he shrugs
        for k, z in enumerate((0.5, 1.05, 1.6)):
            st.arrow(f"arrow_seep{k}", (-1.65, -0.06, z), (3.7, 0, 0), m1 + 2 + 6 * k, e, color=BLUE, width=0.08)
        self.label("SAND LEAKS", (0.0, -0.3, 3.6), m1 + 2, e, size=0.34)
        self.vis(m1 + 10, "wet", True)
        self.v1.scale = (1, 1, 1)
        self.v1.keyframe_insert("scale", frame=s - 1)
        self.v1.scale = (1.7, 1.0, 0.45)
        self.v1.keyframe_insert("scale", frame=s + 14)
        events.add(s, "creak", gain=0.5)
        events.add(s + 4, "rumble", duration=14, gain=0.6)
        self.river(s + 20, 1.3, f_from=s)
        self.duck_key(s, (-1.55, 0.4, HIGH - 0.03))
        self.duck_key(s + 10, (-0.6, 0.4, 1.5), (0, R(-8), 0))
        self.duck_key(s + 22, (0.9, 0.4, 1.45), (0, R(10), 0))
        self.duck_key(s + 34, (1.8, 0.3, 0.8), (0, R(25), 0))
        self.duck_key(s + 44, (2.1, 0.25, 0.6), (0, R(25), 0))
        self.lamp(s + 18, "red")
        self.shrug(s + 22, e - 2)
        self.view(m1, e, 0.9, 2.0, 10.5)

    def a_fix_core(self, i, b, e):
        m1 = fr(b, e, 0.37)
        g = fr(m1, e, 0.45)
        self.stage(b, {"v2", "shovel"})
        self.weather(b, False)
        self.river(b, HIGH)
        self.duck_river(b, -2.3)
        self.duck_key(e, (-2.0, 0.6, HIGH - 0.03))
        self.lamp(b, "off", CORE_LAMP)
        # CHANGE: Max shapes the wide, gentle levee around its clay core, from its crest
        self.at(b, CORE_MAX, 0)
        self.max.sweep(b + 8, m1 - 4, hand="R")
        self.fill_puffs("puff_core", range(b + 8, m1 - 4, 5), [(0.3, 0.9, 2.25)])
        events.add(b + 8, "step", gain=0.4)
        self.close(b, m1, frac=0.38, offset=(0, 0, -0.7), angle=-92)
        # WHY + RESULT: the arrow runs through the sand, stops short inside the clay; green lamp, Max cheers
        st.arrow("arrow_sand", (-2.5, -0.06, 0.9), (1.6, 0, 0), m1 + 2, e, color=BLUE, width=0.09)
        st.arrow("arrow_clay", (-0.75, -0.07, 0.9), (0.4, 0, 0), m1 + 10, e, color=BLUE, width=0.05)
        self.label("SAND", (-1.75, -0.3, 1.45), m1 + 2, e, size=0.3)
        self.label("CLAY CORE", (0.0, -0.3, -0.35), m1 + 2, e, size=0.28)
        self.lamp(g, "green")
        self.v_arms(g + 4, e - 2)
        self.view(m1, e, -0.3, 2.4, 9.0)

    def a_fail_boil(self, i, b, e):
        m1, erupt, p = fr(b, e, 0.3), fr(b, e, 0.4), fr(b, e, 0.45)
        bag0, bag1 = fr(b, e, 0.55), fr(b, e, 0.8)
        self.stage(b, {"v2", "rain"})
        self.weather(b, True)
        self.river(b, HIGH)
        self.duck_river(b, -3.8)
        self.lamp(b, "off", BOIL_LAMP)
        self.at(b, BOIL_MAX, 0)
        self.v_arms(b + 4, m1 - 2)
        self.close(b, m1, frac=0.36, offset=(-0.9, 0, -0.2), angle=-94)
        # WHY: the camera follows the water UNDER the levee through the buried sand, up to the boil in the yard
        st.arrow("arrow_bed", (-9.0, -0.06, -1.0), (1.6, 0, -0.75), m1 + 2, e, color=BLUE, width=0.1)
        st.arrow("arrow_under0", (-6.6, -0.06, -1.9), (13.2, 0, 0), m1 + 2, e, color=BLUE, width=0.11)
        st.arrow("arrow_under1", (-5.6, -0.06, -2.5), (12.0, 0, 0), m1 + 8, e, color=BLUE, width=0.09)
        for k, x in enumerate((7.3, 8.7)):
            st.arrow(f"arrow_up{k}", (x, -0.06, -1.6), (0, 0, 1.45), erupt - 10, e, color=BLUE, width=0.11)
        self.travel(m1, p, [(0.0, -3.6, -0.6, 8.0), (0.2, -3.0, -0.5, 8.0), (1.0, 8.1, 0.6, 9.0)])
        # RESULT in the same frame: the boil erupts beside Max, the lamp behind him turns red, he rings it
        self.vis(erupt, "boil", True)
        self.fountain.scale = (1, 1, 0.05)
        self.fountain.keyframe_insert("scale", frame=erupt)
        self.fountain.scale = (1, 1, 1)
        self.fountain.keyframe_insert("scale", frame=erupt + 10)
        toy.add_noise(self.fountain, "scale", 2, strength=0.08, scale=6, phase=erupt)
        self.boil_spray.run(erupt + 4, e, (BOIL.x, BOIL.y, 1.05), (BOIL.x, BOIL.y, 0.36), spread=0.5, arc=0.35,
                            period=14)
        events.add(erupt, "bubbles", duration=e - erupt, gain=0.6)
        self.label("SAND BOIL", (BOIL.x, -0.3, 2.1), erupt + 4, e, size=0.32)
        self.duck_cut(erupt + 4, (BOIL.x, BOIL.y, 0.1))
        self.duck_key(erupt + 16, (BOIL.x, BOIL.y, 1.1), (0, 0, R(-30)))
        self.lamp(erupt + 6, "red")
        self.max.look_at(erupt + 2, (BOIL.x, BOIL.y, 0.6), hold=max(0, bag0 - erupt - 6))
        self.max.brows(erupt + 2, 1.0)
        self.max.sweep(bag0, bag1, hand="R")
        n = len(self.bags)
        for k, bag in enumerate(self.bags):
            f = bag0 + int((bag1 - bag0 - 4) * k / n)
            self.show(bag, f)
            bag.keyframe_insert("scale", frame=f + 3)
            sc = tuple(bag.scale)
            bag.scale = (0.01, 0.01, 0.01)
            bag.keyframe_insert("scale", frame=f)
            bag.scale = sc
            if k % 4 == 0:
                events.add(f, "stone_thud", gain=0.3)
        self.shrug(bag1 + 2, e - 2)
        self.view(p, e, 8.1, 0.6, 9.0)

    def a_fix_berm(self, i, b, e):
        m1, a, g = fr(b, e, 0.37), fr(b, e, 0.44), fr(b, e, 0.6)
        self.stage(b, {"v2", "berm"})
        self.weather(b, False)
        self.river(b, HIGH)
        self.duck_river(b, -3.8)
        self.duck_key(e, (-4.6, 0.6, HIGH - 0.03))
        # CHANGE: the berm rises on the land side, the wells go in at its toe
        self.at(b, YARD, 0)
        self.berm.scale = (1, 1, 0.02)
        self.berm.keyframe_insert("scale", frame=b + 4)
        self.berm.scale = (1, 1, 1)
        self.berm.keyframe_insert("scale", frame=m1 - 8)
        self.fill_puffs("puff_berm", range(b + 6, m1 - 8, 5), [(5.0, 0.6, 0.8), (7.0, 0.6, 0.6), (9.0, 0.6, 0.3)])
        events.add(b + 6, "rumble", duration=m1 - b - 12, gain=0.4)
        self.vis(b + 20, "wells", True)
        events.add(b + 20, "steel_clank", gain=0.4)
        self.max.point(b + 8, m1 - 2, hand="R", up_deg=20, side_deg=70)
        self.close(b, m1, frac=0.36, offset=(-1.3, 0, -0.3), angle=-100)
        # WHY + RESULT in one cutaway: Max on the new berm, weight arrows press down, the wells vent into the
        # ditch, the up-arrow under the yard shrinks, the lamp behind him turns green
        self.at(m1, BERM_MAX, 0)
        self.lamp(m1, "off", BERM_LAMP)
        st.arrow("arrow_under2", (5.0, -0.06, -1.7), (2.6, 0, 0), m1 + 2, e, color=BLUE, width=0.1)
        st.arrow("arrow_upbig", (8.0, -0.06, -1.6), (0, 0, 1.45), m1 + 2, a, color=BLUE, width=0.11)
        st.arrow("arrow_upsmall", (8.0, -0.06, -1.6), (0, 0, 0.45), a, e, color=BLUE, width=0.08)
        st.arrow("arrow_well", (9.9, -0.08, -2.1), (0, 0, 2.7), a, e, color=BLUE, width=0.09)
        st.arrow("arrow_ditch", (9.95, -0.08, 0.62), (0.35, 0, -0.55), a + 6, e, color=BLUE, width=0.07)
        for k, (x, z) in enumerate(((6.5, 1.65), (8.3, 1.2))):
            st.arrow(f"arrow_weight{k}", (x, -0.06, z), (0, 0, -0.6), m1 + 4, e, color=YELLOW, width=0.1)
        self.label("SEEPAGE BERM", (7.9, -0.3, 2.3), m1 + 2, e, size=0.3)
        self.label("RELIEF WELLS", (8.6, -0.3, -0.8), a, e, size=0.3)
        events.add(a, "pour", duration=e - a, gain=0.25)
        self.lamp(g, "green")
        self.v_arms(g + 4, e - 2)
        self.view(m1, e, 7.4, 0.4, 10.0, sway=0.4)

    def a_fail_overtop(self, i, b, e):
        m1, m2 = fr(b, e, 0.37), fr(b, e, 0.8)
        red = fr(b, e, 0.5)
        self.stage(b, {"v2", "berm", "wells", "rain"})
        self.weather(b, True)
        self.river(b, HIGH)
        self.river(m1, OVER, f_from=b + 4)
        self.duck_river(b, -3.4, HIGH)
        self.duck_key(m1, (-0.3, 0.5, OVER - 0.03))
        events.add(b + 4, "water_rush", duration=e - b - 4, gain=0.6)
        self.lamp(b, "off", OVER_LAMP)
        # CHANGE: a huge storm, the river climbs toward the crest while Max watches from the land slope
        self.at(b, OVER_MAX, 0)
        self.max.look_at(b + 8, (-2.0, 0, 4.0), hold=max(0, m1 - b - 12))
        self.max.brows(b + 8, 0.9)
        self.max.brows(m1 - 2, 0.0)
        self.close(b, m1, frac=0.36, offset=(-1.4, 0, 0.4), angle=-100)
        # WHY + RESULT in one cutaway: water pours over the crest, scours the bare slope, the duck surfs down,
        # the lamp behind Max turns red and he shrugs
        self.vis(m1 - 4, "falls", True)
        self.vis(m1 + 6, "gouge", True)
        self.gouge.scale = (0.15, 1, 0.15)
        self.gouge.keyframe_insert("scale", frame=m1 + 6)
        self.gouge.scale = (1, 1, 1)
        self.gouge.keyframe_insert("scale", frame=m2 - 6)
        self.splash.run(m1, e, (3.4, 0.3, 1.2), (3.95, 0.3, 0.95), spread=0.3, arc=0.4, period=12)
        Puffs("puff_scour", "#5A4028", count=14, size=0.25, seed=8).emit(
            range(m1 + 8, m2 - 6, 4), lambda f: V((2.8, -0.25, 1.3)), rise=0.6, life=18)
        self.label("OVERTOPPING", (1.4, -0.3, 3.7), m1 + 2, e, size=0.32)
        sf = fr(m1, m2, 0.3)
        self.duck_key(sf, (0.6, 0.5, CREST2 + 0.15))
        self.duck_key(sf + 12, (2.2, 0.5, 1.75), (0, R(22), 0))
        self.duck_key(sf + 24, (3.0, 0.45, 1.38), (0, R(18), 0))
        self.lamp(red, "red")
        self.shrug(red + 4, e - 2)
        self.view(m1, e, 2.5, 1.4, 10.0, sway=0.4)

    def a_fix_armor(self, i, b, e):
        m1, m2 = fr(b, e, 0.3), fr(b, e, 0.78)
        rise1 = b + 28
        self.stage(b, {"v3", "berm", "wells"})
        self.weather(b, False)
        self.river(b, FLOOD100)
        self.duck_river(b, -3.8)
        self.duck_key(e, (-4.6, 0.6, FLOOD100 - 0.03))
        self.meter(b, "off")
        for ob in self.v3[:2]:
            ob.scale = (1, 1, CREST2 / CREST3)
            ob.keyframe_insert("scale", frame=b + 4)
            ob.scale = (1, 1, 1)
            ob.keyframe_insert("scale", frame=rise1)
        self.show(self.v3[2], b, False)
        self.show(self.v3[2], rise1)
        self.vis(rise1, "grass", True)
        self.vis(rise1, "tufts", True)
        self.vis(rise1 + 4, "riprap", True)
        events.add(b + 4, "rumble", duration=rise1 - b - 4, gain=0.4)
        events.add(rise1 + 4, "stone_thud", gain=0.5)
        self.max.cut_place(b, V((CREST3_MAX.x, CREST3_MAX.y, CREST2 + 0.012)), 0)
        self.max.pose(b + 2)
        self.max.move(b + 4, rise1, CREST3_MAX)
        self.v_arms(rise1 + 2, m1 - 2)
        # WHY: freeboard above the flood line + armour on both slopes
        self.vis(m1, "marker", True)
        st.arrow("dim_up", (1.15, -0.07, 2.65), (0, 0, 0.45), m1 + 2, m2, color=YELLOW, width=0.07)
        st.arrow("dim_down", (1.15, -0.07, 2.65), (0, 0, -0.45), m1 + 2, m2, color=YELLOW, width=0.07)
        self.label("3 FT ABOVE\n100-YEAR FLOOD", (1.35, -0.3, 4.05), m1 + 2, m2, size=0.26)
        self.label("RIPRAP", (-1.9, -0.3, 3.75), m1 + 6, m2, size=0.28)
        self.close(b, m1, frac=0.34, offset=(0, 0, -0.5), angle=-92)
        self.shot(m1, m2, (-0.7, -7.1, 2.6), (0.3, -6.6, 2.4), (-0.2, 0, 2.3), (0.0, 0, 2.25))
        self.result(m2, e, ok=True)

    def a_fail_burrow(self, i, b, e):
        m1, rise = fr(b, e, 0.3), fr(b, e, 0.4)
        p, jet = fr(b, e, 0.44), fr(b, e, 0.5)
        dig = b + 14
        self.stage(b, {"v3", "grass", "tufts", "riprap", "berm", "wells", "squirrel"})
        self.weather(b, False)
        self.river(b, LOW)
        self.duck_river(b, -9.0)
        self.lamp(b, "off", BUR_LAMP)
        self.at(b, BUR_MAX2, 0)
        self.v_arms(b + 4, b + 22)
        self.max.look_at(b + 26, (4.6, 0, 1.0), hold=max(0, m1 - b - 28))
        # CHANGE: a ground squirrel digs a tunnel into the land slope, right beside Max
        self.sq_cut(b, (5.1, 0.25, berm_z(5.1) + 0.13), -90)
        self.sq_key(dig - 4, (4.75, 0.05, 1.0), -90)
        self.vis(dig, "v3", False)
        self.vis(dig, "v3b", True)
        for f, (x, _, z) in zip((dig, dig + 14, m1 - 6), BURROW[:3]):
            self.sq_key(f, (x, 0.0, z - 0.17), -90)
        self.vis(m1 - 4, "squirrel", False)
        self.fill_puffs("puff_dig", range(dig - 2, m1 - 6, 4), [(4.7, 0, 1.15), (4.2, 0, 1.2), (3.6, 0, 1.25)])
        events.add(dig, "rumble", duration=m1 - dig - 6, gain=0.25)
        self.view(b, m1, 5.7, 1.3, 6.4, sway=0.3)
        # WHY: the camera follows the flood into the burrow; the water carries soil out and the hole widens
        self.weather(m1, True)
        self.river(rise, FLOOD100, f_from=m1 + 2)
        events.add(m1 + 2, "water_rush", duration=e - m1 - 2, gain=0.5)
        self.duck_key(m1 + 2, (-9.0, 0.6, LOW - 0.03))
        self.vis(p, "v3b", False)
        self.vis(p, "v3p", True)
        self.vis(p, "pipewater", True)
        st.arrow("arrow_pipe0", (-2.4, -0.12, 1.95), (2.0, 0, -0.15), p, e, color=BLUE, width=0.08)
        st.arrow("arrow_pipe1", (2.3, -0.12, 1.75), (2.0, 0, -0.45), p, e, color=BLUE, width=0.08)
        self.label("PIPING", (4.0, -0.3, 3.0), jet - 4, e, size=0.42)
        self.travel(m1, jet, [(0.0, -1.6, 1.4, 8.0), (0.4, -1.2, 1.4, 8.0), (1.0, 4.5, 1.3, 9.0)])
        # RESULT in the same frame: a muddy jet blasts out beside Max, the duck rides it onto the berm,
        # the squirrel pops out and salutes, the lamp behind Max turns red, his jaw drops
        self.jet.run(jet - 4, e, JET_SRC, JET_HIT, spread=0.35, arc=0.9, period=14)
        self.mud_jet.run(jet - 4, e, JET_SRC, JET_HIT, spread=0.3, arc=0.95, period=12)
        events.add(jet - 4, "pour", duration=e - jet + 4, gain=0.5)
        self.show(self.duck, p, False)
        self.duck_cut(jet - 2, (4.7, 0.3, 1.15), (0, R(-25), 0))
        self.show(self.duck, jet - 2, True)
        self.duck_key(jet + 8, (5.6, 0.4, 1.85), (0, R(10), 0))
        self.duck_key(jet + 18, (6.35, 0.45, berm_z(6.35) + 0.15), (0, R(15), 0))
        self.vis(jet + 6, "squirrel", True)
        self.sq_cut(jet + 6, tuple(SQ_PEEK), -20)
        self.salute(jet + 10, e - 2)
        self.lamp(jet + 4, "red")
        self.jaw_drop(jet + 2, e - 2)
        self.view(jet, e, 5.2, 1.3, 9.5, sway=0.3)

    def a_fix_maintain(self, i, b, e):
        m1, filled = fr(b, e, 0.37), fr(b, e, 0.6)
        g0, g1 = fr(b, e, 0.66), fr(b, e, 0.76)
        self.stage(b, {"v3p", "grass", "riprap", "berm", "wells", "shovel"})
        self.weather(b, False)
        self.river(b, LOW)
        self.duck_river(b, -9.0)
        self.duck_key(e, (-8.0, 0.6, LOW - 0.03))
        self.lamp(b, "off", MAINT_LAMP)
        # CHANGE: grass mowed short; Max inspects the hole and packs it shut with his shovel
        self.at(b, MAINT_MAX, facing_to(MAINT_MAX, V((4.5, MAINT_MAX.y, MAINT_MAX.z))))
        self.max.hammer(b + 6, filled - 2, hand="R")
        self.fill_puffs("puff_pack", range(b + 8, filled - 2, 5), [(4.8, 0.2, 1.05)])
        for f in range(b + 12, filled - 2, 14):
            events.add(f, "stone_thud", gain=0.4)
        self.close(b, m1, frac=0.4, offset=(-0.4, 0, -0.3), angle=-98, swing=14)
        # WHY + RESULT in one cutaway: the 8.2 m tunnel is a shortcut for the water; packed, it is gone,
        # the lamp behind Max turns green
        st.arrow("dim_burrow0", (2.6, -0.1, 1.95), (1.95, 0, -0.55), m1 + 2, e, color=YELLOW, width=0.06)
        st.arrow("dim_burrow1", (2.6, -0.1, 1.95), (-5.3, 0, -0.05), m1 + 2, e, color=YELLOW, width=0.06)
        self.label("8.2 m", (2.6, -0.3, 2.6), m1 + 2, e, size=0.5)
        self.fill_puffs("puff_fill", range(filled - 14, filled + 6, 3),
                        [(1.6, 0, 1.4), (2.6, 0, 1.33), (3.6, 0, 1.25), (4.4, 0, 1.18)])
        self.vis(filled, "v3p", False)
        self.vis(filled, "v3", True)
        events.add(filled, "stone_thud", gain=0.6)
        self.max.turn(filled + 2, 0, frames=8)
        self.lamp(filled + 4, "green")
        self.v_arms(filled + 10, e - 2)
        self.view(m1, g0, 3.8, 1.3, 9.0)
        # the squirrel moves into its own box in the yard (a short gag), then back to the packed levee
        self.vis(g0, "sbox", True)
        self.vis(g0, "squirrel", True)
        self.sq_cut(g0, (SBOX.x, SBOX.y, SBOX_TOP), 0)
        self.salute(g0 + 2, g1)
        self.shot(g0, g1, (SBOX.x - 0.3, SBOX.y - 2.7, 1.95), (SBOX.x + 0.3, SBOX.y - 2.4, 1.9),
                  (SBOX.x, SBOX.y, 1.6), lens=30)
        self.view(g1, e, 3.8, 1.3, 9.0, sway=-0.9)

    def a_finale(self, i, b, e):
        s1, s2, s3, s4 = fr(b, e, 0.2), fr(b, e, 0.6), fr(b, e, 0.76), e
        clear = fr(b, e, 0.48)
        self.stage(b, {"v3", "grass", "riprap", "berm", "wells", "sbox", "squirrel", "kids", "rain"})
        self.weather(b, True)
        self.weather(clear, False)
        self.river(b, 2.4)
        self.duck_river(b, -3.9)
        self.lamp(b, "green", FIN_LAMP)
        events.add(b, "water_rush", duration=clear - b, gain=0.4)
        # every arrow stays on the river side
        for k, (x, z, L) in enumerate(((-6.0, 1.0, 1.4), (-4.9, 1.8, 1.7), (-6.6, 0.4, 1.0))):
            st.arrow(f"arrow_river{k}", (x, -0.06, z), (L, 0, 0), b + 2 + 4 * k, s1, color=BLUE, width=0.1)
        self.view(b, s1, -3.4, 1.6, 8.0)
        # Max cheers by the green lamp, the kids bounce on the dry trampoline, the squirrel salutes
        self.at(b, FIN_MAX, 0)
        self.max.key("hips", s1, loc=(0, 0, 0.56))
        self.max.cheer(s1 + 2, s2 - 2)
        for k, kid in enumerate(self.kids):
            kid.cut_place(b, KIDS_TRAMP[k], -15 if k == 0 else 15)
            kid.pose(b + 2)
            kid.hop(s1 + 2 + 5 * k, s2 + 20, height=0.32, period=18, sound="boing")
            kid.smile(s1 + 2, big=True)
        self.sq_cut(b, (SBOX.x, SBOX.y, SBOX_TOP), 0)
        self.salute(s1 + 10, s2 - 4)
        events.add(s1 + 4, "kids_cheer", gain=0.7)
        self.view(s1, s2, 14.2, 1.3, 6.8, yc=1.6)
        # the duck floats away down the river
        self.duck_key(s2, (-6.0, 0.8, 2.37))
        self.duck_key(s3, (-11.0, 6.0, 2.37), (0, 0, R(120)))
        self.shot(s2, s3, (-7.0, -6.2, 4.0), (-8.0, -5.4, 3.6), (-7.0, 2.0, 2.2), (-8.6, 3.5, 2.2))
        # pull out to the map line
        self.vis(s3, "map", True)
        self.label("3,787 MILES", (0, 90, 24), s3 + 4, s4, size=9.0, tilt=0)
        self.shot(s3, s4, (8.0, -12.0, 7.0), (6.0, -40.0, 48.0), (6.0, 6.0, 1.0), (0.0, 90.0, 6.0))

    # ------------------- hooks (epilogue, after the finale) -------------------

    def a_burrow_hook(self, i, h0, h1):
        hm = fr(h0, h1, 0.45)
        self.stage(h0, {"v3p", "grass", "tufts", "riprap", "berm", "wells", "rain", "squirrel", "pipewater"})
        self.weather(h0, True)
        self.river(h0, FLOOD100)
        self.meter(h0, "red")
        self.duck_cut(h0, (4.7, 0.3, 1.15), (0, R(-25), 0))
        self.duck_key(h0 + 12, (6.6, 0.5, 1.9), (0, R(10), 0))
        self.duck_key(h0 + 24, tuple(DUCK_LAND), (0, R(15), 0))
        self.jet.run(h0, h1, JET_SRC, (7.6, 0.8, 0.45), spread=0.35, arc=0.9, period=14)
        events.add(h0, "pour", duration=h1 - h0, gain=0.6)
        events.add(h0 + 24, "boing", gain=0.4)
        self.sq_cut(h0, tuple(SQ_HOOK), 0)
        self.salute(h0 + 8, h1 - 2)
        self.at(h0, YARD, 0)
        self.jaw_drop(hm, h1)
        self.shot(h0, hm, (5.8, -7.4, 1.6), (6.6, -6.8, 1.4), (6.4, 0, 0.9), (6.6, 0, 0.85))
        self.close(hm, h1, frac=0.24, offset=(-1.4, 0, -0.3), angle=-94, swing=12)

    def a_happy_hook(self, i, h0, h1):
        self.stage(h0, {"v3", "grass", "riprap", "berm", "wells", "sbox", "squirrel", "kids", "rain"})
        self.weather(h0, True)
        self.river(h0, 2.4)
        self.duck_river(h0, -4.8)
        self.meter(h0, "green")
        self.sq_cut(h0, (SBOX.x, SBOX.y, SBOX_TOP), 0)
        self.salute(h0 + 8, h1 - 2)
        self.at(h0, FIN_MAX, 0)
        self.max.key("hips", h0 + 4, loc=(0, 0, 0.56))
        self.max.cheer(h0 + 6, h1 - 2)
        for k, kid in enumerate(self.kids):
            kid.cut_place(h0, KIDS_TRAMP[k], -15 if k == 0 else 15)
            kid.pose(h0 + 2)
            kid.hop(h0 + 4 + 5 * k, h1, height=0.32, period=18, sound="boing")
            kid.smile(h0 + 4, big=True)
        events.add(h0 + 6, "kids_cheer", gain=0.6)
        self.close(h0, h1, frac=0.26, offset=(1.3, 0, -0.1), angle=-94, swing=14)
