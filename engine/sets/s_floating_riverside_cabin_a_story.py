"""
FLOATING RIVERSIDE CABIN — Blender set for engine/sets/s_floating_riverside_cabin_a_story_spec.py.

Max's riverside timber cabin, told as a trial-and-error ladder: slab (floods) -> hollow pontoon in a wet dock
(floats) -> drifts away -> guide posts -> rigid utilities snap -> coiled flexible lines -> top-heavy lean ->
low centred ballast -> the big 2.7 m flood with the kids eating cake inside.

ASSET PLAN (real object -> shape / proportions -> the detail that makes it read -> how it is built)
- Riverbank cutaway (~10 m of action): flat grass bank at z = 0, the river channel on the left (2.6 m deep,
  sloped bank), a 1.8 m stone-walled terrace on the right where Max watches the floods. The ground is sliced
  at y = 0 so soil, the dock and the water read in section. -> st.terrain (own height function, soil section
  face), st.world_floor, st.carve (the dock pit), st.concrete stone terrace wall; BlenderKit willows.
- Max's timber cabin, 6 x 4 m, 2.6 m log walls, gable roof whose ridge runs front-to-back so the cut shows
  its profile, river-side door with a small porch deck, glowing back/side windows, a pendant lamp. The front
  wall is cut away (doll's-house section) so the flood inside, the floating sofa and the heavy furniture
  read. -> primitives: tx.planks lap logs, tx.shingles roof prisms, st.glass_glow windows (it floods, rises,
  drifts and tilts, and its inside must show, so it is built, not downloaded).
- Plain concrete slab (fail 1): 0.4 m slab on back-filled soil. -> st.concrete + soil boxes.
- Wet dock: concrete pit 6.8 x 4.8 m inside, 1.5 m deep, open at the cut. -> st.concrete walls / floor.
- Pontoon: HOLLOW concrete box 6.2 x 4.4 x 1.54 m (0.2 m walls, 0.25 m floor, deck slab); the cut shows the
  air inside. A front 'lid' closes it in the beats where it is not sectioned. -> boxes.
- Guide posts: four 7.5 m steel posts at the corners, two ring collars + arms on each corner of the house.
- Utilities: blue water riser on a valve box with its buried feed pipe cut in the section, a grey power kiosk
  with a black conduit; house-side stubs; later two coiled 'elephant' hoses (helix tubes whose shape key
  stretches them 3 m).
- Ballast: seven cast-iron blocks low and centred in the pontoon.
- River gauge: white board, red decimetre marks, 1-4 m numerals, in front of the bank beside the cabin.
- Water: river, flooded bank, wet dock (split around the hollow pontoon so its inside stays dry), water inside
  the slab cabin: st.Water pieces keyed together from one level.
- Gusher (core jet + many small drops, machines.Spray), sparks (glowing Spray), smoke (Puffs).
- BlenderKit props with primitive fallbacks: sofa, bathtub, upright piano, bookcase, dining table, cake,
  rowboat, mallard duck (the running gag), willow trees.
- Characters: Max, Kid1, Kid2 (engine.character, motion capture).
"""
import math
import random

import bpy
from mathutils import Vector

from engine import events, props as bk, studio as st, textures as tx, toy
from engine.camera import CameraRig, facing_to
from engine.character import Character
from engine.machines import Puffs, Spray
from engine.sets.s_floating_riverside_cabin_a_story_spec import ACTIONS, beat_actions

V = Vector
R = math.radians

NORMAL = -0.8           # everyday river level
FLOAT_AT = -0.29        # dock level at which the pontoon lifts off its floor (1.15 m draft)
LIFT_MAX = 3.0          # full stretch of the coiled service lines
PBOT = -1.44            # pontoon bottom (house local)
PX, PY0, PY1 = 3.1, 0.06, 4.5
DFLOOR = -1.45          # dock floor top
FLOOR = 0.25            # cabin floor top (house local)
POSTS = ((-3.25, 0.4), (-3.25, 4.4), (3.25, 0.4), (3.25, 4.4))
PORCH = (-3.72, 1.4, FLOOR)
KIDS_AT = ((-1.55, 1.75, FLOOR), (0.35, 1.75, FLOOR))
BANK = (4.05, 0.62, 0.0)
TERRACE = (5.8, 1.05, 1.8)
GAUGE_X, GAUGE_Y = 4.05, -0.24
W_X, W_Y, W_Z = 4.3, 1.3, 0.7          # water connection: ground point, house-side height
P_X, P_Y, P_Z = 4.5, 1.95, 1.25        # power connection
KIOSK_TOP = 0.45
COIL_R = 0.16
BLUE = "#3FB6FF"
RIVER_DUCK = (-6.5, 1.4, -9.0)


def _sm(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _cl(t):
    return max(0.0, min(1.0, t))


def _frames(f0, f1, step):
    out = list(range(int(f0), int(f1), step))
    if not out or out[-1] != int(f1):
        out.append(int(f1))
    return out


def _ground_z(x, y):
    if x < -3.76:                                     # the river channel and its far bank
        z = -2.6 * _sm((-3.76 - x) / 1.3) * (1.0 - _sm((-29.0 - x) / 2.0))
    elif x > 4.92:                                    # the high terrace
        z = 1.8 * _sm((x - 4.92) / 0.2)
    else:
        z = 0.0
    hill = 3.2 * _sm((y - 15.0) / 10.0) * (0.75 + 0.25 * math.sin(x * 0.21 + 1.0)) * _sm((x + 1.0) / 4.0)
    return z + hill


def bx(name, x0, x1, y0, y1, z0, z1, mat, parent=None, bevel=0.01):
    return toy.box(name, (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), mat=mat,
                   parent=parent, bevel=bevel)


def _helix(h, turns=6, tr=0.032, ring=8, per_turn=28):
    """A tube wound round a vertical helix (radius COIL_R) from z = 0 to h; both ends at (COIL_R, 0)."""
    n = turns * per_turn
    verts = []
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        p = V((COIL_R * math.cos(a), COIL_R * math.sin(a), h * t))
        k = 2 * math.pi * turns * COIL_R
        tan = V((-math.sin(a) * k, math.cos(a) * k, h)).normalized()
        nrm = V((math.cos(a), math.sin(a), 0.0))
        bi = tan.cross(nrm).normalized()
        nrm = bi.cross(tan).normalized()
        for j in range(ring):
            b = 2 * math.pi * j / ring
            verts.append(tuple(p + tr * (math.cos(b) * nrm + math.sin(b) * bi)))
    faces = []
    for i in range(n):
        for j in range(ring):
            a0, a1 = i * ring + j, i * ring + (j + 1) % ring
            faces.append((a0, a1, a1 + ring, a0 + ring))
    return verts, faces


WORK = (4.4, 0.72, 0.0)          # Max's work spot on the bank: clear of the dock wall (no forearm in the concrete)


HOUSE_PTS = ((-4.42, 0.6, 0.25), (-4.42, 3.6, 0.25), (-3.72, 1.4, 2.2), (3.15, 0.4, 2.7), (0.0, 0.4, 3.78),
             (3.1, 0.06, -0.35), (-3.1, 0.06, -0.35))


PORCH_IN = (-3.64, 1.5, 0.25)           # porch spot (z = FLOOR) clear of the rail and the door wall


TERRACE_EDGE = (5.45, 0.8, 1.8)         # terrace spot right beside the gauge (fail_slab)


FIN_PORCH = (-3.85, 2.55, FLOOR)        # finale porch spot: clear of the front-left guide post in the camera's view


GAUGE_FIN = -8.9                         # finale: the gauge stands in the river just left of the porch (x = -4.85)


class SFloatingRiversideCabinAStorySet:
    ACTIONS = ACTIONS
    QA_ALLOW = (r"ground_|terrace|dock|pontoon|slab_|fill_|cabin|porch|collar|guide_post|pipe|cable|coil|valve"
                r"|kiosk|gusher|jetdrop|spark|smoke|puff|arrow|label|BK_|fb_|heavy|ballast|boat|rope|table|cake"
                r"|duck|gauge|water|river|flood|tree|stubs|world")

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self.rnd = random.Random(7)
        self.riders, self.duck_fn = [], None
        self.lv, self.hx, self.hz, self.tilt = NORMAL, 0.0, 0.0, 0.0
        self.mode = "slab"
        self._shown = {}
        self._sofa_last = None
        self._world()
        self._dock()
        self._house()
        self._utilities()
        self._gauge()
        self._props()
        self._waters()
        self._fx()
        self._people()
        self.face_porch = facing_to(PORCH, (-2.0, -8.0, 0.0))
        self.face_bank = facing_to(BANK, (1.5, -8.0, 0.0))
        self.face_terrace = facing_to(TERRACE, (2.0, -8.0, 1.8))
        self.stage(1, "slab", slab=True, dock=False, pontoon=False, gauge=True, force=True)
        self.set_state(1, NORMAL)
        self.key_sofa(1, self.sofa_rest, 0.0)
        self.lights(1, True)

    # ------------------- world -------------------

    def _world(self):
        # warm sunlight and a clear blue sky with white clouds (set-wide colour)
        self.sun.data.color = (1.0, 0.86, 0.64)
        self.sun.data.energy = self.sun.data.energy * 1.15
        st.key_sky(self.scene, 1, 42.0)
        top = st.rock_grass("bank_grass", grass="#5DBF2E", grass_dark="#3C9A22", rock="#B07A4A", rock_dark="#7A4E2E")
        soil = st.section_rock("soil_section", light="#B0743E", dark="#8A552C")
        self.ground = st.terrain("ground_bank", -40.0, 26.0, 0.0, 36.0, _ground_z, floor=-80.0, res=0.25, top=top,
                                 side=soil)
        st.world_floor(0.0, around=(-40.0, 26.0, 36.0))
        st.carve(self.ground, st.box_cutter((0.0, 2.05, 0.1), (7.42, 6.2, 3.74)))      # the wet-dock pit
        stone = st.concrete("terrace_stone", "#D9773A", lift=0.35, panel=0.7)
        bx("terrace_wall", 4.86, 5.3, 0.006, 16.0, -0.4, 1.82, stone, bevel=0.02)
        for k, (x, y) in enumerate(((9.5, 8.5), (-1.0, 14.0), (14.0, 5.5), (-34.0, 9.0))):
            tree = bk.prop("willow tree", 8.0, fallback=self._fb_tree, name=f"tree{k}")
            tree.location = (x, y, _ground_z(x, y) - 0.05)
            tree.rotation_euler = (0, 0, R(37 * k))
        cloud = toy.material("world_cloud_white", toy.srgb("#FFFFFF"), roughness=0.9)
        rnd = random.Random(21)
        for i in range(7):
            root = toy.empty(f"world_cloud{i}", (rnd.uniform(-45, 45), rnd.uniform(70, 110), rnd.uniform(16, 30)))
            for k in range(4):
                c = toy.sphere(f"world_cloud{i}_{k}", rnd.uniform(2.6, 4.2),
                               (rnd.uniform(-4.0, 4.0), rnd.uniform(-1.0, 1.0), rnd.uniform(-0.6, 0.9)),
                               scale=(1.4, 1.0, 0.65), mat=cloud, parent=root, subdiv=1)
                st.no_shadow(c)

    def _dock(self):
        conc = st.concrete("dock_concrete", "#4FA3D1", lift=0.5, panel=1.7)
        g = self.dock_grp = toy.empty("dock_grp")
        bx("dock_floor", -3.4, 3.4, 0.004, 4.8, -1.75, -1.45, conc, parent=g)
        bx("dock_wallL", -3.7, -3.4, 0.004, 5.12, -1.75, 0.05, conc, parent=g)
        bx("dock_wallR", 3.4, 3.7, 0.004, 5.12, -1.75, 0.05, conc, parent=g)
        bx("dock_wallB", -3.4, 3.4, 4.8, 5.12, -1.75, 0.05, conc, parent=g)
        # the plain slab of the first attempt, on back-filled soil
        soil = toy.noise_material("fill_soil_mat", toy.srgb("#A8622E"), toy.srgb("#7E4420"), scale=9, bump=0.3)
        slab_m = st.concrete("slab_concrete", "#E8B84A", lift=0.4, panel=1.6)
        s = self.slab_grp = toy.empty("slab_grp")
        bx("fill_soil", -3.7, 3.7, 0.004, 5.12, -1.76, -0.31, soil, parent=s)
        bx("slab_main", -3.3, 3.3, 0.004, 4.72, -0.3, 0.1, slab_m, parent=s)
        bx("fill_left", -3.7, -3.31, 0.004, 5.12, -0.3, -0.012, soil, parent=s)
        bx("fill_right", 3.31, 3.7, 0.004, 5.12, -0.3, -0.012, soil, parent=s)
        bx("fill_back", -3.3, 3.3, 4.73, 5.12, -0.3, -0.012, soil, parent=s)

    def _house(self):
        H = self.house = toy.empty("house_rig")
        logs = tx.planks("cabin_logs", "#B4602A", "#CC7636", width=0.2, lap=True, across="z", along="xy", rough=0.7)
        floor_m = tx.planks("cabin_floorboards", "#E0A05A", "#C98745", width=0.16, across="x", along="y")
        deck_m = tx.planks("porch_boards", "#C27A3C", "#A9662F", width=0.14, across="y", along="x")
        roof_m = tx.shingles("cabin_shingles", "#D23A2A", "#8E2219")
        trim = tx.paint("cabin_trim", "#FFFFFF", 0.45)
        dark = tx.metal("cabin_dark_metal", "#2E3236", 0.45)
        door_m = tx.paint("cabin_door_paint", "#2E9E5B", 0.4)
        post_m = tx.wood("porch_wood", "#A8662F", "#BC7A3E")
        self.glass = st.glass_glow("cabin_glass")
        bx("cabin_floor", -2.99, 2.99, 0.41, 4.39, 0.12, FLOOR, floor_m, parent=H)
        z0, zt = 0.14, 2.6
        bx("cabin_wall_B0", -3.0, 3.0, 4.25, 4.4, z0, 1.0, logs, parent=H)
        bx("cabin_wall_B1", -3.0, 3.0, 4.25, 4.4, 1.9, zt, logs, parent=H)
        bx("cabin_wall_B2", -3.0, -0.65, 4.25, 4.4, 1.0, 1.9, logs, parent=H)
        bx("cabin_wall_B3", 0.65, 3.0, 4.25, 4.4, 1.0, 1.9, logs, parent=H)
        self.glass_back = bx("cabin_glass_back", -0.64, 0.64, 4.31, 4.34, 1.01, 1.89, self.glass, parent=H, bevel=0)
        bx("cabin_mullion_back", -0.03, 0.03, 4.29, 4.36, 1.02, 1.88, trim, parent=H, bevel=0)
        bx("cabin_wall_L0", -3.0, -2.85, 0.4, 1.8, z0, zt, logs, parent=H)
        bx("cabin_wall_L1", -3.0, -2.85, 2.8, 4.25, z0, zt, logs, parent=H)
        bx("cabin_wall_L2", -3.0, -2.85, 1.8, 2.8, 2.2, zt, logs, parent=H)
        bx("cabin_door", -2.97, -2.9, 1.82, 2.78, 0.26, 2.18, door_m, parent=H)
        toy.sphere("cabin_doorknob", 0.04, (-3.0, 2.62, 1.15), mat=dark, parent=H)
        self.wall_R = [bx("cabin_wall_R0", 2.85, 3.0, 0.4, 2.4, z0, zt, logs, parent=H),
                       bx("cabin_wall_R1", 2.85, 3.0, 3.4, 4.25, z0, zt, logs, parent=H),
                       bx("cabin_wall_R2", 2.85, 3.0, 2.4, 3.4, z0, 1.0, logs, parent=H),
                       bx("cabin_wall_R3", 2.85, 3.0, 2.4, 3.4, 1.9, zt, logs, parent=H)]
        bx("cabin_glass_R", 2.91, 2.94, 2.41, 3.39, 1.01, 1.89, self.glass, parent=H, bevel=0)
        st.prism("cabin_gable", [(-3.0, 2.59), (3.0, 2.59), (0.0, 3.58)], 4.25, 4.4, mat=logs).parent = H
        st.prism("cabin_roofL", [(-3.15, 2.56), (-0.004, 3.62), (-0.004, 3.76), (-3.15, 2.70)], 0.25, 4.6,
                 mat=roof_m).parent = H
        st.prism("cabin_roofR", [(0.004, 3.62), (3.15, 2.56), (3.15, 2.70), (0.004, 3.76)], 0.25, 4.6,
                 mat=roof_m).parent = H
        toy.cylinder("cabin_ridge", 0.075, 4.4, (0, 2.425, 3.74), rotation=(R(90), 0, 0), mat=trim, parent=H)
        # pendant lamp (the 'lights on' meter of the story)
        self.bulb_mat = st.glow_mat("cabin_lamp_glow", "#FFD58A", 0.0)
        toy.cylinder("cabin_lamp_cord", 0.012, 1.2, (0, 2.4, 2.95), mat=dark, parent=H, vertices=8)
        toy.sphere("cabin_lamp_bulb", 0.11, (0, 2.4, 2.3), mat=self.bulb_mat, parent=H)
        ld = bpy.data.lights.new("cabin_lamp_light", "POINT")
        ld.energy, ld.color, ld.shadow_soft_size = 0.0, (1.0, 0.8, 0.55), 0.3
        self.lamp = bpy.data.objects.new("cabin_lamp_light", ld)
        self.scene.collection.objects.link(self.lamp)
        self.lamp.parent = H
        self.lamp.location = (0, 2.4, 2.1)
        # porch on the river side, at the front door
        self.porch_parts = [bx("porch_deck", -4.42, -3.02, 0.6, 3.6, 0.13, FLOOR, deck_m, parent=H)]
        for k, y in enumerate((0.69, 3.51)):
            self.porch_parts.append(toy.cylinder(f"porch_post{k}", 0.05, 0.85, (-4.33, y, FLOOR + 0.405), mat=trim,
                                                 parent=H, vertices=12))
        self.porch_parts.append(bx("porch_rail", -4.37, -4.29, 0.69, 3.51, 0.97, 1.04, trim, parent=H))
        self.porch_parts.append(bx("porch_rail_mid", -4.36, -4.30, 0.69, 3.51, 0.6, 0.65, post_m, parent=H,
                                   bevel=0.005))
        # the hollow concrete pontoon, painted like a toy hull (house local; slides up when it is built)
        conc = st.concrete("pontoon_concrete", "#E8572C", lift=0.5, panel=1.4)
        inner = st.concrete("pontoon_inside", "#B8401F", lift=0.5, panel=1.4)
        P = self.pontoon_grp = toy.empty("pontoon", parent=H)
        self.pontoon_parts = [
            bx("pontoon_base", -PX, PX, PY0, PY1, PBOT, PBOT + 0.25, conc, parent=P),
            bx("pontoon_deck", -PX, PX, PY0, PY1, -0.1, 0.1, conc, parent=P),
            bx("pontoon_sideL", -PX, -2.9, PY0, PY1, PBOT + 0.25, -0.1, conc, parent=P),
            bx("pontoon_sideR", 2.9, PX, PY0, PY1, PBOT + 0.25, -0.1, conc, parent=P),
            bx("pontoon_back", -2.9, 2.9, 4.3, PY1, PBOT + 0.25, -0.1, inner, parent=P)]
        self.lid = bx("pontoon_lid", -2.9, 2.9, PY0, 0.24, PBOT + 0.25, -0.1, conc, parent=H)
        # guide posts (world, safety-yellow) and the collars on the house corners
        metal = tx.paint("guide_steel", "#FFC21A", 0.35, coat=0.5)
        self.posts_grp = toy.empty("guide_posts", (0, 0, DFLOOR + 0.005))
        self.collars = toy.empty("collars", parent=H)
        self.postL_parts, self.collarL_parts = [], []
        for k, (px, py) in enumerate(POSTS):
            side, sg = ("L", -1) if px < 0 else ("R", 1)
            p = toy.cylinder(f"guide_post{side}{k}", 0.07, 7.45, (px, py, 3.725), mat=metal, parent=self.posts_grp,
                             vertices=16)
            cap = toy.sphere(f"guide_post{side}{k}_cap", 0.085, (px, py, 7.45), mat=metal, parent=self.posts_grp)
            if side == "L":
                self.postL_parts += [p, cap]
            for j, z in enumerate((-0.5, 2.3)):
                bpy.ops.mesh.primitive_torus_add(major_radius=0.11, minor_radius=0.025, major_segments=28,
                                                 minor_segments=8, location=(px, py, z))
                ring = bpy.context.active_object
                ring.name = f"collar{side}{k}_{j}"
                ring.data.materials.append(metal)
                ring.parent = self.collars
                lo, hi = sorted((sg * 2.98, sg * 3.15))
                arm = bx(f"collar{side}{k}_{j}_arm", lo, hi, py - 0.03, py + 0.03, z - 0.035, z + 0.035, metal,
                         parent=self.collars, bevel=0.005)
                if side == "L":
                    self.collarL_parts += [ring, arm]
        # ballast: cast-iron blocks (painted deep blue) low and centred on the pontoon floor
        iron = tx.paint("ballast_iron", "#2A4FB8", 0.45, coat=0.3, metallic=0.3)
        self.ballast_grp = toy.empty("ballast_grp", parent=H)
        zb = PBOT + 0.255
        self.ballast_parts = []
        for r, y in enumerate((1.25, 2.5)):
            for k, x in enumerate((-1.0, 0.0, 1.0)):
                self.ballast_parts.append(bx(f"ballast{r}{k}", x - 0.45, x + 0.45, y - 0.56, y + 0.56, zb, zb + 0.4,
                                             iron, parent=self.ballast_grp))
        self.ballast_parts.append(bx("ballast_top", -0.45, 0.45, 0.75, 3.0, zb + 0.41, zb + 0.7, iron,
                                     parent=self.ballast_grp))

    def _utilities(self):
        H = self.house
        blue = tx.paint("water_pipe_blue", "#2F6FB5", 0.35, coat=0.4)
        black = tx.paint("cable_black", "#26282B", 0.5)
        steel = tx.metal("valve_steel", "#8D949B", 0.35)
        kiosk_m = tx.paint("kiosk_green", "#7E8C7A", 0.45, seams=0.3)
        self.base_grp = toy.empty("utilbase_grp")
        bx("valve_box", W_X - 0.16, W_X + 0.16, W_Y - 0.16, W_Y + 0.16, -0.06, 0.08, steel, parent=self.base_grp)
        bx("kiosk", P_X - 0.2, P_X + 0.2, P_Y - 0.16, P_Y + 0.16, -0.05, KIOSK_TOP, kiosk_m, parent=self.base_grp)
        toy.cylinder("pipe_feed", 0.05, W_Y + 0.03, (W_X, (W_Y - 0.03) / 2, -0.55), rotation=(R(90), 0, 0),
                     mat=blue, parent=self.base_grp)
        # rigid connections, anchored in the ground
        self.rigid_grp = toy.empty("rigid_grp")
        self.riser_parts = [
            toy.cylinder("pipe_riser", 0.05, W_Z - 0.05, (W_X, W_Y, (W_Z + 0.05) / 2), mat=blue, parent=self.rigid_grp),
            toy.cylinder("pipe_riser_flange", 0.075, 0.04, (W_X, W_Y, W_Z - 0.03), mat=steel, parent=self.rigid_grp)]
        toy.cylinder("cable_riser", 0.04, P_Z - KIOSK_TOP + 0.03, (P_X, P_Y, (P_Z + KIOSK_TOP - 0.03) / 2), mat=black,
                     parent=self.rigid_grp)
        # house-side stubs (ride with the house)
        self.stubs = toy.empty("stubs", parent=H)
        l1, l2 = W_X - 2.95, P_X - 2.95
        toy.cylinder("pipe_house", 0.05, l1, (2.95 + l1 / 2, W_Y, W_Z), rotation=(0, R(90), 0), mat=blue,
                     parent=self.stubs)
        toy.sphere("pipe_house_elbow", 0.065, (W_X, W_Y, W_Z), mat=blue, parent=self.stubs)
        toy.cylinder("cable_house", 0.04, l2, (2.95 + l2 / 2, P_Y, P_Z), rotation=(0, R(90), 0), mat=black,
                     parent=self.stubs)
        toy.sphere("cable_house_elbow", 0.05, (P_X, P_Y, P_Z), mat=black, parent=self.stubs)
        # flexible 'elephant' lines: helices whose shape key stretches them LIFT_MAX metres
        self.coils_grp = toy.empty("coils_grp")
        cw, skw = self._coil("coil_water", W_X, W_Y, 0.05, W_Z - 0.05, tx.rubber("coil_blue", "#2D6DB8", 0.6))
        cp, skp = self._coil("coil_power", P_X, P_Y, KIOSK_TOP - 0.02, P_Z - KIOSK_TOP + 0.02,
                             tx.rubber("coil_orange", "#E2742A", 0.6))
        for c in (cw, cp):
            c.parent = self.coils_grp
        self.coil_objs = [cw, cp]
        self.coil_keys = [(skw, (W_X, W_Y, W_Z)), (skp, (P_X, P_Y, P_Z))]

    def _coil(self, name, x, y, z0, h, mat):
        v0, faces = _helix(h)
        v1, _ = _helix(h + LIFT_MAX)
        ob = st.mesh_obj(name, v0, faces, mats=(mat,), smooth=True)
        ob.location = (x - COIL_R, y, z0)
        ob.shape_key_add(name="Basis", from_mix=False)
        sk = ob.shape_key_add(name="stretch", from_mix=False)
        for i, co in enumerate(v1):
            sk.data[i].co = co
        return ob, sk

    def _text(self, name, body, loc, size, mat, parent=None):
        cu = bpy.data.curves.new(name, "FONT")
        cu.body, cu.size = body, size
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        ob = bpy.data.objects.new(name, cu)
        self.scene.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (R(90), 0, 0)
        cu.materials.append(mat)
        if parent is not None:
            ob.parent = parent
        return ob

    def _gauge(self):
        """River gauge in front of the bank cut: white board, red decimetre marks, metre numerals."""
        board_m = tx.paint("gauge_white", "#F4F2EC", 0.4)
        red = tx.paint("gauge_red", "#D2302A", 0.4)
        post_m = tx.metal("gauge_post_steel", "#6C7278")
        g = self.gauge_grp = toy.empty("gauge_grp")
        x, y = GAUGE_X, GAUGE_Y
        parts = [bx("gauge_post", x - 0.06, x + 0.06, y + 0.03, y + 0.11, -1.2, 4.4, post_m, parent=g),
                 bx("gauge_board", x - 0.3, x + 0.3, y - 0.02, y + 0.02, -1.1, 4.3, board_m, parent=g, bevel=0.005)]
        for k in range(-5, 21):
            z = k * 0.2
            w = 0.26 if k % 5 == 0 else 0.15
            parts.append(bx(f"gauge_mark{k + 5}", x - 0.28, x - 0.28 + w, y - 0.034, y - 0.026, z - 0.03, z + 0.03,
                            red, parent=g, bevel=0))
        for m in range(1, 5):
            parts.append(self._text(f"gauge_num{m}", str(m), (x + 0.15, y - 0.03, m + 0.16), 0.36, red, parent=g))
        self.gauge_parts = parts

    def _props(self):
        H = self.house
        self.sofa = bk.prop("sofa", 2.0, fallback=self._fb_sofa, name="sofa")
        self.sofa.parent = H
        self.sofa_rest = (-1.6, 3.78, FLOOR + 0.004)
        self.sofa.location = self.sofa_rest
        self.heavy = toy.empty("heavy", parent=H)
        tub = bk.prop("bathtub", 1.7, fallback=self._fb_tub, name="bathtub")
        piano = bk.prop("upright piano", 1.5, fallback=self._fb_piano, name="piano")
        books = bk.prop("bookcase", 1.8, fallback=self._fb_books, name="bookcase")
        for ob, (x, y), rot in ((tub, (2.3, 1.35), 90), (piano, (2.45, 2.98), 90), (books, (1.6, 4.0), 0)):
            ob.parent = self.heavy
            ob.location = (x, y, FLOOR + 0.004)
            ob.rotation_euler = (0, 0, R(rot))
        self.table_grp = toy.empty("table_grp", parent=H)
        table = bk.prop("dining table", 1.4, fallback=self._fb_table, name="table")
        top = self._top(table)
        table.parent = self.table_grp
        table.location = (-0.6, 2.85, FLOOR + 0.004)
        cake = bk.prop("birthday cake", 0.32, fallback=self._fb_cake, name="cake")
        cake.parent = self.table_grp
        cake.location = (-0.6, 2.85, FLOOR + top + 0.01)
        self.boat_grp = toy.empty("boat_grp", parent=H)
        boat = bk.prop("rowboat", 3.2, fallback=self._fb_boat, name="boat")
        boat.parent = self.boat_grp
        boat.location = (-5.95, 2.1, -0.44)
        boat.rotation_euler = (0, 0, R(90))
        a, b = V((-4.36, 0.69, 0.9)), V((-5.9, 0.75, 0.0))
        rope = toy.cylinder("boat_rope", 0.015, (b - a).length, (a + b) / 2, mat=tx.cloth("rope_hemp", "#C9A86A"),
                            parent=self.boat_grp, vertices=8)
        rope.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
        self.duck = bk.prop("mallard duck", 0.45, fallback=self._fb_duck, name="duck")
        self.duck.location = (RIVER_DUCK[0], RIVER_DUCK[1], NORMAL - 0.07)
        self.duck.rotation_euler = (0, 0, R(180))
        toy.add_noise(self.duck, "location", 2, strength=0.02, scale=9)

    @staticmethod
    def _top(root):
        bpy.context.view_layer.update()
        zs = [(o.matrix_world @ V(c)).z for o in root.children_recursive if o.type == "MESH" for c in o.bound_box]
        return max(zs) if zs else 0.75

    def _waters(self):
        self.waters = {
            "river": st.Water("river", -40.0, -3.4, 0.05, 34.0, -2.5, NORMAL),
            "bank": st.Water("flood_bank", 3.4, 26.0, 0.05, 34.0, 0.012, 0.035),
            "D": st.Water("dock_water", -3.39, 3.39, 0.05, 4.79, -1.44, NORMAL),
            "I": st.Water("flood_in", -3.39, 3.39, 0.05, 4.79, 0.106, 0.13),
            "gapL": st.Water("dock_gapL", -3.39, -3.12, 0.05, 4.79, -1.44, NORMAL),
            "gapR": st.Water("dock_gapR", 3.12, 3.39, 0.05, 4.79, -1.44, NORMAL),
            "back": st.Water("dock_back", -3.11, 3.11, 4.52, 4.79, -1.44, NORMAL),
            "U": st.Water("dock_under", -3.11, 3.11, 0.05, 4.51, -1.44, -1.42),
        }

    def _fx(self):
        gm = st.glow_mat("gusher_glow", "#C8EEFF", 0.8)
        self.gush_core = toy.cylinder("gusher_core", 0.06, 1.0, (W_X, W_Y, W_Z + 0.5), mat=gm, vertices=16)
        st.no_shadow(self.gush_core)
        toy.add_noise(self.gush_core, "scale", 0, strength=0.25, scale=3)
        toy.add_noise(self.gush_core, "scale", 1, strength=0.25, scale=3, phase=4)
        self.gush_spray = Spray("jetdrop", gm, count=70, radius=0.045, seed=5)
        self.sparks = Spray("spark", st.glow_mat("spark_glow", "#FFC23A", 9.0), count=26, radius=0.022, seed=8)
        for sp in (self.gush_spray, self.sparks):
            for p in sp.parts:
                p.location, p.scale = (0, 0, -60), (0.01, 0.01, 0.01)
                p.keyframe_insert("location", frame=1)
                p.keyframe_insert("scale", frame=1)
        self.smoke = Puffs("smoke", "#5E5E60", count=10, size=0.14, seed=4)

    def _people(self):
        self.max = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
        self.max.place(1, PORCH, 0)
        self.max.key("hips", 1, loc=(0, 0, 0.56))
        self.max.auto_blink(1, self.total + 400, seed=11)
        self.kids = [Character("Kid1", {"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5",
                                        "hair": "#5B3A1E", "scale": 0.6, "ponytail": True}),
                     Character("Kid2", {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B",
                                        "hair": "#2B1A10", "scale": 0.56})]
        cake_m = tx.paint("cake_slice_cream", "#F6D7E0", 0.5)
        for k, kid in enumerate(self.kids):
            kid.place(1, KIDS_AT[k], 0)
            kid.key("hips", 1, loc=(0, 0, 0.56))
            kid.auto_blink(1, self.total + 400, seed=k + 3)
            sl = toy.box(f"cake_slice{k}", (0.1, 0.07, 0.06), mat=cake_m, bevel=0.01)
            kid.hold(sl, "R")
            sl.location = (0.0, -0.06, -0.5)

    # ------------------- fallbacks (built at the origin) -------------------

    def _fb_sofa(self):
        m = tx.cloth("fb_sofa_cloth", "#B9553D")
        r = toy.empty("fb_sofa")
        bx("fb_sofa_seat", -1.0, 1.0, -0.42, 0.42, 0.0, 0.45, m, parent=r, bevel=0.04)
        bx("fb_sofa_back", -1.0, 1.0, 0.2, 0.42, 0.46, 0.88, m, parent=r, bevel=0.04)
        bx("fb_sofa_armL", -1.0, -0.84, -0.42, 0.19, 0.46, 0.66, m, parent=r, bevel=0.03)
        bx("fb_sofa_armR", 0.84, 1.0, -0.42, 0.19, 0.46, 0.66, m, parent=r, bevel=0.03)
        return r

    def _fb_tub(self):
        r = toy.empty("fb_tub")
        bx("fb_tub_body", -0.85, 0.85, -0.38, 0.38, 0.0, 0.58, tx.paint("fb_tub_white", "#F3F3F0", 0.2), parent=r,
           bevel=0.06)
        bx("fb_tub_inside", -0.75, 0.75, -0.28, 0.28, 0.3, 0.586, tx.paint("fb_tub_in", "#DDE6EA", 0.15), parent=r,
           bevel=0.05)
        return r

    def _fb_piano(self):
        r = toy.empty("fb_piano")
        bx("fb_piano_body", -0.75, 0.75, -0.3, 0.3, 0.0, 1.3, tx.paint("fb_piano_black", "#1B1B1E", 0.2, coat=0.8),
           parent=r, bevel=0.02)
        bx("fb_piano_keys", -0.7, 0.7, -0.45, -0.25, 0.68, 0.76, tx.paint("fb_piano_ivory", "#F4F0E4", 0.3),
           parent=r, bevel=0.005)
        return r

    def _fb_books(self):
        r = toy.empty("fb_books")
        bx("fb_books_case", -0.5, 0.5, -0.17, 0.17, 0.0, 1.8, tx.wood("fb_books_wood", "#6E4A2C", "#80583A"),
           parent=r, bevel=0.01)
        cols = ("#C0392B", "#2E86C1", "#F1C40F", "#27AE60")
        for k, z in enumerate((0.15, 0.6, 1.05, 1.45)):
            bx(f"fb_books_row{k}", -0.44, 0.44, -0.2, -0.1, z, z + 0.3, tx.paint(f"fb_book{k}", cols[k], 0.5),
               parent=r, bevel=0.005)
        return r

    def _fb_table(self):
        r = toy.empty("fb_table")
        wood = tx.wood("fb_table_wood", "#A0703F", "#B5824C")
        bx("fb_table_top", -0.7, 0.7, -0.42, 0.42, 0.72, 0.77, wood, parent=r, bevel=0.01)
        for k, (x, y) in enumerate(((-0.62, -0.34), (0.62, -0.34), (-0.62, 0.34), (0.62, 0.34))):
            toy.cylinder(f"fb_table_leg{k}", 0.03, 0.74, (x, y, 0.37), mat=wood, parent=r, vertices=10)
        return r

    def _fb_cake(self):
        r = toy.empty("fb_cake")
        toy.cylinder("fb_cake_base", 0.15, 0.12, (0, 0, 0.06), mat=tx.paint("fb_cake_pink", "#F29BB5", 0.5), parent=r)
        toy.cylinder("fb_cake_icing", 0.11, 0.06, (0, 0, 0.15), mat=tx.paint("fb_cake_cream", "#FFF6EA", 0.5),
                     parent=r)
        toy.cylinder("fb_cake_candle", 0.012, 0.08, (0, 0, 0.21), mat=tx.paint("fb_candle", "#5DADE2", 0.5), parent=r)
        toy.sphere("fb_cake_flame", 0.016, (0, 0, 0.26), mat=st.glow_mat("fb_flame", "#FFB43A", 6.0), parent=r)
        return r

    def _fb_boat(self):
        r = toy.empty("fb_boat")
        wood = tx.planks("fb_boat_planks", "#8C5A33", "#A06A3E", width=0.12, across="z", along="xy", lap=True)
        bx("fb_boat_bottom", -1.5, 1.5, -0.5, 0.5, 0.0, 0.1, wood, parent=r, bevel=0.03)
        bx("fb_boat_sideL", -1.5, 1.5, -0.6, -0.5, 0.0, 0.45, wood, parent=r, bevel=0.02)
        bx("fb_boat_sideR", -1.5, 1.5, 0.5, 0.6, 0.0, 0.45, wood, parent=r, bevel=0.02)
        bx("fb_boat_stern", -1.6, -1.5, -0.6, 0.6, 0.0, 0.45, wood, parent=r, bevel=0.02)
        bx("fb_boat_bow", 1.5, 1.6, -0.6, 0.6, 0.0, 0.45, wood, parent=r, bevel=0.02)
        bx("fb_boat_seat", -0.2, 0.2, -0.5, 0.5, 0.28, 0.33, wood, parent=r, bevel=0.01)
        return r

    def _fb_duck(self):
        r = toy.empty("fb_duck")
        toy.sphere("fb_duck_body", 0.14, (0, 0, 0.12), scale=(1.35, 1.0, 0.8), mat=tx.paint("fb_duck_brown", "#8A6A4A",
                                                                                              0.6), parent=r)
        toy.sphere("fb_duck_head", 0.075, (0.17, 0, 0.27), mat=tx.paint("fb_duck_green", "#2E7D4F", 0.4), parent=r)
        bx("fb_duck_beak", 0.22, 0.31, -0.025, 0.025, 0.25, 0.28, tx.paint("fb_duck_beak", "#F2A43A", 0.4), parent=r,
           bevel=0.008)
        return r

    def _fb_tree(self):
        r = toy.empty("fb_tree")
        toy.cylinder("fb_tree_trunk", 0.22, 3.2, (0, 0, 1.6), mat=tx.wood("fb_bark", "#5A4632", "#74604A"), parent=r)
        leaf = toy.noise_material("fb_leaves", toy.srgb("#4F7A32"), toy.srgb("#6E9A44"), scale=6, bump=0.4)
        for k, (x, z, s) in enumerate(((0, 4.2, 1.9), (0.9, 3.4, 1.3), (-0.9, 3.5, 1.4))):
            toy.sphere(f"fb_tree_leaves{k}", s, (x, 0, z), mat=leaf, parent=r)
        return r

    # ------------------- state: water level, house, riders -------------------

    def world(self, loc):
        t = R(self.tilt)
        x, y, z = loc
        return V((self.hx + x * math.cos(t) + z * math.sin(t), y, self.hz - x * math.sin(t) + z * math.cos(t)))

    def world_f(self, f, loc):
        hl = toy.value_at(self.house, "location", f)
        t = toy.value_at(self.house, "rotation_euler", f)[1]
        x, y, z = loc
        return (hl[0] + x * math.cos(t) + z * math.sin(t), y, hl[2] - x * math.sin(t) + z * math.cos(t))

    def _piece(self, key, lv, hz):
        if key == "bank":
            return max(lv, 0.035)
        if key == "I":
            return max(lv, 0.13)
        if key == "U":
            return max(PBOT + hz - 0.015, -1.42)
        return lv

    def _auto_vis(self, f, force=False):
        m = self.mode
        want = {"river": True, "bank": self.lv > 0.045, "D": m == "closed", "I": m == "slab" and self.lv > 0.14,
                "gapL": m == "open", "gapR": m == "open", "back": m == "open", "U": m == "open" and self.hz > 0.03}
        for k, on in want.items():
            if force or self._shown.get("w_" + k) != on:
                self.waters[k].hide(f, not on)
                self._shown["w_" + k] = on

    def set_state(self, f, lv, hx=0.0, hz=0.0, tilt=0.0):
        self.lv, self.hx, self.hz, self.tilt = lv, hx, hz, tilt
        for key, w in self.waters.items():
            w.key_level(f, self._piece(key, lv, hz))
        self._auto_vis(f)
        H = self.house
        H.location = (hx, 0.0, hz)
        H.rotation_euler = (0.0, R(tilt), 0.0)
        H.keyframe_insert("location", frame=f)
        H.keyframe_insert("rotation_euler", frame=f)
        for ch, loc in self.riders:
            ch.root.location = self.world(loc)
            ch.root.keyframe_insert("location", frame=f)
        for sk, tip in self.coil_keys:
            sk.value = _cl((self.world(tip).z - tip[2]) / LIFT_MAX)
            sk.keyframe_insert("value", frame=f)
        if self.duck_fn is not None:
            x, y, zmin = self.duck_fn(f)
            self.duck.location = (x, y, max(lv, zmin) - 0.07)
            self.duck.keyframe_insert("location", frame=f)

    def hold(self, f):
        self.set_state(f, self.lv, self.hx, self.hz, self.tilt)

    def ramp(self, f0, f1, lv0, lv1, x=None, tilt=None, floating=True, extra=None, ease=True, step=2):
        """The river goes lv0 -> lv1 over f0..f1; a floating house rides it (x(t), tilt(t, lift) optional)."""
        for f in _frames(f0, f1, step):
            t = (f - f0) / max(1, f1 - f0)
            lv = lv0 + (lv1 - lv0) * (_sm(t) if ease else t)
            hz = max(0.0, lv - FLOAT_AT) if floating else 0.0
            hx = x(t) if x else self.hx
            tl = tilt(t, hz) if tilt else 0.0
            self.set_state(f, lv, hx, hz, tl)
            if extra:
                extra(f, t, lv)

    @staticmethod
    def level_at(f, f0, f1, lv0, lv1):
        return lv0 + (lv1 - lv0) * _sm((f - f0) / max(1, f1 - f0))

    def key_sofa(self, f, loc, rot):
        self.sofa.location = loc
        self.sofa.rotation_euler = (0, 0, R(rot))
        self.sofa.keyframe_insert("location", frame=f)
        self.sofa.keyframe_insert("rotation_euler", frame=f)
        self._sofa_last = (tuple(loc), rot)

    # ------------------- staging -------------------

    def vis(self, key, objs, f, on, force=False):
        if force or self._shown.get(key) != on:
            for o in objs:
                toy.hide_tree(o, f, not on)
            self._shown[key] = on

    def stage(self, f, mode, slab=False, dock=True, pontoon=True, lid=False, posts=False, collars=None, utils=None,
              heavy=False, ballast=False, boat=False, kids=False, table=False, gauge=False, force=False):
        self.mode = mode
        self.vis("slab", [self.slab_grp], f, slab, force)
        self.vis("dock", [self.dock_grp], f, dock, force)
        self.vis("pontoon", [self.pontoon_grp], f, pontoon, force)
        self.vis("lid", [self.lid], f, lid, force)
        self.vis("posts", [self.posts_grp], f, posts, force)
        self.vis("collars", [self.collars], f, posts if collars is None else collars, force)
        self.vis("ubase", [self.base_grp, self.stubs], f, utils is not None, force)
        self.vis("rigid", [self.rigid_grp], f, utils == "rigid", force)
        self.vis("coils", [self.coils_grp], f, utils == "coil", force)
        self.vis("heavy", [self.heavy], f, heavy, force)
        self.vis("ballast", [self.ballast_grp], f, ballast, force)
        self.vis("boat", [self.boat_grp], f, boat, force)
        self.vis("kids", [k.root for k in self.kids], f, kids, force)
        self.vis("table", [self.table_grp], f, table, force)
        self.vis("gauge", [self.gauge_grp], f, gauge, force)
        self.vis("gusher", [self.gush_core], f, False, force)
        self._auto_vis(f, force)

    def set_mode(self, f, mode):
        self.mode = mode
        self._auto_vis(f)

    def begin(self, b, mode, lv=NORMAL, hz=0.0, hx=0.0, duck=None, **kw):
        """A cut: the new beat's state from frame b (the previous beat holds its own until b - 1)."""
        self.riders = []
        self.duck_fn = duck or (lambda f: RIVER_DUCK)
        self.lv, self.hz = lv, hz
        self.stage(b, mode, **kw)
        self.lights(b, True)
        self.set_state(b, lv, hx, hz, 0.0)
        if self._sofa_last is not None and self._sofa_last[0] != tuple(self.sofa_rest):
            self.key_sofa(b - 1, *self._sofa_last)
        self.key_sofa(b, self.sofa_rest, 0.0)

    def lights(self, f, on):
        st.key_glow(self.glass, f, 2.6 if on else 0.0, constant=True)
        st.key_glow(self.bulb_mat, f, 9.0 if on else 0.0, constant=True)
        d = self.lamp.data
        d.energy = 150.0 if on else 0.0
        d.keyframe_insert("energy", frame=f)
        toy.set_interpolation(d, "energy", (f,), "CONSTANT")

    def label(self, text, loc, f0, f1, size=0.32):
        root = st.label(text, loc, f0, f1, size=size, tilt=-3)
        for f in (f0, f0 + 5, f0 + 8, f1 - 5, f1):
            root.scale = (1, 1, 1)
            root.keyframe_insert("scale", frame=f)
        lines = text.split("\n")
        w = 0.62 * size * max(len(s) for s in lines) / 2 + 0.1
        h = 0.62 * size * len(lines) + 0.1
        x, y, z = loc
        return [(x - w, y, z + h), (x + w, y, z - h)]

    # ------------------- camera -------------------

    def close(self, f0, f1, who=None, frac=0.42, angle=-90.0, swing=14.0, lens=32.0, side=0.0, step=3):
        """A moving close shot that follows `who` (also while he rides the floating house)."""
        who = who or self.max
        h = 1.9 if who is self.max else 1.15
        dist = st.frame_distance(h, frac, lens)
        keys = []
        for f in _frames(f0, f1, step):
            p = V(toy.value_at(who.root, "location", f))
            t = _sm((f - f0) / max(1, f1 - f0))
            a = R(angle - swing / 2 + swing * t)
            aim = p + V((side, 0.0, h * 0.52))
            cam = aim + V((math.cos(a) * dist, math.sin(a) * dist, h * 0.2 + 0.15))
            keys.append((f, cam, aim))
        self.rig.track(f0, f1, keys, lens=lens, fstop=5.6, cut=True)

    def track_all(self, f0, f1, things, angle=-90.0, rise=0.16, lens=28.0, margin=0.12, swing=8.0, pts=(),
                  pts_fn=None, step=4):
        """frame_all solved again every few frames, so a rising or drifting house stays framed."""
        from engine import framing
        keys = []
        for f in _frames(f0, f1, step):
            p = [tuple(q) for q in st._frame_points(things, (f,))] + [tuple(q) for q in pts]
            if pts_fn:
                p += [tuple(q) for q in pts_fn(f)]
            t = _sm((f - f0) / max(1, f1 - f0))
            cam, aim, _ = framing.solve(p, angle - swing / 2 + swing * t, rise, lens, margin)
            keys.append((f, V(cam), V(aim)))
        self.rig.track(f0, f1, keys, lens=lens, fstop=8.0, cut=True)

    # ------------------- gestures (hand keys only where no clip does it) -------------------

    def _arms(self, who, f0, f1, rot_l, rot_r, ramp=6):
        for j, rot in (("shoulderL", rot_l), ("shoulderR", rot_r)):
            who.key(j, f0 - ramp, rot_deg=(0, 0, 0))
            who.key(j, f0, rot_deg=rot)
            who.key(j, max(f0 + 1, f1 - 4), rot_deg=(rot[0], rot[1] * 1.05, rot[2]))
            who.key(j, f1 + ramp, rot_deg=(0, 0, 0))

    def v_arms(self, f0, f1, who=None):
        """Success: both arms up in a V (a one-arm thumbs-up reads as thumbs down on this rig)."""
        who = who or self.max
        self._arms(who, f0, f1, (0, -150, 0), (0, 150, 0))
        who.smile(f0, big=True)
        who.brows(f0, 0.6)
        who.brows(f1, 0.0)

    def shrug(self, f0, f1):
        m = self.max
        self._arms(m, f0 + 5, f1 - 2, (-15, -62, 0), (-15, 62, 0))
        m.key("head", f0, rot_deg=(0, 0, 0))
        m.key("head", f0 + 6, rot_deg=(-4, 0, 14))
        m.key("head", f1 - 4, rot_deg=(-4, 0, 16))
        m.key("head", f1 + 4, rot_deg=(0, 0, 0))
        m.brows(f0 + 6, 0.9)
        m.brows(f1, 0.0)
        events.add(f0 + 6, "boing", gain=0.3)

    def jaw_drop(self, f0, f1):
        """The one gasp of a beat: mouth open, brows up, hands out."""
        m = self.max
        m.key("mouth", f0 - 1, scale=(0.7, 0.6, 1.0))
        m.key("mouth", f0 + 3, scale=(1.2, 0.6, 2.6))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f0, 1.0)
        m.brows(f1, 0.0)
        self._arms(m, f0 + 3, f1 - 2, (-10, -60, 0), (-10, 60, 0), ramp=4)

    # ------------------- driver -------------------

    def run(self, beats, spans, epilogue_offset):
        self.EPI = epilogue_offset
        acts, sp = [], []
        for i, b in enumerate(beats):
            al = beat_actions(b)
            s, e = spans[i]
            weights = [sum(self.ACTIONS[a].get("seconds", (1, 1))) for a in al]
            t = s
            for k, (a, w) in enumerate(zip(al, weights)):
                end = e if k == len(al) - 1 else t + int((e - s + 1) * w / sum(weights)) - 1
                acts.append(a)
                sp.append((t, end))
                t = end + 1
        for i, a in enumerate(acts):
            if self.ACTIONS[a]["kind"] in ("hook", "rewind"):
                continue
            getattr(self, f"a_{a}")(i, *sp[i])
        hb, he = sp[0]
        getattr(self, f"a_{acts[0]}")(0, hb + epilogue_offset, he + epilogue_offset)
        self.rig.build()

    # ------------------- the ladder -------------------

    def a_fail_slab(self, i, b, e):
        L = e - b
        c, mid = b + int(L * 0.36), b + L // 2
        s2 = b + int(L * 0.6)
        r0, r1 = b + 4, b + int(L * 0.84)                    # rising from the start, still rising through 7/8
        top = 1.4
        self.begin(b, "slab", slab=True, dock=False, pontoon=False, gauge=True,
                   duck=lambda f: (-4.6 + 5.2 * _cl((f - r0) / max(1, e - r0)), 0.25, -9.0))
        g = self.gauge_grp                                   # the gauge stands beside the cabin, below Max's terrace
        g.location = (0.4, 0.0, 0.0)
        g.keyframe_insert("location", frame=b)
        m = self.max
        m.cut_place(b, self.world(PORCH), self.face_porch)
        m.act("idle", b, c)
        fa = b + int(L * 0.17)
        m.act("fold_arms", b + 2, fa)                        # 'the river never gets this high'
        m.smile(b + 4, big=True)
        m.look_at(fa + 2, (-4.9, 0.5, -0.4), hold=max(1, c - fa - 8))   # ...then he sees it climbing the bank
        m.point(fa + 4, c - 3, hand="R", up_deg=30, side_deg=55)
        m.brows(fa + 4, 0.9)
        m.brows(c - 2, 0.0)
        m.cut_place(c, TERRACE_EDGE, facing_to(TERRACE_EDGE, (1.0, -8.0, 1.8)))   # dry, right beside the gauge
        m.act("idle", c, e)
        m.turn(s2 - 10, facing_to(TERRACE_EDGE, (4.0, -8.0, 1.8)), frames=8)    # face toward the last camera
        self.ramp(r0, r1, NORMAL, top, floating=False)
        self.hold(e)

        def lv(f):
            return self.level_at(f, r0, r1, NORMAL, top)
        f_float = next((f for f in range(r0, r1 + 1) if lv(f) - 0.25 > FLOOR + 0.004), mid)
        f_float = min(f_float, s2 - 10)
        f_in = next((f for f in range(r0, r1 + 1) if lv(f) > 0.3), r0 + 10)
        f_lab = min(next((f for f in range(r0, r1 + 1) if lv(f) >= 0.9), mid - 2), mid - 2)
        for f in _frames(r0, e, 2):                          # the sofa lifts off and drifts across the back window
            z = max(FLOOR + 0.004, lv(f) - 0.25)
            u = _cl((f - f_float) / max(1, e - 4 - f_float))
            fl = f > f_float
            bob = 0.05 * math.sin(f * 0.25) * _cl((z - FLOOR - 0.004) / 0.1) if fl else 0.0
            self.key_sofa(f, (-1.6 + 2.7 * _sm(u), 3.78 - 0.3 * _sm(u), z + bob), 14.0 * math.sin(3.0 * u))
        leak = st.Jet("flood_leak", (-2.84, 2.3, 0.32), direction=(1.0, -0.35, 0.2), speed=2.6, color="#BFE6FF",
                      radius=0.07, drops=70, drop_size=0.05, spread=0.25, seed=9)
        leak.erupt(f_in, b + int(L * 0.7), rise=5)
        for k, z in enumerate((0.55, 1.0)):
            st.arrow(f"inflow_arrow{k}", (-4.3, 0.5, z), (1.0, 0, 0), f_in, e, color=BLUE, width=0.13)
        pts = self.label("1 m INSIDE", (3.0, -0.4, 4.45), f_lab, e, size=0.44)
        self.jaw_drop(mid - 4, mid + 14)
        m.act("no", mid + 16, b + int(L * 0.72))
        self.shrug(b + int(L * 0.74), e)
        events.add(r0, "water_rush", duration=r1 - r0, gain=0.5)
        events.add(f_in, "water_spray", duration=b + int(L * 0.7) - f_in, gain=0.3)
        events.add(f_float + 4, "splash", gain=0.4)
        # opening: from the river side, Max on his porch, the river climbing the bank below him, the cabin on its
        # slab and the marker post behind it (the angle folds the 8 m between them into depth, so Max stays big)
        st.frame_all(self.rig, b, c - 1, [m, self.gauge_parts[1], (-4.8, 0.3, -0.8), (-3.3, 0.0, -0.3),
                                          (-3.3, 0.3, 2.6)], angle=-150.0, rise=0.14, lens=28.0, margin=0.08,
                     push=0.05, swing=6.0, cut=True)
        # the section: water around and pouring in at the door, the gauge, the back window and Max
        st.frame_all(self.rig, c, s2, self.gauge_parts[:2] + [self.glass_back, m] + pts +
                     [(-4.35, 0.5, 1.0), (-3.1, 0.3, 0.2)], angle=-82.0, rise=0.12, lens=28.0, margin=0.1,
                     push=0.04, swing=5.0, cut=True)
        # closer, from the terrace side: Max big beside the gauge in front, the sofa floating across the back
        # window seen through the open cut as the water keeps rising
        st.frame_all(self.rig, s2, e, self.gauge_parts[:2] + [self.glass_back, m] + pts + [(0.0, 3.7, 0.6)],
                     angle=-64.0, rise=0.1, lens=28.0, margin=0.08, push=0.05, swing=5.0, cut=True)

    def a_fix_pontoon(self, i, b, e):
        L = e - b
        c, mid = b + int(L * 0.38), b + L // 2
        up = b + int(L * 0.2)
        r0, r1 = up + 2, b + int(L * 0.76)
        top = 1.3
        self.begin(b, "dry", dock=True, pontoon=True,
                   duck=lambda f: (-6.4 - 0.8 * (f - b) / max(1, L), 1.4, -9.0))
        for g in (self.dock_grp, self.pontoon_grp):           # the dock and the pontoon are built up from below
            g.location = (0, 0, -2.6)
            g.keyframe_insert("location", frame=b + 3)
            g.location = (0, 0, 0.0)
            g.keyframe_insert("location", frame=up)
        self.set_mode(up + 1, "open")
        events.add(b + 4, "rumble", duration=up - b - 4, gain=0.4)
        events.add(up, "clunk", gain=0.6)
        m = self.max
        m.cut_place(b, WORK, self.face_work())
        m.act("idle", b, c)
        m.act("talk", b + 3, up)                               # upright, face to camera (no bent-over 'fix' clip)
        m.point(up + 2, c - 3, hand="R", up_deg=20, side_deg=55)
        m.cut_place(c, self.world(PORCH), self.face_porch)
        m.act("idle", c, e)
        self.ramp(r0, r1, NORMAL, top)                        # the dock fills in the first shot, lifts it after
        self.hold(e)
        self.ride(m, PORCH, c, e)
        fa = next((f for f in range(r0, r1 + 1) if self.level_at(f, r0, r1, NORMAL, top) - FLOAT_AT >= 0.47), mid)
        fa = min(fa, mid - 4)
        arrows = []
        for k, x in enumerate((-2.3, -0.8, 0.8, 2.3)):
            a = st.arrow(f"buoy_arrow{k}", (x, -0.03, PBOT - 0.5), (0, 0, 0.45), fa, e, color=BLUE, width=0.22,
                         parent=self.house)
            arrows += list(a.children)
        pts = self.label("1 m³ WATER\n= 1 TONNE", (0.0, -0.4, 6.35), c + 6, e, size=0.44)
        m.brows(mid, 0.8)
        self.v_arms(b + int(L * 0.66), e - 3)
        events.add(r0, "water_rush", duration=r1 - r0, gain=0.4)
        events.add(b + int(L * 0.66), "cheer", gain=0.4)
        # Max beside the right half of the dock section: the dock and pontoon rise into place, the dock fills
        self.track_all(b, c, [m], angle=-96.0, rise=0.1, swing=6.0, margin=0.1,
                       pts=[(1.3, 0.0, -1.8), (1.3, 0.0, 1.0), (3.7, 0.0, -1.8), (3.7, 0.0, 0.1)])
        st.frame_all(self.rig, c, e, self.pontoon_parts + arrows + [m] + pts +
                     [(-3.7, 0.0, -1.75), (3.7, 0.0, -1.75), (3.7, 0.0, 0.05)], angle=-90.0, rise=0.12, lens=28.0,
                     margin=0.1, push=0.04, swing=6.0, cut=True)

    def a_fail_drift(self, i, b, e):
        L = e - b
        c = b + int(L * 0.34)
        d = c + int((e - c) * 0.45)

        def duck(f):                                         # paddles just off the bow, then overtakes the porch
            u = _cl((f - c) / max(1, e - c))
            return (self.hx - 3.9 - 1.3 * _sm(u), 0.32, -9.0)
        self.begin(b, "closed", lid=True, lv=1.4, hz=1.4 - FLOAT_AT, duck=duck)
        self.flood_extras(b, e)
        self.porch_balusters(b, e)
        self.duck_scale(b, e, 1.6)
        m = self.max
        m.cut_place(b, self.world(PORCH), self.face_porch)
        self.riders = [(m, PORCH)]
        m.act("idle", b, e)
        m.wave(b + 4, c - 2)
        m.smile(b + 4, big=True)
        self.ramp(b, c, 1.4, 1.5, x=lambda t: -2.4 * t * t)
        self.ramp(c + 1, e, 1.5, 1.5, x=lambda t: -2.4 - 15.0 * t ** 0.9, ease=False)
        self.wake(b, e, 1.5, "drift")
        m.turn(c + 2, facing_to(PORCH, (PORCH[0] - 3.0, PORCH[1] - 7.0, 0.0)), frames=10)
        m.wave(c + 6, e - 4)
        m.brows(c + 6, 1.0)
        events.add(c, "creak", gain=0.5)
        events.add(c + 4, "water_rush", duration=e - c - 4, gain=0.3)
        events.add(b + int(L * 0.7), "quack", gain=0.5)
        self.close(b, c, frac=0.42, side=-0.2)
        # the WHOLE house sliding out of the dock: the camera follows it only half way, so it visibly travels
        # across the frame past the fence posts (a close shot that follows the porch made it look parked)...
        self.lag_track(c, d, HOUSE_PTS + ((-5.4, 0.3, -0.1),), angle=-108.0, rise=0.24, margin=0.18, lag=0.5)
        # ...then close on Max out on the open river, the duck overtaking just ahead of the porch
        self.drift_cam(d, e, PORCH, frac=0.3, angle0=-100.0, angle1=-92.0, lag=0.2, side=-0.45, up=1.3)

    def a_fix_guides(self, i, b, e):
        L = e - b
        c, mid = b + int(L * 0.38), b + L // 2
        r0, r1 = c + 2, b + int(L * 0.82)
        self.begin(b, "open", posts=True, collars=False,
                   duck=lambda f: (-6.0 - 5.0 * _cl((f - b) / max(1, L)), 1.2, -9.0))
        g = self.posts_grp                                    # the posts are driven up from the dock floor
        g.scale = (1, 1, 0.02)
        g.keyframe_insert("scale", frame=b + 3)
        g.scale = (1, 1, 1)
        g.keyframe_insert("scale", frame=c - 6)
        self.vis("collars", [self.collars], c - 6, True)
        events.add(b + 6, "clank", duration=c - b - 12, gain=0.5)
        m = self.max
        m.cut_place(b, BANK, self.face_bank)
        m.act("idle", b, c)
        m.act("talk", b + 3, c - 3)                            # upright in his close shot (kneeling 'fix' = giant hat)
        m.point(b + 8, c - 4, hand="R", up_deg=20, side_deg=55)
        m.cut_place(c, self.world(PORCH), self.face_porch)
        self.riders = [(m, PORCH)]
        m.act("idle", c, e)
        self.ramp(r0, r1, NORMAL, 1.3)
        self.hold(e)
        pts = self.label("GUIDE POSTS", (-1.75, -0.35, -0.85), mid - 6, e, size=0.32)
        self.v_arms(b + int(L * 0.74), e - 3)
        events.add(r0, "water_rush", duration=r1 - r0, gain=0.4)
        self.close(b, c, side=-0.35)
        self.track_all(c, e, self.postL_parts + self.collarL_parts + [m], pts=pts)

    def a_fail_snap(self, i, b, e):
        L = e - b
        c, mid = b + int(L * 0.36), b + L // 2
        r0, r1 = b + int(L * 0.26), b + int(L * 0.66)
        top = 0.55                                            # the broken riser stays above the flood
        self.begin(b, "open", posts=True)
        self.vis("ubase", [self.base_grp, self.stubs], b + 6, True)
        self.vis("rigid", [self.rigid_grp], b + 6, True)
        events.add(b + 6, "pop", gain=0.4)
        m = self.max
        m.cut_place(b, WORK, self.face_work())
        m.act("idle", b, c)
        m.act("talk", b + 3, c - 3)                            # upright in his close shot (kneeling 'fix' = giant hat)
        m.point(b + 10, c - 4, hand="R", up_deg=20, side_deg=55)
        m.cut_place(c, TERRACE, facing_to(TERRACE, (3.0, -8.0, 1.8)))
        m.act("idle", c, e)
        self.ramp(r0, r1, NORMAL, top)
        self.hold(e)
        fs = next((f for f in range(r0, r1 + 1) if self.level_at(f, r0, r1, NORMAL, top) - FLOAT_AT > 0.02), mid - 4)
        fs = min(fs, mid - 4)
        jet = st.Jet("gusher_jet", (W_X, W_Y, W_Z + 0.02), direction=(0.12, -0.22, 1.0), speed=7.2, color="#DDF4FF",
                     radius=0.1, drops=120, drop_size=0.06, spread=0.28, seed=4)
        jet.erupt(fs, e, rise=4)
        sparks = Spray("spark_break", st.glow_mat("spark_hot", "#FFD43A", 14.0), count=40, radius=0.035, seed=12)
        for p in sparks.parts:
            p.location, p.scale = (0, 0, -60), (0.01, 0.01, 0.01)
            p.keyframe_insert("location", frame=1)
            p.keyframe_insert("scale", frame=1)
        sparks.run(fs, e, (P_X, P_Y, P_Z + 0.03), (P_X + 0.4, P_Y - 0.7, 0.75), spread=0.5, arc=0.6, period=9)
        self.smoke.emit(range(fs + 2, fs + 40, 3), lambda f: (P_X, P_Y, P_Z + 0.1), rise=0.9, life=24, drift=0.2)
        self.lights(fs, True)
        self.lights(fs + 2, False)
        self.lights(fs + 4, True)
        self.lights(fs + 7, False)
        self.jaw_drop(fs + 3, fs + 26)
        m.act("no", fs + 28, b + int(L * 0.8))
        self.shrug(b + int(L * 0.8), e)
        pts = self.label("FIXED TO\nTHE GROUND", (3.4, -0.3, 4.6), fs, e, size=0.3)
        events.add(fs, "snap", gain=0.8)
        events.add(fs, "spark", gain=0.6)
        events.add(fs + 2, "water_spray", duration=e - fs - 2, gain=0.6)
        events.add(fs + 7, "power_down", gain=0.5)
        self.close(b, c, side=0.25)
        glass_r = bpy.data.objects.get("cabin_glass_R")
        things = self.riser_parts + ([glass_r] if glass_r else []) + [m]
        # from the front-LEFT: the terrace is beside the riser, never between it and the camera
        self.track_all(c, e, things, angle=-98.0, rise=0.2, swing=6.0, margin=0.1,
                       pts=pts + [(W_X, W_Y, W_Z + 2.7), (W_X, 0.0, -2.4)],
                       pts_fn=lambda f: [self.world_f(f, (P_X, P_Y, P_Z + 0.1)), self.world_f(f, (2.92, 3.4, 1.9))])

    def a_fix_coils(self, i, b, e):
        L = e - b
        c, mid = b + int(L * 0.38), b + L // 2
        r0, r1 = c + 2, b + int(L * 0.82)
        self.begin(b, "open", posts=True, utils="base")
        self.vis("coils", [self.coils_grp], b + 6, True)
        events.add(b + 6, "pop", gain=0.4)
        m = self.max
        m.cut_place(b, BANK, self.face_bank)
        m.act("idle", b, c)
        m.act("talk", b + 3, c - 3)                            # upright in his close shot (kneeling 'fix' = giant hat)
        m.point(b + 10, c - 4, hand="R", up_deg=20, side_deg=55)
        m.cut_place(c, TERRACE, self.face_terrace)
        m.act("idle", c, e)
        self.ramp(r0, r1, NORMAL, 1.4)
        self.hold(e)
        pts = self.label("3 m SLACK", (4.05, -0.3, 3.75), mid - 6, e, size=0.34)
        m.brows(mid, 0.8)
        self.v_arms(b + int(L * 0.72), e - 3)
        events.add(r0, "water_rush", duration=r1 - r0, gain=0.4)
        events.add(r0 + 10, "spring_stretch", duration=r1 - r0 - 10, gain=0.4)
        self.close(b, c, side=0.25)
        # the stretched coil tops ride up with the house (their mesh bounds do not): frame them and the lit window
        self.track_all(c, e, self.coil_objs + [m], pts=pts,
                       pts_fn=lambda f: [self.world_f(f, (W_X, W_Y, W_Z + 0.12)), self.world_f(f, (P_X, P_Y, P_Z + 0.12)),
                                         self.world_f(f, (2.92, 2.9, 1.95))])

    def a_fail_lean(self, i, b, e):
        L = e - b
        c, mid = b + int(L * 0.38), b + L // 2
        r0, r1 = b + int(L * 0.3), b + int(L * 0.72)
        self.begin(b, "closed", lid=True, posts=True, utils="coil",
                   duck=lambda f: (-6.5 - 0.6 * (f - b) / max(1, L), 1.5, -9.0))
        hv = self.heavy
        self.vis("heavy", [hv], b + 5, True)
        hv.location = (0, 0, 0.8)
        hv.keyframe_insert("location", frame=b + 5)
        hv.location = (0, 0, 0.0)
        hv.keyframe_insert("location", frame=b + 14)
        events.add(b + 14, "thud", gain=0.7)
        m = self.max
        m.cut_place(b, WORK, self.face_work())
        m.act("idle", b, c)
        m.act("talk", b + 3, c - 3)                            # upright in his close shot (leaning 'push' = blurred hat)
        m.point(b + 10, c - 4, hand="R", up_deg=20, side_deg=55)
        m.cut_place(c, self.world(PORCH_IN), self.face_porch)
        m.act("idle", c, e)
        # a clear list to the heavy side: still tilting at 1/2, ~9.5 deg (jammed on the right posts) by 7/8
        self.ramp(r0, r1, NORMAL, 1.1, tilt=lambda t, hz: 9.5 * _sm(hz / 0.8))
        self.hold(e)
        self.ride(m, PORCH_IN, c, e)
        arrow = st.arrow("heavy_arrow", (2.35, 0.12, 2.5), (0, 0, -1.4), mid - 10, e, color="#FF4B3A", width=0.2,
                         parent=self.house)
        pts = self.label("TOP-HEAVY", (0.5, -0.25, 6.0), mid - 6, e, size=0.48)
        dust = Puffs("puff_scrape", "#CBBBA0", count=10, size=0.12, seed=6)   # the collar grinding on the post
        dust.emit(range(mid + 4, e - 6, 4), lambda f: self.world_f(f, (3.18, 0.45, 2.1)), rise=0.5, life=18,
                  drift=0.25)
        self.gasp_narrow(mid, mid + 18)
        self.shrug_narrow(b + int(L * 0.78), e)
        events.add(mid, "creak", gain=0.6)
        events.add(mid + 6, "scrape", duration=e - mid - 6, gain=0.5)
        furniture = ((2.3, 0.9, FLOOR), (2.45, 2.98, FLOOR + 1.35), (1.6, 4.2, FLOOR + 1.85), (0.7, 4.2, FLOOR))
        self.close(b, c, side=-0.35)
        # nearly square to the section, so the tilt reads against the level water line and the vertical posts
        self.track_all(c, e, self.wall_R + list(arrow.children) + [m], angle=-96.0, rise=0.1, swing=4.0,
                       margin=0.1, pts=pts + [(3.25, 0.4, -0.2), (3.25, 0.4, 4.2)],
                       pts_fn=lambda f: [self.world_f(f, q) for q in furniture])

    def a_fix_ballast(self, i, b, e):
        L = e - b
        c, mid = b + int(L * 0.4), b + L // 2
        drops = [b + int(L * k) for k in (0.2, 0.43, 0.52)]    # the blocks drop one by one, the last around 1/2
        r0, r1 = b + int(L * 0.58), b + int(L * 0.84)          # then the house rises level, done by 7/8
        top = 1.2
        self.begin(b, "open", posts=True, utils="coil", heavy=True,
                   duck=lambda f: (-6.5 - 0.6 * (f - b) / max(1, L), 1.5, -9.0))
        # the two front guide posts (and their collars) step out of this section so they never cover the pontoon
        for nm in ("guide_postL0", "guide_postL0_cap", "guide_postR2", "guide_postR2_cap",
                   "collarL0_0", "collarL0_0_arm", "collarL0_1", "collarL0_1_arm",
                   "collarR2_0", "collarR2_0_arm", "collarR2_1", "collarR2_1_arm"):
            ob = bpy.data.objects.get(nm)
            if ob is not None:
                toy.hide_tree(ob, b, True)
                toy.hide_tree(ob, e + 1, False)
        bg = self.ballast_grp
        toy.hide_tree(bg, b, False)
        self._shown["ballast"] = True
        byname = {o.name: o for o in self.ballast_parts}
        groups = (("ballast00", "ballast10"), ("ballast01", "ballast11", "ballast_top"), ("ballast02", "ballast12"))
        for d, group in zip(drops, groups):
            for n in group:
                ob = byname.get(n)
                if ob is None:
                    continue
                x, y, z = tuple(ob.location)
                toy.hide_tree(ob, b, True)
                toy.hide_tree(ob, d - 6, False)
                for s in (0, 3, 5, 7, 8):                     # falls under gravity from just under the deck
                    ob.location = (x, y, z + 0.6 * (1 - (s / 8) ** 2))
                    ob.keyframe_insert("location", frame=d - 6 + s)
                toy.set_interpolation(ob, "location", tuple(d - 6 + s for s in (0, 3, 5, 7)), "LINEAR")
                ob.location = (x, y, z + 0.04)
                ob.keyframe_insert("location", frame=d + 4)
                ob.location = (x, y, z)
                ob.keyframe_insert("location", frame=d + 6)
            events.add(d + 2, "thud", gain=0.8)
        m = self.max
        m.cut_place(b, self.world(PORCH), self.face_porch)
        self.riders = [(m, PORCH)]
        m.act("idle", b, e)
        m.act("talk", b + 3, max(b + 10, drops[0] - 8))
        self.ramp(r0, r1, NORMAL, top)                         # level: no tilt at all
        self.hold(e)
        m.point(drops[0] - 4, r0, hand="L", up_deg=25, side_deg=50)
        arrow = st.arrow("ballast_arrow", (0.0, -0.02, -0.12), (0, 0, -0.55), drops[0] - 8, e, color="#FFD23F",
                         width=0.16, parent=self.house)
        pts = self.label_ride("LOW BALLAST", (-1.6, -0.45, 1.75), mid - 8, e, size=0.42)
        self.v_arms(b + int(L * 0.8), e - 3)
        events.add(r0, "water_rush", duration=r1 - r0, gain=0.4)
        # the change: Max on the porch beside the open pontoon section, pointing down as the first blocks drop in
        st.frame_all(self.rig, b, c, [m, (-4.05, 0.06, PBOT - 0.05), (-0.45, 0.06, PBOT - 0.05),
                                      (-0.45, 0.06, 0.3)], angle=-86.0, rise=0.12, lens=28.0, margin=0.1,
                     push=0.05, swing=5.0, cut=True)
        # one steady section through the end: the last blocks drop into the pontoon, then the house rises level
        # out of the fixed dock
        hz1 = top - FLOAT_AT
        st.frame_all(self.rig, c, e, self.ballast_parts + list(arrow.children) + [m] + pts +
                     [(-3.7, 0.0, -1.75), (3.7, 0.0, -1.75), (3.3, 0.0, 2.7 + hz1)], angle=-90.0, rise=0.1,
                     lens=28.0, margin=0.1, push=0.04, swing=5.0, cut=True)

    def a_finale(self, i, b, e):
        L = e - b
        c = b + int(L * 0.36)
        r0, r1 = b + int(L * 0.2), b + int(L * 0.78)
        top = 2.7
        self.begin(b, "open", posts=True, utils="coil", heavy=True, ballast=True, kids=True, table=True, gauge=True,
                   duck=lambda f: (-7.7, 0.9 + 0.6 * (f - b) / max(1, L), -9.0))
        g = self.gauge_grp                                     # the gauge in the river right beside the porch
        g.location = (0.4, 0.0, 0.0)
        g.keyframe_insert("location", frame=b - 1)
        g.location = (GAUGE_FIN, 0.0, 0.0)
        g.keyframe_insert("location", frame=b)
        toy.set_interpolation(g, "location", (b - 1,), "CONSTANT")
        # brighter windows and lamp (they must read lit in daylight)
        st.key_glow(self.glass, b, 7.0, constant=True)
        st.key_glow(self.bulb_mat, b, 30.0, constant=True)
        d = self.lamp.data
        d.energy = 600.0
        d.keyframe_insert("energy", frame=b)
        toy.set_interpolation(d, "energy", (b,), "CONSTANT")
        self.lights(e + 1, True)
        # a bigger cake and two plates with slices on the table
        cake = next((o for o in self.table_grp.children if "cake" in o.name.lower()), None)
        ztop = FLOOR + 0.75
        if cake is not None:
            ztop = cake.location.z - 0.01
            cake.scale = (1.7, 1.7, 1.7)
        plate_m = tx.paint("table_plate_white", "#FFFFFF", 0.3)
        cream = bpy.data.materials.get("cake_slice_cream")
        for k, x in enumerate((-1.05, -0.15)):
            p = toy.cylinder(f"table_plate{k}", 0.13, 0.016, (x, 2.55, ztop + 0.009), mat=plate_m,
                             parent=self.table_grp, vertices=24)
            s = toy.box(f"table_slice{k}", (0.11, 0.08, 0.07), (x, 2.55, ztop + 0.053), mat=cream,
                        parent=self.table_grp, bevel=0.01)
            for o in (p, s):
                toy.hide_tree(o, 1, True)
                toy.hide_tree(o, b, False)
                toy.hide_tree(o, e + 1, True)
        m = self.max
        m.cut_place(b, self.world(FIN_PORCH), facing_to(FIN_PORCH, (-2.0, -8.0, 0.0)))
        for k, kid in enumerate(self.kids):
            kid.cut_place(b, self.world(KIDS_AT[k]), 0)
            kid.act("idle", b, e)
            kid.smile(b + 6, big=True)
            sl = bpy.data.objects.get(f"cake_slice{k}")
            if sl is not None:
                sl.scale = (1.8, 1.8, 1.8)
            f = b + 8 + 7 * k                                  # bites: the slice comes up to the mouth, chew, down
            while f + 22 < e:
                kid.key("shoulderR", f, rot_deg=(-15, 0, 0))
                kid.key("shoulderR", f + 8, rot_deg=(-88, 0, 0))
                kid.key("shoulderR", f + 14, rot_deg=(-88, 0, 0))
                kid.key("head", f + 8, rot_deg=(0, 0, 0))
                kid.key("head", f + 10, rot_deg=(7, 0, 0))
                kid.key("head", f + 13, rot_deg=(-3, 0, 0))
                kid.key("head", f + 16, rot_deg=(5, 0, 0))
                kid.key("head", f + 20, rot_deg=(0, 0, 0))
                kid.key("shoulderR", f + 21, rot_deg=(-15, 0, 0))
                f += 26
        self.riders = [(m, FIN_PORCH)] + [(kid, KIDS_AT[k]) for k, kid in enumerate(self.kids)]
        self.ramp(r0, r1, NORMAL, top)                         # rising through 1/2, at 2.7 m on the gauge by 7/8
        self.hold(e)
        fb = next((f for f in range(r0, r1 + 1) if self.level_at(f, r0, r1, NORMAL, top) - FLOAT_AT > 0.2), r0 + 10)
        self.vis("boat", [self.boat_grp], fb, True)
        events.add(fb, "pop", gain=0.3)
        m.act("idle", b, e)
        m.wave(b + 6, c - 2)
        m.smile(b + 6, big=True)
        self.v_arms(b + int(L * 0.62), e - 3)
        events.add(r0, "water_rush", duration=r1 - r0, gain=0.5)
        events.add(b + int(L * 0.8), "kids_cheer", gain=0.7)
        self.close(b, c, frac=0.4, side=0.35)
        # a steady frame: the house visibly climbs the gauge and leaves the fixed dock rim below
        hz1 = top - FLOAT_AT
        st.frame_all(self.rig, c, e, self.porch_parts + self.kids + [m] + self.gauge_parts[:2] +
                     [(-0.6, 2.85, FLOOR + 1.0 + hz1), (-3.55, 0.0, 0.05), (-2.0, 0.0, 0.05)],
                     angle=-100.0, rise=0.1, lens=28.0, margin=0.1, push=0.04, swing=5.0, cut=True)

    # ------------------- hooks (epilogue, after the finale) -------------------

    def a_drift_hook(self, i, h0, h1):
        L = h1 - h0
        hx0, run, lv = -7.5, 16.0, 1.5                         # racing down the flooded river from frame 1
        hz0 = lv - FLOAT_AT
        self.begin(h0, "closed", lid=True, lv=lv, hz=hz0, hx=hx0,
                   duck=lambda f: (self.hx - 5.6, 1.6, -9.0))
        self.flood_extras(h0, h1 + 30)
        self.porch_balusters(h0, h1)
        self.duck_scale(h0, h1, 1.4)
        m = self.max
        m.cut_place(h0, self.world(PORCH_IN), facing_to(PORCH_IN, (PORCH_IN[0] - 4.0, PORCH_IN[1] - 6.0, 0.0)))
        self.riders = [(m, PORCH_IN)]
        m.act("idle", h0, h1)
        for f in _frames(h0, h1, 2):                           # fast, bobbing and pitching
            t = (f - h0) / max(1, L)
            self.set_state(f, lv, hx0 - run * t, hz0 + 0.1 * math.sin(f * 0.45 + 0.6),
                           3.5 * math.sin(f * 0.3 + 0.9))
        self.wake(h0, h1, lv, "hook")
        # frantic waving from the first frame, then the gasp with both arms flung up
        w1 = h0 + int(L * 0.48)
        m.key("shoulderL", h0, rot_deg=(0, -20, 0))
        for k, f in enumerate(range(h0, w1, 5)):
            m.key("shoulderR", f, rot_deg=(0, 160 if k % 2 == 0 else 118, 0))
        m.smile(h0, big=True)
        m.brows(h0, 0.8)
        g0 = w1 + 2
        m.key("mouth", g0 - 1, scale=(0.7, 0.6, 1.0))
        m.key("mouth", g0 + 3, scale=(1.2, 0.6, 2.6))
        m.key("mouth", h1, scale=(1.15, 0.6, 2.4))
        m.key("mouth", h1 + 6, scale=(0.7, 0.6, 1.0))
        m.brows(g0, 1.0)
        m.brows(h1 + 6, 0.0)
        for j, sg in (("shoulderL", -1), ("shoulderR", 1)):
            m.key(j, g0 + 4, rot_deg=(0, sg * 145, 0))
            m.key(j, h1, rot_deg=(0, sg * 152, 0))
            m.key(j, h1 + 8, rot_deg=(0, 0, 0))
        events.add(h0, "water_rush", duration=L, gain=0.6)
        events.add(h0, "water_spray", duration=L, gain=0.3)
        events.add(g0, "creak", gain=0.5)
        # the whole racing cabin from ahead of its bow (the camera trails it, the bank posts stream past), then
        # close on Max's face for the gasp
        s = h0 + int(L * 0.5)
        # frame 1: the whole cabin racing past the flooded posts and willows, its wake spraying (the camera follows
        # it only half way, so the speed reads; a close on the porch made the house look parked)
        self.lag_track(h0, s, HOUSE_PTS + ((-6.2, 0.3, -0.1),), angle=-122.0, rise=0.2, margin=0.14, lag=0.5)
        self.drift_cam(s, h1, PORCH_IN, frac=0.36, angle0=-124.0, angle1=-114.0, lag=0.0, side=0.0, up=0.5)

    def a_rise_hook(self, i, h0, h1):
        L = h1 - h0
        m1 = h0 + int(L * 0.45)
        self.begin(h0, "open", posts=True, utils="coil", heavy=True, ballast=True, kids=True, table=True, boat=True,
                   lv=0.1, hz=0.1 - FLOAT_AT, duck=lambda f: (-7.7, 1.2, -9.0))
        m = self.max
        m.cut_place(h0, self.world(PORCH), self.face_porch)
        for k, kid in enumerate(self.kids):
            kid.cut_place(h0, self.world(KIDS_AT[k]), 0)
            kid.act("dance", h0, h1)
        self.riders = [(m, PORCH)] + [(kid, KIDS_AT[k]) for k, kid in enumerate(self.kids)]
        m.act("idle", h0, h1)
        self.v_arms(h0 + 6, h1 - 3)
        self.ramp(h0, h0 + int(L * 0.6), 0.1, 2.7, ease=False)
        self.hold(h1)
        events.add(h0, "water_rush", duration=L, gain=0.6)
        events.add(h0 + 8, "kids_cheer", gain=0.6)
        self.rig.shot(h0, m1, cam_from=(-1.2, -13.0, 2.6), cam_to=(-1.4, -12.4, 3.6), aim_from=(-1.2, 2.0, 1.4),
                      aim_to=(-1.4, 2.0, 2.6), lens=26.0, fstop=8.0, cut=True)
        self.close(m1, h1, frac=0.42, side=0.35)

    def face_work(self):
        return facing_to(WORK, (1.5, -8.0, 0.0))

    def ride(self, who, loc, f0, f1, step=2):
        """Key a character standing on the house (also tilted / lifted) from f0 to f1."""
        for f in _frames(f0, f1, step):
            who.root.location = self.world_f(f, loc)
            who.root.keyframe_insert("location", frame=f)

    def flood_extras(self, f0, f1):
        """A shallow sandy flood plain under the river (no dark void below the floating house), a row of flooded
        fence posts and two flooded willows: fixed marks the drifting house visibly passes (drift beats only)."""
        if not hasattr(self, "_flood_objs"):
            sand = toy.noise_material("river_bed_sand", toy.srgb("#C9A66B"), toy.srgb("#A4824E"), scale=6, bump=0.2)
            wood = tx.wood("river_post_wood", "#6B4A2E", "#8A6240")
            objs = [bx("river_bed", -31.0, -3.78, 0.07, 34.0, -2.75, -0.2, sand)]
            for k in range(9):
                objs.append(toy.cylinder(f"river_post{k}", 0.11, 2.6, (-5.0 - 2.0 * k, 5.6 + 0.3 * (k % 2), 1.0),
                                         mat=wood, vertices=12))
            for k, (x, y) in enumerate(((-11.0, 9.5), (-19.0, 10.5))):
                tree = bk.prop("willow tree", 8.0, fallback=self._fb_tree, name=f"tree_flood{k}")
                tree.location = (x, y, -0.25)
                tree.rotation_euler = (0, 0, R(50 + 70 * k))
                objs.append(tree)
            for o in objs:
                toy.hide_tree(o, 1, True)
            self._flood_objs = objs
        for o in self._flood_objs:
            toy.hide_tree(o, f0, False)
            toy.hide_tree(o, f1 + 1, True)

    def lag_track(self, f0, f1, local_pts, angle=-110.0, rise=0.28, lens=26.0, margin=0.14, lag=0.35, swing=6.0,
                  step=3, ref_f=None):
        """Frame the whole drifting house, but let the camera follow it only (1 - lag) of the way, so the house
        visibly travels across the frame and past the fixed river marks (ref_f: the frame where it is centred)."""
        from engine import framing
        ref = toy.value_at(self.house, "location", (f0 + f1) // 2 if ref_f is None else ref_f)[0]
        keys = []
        for f in _frames(f0, f1, step):
            p = [self.world_f(f, q) for q in local_pts]
            t = _sm((f - f0) / max(1, f1 - f0))
            cam, aim, _ = framing.solve(p, angle - swing / 2 + swing * t, rise, lens, margin)
            hx = toy.value_at(self.house, "location", f)[0]
            sh = V((lag * (ref - hx), 0.0, 0.0))
            keys.append((f, V(cam) + sh, V(aim) + sh))
        self.rig.track(f0, f1, keys, lens=lens, fstop=8.0, cut=True)

    def gasp_narrow(self, f0, f1):
        """The one gasp, hands forward (no arm reaches the porch rail or the door wall)."""
        m = self.max
        m.key("mouth", f0 - 1, scale=(0.7, 0.6, 1.0))
        m.key("mouth", f0 + 3, scale=(1.2, 0.6, 2.6))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f0, 1.0)
        m.brows(f1, 0.0)
        self._arms(m, f0 + 3, f1 - 2, (-40, -32, 0), (-40, 32, 0), ramp=4)

    def shrug_narrow(self, f0, f1):
        m = self.max
        self._arms(m, f0 + 5, f1 - 2, (-35, -38, 0), (-35, 38, 0))
        m.key("head", f0, rot_deg=(0, 0, 0))
        m.key("head", f0 + 6, rot_deg=(-4, 0, 14))
        m.key("head", f1 - 4, rot_deg=(-4, 0, 16))
        m.key("head", f1 + 4, rot_deg=(0, 0, 0))
        m.brows(f0 + 6, 0.9)
        m.brows(f1, 0.0)
        events.add(f0 + 6, "boing", gain=0.3)

    def label_ride(self, text, local, f0, f1, size=0.4):
        """A callout that rides with the house (keyed to its local point every 2 frames)."""
        root = st.label(text, local, f0, f1, size=size, tilt=-3)
        for f in (f0, f0 + 5, f0 + 8, f1 - 5, f1):
            root.scale = (1, 1, 1)
            root.keyframe_insert("scale", frame=f)
        for f in _frames(f0 - 2, f1, 2):
            root.location = self.world_f(f, local)
            root.keyframe_insert("location", frame=f)
        lines = text.split("\n")
        w = 0.62 * size * max(len(s) for s in lines) / 2 + 0.1
        h = 0.62 * size * len(lines) + 0.1
        pts = []
        for f in (f0, f1):
            x, y, z = self.world_f(f, local)
            pts += [(x - w, y, z + h), (x + w, y, z - h)]
        return pts

    def porch_balusters(self, f0, f1):
        """Balusters under the porch rail, plus an edge beam, two joists and two knee braces that carry the deck on
        the pontoon's side (the drifting shots read the porch as one built, supported deck)."""
        if not hasattr(self, "_balusters"):
            trim = bpy.data.materials.get("cabin_trim")
            wood = bpy.data.materials.get("porch_wood") or trim
            H = self.house
            self._balusters = []
            for k in range(7):
                y = 0.69 + (3.51 - 0.69) * (k + 1) / 8
                self._balusters.append(toy.cylinder(f"porch_baluster{k}", 0.022, 0.79, (-4.33, y, 0.595), mat=trim,
                                                    parent=H, vertices=8))
            self._balusters.append(bx("porch_beam_edge", -4.40, -4.22, 0.62, 3.58, -0.06, 0.125, wood, parent=H))
            ang = math.atan2(0.83, 1.13)
            ln = math.hypot(0.83, 1.13)
            for k, y in enumerate((0.72, 3.48)):
                self._balusters.append(bx(f"porch_joist{k}", -4.38, -3.12, y - 0.06, y + 0.06, -0.04, 0.12, wood,
                                          parent=H))
                self._balusters.append(toy.box(f"porch_brace{k}", (ln, 0.1, 0.1), (-3.685, y, -0.435), mat=wood,
                                               parent=H, rotation=(0, ang, 0)))
            for o in self._balusters:
                toy.hide_tree(o, 1, True)
        for o in self._balusters:
            toy.hide_tree(o, f0, False)
            toy.hide_tree(o, f1 + 1, True)

    def wake(self, f0, f1, lv, tag):
        """A curling bow wave with a foam lip piled against the pontoon's bow, two foam streaks behind the stern and
        low splashes thrown off the bow toward the camera (never up through the porch), scaled by the speed."""
        foam_m = toy.material("water_foam", toy.srgb("#F2FAFF"), roughness=0.55)
        wave_m = toy.material("water_bow_wave", toy.srgb("#3D9FD8"), roughness=0.08)
        drop_m = toy.material("water_spray_drop", toy.srgb("#DCF1FF"), roughness=0.15)
        bow = toy.empty(f"water_bowwave_{tag}", (0, 0, -60))
        st.prism(f"water_bowwave_body_{tag}", [(0.02, -0.14), (0.02, 0.3), (-0.24, 0.42), (-0.5, 0.36),
                                               (-0.42, 0.27), (-0.8, 0.09), (-1.4, 0.0), (-1.4, -0.14)],
                 0.08, 4.45, mat=wave_m).parent = bow
        st.prism(f"water_bowwave_lip_{tag}", [(0.04, 0.26), (0.04, 0.33), (-0.24, 0.46), (-0.54, 0.38),
                                              (-0.44, 0.24), (-0.3, 0.33), (-0.1, 0.3)],
                 0.03, 4.5, mat=foam_m).parent = bow
        trails = [toy.sphere(f"water_foam_wake{k}_{tag}", 1.0, (0, 0, -60), scale=(1.9, 0.32, 0.05), mat=foam_m)
                  for k in range(2)]

        def hx(f):
            return toy.value_at(self.house, "location", f)[0]

        def speed(f):
            return (hx(f + 1) - hx(f - 1)) * 15.0          # m/s (30 fps)

        for f in _frames(f0, f1, 2):
            x, v = hx(f), speed(f)
            sp = min(1.0, abs(v) / 4.0)
            bow.location = (x - PX - 0.01, 0.0, lv - 0.02)
            bow.scale = (0.35 + 0.75 * sp, 1.0, 0.25 + 0.6 * sp)
            bow.keyframe_insert("location", frame=f)
            bow.keyframe_insert("scale", frame=f)
            for k, tr in enumerate(trails):
                ln = 0.6 + 1.6 * sp
                tr.location = (x + 3.1 + ln, (0.5, 4.1)[k], lv + 0.005)
                tr.rotation_euler = (0, 0, R((-7, 7)[k]))
                tr.scale = (ln, 0.32, 0.05)
                tr.keyframe_insert("location", frame=f)
                tr.keyframe_insert("scale", frame=f)
                tr.keyframe_insert("rotation_euler", frame=f)
        objs = [bow] + trails
        rnd = random.Random(31 + len(tag))
        life = 14
        n = 26
        for k in range(n):
            d = toy.sphere(f"water_drop_{tag}{k}", rnd.uniform(0.035, 0.065), (0, 0, -60), mat=drop_m, subdiv=1)
            objs.append(d)
            y, vy = rnd.uniform(0.06, 0.4), rnd.uniform(-1.3, -0.4)
            up, fwd = rnd.uniform(1.6, 2.8), rnd.uniform(0.3, 1.0)
            fl = f0 + int(k * (life + 1) / n)
            d.scale = (0, 0, 0)
            d.keyframe_insert("scale", frame=f0)
            while fl + life < f1:
                v = speed(fl)
                sp = min(1.0, abs(v) / 4.0)
                p0 = V((hx(fl) - PX - 0.1 - 0.3 * rnd.random(), y, lv + 0.1))
                vel = V((v - fwd * (0.4 + sp), vy, up * (0.35 + 0.65 * sp)))
                for s in (0, 2, 4, 6, 8, 10, 12, 14):
                    tt = s / 30.0
                    d.location = p0 + vel * tt + V((0, 0, -4.9 * tt * tt))
                    d.keyframe_insert("location", frame=fl + s)
                for s, sc in ((0, 1.0), (life - 4, 1.0), (life, 0.0)):
                    d.scale = (sc, sc, sc)
                    d.keyframe_insert("scale", frame=fl + s)
                fl += life + 1
        for o in objs:
            toy.hide_tree(o, 1, True)
            toy.hide_tree(o, f0, False)
            toy.hide_tree(o, f1 + 1, True)

    def drift_cam(self, f0, f1, loc, frac=0.3, angle0=-120.0, angle1=-110.0, lag=0.15, lens=26.0, up=1.2, side=0.0,
                  step=2):
        """A moving close shot on a rider of the drifting house (world space, house-local `loc`). The camera trails
        the house by `lag` around the shot's middle, so the house visibly slides across the frame and past the
        fixed river marks while the rider stays big."""
        h = 1.9
        dist = st.frame_distance(h, frac, lens)
        ref = self.world_f((f0 + f1) // 2, loc)[0]
        keys = []
        for f in _frames(f0, f1, step):
            p = V(self.world_f(f, loc))
            t = _sm((f - f0) / max(1, f1 - f0))
            a = R(angle0 + (angle1 - angle0) * t)
            aim = V((p.x + lag * (ref - p.x) + side, p.y + 0.2, p.z + h * 0.5))
            cam = aim + V((math.cos(a) * dist, math.sin(a) * dist, up))
            keys.append((f, cam, aim))
        self.rig.track(f0, f1, keys, lens=lens, fstop=8.0, cut=True)

    def duck_scale(self, f0, f1, s=1.5):
        """The duck reads bigger for one drifting beat only (back to its own size before and after)."""
        d = self.duck
        for f, k in ((f0 - 1, 1.0), (f0, s), (f1, s), (f1 + 1, 1.0)):
            d.scale = (k, k, k)
            d.keyframe_insert("scale", frame=f)
        toy.set_interpolation(d, "scale", (f0 - 1, f0, f1), "CONSTANT")
