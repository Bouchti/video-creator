"""
IMMERSED UNDERSEA TUNNEL story set: ONE vertical cutaway of a narrow sea strait. Max wants to drive his family
car under the sea to his kids' island picnic; each naive attempt fails for a real reason and each fix is how
immersed-tube tunnels are really built. The cut face is the plane y = 0; the camera looks along +Y.

ASSET PLAN (real object -> real shape / proportions -> the detail that reads at a glance -> how it is built)
- Sea strait: 40 m deep strait (scene: 8 units) between two shores -> a translucent blue water VOLUME cut open
  at the front like an aquarium -> st.Reservoir("sea").
- Layered seabed: soft sand on top, dark soaked clay below, rock at depth, grey gravel lenses -> ONE z-banded
  procedural ground material shared by every ground prism (layers line up across beach, seabed, island),
  low-poly icosphere gravel lenses half out of the cut face.
- Beach + dry dock (left): sandy shore; a rectangular concrete basin with a steel gate at the water's edge ->
  front ground prisms (plain / bored / dock / final-with-ramps variants, swapped at cuts), st.concrete lining,
  painted steel gate that sinks into its slot, st.Reservoir("dock"), plus a clearly tinted flood volume with a
  rippling skin (made after the colour grade) that rises when the dock is flooded in front of the viewer.
- Max's dig: a shaft from the beach and a horizontal drift under the submerged shore; a mud volume floods it;
  blue sea-pressure arrows squeeze the soaked clay in on the drift.
- Island + picnic (right): grassy top, a red blanket, a wicker basket, a tree; the two kids wait there.
- Trench: the seabed strip in front of the cut is an 8-chunk "plug" a grab dredger scoops out chunk by chunk;
  the trench water sits inside the plug and shows in every hole the grab opens.
- Tunnel element (x3): a long concrete box (6 x 4.4 x 2.8) with TWO road bores side by side, a middle wall,
  asphalt road, ceiling lamps -> boxes in st.concrete; the front wall is the removable cutaway.
- Bulkheads: flat orange steel plates closing each bore, set back inside the open ends, with a stiffener rib.
- Ballast tanks: steel frames inside bore 1 whose blue water fill visibly rises; red valve handwheels.
- Gasket: a fat black rubber ring around the leading end (4 capsules) that squashes (scale) when clamped.
- The leak gap: a dark slot between block one and the badly seated block two.
- Jacks: a steel barrel on block 1's roof and a rod on block 2's roof.  Pump: yellow box + hose.
- Inner safety seal: a black rubber strip with steel clamp bars across the joint inside.
- Tugboats: red hull prisms with a white wheelhouse and funnel; towlines.  Winch barge: grey pontoon with an
  A-frame reaching over the trench, two winch cables down to the roof bollards.
- Grab dredger: blue barge, yellow crane cab, boom, cable and a CLAMSHELL grab bucket (~1 m: steel head, two
  orange jaws on hinges that open wide, bite shut on a mud load and lift) -> boxes on pivot empties.
- Ship: dark hull prism with a red waterline band, white superstructure, funnel; a chain and a cone anchor.
  A second, bigger RED anchor (crown, flukes, shank, stock) for the bounce, so it reads against the rocks.
- Stone-dumping vessel: yellow hull with a gravel hopper and a vertical fall pipe pouring gravel.
- Locking gravel / backfill / rock armour: gravel strips along both sides, a sand-gravel layer, a DENSE two-layer
  blanket of low-poly rocks (one merged mesh per segment) laid segment by segment.
- Seagull (running gag): cone-and-plane bird (white body, grey wings, orange beak and legs); copies on Max's
  hat and on the car's dashboard.  Fish: orange body + tail (lands on Max's hat brim).
- Family car: open-top blue car with low seats, dashboard, windshield, rubber tyres, headlights.
- Scale model: a table with a blue strait, two green shores and a chain of 89 tiny blocks in two alternating
  colours (so each block reads), Max standing right behind it.
Everything is built from primitives with engine.studio / engine.textures materials. No downloaded assets.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from engine import events, studio as st, textures as tx, toy
from engine.camera import CameraRig
from engine.character import Character
from engine.machines import Puffs, Spray
from engine.sets.immersed_undersea_tunnel_con_story_spec import ACTIONS, beat_actions

R = math.radians
V = Vector

D = 14.0                         # diorama depth behind the cut face
BOT = -30.0
SEABED = -8.0
BACK_TOP = SEABED - 0.01         # back strip seabed top (1 cm under the front, never coplanar)
TRENCH = -10.4
STRIP = 4.9                      # front ground strip (the trench) width in y
L = 6.0                          # element length
HH = 1.4                         # element half height
TUBE_Z = TRENCH + HH + 0.01
ROAD = TUBE_Z - 1.0              # road surface in bore 1
G0, GS = 0.55, 0.5               # gasket protrusion, squashed scale
XB = -12.4                       # beach face of the strait
SX = [XB + 3.0, XB + 6.0 + G0 * GS + 3.0, XB + 12.0 + 2 * G0 * GS + 3.0]
XI = SX[2] + 3.0 + 0.01          # island face of the strait
SX_LEAK = SX[0] + 3.0 + 0.14 + 3.0
RH = 2.3                         # approach ramp clear height
LX0, RX1 = -50.0, 48.0           # ramp tops on the beach / island
DOCK_X0, DOCK_X1 = -22.0, -14.4
DOCK_FLOOR = -3.2
S1_DOCK = (-18.2, 0.0, DOCK_FLOOR + HH + 0.01)
FLOAT_Z = -0.95
FLOAT_HI = -0.35                 # the sealed, empty box rides high in the flooded dock (draft 1.75)
GRASS_X = 49.0
GRASS_Z = 0.86
KID_SPOTS = [(53.6, 1.7, 0.915), (54.7, 2.1, 0.915)]   # on the blanket (top 0.90), never inside it
BLUE, YELLOW = "#3FA9FF", "#FFD23F"
DIG_Z = -10.75                   # floor of Max's dug drift (2.73 m clear: his hat and raised brows stay well under it)
DIG_TOP = SEABED - 0.02          # drift roof: below the sea volume, so no water inside the bore
SEAT_OFF = (-0.45, -0.28, 0.15)  # Max's root in the car, on the low driver's seat
SEAT_FACE = 78.0
ARMOUR_TOP = -6.45               # top of the rock blanket where the anchor strikes
ANCHOR_LIFT = 0.82               # the big anchor's origin above the surface it rests on


def fr(b, e, t):
    return int(round(b + (e - b) * t))


def lfloor(x):
    """Left approach ramp floor line (beach), from (LX0, 0.5) down to the tunnel road at XB."""
    return 0.5 + (ROAD - 0.05 - 0.5) * (x - LX0) / (XB - LX0)


def rfloor(x):
    """Island approach ramp floor line, from the tunnel road at XI up to (RX1, 0.8)."""
    return ROAD - 0.05 + (0.8 - ROAD + 0.05) * (x - XI) / (RX1 - XI)


L_PORTAL = LX0 + RH * (XB - LX0) / (0.5 - ROAD + 0.05)
R_PORTAL = XI + (0.8 - ROAD + 0.05 - RH) / (0.8 - ROAD + 0.05) * (RX1 - XI)
RAMP_K = (0.8 - ROAD + 0.05) / (RX1 - XI)


class _Who:
    """Lets studio.close_on follow a plain object (it reads .root)."""

    def __init__(self, obj):
        self.root = obj


def beam(name, p0, p1, w, mat, parent=None, h=None):
    p0, p1 = V(p0), V(p1)
    d = p1 - p0
    ob = toy.box(name, (w, h or w, d.length), (p0 + p1) / 2, mat=mat, parent=parent, bevel=0.01)
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return ob


def merged(name, items, mat, kind="ico", jitter=0.0, seed=1):
    """One static mesh of many low-poly rocks / blocks: items = [(center, (sx, sy, sz), yaw)]."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    for c, s, yaw in items:
        mtx = Matrix.Translation(V(c)) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Diagonal((s[0], s[1], s[2], 1.0))
        if kind == "ico":
            res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0, matrix=mtx, calc_uvs=False)
        else:
            res = bmesh.ops.create_cube(bm, size=1.0, matrix=mtx, calc_uvs=False)
        if jitter:
            for v in res["verts"]:
                v.co += V((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * jitter * min(s)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    return ob


def cone(name, r1, r2, depth, loc, rot, mat, parent=None):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=depth, vertices=16, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    toy._finish(ob, mat, subdiv=0, parent=parent)
    return ob


class ImmersedUnderseaTunnelConStorySet:
    ACTIONS = ACTIONS
    QA_ALLOW = (r"front_|back_ground|chunk|sea_|dock|S[123]_|tunnel_light|gasket|arrow|label|grab|dredger"
                r"|cable|tug|tow|winch|ship|anchor|chain|stoner|lock|backfill|armour|rock|lens|car|road|seal"
                r"|jack|pump|bore|flood|mud|leak|gull|fish|far_|ruler|picnic|blanket|basket|table|scale_model"
                r"|tree|ramp|tw_|shovel|grass|crack|joint|_grip|puff|Spray|drops|squirt")

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self.rnd = random.Random(17)
        self.groups = {}
        self._lit = False
        self._seated_end = None
        self._dock_lvl = DOCK_FLOOR + 0.02
        self._materials()
        self._ground()
        self._dock()
        self._ruler_and_bore()
        self.S = {k: self._section(k) for k in (1, 2, 3)}
        self._joint_parts()
        self._boats()
        self._anchor_b()
        self._fill_layers()
        self._car()
        self._picnic_and_model()
        self._people()
        self._critters()
        self._colour_grade()
        self._dock_flood()
        self._initial()

    # ------------------- materials -------------------

    def _colour_grade(self):
        """Set-wide toy look: CLEAR bright-blue water with a crisp surface (no haze), warm sun, white clouds."""
        for mat in list(bpy.data.materials):
            if not mat.use_nodes or mat.node_tree is None:
                continue
            for n in mat.node_tree.nodes:
                if n.type == "VOLUME_SCATTER":
                    n.inputs["Density"].default_value = 0.015
                    n.inputs["Color"].default_value = (*toy.srgb("#7FD2FF"), 1)
                elif n.type == "VOLUME_ABSORPTION":
                    n.inputs["Color"].default_value = (*toy.srgb("#2FA4F5"), 1)
                    n.inputs["Density"].default_value = min(n.inputs["Density"].default_value, 0.14)
            if mat.name.endswith("_surface") and getattr(mat, "surface_render_method", "") == "BLENDED":
                bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf is not None:
                    bsdf.inputs["Base Color"].default_value = (*toy.srgb("#33C2F7"), 1)
        if self.sun is not None and getattr(self.sun, "data", None) is not None:
            self.sun.data.color = (1.0, 0.88, 0.7)
        try:
            vs = self.scene.view_settings
            if vs.view_transform == "AgX":
                vs.look = "AgX - Punchy"
        except Exception:
            pass
        # white cumulus clouds in the blue sky, far behind the strait
        cloud = toy.material("ut_cloud", (0.95, 0.96, 1.0), roughness=0.9)
        crnd = random.Random(41)
        for k, (cx, cy, cz) in enumerate(((-110, 330, 70), (-30, 360, 92), (60, 320, 64), (150, 380, 100),
                                          (-190, 400, 110), (10, 300, 48))):
            for j in range(5):
                ob = toy.sphere(f"far_cloud{k}_{j}", crnd.uniform(9, 16),
                                (cx + j * 11 - 22 + crnd.uniform(-3, 3), cy, cz + crnd.uniform(-3, 5)),
                                scale=(1.3, 0.8, 0.6), mat=cloud, subdiv=1)
                st.no_shadow(ob)

    def _materials(self):
        m = self.m = {}
        m["ground"] = self._ground_mat()
        m["conc"] = st.concrete("ut_concrete", hexc="#E2C79A", lift=1.4, panel=3.0)
        m["dock"] = st.concrete("ut_dock", hexc="#D9A36A", lift=1.0, panel=2.0)
        m["asph"] = st.asphalt("ut_asphalt")
        m["cavity"] = st.cavity_rock("ut_cavity", hexc="#6A4630")
        m["steel"] = tx.paint("ut_steel", "#E8A21C", rough=0.4, coat=0.2, seams=0.7, seam_axis="y")
        m["metal"] = tx.metal("ut_metal", "#5D8FC0")
        m["rubber"] = tx.rubber("ut_rubber", "#141416", rough=0.75)
        m["ballast"] = toy.material("ut_ballast", toy.srgb("#2E8FE6"), roughness=0.12, coat=0.6)
        # the leak jet and the pool it makes: clearly blue sea water, not a pale haze
        m["jet"] = toy.noise_material("ut_jetwater", toy.srgb("#8FD0F8"), toy.srgb("#3E9BE6"), scale=14,
                                      roughness=0.08, bump=0.0)
        m["lamp"] = st.glow_mat("ut_lamp", "#FFE6A8", strength=0.0)
        m["mud"] = toy.noise_material("ut_mud", toy.srgb("#8E5A2C"), toy.srgb("#653C1C"), scale=8,
                                      roughness=0.4, bump=0.2)
        m["gravel"] = toy.noise_material("ut_gravel", toy.srgb("#B58C5E"), toy.srgb("#7A5838"), scale=22,
                                         roughness=0.85, bump=0.4)
        m["backfill"] = toy.noise_material("ut_backfill", toy.srgb("#D9A55A"), toy.srgb("#A8743A"), scale=9,
                                           roughness=0.9, bump=0.3)
        m["rock"] = toy.noise_material("ut_rock", toy.srgb("#9C7A5C"), toy.srgb("#66503E"), scale=5,
                                       roughness=0.8, bump=0.35)
        m["white"] = tx.paint("ut_white", "#F4F2EC", rough=0.5, coat=0.1)
        m["grey"] = tx.paint("ut_gullgrey", "#9AA3AD", rough=0.5)
        m["orange"] = tx.paint("ut_orange", "#F29A1F", rough=0.4)
        m["black"] = toy.material("ut_black", toy.srgb("#101010"), roughness=0.4)
        m["crack"] = toy.material("ut_crack", toy.srgb("#1A1612"), roughness=0.9)
        m["gap"] = st.cavity_rock("ut_gap", hexc="#2E2722")
        m["tug"] = tx.paint("ut_tug", "#D2402F", seams=0.6)
        m["cabin"] = tx.paint("ut_cabin", "#EDE7DA", seams=0.5)
        m["hull"] = tx.paint("ut_hull", "#1E5AA8", seams=1.2)
        m["hullred"] = tx.paint("ut_hullred", "#A8322A")
        m["yellow"] = tx.paint("ut_yellow", "#E9B526", seams=0.8)
        m["barge"] = tx.paint("ut_barge", "#2E86C8", seams=1.0)
        m["chain"] = tx.metal("ut_chain", "#2B2B2D", rough=0.5, metallic=0.8)
        m["cable"] = tx.rubber("ut_cable", "#1E1E1E", rough=0.5)
        m["car"] = tx.paint("ut_car", "#2F7FD8", rough=0.25, coat=0.9)
        m["tyre"] = tx.rubber("ut_tyre", tread=0.04)
        m["glass"] = toy.material("ut_glass", toy.srgb("#26343E"), roughness=0.05, coat=1.0)
        m["seat"] = tx.cloth("ut_seat", "#C9A26B")
        m["blanket"] = tx.cloth("ut_blanket", "#D8413A")
        m["wood"] = tx.wood("ut_wood", "#A0703F", "#7A5230", along="x")
        m["planks"] = tx.planks("ut_planks", "#B8834F", "#94643A", width=0.2, across="y", along="x")
        m["leaf"] = tx.paint("ut_leaf", "#4E9A3A", rough=0.8, coat=0.0)
        m["msea"] = tx.paint("ut_modelsea", "#3D8FD6", rough=0.2, coat=0.8)
        m["mland"] = tx.paint("ut_modelland", "#6DAE4A", rough=0.7)
        m["mblock"] = tx.paint("ut_modelblock", "#F2C27A", rough=0.5)
        m["mblock2"] = tx.paint("ut_modelblock2", "#D97B3A", rough=0.5)
        m["fish"] = tx.paint("ut_fish", "#FF8A1E")
        m["red"] = tx.paint("ut_red", "#D12F2F")
        m["trenchwater"] = st.water_volume("ut_trench_vol", color="#2FA4F5", density=0.14, scatter=0.015)
        m["grass"] = st.rock_grass("ut_grass", grass="#62C23A", grass_dark="#3E9A2A")
        m["headlight"] = st.glow_mat("ut_headlight", "#FFF3D0", strength=2.5)

    def _ground_mat(self):
        """Ground in world-z bands: dry sand on top, wet sand, dark soaked clay, rock; mottled, bumpy."""
        mat = bpy.data.materials.new("ut_ground")
        mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
        geo = nodes.new("ShaderNodeNewGeometry")
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(geo.outputs["Position"], sep.inputs[0])
        mr = nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = BOT
        mr.inputs["From Max"].default_value = 2.0
        links.new(sep.outputs["Z"], mr.inputs["Value"])
        ramp = nodes.new("ShaderNodeValToRGB")
        cr = ramp.color_ramp
        cr.interpolation = "CONSTANT"
        pos = lambda z: (z - BOT) / (2.0 - BOT)                              # noqa: E731
        stops = [(0.0, "#8A6A52"), (pos(-14.0), "#8A4E2C"), (pos(-9.0), "#E0A24E"), (pos(-0.4), "#F7C860")]
        cr.elements[0].position, cr.elements[0].color = stops[0][0], (*toy.srgb(stops[0][1]), 1)
        cr.elements[1].position, cr.elements[1].color = stops[1][0], (*toy.srgb(stops[1][1]), 1)
        for p, c in stops[2:]:
            el = cr.elements.new(p)
            el.color = (*toy.srgb(c), 1)
        links.new(mr.outputs["Result"], ramp.inputs["Fac"])
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 2.4
        noise.inputs["Detail"].default_value = 8.0
        links.new(geo.outputs["Position"], noise.inputs["Vector"])
        nr = nodes.new("ShaderNodeValToRGB")
        nr.color_ramp.elements[0].position, nr.color_ramp.elements[0].color = 0.3, (0.72, 0.72, 0.72, 1)
        nr.color_ramp.elements[1].position, nr.color_ramp.elements[1].color = 0.72, (1.0, 1.0, 1.0, 1)
        links.new(noise.outputs["Fac"], nr.inputs["Fac"])
        mul = nodes.new("ShaderNodeVectorMath")
        mul.operation = "MULTIPLY"
        links.new(ramp.outputs["Color"], mul.inputs[0])
        links.new(nr.outputs["Color"], mul.inputs[1])
        links.new(mul.outputs["Vector"], bsdf.inputs["Base Color"])
        fine = nodes.new("ShaderNodeTexNoise")
        fine.inputs["Scale"].default_value = 14.0
        links.new(geo.outputs["Position"], fine.inputs["Vector"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.3
        bump.inputs["Distance"].default_value = 0.04
        links.new(fine.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        bsdf.inputs["Roughness"].default_value = 0.88
        return mat

    # ------------------- the world -------------------

    def _ground(self):
        g = self.m["ground"]
        left_plain = [(XB, -7.5), (-14.6, 0.5), (-120.0, 0.5)]
        left_dock = [(XB, -7.5), (DOCK_X1, -3.5), (DOCK_X0, -3.5), (DOCK_X0, 0.5), (-120.0, 0.5)]
        right = [(-120.0, BOT), (120.0, BOT), (120.0, 0.8), (9.0, 0.8), (XI, -7.5), (XI, TRENCH), (XB, TRENCH)]
        self.front_plain = st.prism("front_plain", right + left_plain, 0.0, STRIP, mat=g)
        self.front_bored = st.prism("front_bored", right + left_plain, 0.0, STRIP, mat=g)
        # Max's dig: a shaft down from the beach and a drift toward the sea, its roof under the seabed
        cutter = st.prism("bore_cutter", [(-16.6, 0.9), (-16.6, DIG_Z), (-12.6, DIG_Z), (-12.6, DIG_TOP),
                                          (-15.2, DIG_TOP), (-15.2, 0.9)], -0.6, 0.9)
        st.carve(self.front_bored, cutter, mat=self.m["cavity"])
        self.front_dock = st.prism("front_dock", right + left_dock, 0.0, STRIP, mat=g)
        low = st.prism("front_final_low", [(-120.0, BOT), (120.0, BOT), (120.0, 0.8), (RX1, 0.8),
                                           (XI, ROAD - 0.05), (XI, TRENCH), (XB, TRENCH), (XB, ROAD - 0.05),
                                           (LX0, 0.5), (-120.0, 0.5)], 0.0, STRIP, mat=g)
        upl = st.prism("front_final_upl", [(L_PORTAL, 0.5), (XB, ROAD - 0.05 + RH), (XB, -7.5),
                                           (DOCK_X1, -3.5), (DOCK_X0, -3.5), (DOCK_X0, 0.5)], 0.0, STRIP, mat=g)
        upr = st.prism("front_final_upr", [(XI, -7.5), (XI, ROAD - 0.05 + RH), (R_PORTAL, 0.8), (9.0, 0.8)],
                       0.0, STRIP, mat=g)
        roads = []
        for nm, (xa, za), (xb, zb) in (("ramp_road_l", (LX0, lfloor(LX0)), (XB, lfloor(XB))),
                                       ("ramp_road_r", (XI, rfloor(XI)), (RX1, rfloor(RX1)))):
            d = V((xb - xa, 0, zb - za))
            n = V((-d.z, 0, d.x)).normalized()
            c = V(((xa + xb) / 2, 1.4, (za + zb) / 2)) + n * 0.025
            ob = toy.box(nm, (d.length - 0.2, 1.86, 0.04), c, mat=self.m["asph"], bevel=0)
            ob.rotation_euler = (0, -math.atan2(d.z, d.x), 0)
            roads.append(ob)
        self.groups.update({"front_plain": [self.front_plain], "front_bored": [self.front_bored],
                            "front_dock": [self.front_dock], "front_final": [low, upl, upr] + roads})
        back = [(-120.0, BOT), (120.0, BOT), (120.0, 0.79), (9.0, 0.79), (XI, -7.51), (XI, BACK_TOP),
                (XB, BACK_TOP), (XB, -7.51), (-14.6, 0.49), (-120.0, 0.49)]
        st.prism("back_ground", back, 4.88, D, mat=g)
        toy.box("grass_island", (120.0 - GRASS_X, D + 0.006, 0.08), ((120.0 + GRASS_X) / 2, D / 2 - 0.003,
                                                                     GRASS_Z - 0.04), mat=self.m["grass"], bevel=0)
        # gravel lenses in the soaked clay, half out of the cut face
        lens = [((x, 0.0, z), (sx, 0.12, 0.22), 0.0) for x, z, sx in
                ((-30, -11.5, 1.4), (-19, -12.6, 1.1), (-7, -12.2, 1.3), (1.5, -11.6, 0.9), (9, -12.8, 1.2),
                 (20, -11.4, 1.5), (-3, -13.4, 1.0), (-24, -10.6, 0.8), (14, -13.2, 1.1))]
        merged("lens_gravel", lens, self.m["gravel"], jitter=0.12, seed=3)
        # the sea, open at the front like an aquarium; it ends 2 cm above the seabed / trench plug
        self.sea = st.Reservoir("sea", -14.31, 8.7, 0.05, D, bottom=SEABED + 0.02, level=0.0, density=0.22)
        # far scenery: land behind both shores, the strait's far water
        hill = lambda base: (lambda x, y: base + max(0.0, (y - 60.0) / 80.0) * 9.0       # noqa: E731
                             * (0.6 + 0.4 * math.sin(x / 31.0 + 1.3)))
        st.terrain("far_left", -450.0, -14.6, D + 0.06, 450.0, hill(0.5), floor=BOT, res=6.0, edge=0)
        st.terrain("far_right", 8.7, 450.0, D + 0.06, 450.0, hill(0.8), floor=BOT, res=6.0, edge=0)
        toy.box("far_seabed", (23.3, 440.0, 29.7), (-2.95, D + 0.06 + 220.0, -15.15), mat=g, bevel=0)
        bpy.ops.mesh.primitive_plane_add(size=1, location=(-2.95, D + 220.0, 0.0))
        fs = bpy.context.active_object
        fs.name = "far_sea_surface"
        fs.scale = (23.3, 439.8, 1)
        fs.data.materials.append(st.water_surface("ut_far_surface"))
        # rock piles on the back ledge (Max hides behind the first one)
        for k, (x, y) in enumerate(((3.0, 5.35), (-9.5, 6.4), (5.2, 9.0))):
            items = [((x + self.rnd.uniform(-0.6, 0.6), y + self.rnd.uniform(-0.25, 0.25),
                       BACK_TOP + self.rnd.uniform(0.15, 0.55)),
                      (self.rnd.uniform(0.35, 0.6), self.rnd.uniform(0.3, 0.5), self.rnd.uniform(0.3, 0.5)),
                      self.rnd.uniform(0, 3)) for _ in range(7)]
            merged(f"rockpile{k}", items, self.m["rock"], jitter=0.15, seed=20 + k)
        # trench water, one block per element slot (hidden while the plug fills it / an element sits there)
        edges = [XB, SX[0] + 3.0, SX[1] + 3.0, XI]
        self.tw = []
        for j in range(3):
            x0, x1 = edges[j] + 0.004, edges[j + 1] - 0.004
            self.tw.append(toy.box(f"tw_{j}", (x1 - x0, STRIP - 0.09, SEABED - TRENCH - 0.012),
                                   ((x0 + x1) / 2, 0.05 + (STRIP - 0.09) / 2, (SEABED + TRENCH) / 2 - 0.0),
                                   mat=self.m["trenchwater"], bevel=0))
        self.tw_edges = edges
        # the trench plug: 8 chunks of soaked seabed the grab removes
        w = (XI - XB) / 8
        self.chunks = []
        for k in range(8):
            y0 = 0.006 if k % 2 == 0 else 0.012
            x0 = XB + 0.004 if k == 0 else XB + k * w - 0.01
            x1 = XI - 0.004 if k == 7 else XB + (k + 1) * w + 0.01
            ob = toy.box(f"chunk{k}", (x1 - x0, 4.868 - y0 - (0.006 if k % 2 else 0.0), SEABED - TRENCH - 0.006),
                         ((x0 + x1) / 2, (y0 + 4.868 - (0.006 if k % 2 else 0.0)) / 2, (SEABED + TRENCH + 0.006) / 2),
                         mat=g, bevel=0)
            ob["cx"] = XB + (k + 0.5) * w
            self.chunks.append(ob)

    def _dock(self):
        c = self.m["dock"]
        parts = [toy.box("dock_floor", (DOCK_X1 - DOCK_X0 - 0.02, 4.86, 0.35), ((DOCK_X0 + DOCK_X1) / 2, 2.44,
                                                                             DOCK_FLOOR - 0.175), mat=c),
                 toy.box("dock_wall_l", (0.35, 4.86, 4.1), (DOCK_X0 + 0.125, 2.44, -1.5), mat=c),
                 toy.box("dock_wall_b", (DOCK_X1 - DOCK_X0 - 0.3, 0.35, 3.8), ((DOCK_X0 + DOCK_X1) / 2 + 0.14, 4.775,
                                                                            -1.35), mat=c)]
        self.gate = toy.box("dock_gate", (0.3, 4.8, 4.2), (-14.47, 2.46, -1.4), mat=self.m["steel"])
        for k, z in enumerate((-2.6, -1.4, -0.2)):
            toy.box(f"dock_gate_rib{k}", (0.12, 4.7, 0.14), (-0.2, 0.0, z + 1.4), mat=self.m["steel"], parent=self.gate)
        self.gate_home = V(self.gate.location)
        self.groups["dock"] = parts + [self.gate]
        self.dockres = st.Reservoir("dock", -21.69, -14.63, 0.05, 4.59, bottom=DOCK_FLOOR + 0.01,
                                    level=DOCK_FLOOR + 0.02, density=0.3)
        self.dockres.puddle.data.materials[0] = tx.paint("ut_puddle", "#3E5A66", rough=0.05, coat=1.0)

    def _dock_flood(self):
        """The flood the viewer watches fill the dock: a clearly blue volume (made AFTER the colour grade, so it
        keeps its tint) with a rippling skin on top; it rises by scale."""
        mat = st.water_volume("ut_dockflood", color="#1E7FD0", density=0.35, scatter=0.06)
        self.dflood = toy.empty("dock_flood", (-18.16, 2.32, DOCK_FLOOR + 0.012))
        toy.box("dock_flood_vol", (7.04, 4.52, 1.0), (0, 0, 0.5), mat=mat, parent=self.dflood, bevel=0)
        bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
        sk = bpy.context.active_object
        sk.name = "dock_flood_skin"
        sk.scale = (7.02, 4.5, 1)
        sk.data.materials.append(st.water_surface("ut_dockflood_skin"))
        sk.parent = self.dflood
        sk.location = (0, 0, 1.0)
        self.groups["dockflood"] = [self.dflood]

    def _ruler_and_bore(self):
        ru = [toy.box("ruler_post", (0.12, 0.08, 8.7), (-11.6, -0.12, -3.75), mat=self.m["white"])]
        for k in range(1, 5):
            ru.append(toy.box(f"ruler_tick{k}", (0.5, 0.1, 0.09), (-11.6, -0.13, -2.0 * k + (0.3 if k == 4 else 0)),
                              mat=self.m["black"], bevel=0.01))
            ru.append(toy.box(f"ruler_band{k}", (0.13, 0.09, 0.9), (-11.6, -0.125, -2.0 * k + 1.0),
                              mat=self.m["red"], bevel=0.005))
        self.groups["ruler"] = ru
        # the flood: a muddy box behind the cut face, seen only through the dug groove; it rises by scale
        self.flood = toy.empty("bore_flood", (-14.6, 0.45, DIG_Z))
        self.flood_box = toy.box("bore_flood_box", (3.98, 0.8, 1.0), (0, 0, 0.5), mat=self.m["mud"],
                                 parent=self.flood, bevel=0)
        self.jet = toy.empty("mudjet", (-15.9, 0.45, 0.48))
        toy.cylinder("mudjet_col", 0.45, 1.0, (0, 0, 0.5), mat=self.m["mud"], parent=self.jet, vertices=20)
        self.shovel = toy.empty("shovel", (0, 0, 0))
        toy.cylinder("shovel_handle", 0.03, 1.0, (0, 0, -0.1), mat=self.m["wood"], parent=self.shovel, vertices=10)
        toy.box("shovel_blade", (0.24, 0.04, 0.3), (0, 0, -0.72), mat=self.m["metal"], parent=self.shovel)
        self.groups.update({"flood": [self.flood], "mudjet": [self.jet], "shovel": [self.shovel]})
        self.mud_squirt = Spray("mud_squirt", self.m["mud"], count=26, radius=0.07, seed=4)
        self.mud_drops = Spray("mud_drops", self.m["mud"], count=20, radius=0.09, seed=6)

    # ------------------- the tunnel elements -------------------

    def _section(self, k):
        n = f"S{k}"
        m = self.m
        root = toy.empty(f"{n}_root")
        S = {"root": root, "bulkL": [], "bulkR": [], "tanks": [], "fills": [], "valves": []}
        toy.box(f"{n}_floor", (L, 4.39, 0.35), (0, 2.4, -HH + 0.175), mat=m["conc"], parent=root)
        toy.box(f"{n}_roof", (L, 4.39, 0.35), (0, 2.4, HH - 0.175), mat=m["conc"], parent=root)
        toy.box(f"{n}_wallback", (L - 0.01, 0.25, 2.2), (0, 4.475, 0), mat=m["conc"], parent=root)
        toy.box(f"{n}_wallmid", (L - 0.01, 0.3, 2.2), (0, 2.5, 0), mat=m["conc"], parent=root)
        S["front"] = toy.box(f"{n}_front", (L - 0.01, 0.25, 2.2), (0, 0.325, 0), mat=m["conc"], parent=root)
        toy.box(f"{n}_road", (L - 0.04, 1.86, 0.04), (0, 1.4, -1.02), mat=m["asph"], parent=root, bevel=0)
        toy.box(f"{n}_road2", (L - 0.04, 1.66, 0.04), (0, 3.5, -1.02), mat=m["asph"], parent=root, bevel=0)
        for j, x in enumerate((-2.0, 0.0, 2.0)):
            toy.box(f"tunnel_light_{n}_{j}", (0.6, 0.3, 0.05), (x, 1.4, 1.015), mat=m["lamp"], parent=root, bevel=0)
        ld = bpy.data.lights.new(f"{n}_lamp", "POINT")
        ld.energy, ld.color, ld.shadow_soft_size = 0.0, (1.0, 0.88, 0.66), 0.3
        lo = bpy.data.objects.new(f"{n}_lamp", ld)
        self.scene.collection.objects.link(lo)
        lo.parent = root
        lo.location = (0, 1.4, 0.5)
        S["lamp"] = ld
        for side, sx in (("L", -1), ("R", 1)):
            for b, (yc, wy) in enumerate(((1.4, 1.86), (3.5, 1.66))):
                x = sx * (L / 2 - 0.35)
                p = toy.box(f"{n}_bulk{side}{b}", (0.06, wy, 2.06), (x, yc, 0), mat=m["steel"], parent=root, bevel=0.01)
                r = toy.box(f"{n}_bulk{side}{b}_rib", (0.05, wy - 0.16, 0.12), (x + sx * 0.05, yc, 0.35),
                            mat=m["steel"], parent=root, bevel=0.005)
                S[f"bulk{side}"] += [p, r]
        for j, x in enumerate((-2.0, -0.4)):
            t = [toy.box(f"{n}_tank{j}_base", (1.2, 1.5, 0.06), (x, 1.4, -0.965), mat=m["steel"], parent=root, bevel=0),
                 toy.box(f"{n}_tank{j}_top", (1.2, 1.5, 0.05), (x, 1.4, 0.29), mat=m["steel"], parent=root, bevel=0),
                 toy.box(f"{n}_tank{j}_back", (1.2, 0.04, 1.2), (x, 2.13, -0.335), mat=m["steel"], parent=root,
                         bevel=0)]
            for a in (-1, 1):
                for c in (-1, 1):
                    t.append(toy.box(f"{n}_tank{j}_post{a}{c}", (0.06, 0.06, 1.2), (x + a * 0.57, 1.4 + c * 0.72,
                                                                                     -0.335), mat=m["steel"],
                                     parent=root, bevel=0))
            fill = toy.empty(f"{n}_tank{j}_fill", (x, 1.4, -0.935), root)
            t += [fill, toy.box(f"{n}_tank{j}_water", (1.08, 1.36, 1.0), (0, 0, 0.5), mat=m["ballast"], parent=fill,
                                bevel=0)]
            wheel = toy.cylinder(f"{n}_tank{j}_valve", 0.14, 0.04, (x + 0.3, 0.6, -0.72), rotation=(R(90), 0, 0),
                                 mat=m["red"], parent=root, vertices=16)
            t.append(wheel)
            S["tanks"] += t
            S["fills"].append(fill)
            S["valves"].append(wheel)
        for j, x in enumerate((-1.8, 1.8)):
            toy.cylinder(f"{n}_bollard{j}", 0.12, 0.26, (x, 2.4, HH + 0.125), mat=m["metal"], parent=root, vertices=14)
        S["gasket"] = S["gfront"] = None
        if k >= 2:
            g = toy.empty(f"{n}_gasket", (-L / 2, 0, 0), root)
            S["gfront"] = toy.capsule(f"{n}_gasket_front", 0.27, 2.3, (-0.28, 0.5, 0), mat=m["rubber"], parent=g)
            toy.capsule(f"{n}_gasket_back", 0.27, 2.3, (-0.28, 4.3, 0), mat=m["rubber"], parent=g)
            for z in (-1.13, 1.13):
                toy.capsule(f"{n}_gasket_{'top' if z > 0 else 'bot'}", 0.27, 3.8, (-0.28, 2.4, z),
                            rotation=(R(90), 0, 0), mat=m["rubber"], parent=g)
            S["gasket"] = g
        return S

    def _joint_parts(self):
        m = self.m
        self.joint = toy.empty("joint_water", (SX[0] + 3.0 - 0.305, 1.4, ROAD + 0.006))
        toy.box("joint_water_box", (1.1, 1.84, 1.0), (0.55, 0, 0.5), mat=m["ballast"], parent=self.joint, bevel=0)
        S1, S2 = self.S[1]["root"], self.S[2]["root"]
        jacks = [toy.cylinder("jack_barrel", 0.12, 0.9, (2.55, 0.9, HH + 0.32), rotation=(0, R(90), 0),
                              mat=m["yellow"], parent=S1, vertices=14),
                 toy.box("jack_bracket1", (0.2, 0.3, 0.32), (2.1, 0.9, HH + 0.17), mat=m["metal"], parent=S1),
                 toy.cylinder("jack_rod", 0.07, 1.6, (-3.4, 0.9, HH + 0.32), rotation=(0, R(90), 0),
                              mat=m["metal"], parent=S2, vertices=12),
                 toy.box("jack_bracket2", (0.2, 0.3, 0.32), (-2.6, 0.9, HH + 0.17), mat=m["metal"], parent=S2)]
        px = SX[0] + 3.0 - 0.75
        pump = [toy.box("pump_body", (0.5, 0.4, 0.45), (px - 0.25, 2.05, ROAD + 0.23), mat=m["yellow"]),
                toy.cylinder("pump_hose", 0.05, 0.42, (px + 0.1, 2.05, ROAD + 0.35), rotation=(0, R(90), 0),
                             mat=m["rubber"], vertices=10)]
        seals = []
        for j, x in enumerate(((SX[0] + 3.0 + SX[1] - 3.0) / 2, (SX[1] + 3.0 + SX[2] - 3.0) / 2)):
            seals += [toy.box(f"inner_seal{j}", (0.7, 0.04, 2.0), (x, 2.325, TUBE_Z), mat=m["rubber"], bevel=0.005),
                      toy.box(f"inner_seal{j}_clampa", (0.07, 0.05, 2.0), (x - 0.3, 2.3, TUBE_Z), mat=m["metal"]),
                      toy.box(f"inner_seal{j}_clampb", (0.07, 0.05, 2.0), (x + 0.3, 2.3, TUBE_Z), mat=m["metal"])]
        crack = []
        pts = [(-1.5, -7.62), (-1.3, -8.0), (-1.62, -8.35), (-1.35, -8.8), (-1.55, -9.15)]
        for j, (a, b) in enumerate(zip(pts, pts[1:])):
            crack.append(beam(f"crack{j}", (a[0], 0.19, a[1]), (b[0], 0.19, b[1]), 0.07, m["crack"], h=0.008))
        crack.append(beam("crack_roof", (-1.5, 0.3, TUBE_Z + HH + 0.006), (-1.15, 2.2, TUBE_Z + HH + 0.006), 0.07,
                          m["crack"], h=0.008))
        self.crack = crack
        self.groups.update({"joint": [self.joint], "jacks": jacks, "pump": pump, "seal": seals, "crack": crack})
        # the leak: a water jet cone from the gap toward Max, a rising pool on block one's floor
        self.leak_jet = cone("leak_jet", 0.34, 0.06, 1.9, (SX[0] + 3.0 - 0.95, 1.3, -8.8), (0, R(90), 0), m["jet"])
        self.pool = toy.empty("leak_pool", (SX[0] + 3.0 - 1.375, 1.4, ROAD + 0.006))
        toy.box("leak_pool_box", (2.65, 1.8, 1.0), (0, 0, 0.5), mat=m["jet"], parent=self.pool, bevel=0)
        # the dark slot between block one and the badly seated block two (2 cm clear of both): a dark, wet,
        # shotcrete-textured void, never a flat colour
        self.leak_gap = toy.box("leak_gap", (0.1, 4.5, 2.74), (SX[0] + 3.07, 2.35, TUBE_Z), mat=m["gap"], bevel=0)
        self.groups["leak"] = [self.leak_jet, self.pool, self.leak_gap]
        self.leak_drops = Spray("leak_drops", m["jet"], count=30, radius=0.05, seed=8)

    # ------------------- boats -------------------

    def _hull(self, name, outline, half_w, mat, parent):
        h = st.prism(name, outline, -half_w, half_w, mat=mat)
        h.parent = parent
        return h

    def _boats(self):
        m = self.m
        # tugboats
        self.tugs, self.towlines = [], []
        for k, off in enumerate(((-0.1, 0.4, 0.7), (0.5, 0.4, 0.7))):
            r = toy.empty(f"tug{k + 1}")
            self._hull(f"tug{k + 1}_hull", [(-1.5, -0.45), (1.1, -0.45), (1.7, 0.5), (-1.6, 0.5)], 0.8, m["tug"], r)
            toy.box(f"tug{k + 1}_deck", (2.9, 1.5, 0.05), (0.0, 0, 0.52), mat=m["planks"], parent=r, bevel=0)
            toy.box(f"tug{k + 1}_cabin", (1.0, 1.0, 0.75), (0.3, 0, 0.92), mat=m["cabin"], parent=r)
            toy.box(f"tug{k + 1}_glass", (1.02, 0.8, 0.2), (0.3, 0, 1.08), mat=m["glass"], parent=r, bevel=0.01)
            toy.cylinder(f"tug{k + 1}_funnel", 0.16, 0.6, (-0.4, 0, 1.2), mat=m["red"], parent=r, vertices=14)
            for x in (-1.4, 1.4):
                toy.cylinder(f"tug{k + 1}_fender{x}", 0.14, 1.5, (x, 0, 0.3), rotation=(R(90), 0, 0),
                             mat=m["rubber"], parent=r, vertices=12)
            self.towlines.append(beam(f"towline{k + 1}", (0, -0.8, 0.4), (off[0], -3.8, off[2]), 0.04,
                                      m["cable"], parent=r))
            self.tugs.append(r)
        # winch barge with an A-frame over the trench
        self.winch = toy.empty("winch_barge")
        toy.box("winch_hull", (5.2, 2.6, 1.0), (0, 0, -0.1), mat=m["barge"], parent=self.winch)
        self.cables = []
        for j, x in enumerate((-1.8, 1.8)):
            toy.cylinder(f"winch_drum{j}", 0.3, 0.6, (x, 0.3, 0.75), rotation=(0, R(90), 0), mat=m["yellow"],
                         parent=self.winch, vertices=16)
            toy.box(f"winch_post{j}", (0.3, 0.3, 1.2), (x, -1.0, 1.0), mat=m["yellow"], parent=self.winch)
            beam(f"winch_arm{j}", (x, -1.0, 1.55), (x, -7.2, 3.45), 0.2, m["yellow"], parent=self.winch)
            c = toy.empty(f"cable{j}", (x, -7.2, 3.4), self.winch)
            toy.cylinder(f"cable{j}_line", 0.035, 1.0, (0, 0, -0.5), mat=m["cable"], parent=c, vertices=8)
            self.cables.append(c)
        beam("winch_cross", (-1.9, -7.2, 3.5), (1.9, -7.2, 3.5), 0.22, m["yellow"], parent=self.winch)
        # grab dredger
        self.dredger = toy.empty("dredger")
        toy.box("dredger_hull", (5.0, 3.2, 1.0), (0, 0, -0.1), mat=m["barge"], parent=self.dredger)
        toy.box("dredger_cab", (1.2, 1.2, 1.1), (1.4, -0.3, 0.95), mat=m["yellow"], parent=self.dredger)
        toy.box("dredger_window", (0.9, 1.22, 0.35), (1.4, -0.3, 1.2), mat=m["glass"], parent=self.dredger, bevel=0.01)
        beam("dredger_boom", (1.2, -0.6, 1.4), (0.0, -4.5, 3.6), 0.22, m["yellow"], parent=self.dredger)
        self.grab_cable = toy.empty("grab_cable", (0.0, -4.5, 3.55), self.dredger)
        toy.cylinder("grab_cable_line", 0.035, 1.0, (0, 0, -0.5), mat=m["cable"], parent=self.grab_cable, vertices=8)
        # the clamshell grab: a steel head and two orange jaws on hinges that swing open and bite shut
        self.grab = toy.empty("grab", (0.0, -4.5, 0.55), self.dredger)
        toy.box("grab_head", (0.8, 0.7, 0.35), (0, 0, -0.18), mat=m["metal"], parent=self.grab)
        toy.box("grab_beam", (1.1, 0.16, 0.14), (0, 0, -0.4), mat=m["metal"], parent=self.grab)
        self.grab_jaws = []
        for s in (-1, 1):
            pv = toy.empty(f"grab_pivot{s}", (s * 0.1, 0, -0.4), self.grab)
            toy.box(f"grab_jaw{s}", (0.62, 1.0, 0.7), (s * 0.33, 0, -0.38), mat=m["steel"], parent=pv)
            toy.box(f"grab_tooth{s}", (0.1, 0.96, 0.12), (s * 0.07, 0, -0.74), mat=m["metal"], parent=pv)
            beam(f"grab_rod{s}", (s * 0.6, 0, -0.1), (s * 0.25, 0, 0.32), 0.06, m["metal"], parent=pv)
            pv.rotation_euler = (0, R(-30 * s), 0)
            self.grab_jaws.append((s, pv))
        self.grab_load = toy.sphere("grab_load", 0.42, (0, 0, -0.85), scale=(1.25, 1.1, 0.8), mat=m["mud"],
                                    parent=self.grab)
        self.dredge_puffs = Puffs("puff_dredge", "#6B5A47", count=16, size=0.3, seed=5)
        # ship with chain and anchor
        self.ship = toy.empty("ship")
        self._hull("ship_hull", [(-3.6, -1.1), (3.0, -1.1), (4.0, 1.0), (-3.8, 1.0)], 1.5, m["hull"], self.ship)
        toy.box("ship_band", (7.2, 3.06, 0.22), (0.1, 0, -0.15), mat=m["hullred"], parent=self.ship, bevel=0)
        toy.box("ship_house", (1.8, 2.2, 1.3), (-2.3, 0, 1.65), mat=m["cabin"], parent=self.ship)
        toy.box("ship_bridge", (1.9, 2.3, 0.3), (-2.3, 0, 2.2), mat=m["glass"], parent=self.ship, bevel=0.01)
        toy.cylinder("ship_funnel", 0.3, 1.0, (-3.0, 0, 2.6), mat=m["red"], parent=self.ship, vertices=16)
        toy.box("ship_deck", (5.6, 2.9, 0.05), (0.3, 0, 1.03), mat=m["planks"], parent=self.ship, bevel=0)
        self.hawse = V((3.7, -1.55, 0.3))
        self.anchor = toy.empty("anchor")
        cone("anchor_crown", 0.42, 0.05, 0.6, (0, 0, -0.15), (R(180), 0, 0), m["chain"], parent=self.anchor)
        toy.cylinder("anchor_shank", 0.07, 0.9, (0, 0, 0.1), mat=m["chain"], parent=self.anchor, vertices=10)
        for s in (-1, 1):
            f = toy.box(f"anchor_fluke{s}", (0.18, 0.12, 0.5), (s * 0.4, 0, -0.25), mat=m["chain"], parent=self.anchor)
            f.rotation_euler = (0, R(35 * s), 0)
        toy.box("anchor_stock", (0.8, 0.1, 0.08), (0, 0, 0.5), mat=m["chain"], parent=self.anchor)
        self.chain = toy.empty("chain")
        toy.cylinder("chain_line", 0.06, 1.0, (0, 0, 0.5), mat=m["chain"], parent=self.chain, vertices=8)
        # stone-dumping vessel
        self.stoner = toy.empty("stoner")
        self._hull("stoner_hull", [(-3.0, -0.8), (2.6, -0.8), (3.2, 0.6), (-3.1, 0.6)], 1.6, m["yellow"], self.stoner)
        toy.box("stoner_hopper", (1.8, 2.2, 0.9), (1.2, 0, 1.05), mat=m["steel"], parent=self.stoner)
        heap = [((1.2 + self.rnd.uniform(-0.6, 0.6), self.rnd.uniform(-0.7, 0.7), 1.55), (0.25, 0.25, 0.16),
                 self.rnd.uniform(0, 3)) for _ in range(14)]
        heap_ob = merged("stoner_heap", heap, m["gravel"], jitter=0.15, seed=9)
        heap_ob.parent = self.stoner
        toy.box("stoner_house", (1.2, 1.6, 1.1), (-2.2, 0.5, 1.15), mat=m["cabin"], parent=self.stoner)
        toy.cylinder("stoner_pipe", 0.18, 5.2, (1.2, 0, -3.4), mat=m["metal"], parent=self.stoner, vertices=16)
        toy.cylinder("stoner_stream", 0.2, 1.0, (1.2, 0, -6.5), mat=m["gravel"], parent=self.stoner, vertices=12)
        self.grav_puffs = Puffs("puff_gravel", "#8E8778", count=16, size=0.28, seed=7)
        self.spark = Puffs("puff_spark", "#FFC85A", count=12, size=0.14, seed=11)
        self.groups.update({"tugs": self.tugs, "towline": self.towlines, "winch": [self.winch],
                            "cables": self.cables, "dredger": [self.dredger], "grab_load": [self.grab_load],
                            "ship": [self.ship], "anchor": [self.anchor], "chain": [self.chain],
                            "stoner": [self.stoner]})

    def _anchor_b(self):
        """The anchor that bounces off the rock armour: 1.6x bigger and painted red so it reads on the rocks."""
        m = self.m
        k = 1.6
        a = self.anchor_b = toy.empty("anchor_b")
        cone("anchor_b_crown", 0.42 * k, 0.05 * k, 0.6 * k, (0, 0, -0.15 * k), (R(180), 0, 0), m["red"], parent=a)
        toy.cylinder("anchor_b_shank", 0.07 * k, 0.9 * k, (0, 0, 0.1 * k), mat=m["red"], parent=a, vertices=12)
        for s in (-1, 1):
            f = toy.box(f"anchor_b_fluke{s}", (0.18 * k, 0.12 * k, 0.5 * k), (s * 0.4 * k, 0, -0.25 * k), mat=m["red"],
                        parent=a)
            f.rotation_euler = (0, R(35 * s), 0)
        toy.box("anchor_b_stock", (0.8 * k, 0.1 * k, 0.08 * k), (0, 0, 0.5 * k), mat=m["red"], parent=a)
        self.chain_b = toy.empty("chain_b")
        toy.cylinder("chain_b_line", 0.08, 1.0, (0, 0, 0.5), mat=m["chain"], parent=self.chain_b, vertices=8)
        self.impact = Puffs("puff_impact", "#FFE7A0", count=12, size=0.3, seed=23)
        self.groups.update({"anchor_b": [a], "chain_b": [self.chain_b]})

    def _fill_layers(self):
        """Locking gravel, backfill and a dense two-layer rock armour blanket along the trench, in 9 segments."""
        m = self.m
        arnd = random.Random(55)
        n = 9
        w = (XI - XB) / n
        self.segs = []
        for k in range(n):
            x0 = XB + k * w - (0.0 if k == 0 else 0.01)
            x1 = XB + (k + 1) * w + (0.0 if k == n - 1 else 0.01)
            cx, wx = (x0 + x1) / 2, x1 - x0
            o = 0.006 * (k % 2)
            seg = {"cx": XB + (k + 0.5) * w, "x0": XB + k * w}
            seg["lockfront"] = toy.box(f"lockfront_{k}", (wx, 0.17 - o, 0.8), (cx, 0.095 + o / 2, TRENCH + 0.41),
                                       mat=m["gravel"], bevel=0)
            seg["lockback"] = toy.box(f"lockback_{k}", (wx, 0.257 - o, HH * 2 - 0.0),
                                      (cx, 4.7435 + o / 2, TRENCH + HH + 0.01), mat=m["gravel"], bevel=0)
            top = -7.15 + (0.01 if k % 2 else 0.0)
            seg["backfill"] = toy.box(f"backfill_{k}", (wx, 4.85 - o, top + 7.58), (cx, 2.445 + o / 2, (top - 7.58) / 2),
                                      mat=m["backfill"], bevel=0)
            rocks = []
            for a in range(6):
                for c in range(9):
                    rocks.append(((x0 + (a + 0.5 + arnd.uniform(-0.3, 0.3)) * wx / 6,
                                   0.4 + (c + 0.5 + arnd.uniform(-0.3, 0.3)) * 4.2 / 9,
                                   top + 0.2 + arnd.uniform(-0.04, 0.06)),
                                  (arnd.uniform(0.24, 0.32), arnd.uniform(0.22, 0.3), arnd.uniform(0.17, 0.24)),
                                  arnd.uniform(0, 3)))
            for _ in range(16):
                rocks.append(((arnd.uniform(x0 + 0.25, x1 - 0.25), arnd.uniform(0.6, 4.4), top + 0.42),
                              (arnd.uniform(0.24, 0.34), arnd.uniform(0.22, 0.3), arnd.uniform(0.17, 0.24)),
                              arnd.uniform(0, 3)))
            seg["armour"] = merged(f"armour_{k}", rocks, m["rock"], jitter=0.18, seed=40 + k)
            self.segs.append(seg)
        hit = [((arnd.uniform(-1.8, 1.0), arnd.uniform(1.4, 3.9), ARMOUR_TOP - 0.36),
                (arnd.uniform(0.3, 0.42), arnd.uniform(0.28, 0.4), arnd.uniform(0.24, 0.3)),
                arnd.uniform(0, 3)) for _ in range(16)]
        self.armour_hit = merged("armour_hit", hit, m["rock"], jitter=0.18, seed=77)

    def _car(self):
        m = self.m
        c = self.car = toy.empty("car")
        toy.box("car_floor", (3.0, 1.46, 0.08), (0, 0, 0.12), mat=m["car"], parent=c)
        toy.box("car_hood", (0.95, 1.5, 0.5), (1.02, 0, 0.4), mat=m["car"], parent=c)
        toy.box("car_trunk", (0.75, 1.5, 0.5), (-1.12, 0, 0.4), mat=m["car"], parent=c)
        for s in (-1, 1):
            toy.box(f"car_door{s}", (1.32, 0.08, 0.42), (0.0, s * 0.70, 0.37), mat=m["car"], parent=c)
            # low bench seats (top at 0.33): a seated Max sits on them, his hat clear of the tunnel roof
            toy.box(f"car_seat{s}", (0.5, 0.6, 0.16), (-0.5, s * 0.33, 0.25), mat=m["seat"], parent=c)
            toy.box(f"car_back{s}", (0.14, 0.6, 0.7), (-0.83, s * 0.33, 0.52), mat=m["seat"], parent=c)
            for x in (-1.0, 1.0):
                toy.cylinder(f"car_wheel{s}{x}", 0.24, 0.2, (x, s * 0.76, 0.24), rotation=(R(90), 0, 0),
                             mat=m["tyre"], parent=c, vertices=20)
            toy.cylinder(f"car_headlight{s}", 0.09, 0.05, (1.5, s * 0.5, 0.5), rotation=(0, R(90), 0),
                         mat=m["headlight"], parent=c, vertices=14)
        toy.box("car_dash", (0.12, 1.34, 0.18), (0.5, 0, 0.72), mat=m["planks"], parent=c)
        g = toy.box("car_windshield", (0.04, 1.4, 0.42), (0.6, 0, 1.0), mat=m["glass"], parent=c, bevel=0.01)
        g.rotation_euler = (0, R(-18), 0)
        toy.cylinder("car_wheelrim", 0.13, 0.03, (0.36, -0.33, 0.86), rotation=(0, R(70), 0), mat=m["black"],
                     parent=c, vertices=16)
        self.groups["car"] = [c]

    def _picnic_and_model(self):
        m = self.m
        top = GRASS_Z
        pic = [toy.box("blanket", (3.0, 2.0, 0.034), (54.1, 2.0, top + 0.023), mat=m["blanket"], bevel=0.005),
               toy.box("basket", (0.5, 0.36, 0.3), (55.2, 2.7, 0.9 + 0.155), mat=m["wood"]),
               toy.box("basket_lid", (0.52, 0.38, 0.05), (55.2, 2.7, 1.235), mat=m["planks"])]
        for k, (x, y) in enumerate(((56.6, 6.4), (45.0, 9.5), (62.0, 10.5), (-34.0, 8.5))):
            z0 = top if x > GRASS_X else 0.49
            toy.cylinder(f"tree{k}_trunk", 0.18, 1.8, (x, y, z0 + 0.88), mat=m["wood"], vertices=12)
            toy.sphere(f"tree{k}_crown", 1.1, (x, y, z0 + 2.3), scale=(1, 1, 1.15), mat=m["leaf"], subdiv=1)
        # the scale model on a compact table: a strait with a chain of 89 tiny blocks
        tx0, tx1, ty = 58.0, 61.8, 2.0
        ttop = top + 0.8
        toy.box("table_top", (tx1 - tx0, 1.2, 0.08), ((tx0 + tx1) / 2, ty, ttop - 0.04), mat=m["planks"])
        for a in (tx0 + 0.15, tx1 - 0.15):
            for b in (ty - 0.45, ty + 0.45):
                toy.box(f"table_leg{a:.0f}{b:.0f}", (0.08, 0.08, 0.76), (a, b, top + 0.38), mat=m["wood"])
        cxm = (tx0 + tx1) / 2
        toy.box("scale_model_sea", (3.0, 0.9, 0.04), (cxm, ty, ttop + 0.026), mat=m["msea"], bevel=0)
        for s in (-1, 1):
            toy.box(f"scale_model_land{s}", (0.3, 1.1, 0.14), (cxm + s * 1.66, ty, ttop + 0.076), mat=m["mland"])
        # 89 blocks in two alternating colours, so every block reads as its own segment of the chain
        pitch = 2.9 / 89
        for par, key, nm in ((0, "mblock", "scale_model_blocks"), (1, "mblock2", "scale_model_blocks_b")):
            blocks = [((cxm - 1.45 + pitch * (k + 0.5), ty, ttop + 0.097), (pitch - 0.008, 0.24, 0.09), 0.0)
                      for k in range(par, 89, 2)]
            merged(nm, blocks, m[key], kind="cube")
        self.model_pts = [(cxm - 1.85, ty, ttop), (cxm + 1.85, ty, ttop + 0.2)]
        self.model_cx = cxm
        return pic

    def _gull(self, name):
        m = self.m
        r = toy.empty(name)
        toy.sphere(f"{name}_body", 0.16, (0, 0, 0.17), scale=(1.6, 0.85, 0.8), mat=m["white"], parent=r, subdiv=1)
        toy.sphere(f"{name}_head", 0.095, (0.24, 0, 0.29), mat=m["white"], parent=r, subdiv=1)
        cone(f"{name}_beak", 0.035, 0.0, 0.13, (0.37, 0, 0.28), (0, R(90), 0), m["orange"], parent=r)
        for s in (-1, 1):
            wg = toy.box(f"{name}_wing{s}", (0.3, 0.36, 0.02), (-0.02, s * 0.2, 0.24), mat=m["grey"], parent=r,
                         bevel=0.005)
            wg.rotation_euler = (R(-12 * s), 0, 0)
            toy.cylinder(f"{name}_leg{s}", 0.012, 0.08, (0.0, s * 0.05, 0.04), mat=m["orange"], parent=r, vertices=6)
            toy.sphere(f"{name}_eye{s}", 0.018, (0.31, s * 0.06, 0.32), mat=m["black"], parent=r, subdiv=0)
        toy.box(f"{name}_tail", (0.16, 0.14, 0.02), (-0.27, 0, 0.2), mat=m["grey"], parent=r, bevel=0.005)
        return r

    def _fish(self, name):
        r = toy.empty(name)
        toy.sphere(f"{name}_body", 0.14, (0, 0, 0.07), scale=(1.6, 0.6, 0.75), mat=self.m["fish"], parent=r, subdiv=1)
        cone(f"{name}_tail", 0.1, 0.0, 0.16, (-0.26, 0, 0.07), (0, R(-90), 0), self.m["fish"], parent=r)
        toy.sphere(f"{name}_eye", 0.02, (0.15, -0.07, 0.1), mat=self.m["black"], parent=r, subdiv=0)
        return r

    def _people(self):
        self.max = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
        self.max.place(1, (0, 0, 0), 0)
        self.max.key("hips", 1, loc=(0, 0, 0.56))
        bpy.context.view_layer.update()
        self.hmax = st.max_height(self.max)
        self.hat_off = self.hmax - self.max.j["head"].matrix_world.translation.z
        self.max.place(1, (-30.6, 0.8, 0.5), 0)
        self.max.auto_blink(1, self.total + 400, seed=11)
        self.max.hold(self.shovel, "R")
        self.shovel.location = (0, -0.02, 0.0)
        self.kids = [Character("Kid1", {"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5",
                                        "hair": "#5B3A1E", "scale": 0.6, "ponytail": True}),
                     Character("Kid2", {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B",
                                        "hair": "#2B1A10", "scale": 0.56})]
        for k, kid in enumerate(self.kids):
            kid.place(1, KID_SPOTS[k], -10 if k == 0 else 10)
            kid.key("hips", 1, loc=(0, 0, 0.56))
            kid.auto_blink(1, self.total + 400, seed=k + 3)

    def _critters(self):
        self.gull = self._gull("gull")
        for wg in (bpy.data.objects["gull_wing-1"], bpy.data.objects["gull_wing1"]):
            toy.add_noise(wg, "rotation_euler", 0, strength=0.9, scale=2.5, phase=wg.name.__len__())
        self.gull_hat = self._gull("gull_hat")
        self.gull_hat.parent = self.max.j["head"]
        # its feet rest 12 mm above the hat's crown (never inside the hat)
        self.gull_hat.location = (0.02, 0, self.hat_off + 0.012)
        self.gull_hat.rotation_euler = (0, 0, R(-70))
        self.gull_dash = self._gull("gull_dash")
        self.gull_dash.parent = self.car
        self.gull_dash.location = (0.52, 0.34, 0.81)
        self.gull_dash.rotation_euler = (0, 0, R(-60))
        self.fish = self._fish("fish")
        # the fish flops onto the camera side of the hat BRIM (not the crown): it stays under the tunnel roof
        self.fish_hat = self._fish("fish_hat")
        self.fish_hat.parent = self.max.j["head"]
        self.fish_hat.location = (-0.34, -0.12, 0.53)
        self.fish_hat.rotation_euler = (0, 0, R(-70))
        self.groups.update({"gull": [self.gull], "gull_hat": [self.gull_hat], "gull_dash": [self.gull_dash],
                            "fish": [self.fish], "fish_hat": [self.fish_hat]})

    def _initial(self):
        for k in (1, 2, 3):
            toy.hide_tree(self.S[k]["root"], 1, True)
        self.stage(1, set())
        self.dock_state(1, None)
        self.armour(1, "none")
        for o in self.tw:
            toy.hide_tree(o, 1, True)
        for o in (self.armour_hit,):
            toy.hide_tree(o, 1, True)
        st.key_glow(self.m["lamp"], 1, 0.0)
        for k in (1, 2, 3):
            d = self.S[k]["lamp"]
            d.energy = 0.0
            d.keyframe_insert("energy", frame=1)

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
        self._settle_jumps()
        self.rig.build()

    def _settle_jumps(self):
        """A key right before a cut jump (key at f-1, next key at f) keeps the FLAT ease it had when its beat
        was staged. Otherwise the next beat's jump bends the previous beat's motion curve after riders (Max on
        the car, the roof, the dredger) were keyed from it, and they drift apart from what they ride."""
        for ob in bpy.data.objects:
            if ob.animation_data is None or ob.animation_data.action is None:
                continue
            for fc in toy.fcurves(ob):
                if fc.data_path not in ("location", "rotation_euler", "scale"):
                    continue
                kps = fc.keyframe_points
                for j in range(len(kps) - 1):
                    a, c = kps[j], kps[j + 1]
                    if c.co.x - a.co.x > 1.01 or a.interpolation != "BEZIER":
                        continue
                    dx = (a.co.x - kps[j - 1].co.x) / 3.0 if j > 0 else 0.33
                    a.handle_left_type = "FREE"
                    a.handle_right_type = "FREE"
                    a.handle_left = (a.co.x - dx, a.co.y)
                    a.handle_right = (a.co.x + 0.33, a.co.y)
                    toy.set_key_interpolation(ob, fc, a, "CONSTANT")

    # ------------------- helpers: state -------------------

    def show(self, obj, f, visible=True):
        toy.hide_tree(obj, f, not visible)

    def stage(self, f, names):
        """At a cut: exactly these optional groups are on stage."""
        for g, objs in self.groups.items():
            for o in objs:
                self.show(o, f, g in names)

    def put(self, obj, f, loc, rot=None):
        toy.key_hold(obj, "location", f - 1)
        obj.location = loc
        obj.keyframe_insert("location", frame=f)
        if rot is not None:
            toy.key_hold(obj, "rotation_euler", f - 1)
            obj.rotation_euler = rot
            obj.keyframe_insert("rotation_euler", frame=f)

    def glide(self, obj, f0, f1, loc, rot=None):
        toy.key_hold(obj, "location", f0)
        obj.location = loc
        obj.keyframe_insert("location", frame=f1)
        if rot is not None:
            toy.key_hold(obj, "rotation_euler", f0)
            obj.rotation_euler = rot
            obj.keyframe_insert("rotation_euler", frame=f1)

    def put_scale(self, obj, f, s):
        toy.key_hold(obj, "scale", f - 1)
        obj.scale = s
        obj.keyframe_insert("scale", frame=f)

    def scale_to(self, obj, f0, f1, s):
        toy.key_hold(obj, "scale", f0)
        obj.scale = s
        obj.keyframe_insert("scale", frame=f1)

    def at_loc(self, obj, f):
        return V(toy.value_at(obj, "location", f))

    def follow_keys(self, dst, src, f0, f1, off, step=2):
        """Key dst's location = src's animated location + off every `step` frames (riding / towing)."""
        frames = list(range(f0, f1, step)) + [f1]
        for f in frames:
            dst.location = self.at_loc(src, f) + V(off)
            dst.keyframe_insert("location", frame=f)
        toy.set_interpolation(dst, "location", frames, "LINEAR")

    def ride(self, who, src, f0, f1, off):
        self.follow_keys(who.root, src, f0, f1, off)

    def sec(self, f, k, on=True, front=True, bulk=(True, True), tanks=True, fill=None, gasket=None, gfront=None,
            loc=None):
        S = self.S[k]
        self.show(S["root"], f, on)
        if not on:
            return
        if loc is not None:
            self.put(S["root"], f, loc, (0, 0, 0))
        self.show(S["front"], f, front)
        for o in S["bulkL"]:
            self.show(o, f, bulk[0])
        for o in S["bulkR"]:
            self.show(o, f, bulk[1])
        for o in S["tanks"]:
            self.show(o, f, tanks)
        if S["gasket"] is not None:
            self.show(S["gasket"], f, gasket is not None)
            if gasket is not None:
                self.show(S["gfront"], f, front if gfront is None else gfront)
                self.put_scale(S["gasket"], f, (gasket, 1, 1))
        if fill is not None:
            for r in S["fills"]:
                self.put_scale(r, f, (1, 1, fill))

    def sections_off(self, f):
        for k in (1, 2, 3):
            self.sec(f, k, on=False)

    def chunks_on(self, f, on):
        for c in self.chunks:
            self.show(c, f, on)

    def tw_state(self, f, flags):
        for o, fl in zip(self.tw, flags):
            self.show(o, f, fl)

    def dock_state(self, f, state):
        r = self.dockres
        if state is None:
            for o in r.parts():
                toy.hide_tree(o, f, True)
            return
        if state == "empty":
            r.empty(f)
            self.dock_level(f, DOCK_FLOOR + 0.03)
        else:
            r.fill(f)
            self.dock_level(f, 0.0)

    def dock_level(self, f, level, f_from=None):
        self.dockres.key_level(f_from if f_from is not None else f - 1, self._dock_lvl)
        self.dockres.key_level(f, level)
        self._dock_lvl = level

    def armour(self, f, mode):
        """none / all / cut (all but the front locking strip, which the cutaway removes)."""
        for s in self.segs:
            for key in ("lockfront", "lockback", "backfill", "armour"):
                on = mode == "all" or (mode == "cut" and key != "lockfront")
                self.show(s[key], f, on)
        self.show(self.armour_hit, f, mode in ("all", "cut"))

    def seg_on(self, f, s, front=True):
        for key in ("lockfront", "lockback", "backfill", "armour"):
            self.show(s[key], f, front or key != "lockfront")

    def lights(self, f, on, ramp=5):
        if on == self._lit:
            return
        self._lit = on
        a, b = (0.0, 7.0) if on else (7.0, 0.0)
        st.key_glow(self.m["lamp"], f, a)
        st.key_glow(self.m["lamp"], f + ramp, b)
        for k in (1, 2, 3):
            d = self.S[k]["lamp"]
            for ff, v in ((f, a * 9.0), (f + ramp, b * 9.0)):
                d.energy = v
                d.keyframe_insert("energy", frame=ff)

    def label(self, text, loc, f0, f1, size=0.42, tilt=-4, parent=None):
        root = st.label(text, loc, f0, f1, size=size, tilt=tilt)
        for f in (f0, f0 + 5, f0 + 8, f1 - 5, f1):
            root.scale = (1, 1, 1)
            root.keyframe_insert("scale", frame=f)
        if parent is not None:
            root.parent = self.carrier(parent)
        return root

    def carrier(self, obj):
        """An empty that copies `obj`'s transform but is NOT in its tree, so showing the block's tree in a
        later beat never re-shows the callouts that ride on it."""
        cache = self.__dict__.setdefault("_carriers", {})
        if obj.name not in cache:
            c = toy.empty(f"carry_{obj.name}")
            con = c.constraints.new("COPY_TRANSFORMS")
            con.target = obj
            cache[obj.name] = c
        return cache[obj.name]

    def link_key(self, obj, f, p0, p1):
        p0, p1 = V(p0), V(p1)
        d = p1 - p0
        obj.location = p0
        obj.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        obj.scale = (1, 1, max(0.05, d.length))
        for path in ("location", "rotation_euler", "scale"):
            obj.keyframe_insert(path, frame=f)

    def chain_keys(self, f0, f1, anchor=None, chain=None, top=0.5):
        anchor, chain = anchor or self.anchor, chain or self.chain
        for f in list(range(f0, f1, 2)) + [f1]:
            hw = self.at_loc(self.ship, f) + self.hawse
            an = self.at_loc(anchor, f) + V((0, 0, top))
            self.link_key(chain, f, hw, an)

    # ------------------- helpers: Max -------------------

    def at(self, f, spot, face=0.0, pose=True):
        self.max.cut_place(f, spot, face)
        if pose:
            self.max.pose(f + 6)

    def seat(self, f0, f1):
        """Seated in the car: thighs forward, knees bent so the shins hang and the shoes rest on the car floor."""
        m = self.max
        if self._seated_end != f0 - 1:
            # stand-up key before sitting, unless the previous beat ended seated (never overwrite its last key)
            m.key("hips", f0 - 1, loc=(0, 0, 0.56))
            for leg in ("legL", "legR"):
                m.key(leg, f0 - 1, rot_deg=(0, 0, 0))
            for kn in ("kneeL", "kneeR"):
                m.key(kn, f0 - 1, rot_deg=(0, 0, 0))
        for f in (f0, f1):
            m.key("hips", f, loc=(0, 0, 0.34))
            for leg in ("legL", "legR"):
                m.key(leg, f, rot_deg=(-85, 0, 0))
            for kn in ("kneeL", "kneeR"):
                m.key(kn, f, rot_deg=(85, 0, 0))
            m.key("shoulderL", f, rot_deg=(-50, -8, 0))
            m.key("shoulderR", f, rot_deg=(-50, 8, 0))
        self._seated_end = f1

    def unseat(self, f):
        m = self.max
        m.key("hips", f - 1, loc=(0, 0, 0.34))
        m.key("hips", f, loc=(0, 0, 0.56))
        for leg in ("legL", "legR"):
            m.key(leg, f - 1, rot_deg=(-85, 0, 0))
            m.key(leg, f, rot_deg=(0, 0, 0))
        for kn in ("kneeL", "kneeR"):
            m.key(kn, f - 1, rot_deg=(85, 0, 0))
            m.key(kn, f, rot_deg=(0, 0, 0))
        self._seated_end = None

    def seated_cheer(self, f0, f1):
        m = self.max
        m.key("shoulderL", f0, rot_deg=(-50, -8, 0))
        m.key("shoulderR", f0, rot_deg=(-50, 8, 0))
        m.key("shoulderL", f0 + 6, rot_deg=(0, -150, 0))
        m.key("shoulderR", f0 + 6, rot_deg=(0, 150, 0))
        m.key("shoulderL", f1, rot_deg=(0, -156, 0))
        m.key("shoulderR", f1, rot_deg=(0, 156, 0))
        m.smile(f0 + 6, big=True)
        m.brows(f0 + 6, 0.6)

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
        m = self.max
        m.pose(f0)
        m.pose(f0 + 5, shoulderL=(-32, -40, 0), shoulderR=(-32, 40, 0), head=(-4, 0, 16))
        m.pose(max(f0 + 6, f1 - 4), shoulderL=(-36, -44, 0), shoulderR=(-36, 44, 0), head=(-4, 0, 18))
        m.brows(f0 + 5, 0.9)
        m.key("mouth", f0 + 5, scale=(1.3, 0.6, 0.7))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f1, 0.0)
        m.pose(f1)
        events.add(f0 + 5, "boing", gain=0.3)

    def jaw_drop(self, f0, f1):
        m = self.max
        m.pose(f0)
        m.pose(f0 + 4, shoulderL=(-35, -118, 0), shoulderR=(-35, 118, 0), head=(-16, 0, 0))
        m.pose(max(f0 + 5, f1 - 2), shoulderL=(-38, -124, 0), shoulderR=(-38, 124, 0), head=(-18, 0, 0))
        m.key("mouth", f0 + 4, scale=(1.3, 0.6, 3.4))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f0 + 4, 1.0)
        m.brows(f1, 0.0)

    def hat_top(self, f):
        return self.at_loc(self.max.root, f) + V((0, 0, self.hmax))

    # ------------------- helpers: camera -------------------

    def close(self, f0, f1, frac=0.42, angle=-88.0, swing=16.0, offset=(0, 0, 0), rise=0.22, who=None, h=1.9):
        st.close_on(self.rig, f0, f1, who or self.max, frac=frac, angle=angle, swing=swing, rise=rise, lens=32.0,
                    look=0.62, offset=offset, cut=True, fstop=5.6, height=h)

    def follow(self, f0, f1, obj, H, angle=-88.0, swing=8.0, off=(0, 0, 0)):
        st.close_on(self.rig, f0, f1, _Who(obj), frac=1.0, angle=angle, swing=swing, rise=0.02, lens=30.0,
                    look=0.0, offset=off, cut=True, fstop=8.0, height=H)

    def frame(self, f0, f1, things, angle=-90.0, swing=10.0, rise=0.16, lens=30.0, margin=0.08):
        if f1 - f0 > 110:
            fm = (f0 + f1) // 2
            st.frame_all(self.rig, f0, fm, things, angle=angle - 4, rise=rise, lens=lens, swing=swing,
                         margin=margin, cut=True)
            st.frame_all(self.rig, fm, f1, things, angle=angle + 4, rise=rise, lens=lens, swing=-swing,
                         margin=margin, cut=True)
        else:
            st.frame_all(self.rig, f0, f1, things, angle=angle, rise=rise, lens=lens, swing=swing, margin=margin,
                         cut=True)

    def frame_steps(self, f0, f1, things, n, angle, rise, lens=30.0, margin=0.08, swing=6.0):
        """frame_all in n short windows so a MOVING subject stays close; the rig glides between windows."""
        cuts = [fr(f0, f1, k / n) for k in range(n + 1)]
        for k in range(n):
            st.frame_all(self.rig, cuts[k], cuts[k + 1], things, angle=angle + swing * k, rise=rise, lens=lens,
                         swing=swing, margin=margin, cut=(k == 0))

    # ------------------- the ladder -------------------

    def a_rewind(self, i, b, e):
        pass

    def a_goal(self, i, b, e):
        m1, g1 = fr(b, e, 0.36), fr(b, e, 0.46)
        self.sections_off(b)
        self.dock_state(b, None)
        self.chunks_on(b, True)
        self.tw_state(b, (False, False, False))
        self.stage(b, {"front_plain", "car", "gull_dash"})
        self.armour(b, "none")
        self.lights(b, False)
        # Max at the water's edge (shoes 8 mm above the beach), the car parked right behind him, its nose toward
        # the sea: the strait opens right beside them, so all three share one close frame
        self.put(self.car, b, (-15.9, 3.6, 0.5), (0, 0, 0))
        self.at(b, (-15.4, 0.9, 0.508), 0)
        self.max.talk(b + 3, m1)
        self.max.point(fr(b, e, 0.08), fr(b, e, 0.3), hand="L", up_deg=40, side_deg=80)
        self.max.smile(b + 4, big=True)
        for k, kid in enumerate(self.kids):
            kid.wave(m1 + 2 * k, g1, hand="R" if k == 0 else "L")
            kid.smile(m1, big=True)
        events.add(m1 + 2, "kids_cheer", gain=0.4)
        self.max.point(g1 + 4, fr(b, e, 0.97), hand="L", up_deg=55, side_deg=85)
        self.max.talk(g1 + 2, e - 4)
        self.close(b, m1, frac=0.42, angle=-86, offset=(0.4, 0, 0))
        self.close(m1, g1, frac=0.34, angle=-92, swing=12, offset=(0.5, 0, 0), who=self.kids[0], h=1.12)
        # the strait he points across stays in the shot: its open water just right of Max, kept close
        self.frame(g1, e, [self.max, self.car, (-13.0, 1.5, -1.0)], angle=-84, rise=0.14)

    def a_fail_dig(self, i, b, e):
        m1, sq, fl0, fl1 = fr(b, e, 0.36), fr(b, e, 0.38), fr(b, e, 0.42), fr(b, e, 0.84)
        self.sections_off(b)
        self.dock_state(b, None)
        self.chunks_on(b, True)
        self.tw_state(b, (False, False, False))
        self.stage(b, {"front_bored", "shovel"})
        self.armour(b, "none")
        # the mud floods the drift: still rising at the beat's middle, knee-deep by 7/8
        self.put_scale(self.flood, b, (1, 1, 0.001))
        self.show(self.flood, fl0, True)
        self.put_scale(self.flood, fl0, (1, 1, 0.02))
        self.scale_to(self.flood, fl0, fl1, (1, 1, 0.85))
        self.show(self.shovel, fl0 + 6, False)
        # Max digs near the end of his drift under the submerged shore (feet 6 mm above its floor, his head
        # well clear of the end wall and the roof)
        self.at(b, (-13.8, 0.4, DIG_Z + 0.006), 80)
        self.max.rake(b + 4, sq - 2, stroke=12)
        for f in range(b + 8, sq, 12):
            events.add(f, "stone_thud", gain=0.25)
        # the soaked clay gives way: mud squirts from the end wall, Max backs off toward the shaft
        self.mud_squirt.run(sq, fl1, (-12.66, 0.45, DIG_Z + 1.4), (-13.7, 0.45, DIG_Z + 0.1), spread=0.3, arc=0.4,
                            period=10)
        self.mud_drops.run(fl0, e, (-13.4, 0.45, DIG_TOP - 0.1), (-13.2, 0.45, DIG_Z + 0.2), spread=0.5, arc=0.1,
                           period=12)
        events.add(sq, "creak", gain=0.5)
        events.add(fl0, "water_rush", duration=fl1 - fl0, gain=0.7)
        events.add(fl0 + 4, "bubbles", gain=0.5)
        self.max.move(fl0 + 2, fl0 + 14, (-14.9, 0.4, DIG_Z + 0.006))
        self.max.turn(fl0 + 2, 0, frames=8)
        self.jaw_drop(fl0 + 4, fr(b, e, 0.66))
        self.shrug(fr(b, e, 0.70), e)
        # why: the sea's weight squeezes the soaked clay in on the drift (arrows drawn in the clay)
        things = [self.max, self.flood_box]
        for k, (base, vec) in enumerate((((-11.3, -0.25, DIG_Z + 1.0), (-1.2, 0, 0)),
                                         ((-13.4, -0.25, -6.2), (0, 0, -1.6)),
                                         ((-14.5, -0.25, -6.2), (0, 0, -1.6)))):
            things.append(st.arrow(f"arrow_press{k}", base, vec, m1 + 2 * k, e, color=BLUE, width=0.2))
        things.append(self.label("SEA PRESSURE\n4 ATM", (-13.9, -0.4, -5.3), m1 + 4, e, size=0.4))
        things.append(self.label("SOAKED CLAY", (-12.2, -0.4, DIG_Z - 0.6), m1 + 8, e, size=0.44))
        self.close(b, m1, frac=0.42, angle=-84, offset=(0.3, 0, -0.1))
        self.frame(m1, e, things, angle=-90, rise=0.08, margin=0.06)

    def a_fix_trench(self, i, b, e):
        m1 = fr(b, e, 0.38)
        self.sections_off(b)
        self.dock_state(b, None)
        self.chunks_on(b, True)
        # the trench water sits inside the plug (hidden by the opaque chunks) and fills every hole the grab opens
        self.tw_state(b, (True, True, True))
        self.stage(b, {"front_plain", "dredger"})
        self.armour(b, "none")
        w = (XI - XB) / 8
        cxs = [XB + (k + 0.5) * w for k in range(8)]
        # five readable bites, one chunk each: nothing is open at the start, the trench grows to the end
        fks = []
        for t in (0.14, 0.31, 0.48, 0.65, 0.82):
            fk = fr(b, e, t)
            if fks:
                fk = max(fk, fks[-1] + 15)
            if fk > e - 10:
                break
            fks.append(fk)
        # the dredger steps along the trench and holds still over each bite
        self.put(self.dredger, b, (cxs[0], 6.9, 0.0))
        for k, fk in enumerate(fks):
            for f in (fk - 3, fk + 3):
                self.dredger.location = (cxs[k], 6.9, 0.0)
                self.dredger.keyframe_insert("location", frame=f)
        self.dredger.keyframe_insert("location", frame=e)
        self.at(b, (cxs[0] - 1.4, 5.7, 0.404), 0)
        self.ride(self.max, self.dredger, b, e, (-1.4, -1.2, 0.404))
        tip = 3.55
        UP, LAND, LOW = -4.0, SEABED + 1.15, TRENCH + 1.2

        def grab_key(f, z):
            self.grab_cable.scale = (1, 1, tip - z)
            self.grab_cable.keyframe_insert("scale", frame=f)
            self.grab.location = (0.0, -4.5, z)
            self.grab.keyframe_insert("location", frame=f)

        def jaws(f, ang):
            for s, pv in self.grab_jaws:
                pv.rotation_euler = (0, R(ang * s), 0)
                pv.keyframe_insert("rotation_euler", frame=f)

        OPEN, SHUT = -30, 4
        grab_key(b, 0.55)
        jaws(b, OPEN)
        self.show(self.grab_load, b, False)
        prev = b
        for k, fk in enumerate(fks):
            d0 = max(prev + 1, fk - 4)
            grab_key(d0, UP)
            if k:
                # the jaws swing open again (the last load drops away) as the grab goes down for the next bite
                jaws(prev, SHUT)
                self.show(self.grab_load, d0, False)
                jaws(min(d0 + 2, fk - 2), OPEN)
            # it lands open on the seabed, bites in (the block of seabed is gone), shuts on the mud and lifts
            grab_key(fk - 1, LAND)
            self.show(self.chunks[k], fk, False)
            grab_key(fk + 2, LOW)
            jaws(fk + 2, OPEN)
            jaws(fk + 5, SHUT)
            self.show(self.grab_load, fk + 4, True)
            grab_key(fk + 5, LOW)
            up = min(fk + 11, e)
            grab_key(up, UP)
            prev = up
            events.add(fk, "steel_clank", gain=0.35)
        self.dredge_puffs.emit(fks, lambda f: self.at_loc(self.dredger, f) + V((0, -4.5, SEABED + 0.3)), rise=0.8,
                               life=18)
        events.add(b, "engine_rev", duration=e - b, gain=0.35)
        self.max.sweep(b + 4, m1 - 2, hand="R", stroke=10)
        self.max.point(m1 + 2, fr(b, e, 0.7), hand="R", up_deg=20, side_deg=60)
        self.v_arms(fr(b, e, 0.76), e)
        # the close shot looks from Max's left, so the grab cable never crosses his head
        self.close(b, m1, frac=0.40, angle=-102, offset=(0.3, 0, -0.2))
        # then one tracking shot keeps the barge, Max on its deck AND the grab on the seabed together
        lens = 28.0
        dist = st.frame_distance(14.0, 1.0, lens)
        keys = []
        for f in list(range(m1, e, 3)) + [e]:
            t = (f - m1) / max(1, e - m1)
            xs = [self.at_loc(self.dredger, min(e, max(b, f + d))).x for d in (-6, -3, 0, 3, 6)]
            aim = V((sum(xs) / len(xs) - 0.3, 4.0, -3.9))
            keys.append((f, aim + V((0.9 * (t - 0.5), -dist, 0.9)), aim))
        self.rig.track(m1, e, keys, lens=lens, fstop=8.0, cut=True)

    def a_fail_float(self, i, b, e):
        S1 = self.S[1]["root"]
        c1, c2, m1 = fr(b, e, 0.10), fr(b, e, 0.16), fr(b, e, 0.36)
        g0, g1 = fr(b, e, 0.18), fr(b, e, 0.24)
        fa, fb = fr(b, e, 0.22), fr(b, e, 0.58)
        d0, d1 = fr(b, e, 0.64), fr(b, e, 0.96)
        land = fr(b, e, 0.80)
        self.sections_off(b)
        self.chunks_on(b, False)
        self.tw_state(b, (True, True, True))
        self.sec(b, 1, front=True, bulk=(False, False), tanks=False, fill=0.02)
        self.stage(b, {"front_dock", "dock", "gull", "dockflood"})
        self.armour(b, "none")
        self.lights(b, False)
        self.dock_state(b, "empty")
        self.put(self.gate, b, self.gate_home)
        self.glide(self.gate, g0, g1, self.gate_home - V((0, 0, 4.1)))
        # the steel bulkheads seal both ends of the cast box
        for o in self.S[1]["bulkL"]:
            self.show(o, c1, True)
        for o in self.S[1]["bulkR"]:
            self.show(o, c2, True)
        events.add(c1, "steel_clank", gain=0.6)
        events.add(c2, "steel_clank", gain=0.6)
        events.add(g0, "creak", gain=0.5)
        events.add(fa, "water_rush", duration=fb - fa, gain=0.7)
        # the dock floods (clearly blue water, rising linearly) and the sealed box rises WITH the water
        base = DOCK_FLOOR + 0.012
        h0, h1 = 0.05, -base
        fl = self.dflood
        self.show(fl, b, False)
        self.show(fl, fa, True)
        fl.scale = (1, 1, h0)
        fl.keyframe_insert("scale", frame=b)
        fl.keyframe_insert("scale", frame=fa)
        fl.scale = (1, 1, h1)
        fl.keyframe_insert("scale", frame=fb)
        toy.set_interpolation(fl, "scale", [fa], "LINEAR")

        def level(f):
            t = min(1.0, max(0.0, (f - fa) / max(1, fb - fa)))
            return base + h0 + (h1 - h0) * t

        z0 = S1_DOCK[2]
        self.put(S1, b, S1_DOCK, (0, 0, 0))
        fs = list(range(fa, fb, 2)) + [fb]
        r0 = None
        for f in fs:
            z = max(z0, level(f) + FLOAT_HI)
            if r0 is None and z > z0 + 0.01:
                r0 = f
            S1.location = (S1_DOCK[0], 0.0, z)
            S1.keyframe_insert("location", frame=f)
        toy.set_interpolation(S1, "location", fs, "LINEAR")
        r0 = r0 or fr(b, e, 0.42)
        events.add(r0, "bubbles", gain=0.5)
        # ... and floats away out of the open gate
        self.glide(S1, d0, d1, (-11.4, 0.0, FLOAT_HI), (0, R(1.2), 0))
        # Max rides the roof
        off = (1.4, 1.4, HH + 0.004)
        self.at(b, tuple(self.at_loc(S1, b) + V(off)), 0)
        self.ride(self.max, S1, b, e, off)
        # the seagull flies in and lands on his hat
        g_start = fr(b, e, 0.60)
        self.put(self.gull, g_start, tuple(self.hat_top(g_start) + V((-2.6, 1.2, 2.4))), (0, 0, R(10)))
        self.glide(self.gull, g_start, land, tuple(self.hat_top(land) + V((0, 0, 0.012))), (0, 0, R(-70)))
        self.show(self.gull, b, True)
        self.show(self.gull, land, False)
        self.show(self.gull_hat, land, True)
        events.add(land, "boing", gain=0.4)
        self.max.talk(b + 3, c2 + 6)
        self.max.point(c2 + 2, g1, hand="L", up_deg=40, side_deg=80)
        self.max.smile(b + 4, big=True)
        self.jaw_drop(r0, fr(b, e, 0.62))
        self.shrug(fr(b, e, 0.82), e)
        # why: a BIG buoyancy arrow beats a small weight arrow, both drawn on the box's front wall; the two
        # labels are big enough to read on a phone and sit clear of both arrows
        f0 = fr(b, e, 0.34)
        ab = st.arrow("arrow_buoy", (-2.62, -0.3, -1.2), (0, 0, 2.5), f0, e, color=BLUE, width=0.44,
                      parent=self.carrier(S1))
        st.arrow("arrow_weight", (2.68, -0.3, 1.05), (0, 0, -0.75), f0 + 4, e, color=YELLOW, width=0.15,
                 parent=self.carrier(S1))
        lb = self.label("BUOYANCY", (-0.5, -0.55, -0.72), f0, e, size=0.85, parent=S1)
        lw = self.label("WEIGHT", (1.2, -0.55, 0.45), f0 + 4, e, size=0.75, parent=S1)
        self.close(b, m1, frac=0.40, angle=-60, offset=(0.9, 0, -0.5))
        self.frame(m1, d0, [self.S[1]["front"], ab, self.max, lb, lw], angle=-66, rise=0.12)
        # it floats away: the box, its arrows and Max on the roof stay framed close as it drifts out
        self.frame_steps(d0, e, [self.S[1]["front"], ab, self.max, lb, lw], 2, angle=-70, rise=0.12, swing=6.0)

    def a_fix_ballast(self, i, b, e):
        S1 = self.S[1]["root"]
        tow, v0, v1 = fr(b, e, 0.22), fr(b, e, 0.22), fr(b, e, 0.28)
        f0, f1, w0, w1, m1 = fr(b, e, 0.24), fr(b, e, 0.56), fr(b, e, 0.40), fr(b, e, 0.84), fr(b, e, 0.38)
        self.sections_off(b)
        self.chunks_on(b, False)
        self.tw_state(b, (True, True, True))
        self.dock_state(b, "full")
        self.put(self.gate, b, self.gate_home - V((0, 0, 4.1)))
        self.sec(b, 1, front=False, bulk=(True, True), tanks=True, fill=0.02)
        self.stage(b, {"front_dock", "dock", "tugs", "towline", "winch"})
        self.armour(b, "none")
        # towed over the trench, then lowered WHILE the tanks still fill: at the beat's middle the blue water is
        # still rising and the block is on its way down; it lands by 7/8
        self.put(S1, b, (-13.4, 0.0, FLOAT_Z), (0, 0, 0))
        self.glide(S1, b + 2, tow, (SX[0], 0.0, FLOAT_Z))
        self.glide(S1, w0, w1, (SX[0], 0.0, TUBE_Z))
        for tug, off in zip(self.tugs, ((1.9, 6.2, -FLOAT_Z), (-2.3, 6.2, -FLOAT_Z))):
            self.put(tug, b, tuple(self.at_loc(S1, b) + V(off)), (0, 0, 0))
            self.follow_keys(tug, S1, b + 1, tow, off)
        for ln in self.towlines:
            self.show(ln, f0, False)
        self.put(self.winch, b, (SX[0], 9.6, 0.0))
        for c in self.cables:
            self.show(c, f0, True)
            for f in list(range(f0, e, 2)) + [e]:
                c.scale = (1, 1, 3.4 - (self.at_loc(S1, f).z + HH + 0.25))
                c.keyframe_insert("scale", frame=f)
        events.add(b, "engine_rev", duration=tow - b, gain=0.4)
        # valves open: seawater into the ballast tanks until the box is just heavier than the water
        for wv in self.S[1]["valves"]:
            self.put(wv, v0, (wv.location.x, wv.location.y, wv.location.z), (R(90), 0, 0))
            self.glide(wv, v0, v1, tuple(wv.location), (R(90), R(400), 0))
        events.add(v0, "switch", gain=0.5)
        for r in self.S[1]["fills"]:
            self.scale_to(r, f0, f1, (1, 1, 1.12))
        events.add(f0, "water_rush", duration=f1 - f0, gain=0.6)
        events.add(w0, "creak", duration=w1 - w0, gain=0.4)
        events.add(w1, "stone_thud", gain=0.5)
        self.show(self.tw[0], w1, False)
        off = (0.9, 1.4, HH + 0.004)
        self.at(b, tuple(self.at_loc(S1, b) + V(off)), 0)
        self.ride(self.max, S1, b, e, off)
        self.max.wave(b + 4, fr(b, e, 0.2), hand="L")
        self.max.point(v0, fr(b, e, 0.36), hand="R", up_deg=-20, side_deg=40)
        self.max.brows(w0, 0.8)
        self.v_arms(w1, e)
        lt = self.label("BALLAST TANKS", (-1.2, -0.5, 0.72), f0 + 3, e, size=0.36, parent=S1)
        hb = fr(b, e, 0.36)
        st.arrow("arrow_buoy2", (-2.7, -0.3, -2.8), (0, 0, 1.15), hb, e, color=BLUE, width=0.2,
                 parent=self.carrier(S1))
        st.arrow("arrow_heavy", (2.2, -0.3, 0.95), (0, 0, -1.7), hb, e, color=YELLOW, width=0.2,
                 parent=self.carrier(S1))
        self.label("JUST HEAVIER", (0.9, -0.6, -1.85), hb + 2, e, size=0.36, parent=S1)
        self.close(b, m1, frac=0.40, angle=-84, offset=(0.4, 0, -0.3))
        self.follow(m1, e, S1, 12.2, angle=-88, swing=8, off=(0, 1.4, 0.9))
        return lt

    def a_fail_leak(self, i, b, e):
        S2 = self.S[2]["root"]
        land, m1, lk = fr(b, e, 0.30), fr(b, e, 0.38), fr(b, e, 0.40)
        fish_land = fr(b, e, 0.60)
        self.sections_off(b)
        self.chunks_on(b, False)
        self.tw_state(b, (False, True, True))
        self.dock_state(b, "full")
        self.put(self.gate, b, self.gate_home - V((0, 0, 4.1)))
        self.sec(b, 1, front=False, bulk=(True, False), tanks=True, fill=1.12, loc=(SX[0], 0, TUBE_Z))
        self.sec(b, 2, front=True, bulk=(True, True), tanks=True, fill=1.12, gasket=None)
        self.stage(b, {"front_dock", "dock", "winch", "cables", "leak"})
        self.armour(b, "none")
        self.put(S2, b, (SX_LEAK, 0.0, -1.6), (0, 0, 0))
        self.glide(S2, b + 2, land, (SX_LEAK, 0.0, TUBE_Z))
        self.put(self.winch, b, (SX_LEAK, 9.6, 0.0))
        for c in self.cables:
            for f in list(range(b, land, 2)) + [land]:
                c.scale = (1, 1, 3.4 - (self.at_loc(S2, f).z + HH + 0.25))
                c.keyframe_insert("scale", frame=f)
        self.show(self.tw[1], land, False)
        events.add(land, "stone_thud", gain=0.6)
        events.add(land + 1, "steel_clank", gain=0.4)
        # block two lands crooked: a dark gap between the blocks
        self.show(self.leak_gap, b, False)
        self.show(self.leak_gap, land, True)
        # the gap: the sea jets in and floods block one's floor
        self.show(self.leak_jet, b, False)
        self.show(self.leak_jet, lk - 2, True)
        self.put_scale(self.leak_jet, lk - 2, (0.05, 0.05, 0.05))
        self.scale_to(self.leak_jet, lk - 2, lk + 3, (1, 1, 1))
        self.show(self.pool, b, False)
        self.show(self.pool, lk, True)
        self.put_scale(self.pool, lk, (1, 1, 0.01))
        self.scale_to(self.pool, lk, fr(b, e, 0.85), (1, 1, 0.32))
        self.leak_drops.run(lk, e, (SX[0] + 2.95, 1.3, -8.8), (SX[0] + 0.85, 1.3, -8.3), spread=0.35, arc=0.25,
                            period=9)
        events.add(lk, "water_rush", duration=e - lk, gain=0.7)
        self.at(b, (SX[0] + 0.9, 1.3, ROAD + 0.004), 70)
        self.max.wave(b + 4, land - 2, hand="L")
        self.max.look_at(b + 4, (SX_LEAK, 1.4, -6.0), hold=max(0, land - b - 8))
        self.jaw_drop(lk, fr(b, e, 0.58))
        self.shrug(fr(b, e, 0.64), e)
        # a fish rides the jet in, arcs around Max's head on the camera side and flops onto his hat brim
        mr = self.at_loc(self.max.root, fish_land)
        fish_mid = fr(b, e, 0.50)
        self.put(self.fish, lk + 2, (SX[0] + 2.9, 1.3, -8.8), (0, 0, R(180)))
        self.show(self.fish, b, False)
        self.show(self.fish, lk + 2, True)
        self.glide(self.fish, lk + 2, fish_mid, tuple(mr + V((0.7, -0.95, 1.6))), (0, 0, R(200)))
        self.glide(self.fish, fish_mid, fish_land, tuple(mr + V((-0.2, -0.62, 1.66))), (0, 0, R(160)))
        self.show(self.fish, fish_land, False)
        self.show(self.fish_hat, fish_land, True)
        events.add(fish_land, "boing", gain=0.45)
        # the sea arrows and the GAP! label sit just above the joint, so the solved shot stays close on the leak
        gx = SX[0] + 3.0 + 0.07
        things = [self.leak_jet, self.pool, self.max, self.leak_gap]
        things.append(st.arrow("arrow_sea0", (gx, -0.2, -6.5), (0, 0, -0.95), m1 - 4, e, color=BLUE, width=0.14))
        things.append(st.arrow("arrow_sea1", (gx + 1.2, -0.2, -6.7), (-1.0, 0, -0.7), m1 - 2, e, color=BLUE,
                               width=0.12))
        things.append(self.label("GAP!", (gx, -0.4, -5.9), m1 - 4, e, size=0.5))
        self.close(b, m1, frac=0.42, angle=-78, offset=(0.5, 0, -0.2))
        self.frame(m1, e, things, angle=-86, rise=0.1)

    def a_fix_seal(self, i, b, e):
        S2 = self.S[2]["root"]
        g = self.S[2]["gasket"]
        gf = self.S[2]["gfront"]
        j0, j1, m1 = fr(b, e, 0.06), fr(b, e, 0.22), fr(b, e, 0.40)
        p0, p1, h0, h1 = fr(b, e, 0.26), fr(b, e, 0.42), fr(b, e, 0.46), fr(b, e, 0.80)
        self.sections_off(b)
        self.chunks_on(b, False)
        self.tw_state(b, (False, False, True))
        self.dock_state(b, "full")
        self.put(self.gate, b, self.gate_home - V((0, 0, 4.1)))
        self.sec(b, 1, front=False, bulk=(True, True), tanks=True, fill=1.12, loc=(SX[0], 0, TUBE_Z))
        # the black gasket ring's front leg stays on in the cutaway: the rubber is big and dark at the joint
        self.sec(b, 2, front=False, bulk=(True, True), tanks=True, fill=1.12, gasket=1.0, gfront=True,
                 loc=(SX[0] + 3.0 + G0 + 3.0, 0, TUBE_Z))
        self.stage(b, {"front_dock", "dock", "jacks", "pump", "joint"})
        self.armour(b, "none")
        # jacks pull block two gently into contact
        self.glide(S2, j0, j1, (SX[0] + 3.0 + G0 * 0.9 + 3.0, 0, TUBE_Z))
        self.scale_to(g, j0, j1, (0.9, 1, 1))
        events.add(j0, "creak", gain=0.5)
        # pumps empty the water between the two bulkheads
        self.put_scale(self.joint, b, (1, 1, 2.03))
        self.scale_to(self.joint, p0, p1, (1, 1, 0.03))
        self.show(self.joint, p1 + 1, False)
        events.add(p0, "pump", duration=p1 - p0, gain=0.6)
        # the sea pressure shoves block two home and squashes the rubber: still squashing at the beat's
        # middle, shut by 7/8
        self.glide(S2, h0, h1, (SX[1], 0, TUBE_Z))
        self.scale_to(g, h0, h1, (GS, 1, 1))
        events.add(h0, "creak", gain=0.4)
        events.add(h1, "stone_thud", gain=0.7)
        sf = fr(b, e, 0.82)
        for o in self.groups["seal"][:3]:
            self.show(o, sf, True)
        events.add(sf, "steel_clank", gain=0.6)
        self.at(b, (SX[0] + 1.55, 1.0, ROAD + 0.004), 60)
        self.max.point(j0, j1 + 4, hand="L", up_deg=60, side_deg=70)
        self.max.sweep(p0 - 4, p1, hand="R", stroke=10)
        self.v_arms(fr(b, e, 0.84), e)
        # the push is drawn on block two right beside the joint (they ride with it and shove toward the rubber)
        things = [gf, self.max]
        f0 = m1 + 2
        for k, z in enumerate((-0.7, 0.0, 0.7)):
            things.append(st.arrow(f"arrow_clamp{k}", (-1.4, -0.3, z), (-1.1, 0, 0), f0 + 2 * k, e, color=BLUE,
                                   width=0.2, parent=self.carrier(S2)))
        things.append(self.label("SEA PRESSURE", (-1.9, -0.5, 1.95), f0, e, size=0.5, parent=S2))
        things.append(self.label("RUBBER GASKET", (SX[0] + 3.2, -0.5, TUBE_Z - 1.95), f0 + 4, e, size=0.5))
        self.close(b, m1, frac=0.42, angle=-76, offset=(0.5, 0, -0.1))
        self.frame(m1, e, things, angle=-84, rise=0.12, margin=0.06)

    def _three(self, f, front, tanks=True, bulk=True, gfront=None):
        for k in (1, 2, 3):
            self.sec(f, k, front=front, bulk=(bulk, bulk), tanks=tanks, fill=1.12,
                     gasket=GS if k > 1 else None, gfront=gfront, loc=(SX[k - 1], 0, TUBE_Z))

    def _anchor_drop(self, t0, t1, ledge_y=5.6, anchor=None, chain=None, lift=0.47):
        anchor, chain = anchor or self.anchor, chain or self.chain
        hw0 = self.at_loc(self.ship, t0) + self.hawse
        self.put(anchor, t0, tuple(hw0 + V((0, 0, -0.6))), (0, 0, 0))
        self.show(anchor, t0, True)
        self.show(chain, t0, True)
        self.glide(anchor, t0, t1, (hw0.x, ledge_y, BACK_TOP + lift), (R(10), 0, 0))
        events.add(t0, "pour", duration=t1 - t0, gain=0.4)
        events.add(t1, "stone_thud", gain=0.4)

    def a_fail_anchor(self, i, b, e):
        t0, t1, cl, m1 = fr(b, e, 0.30), fr(b, e, 0.37), fr(b, e, 0.46), fr(b, e, 0.38)
        self.chunks_on(b, False)
        self.tw_state(b, (False, False, False))
        self.dock_state(b, "full")
        self.put(self.gate, b, self.gate_home - V((0, 0, 4.1)))
        self._three(b, front=True)
        self.stage(b, {"front_dock", "dock", "ship", "seal"})
        self.armour(b, "none")
        self.put(self.ship, b, (-9.0, 6.6, 0.0), (0, 0, 0))
        self.glide(self.ship, b, e, (0.5, 6.6, 0.0))
        self._anchor_drop(t0, t1)
        roof = TUBE_Z + HH
        self.glide(self.anchor, t1, cl, (-1.5, 3.9, roof + 0.47), (R(28), 0, R(10)))
        self.glide(self.anchor, cl, fr(b, e, 0.7), (-0.7, 2.7, roof + 0.46), (R(32), 0, R(14)))
        self.chain_keys(t0, e)
        events.add(t1, "rumble", duration=cl - t1, gain=0.6)
        events.add(cl, "steel_clank", gain=0.9)
        events.add(cl, "stone_thud", gain=0.8)
        for o in self.crack:
            self.show(o, cl + 1, True)
        Puffs("puff_crack", "#9B958A", count=12, size=0.22, seed=13).emit(
            range(cl, cl + 14, 3), lambda f: V((-1.4, 0.0, roof)), rise=0.6, life=16)
        # Max celebrates on the bare tube, then dives behind a rock pile
        self.at(b, (-2.6, 1.5, roof + 0.004), 0)
        self.v_arms(b + 3, fr(b, e, 0.26))
        self.max.move(fr(b, e, 0.28), fr(b, e, 0.33), (0.4, 4.0, -5.6))
        self.max.move(fr(b, e, 0.33), m1, (3.0, 6.3, BACK_TOP + 0.004))
        events.add(m1, "boing", gain=0.4)
        self.max.turn(m1, -40, frames=6)
        self.max.look_at(m1 + 4, (-1.5, 3.9, roof + 0.4), hold=max(0, e - m1 - 10))
        self.max.brows(cl, 1.0)
        self.max.key("mouth", cl + 2, scale=(1.2, 0.6, 2.4))
        self.max.key("mouth", e, scale=(0.8, 0.6, 1.4))
        self.close(b, m1, frac=0.42, angle=-84, swing=14)
        self.frame(m1, e, [self.anchor, self.crack[1], self.crack[-1], self.max], angle=-84, rise=0.35)

    def a_fix_armor(self, i, b, e):
        m1, t0, t1 = fr(b, e, 0.38), fr(b, e, 0.40), fr(b, e, 0.48)
        hit, apex, hit2, hop, rest = (fr(b, e, 0.70), fr(b, e, 0.78), fr(b, e, 0.85), fr(b, e, 0.90),
                                      fr(b, e, 0.95))
        ab = self.anchor_b
        self.chunks_on(b, False)
        self.tw_state(b, (False, False, False))
        self.dock_state(b, "full")
        self.put(self.gate, b, self.gate_home - V((0, 0, 4.1)))
        self._three(b, front=True)
        self.stage(b, {"front_dock", "dock", "stoner", "ship", "seal", "anchor_b", "chain_b"})
        self.armour(b, "none")
        # the stone-dumping vessel lays gravel, backfill and the rock blanket along the whole tunnel
        self.put(self.stoner, b, (-9.4, 2.4, 0.0), (0, 0, 0))
        self.glide(self.stoner, b + 2, fr(b, e, 0.36), (-4.0, 2.4, 0.0))
        self.glide(self.stoner, fr(b, e, 0.36), fr(b, e, 0.66), (4.0, 2.4, 0.0))
        for s in self.segs:
            fk = next((f for f in range(b, e) if self.at_loc(self.stoner, f).x + 1.2 >= s["x0"] + 0.6), None)
            if fk is not None:
                self.seg_on(fk, s)
        self.show(self.armour_hit, fr(b, e, 0.44), True)
        self.grav_puffs.emit(range(b + 2, fr(b, e, 0.66), 4),
                             lambda f: self.at_loc(self.stoner, f) + V((1.2, 0, -7.0)), rise=0.5, life=16)
        events.add(b, "pour", duration=fr(b, e, 0.66) - b, gain=0.5)
        events.add(b, "engine_rev", duration=fr(b, e, 0.66) - b, gain=0.3)
        # the next ship drags its big red anchor over the blanket: it strikes the rocks and bounces up and away
        self.put(self.ship, b, (-8.0, 6.6, 0.0), (0, 0, 0))
        self.glide(self.ship, b, e, (2.0, 6.6, 0.0))
        self.put(ab, b, (0.0, 3.0, ARMOUR_TOP + ANCHOR_LIFT), (0, 0, 0))
        self._anchor_drop(t0, t1, anchor=ab, chain=self.chain_b, lift=ANCHOR_LIFT)
        az = ARMOUR_TOP + ANCHOR_LIFT
        for f, p, rot in ((fr(b, e, 0.60), (-0.5, 4.7, az + 0.25), (R(25), 0, R(8))),
                          (hit, (-0.2, 3.0, az), (R(30), 0, R(14))),
                          (apex, (0.6, 2.5, az + 1.25), (R(-25), 0, R(30))),
                          (hit2, (1.2, 2.1, az - 0.04), (R(15), 0, R(36))),
                          (hop, (1.5, 1.9, az + 0.45), (R(4), 0, R(38))),
                          (rest, (1.7, 1.8, az - 0.04), (R(10), 0, R(40)))):
            toy.key_hold(ab, "location", max(t1, f - 6))
            toy.key_hold(ab, "rotation_euler", max(t1, f - 6))
            ab.location = p
            ab.rotation_euler = rot
            ab.keyframe_insert("location", frame=f)
            ab.keyframe_insert("rotation_euler", frame=f)
        self.chain_keys(t0, e, anchor=ab, chain=self.chain_b, top=0.8)
        # impact cue: a clank, a burst of rock dust where it strikes, an arrow showing the rebound
        for f in (hit, hit2):
            events.add(f, "steel_clank", gain=0.7)
        events.add(hit, "boing", gain=0.5)
        self.impact.emit([hit, hit + 2, hit + 4, hit2, hit2 + 2],
                         lambda f: self.at_loc(ab, f) + V((0, -0.5, -0.7)), rise=0.5, life=14)
        bounce = st.arrow("arrow_bounce", (0.0, 1.0, az - 0.3), (0.9, 0, 1.2), hit, e, color=YELLOW, width=0.16)
        tun = self.label("TUNNEL", (-0.4, -0.45, -8.75), m1, e, size=0.48)
        # Max pours from the vessel, then watches from the seabed beside the rock pile
        off = (-1.8, -0.9, 0.604)
        self.at(b, tuple(self.at_loc(self.stoner, b) + V(off)), 0)
        self.ride(self.max, self.stoner, b, m1 - 1, off)
        self.max.cut_place(m1, (-2.3, 5.4, BACK_TOP + 0.004), 0)
        self.max.pose(m1 + 4)
        self.max.sweep(b + 3, m1 - 4, hand="R", stroke=10)
        self.max.look_at(m1 + 4, (0.0, 3.0, az), hold=max(0, hit - m1 - 8))
        self.max.point(fr(b, e, 0.56), fr(b, e, 0.78), hand="L", up_deg=10, side_deg=60)
        self.v_arms(fr(b, e, 0.80), e)
        self.close(b, m1, frac=0.40, angle=-82, offset=(0.6, 0, -0.4))
        self.frame(m1, e, [self.armour_hit, ab, self.max, tun, bounce], angle=-86, rise=0.38)

    def drive_scene(self, b, e, hook):
        self.chunks_on(b, False)
        self.tw_state(b, (False, False, False))
        self.dock_state(b, "full")
        self.put(self.gate, b, self.gate_home - V((0, 0, 4.1)))
        self._three(b, front=False, tanks=False, bulk=not hook, gfront=False)
        self.stage(b, {"front_final", "dock", "car", "gull_dash", "seal", "ship"})
        self.armour(b, "cut")
        x0, x1 = (-9.0, 3.5) if hook else (-10.4, 4.6)
        go = b + 2 if hook else fr(b, e, 0.34)
        self.put(self.car, b, (x0, 1.4, ROAD), (0, 0, 0))
        self.glide(self.car, go, e, (x1, 1.4, ROAD))
        events.add(go, "engine_rev", duration=e - go, gain=0.5)
        self.put(self.ship, b, (8.0, 3.0, 0.0), (0, 0, 0))
        self.glide(self.ship, b, e, (-6.0, 3.0, 0.0))
        self.max.cut_place(b, tuple(self.at_loc(self.car, b) + V(SEAT_OFF)), SEAT_FACE)
        self.seat(b, e)
        self.ride(self.max, self.car, b, e, SEAT_OFF)
        self.max.smile(b + 2, big=True)
        if hook:
            self.lights(b, True, ramp=1)
            self.seated_cheer(fr(b, e, 0.55), e)
            self.follow(b, e, self.car, 6.4, angle=-84, swing=12, off=(0.2, 0, 1.25))
            return
        # bulkheads cut away (sparks), then the lights come on
        cuts = ((fr(b, e, 0.10), ((1, "bulkR"), (2, "bulkL"))), (fr(b, e, 0.16), ((2, "bulkR"), (3, "bulkL"))),
                (fr(b, e, 0.22), ((1, "bulkL"), (3, "bulkR"))))
        for f, items in cuts:
            for k, side in items:
                for o in self.S[k][side]:
                    self.show(o, f, False)
            events.add(f, "steel_clank", gain=0.5)
        self.spark.emit([f for f, _ in cuts], lambda f: V((SX[0] + 2.6, 1.3, ROAD + 1.0)), rise=0.4, life=10)
        self.lights(fr(b, e, 0.26), True)
        events.add(fr(b, e, 0.26), "power_up", gain=0.6)
        events.add(fr(b, e, 0.28), "hum", duration=e - fr(b, e, 0.28), gain=0.3)
        self.max.brows(fr(b, e, 0.27), 0.9)
        self.seated_cheer(fr(b, e, 0.72), e)
        self.close(b, fr(b, e, 0.38), frac=0.42, angle=-74, offset=(0.4, 0, -0.35))
        self.follow(fr(b, e, 0.38), e, self.car, 6.4, angle=-88, swing=10, off=(0.2, 0, 1.25))

    def a_drive(self, i, b, e):
        self.drive_scene(b, e, hook=False)

    def a_finale(self, i, b, e):
        top, park, m1 = fr(b, e, 0.2), fr(b, e, 0.34), fr(b, e, 0.38)
        self.chunks_on(b, False)
        self.tw_state(b, (False, False, False))
        self.dock_state(b, "full")
        self._three(b, front=False, tanks=False, bulk=False, gfront=False)
        self.stage(b, {"front_final", "dock", "car", "gull_dash", "seal"})
        self.armour(b, "cut")
        x0 = 41.0
        pitch = math.atan(RAMP_K)
        self.put(self.car, b, (x0, 1.4, rfloor(x0) + 0.045), (0, -pitch, 0))
        self.glide(self.car, b + 1, top, (RX1 + 0.2, 1.4, 0.8), (0, 0, 0))
        self.glide(self.car, top, park, (50.2, 1.3, GRASS_Z), (0, 0, 0))
        events.add(b, "engine_rev", duration=park - b, gain=0.5)
        self.max.cut_place(b, tuple(self.at_loc(self.car, b) + V(SEAT_OFF)), SEAT_FACE)
        self.seat(b, m1 - 1)
        self.ride(self.max, self.car, b, m1 - 1, SEAT_OFF)
        self.seated_cheer(fr(b, e, 0.2), m1 - 1)
        # out of the car: Max and the kids cheer at the picnic
        self.unseat(m1)
        self.at(m1, (52.0, 0.9, GRASS_Z + 0.004), 0)
        self.v_arms(fr(b, e, 0.42), e)
        for k, kid in enumerate(self.kids):
            kid.cut_place(b, KID_SPOTS[k], -15 if k == 0 else 15)
            kid.cheer(fr(b, e, 0.40) + 3 * k, e)
            kid.smile(fr(b, e, 0.40), big=True)
        events.add(fr(b, e, 0.40), "kids_cheer", gain=0.7)
        self.close(b, m1, frac=0.42, angle=-80, offset=(0.5, 0, -0.3))
        self.frame(m1, e, [self.car, self.max, self.kids[0], self.kids[1]], angle=-86, rise=0.14)

    def a_scale(self, i, b, e):
        m1 = fr(b, e, 0.38)
        self.chunks_on(b, False)
        self.dock_state(b, "full")
        self._three(b, front=False, tanks=False, bulk=False, gfront=False)
        self.stage(b, {"front_final", "dock", "car", "gull_dash", "seal"})
        self.armour(b, "cut")
        self.put(self.car, b, (50.2, 1.3, GRASS_Z), (0, 0, 0))
        cx = self.model_cx
        # Max stands right behind the island end of the model table, facing us: he and the whole model share one
        # close frame, and his right arm (screen left) reaches out over the chain of blocks to the end of the beat
        self.at(b, (cx + 1.35, 3.1, GRASS_Z + 0.004), 0)
        self.max.point(b + 4, fr(b, e, 0.97), hand="R", up_deg=45, side_deg=80)
        self.max.look_at(b + 8, (cx - 0.4, 2.0, GRASS_Z + 0.9), hold=max(0, fr(b, e, 0.9) - b - 12))
        self.max.smile(b + 4, big=True)
        self.max.brows(fr(b, e, 0.5), 0.6)
        # the labels sit right above the model (never over Max), popping in after the cut to the framed shot
        labs = [self.label("89 BLOCKS", (cx - 0.75, 2.25, GRASS_Z + 1.6), m1 + 2, e, size=0.5),
                self.label("18 km", (cx - 0.75, 2.25, GRASS_Z + 1.12), m1 + 6, e, size=0.5)]
        blocks = [bpy.data.objects["scale_model_blocks"], bpy.data.objects["scale_model_blocks_b"]]
        sea = bpy.data.objects["scale_model_sea"]
        self.close(b, m1, frac=0.42, angle=-84, offset=(-0.5, 0, -0.2))
        # a close, slightly high view: the long blue strait and its block chain read across the frame
        self.frame(m1, e, blocks + [sea, self.max] + labs, angle=-88, rise=0.34, margin=0.06)

    # ------------------- hooks (epilogue, after the finale) -------------------

    def a_float_hook(self, i, h0, h1):
        b, e = h0, h1
        S1 = self.S[1]["root"]
        land = fr(b, e, 0.70)
        self.sections_off(b)
        self.chunks_on(b, False)
        self.tw_state(b, (True, True, True))
        self.sec(b, 1, front=True, bulk=(True, True), tanks=False, fill=0.02)
        # the flooded dock reads as clearly blue water (the tinted flood volume, as when it floated up)
        self.stage(b, {"front_dock", "dock", "gull", "dockflood"})
        self.armour(b, "none")
        self.lights(b, False)
        self.dock_state(b, "empty")
        self.dflood.scale = (1, 1, -(DOCK_FLOOR + 0.012))
        self.dflood.keyframe_insert("scale", frame=b)
        # the dock gate lies open just under the water; the sealed block floats out of the dock and on across
        # the open sea
        self.put(self.gate, b, self.gate_home - V((0, 0, 3.3)))
        self.put(S1, b, (-17.6, 0.0, FLOAT_Z), (0, 0, 0))
        self.glide(S1, b + 2, e, (-10.6, 0.0, FLOAT_Z), (0, R(1.2), 0))
        events.add(b, "water_rush", duration=e - b, gain=0.3)
        # Max rides the roof near the sea-side end
        off = (2.0, 1.4, HH + 0.004)
        self.at(b, tuple(self.at_loc(S1, b) + V(off)), 0)
        self.ride(self.max, S1, b, e, off)
        # the seagull flies in during the window and lands on his hat
        g0 = b + 2
        self.put(self.gull, g0, tuple(self.hat_top(g0) + V((-1.4, 0.7, 1.4))), (0, 0, R(10)))
        self.glide(self.gull, g0, land, tuple(self.hat_top(land) + V((0, 0, 0.012))), (0, 0, R(-70)))
        self.show(self.gull, b, True)
        self.show(self.gull, land, False)
        self.show(self.gull_hat, land, True)
        events.add(land, "boing", gain=0.4)
        self.max.point(b + 3, land - 4, hand="L", up_deg=50, side_deg=70)
        self.jaw_drop(land - 2, land + 10)
        self.shrug(land + 11, e)
        # a close, high 3/4 view from the sea side: Max big on the roof of the floating block, open water around
        self.frame_steps(b, e, [self.S[1]["front"], self.max], 3, angle=-40, rise=0.42, lens=30.0,
                         margin=0.06, swing=6.0)

    def a_happy_hook(self, i, h0, h1):
        self.drive_scene(h0, h1, hook=True)
