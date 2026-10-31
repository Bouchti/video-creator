"""
BACKYARD WATER TOWER set (trial-and-error): Max builds his own backyard water tower to feed his kids' 3 m water
slide "like a real town", with no pump running. A sunny backyard ~10 m wide, sliced open at y = 0 (camera at -y):
the soil face shows the buried supply and outlet pipes, the well, and (later) the tower's concrete footings.

ASSET PLAN (real object -> real shape / proportions -> the detail that makes it read -> how it is built)
- YARD GROUND: flat lawn, soil section face with strata; a pipe trench, a well shaft and two footing pits carved
  into the face so the buried parts are seen -> st.terrain + st.section_rock + st.carve(box_cutter) + world_floor.
- WELL + PUMP: a small surface pump (blue motor drum, dark volute, concrete pad) over a drilled well with water at
  the bottom, a wall switch with a lamp -> primitives, st.Water in the carved shaft.
- TANK: 1,000 L galvanised steel cube 1.2 m -> subdivided cube (bmesh) with a 'dent' shape key for the vacuum
  crumple; cut open on the camera side (st.Cutaway + st.section_clip) so the water level and float valve show.
  Water inside: a box whose level is a shape key (no squashing). Lid with bolts; screened vent (pipe, mesh band,
  mushroom cap); float valve (brass body, arm, big ball); inlet pipe; overflow pipe -> primitives / st.pipe.
- THIN POLES: four 6 m wooden poles 9 cm thick, each two segments with a knee pivot so they bow and fold.
- STEEL TOWER: four splayed painted steel legs, X cross-braces on every face (visible triangles), ring beam under
  the tank, a grated balcony with railing and a ladder, concrete footings in the cutaway pits -> rods, boxes.
- PRESSURE POST + GAUGE: white survey post with yellow ticks every metre (0.1 bar each) and a round dial gauge
  (dark bezel, white face, tick ring, red needle) at its foot, copper tube to the outlet pipe -> primitives.
- WATER SLIDE (it carries the gushing water, so it is part of the mechanism): platform 3 m up on posts, ladder,
  yellow chute with blue side walls, a run-out; a water sheet on the chute; nozzle + valve wheel -> st.prism, rods.
- STREAMS: slide gush, overflow cascade and inlet stream are continuous ballistic curves with drops (Spray); the
  crash splash is st.Jet crowns + Puffs.
- GARDEN HOSE (failure 1): green rubber hose on the grass, a clear vertical section up the ladder showing the water
  column stop at the tank's own level, a dashed blue WATER LEVEL line.
- CITY MODEL (scale card): tabletop New York block, brick towers with window grids, little wooden rooftop tanks on
  stilts with conical roofs, a sky board behind, a glowing blue sixth-floor line -> primitives, tx.tiles / planks.
- BLENDERKIT (whole recognisable props, with primitive fallbacks): house, trees, deckchair, owl.
- PEOPLE: Max (orange hard hat) and his two kids (engine.character), held props: wrench, lemonade, float, vent.
"""

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from engine import events, studio as st, textures as tx, toy
from engine import props as bk
from engine.camera import CameraRig, facing_to
from engine.character import Character
from engine.machines import Puffs, Spray
from engine.sets.s_backyard_water_tower_raise_story_spec import ACTIONS, beat_actions
import zlib

V = Vector
R = math.radians

# ------------------- layout (metres; cut face y = 0, camera at -y) -------------------
FOOT = 0.025
TY = 0.9                     # tank centre y (x = 0)
TS = 1.2                     # tank cube
H = 6.0                      # tank base when raised
GROUND_Z = 0.02              # tank base on the grass
WATER_B, WATER_H = 0.03, 1.16
MAX_AT = V((2.55, 0.14, FOOT))          # beside the gauge, in front of its dial plane (arms clear the dial)
PUMP_MAX = V((-2.75, 0.3, FOOT))
CHAIR_AT = V((2.0, 1.25, 0.0))
CHAIR_MAX = V((2.55, 0.14, FOOT))       # stands beside the deckchair with his lemonade (no sitting)
BALC_AT = V((-1.12, 0.9, H + FOOT))
TABLE_MAX = V((-1.2, 0.15, FOOT))
SLIDE_MAX = V((6.1, 0.12, FOOT))
GAUGE = V((1.8, 0.33, 1.0))
NOZZLE = V((3.9, 0.9, 3.15))
FALL_TO = V((-2.25, 0.95, 0.14))
FALL_ROT = -0.55
CHUTE_X0, CHUTE_X1, RUN_X1 = 3.75, 6.6, 7.4
KID_PLAT = [Vector((3.2, 0.68, 3.045)), Vector((3.5, 1.08, 3.045))]   # soles 2 cm clear of the deck
OWL_TREE = V((-5.6, 6.5, 4.2))
OWL_RIM = V((0.25, 1.42, GROUND_Z + 1.205))
OWL_RIM_HIGH = V((0.25, 1.42, H + 1.205))
OWL_VENT = Vector((0.0, 0.9, 7.877))                    # 12 mm above the vent cap (no intersection)
OWL_RAIL = V((-0.8, 1.47, 7.03))
FACE_DOWNHILL = facing_to((0, 0, 0), (1, 0, 0))

_P = (r"(ground|yard|pit|footing|steel_leg|brace|ring_beam|balcony|tank|outlet|supply|inlet|float|valve|vent"
      r"|bolt|overflow|gauge|tick|post|hose|slide|chute|nozzle|wheel|stream|spill|splash|drop|jet|puddle|flower"
      r"|pole|well|pump|switch|city|label|arrow|press|vac|air_in|load|tap|house|tree|gravel|water|lemon|wrench"
      r"|crane|owl|deckchair|prop_)")
_W = r"(Max|Kid1|Kid2)"
_T = (r"(deckchair|outlet|hose|slide|chute|stream|spill|splash|drop|jet|balcony|lemon|wrench|prop_|yard_ground"
      r"|ground|label|arrow|gauge|water|puddle)")


def chute_z(x):
    if x <= CHUTE_X1:
        return 3.0 - (x - CHUTE_X0) * (2.55 / (CHUTE_X1 - CHUTE_X0))
    return 0.45 - (x - CHUTE_X1) * (0.05 / (RUN_X1 - CHUTE_X1))


def _mat(name, hexc, rough=0.5, **kw):
    return toy.material(name, toy.srgb(hexc), roughness=rough, **kw)


def rod(name, p0, p1, r, mat, verts=12, parent=None):
    """A cylinder from p0 to p1 whose origin sits at p0 (so a uniform scale grows it out of p0).
    Each rod gets its own mesh, a per-name twist about its axis and a sub-mm radius change, so two rods
    in one plane never share coplanar faces (no z-fighting)."""
    p0, p1 = V(p0), V(p1)
    d = p1 - p0
    h = zlib.crc32(name.encode())
    r = r * (1.0 + 0.04 * ((h % 997) / 997.0 - 0.5))
    ob = toy.cylinder(name, r, d.length, (0, 0, 0), mat=mat, vertices=verts)
    if ob.data.users > 1:
        ob.data = ob.data.copy()
    twist = math.radians((h % 1000) / 1000.0 * 360.0 / verts)
    ob.data.transform(Matrix.Translation((0, 0, d.length / 2)) @ Matrix.Rotation(twist, 4, "Z"))
    ob.location = p0
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    if parent is not None:
        toy.parent_keep(ob, parent)
    return ob


def level_key(ob):
    """Shape key 'low' squeezes the top verts down to the bottom: value 1 = empty, 0 = full (never a scale)."""
    me = ob.data
    zs = [v.co.z for v in me.vertices]
    lo, hi = min(zs), max(zs)
    ob.shape_key_add(name="Basis", from_mix=False)
    sk = ob.shape_key_add(name="low", from_mix=False)
    for k, v in enumerate(me.vertices):
        if v.co.z > (lo + hi) / 2:
            sk.data[k].co.z = lo + 0.01
    return sk


def key_frac(sk, f, frac):
    sk.value = max(0.0, min(1.0, 1.0 - frac))
    sk.keyframe_insert("value", frame=f)


def dent_cube(name, s, mat):
    """The tank: a subdivided cube (base on z = 0) with a 'dent' shape key: the top and the UPPER walls cave in
    (the lower walls, where the remaining water sits, stay put), smooth-shaded with sharp box edges."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=s)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, s / 2))
    _smooth_sharp(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    ob.shape_key_add(name="Basis", from_mix=False)
    sk = ob.shape_key_add(name="dent", from_mix=False)
    h = s / 2
    bump = lambda u, w: max(0.0, 1 - (u / h) ** 2) * max(0.0, 1 - (w / h) ** 2)     # noqa: E731
    for k, v in enumerate(me.vertices):
        c = v.co - Vector((0, 0, h))
        wz = _ease((v.co.z - 0.38 * s) / (0.42 * s))
        d = Vector((0, 0, 0))
        if abs(abs(c.x) - h) < 1e-4:
            d.x -= math.copysign(bump(c.y, c.z) * wz, c.x)
        if abs(abs(c.y) - h) < 1e-4:
            d.y -= math.copysign(bump(c.x, c.z) * wz, c.y)
        if abs(c.z - h) < 1e-4:
            d.z -= bump(c.x, c.y)
        wr = 0.7 + 0.6 * abs(math.sin(c.x * 7.3 + c.y * 5.1 + c.z * 6.7))
        sk.data[k].co = v.co + d * 0.38 * wr
    return ob, sk


def _kids_look(k):
    return [{"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5", "hair": "#5B3A1E",
             "scale": 0.6, "ponytail": True},
            {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B", "hair": "#2B1A10",
             "scale": 0.56}][k]


HOOK_MAX = V((0.75, 0.12, FOOT))


KID_LANE = 0.72                                         # the kids ride the chute here, clear of the nozzle pipe


GROUND_MAX = Vector((1.1, 0.12, 0.025))                 # fail_ground: between tank and gauge, the hose stays clear


POLE_MAX = Vector((1.3, 0.12, 0.025))                   # fail_poles: close to the poles and the tank


OVER_MAX = Vector((2.6, 0.55, 0.025))                   # fail_overflow: right under the spill


BALC_MAX = Vector((-1.04, 0.85, 6.025))                 # mid-balcony: arms clear of rail and tank


POLE_XY = ((-0.45, 0.6), (0.45, 0.6), (-0.25, 1.2), (0.25, 1.2))   # back pair narrower: four poles read from the front


def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _child(ob, parent, loc):
    """Parent with an identity inverse and an explicit LOCAL offset (independent of stale world matrices)."""
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.location = loc


def _smooth_sharp(bm, angle=30.0):
    """Smooth-shaded panels, sharp only along the real (base mesh) box edges: dents shade cleanly."""
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if e.is_manifold and e.calc_face_angle(0.0) > math.radians(angle):
            e.smooth = False


def dent_lid(name, w, t, mat):
    """The bolted lid (centred on its origin) with a 'dent' shape key: its middle sags, the bolted rim stays."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(w, w, t), verts=bm.verts)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=9, use_grid_fill=True)
    _smooth_sharp(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    ob.shape_key_add(name="Basis", from_mix=False)
    sk = ob.shape_key_add(name="dent", from_mix=False)
    b = lambda u: max(0.0, 1.0 - (u / 0.5) ** 2)                  # noqa: E731
    for k, v in enumerate(me.vertices):
        sk.data[k].co = v.co - Vector((0, 0, 0.3 * b(v.co.x) * b(v.co.y)))
    return ob, sk


KID_LANE2 = 1.08                                        # the second chute lane (the hook: two kids at once)


HOOK_SLIDE_MAX = Vector((8.95, 0.3, 0.025))             # slide hook: right of the run-out, clear of the chute


STEEL_MAX = V((1.6, 0.14, FOOT))                        # steel_legs: beside the right footing, clear of the leg


def crumple_cube(name, s, mat, amp, seed):
    """A STATIC crumpled tank shell (base on z = 0): the dent_cube caving, stronger and creased into folds."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=s)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=9, use_grid_fill=True)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, s / 2))
    h = s / 2
    bump = lambda u, w: max(0.0, 1 - (u / h) ** 2) * max(0.0, 1 - (w / h) ** 2)     # noqa: E731
    for v in bm.verts:
        c = v.co - Vector((0, 0, h))
        wz = _ease((v.co.z - 0.38 * s) / (0.42 * s))
        d = Vector((0, 0, 0))
        if abs(abs(c.x) - h) < 1e-4:
            d.x -= math.copysign(bump(c.y, c.z) * wz, c.x)
        if abs(abs(c.y) - h) < 1e-4:
            d.y -= math.copysign(bump(c.x, c.z) * wz, c.y)
        if abs(c.z - h) < 1e-4:
            d.z -= bump(c.x, c.y)
        wr = 0.6 + 0.7 * abs(math.sin(c.x * 11.3 + c.y * 8.7 + c.z * 9.9 + seed))
        v.co = v.co + d * 0.38 * amp * wr
    _smooth_sharp(bm, angle=22.0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def bang_star(name, r_out, r_in, y0, y1, mat, spikes=9, seed=1):
    """A jagged comic 'BANG' burst (no lettering): a star prism in x-z centred on its origin."""
    rnd = random.Random(seed)
    pts = []
    for k in range(2 * spikes):
        a = math.pi * k / spikes
        r = r_out * rnd.uniform(0.8, 1.15) if k % 2 == 0 else r_in
        pts.append((r * math.cos(a), r * math.sin(a)))
    ob = st.prism(name, pts, y0, y1, mat=mat)
    st.no_shadow(ob)
    return ob


FALL2 = Vector((-2.25, 1.4, 0.14))                       # fail_poles: the tank lands deeper in the bed (closed shell)


OVER2 = Vector((1.6, 0.14, 0.025))                       # fail_overflow: at the tower's foot, under the spill


HOOK_MAX2 = Vector((9.15, 1.65, 0.025))                  # slide hook: behind the landing kid, clear of the out-jet


def crush_box(name, s, mat, cut_y, seed=2.3):
    """The tank shell for the vacuum crumple, base on z = 0, with its camera side REMOVED along the cutaway plane
    (local y = cut_y, a grid line) instead of a live section cut, and a 'crush' shape key: the walls pinch into an
    hourglass, every panel caves deep with creases and the top sags (the bolted rim edges stay)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=s)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=19, use_grid_fill=True)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, s / 2))
    front = [f for f in bm.faces if f.calc_center_median().y < cut_y]
    bmesh.ops.delete(bm, geom=front, context="FACES")
    _smooth_sharp(bm, angle=22.0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    ob.shape_key_add(name="Basis", from_mix=False)
    sk = ob.shape_key_add(name="crush", from_mix=False)
    h = s / 2
    bump = lambda u, w: max(0.0, 1 - (u / h) ** 2) * max(0.0, 1 - (w / h) ** 2)     # noqa: E731
    for k, v in enumerate(me.vertices):
        co = v.co.copy()
        c = co - Vector((0, 0, h))
        u = co.z / s
        p = 0.2 * math.sin(math.pi * 0.92 * u) * _ease(u / 0.35)
        wz = _ease((u - 0.15) / 0.5)
        fold = 0.65 + 0.7 * abs(math.sin(c.x * 9.1 + c.y * 7.3 + c.z * 8.7 + seed))
        d = Vector((0, 0, 0))
        if abs(abs(c.x) - h) < 1e-4:
            d.x -= math.copysign(bump(c.y, c.z) * wz * fold, c.x)
        if abs(c.y - h) < 1e-4:
            d.y -= bump(c.x, c.z) * wz * fold
        if abs(c.z - h) < 1e-4:
            d.z -= 0.8 * bump(c.x, c.y) * fold
        sk.data[k].co = Vector((co.x * (1 - p), co.y * (1 - p), co.z)) + d * 0.32
    sk.value = 0.0
    return ob, sk


class SBackyardWaterTowerRaiseStorySet:
    ACTIONS = ACTIONS
    QA_ALLOW = (rf"{_P}\S* x \S*{_P}|{_W}\S* x \S*{_T}|{_T}\S* x \S*{_W}")

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self.rnd = random.Random(31)
        self._pts = []
        self._n = 0
        self.m_stream = st.water_surface("wt_stream", "#8FD3FF")
        self._world()
        self._yard()
        self._pump()
        self._slide()
        self._gauge()
        self._tank()
        self._poles()
        self._steel()
        self._pipes()
        self._city()
        self._held()
        self._people()
        self._initial()
        self._colour_grade()

    # ------------------- world -------------------

    def _world(self):
        soil = st.section_rock("wt_soil", light="#A07A52", dark="#7E5D3F")
        self.soil = soil
        self.ground = st.terrain("yard_ground", -30.0, 30.0, 0.0, 60.0, lambda x, y: 0.0, floor=-80.0, res=0.5,
                                 side=soil)
        st.world_floor(0.0, around=(-30.0, 30.0, 60.0))
        st.carve(self.ground, st.box_cutter((0.0, 0.15, -1.1), (7.8, 0.7, 0.45)))      # pipe trench
        st.carve(self.ground, st.box_cutter((3.71, 0.15, -0.5), (0.26, 0.7, 1.0)))     # the outlet's rise to the lawn
        st.carve(self.ground, st.box_cutter((-3.6, 0.15, -1.95), (0.6, 0.7, 1.9)))     # well shaft
        for sx in (-1, 1):
            st.carve(self.ground, st.box_cutter((sx * 0.9, 0.125, -0.39), (0.62, 0.65, 0.92)))   # footing pits
        self.well = st.Water("well_water", -3.88, -3.32, 0.01, 0.48, bottom=-2.88, level=-2.3)
        self.pit_fill = [toy.box(f"pit_fill_{k}", (0.6, 0.43, 0.82), location=(sx * 0.9, 0.225, -0.415),
                                 mat=soil, bevel=0.0) for k, sx in enumerate((-1, 1))]
        gravel = toy.noise_material("wt_gravel", toy.srgb("#9C968C"), toy.srgb("#6E6A63"), scale=40, bump=0.3)
        self.gravel = toy.box("gravel_soak", (0.6, 0.6, 0.05), location=(1.22, 0.9, 0.005), mat=gravel, bevel=0.01)

    def _yard(self):
        self.house = bk.prop("house", 9.0, fallback=self._fb_house, name="house")
        self.house.location = (-14.5, 11.0, 0.03)          # well clear of the trees, slab above the lawn
        self.trees = []
        for k, (x, y, s) in enumerate(((-6.0, 7.0, 6.5), (9.5, 6.5, 7.0), (4.5, 11.0, 6.0))):
            t = bk.prop("tree", 6.5, fallback=self._fb_tree, name=f"tree_{k}")
            t.location = (x, y, 0.0)
            t.rotation_euler = (0, 0, R(40 * k))
            t.scale = (s / 6.5, s / 6.5, s / 6.5)
            self.trees.append(t)
        self.chair = bk.prop("deck chair", 1.0, fallback=self._fb_chair, name="deckchair")
        self.chair.location = CHAIR_AT
        self.owl = bk.prop("owl", 0.35, fallback=self._fb_owl, name="owl")
        self.owl.location = OWL_TREE
        # raised flower bed (the crash site)
        dirt = toy.noise_material("wt_bed_soil", toy.srgb("#5A3E28"), toy.srgb("#3E2A1B"), scale=18, bump=0.2)
        board = tx.wood("wt_bed_board", "#9C6B3E", "#7A4F2B", along="x")
        toy.box("flower_bed_soil", (1.4, 1.1, 0.3), location=(-2.25, 1.35, 0.1), mat=dirt, bevel=0.0)
        for k, (loc, size) in enumerate((((-2.25, 0.77, 0.12), (1.5, 0.05, 0.3)),
                                         ((-2.25, 1.93, 0.12), (1.5, 0.05, 0.3)),
                                         ((-2.98, 1.35, 0.12), (0.05, 1.11, 0.3)),
                                         ((-1.52, 1.35, 0.12), (0.05, 1.11, 0.3)))):
            toy.box(f"flower_bed_board{k}", size, location=loc, mat=board, bevel=0.005)
        stem = _mat("wt_stem", "#3F8F35", 0.6)
        cols = ("#E8384F", "#FFD23F", "#FF7AC6", "#F28C28", "#B455E0")
        rnd = random.Random(5)
        self.flowers = []
        for k in range(16):
            x, y = rnd.uniform(-2.85, -1.65), rnd.uniform(0.9, 1.8)
            hgt = rnd.uniform(0.32, 0.5)
            toy.cylinder(f"flower_stem{k}", 0.012, hgt - 0.24, (x, y, 0.24 + (hgt - 0.24) / 2), mat=stem,
                         vertices=6)
            self.flowers.append(toy.sphere(f"flower_{k}", 0.055, (x, y, hgt),
                                           mat=_mat(f"wt_petal{k % 5}", cols[k % 5], 0.5)))
        # the house wall with the garden tap
        siding = tx.planks("wt_siding", "#EDE2C8", "#DCCFAF", width=0.18, across="z", along="y", lap=True)
        toy.box("house_wall", (0.25, 1.7, 2.8), location=(-4.85, 0.95, 1.3), mat=siding, bevel=0.01)
        brass = tx.metal("wt_brass", "#C9A227", rough=0.3)
        rod("house_tap_pipe", (-4.73, 0.6, 0.85), (-4.55, 0.6, 0.85), 0.025, brass)
        rod("house_tap_spout", (-4.55, 0.6, 0.86), (-4.55, 0.6, 0.74), 0.02, brass)
        toy.cylinder("house_tap_handle", 0.05, 0.02, (-4.6, 0.6, 0.92), mat=_mat("wt_tap_red", "#C8322A", 0.4))

    def _fb_house(self):
        h = st.House("house_fb", (0, 0, 0), w=7.0, d=6.0, h=2.8)
        return h.root

    def _fb_tree(self):
        self._n += 1
        n = self._n
        root = toy.empty(f"tree_fb{n}", (0, 0, 0))
        bark = tx.wood("wt_bark", "#6B4A2E", "#4A3220", along="z")
        leaf = toy.noise_material("wt_leaves", toy.srgb("#4E9A36"), toy.srgb("#2F6B22"), scale=8, bump=0.3)
        toy.cylinder(f"tree_fb{n}_trunk", 0.18, 2.6, (0, 0, 1.3), mat=bark, parent=root)
        for k, (x, y, z, r) in enumerate(((0, 0, 3.4, 1.5), (0.8, 0.2, 2.9, 1.0), (-0.7, -0.1, 3.0, 1.1),
                                          (0.1, 0.3, 4.3, 1.0))):
            toy.sphere(f"tree_fb{n}_leaf{k}", r, (x, y, z), mat=leaf, parent=root)
        return root

    def _fb_chair(self):
        root = toy.empty("deckchair_fb", (0, 0, 0))
        wood = tx.wood("wt_chair_wood", "#B98A55", "#94683A", along="z")
        stripe = tx.cloth("wt_chair_cloth", "#2E7DD1")
        for k, sy in enumerate((-0.28, 0.28)):
            rod(f"deckchair_fb_back{k}", (0, sy, 0.0), (-0.35, sy, 0.95), 0.025, wood, parent=root)
            rod(f"deckchair_fb_leg{k}", (-0.15, sy * 0.85, 0.008), (0.55, sy * 0.85, 0.45), 0.025, wood, parent=root)
        toy.box("deckchair_fb_seat", (0.75, 0.52, 0.02), location=(0.12, 0, 0.36), rotation=(0, R(-22), 0),
                mat=stripe, parent=root, bevel=0.0)
        toy.box("deckchair_fb_sling", (0.02, 0.52, 0.7), location=(-0.22, 0, 0.66), rotation=(0, R(-20), 0),
                mat=stripe, parent=root, bevel=0.0)
        return root

    def _fb_owl(self):
        root = toy.empty("owl_fb", (0, 0, 0))
        feather = toy.noise_material("wt_owl", toy.srgb("#8A6440"), toy.srgb("#5E4128"), scale=30, bump=0.1)
        face = _mat("wt_owl_face", "#E9D3B0", 0.7)
        eye = _mat("wt_owl_eye", "#FFC21A", 0.3)
        dark = _mat("wt_owl_dark", "#1A1410", 0.3)
        toy.sphere("owl_fb_body", 0.11, (0, 0, 0.12), scale=(1, 0.9, 1.15), mat=feather, parent=root)
        toy.sphere("owl_fb_head", 0.085, (0, 0, 0.27), mat=feather, parent=root)
        toy.sphere("owl_fb_face", 0.065, (0, -0.04, 0.27), scale=(1.1, 0.5, 0.9), mat=face, parent=root)
        for sx in (-1, 1):
            toy.sphere(f"owl_fb_eye{sx}", 0.024, (sx * 0.03, -0.07, 0.285), mat=eye, parent=root)
            toy.sphere(f"owl_fb_pupil{sx}", 0.011, (sx * 0.03, -0.09, 0.285), mat=dark, parent=root)
            toy.sphere(f"owl_fb_tuft{sx}", 0.02, (sx * 0.055, 0, 0.35), scale=(0.6, 0.6, 1.6), mat=feather,
                       parent=root)
        toy.sphere("owl_fb_beak", 0.012, (0, -0.085, 0.255), scale=(1, 1, 1.5), mat=_mat("wt_beak", "#E0A030"),
                   parent=root)
        return root

    def _pump(self):
        conc = st.concrete("wt_pad", "#BDB7AA", lift=5.0, panel=5.0)
        blue = tx.paint("wt_pump_blue", "#2D62B8", rough=0.3, coat=0.5)
        dark = tx.metal("wt_pump_dark", "#3A3F45", rough=0.35)
        toy.box("pump_pad", (0.8, 0.6, 0.15), location=(-3.6, 0.35, 0.025), mat=conc, bevel=0.01)
        toy.box("pump_foot", (0.42, 0.26, 0.12), location=(-3.6, 0.35, 0.165), mat=dark, bevel=0.01)
        toy.cylinder("pump_motor", 0.15, 0.42, (-3.74, 0.35, 0.33), rotation=(0, R(90), 0), mat=blue, vertices=24)
        for k in range(5):
            toy.cylinder(f"pump_fin{k}", 0.158, 0.02, (-3.9 + 0.075 * k, 0.35, 0.33), rotation=(0, R(90), 0),
                         mat=blue, vertices=24)
        toy.cylinder("pump_head", 0.17, 0.16, (-3.44, 0.35, 0.33), rotation=(0, R(90), 0), mat=dark, vertices=24)
        rod("pump_switch_post", (-3.15, 0.62, -0.1), (-3.15, 0.62, 1.12), 0.03, dark)
        toy.box("pump_switch", (0.16, 0.08, 0.22), location=(-3.15, 0.56, 1.0), mat=tx.paint("wt_switch", "#E8E4DA"),
                bevel=0.01)
        self.lamp_mat = st.glow_mat("wt_switch_lamp", "#44FF66", 0.0)
        toy.sphere("pump_switch_lamp", 0.025, (-3.15, 0.51, 1.07), mat=self.lamp_mat)

    def _slide(self):
        yel = tx.paint("wt_slide_yellow", "#F2A71B", rough=0.22, coat=0.8)
        blue = tx.paint("wt_slide_blue", "#2E7DD1", rough=0.25, coat=0.7)
        deck = tx.planks("wt_deck", "#B88B5A", "#9A7046", width=0.14, across="x", along="y")
        post = tx.paint("wt_slide_post", "#E8E4DA", rough=0.4)
        toy.box("slide_platform", (0.75, 0.9, 0.1), location=(3.375, 0.9, 2.95), mat=deck, bevel=0.01)
        for x in (3.05, 3.7):
            for y in (0.5, 1.3):
                rod(f"slide_post_{x}_{y}", (x, y, -0.2), (x, y, 2.9), 0.05, post)
        for y in (0.6, 1.2):
            rod(f"slide_ladder_rail{y}", (2.95, y, -0.1), (2.95, y, 3.9), 0.03, post)
        for k in range(10):
            rod(f"slide_ladder_rung{k}", (2.95, 0.6, 0.3 + 0.3 * k), (2.95, 1.2, 0.3 + 0.3 * k), 0.022, post)
        for x in (3.1, 3.7):
            rod(f"slide_rail_post{x}", (x, 1.32, 3.0), (x, 1.32, 3.65), 0.025, post)
        rod("slide_rail_top", (3.0, 1.32, 3.65), (3.75, 1.32, 3.65), 0.025, post)
        lo = [(CHUTE_X0, 2.9), (CHUTE_X1, 0.35), (RUN_X1, 0.30)]
        top = [(RUN_X1, 0.40), (CHUTE_X1, 0.45), (CHUTE_X0, 3.0)]
        self.chute = st.prism("slide_chute", lo + top, 0.545, 1.255, mat=yel)
        wall = lo + [(RUN_X1, 0.62), (CHUTE_X1, 0.67), (CHUTE_X0, 3.22)]
        for k, (y0, y1) in enumerate(((0.48, 0.55), (1.25, 1.32))):
            st.prism(f"slide_wall{k}", wall, y0, y1, mat=blue)
        for x, z in ((5.2, chute_z(5.2)), (7.25, 0.3)):
            rod(f"slide_support{x}", (x, 0.9, -0.1), (x, 0.9, z - 0.12), 0.05, post)
        wtop = [(RUN_X1, 0.405), (CHUTE_X1, 0.455), (CHUTE_X0, 3.005)]
        wlo = [(CHUTE_X0, 3.03), (CHUTE_X1, 0.48), (RUN_X1, 0.43)]
        self.chute_water = st.prism("slide_water", list(reversed(wlo)) + list(reversed(wtop)), 0.56, 1.24,
                                    mat=st.flowing_water("wt_chute_water", "#5CC4E6", along="X", speed=3.0))   # foam streaks racing down
        self.slide_puddle = toy.cylinder("slide_puddle", 0.7, 0.02, (8.0, 0.9, 0.012),
                                         mat=st.water_surface("wt_puddle", "#5CC4E6"), vertices=32)
        red = _mat("wt_wheel", "#D3302A", 0.4)
        rod("slide_valve_stem", (3.77, 1.46, 3.0), (3.72, 1.45, 3.43), 0.02, tx.metal("wt_stem_m", "#8A9096"))
        self.wheel = toy.cylinder("slide_valve_wheel", 0.13, 0.03, (3.72, 1.45, 3.45), mat=red, vertices=16)
        for k in range(3):
            toy.box(f"slide_valve_spoke{k}", (0.24, 0.02, 0.02), location=(0, 0, 0), rotation=(0, 0, R(60 * k)),
                    mat=red, parent=self.wheel, bevel=0.0)

    def _gauge(self):
        white = tx.paint("wt_post_white", "#F2F0EA", rough=0.4)
        yellow = tx.paint("wt_tick", "#FFC21A", rough=0.4)
        dark = tx.metal("wt_gauge_body", "#2B2F33", rough=0.3)
        rod("gauge_post", (1.8, 0.45, -0.3), (1.8, 0.45, 7.4), 0.045, white)
        for k in range(1, 8):
            toy.box(f"gauge_tick{k}", (0.26, 0.04, 0.045), location=(1.8, 0.4, float(k)), mat=yellow, bevel=0.005)
        rod("gauge_stub", (1.8, 0.36, 1.0), (1.8, 0.43, 1.0), 0.03, dark)
        self.dial = toy.cylinder("gauge_dial", 0.2, 0.07, GAUGE, rotation=(R(90), 0, 0), mat=dark, vertices=32)
        toy.cylinder("gauge_face", 0.175, 0.01, (GAUGE.x, GAUGE.y - 0.045, GAUGE.z), rotation=(R(90), 0, 0),
                     mat=tx.paint("wt_gauge_face_paint", "#FAFAF5", rough=0.3, coat=0.6), vertices=32)
        tick = _mat("wt_gauge_ticks", "#1C1C1C", 0.5)
        redm = _mat("wt_gauge_red", "#D3242A", 0.4)
        for k in range(11):
            a = R(-120 + 24 * k)
            toy.box(f"gauge_mark{k}", (0.012, 0.006, 0.04 if k % 5 else 0.06),
                    location=(GAUGE.x + 0.14 * math.sin(a), GAUGE.y - 0.054, GAUGE.z + 0.14 * math.cos(a)),
                    rotation=(0, a, 0), mat=redm if k >= 8 else tick, bevel=0.0)
        self.needle = toy.empty("gauge_pivot", (GAUGE.x, GAUGE.y - 0.062, GAUGE.z))
        toy.box("gauge_needle", (0.02, 0.006, 0.15), location=(0, 0, 0.06), mat=redm, parent=self.needle,
                bevel=0.0)

    def _tank(self):
        steel = tx.paint("wt_tank", "#AEBBC3", rough=0.3, coat=0.4, seams=0.4, metallic=0.5)
        self.tank = toy.empty("tank", (0, TY, H))
        self.shell, self.dent = dent_cube("tank_shell", TS, steel)
        self.shell.location = (0, TY, H)
        toy.parent_keep(self.shell, self.tank)
        self.water = toy.box("tank_water", (1.14, 1.14, WATER_H), location=(0, TY, H + WATER_B + WATER_H / 2),
                             mat=st.water_surface("wt_tank_water", "#3BA7E8"), bevel=0.0)
        self.water_sk = level_key(self.water)
        toy.parent_keep(self.water, self.tank)
        self.cut = st.Cutaway("tank_cut", origin=(0, 0.72, 0), y_open=0.0, y_closed=-30.0)
        st.section_clip(self.shell, self.cut.section)
        st.section_clip(self.water, self.cut.section)
        pipe_m = tx.paint("wt_pipe", "#5E7A8C", rough=0.35, coat=0.4)
        self.pipe_m = pipe_m
        self.downpipe = rod("outlet_down", (0.35, TY, 0.0), (0.35, TY, H), 0.055, pipe_m)   # scaled to the tank
        # inlet riser inside the tank + the open spout (fail_overflow)
        self.inlet = [rod("inlet_pipe", (-0.25, TY, H), (-0.25, TY, H + 0.95), 0.04, pipe_m, parent=self.tank),
                      rod("inlet_spout", (-0.25, TY, H + 0.95), (-0.1, TY, H + 0.95), 0.04, pipe_m, parent=self.tank)]
        # float valve: pivot, arm and ball parented by explicit LOCAL offsets (the ball rides the water surface)
        brass = tx.metal("wt_float_brass", "#C9A227", rough=0.3)
        body = toy.box("float_valve_body", (0.1, 0.1, 0.1), location=(-0.12, TY, H + 0.95), mat=brass, bevel=0.01)
        toy.parent_keep(body, self.tank)
        self.pivot = toy.empty("float_pivot", (0, 0, 0))
        _child(self.pivot, self.tank, (-0.07, 0.0, 0.95))
        arm = rod("float_arm", (0, 0, 0), (0.34, 0, 0), 0.015, brass)
        _child(arm, self.pivot, (0, 0, 0))
        ball = toy.sphere("float_ball", 0.17, (0, 0, 0), mat=tx.paint("wt_ball", "#F06A1A", coat=0.6))
        _child(ball, self.pivot, (0.34, 0, 0))
        self.float_parts = [body, arm, ball]
        # overflow pipe (fix 3) down the right side of the tower
        ov = st.pipe("overflow_pipe", [(0.5, TY, H + 1.0), (0.78, TY, H + 1.0), (1.0, TY, H + 0.75),
                                       (1.1, TY, H - 0.4), (1.15, TY, 0.6), (1.2, TY, 0.06)], 0.05,
                     mat=pipe_m, wall=0.012, flange_every=2.0)
        toy.parent_keep(ov, self.tank)
        self.overflow = ov
        # airtight lid with bolts (fail 4): its middle sags with the crumple; the screened vent (fix 4)
        lidm = tx.paint("wt_lid", "#9AA8B0", rough=0.3, coat=0.4, metallic=0.5)
        self.lid, self.lid_dent = dent_lid("tank_lid", 1.26, 0.06, lidm)
        _child(self.lid, self.tank, (0.0, 0.0, 1.235))
        self.lid_dent.value = 0.0
        self.lid_dent.keyframe_insert("value", frame=1)
        self.bolts = []
        bm = tx.metal("wt_bolt", "#4A4F55")
        for k, (x, y) in enumerate(((-0.56, -0.56), (0.0, -0.56), (0.56, -0.56), (0.56, 0.0), (0.56, 0.56),
                                    (0.0, 0.56), (-0.56, 0.56), (-0.56, 0.0))):
            b = toy.cylinder(f"tank_lid_bolt{k}", 0.035, 0.05, (x, TY + y, H + 1.285), mat=bm, vertices=6)
            toy.parent_keep(b, self.tank)
            self.bolts.append(b)
        screen = tx.metal("wt_vent_screen", "#2F3438", rough=0.6)
        self.vent = [rod("vent_pipe", (0, TY, H + 1.24), (0, TY, H + 1.72), 0.1, pipe_m),
                     toy.cylinder("vent_screen", 0.12, 0.12, (0, TY, H + 1.76), mat=screen, vertices=24),
                     toy.cylinder("vent_cap", 0.22, 0.06, (0, TY, H + 1.835), mat=lidm, vertices=24)]
        for ob in self.vent:
            toy.parent_keep(ob, self.tank)
        cable = rod("crane_cable", (0, TY, H + 1.2), (0, TY, H + 16.0), 0.015, tx.metal("wt_cable", "#3A3A3A"))
        toy.parent_keep(cable, self.tank)
        self.cable = cable

    def _poles(self):
        """Four 6 m poles, each a lower segment, a knee pivot and an upper segment, parented by LOCAL offsets.
        Every cap sits at its own height and the upper segment is thinner (nested at the knee): no coplanar faces."""
        wood = tx.wood("wt_pole", "#A27648", "#74512E", along="z")
        self.poles = []
        self.pole_xy = POLE_XY
        for k, (px, py) in enumerate(POLE_XY):
            root = toy.empty(f"pole_{k}", (px, py, 0.0))
            zb, zt = -0.05 - 0.007 * k, 3.0 + 0.006 * (k + 1)
            low = rod(f"pole_{k}_low", (0, 0, zb), (0, 0, zt), 0.05, wood)
            _child(low, root, (0, 0, zb))
            knee = toy.empty(f"pole_{k}_knee", (0, 0, 0))
            _child(knee, root, (0, 0, 3.0))
            ua, ub = -0.03 - 0.004 * k, H - 3.0 - 0.012 - 0.006 * k
            up = rod(f"pole_{k}_up", (0, 0, 0), (0, 0, ub - ua), 0.042, wood)
            _child(up, knee, (0, 0, ua))
            self.poles.append((root, knee))

    def _steel(self):
        conc = st.concrete("wt_footing", "#C2BCB0", lift=0.3, panel=0.6)
        paint = tx.paint("wt_steel", "#4E6E80", rough=0.35, coat=0.4, metallic=0.4)
        grate = tx.metal("wt_grate", "#5A6066", rough=0.5)
        self.footings = []
        for sx in (-1, 1):
            self.footings.append(toy.box(f"footing_f{sx + 1}", (0.6, 0.43, 0.86), location=(sx * 0.9, 0.225, -0.4),
                                         mat=conc, bevel=0.01))
            self.footings.append(toy.box(f"footing_b{sx + 1}", (0.6, 0.6, 0.86), location=(sx * 0.9, 1.65, -0.4),
                                         mat=conc, bevel=0.01))
        base = {(sx, sy): V((sx * 0.9, TY + sy * 0.75, 0.03)) for sx in (-1, 1) for sy in (-1, 1)}
        top = {(sx, sy): V((sx * 0.62, TY + sy * 0.6, 5.9)) for sx in (-1, 1) for sy in (-1, 1)}
        at = lambda c, z: base[c].lerp(top[c], (z - 0.03) / 5.87)      # noqa: E731
        self.legs = [rod(f"steel_leg_{c[0] + 1}{c[1] + 1}", base[c], top[c], 0.065, paint) for c in base]
        faces = [((-1, -1), (1, -1)), ((-1, 1), (1, 1)), ((-1, -1), (-1, 1)), ((1, -1), (1, 1))]
        self.rings = []
        for k, (c0, c1) in enumerate(faces):
            self.rings.append(rod(f"ring_beam{k}", top[c0] + V((0, 0, 0.04)), top[c1] + V((0, 0, 0.04)), 0.045,
                                  paint))
        levels = [0.25, 2.1, 4.0, 5.8]
        self.braces = []                    # [(level index, obj)]
        for fi, (c0, c1) in enumerate(faces):
            for li in range(3):
                za, zb = levels[li], levels[li + 1]
                self.braces.append((li, rod(f"brace_{fi}_{li}a", at(c0, za), at(c1, zb), 0.025, paint, verts=8)))
                self.braces.append((li, rod(f"brace_{fi}_{li}b", at(c1, za), at(c0, zb), 0.025, paint, verts=8)))
                if li > 0:
                    self.braces.append((li, rod(f"brace_{fi}_{li}h", at(c0, za), at(c1, za), 0.022, paint,
                                                verts=8)))
        # the balcony on the left, with its railing and ladder
        self.balcony = [toy.box("balcony_deck", (0.84, 1.2, 0.04), location=(-1.08, TY, 5.975), mat=grate,
                                bevel=0.005)]
        for k, y in enumerate((0.35, 1.45)):
            self.balcony.append(rod(f"balcony_post{k}", (-1.47, y, 5.995), (-1.47, y, 7.0), 0.025, paint))
            self.balcony.append(rod(f"balcony_strut{k}", (-0.7, y, 5.3), (-1.45, y, 5.955), 0.025, paint))
        self.balcony.append(rod("balcony_rail", (-1.47, 0.35, 7.0), (-1.47, 1.45, 7.0), 0.025, paint))
        self.balcony.append(rod("balcony_back", (-1.47, 1.47, 7.0), (-0.68, 1.47, 7.0), 0.025, paint))
        for k, x in enumerate((-1.15, -1.45)):
            self.balcony.append(rod(f"balcony_ladder{k}", (x, 1.62, 0.0), (x, 1.62, 6.9), 0.025, paint))
        for k in range(17):
            self.balcony.append(rod(f"balcony_ladder_rung{k}", (-1.15, 1.62, 0.3 + 0.35 * k),
                                    (-1.45, 1.62, 0.3 + 0.35 * k), 0.018, paint, verts=8))

    def _pipes(self):
        pm = self.pipe_m
        # the whole run reads in the cutaway: along the trench, up the section shaft, out through a cover plate,
        # along the lawn under the slide deck and up the riser to the nozzle (it used to turn back into the soil
        # at the trench end and read as a cut-off pipe)
        self.outlet = st.pipe("outlet_main", [(0.35, TY, 0.05), (0.35, 0.85, -0.5), (0.45, 0.4, -1.0),
                                              (0.8, 0.2, -1.1), (3.45, 0.2, -1.1), (3.68, 0.2, -0.88),
                                              (3.71, 0.2, -0.1), (3.8, 0.32, 0.1), (3.92, 0.62, 0.11),
                                              (3.92, 1.42, 0.11), (3.84, 1.5, 0.32), (3.78, 1.5, 0.6),
                                              (3.78, 1.5, 2.85), (3.8, 1.25, 3.15),
                                              (NOZZLE.x, NOZZLE.y, NOZZLE.z)], 0.06, mat=pm, wall=0.012,
                              flange_every=1.6)
        self.outlet_plate = toy.box("outlet_cover_plate", (0.34, 0.5, 0.04), location=(3.71, 0.26, 0.016),
                                    mat=st.concrete("wt_plate", "#BDB7AA", lift=5.0, panel=5.0), bevel=0.008)
        # until the pipe is laid the trench is filled with soil (an empty dark slot read as a missing pipe)
        self.trench_fill = [toy.box("trench_fill_R", (3.9, 0.5, 0.45), location=(1.95, 0.25, -1.1), mat=self.soil,
                                    bevel=0.0),
                            toy.box("trench_fill_shaft", (0.26, 0.5, 1.0), location=(3.71, 0.25, -0.5),
                                    mat=self.soil, bevel=0.0)]
        self.trench_fill_L = [toy.box("trench_fill_L", (3.9, 0.5, 0.45), location=(-1.95, 0.25, -1.1),
                                      mat=self.soil, bevel=0.0)]
        self.tube = rod("gauge_tube", (0.4, TY, 0.95), (1.76, 0.38, 1.0), 0.018, tx.metal("wt_copper", "#C46A36"))
        self.supply = [st.pipe("supply_drop", [(-3.6, 0.2, -2.7), (-3.6, 0.2, -1.2), (-3.6, 0.2, 0.12)], 0.05,
                               mat=pm, wall=0.012, flange_every=1.5),
                       st.pipe("supply_main", [(-3.27, 0.2, 0.3), (-3.15, 0.2, -0.4), (-3.0, 0.2, -1.1),
                                               (-0.5, 0.2, -1.1), (-0.3, 0.6, -0.95), (-0.25, TY, -0.5),
                                               (-0.25, TY, 2.0), (-0.25, TY, H - 0.01)], 0.05, mat=pm, wall=0.012,
                               flange_every=1.6)]
        # failure 1: a garden hose from the tank on the grass, up the slide ladder (clear section) to the nozzle
        green = tx.rubber("wt_hose", "#2F8F3A")
        self.hose = [st.pipe("hose_ground", [(0.62, 0.7, 0.12), (1.3, 0.7, 0.062), (2.3, 0.6, 0.062),
                                             (2.8, 0.45, 0.1), (2.85, 0.45, 0.16)], 0.035, mat=green, wall=0.008,
                             flange_every=99.0),
                     st.pipe("hose_top", [(2.85, 0.45, 3.08), (2.88, 0.5, 3.3), (3.2, 0.7, 3.32),
                                          (NOZZLE.x, NOZZLE.y, NOZZLE.z)], 0.035, mat=green, wall=0.008,
                             flange_every=99.0)]
        clear = toy.material("wt_clear_hose", toy.srgb("#DDEFF5"), roughness=0.08, transmission=0.92)
        self.hose_up = toy.cylinder("hose_up", 0.045, 2.96, (2.85, 0.45, 1.62), mat=clear, vertices=16)
        self.hose_water = toy.cylinder("hose_water", 0.03, 2.94, (2.85, 0.45, 1.62),
                                       mat=st.water_surface("wt_hose_water", "#2E8FE0"), vertices=12)
        self.hose_sk = level_key(self.hose_water)
        self.hose += [self.hose_up, self.hose_water]
        glow = st.glow_mat("wt_level_line", "#46C2FF", 2.2)
        self.dashes = [toy.box(f"water_line{k}", (0.18, 0.02, 0.035), location=(-0.6 + 0.3 * k, 0.2, 1.17),
                               mat=glow, bevel=0.0) for k in range(12)]
        self.bed_puddle = toy.cylinder("puddle_bed", 0.75, 0.02, (-2.2, 1.3, 0.262),
                                       mat=st.water_surface("wt_bed_puddle", "#5CC4E6"), vertices=32)

    def _city(self):
        self.city = []
        wood = tx.planks("wt_table", "#B98A55", "#94683A", width=0.12, across="x", along="y")
        self.city.append(toy.box("city_table_top", (1.15, 0.5, 0.05), location=(-2.45, 0.45, 0.725), mat=wood,
                                 bevel=0.01))
        for kx, x in enumerate((-2.95, -1.95)):
            for ky, y in enumerate((0.25, 0.65)):
                self.city.append(rod(f"city_table_leg{kx}{ky}", (x, y, 0.0), (x, y, 0.7), 0.025, wood))
        self.city.append(toy.box("city_model_sky", (1.1, 0.02, 1.0), location=(-2.45, 0.68, 1.265),
                                 mat=tx.paint("wt_sky_board", "#9FD0F0", rough=0.6), bevel=0.0))
        bricks = [tx.tiles("wt_nyc_brick", "#9C5B43", grout="#E8D9B8", size=0.045, rough=0.6, coat=0.1),
                  tx.tiles("wt_nyc_stone", "#B7A68A", grout="#F2EAD5", size=0.045, rough=0.6, coat=0.1)]
        barrel = tx.planks("wt_rooftank", "#8A5A32", "#6B4424", width=0.015, across="x", along="z")
        roof = _mat("wt_rooftank_roof", "#4A3828", 0.7)
        rnd = random.Random(9)
        x = -2.95
        for k, (w, h) in enumerate(((0.18, 0.55), (0.22, 0.85), (0.16, 0.45), (0.2, 0.7), (0.19, 0.6))):
            cx = x + w / 2
            self.city.append(toy.box(f"city_model_bldg{k}", (w, 0.26, h), location=(cx, 0.45, 0.755 + h / 2),
                                     mat=bricks[k % 2], bevel=0.003))
            tz = 0.755 + h + 0.035
            for j, lx in enumerate((-0.03, 0.03)):
                self.city.append(rod(f"city_model_stilt{k}{j}", (cx + lx, 0.45, 0.755 + h), (cx + lx, 0.45, tz),
                                     0.006, roof, verts=6))
            self.city.append(toy.cylinder(f"city_model_tank{k}", 0.045, 0.075, (cx, 0.45, tz + 0.04), mat=barrel,
                                          vertices=16))
            bpy.ops.mesh.primitive_cone_add(radius1=0.05, depth=0.04, vertices=16, location=(cx, 0.45, tz + 0.1))
            cone = bpy.context.active_object
            cone.name = f"city_model_tankroof{k}"
            cone.data.materials.append(roof)
            self.city.append(cone)
            x += w + rnd.uniform(0.0, 0.01)
        self.city.append(toy.box("city_model_6th", (1.05, 0.015, 0.02), location=(-2.45, 0.31, 0.755 + 0.33),
                                 mat=st.glow_mat("wt_sixth", "#3FB8FF", 3.0), bevel=0.0))

    def _held(self):
        steel = tx.metal("wt_wrench", "#9AA3AA", rough=0.3)
        self.wrench = toy.empty("prop_wrench", (0, 0, 0))
        toy.box("prop_wrench_handle", (0.03, 0.02, 0.24), location=(0, 0, -0.1), mat=steel, parent=self.wrench)
        toy.box("prop_wrench_head", (0.08, 0.025, 0.05), location=(0, 0, -0.23), mat=steel, parent=self.wrench)
        self.lemon = toy.empty("prop_lemonade", (0, 0, 0))
        toy.cylinder("prop_lemonade_glass", 0.045, 0.13, (0, 0, -0.06),
                     mat=toy.material("wt_glass", toy.srgb("#F4F0C0"), roughness=0.1, transmission=0.6),
                     parent=self.lemon)
        toy.sphere("prop_lemonade_slice", 0.025, (0.04, 0, 0.0), scale=(1, 0.3, 1), mat=_mat("wt_lemon", "#F2D42A"),
                   parent=self.lemon)
        self.float_prop = toy.empty("prop_float", (0, 0, 0))
        toy.sphere("prop_float_ball", 0.14, (0, 0, 0.12), mat=tx.paint("wt_ball2", "#F06A1A", coat=0.6),
                   parent=self.float_prop)
        toy.cylinder("prop_float_arm", 0.015, 0.3, (0, 0, -0.1), mat=tx.metal("wt_float_brass2", "#C9A227"),
                     parent=self.float_prop)
        self.vent_prop = toy.empty("prop_vent", (0, 0, 0))
        toy.cylinder("prop_vent_pipe", 0.1, 0.45, (0, 0, -0.05), mat=self.pipe_m, parent=self.vent_prop)
        toy.cylinder("prop_vent_cap", 0.2, 0.05, (0, 0, 0.2), mat=tx.paint("wt_lid2", "#9AA8B0"),
                     parent=self.vent_prop)

    def _people(self):
        self.max = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
        self.max.place(1, MAX_AT, 0)
        self.max.key("hips", 1, loc=(0, 0, 0.56))
        self.max.auto_blink(1, self.total + 900, seed=11)
        self.max.act("idle", 1, self.total + 900)
        for ob in (self.wrench, self.lemon, self.float_prop, self.vent_prop):
            self.max.hold(ob, "R")
            ob.location = (0.0, 0.0, -0.05)
            toy.hide_tree(ob, 1, True)
        self.kids = []
        for k in range(2):
            kid = Character(f"Kid{k + 1}", _kids_look(k))
            kid.place(1, KID_PLAT[k], 0)
            kid.key("hips", 1, loc=(0, 0, 0.56))
            kid.auto_blink(1, self.total + 900, seed=k + 3)
            kid.act("idle", 1, self.total + 900)
            toy.hide_tree(kid.root, 1, True)
            self.kids.append(kid)

    def _initial(self):
        for ob in ([self.downpipe, self.tube, self.overflow, self.lid, self.cable, self.chute_water,
                    self.slide_puddle, self.bed_puddle, self.outlet, self.outlet_plate] + self.float_parts + self.inlet + self.bolts
                   + self.vent + self.supply + self.dashes + self.footings + self.legs + self.rings + self.balcony
                   + [b for _, b in self.braces] + self.city + [r for r, _ in self.poles]):
            toy.hide_tree(ob, 1, True)
        self.tank.location = (0, TY, GROUND_Z)
        self.tank.keyframe_insert("location", frame=1)
        self.tank.rotation_euler = (0, 0, 0)
        self.tank.keyframe_insert("rotation_euler", frame=1)
        for root, knee in self.poles:
            root.location.z = GROUND_Z - H
            root.keyframe_insert("location", frame=1)
            root.keyframe_insert("rotation_euler", frame=1)
            knee.keyframe_insert("rotation_euler", frame=1)
        self.shell.keyframe_insert("scale", frame=1)
        self.dent.value = 0.0
        self.dent.keyframe_insert("value", frame=1)
        self.level(1, 0.98)
        key_frac(self.hose_sk, 1, 0.0)
        self.gauge(1, 0.0)
        toy.key_hold(self.cut.section, "location", 1)
        self.cut._at(2, self.cut.y_open)
        st.key_glow(self.lamp_mat, 1, 0.0)

    def _colour_grade(self):
        try:
            st.key_sky(self.scene, 1, 40)
        except Exception:
            pass
        if self.sun is not None and getattr(self.sun, "data", None) is not None:
            self.sun.data.color = (1.0, 0.9, 0.74)
        try:
            vs = self.scene.view_settings
            if vs.view_transform == "AgX":
                vs.look = "AgX - Punchy"
        except Exception:
            pass

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
        self.rig.build()

    # ------------------- helpers -------------------

    def show(self, objs, f, visible=True):
        for ob in (objs if isinstance(objs, (list, tuple)) else [objs]):
            toy.hide_tree(ob, f, not visible)

    def pop_in(self, ob, f, frames=8):
        ob.scale = (0.001, 0.001, 0.001)
        ob.keyframe_insert("scale", frame=f)
        ob.scale = (1, 1, 1)
        ob.keyframe_insert("scale", frame=f + frames)
        toy.hide_tree(ob, f, False)

    def jump(self, ob, f, loc=None, rot=None):
        """Move instantly at f (constant hold from f-1): a cut-hidden reset."""
        for path, val in (("location", loc), ("rotation_euler", rot)):
            if val is None:
                continue
            toy.key_hold(ob, path, f - 1)
            setattr(ob, path, val)
            ob.keyframe_insert(path, frame=f)
            toy.set_interpolation(ob, path, [f - 1], "CONSTANT")

    def pipe_to_tank(self, f, z):
        """The outlet downpipe stands on the ground and ends at the tank's bottom at height z (a fixed 6 m rod
        riding on the tank poked down through the soil while the tank was being raised)."""
        self.downpipe.scale = (1.0, 1.0, max(0.001, z / H))
        self.downpipe.keyframe_insert("scale", frame=f)

    def key_loc(self, ob, f, loc):
        ob.location = loc
        ob.keyframe_insert("location", frame=f)

    def key_rot(self, ob, f, rot):
        ob.rotation_euler = rot
        ob.keyframe_insert("rotation_euler", frame=f)

    def level(self, f, frac):
        """Tank water level (0..1 of the inside height) and the float arm that rides on it."""
        key_frac(self.water_sk, f, frac)
        wt = WATER_B + WATER_H * frac
        s = max(0.0, min(0.95, (0.95 - wt - 0.02) / 0.34))
        self.pivot.rotation_euler = (0, math.asin(s), 0)
        self.pivot.keyframe_insert("rotation_euler", frame=f)

    def level_ramp(self, f0, f1, a, b, step=4):
        for f in sorted(set(list(range(f0, f1, step)) + [f1])):
            t = st.smooth((f - f0) / max(1, f1 - f0))
            self.level(f, a + (b - a) * t)

    def gauge(self, f, bar):
        self.needle.rotation_euler = (0, R(-120 + 240 * max(0.0, min(1.0, bar))), 0)
        self.needle.keyframe_insert("rotation_euler", frame=f)

    @staticmethod
    def bar_at(base_z, frac):
        return max(0.0, 0.1 * (base_z + WATER_B + WATER_H * frac - GAUGE.z))

    def label(self, text, loc, f0, f1, size=0.34):
        root = st.label(text, tuple(loc), f0, f1, size=size, tilt=-3)
        w = 0.62 * size * len(text) / 2 + 0.08
        self._pts += [(loc[0] - w, loc[1], loc[2] + size * 0.7), (loc[0] + w, loc[1], loc[2] - size * 0.7)]
        return root

    def at(self, f, spot, face=0.0):
        self.max.cut_place(f, spot, face)

    def close(self, f0, f1, offset=(0.3, 0, 0), frac=0.42, swing=12.0, height=1.9):
        st.close_on(self.rig, f0, f1, self.max, frac=frac, angle=-90.0, swing=swing, rise=0.22, lens=32,
                    look=0.62, offset=offset, cut=True, fstop=5.6, height=height)

    def frame_on(self, f0, f1, pts, margin=0.1, with_max=True, angle=-90.0):
        things = list(pts) + self._pts + ([self.max] if with_max else [])
        st.frame_all(self.rig, f0, f1, things, angle=angle, cut=True, margin=margin, lens=28, rise=0.16, swing=6.0)

    @staticmethod
    def tank_pts(z):
        return [(-0.62, 0.3, z), (0.62, 0.3, z + 1.22)]

    def key_dense(self, ch, joint, f0, f1, rot_fn, step=8):
        for f in sorted(set(list(range(f0, f1, step)) + [f1])):
            ch.key(joint, f, rot_deg=rot_fn(f))

    def shrug(self, f0, f1, amp=62):
        m = self.max
        for f, a in ((f0, 0), (f0 + 5, amp), (f1 - 4, amp + 4), (f1, 0)):
            m.key("shoulderL", f, rot_deg=(-15 if a else 0, -a, 0))
            m.key("shoulderR", f, rot_deg=(-15 if a else 0, a, 0))
        m.key("head", f0 + 5, rot_deg=(-4, 0, 14))
        m.key("head", f1, rot_deg=(0, 0, 0))
        m.brows(f0 + 5, 0.9)
        m.brows(f1, 0.0)
        events.add(f0 + 5, "boing", gain=0.3)

    def arms_v(self, ch, f0, f1):
        for f, a in ((f0, 0), (f0 + 5, 150), (f1 - 4, 158), (f1, 0)):
            ch.key("shoulderL", f, rot_deg=(0, -a, 0))
            ch.key("shoulderR", f, rot_deg=(0, a, 0))
        ch.smile(f0 + 5, big=True)

    def point_side(self, f0, f1, hand="R", up=80):
        sign = 1 if hand == "R" else -1
        self.key_dense(self.max, f"shoulder{hand}", f0, f1,
                       lambda f: (0, 0, 0) if f < f0 + 6 else (0, sign * up, 0))
        self.max.key(f"shoulder{hand}", f1 + 6, rot_deg=(0, 0, 0))

    def gasp(self, f0, f1):
        m = self.max
        m.key("mouth", f0, scale=(0.7, 0.6, 1.0))
        m.key("mouth", f0 + 4, scale=(1.2, 0.6, 2.6))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f0 + 4, 1.0)
        m.brows(f1, 0.0)

    def hold(self, ob, f0, f1):
        toy.hide_tree(ob, f0, False)
        toy.hide_tree(ob, f1 + 1, True)

    def stream(self, name, p0, v, f0, f1, z_stop, radius=0.06, rise=6, drops=18):
        """A continuous ballistic water stream (curve) from p0, with a few drops riding along it."""
        p, v = V(p0), V(v)
        pts = [p.copy()]
        dt = 1.0 / 90.0
        for _ in range(600):
            v.z -= 9.81 * dt
            p = p + v * dt
            pts.append(p.copy())
            if p.z <= z_stop(p.x):
                break
        cu = bpy.data.curves.new(f"{name}_core", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = radius
        cu.bevel_resolution = 3
        cu.use_fill_caps = True
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for k, q in enumerate(pts):
            sp.points[k].co = (q.x, q.y, q.z, 1.0)
        ob = bpy.data.objects.new(f"{name}_core", cu)
        bpy.context.scene.collection.objects.link(ob)
        cu.materials.append(self.m_stream)
        toy.hide_tree(ob, 1, True)
        toy.hide_tree(ob, f0, False)
        toy.hide_tree(ob, f1 + 11, True)
        for f, end, start in ((f0, 0.0, 0.0), (f0 + rise, 1.0, 0.0), (f1, 1.0, 0.0), (f1 + 10, 1.0, 1.0)):
            cu.bevel_factor_end, cu.bevel_factor_start = end, start
            cu.keyframe_insert("bevel_factor_end", frame=f)
            cu.keyframe_insert("bevel_factor_start", frame=f)
        if drops:
            Spray(f"{name}_drops", self.m_stream, count=drops, radius=radius * 0.6, seed=len(name)).run(
                f0 + rise, f1, tuple(pts[0]), tuple(pts[-1]), spread=0.12, arc=0.08, period=12)
        return ob

    def gush(self, tag, f0, f1, strong=True):
        """Water from the nozzle down the chute (stream + water sheet + drops), a puddle at the end."""
        speed = 2.2 if strong else 0.9
        self.stream(f"slide_stream_{tag}", NOZZLE + V((0.05, 0, 0)), (speed, 0, -0.2), f0, f1,
                    lambda x: chute_z(x) + 0.03, radius=0.045 if strong else 0.03, drops=6)
        if strong:
            self.show(self.chute_water, f0 + 4)
            self.show(self.chute_water, f1 + 8, False)
            self.show(self.slide_puddle, f0 + 10)
            Spray(f"slide_run_{tag}", self.m_stream, count=14, radius=0.02, seed=f0 % 97).run(
                f0 + 4, f1, (4.0, 0.9, 2.85), (RUN_X1 + 0.2, 0.9, 0.42), spread=0.3, arc=0.04, period=26)
            Puffs(f"slide_splash_{tag}", "#F2FAFF", count=10, size=0.07, seed=f0 % 13).emit(
                range(f0 + 12, f1, 5), lambda f: (RUN_X1 + 0.15, 0.9, 0.42), rise=0.4, life=16, drift=0.3)
        events.add(f0, "water_rush", duration=f1 - f0, gain=0.5 if strong else 0.25)

    def splash(self, tag, f, at, big=False):
        Puffs(f"splash_{tag}", "#F2FAFF", count=40 if big else 14, size=0.4 if big else 0.2, seed=len(tag)).emit(
            range(f, f + (14 if big else 8)), lambda _f: at, rise=1.6 if big else 0.7, life=24, drift=0.9)
        if big:
            for k, d in enumerate(((-0.5, 0, 1), (0.6, 0, 1), (0.0, -0.4, 1), (0.2, 0.3, 1))):
                st.Jet(f"splash_{tag}_jet{k}", at, d, speed=4.2 + 0.4 * k, radius=0.07, drops=50,
                       drop_size=0.06, spread=0.5, seed=k + 3).erupt(f, f + 14, rise=3)
        events.add(f, "splash", gain=1.0 if big else 0.6)

    def owl_fly(self, f0, f1, to, hop=0.8):
        a = V(toy.value_at(self.owl, "location", f0))
        b = V(to)
        toy.key_hold(self.owl, "location", f0)
        self.key_loc(self.owl, (f0 + f1) // 2, (a + b) / 2 + V((0, 0, hop)))
        self.key_loc(self.owl, f1, b)

    def kids_on(self, f, visible=True):
        for kid in self.kids:
            toy.hide_tree(kid.root, f, not visible)

    def slide_kid(self, kid, f0, f1, end_x):
        """Step off the platform onto the chute in the lane beside the nozzle pipe, whoosh down, stop on the run-out."""
        lift = 0.12
        y = KID_LANE
        x0 = CHUTE_X0 + 0.45
        top = V((x0, y, chute_z(x0) + lift))
        bot = V((CHUTE_X1, y, chute_z(CHUTE_X1) + lift))
        end = V((end_x, y, chute_z(end_x) + lift))
        kid.turn(f0, FACE_DOWNHILL, frames=4)
        kid.move(f0, f0 + 6, top)
        kid.sit(f0, f1 + 14, frames=6)
        t_bot = f0 + 6 + int((f1 - f0 - 6) * 0.72)
        kid.move(f0 + 6, t_bot, bot)
        kid.move(t_bot, f1, end)
        kid.key("mouth", f0 + 6, scale=(1.0, 0.6, 1.6))
        kid.key("mouth", f1 + 10, scale=(0.7, 0.6, 1.0))
        events.add(f0 + 6, "whoosh", gain=0.4)
        Puffs(f"kid_splash_{kid.root.name}_{f1}", "#F2FAFF", count=10, size=0.07, seed=f1 % 11).emit(
            range(f1 - 4, f1 + 6), lambda f: (end_x + 0.2, y, 0.5), rise=0.8, life=18, drift=0.5)
        events.add(f1, "splash", gain=0.7)

    # ------------------- the ladder -------------------

    def a_fail_ground(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, GROUND_MAX, 0.0)
        self.jump(self.owl, b, loc=OWL_RIM)
        self.owl_fly(fr(0.22), fr(0.34), OWL_TREE, hop=1.5)
        key_frac(self.hose_sk, fr(0.24), 0.0)
        key_frac(self.hose_sk, fr(0.56), 0.357)
        self.gauge(b, 0.0)
        self.gauge(fr(0.56), 0.02)
        for k, d in enumerate(self.dashes):
            if abs(d.location.x - GROUND_MAX.x) < 0.4:       # the level line stops short of Max
                continue
            self.show(d, fr(0.3) + k)
            self.show(d, e + 1, False)
        self.label("WATER LEVEL", (-0.15, 0.1, 1.6), fr(0.32), e, size=0.3)
        events.add(fr(0.24), "pour", duration=int(L * 0.3), gain=0.3)
        m.act("pick_up", b + 2, fr(0.26))
        m.look_at(fr(0.32), (3.6, 0.9, 3.2), hold=int(L * 0.4))
        m.act("talk", fr(0.28), fr(0.8))
        self.shrug(fr(0.84), e)
        # tank, hose, gauge and Max in every frame: the change, then the cause and its result
        pts = self.tank_pts(0.0) + [(2.85, 0.45, 3.35), (GAUGE.x, 0.3, 0.7), (NOZZLE.x, 0.9, 3.2)]
        self.frame_on(b, fr(0.4), pts, angle=-82.0)
        self.frame_on(fr(0.4), e, pts)

    def a_raise_tank(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, MAX_AT, 0.0)
        self.show(self.hose, b, False)
        self.level(b, 0.5)
        # the crane lifts the tank from the first frames, one metre at a time, the poles rising under it
        f0, f1 = b + 4, fr(0.72)
        self.show(self.cable, b, False)        # no crane in the shot: its cable read as a stray black line
        self.show([self.downpipe], f0)
        self.show([self.outlet, self.outlet_plate], fr(0.3))
        self.show(self.trench_fill, fr(0.3), False)
        self.show(self.tube, f1)
        toy.key_hold(self.tank, "location", f0)
        self.pipe_to_tank(f0, GROUND_Z)
        for root, _ in self.poles:
            self.show(root, f0)
            toy.key_hold(root, "location", f0)
        marks = []
        for k in range(1, 7):
            fk = f0 + (f1 - f0) * k // 6
            z = GROUND_Z + (H - GROUND_Z) * k / 6.0
            self.key_loc(self.tank, fk, (0, TY, z))
            self.pipe_to_tank(fk, z)
            for root, _ in self.poles:
                self.key_loc(root, fk, (root.location.x, root.location.y, z - H))
            marks.append(fk)
        events.add(f0, "creak", duration=f1 - f0, gain=0.4)
        for f in list(range(b, f1, 4)) + [f1, e]:
            z = toy.value_at(self.tank, "location", f)[2]
            self.gauge(f, self.bar_at(z, 0.5))
        # the pressure arrow at the gauge grows with every metre of height
        starts = [f0] + marks
        for k in range(7):
            a0 = starts[k]
            a1 = starts[k + 1] - 1 if k < 6 else e
            st.arrow(f"press_arrow{k}", (GAUGE.x, 0.2, 1.26), (0, 0, 0.12 + 0.215 * k), a0, a1, color="#FF8A1A",
                     width=0.13)
        self.label("0.1 BAR / METRE", (2.9, 0.1, 4.6), fr(0.12), f1 - 1, size=0.28)
        self.label("6 m = 0.6 BAR", (2.7, 0.1, 5.0), f1, e, size=0.34)
        self.gush("raise_weak", fr(0.48), fr(0.64), strong=False)
        self.gush_big("raise", fr(0.62), e + 2)
        m.act("talk", b + 2, fr(0.74))          # upright (a leaning 'push' hid his face from the high wide camera)
        m.look_at(fr(0.3), (0, TY, 4.0), hold=int(L * 0.4))
        self.arms_v(m, fr(0.8), e)
        # ONE continuous wide shot: the whole 6 m rise, the gauge and its arrow, the slide and Max
        self.frame_on(b, e, [(-0.62, 0.3, 0.0), (0.62, 0.3, H + 1.22), (GAUGE.x, 0.3, 0.75),
                             (GAUGE.x, 0.2, 2.7), (NOZZLE.x + 0.4, 0.9, 3.2)])

    def a_fail_poles(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, POLE_MAX, 0.0)
        self.level(b, 0.5)
        self.level_ramp(b + 2, fr(0.28), 0.5, 1.0)
        events.add(b + 2, "pour", duration=int(L * 0.26), gain=0.35)
        self.gauge(b + 2, self.bar_at(H, 0.5))
        self.gauge(fr(0.28), self.bar_at(H, 1.0))
        self.label("1 TONNE", (-1.6, 0.1, H + 0.55), fr(0.1), e, size=0.4)
        # the owl perches on the rim while it fills, flaps off as the poles creak, glides away past the tower
        self.jump(self.owl, b, loc=OWL_RIM_HIGH)
        self.owl_fly(fr(0.36), fr(0.56), (-1.3, 0.7, 7.3), hop=0.4)
        self.owl_fly(fr(0.56), fr(0.84), (-2.6, 1.2, 5.6), hop=0.3)
        self.owl_fly(fr(0.84), e, OWL_TREE + V((0.4, 0, 0.6)), hop=0.5)
        bow0, crack, land = fr(0.32), fr(0.68), fr(0.8)
        # the four poles bow one after the other (growing C-bows with a sway) for a long time, tank still on top
        rnd = random.Random(12)
        for k in range(4):
            ph = rnd.uniform(0, 3)
            s_k = bow0 + int(L * 0.04 * k)
            self.poles_bow(b, k, 0.0)
            self.poles_bow(s_k, k, 0.0)
            for f in range(s_k + 4, crack, 4):
                t = (f - bow0) / max(1, crack - bow0)
                self.poles_bow(f, k, -(2.0 + 12.0 * t) - 3.0 * t * math.sin(f * 0.45 + ph))
            self.poles_bow(crack, k, -16.0)
        # ... they snap at the knee and fold over WITH the falling tank, ending folded onto the wreck in the bed
        rnd2 = random.Random(5)
        mid = (crack + land) // 2
        for k, (root, knee) in enumerate(self.poles):
            j = rnd2.uniform(-4.0, 4.0)
            self.key_rot(root, mid, (0, R(-20 + j), 0))
            self.key_rot(knee, mid, (0, R(-55 - j), 0))
            self.key_rot(root, land + 2 + k, (0, R(-31 + j), 0))
            self.key_rot(knee, land + 2 + k, (0, R(-118 - j), 0))
            self.key_rot(knee, land + 6 + k, (0, R(-112 - j), 0))
            self.key_rot(knee, land + 10 + k, (0, R(-118 - j), 0))
            events.add(land + 2 + k, "stone_thud", gain=0.3)
        events.add(bow0, "creak", duration=crack - bow0, gain=0.8)
        events.add(crack, "crack", gain=1.0)
        # the tank sags with the bowing poles, tips off and falls into the flower bed
        toy.key_hold(self.tank, "location", bow0)
        toy.key_hold(self.tank, "rotation_euler", bow0)
        self.key_loc(self.tank, crack, (-0.12, TY, H - 0.2))
        self.pipe_to_tank(bow0, H)
        self.pipe_to_tank(crack, H - 0.2)
        self.key_rot(self.tank, crack, (0, -0.06, 0))
        self.key_loc(self.tank, fr(0.74), (-1.0, 1.15, 3.6))
        self.key_rot(self.tank, fr(0.74), (0, -0.25, 0))
        self.key_loc(self.tank, land, FALL2)
        self.key_rot(self.tank, land, (0, FALL_ROT, 0))
        self.key_loc(self.tank, land + 4, FALL2 + V((0, 0, 0.08)))
        self.key_loc(self.tank, land + 8, FALL2)
        self.show(self.downpipe, crack, False)
        self.show(self.tube, crack, False)
        self.show(self.water, land + 1, False)
        self.show(self.bed_puddle, land + 1)
        for fl in self.flowers[:10]:
            self.show(fl, land, False)
        self.gauge(crack + 6, 0.0)
        self.big_splash("poles", land, (-2.2, 1.0, 0.6))
        # the wrecked tank keeps dumping its water out of its top corner, toward the lawn
        st.Jet("jet_pour_poles", (-3.3, 0.85, 0.85), (0.2, -1.0, 0.3), speed=1.8, radius=0.08, drops=50,
               drop_size=0.05, spread=0.3, seed=9).erupt(land + 6, e, rise=4)
        events.add(land, "stone_thud", gain=1.0)
        m.act("interact", b + 2, fr(0.14))
        m.act("talk", fr(0.14), fr(0.3))
        m.look_at(fr(0.3), (0, TY, H), hold=int(L * 0.3))
        m.look_at(fr(0.66), (-2.2, 1.0, 1.2), hold=int(L * 0.2))
        self.gasp(fr(0.66), fr(0.8))
        m.act("jump", land, fr(0.86))
        self.shrug(fr(0.87), e)
        # the tower filling, then the poles bowing (tank on top), then the fold and the fall into the flower bed
        tower = self.tank_pts(H) + [(-0.6, 0.6, 0.0), (0.6, 0.6, 0.0)]
        self.frame_on(b, fr(0.3), tower, angle=-82.0)
        self.frame_on(fr(0.3), fr(0.66), tower, angle=-96.0)
        self.frame_on(fr(0.66), e, self.tank_pts(H) + [(-3.4, 0.3, 0.0), (-1.4, 0.3, 1.9), (0.6, 0.6, 0.0)])

    def a_steel_legs(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, STEEL_MAX, facing_to(tuple(STEEL_MAX), (0.3, -1.6, 0.0)))
        self.show(self.pit_fill, b, False)
        self.show([r for r, _ in self.poles], b, False)
        self.show(self.bed_puddle, b, False)
        for fl in self.flowers:
            self.show(fl, b)
        # the tower stands from the first frame: footings, legs, ring beam, balcony, the refilled tank seated on top
        self.jump(self.tank, b, loc=(0, TY, H), rot=(0, 0, 0))
        self.show(self.water, b)
        self.level(b, 0.9)
        self.show(self.cable, b, False)
        self.show(self.footings + self.legs + self.rings + self.balcony + [self.downpipe, self.tube], b)
        # ... while Max bolts the footing, the cross-braces clank in, level by level
        n = {0: 0, 1: 0, 2: 0}
        for li, ob in self.braces:
            self.pop_in(ob, fr(0.05 + 0.07 * li) + n[li], frames=6)
            n[li] += 1
        for k in range(3):
            events.add(fr(0.05 + 0.07 * k), "steel_clank", gain=0.6)
        self.gauge(b, self.bar_at(H, 0.9))
        self.hold(self.wrench, b, fr(0.36))
        m.act("idle", b + 2, fr(0.34))          # upright in his close shot (the crouch clip laid him flat: a giant hat)
        m.key("shoulderR", b + 4, rot_deg=(0, 0, 0))
        self.key_dense(m, "shoulderR", b + 8, fr(0.32),
                       lambda f: (-55 + 22 * math.sin((f - b) * 0.45), 0, 0), step=3)
        m.key("shoulderR", fr(0.36), rot_deg=(0, 0, 0))
        for f in (b + 12, b + 24, fr(0.28)):
            events.add(f, "clink", gain=0.5)
        m.turn(fr(0.36), 0.0, frames=6)
        # the load path: bright arrows from the tank down the legs into the footings in the cutaway
        for k, sx in enumerate((-1, 1)):
            st.arrow(f"load_arrow_leg{k}", (sx * 0.66, -0.06, 5.5), (sx * 0.22, 0, -4.9), fr(0.38), e,
                     color="#FFE01A", width=0.18)
            st.arrow(f"load_arrow_foot{k}", (sx * 0.9, -0.12, 0.45), (0, 0, -1.15), fr(0.4), e,
                     color="#FFE01A", width=0.18)
            self._pts += [(sx * 1.1, -0.1, 5.7), (sx * 1.1, -0.1, -0.8)]
        self.label("LOAD PATH", (-2.15, -0.8, 3.2), fr(0.38), e, size=0.36)   # beside the tower: never behind a leg
        m.act("talk", fr(0.38), fr(0.5))
        self.point_side(fr(0.5), fr(0.74), hand="R", up=70)
        self.arms_v(m, fr(0.84), e)
        # 1) close on Max bolting the footing; 2) legs, braces, footings and arrows with Max beside them
        self.close(b, fr(0.36), offset=(-0.4, 0, 0))
        things = self.legs + self.footings + [self.max] + self._pts
        st.frame_all(self.rig, fr(0.36), fr(0.68), things, angle=-84.0, cut=True, margin=0.07, lens=28,
                     rise=0.14, swing=6.0)
        st.frame_all(self.rig, fr(0.68), e, things, angle=-96.0, cut=True, margin=0.07, lens=28,
                     rise=0.14, swing=6.0)

    def a_fail_overflow(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, PUMP_MAX, 0.0)
        self.show(self.supply + self.inlet, b)
        self.show(self.trench_fill_L, b, False)
        self.level(b, 0.45)
        self.gauge(b, self.bar_at(H, 0.45))
        self.hold(self.lemon, b, e)
        # 1) close on Max, lemonade in hand, flipping the pump on: the lamp lights, the pump hums
        m.act("interact", b + 3, fr(0.16))
        st.key_glow(self.lamp_mat, fr(0.08) - 1, 0.0)
        st.key_glow(self.lamp_mat, fr(0.08), 6.0)
        events.add(fr(0.08), "switch", gain=0.6)
        events.add(fr(0.09), "pump", duration=e - fr(0.09), gain=0.45)
        self.pump_run(fr(0.08), e)
        m.act("yes", fr(0.17), fr(0.3))
        # 2) close on the cut-open tank: the inlet pours, the water climbs to the brim (no shut-off)
        self.stream("inlet_stream_fill", (-0.08, TY, H + 0.95), (0.25, 0, -0.1), fr(0.1), e,
                    lambda x: H + 0.08, radius=0.035, drops=6)
        self.level_ramp(fr(0.1), fr(0.45), 0.45, 1.0)
        self.gauge(fr(0.45), self.bar_at(H, 1.0))
        self.label("NO SHUT-OFF", (0.0, 0.1, H + 1.75), fr(0.3), fr(0.47) - 1, size=0.3)
        pts_tank = list(self._pts)
        self._pts = []
        # 3) brimful: it spills over the right rim and falls down the tower straight onto Max's hard hat
        self.at(fr(0.3), OVER2, 0.0)
        sp, fall = fr(0.44), 30
        hit = sp + fall
        head = OVER2.z + 1.85
        spills = []
        for k, (y, rad) in enumerate(((0.8, 0.085), (1.0, 0.05))):
            tx_, ty_ = OVER2.x - 0.04 * k, OVER2.y + 0.04 * k
            v = ((tx_ - 0.64) / 1.05, (ty_ - y) / 1.05, 0.1)
            spills.append(self.stream(f"spill_{k}", (0.64, y, H + 1.2), v, sp + 2 * k, e,
                                      lambda x, thr=tx_ - 0.12: head if x > thr else 0.0, radius=rad, rise=fall,
                                      drops=24))
        events.add(sp, "water_rush", duration=e - sp, gain=0.6)
        hat = (OVER2.x, OVER2.y, head + 0.04)
        Puffs("spill_splash", "#F2FAFF", count=16, size=0.12, seed=5).emit(
            range(hit, hit + 8), lambda _f: hat, rise=0.5, life=20, drift=0.3)
        for k, d in enumerate(((1.0, 0.0, 0.7), (-1.0, 0.0, 0.7), (0.0, -1.0, 0.6))):
            st.Jet(f"spill_hat_jet{k}", hat, d, speed=1.5, radius=0.025, drops=30, drop_size=0.035, spread=0.4,
                   seed=k + 21).erupt(hit, e, rise=3)
        events.add(hit, "splash", gain=0.8)
        self.label("NO SHUT-OFF", (2.35, 0.1, H + 0.35), fr(0.47), e, size=0.28)
        # Max sips his lemonade, unaware ... until it lands on his hat: one gasp, a jump, a shrug
        m.key("shoulderR", fr(0.47), rot_deg=(0, 0, 0))
        m.key("shoulderR", fr(0.51), rot_deg=(-70, 0, 0))
        m.key("shoulderR", fr(0.56), rot_deg=(-68, 0, 0))
        m.key("shoulderR", hit - 2, rot_deg=(0, 0, 0))
        m.look_at(hit, (0.4, TY, H + 1.0), hold=int(L * 0.12))
        self.gasp(hit, hit + 16)
        m.act("jump", hit + 2, hit + 22)
        self.shrug(fr(0.8), e)
        self.close(b, fr(0.3), offset=(-0.45, 0, 0))
        st.frame_all(self.rig, fr(0.3), fr(0.47), [self.shell, (-0.1, TY, H + 0.95)] + pts_tank, angle=-88.0,
                     cut=True, margin=0.1, lens=28, rise=0.14, swing=6.0)
        st.frame_all(self.rig, fr(0.47), e, spills + [self.shell, self.max] + self._pts, angle=-92.0,
                     cut=True, margin=0.08, lens=28, rise=0.16, swing=6.0)

    def a_float_valve(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, BALC_MAX, 0.0)
        st.key_glow(self.lamp_mat, b, 6.0)
        self.show(self.inlet[1], b, False)
        self.show(self.float_parts + [self.overflow, self.inlet[0]], b)
        self.level(b, 0.3)
        self.gauge(b, self.bar_at(H, 0.3))
        # Max fits the valve (no prop in hand: the only float on screen is the one in the tank)
        m.act("interact", b + 4, fr(0.26))
        # a thick inlet stream pours out of the valve, in front of the riser, into the rising water
        f0, f1 = fr(0.12), fr(0.72)
        self.stream("inlet_stream_valve", (-0.1, TY - 0.12, H + 0.9), (0.35, -0.04, -0.3), f0, fr(0.58),
                    lambda x: H + 0.08, radius=0.055, rise=5, drops=12)
        # ... the ball pushes the arm up: the stream thins to a trickle and stops as the arm reaches the top
        self.stream("inlet_trickle_valve", (-0.1, TY - 0.12, H + 0.9), (0.12, -0.02, -0.2), fr(0.58), fr(0.68),
                    lambda x: H + 0.08, radius=0.022, rise=2, drops=0)
        self.level_ramp(f0, f1, 0.3, 0.8)
        surf = lambda f: (0.03, TY - 0.12, H + WATER_B + WATER_H * (0.3 + 0.5 * st.smooth((f - f0) / (f1 - f0))))  # noqa
        Puffs("inlet_splash_valve", "#F2FAFF", count=14, size=0.07, seed=6).emit(
            range(f0 + 4, fr(0.58), 3), surf, rise=0.15, life=10, drift=0.12)
        self.gauge(f1, self.bar_at(H, 0.8))
        events.add(fr(0.12), "pour", duration=fr(0.68) - fr(0.12), gain=0.35)
        events.add(fr(0.7), "clink", gain=0.8)
        st.arrow("float_lift_arrow", (0.3, 0.55, H + 0.3), (0, 0, 0.42), fr(0.4), e, color="#FFD23F", width=0.1)
        self.label("FLOAT VALVE", (0.12, 0.5, H + 1.5), fr(0.28), e, size=0.22)
        m.look_at(fr(0.28), (0.27, TY, H + 0.8), hold=int(L * 0.4))
        self.point_side(fr(0.3), fr(0.62), hand="L", up=75)
        self.arms_v(m, fr(0.8), e)
        # the cut-open tank (ball, arm, inlet stream, top of the overflow pipe) close, with Max beside it
        things = [(-0.62, 0.72, H), (0.62, 0.72, H + 1.22), (0.9, TY, H + 1.05), self.max]
        st.frame_all(self.rig, b, fr(0.45), things + self._pts, angle=-86.0,
                     cut=True, margin=0.08, lens=28, rise=0.14, swing=6.0)
        st.frame_all(self.rig, fr(0.45), e, things + self._pts, angle=-96.0,
                     cut=True, margin=0.08, lens=28, rise=0.14, swing=6.0)

    def a_fail_vacuum(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, BALC_MAX, facing_to(tuple(BALC_MAX), (BALC_MAX.x + 1.0, BALC_MAX.y - 1.6, BALC_MAX.z)))
        st.key_glow(self.lamp_mat, b, 0.0)
        self.level(b, 0.78)
        self.kids_on(b)
        for k, kid in enumerate(self.kids):
            kid.cut_place(b, KID_PLAT[k], 0.0)
        # a new sealed tank: no float valve, no overflow pipe (they come back with the vented tank)
        valve = self.float_parts + [self.overflow, self.inlet[0]]
        self.show(valve, b, False)
        self.show(valve, e + 1)
        # the owl peeks in from the rim, flutters up as the lid comes down, sits on it, then flies to its tree
        self.jump(self.owl, b, loc=OWL_RIM_HIGH)
        hover = V((0.35, 1.25, H + 2.3))
        self.owl_fly(b + 1, b + 11, hover, hop=0.25)
        self.owl_fly(b + 11, fr(0.12), hover + V((-0.1, 0.05, 0.12)), hop=0.06)
        self.owl_fly(fr(0.12), fr(0.17), OWL_RIM_HIGH + V((0, 0, 0.065)), hop=0.1)
        self.owl_fly(fr(0.32), fr(0.44), OWL_TREE, hop=1.0)
        # 1) close on Max: the airtight lid comes down onto the tank and he bolts it on, bolt by bolt
        self.pop_in(self.lid, b + 8, frames=5)
        self.key_loc(self.lid, b + 8, (0.0, 0.0, 1.95))
        self.key_loc(self.lid, b + 12, (0.0, 0.0, 1.95))
        self.key_loc(self.lid, fr(0.13), (0.0, 0.0, 1.235))
        events.add(fr(0.13), "steel_clank", gain=0.6)
        for k, bo in enumerate(self.bolts):
            self.pop_in(bo, fr(0.14) + 3 * k, frames=4)
            events.add(fr(0.14) + 3 * k, "clink", gain=0.45)
        self.hold(self.wrench, b, fr(0.25))
        m.act("interact", b + 3, fr(0.25))
        # 2) the kids open the slide valve below: the water drains out of the sealed tank
        self.kids[1].act("interact", fr(0.2), fr(0.3))
        self.wheel.rotation_euler = (0, 0, 0)
        self.wheel.keyframe_insert("rotation_euler", frame=fr(0.21))
        self.wheel.rotation_euler = (0, 0, R(220))
        self.wheel.keyframe_insert("rotation_euler", frame=fr(0.28))
        self.gush("vac", fr(0.26), fr(0.62))
        self.level_ramp(fr(0.26), fr(0.62), 0.78, 0.08)
        self.gauge(fr(0.26), self.bar_at(H, 0.78))
        self.gauge(fr(0.62), 0.05)
        st.arrow("vac_water_out", (0.35, 0.6, H - 0.15), (0, 0, -0.7), fr(0.26), e, color="#2E8FE0", width=0.12)
        m.act("fold_arms", fr(0.27), fr(0.68))
        m.look_at(fr(0.28), (0.0, TY, H + 0.4), hold=int(L * 0.3))
        # 3) outside air pushes on the walls and the lid: they cave in, crease, and crumple with a BANG
        for k, (base, vec) in enumerate((((0.0, 0.6, H + 2.2), (0, 0, -0.82)),
                                         ((1.72, TY, H + 0.9), (-0.97, 0, 0)),
                                         ((1.72, TY, H + 0.48), (-0.97, 0, 0)))):
            st.arrow(f"vac_arrow{k}", base, vec, fr(0.42), e, color="#E8382F", width=0.13)
        base_m = bpy.data.materials.get("wt_tank") or tx.paint("wt_tank", "#AEBBC3", rough=0.3, coat=0.4,
                                                                seams=0.4, metallic=0.5)
        cr, crush = crush_box("tank_shell_crush", TS, base_m, 0.72 - TY)
        _child(cr, self.tank, (0, 0, 0))
        c0, sb = fr(0.44), fr(0.71)
        toy.hide_tree(cr, 1, True)
        toy.hide_tree(cr, c0, False)
        toy.hide_tree(cr, e + 1, True)
        toy.hide_tree(self.shell, 1, False)
        toy.hide_tree(self.shell, c0, True)
        toy.hide_tree(self.shell, e + 1, False)
        for f, v in ((c0, 0.0), (fr(0.53), 0.28), (fr(0.55), 0.45), (fr(0.61), 0.5), (fr(0.63), 0.72),
                     (fr(0.69), 0.76), (sb, 1.0), (e, 1.0)):
            crush.value = v
            crush.keyframe_insert("value", frame=f)
        for f, v in ((c0, 0.0), (fr(0.55), 0.35), (fr(0.63), 0.65), (sb, 1.0), (e, 1.0)):
            self.lid_dent.value = v
            self.lid_dent.keyframe_insert("value", frame=f)
        self.lid_dent.value = 0.0                                  # the new tank (fix_vent) has a flat lid
        self.lid_dent.keyframe_insert("value", frame=e + 1)
        # the bang shakes the whole tank
        for f, a in ((sb - 1, 0.0), (sb + 2, 0.04), (sb + 4, -0.03), (sb + 6, 0.02), (sb + 9, 0.0)):
            self.key_rot(self.tank, f, (0, a, 0))
        events.add(c0, "creak", duration=sb - c0, gain=0.7)
        events.add(fr(0.55), "steel_clank", gain=0.6)
        events.add(fr(0.63), "steel_clank", gain=0.7)
        events.add(sb, "steel_clank", gain=1.0)
        events.add(sb, "stone_thud", gain=0.8)
        outer = bang_star("vac_bang_star", 0.34, 0.16, -0.02, 0.02, st.glow_mat("wt_bang_out", "#FF6A1A", 3.5),
                          seed=4)
        inner = bang_star("vac_bang_core", 0.2, 0.1, -0.035, -0.025, st.glow_mat("wt_bang_in", "#FFE14A", 4.5),
                          seed=7)
        for ob in (outer, inner):
            ob.location = (0.95, 0.35, H + 1.45)
            toy.hide_tree(ob, 1, True)
            self.pop_in(ob, sb, frames=4)
            toy.hide_tree(ob, sb + 12, True)
        self.label("VACUUM", (0.3, 0.1, H + 2.6), fr(0.42), e, size=0.38)
        m.look_at(sb, (0.3, TY, H + 0.7), hold=int(L * 0.2))
        self.gasp(sb, fr(0.86))
        # the bolting close-up, then ONE steady shot of the tank (water draining, arrows, walls crumpling) and Max
        self.close(b, fr(0.25), offset=(0.5, 0, 0))
        things = [self.shell, self.max, (0.0, 0.6, H + 2.25), (1.75, TY, H + 0.9), (1.75, TY, H + 0.48),
                  (0.35, 0.6, H - 0.9)] + self._pts
        st.frame_all(self.rig, fr(0.25), e, things, angle=-88.0, cut=True, margin=0.08, lens=28,
                     rise=0.14, swing=5.0)

    def a_fix_vent(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, BALC_AT, 0.0)
        self.shell.keyframe_insert("scale", frame=b - 1)
        self.dent.keyframe_insert("value", frame=b - 1)
        self.dent.value = 0.0
        self.dent.keyframe_insert("value", frame=b)
        self.shell.scale = (0.9, 0.9, 0.9)
        self.shell.keyframe_insert("scale", frame=b)
        self.shell.scale = (1, 1, 1)
        self.shell.keyframe_insert("scale", frame=b + 8)
        events.add(b, "pop", gain=0.5)
        toy.key_hold(self.cut.section, "location", b)
        self.cut._at(b + 6, self.cut.y_open)
        self.level(b, 0.82)
        self.gauge(b, self.bar_at(H, 0.82))
        m.act("yes", b + 4, fr(0.3))
        m.look_at(b + 4, (0.2, -1.5, H + 1.4), hold=int(L * 0.2))
        for k, ob in enumerate(self.vent):
            self.pop_in(ob, fr(0.1) + 2 * k, frames=6)
        events.add(fr(0.1), "steel_clank", gain=0.5)
        self.kids[1].act("interact", fr(0.26), fr(0.34))
        self.gush("vent", fr(0.3), e + 2)
        self.level_ramp(fr(0.3), fr(0.9), 0.82, 0.42)
        self.gauge(fr(0.9), self.bar_at(H, 0.42))
        st.arrow("air_in_arrow", (0.0, TY, H + 2.65), (0, 0, -0.68), fr(0.3), e, color="#E9F6FF", width=0.13)
        st.arrow("air_in_arrow_inside", (0.0, 0.85, H + 1.17), (0, 0, -0.18), fr(0.36), e, color="#E9F6FF",
                 width=0.08)
        st.arrow("water_out_arrow", (0.35, 0.6, H - 0.15), (0, 0, -0.7), fr(0.3), e, color="#2E8FE0", width=0.12)
        events.add(fr(0.3), "wind", duration=e - fr(0.3), gain=0.25)
        self.label("AIR IN", (0.6, 0.3, H + 2.5), fr(0.32), e, size=0.36)
        self.owl_fly(fr(0.5), fr(0.62), OWL_RAIL, hop=0.6)
        m.look_at(fr(0.3), (0, TY, H + 1.8), hold=int(L * 0.45))
        self.arms_v(m, fr(0.8), e)
        # the new tank, its vent and the AIR IN arrow with Max beside them, all beat long
        pts = self.tank_pts(H) + [(0.0, TY, H + 2.7), (0.35, 0.6, H - 0.85)]
        self.frame_on(b, fr(0.4), pts, angle=-80.0)
        self.frame_on(fr(0.4), e, pts)

    def a_city_tanks(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, TABLE_MAX, 0.0)
        for k, ob in enumerate(self.city):
            self.pop_in(ob, b + 2 + (k % 6), frames=8)
        self.show(self.city, e + 1, False)
        events.add(b + 2, "pop", gain=0.5)
        self.label("10,000 GAL", (-2.45, 0.2, 1.98), fr(0.3), e, size=0.24)
        m.act("talk", b + 2, fr(0.5))
        m.look_at(fr(0.1), (-2.45, 0.45, 1.3), hold=int(L * 0.7))
        self.point_side(fr(0.5), fr(0.86), hand="R", up=78)
        self.close(b, fr(0.4), offset=(-0.45, 0, 0.0))
        self.frame_on(fr(0.4), e, [(-3.0, 0.2, 0.0), (-1.9, 0.2, 1.75)], margin=0.12)

    def a_finale(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, MAX_AT, 0.0)
        self.gauge(b, self.bar_at(H, 0.8))
        self.level(b, 0.8)
        self.jump(self.owl, b, loc=OWL_VENT)
        for k, kid in enumerate(self.kids):
            kid.cut_place(b, KID_PLAT[k], 0.0)
        self.gush("finale", b, e + 2)
        m.look_at(b + 4, GAUGE, hold=int(L * 0.12))
        self.arms_v(m, fr(0.16), fr(0.34))
        self.slide_kid(self.kids[0], fr(0.36), fr(0.56), RUN_X1 - 0.25)
        self.kids[1].move(fr(0.46), fr(0.54), KID_PLAT[0])
        self.slide_kid(self.kids[1], fr(0.56), fr(0.76), RUN_X1 - 0.75)
        self.kids[0].cheer(fr(0.62), e)
        self.kids[1].cheer(fr(0.82), e)
        events.add(fr(0.6), "kids_cheer", gain=0.8)
        self.at(fr(0.36), SLIDE_MAX, 0.0)
        m.look_at(fr(0.4), (6.6, 0.9, 0.8), hold=int(L * 0.3))
        m.cheer(fr(0.8), e)
        # Max at the gauge with both kids on the platform, then the whole slide with both kids whooshing down
        st.frame_all(self.rig, b, fr(0.36), [self.max, self.kids[0], self.kids[1], (NOZZLE.x, 0.9, 3.3)],
                     cut=True, margin=0.12, lens=30, rise=0.16)
        st.frame_all(self.rig, fr(0.36), e, [(CHUTE_X0, 0.5, 3.3), (RUN_X1, 0.5, 0.3), self.kids[0],
                                              self.kids[1], self.max], cut=True, margin=0.1, lens=28, rise=0.16)

    # ------------------- hooks -------------------

    def a_crash_hook(self, i, h0, h1):
        self._pts = []
        L = h1 - h0
        m = self.max
        self.at(h0, HOOK_MAX, 0.0)
        self.kids_on(h0, False)
        self.show(self.footings + self.legs + self.rings + self.balcony + [b for _, b in self.braces]
                  + self.vent + self.bolts + [self.lid, self.overflow, self.downpipe, self.tube, self.chute_water]
                  + self.float_parts + self.inlet + self.supply + self.city, h0, False)
        self.show(self.pit_fill, h0)
        self.show(self.water, h0)
        self.show(self.bed_puddle, h0, False)
        for fl in self.flowers:
            self.show(fl, h0)
        self.dent.keyframe_insert("value", frame=h0 - 1)
        self.dent.value = 0.0
        self.dent.keyframe_insert("value", frame=h0)
        self.jump(self.owl, h0, loc=OWL_TREE)
        self.level(h0, 1.0)
        # frame 1: the poles are already bowing hard and the tank already tipping; they snap and topple back
        for k, (root, knee) in enumerate(self.poles):
            px, py = self.pole_xy[k]
            self.show(root, h0)
            self.jump(root, h0, loc=(px, py, 0.0), rot=(0, R(-10), 0))
            self.jump(knee, h0, rot=(0, R(22), 0))
            self.key_rot(root, h0 + 5, (0, R(-16), 0))
            self.key_rot(knee, h0 + 5, (0, R(32), 0))
        self.poles_fall(h0 + 6, h0 + 18, seed=21)
        self.jump(self.tank, h0, loc=(-0.25, TY, H - 0.2), rot=(0, -0.1, 0))
        self.key_loc(self.tank, h0 + 9, (-1.1, TY, 3.4))
        self.key_rot(self.tank, h0 + 9, (0, -0.28, 0))
        self.key_loc(self.tank, h0 + 16, FALL_TO)
        self.key_rot(self.tank, h0 + 16, (0, FALL_ROT, 0))
        self.key_loc(self.tank, h0 + 19, FALL_TO + V((0, 0, 0.08)))
        self.key_loc(self.tank, h0 + 22, FALL_TO)
        events.add(h0, "crack", gain=1.0)
        self.show(self.water, h0 + 17, False)
        self.show(self.bed_puddle, h0 + 17)
        for fl in self.flowers[:10]:
            self.show(fl, h0 + 16, False)
        self.big_splash("hook", h0 + 16, (-2.2, 1.0, 0.6))
        events.add(h0 + 16, "stone_thud", gain=1.0)
        self.gauge(h0, 0.4)
        self.gauge(h0 + 8, 0.0)
        m.look_at(h0 + 1, (-1.5, 1.0, 1.5), hold=max(1, L - 6))
        self.gasp(h0 + 2, h0 + int(L * 0.8))
        self.key_dense(m, "shoulderL", h0, h1 - 2, lambda f: (0, -60 if f < h0 + 4 else -120, 0))
        self.key_dense(m, "shoulderR", h0, h1 - 2, lambda f: (0, 60 if f < h0 + 4 else 120, 0))
        # the whole fall (tower top to flower bed) in the first second, then close on the wreck and Max
        cut = h0 + min(26, max(12, L // 3))
        st.frame_all(self.rig, h0, cut, [(-3.2, 0.3, 0.0), (0.7, 0.3, H + 0.9), self.max],
                     cut=True, margin=0.06, lens=28, rise=0.16, swing=5.0)
        st.frame_all(self.rig, cut + 1, h1, [(-3.0, 0.8, 0.0), (-1.4, 1.2, 1.3), self.max],
                     cut=True, margin=0.08, lens=28, rise=0.16, swing=6.0)

    def a_slide_hook(self, i, h0, h1):
        self._pts = []
        L = h1 - h0
        m = self.max
        self.at(h0, HOOK_MAX2, facing_to(tuple(HOOK_MAX2), (12.5, -4.5, 0.0)))
        self.kids_on(h0)
        k0, k1 = self.kids
        lane, lift = KID_LANE2, 0.12
        # frame 1: Kid1 has just shot off the end of the gushing run-out and is FLYING into the splash pool
        xs = RUN_X1 - 1.1
        lip = V((RUN_X1 - 0.05, lane, chute_z(RUN_X1 - 0.05) + lift))
        land = V((8.25, lane, 0.022 + lift))
        k0.cut_place(h0 - 9, (xs, lane, chute_z(xs) + lift), FACE_DOWNHILL)
        k0.sit(h0 - 14, h1 + 20, frames=4)
        k0.move(h0 - 9, h0 - 3, lip)
        for f in range(h0 - 2, h0 + 7):
            t = (f - (h0 - 3)) / 9.0
            self.key_loc(k0.root, f, lip.lerp(land, t) + V((0, 0, 1.6 * t * (1 - t))))
        k0.move(h0 + 6, h0 + 16, land + V((0.35, 0, 0)))
        k0.key("mouth", h0 - 9, scale=(1.0, 0.6, 1.6))
        k0.key("mouth", h0 + 24, scale=(0.7, 0.6, 1.0))
        self.arms_v(k0, h0 + 9, h1)
        self.hook_crown("hook_lip", h0 - 4, h0 + 8, (RUN_X1 + 0.05, lane, 0.5), small=True)
        self.hook_crown("hook_land", h0 + 5, h0 + 24, (land.x, lane, 0.05))
        events.add(h0 + 5, "splash", gain=1.0)
        # ... and Kid2 whooshes down the other lane toward the lens
        k1.cut_place(h0, KID_PLAT[0], 0.0)
        self.hook_kid_slide(k1, h0 + int(L * 0.22), h1 - 4, RUN_X1 - 0.4)
        self.hook_gush(h0 - 14, h1 + 2)
        events.add(h0 + 2, "kids_cheer", gain=0.8)
        m.cheer(h0 + 2, h1)
        # low at the slide exit looking up the chute: the flying kid and the splash big in the foreground
        mid = h0 + L // 2
        st.frame_all(self.rig, h0, mid, [self.chute, k0, self.max, (8.9, 1.1, 0.0)], angle=-34.0, cut=True,
                     margin=0.05, lens=20, rise=0.05, push=0.12, swing=5.0)
        st.frame_all(self.rig, mid + 1, h1, [self.chute, k0, k1, self.max], angle=-48.0, cut=True,
                     margin=0.05, lens=20, rise=0.06, push=0.1, swing=5.0)

    def close_side(self, f0, f1, offset=(0.3, 0, 0), angle=-65.0):
        st.close_on(self.rig, f0, f1, self.max, frac=0.42, angle=angle, swing=10.0, rise=0.22, lens=32,
                    look=0.62, offset=offset, cut=True, fstop=5.6, height=1.9)

    def poles_bow(self, f, k, theta):
        """A C-bow: the lower half leans by theta, the upper half back, so the top stays under the tank."""
        root, knee = self.poles[k]
        self.key_rot(root, f, (0, R(theta), 0))
        self.key_rot(knee, f, (0, R(-2 * theta), 0))

    def poles_fall(self, f0, f1, seed=12):
        """The broken poles topple BACKWARD onto the lawn (away from the tank's fall), one after the other,
        and lie flat on the grass (axis 55 mm up = resting on it), each kinked at its broken knee."""
        rnd = random.Random(seed)
        for k, (root, knee) in enumerate(self.poles):
            px, py = self.pole_xy[k]
            a, z = f0 + 2 * k, f1 + 3 * k
            toy.key_hold(root, "rotation_euler", a)
            toy.key_hold(knee, "rotation_euler", a)
            toy.key_hold(root, "location", a)
            kink = math.copysign(rnd.uniform(16, 30), px)
            mid = (a + z) // 2
            self.key_rot(root, mid, (R(-40), R(-8), 0))
            self.key_rot(knee, mid, (0, R(kink * 0.5 + 14), 0))
            self.key_loc(root, mid, (px, py, 0.03))
            self.key_rot(root, z, (R(-90), 0, 0))
            self.key_rot(knee, z, (0, R(kink), 0))
            self.key_loc(root, z, (px, py, 0.055))
            self.key_rot(root, z + 4, (R(-85), 0, 0))
            self.key_rot(root, z + 8, (R(-90), 0, 0))
            events.add(z, "stone_thud", gain=0.35)

    def big_splash(self, tag, f, at):
        """The tank hitting the flower bed: a tall crown of jets (mostly upward, so it stays in frame) + spray puffs."""
        Puffs(f"splash_{tag}", "#F2FAFF", count=48, size=0.42, seed=len(tag) + 7).emit(
            range(f, f + 22), lambda _f: at, rise=1.5, life=26, drift=0.6)
        for k, d in enumerate(((-0.25, 0, 1), (0.3, 0, 1), (0.0, -0.3, 1), (0.1, 0.35, 1), (-0.1, -0.1, 1))):
            st.Jet(f"splash_{tag}_jet{k}", at, d, speed=4.6 + 0.3 * k, radius=0.08, drops=60,
                   drop_size=0.065, spread=0.45, seed=k + 3).erupt(f, f + 18, rise=3)
        events.add(f, "splash", gain=1.0)

    def gush_big(self, tag, f0, f1):
        """The slide REALLY gushing: the usual gush + a thick core jet from the nozzle, white foam racing down the
        chute and a fan of water shooting off the run-out."""
        self.gush(tag, f0, f1)
        self.stream(f"slide_core_{tag}", NOZZLE + V((0.05, 0.0, 0.02)), (2.6, 0, -0.1), f0, f1,
                    lambda x: chute_z(x) + 0.05, radius=0.06, rise=4, drops=6)

        def foam(f):
            u = (f * 0.071) % 1.0
            x = CHUTE_X0 + 0.3 + u * (RUN_X1 - CHUTE_X0 - 0.45)
            return (x, 0.9 + 0.24 * math.sin(f * 1.7), chute_z(x) + 0.08)
        Puffs(f"slide_foam_{tag}", "#F2FAFF", count=16, size=0.05, seed=f0 % 17).emit(
            range(f0 + 2, f1, 2), foam, rise=0.12, life=12, drift=0.25)
        for k, dy in enumerate((-0.22, 0.0, 0.22)):          # a thin fan off the run-out, not one fat tube
            st.Jet(f"slide_outjet_{tag}{k}", (RUN_X1 + 0.02, 0.9 + dy, 0.47), (0.6, dy, 0.9), speed=2.8,
                   radius=0.028, drops=30, drop_size=0.03, spread=0.3, seed=f0 % 7 + 1 + k).erupt(f0 + 4, f1, rise=6)

    def pump_run(self, f0, f1):
        """The surface pump hums: its motor, fins and head buzz a few millimetres while it runs."""
        for name in ["pump_motor", "pump_head"] + [f"pump_fin{k}" for k in range(5)]:
            ob = bpy.data.objects.get(name)
            if ob is None:
                continue
            base = ob.location.copy()
            ob.keyframe_insert("location", frame=f0 - 1)
            for k, f in enumerate(range(f0, f1, 2)):
                ob.location = base + V((0, 0, 0.004 if k % 2 else -0.004))
                ob.keyframe_insert("location", frame=f)
            ob.location = base
            ob.keyframe_insert("location", frame=f1 + 1)

    def hook_crown(self, tag, f0, f1, at, small=False):
        """A splash crown of thin continuous jets with drops (no big foam balls in a close shot)."""
        dirs = ((-0.35, 0, 1), (0.4, 0, 1), (0.0, -0.45, 1), (0.15, 0.4, 1), (-0.15, -0.2, 1))
        for k, d in enumerate(dirs[:3 if small else 5]):
            st.Jet(f"splash_{tag}_jet{k}", at, d, speed=(2.4 if small else 3.6) + 0.25 * k,
                   radius=0.025 if small else 0.035, drops=30 if small else 50, drop_size=0.03, spread=0.5,
                   seed=k + len(tag)).erupt(f0, f1, rise=3)
        Puffs(f"splash_{tag}", "#F2FAFF", count=10 if small else 16, size=0.08, seed=len(tag)).emit(
            range(f0, f0 + 8), lambda _f: at, rise=0.5, life=14, drift=0.4)

    def hook_gush(self, f0, f1):
        """The slide at full blast for the hook: thick nozzle streams, the water sheet, a fat jet off the run-out."""
        self.stream("slide_stream_hook", NOZZLE + V((0.05, 0, 0)), (2.2, 0, -0.2), f0, f1,
                    lambda x: chute_z(x) + 0.03, radius=0.045, rise=4, drops=6)
        self.stream("slide_core_hook", NOZZLE + V((0.05, 0.0, 0.02)), (2.6, 0, -0.1), f0, f1,
                    lambda x: chute_z(x) + 0.05, radius=0.06, rise=4, drops=6)
        self.show(self.chute_water, f0 + 2)
        self.show(self.chute_water, f1 + 8, False)
        self.show(self.slide_puddle, f0 + 4)
        Spray("slide_run_hook", self.m_stream, count=18, radius=0.02, seed=8).run(
            f0 + 2, f1, (4.0, 0.9, 2.85), (RUN_X1 + 0.2, 0.9, 0.42), spread=0.35, arc=0.05, period=22)
        for k, dy in enumerate((-0.25, 0.0, 0.25)):          # a thin fan off the run-out (one 10 cm tube read solid)
            st.Jet(f"slide_outjet_hook{k}", (RUN_X1 + 0.03, 0.9 + dy, 0.47), (1.0, dy, 0.5), speed=3.2,
                   radius=0.03, drops=40, drop_size=0.032, spread=0.35, seed=4 + k).erupt(f0, f1, rise=4)
        events.add(f0, "water_rush", duration=f1 - f0, gain=0.6)

    def hook_kid_slide(self, kid, f0, f1, end_x):
        """Like slide_kid, ending in a thin splash crown instead of foam puffs."""
        lift = 0.12
        y = KID_LANE
        x0 = CHUTE_X0 + 0.45
        top = V((x0, y, chute_z(x0) + lift))
        bot = V((CHUTE_X1, y, chute_z(CHUTE_X1) + lift))
        end = V((end_x, y, chute_z(end_x) + lift))
        kid.turn(f0, FACE_DOWNHILL, frames=4)
        kid.move(f0, f0 + 6, top)
        kid.sit(f0, f1 + 14, frames=6)
        t_bot = f0 + 6 + int((f1 - f0 - 6) * 0.72)
        kid.move(f0 + 6, t_bot, bot)
        kid.move(t_bot, f1, end)
        kid.key("mouth", f0 + 6, scale=(1.0, 0.6, 1.6))
        kid.key("mouth", f1 + 10, scale=(0.7, 0.6, 1.0))
        events.add(f0 + 6, "whoosh", gain=0.4)
        self.hook_crown(f"hook_end_{kid.root.name}", f1 - 3, f1 + 12, (end_x + 0.25, y, 0.45), small=True)
        events.add(f1, "splash", gain=0.7)
