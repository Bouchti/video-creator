"""
BACTERIA-CEMENTED SANDCASTLE story set (Blender side). Spec: s_bacteria_cemented_backyard_story_spec.py.

ASSET PLAN (real object -> real shape / proportions -> the detail that sells it -> how it is built)
- The beach slice, ~8 m wide: a dry upper sand terrace (z 0.2) on the left, a flat wet-sand flat in the
  middle where the castle stands, then the beach slope down into the sea on the right. Sand colour runs
  from pale dry to dark wet across x (node material on st.terrain); the cut face at y = 0 shows sand
  layers (st.section_rock in sand colours) and a dark saturated WATER TABLE band with a bright blue top
  line that rises and falls with the tide (a 1 cm slab just in front of the face, scaled in z).
- The sea: studio.Water (see-through, bright waterline on the cut), level keyed for the tide.
- Waves: a rolling hump of water (a long cylinder along y, blue-white foam material) + white splash puffs.
- The castles (Blender primitives, rebuilt for every attempt): c1 a dry bucket tower (cylinder) that pours
  into a 34-degree cone; c2 a wet tower with a 45-degree skirt that sags into a flat mud cone + puddle;
  c3/c4/c5 the full castle: 2.2 m main tower (cylinder) with an open turret ring on top (the kids stand
  inside, the wall at their waist), crenels (cubes), two side towers with cone roofs, curtain walls, a
  dark door; wet sand (c3, c4 pink-speckled with bacteria, c5w), then pale calcite-cemented stone (c5).
- Moat: a dark wet annular trench with a sand rampart; its water ring rises first in the tide.
- Grain-scale INSET: a brass magnifier ring floating beside the castle with a dark backing; seven quartz
  grains (spheres), 12 blue capillary water bridges at the contacts, a blue pore-water disk that fills the
  gaps, pink rod bacteria on the grains and white calcite crystals (cubes) growing at every contact.
- Protractor: a pale yellow quarter-disk gauge with a red arm keyed to the slope angle (34 / 45 / 16 deg).
- Biocement bath: a big blue plastic tub around the castle (front wall cut away) holding studio.Water;
  a calendar on a stake whose pages flip over; Max's yellow rubber gloves.
- Scale card: a white board on a stake with a tiny stone dune and a blue flume strip.
- BlenderKit props (with primitive fallbacks): beach umbrella, cooler, buckets, spade, garden hose,
  garden sprayer, crab. The striped beach towel is five cloth stripes.
- Characters: Max and his two kids (engine.character), motion-captured; the kids appear in the finale.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from engine import events, props as bk, studio as st, textures as tx, toy
from engine.camera import CameraRig
from engine.character import Character
from engine.machines import Puffs, Spray
from engine.sets.s_bacteria_cemented_backyard_story_spec import ACTIONS, beat_actions
from engine.camera import facing_to
from mathutils import Euler

V = Vector
R = math.radians

# ------------------- layout (metres; cut face y = 0, camera at -y) -------------------
TERRACE_Z = 0.2
FOOT = 0.025                                      # characters' roots sit just above the surface (soles)
CX, CY = 0.8, 2.0                                 # castle centre (base on the wet flat, z = 0)
MAX_AT = V((-1.15, 0.85, TERRACE_Z + FOOT))
INSET = V((2.6, 1.0, 2.75))                      # beside the castle, never sitting on its tower like a ball
INSET_R = 0.7
GRAIN_R, GRAIN_D = 0.12, 0.25
PROT_Y = 0.45                                     # the gauge stands in FRONT of the pile (never hidden by it)
SEA_LOW, SEA_HIGH = -0.45, 0.14
WT_BOT, WT_LOW, WT_HIGH = -3.0, -1.1, -0.26
MOAT_DOWN, MOAT_UP = -0.08, 0.012
KID_TOWER = [V((CX - 0.24, CY + 0.1, 1.70 + FOOT)), V((CX + 0.24, CY + 0.1, 1.70 + FOOT))]
CRAB_SAND = V((2.5, 1.3, -0.03))
CRAB_RIM = V((CX + 0.39, CY - 0.39, 2.04))
CAL_AT = V((-0.35, 0.6, 0.0))
CARD_AT = V((2.25, 0.8, 0.0))
LBL_CASTLE = V((CX - 0.35, 0.85, 3.05))          # the beat's second label: above the castle, apart from the inset's
LBL_INSET = V((INSET.x, 0.85, INSET.z + INSET_R + 0.3))
GROUND_PT = (0.5, 0.2, -0.85)
WAVE_Y = 2.9


def _water_skin(name, hexc, alpha=0.72):
    """A see-through water surface (the waves, the moat): blended, glossy, clearly liquid, never solid plastic."""
    mat = st.water_surface(name, hexc)
    toy._set(toy._principled(mat), "Alpha", alpha)
    toy._set(toy._principled(mat), "Roughness", 0.08)
    return mat


def _ground_h(x, y):
    if x < -0.6:
        z = TERRACE_Z
    elif x < -0.1:
        t = (x + 0.6) / 0.5
        z = TERRACE_Z * (1 - t * t * (3 - 2 * t))
    elif x < 2.4:
        z = 0.0
    else:
        z = max(-2.6, -0.3 * (x - 2.4))
    w = min(1.0, max(0.0, (y - 5.0) / 4.0))
    return z + w * 0.035 * math.sin(0.9 * x + 0.4 * y) * math.sin(0.7 * y + 0.3 * x)


def _recalc(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def _noise(name, a, b, scale=20.0, rough=0.8, bump=0.0):
    a, b = _PALETTE.get(a.upper(), a), _PALETTE.get(b.upper(), b)
    return toy.noise_material(name, toy.srgb(a), toy.srgb(b), scale=scale, roughness=rough, bump=bump)


def _sock(node, ident, out=False):
    return next(s for s in (node.outputs if out else node.inputs) if s.identifier == ident)


def _sand_top():
    """Beach sand: bright golden and dry on the left, warm orange and wet toward the sea (x), grain speckle."""
    m = bpy.data.materials.new("bc_sand_top")
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    mr = N.new("ShaderNodeMapRange")
    mr.inputs[1].default_value = -1.2
    mr.inputs[2].default_value = 0.6
    L.new(sep.outputs[0], mr.inputs[0])
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 38.0
    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    mix = N.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(mr.outputs["Result"], _sock(mix, "Factor_Float"))
    _sock(mix, "A_Color").default_value = (*toy.srgb("#FFD580")[:3], 1.0)
    _sock(mix, "B_Color").default_value = (*toy.srgb("#E0954A")[:3], 1.0)
    mul = N.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 0.35
    L.new(noise.outputs["Fac"], mul.inputs[0])
    mix2 = N.new("ShaderNodeMix")
    mix2.data_type = "RGBA"
    L.new(mul.outputs[0], _sock(mix2, "Factor_Float"))
    L.new(_sock(mix, "Result_Color", True), _sock(mix2, "A_Color"))
    _sock(mix2, "B_Color").default_value = (*toy.srgb("#D7883A")[:3], 1.0)
    L.new(_sock(mix2, "Result_Color", True), bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    bump = N.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.18
    L.new(noise.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def _slab(name, x0, x1, y0, y1, mat, z0=0.0, h=1.0):
    """A box whose origin sits on its BOTTOM face (scale z to raise its top)."""
    vs = [(x, y, z) for z in (0.0, h) for y in (y0, y1) for x in (x0, x1)]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = st.mesh_obj(name, vs, fs, mats=(mat,), smooth=False)
    _recalc(ob)
    ob.location.z = z0
    return ob


def _ring(name, r_in, r_out, z0, z1, mat, loc=(0, 0, 0), n=48):
    vs, fs = [], []
    for (r, z) in ((r_out, z0), (r_out, z1), (r_in, z1), (r_in, z0)):
        for k in range(n):
            a = 2 * math.pi * k / n
            vs.append((r * math.cos(a), r * math.sin(a), z))
    for ring in range(4):
        a0, a1 = ring * n, ((ring + 1) % 4) * n
        for k in range(n):
            fs.append((a0 + k, a0 + (k + 1) % n, a1 + (k + 1) % n, a1 + k))
    ob = st.mesh_obj(name, vs, fs, mats=(mat,), smooth=True)
    _recalc(ob)
    ob.location = loc
    return ob


def _cone(name, r1, r2, depth, loc, mat, n=40):
    bpy.ops.mesh.primitive_cone_add(vertices=n, radius1=r1, radius2=r2, depth=depth, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def _torus(name, major, minor, loc, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=64,
                                     minor_segments=12, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def _kids_look(k):
    return [{"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5", "hair": "#5B3A1E",
             "scale": 0.6, "ponytail": True},
            {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B", "hair": "#2B1A10",
             "scale": 0.56}][k]


_PALETTE = {
    "#E8D2A0": "#FFD27A", "#D2B67E": "#F5B54E",      # dry castle: golden sand
    "#A3845A": "#E0913E", "#8A6D47": "#C2742C",      # wet castle: orange wet sand
    "#A26F6B": "#E8609E",                            # bacteria-coated castle: pink
    "#EEE7D6": "#FFE3A0", "#CFC4AD": "#F2B85E",      # biocemented sandstone: warm cream-gold
    "#6E583B": "#94602C", "#54432C": "#764A1F",      # mud
    "#5B5038": "#8F6A34", "#7A6A48": "#B08A48",      # muddy puddle
    "#7E7358": "#3F86C8", "#665F52": "#2C6CAE",      # sand below the water table: wet blue band
    "#7A6446": "#B0783A", "#5F4D36": "#8F5E28",      # moat bed
    "#26303D": "#173E7A", "#36414F": "#22569E",      # inset backdrop: navy
    "#ECDBB0": "#FFD27A", "#C7A86E": "#EDA640",      # sand grains
}


FLAT_AT = V((0.0, 0.6, FOOT))


DRY_AT = V((0.0, 1.85, FOOT))                     # BESIDE the tower (same depth): the raised arm reaches over it                    # close to the tower: his raised bucket reaches over it


WAVE_PROFILE = [(2.4, -0.4), (1.9, 0.5), (1.4, 1.5), (0.9, 2.4), (0.45, 2.95), (0.0, 3.2), (-0.45, 3.15),
                (-0.8, 2.9), (-0.95, 2.55), (-0.85, 2.3), (-0.6, 2.35), (-0.45, 2.55), (-0.2, 2.55), (0.0, 2.2),
                (0.05, 1.6), (-0.1, 0.9), (-0.4, 0.35), (-0.8, 0.0), (-1.1, -0.4)]


SIDE_AT = V((-0.95, 0.95, TERRACE_Z + FOOT))     # fail_pour: left of the spreading cone


HOSE_AT = V((-1.0, 1.2, TERRACE_Z + FOOT))       # fail_flood: hose in his left hand, aimed at the tower


SPRAY_AT = V((-0.95, 1.0, TERRACE_Z + FOOT))     # spray_bacteria: spray bottle in his left hand


TIDE_AT = V((-0.85, 0.75, TERRACE_Z + FOOT))     # fail_tide: on the dry terrace, above the flood line


FIN_AT = V((-0.75, 0.75, TERRACE_Z + FOOT))      # finale: flat terrace (no shin in the slope), dry when it washes


SIGN_AT = V((2.1, 1.0, 0.0))                     # the scale sign: high on two posts, right of the tower


HOOK_WAVE_SX = 0.5                               # the hook's wave squeezed front-to-back: a steep wall that fits the frame


class SBacteriaCementedBackyardStorySet:
    ACTIONS = ACTIONS
    QA_ALLOW = (r"sand_|sea|c[1-5]w?_|inset|grain|bridge|calcite|bact|pore|wave|splash|puff|moat|prot|tub_|bath"
                r"|calendar|cal_|scale_card|card_|crab|towel|umbrella|cooler|bucket|spade|hose|nozzle|sprayer"
                r"|spray|glove|wt_|label|ground_|world|mist|dump|dust")

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self.rnd = random.Random(23)
        self._pts = []
        self._inset_on = {}
        self._sea = SEA_LOW
        self._wt = WT_LOW
        self.loose_d, self.pack_d = 0.42, 0.36
        # Max's work spot right beside the castle (dry_tower .. pack, finale): the shot stays narrow, he stays big
        self.work_at = V((-0.3, 0.75, _ground_h(-0.3, 0.75) + FOOT))
        a = facing_to(tuple(self.work_at), (CX, CY, 0.0))
        self.work_face = 0.55 * (((a + 180.0) % 360.0) - 180.0)
        self._world()
        self.ground.name = "sand_ground"              # shoes resting on the sand are standing, not colliding
        self._props()
        self._castles()
        self._inset()
        self._gauges()
        self._bath()
        self._people()
        self._colour_grade()

    # ------------------- world -------------------

    def _world(self):
        top = _sand_top()
        side = st.section_rock("bc_sand_section", light="#F5C878", dark="#D99A4E")
        self.ground = st.terrain("sand_beach", -30.0, 70.0, 0.0, 100.0, _ground_h, floor=-80.0, res=0.5,
                                 top=top, side=side)
        st.world_floor(0.0, around=(-30.0, 70.0, 100.0))
        self.sea = st.Water("sea", -0.45, 70.0, 0.02, 100.0, bottom=-3.0, level=SEA_LOW)
        self.sea.key_level(1, SEA_LOW)
        # saturated sand below the water table, seen on the cut face, with a bright line on top
        wet = _noise("bc_saturated", "#7E7358", "#665F52", scale=24, rough=0.5)
        self.wt = _slab("wt_band", -6.0, 2.4, -0.016, -0.008, wet, z0=WT_BOT, h=1.0)
        self.wt_line = _slab("wt_line", -6.0, 2.4, -0.026, -0.018, st.glow_mat("wt_glow", "#46C2FF", 2.2),
                             z0=0.0, h=0.035)
        self._wt_key(1, WT_LOW)
        # the wave: a rolling hump of foamy water, hidden until it rolls in
        self.wave = toy.cylinder("wave", 0.6, 5.5, (7.5, WAVE_Y, -0.3), rotation=(R(90), 0, 0), vertices=40,
                                 mat=_noise("bc_wave", "#1E8FE6", "#DDF3FF", scale=3.5, rough=0.12))
        self.wave.keyframe_insert("location", frame=1)
        self.wave.keyframe_insert("scale", frame=1)
        toy.hide_tree(self.wave, 1, True)
        # striped beach towel on the dry terrace
        cols = ("#E0453A", "#FFD23F", "#2E6FD0", "#FFD23F", "#E0453A")
        for k, c in enumerate(cols):
            toy.box(f"towel_{k}", (0.19, 1.5, 0.006), location=(-3.55 + 0.2 * k, 2.25, TERRACE_Z + 0.009),
                    mat=tx.cloth(f"towel_cloth{k}", c), bevel=0.0)

    def _props(self):
        self.umbrella = bk.prop("beach umbrella", 2.2, fallback=self._fb_umbrella, name="umbrella")
        self.umbrella.location = (-3.3, 3.0, TERRACE_Z)
        self.cooler = bk.prop("cooler", 0.6, fallback=self._fb_cooler, name="cooler")
        self.cooler.location = (-2.5, 3.4, TERRACE_Z)
        self.cooler.rotation_euler = (0, 0, R(12))
        self.bucket = bk.prop("bucket", 0.32, fallback=self._fb_bucket, name="bucket")
        self.bucket.location = (-1.75, 1.75, TERRACE_Z)
        self.spade = bk.prop("spade", 1.0, fallback=self._fb_spade, name="spade")
        self.spade.location = (-2.75, 1.05, TERRACE_Z)
        self.hose = bk.prop("garden hose", 0.5, fallback=self._fb_hose, name="hose")
        self.hose.location = (-1.95, 1.4, TERRACE_Z)
        self.crab = bk.prop("crab", 0.3, fallback=self._fb_crab, name="crab")
        self.crab.location = CRAB_SAND
        self.crab.rotation_euler = (0, 0, R(-20))
        self.crab.keyframe_insert("location", frame=1)
        self.crab.keyframe_insert("scale", frame=1)
        # things Max carries (each its own copy, shown only in its beat)
        self.held = {"bucket": bk.prop("bucket", 0.32, fallback=self._fb_bucket, name="bucket_held"),
                     "sprayer": bk.prop("garden sprayer", 0.55, fallback=self._fb_sprayer, name="sprayer_held"),
                     "spade": bk.prop("spade", 1.0, fallback=self._fb_spade, name="spade_held")}
        noz = toy.empty("nozzle_root")
        toy.cylinder("nozzle_body", 0.035, 0.28, (0, 0, 0.14), mat=tx.paint("nozzle_paint", "#2FA84F"),
                     parent=noz, vertices=16)
        self.held["nozzle"] = noz
        for ob in self.held.values():
            toy.hide_tree(ob, 1, True)

    # fallbacks: simple recognisable builds at the origin, bottom on z = 0
    def _fb_umbrella(self):
        root = toy.empty("umbrella_fb")
        toy.cylinder("umbrella_pole", 0.025, 2.1, (0, 0, 1.05), mat=tx.metal("umb_metal", "#D8D8D8"), parent=root)
        c = _cone("umbrella_canopy", 1.0, 0.04, 0.35, (0, 0, 1.95), tx.fabric("umb_fab", "#F2C230"), n=16)
        c.parent = root
        return root

    def _fb_cooler(self):
        root = toy.empty("cooler_fb")
        toy.box("cooler_box", (0.6, 0.38, 0.34), (0, 0, 0.17), mat=tx.paint("cooler_blue", "#2D74C9"), parent=root)
        toy.box("cooler_lid", (0.62, 0.4, 0.07), (0, 0, 0.37), mat=tx.paint("cooler_white", "#F2F2EE"), parent=root)
        return root

    def _fb_bucket(self):
        root = toy.empty("bucket_fb")
        b = _cone("bucket_body", 0.11, 0.15, 0.26, (0, 0, 0.13), tx.paint("bucket_red", "#E2412F"), n=24)
        b.parent = root
        h = _torus("bucket_handle", 0.14, 0.008, (0, 0, 0.26), tx.metal("bucket_wire", "#CCCCCC"), rot=(R(90), 0, 0))
        h.parent = root
        return root

    def _fb_spade(self):
        root = toy.empty("spade_fb")
        toy.cylinder("spade_shaft", 0.018, 0.75, (0, 0, 0.55), mat=tx.wood("spade_wood", "#A87B4F", "#8A6038"),
                     parent=root, vertices=12)
        toy.box("spade_blade", (0.2, 0.02, 0.24), (0, 0, 0.12), mat=tx.metal("spade_steel", "#9AA3AA"), parent=root,
                bevel=0.004)
        return root

    def _fb_hose(self):
        root = toy.empty("hose_fb")
        mat = tx.rubber("hose_green", "#2E9A48")
        for k in range(4):
            t = _torus(f"hose_coil{k}", 0.22, 0.02, (0, 0, 0.02 + 0.04 * k), mat)
            t.parent = root
        return root

    def _fb_sprayer(self):
        root = toy.empty("sprayer_fb")
        toy.cylinder("sprayer_tank", 0.1, 0.36, (0, 0, 0.18), mat=tx.paint("sprayer_yel", "#F2C230"), parent=root)
        toy.cylinder("sprayer_pump", 0.015, 0.2, (0, 0, 0.44), mat=tx.metal("sprayer_m", "#BBBBBB"), parent=root)
        toy.cylinder("sprayer_wand", 0.01, 0.4, (0.15, 0, 0.3), rotation=(0, R(60), 0),
                     mat=tx.metal("sprayer_m2", "#444444"), parent=root)
        return root

    def _fb_crab(self):
        root = toy.empty("crab_fb")
        red = tx.paint("crab_red", "#E2502F")
        toy.sphere("crab_body", 0.1, (0, 0, 0.06), scale=(1.0, 0.7, 0.45), mat=red, parent=root)
        for s in (-1, 1):
            toy.sphere(f"crab_claw{s}", 0.045, (0.13 * s, -0.07, 0.07), mat=red, parent=root)
            toy.sphere(f"crab_eye{s}", 0.015, (0.03 * s, -0.06, 0.12), mat=tx.paint("crab_eye", "#151515"),
                       parent=root)
        return root

    # ------------------- castles -------------------

    def _castles(self):
        dry = _noise("bc_dry_castle", "#E8D2A0", "#D2B67E", scale=30, rough=0.92)
        wet = _noise("bc_wet_castle", "#A3845A", "#8A6D47", scale=30, rough=0.6)
        pink = _noise("bc_bact_castle", "#A3845A", "#A26F6B", scale=36, rough=0.6)
        stone = _noise("bc_stone_castle", "#EEE7D6", "#CFC4AD", scale=26, rough=0.72)
        mud = _noise("bc_mud", "#6E583B", "#54432C", scale=18, rough=0.28)
        dark = _noise("bc_door", "#2B2118", "#3A2D20", scale=12, rough=0.9)
        self.c = {}
        # c1: the dry bucket tower and the cone it pours into
        r = toy.empty("c1_root", (CX, CY, -0.01))
        toy.parent_keep(toy.cylinder("c1_tower", 0.45, 1.8, (CX, CY, 0.89), mat=dry, vertices=40), r)
        for k in range(6):
            a = 2 * math.pi * k / 6
            toy.parent_keep(toy.box(f"c1_merlon{k}", (0.13, 0.13, 0.14),
                                    (CX + 0.38 * math.cos(a), CY + 0.38 * math.sin(a), 1.85), mat=dry,
                                    rotation=(0, 0, a)), r)
        cr = toy.empty("c1_coneroot", (CX, CY, -0.01))
        toy.parent_keep(_cone("c1_cone", 1.26, 0.03, 0.85, (CX, CY, 0.415), dry), cr)
        self.c["c1"], self.c["c1_cone"] = r, cr
        # c2: the wet tower with its 45-degree skirt, and the mud it sags into
        r = toy.empty("c2_root", (CX, CY, -0.01))
        toy.parent_keep(toy.cylinder("c2_tower", 0.5, 1.9, (CX, CY, 0.94), mat=wet, vertices=40), r)
        toy.parent_keep(_cone("c2_skirt", 0.95, 0.5, 0.45, (CX, CY, 0.215), wet), r)
        for k in range(6):
            a = 2 * math.pi * k / 6 + 0.3
            toy.parent_keep(toy.box(f"c2_merlon{k}", (0.14, 0.14, 0.15),
                                    (CX + 0.42 * math.cos(a), CY + 0.42 * math.sin(a), 1.95), mat=wet,
                                    rotation=(0, 0, a)), r)
        mr = toy.empty("c2_mudroot", (CX, CY, -0.01))
        toy.parent_keep(_cone("c2_mud", 1.45, 0.05, 0.42, (CX, CY, 0.2), mud), mr)
        toy.parent_keep(toy.cylinder("c2_puddle", 1.55, 0.02, (CX, CY, 0.019), mat=_noise(
            "bc_mud_water", "#5B5038", "#7A6A48", scale=8, rough=0.08), vertices=48), mr)
        self.c["c2"], self.c["c2_mud"] = r, mr
        # c3..c5: the full castle
        self.c["c3"] = self._castle("c3", wet, dark)
        self.c["c4"] = self._castle("c4", pink, dark)
        self.c["c5w"] = self._castle("c5w", wet, dark)
        self.c["c5"] = self._castle("c5", stone, dark)
        for root in self.c.values():
            toy.hide_tree(root, 1, True)
            root.keyframe_insert("scale", frame=1)
        # the moat: a dark wet trench, its sand rampart and a water ring that rises first (moved, never squashed)
        self.moat = toy.empty("moat_root", (CX, CY, 0.0))
        bed = _ring("moat_bed", 1.4, 1.62, -0.03, 0.008, _noise("bc_moat_bed", "#7A6446", "#5F4D36", scale=20,
                                                                rough=0.4), loc=(CX, CY, 0.0))
        toy.parent_keep(bed, self.moat)
        ramp = _torus("moat_rampart", 1.72, 0.08, (CX, CY, 0.0), wet)
        ramp.scale = (1, 1, 0.8)
        toy.parent_keep(ramp, self.moat)
        self.moat_water = _ring("moat_water", 1.41, 1.61, 0.0, 0.06, _water_skin("bc_moat_water", "#4FB4EE", 0.6), loc=(CX, CY, MOAT_DOWN))
        toy.parent_keep(self.moat_water, self.moat)
        self.moat_water.keyframe_insert("location", frame=1)
        toy.hide_tree(self.moat, 1, True)

    def _castle(self, tag, mat, dark):
        root = toy.empty(f"{tag}_root", (CX, CY, -0.01))

        def add(ob):
            return self.attach(ob, root)

        add(toy.cylinder(f"{tag}_tower", 0.55, 1.6, (CX, CY, 0.79), mat=mat, vertices=48))
        add(_ring(f"{tag}_turret", 0.48, 0.62, 0.0, 0.47, mat, loc=(CX, CY, 1.57)))
        if tag == "c5":
            # a raised sand floor inside the turret: the kids stand on it, waist-high in the wall
            add(toy.cylinder(f"{tag}_turretfloor", 0.46, 0.104, (CX, CY, 1.648), mat=mat, vertices=40))
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            add(toy.box(f"{tag}_merlon{k}", (0.15, 0.13, 0.15), (CX + 0.55 * math.cos(a), CY + 0.55 * math.sin(a),
                                                                  2.1), mat=mat, rotation=(0, 0, a + R(90))))
        add(_cone(f"{tag}_skirt", 0.95, 0.56, 0.32, (CX, CY, 0.15), mat))
        add(toy.box(f"{tag}_door", (0.26, 0.05, 0.42), (CX, CY - 0.545, 0.52), mat=dark))
        for s in (-1, 1):
            x, y = CX + 0.95 * s, CY + 0.25
            add(toy.cylinder(f"{tag}_side{s}", 0.3, 1.1, (x, y, 0.54), mat=mat, vertices=32))
            add(_cone(f"{tag}_roof{s}", 0.36, 0.02, 0.42, (x, y, 1.29), mat, n=32))
            add(toy.box(f"{tag}_wall{s}", (0.5, 0.3, 0.75), (CX + 0.72 * s, CY + 0.15, 0.37), mat=mat))
            for j in range(2):
                add(toy.box(f"{tag}_crenel{s}{j}", (0.1, 0.3, 0.1), (CX + (0.64 + 0.17 * j) * s, CY + 0.15, 0.78),
                            mat=mat))
        return root

    # ------------------- the grain-scale inset -------------------

    def _inset(self):
        c = INSET
        brass = tx.metal("bc_brass", "#C9A13B", rough=0.25)
        self.inset_ring = _torus("inset_ring", INSET_R, 0.05, c, brass, rot=(R(90), 0, 0))
        back = toy.cylinder("inset_back", INSET_R - 0.01, 0.02, (c.x, c.y + 0.16, c.z), rotation=(R(90), 0, 0),
                            mat=_noise("bc_inset_back", "#26303D", "#36414F", scale=10, rough=0.7), vertices=64)
        self.pore = toy.cylinder("inset_pore", INSET_R - 0.03, 0.02, (c.x, c.y + 0.08, c.z), rotation=(R(90), 0, 0),
                                 mat=_noise("bc_pore", "#2A86D6", "#5DB8F2", scale=7, rough=0.05), vertices=64)
        gmat = _noise("bc_grain", "#ECDBB0", "#C7A86E", scale=9, rough=0.45, bump=0.1)
        self.grain_angles = [None] + [math.pi / 2 + k * math.pi / 3 for k in range(6)]
        self.grains = []
        for k, a in enumerate(self.grain_angles):
            g = toy.sphere(f"grain{k}", GRAIN_R, self.grain_pos(a, GRAIN_D), mat=gmat, subdiv=2)
            g.scale = (1.0 + 0.05 * (k % 3), 1.0, 1.0 - 0.05 * (k % 2))
            g.keyframe_insert("location", frame=1)
            self.grains.append(g)
        packed = [V(self.grain_pos(a, self.pack_d)) for a in self.grain_angles]
        pairs = [(0, k) for k in range(1, 7)] + [(k, k % 6 + 1) for k in range(1, 7)]
        bmat = _noise("bc_bridge", "#3FA9F5", "#9ADAFF", scale=5, rough=0.04)
        cmat = toy.material("bc_calcite", toy.srgb("#FBFAF4"), roughness=0.18, coat=0.6)
        self.bridges, self.calcite = [], []
        for n, (i, j) in enumerate(pairs):
            a, b = packed[i], packed[j]
            m = (a + b) / 2
            d = b - a
            rot_y = math.atan2(d.x, d.z)
            self.bridges.append(toy.cylinder(f"bridge{n}", 0.085, 0.17, tuple(m + V((0, -0.05, 0))),
                                             rotation=(0, rot_y, 0), mat=bmat, vertices=16))
            self.calcite.append(toy.box(f"calcite{n}", (0.12, 0.12, 0.12), tuple(m + V((0, -0.09, 0))), mat=cmat,
                                        rotation=(R(35), rot_y + R(45), 0), bevel=0.006))
            side = V((math.cos(rot_y), 0, -math.sin(rot_y))) * 0.06
            self.calcite.append(toy.box(f"calcite{n}b", (0.075, 0.075, 0.075), tuple(m + side + V((0, -0.12, 0.03))),
                                        mat=cmat, rotation=(R(20), rot_y + R(30), R(15)), bevel=0.004))
        pk = toy.material("bc_bact", toy.srgb("#D0459B"), roughness=0.4)
        self.bact = []
        for k, p0 in enumerate(packed):
            for j in range(2):
                a = 0.6 + 2.3 * j + 0.9 * k
                p = p0 + V((0.1 * math.cos(a), -GRAIN_R * 0.82, 0.1 * math.sin(a)))
                self.bact.append(toy.capsule(f"bact{k}_{j}", 0.028, 0.1, location=tuple(p), rotation=(0, a, 0),
                                             mat=pk))
        self.groups = {"bridges": self.bridges, "pore": [self.pore], "calcite": self.calcite, "bact": self.bact}
        for name, obs in self.groups.items():
            self._inset_on[name] = False
            for ob in obs:
                ob.scale = (0.001, 0.001, 0.001)
                ob.keyframe_insert("scale", frame=1)
        self.inset_objs = [self.inset_ring, back, self.pore] + self.grains + self.bridges + self.calcite + self.bact

    def grain_pos(self, a, d, drop=0.0):
        if a is None:
            return (INSET.x, INSET.y, INSET.z + drop)
        return (INSET.x + d * math.cos(a), INSET.y, INSET.z + d * math.sin(a) + drop)

    def inset_set(self, f, ramp=10, **groups):
        for name, on in groups.items():
            if self._inset_on[name] == on:
                continue
            self._inset_on[name] = on
            for k, ob in enumerate(self.groups[name]):
                lag = (k % 4) * 2 if name in ("calcite", "bact") else 0
                toy.key_hold(ob, "scale", f + lag)
                ob.scale = (1, 1, 1) if on else (0.001, 0.001, 0.001)
                ob.keyframe_insert("scale", frame=f + ramp + lag)

    def grains_to(self, f0, f1, d, drop=0.0):
        for k, (g, a) in enumerate(zip(self.grains, self.grain_angles)):
            toy.key_hold(g, "location", f0)
            dd = drop * (0.4 + 0.6 * (k % 2)) if a is not None else drop * 0.3
            g.location = self.grain_pos(a, d, dd)
            g.keyframe_insert("location", frame=f1)

    # ------------------- gauges: protractor, calendar, scale card -------------------

    def _gauges(self):
        p0 = V((2.0, PROT_Y, 0.008))
        self.prot = toy.empty("prot_root", tuple(p0))
        # an open ARC (not a solid disk): the pile it measures stays visible through it
        r0, r1, n = 0.5, 0.62, 24
        vs, fs = [], []
        for k in range(n + 1):
            a = R(90) * k / n
            vs += [(-r0 * math.cos(a), 0, r0 * math.sin(a)), (-r1 * math.cos(a), 0, r1 * math.sin(a))]
        fs = [(2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1) for k in range(n)]
        disk = st.mesh_obj("prot_disk", vs, fs, mats=(tx.paint("bc_prot", "#FFE07A", coat=0.3),), smooth=False)
        disk.location = p0
        self.attach(disk, self.prot)
        tick = tx.paint("bc_prot_tick", "#3A2A10")
        for k in range(7):
            a = R(15 * k)
            c = p0 + V((-0.465 * math.cos(a), -0.012, 0.465 * math.sin(a)))
            self.attach(toy.box(f"prot_tick{k}", (0.07, 0.008, 0.014), tuple(c), mat=tick, rotation=(0, a, 0),
                                bevel=0.0), self.prot)
        red = tx.paint("bc_prot_arm", "#E5392B")
        self.attach(toy.box("prot_base", (0.8, 0.02, 0.035), tuple(p0 + V((-0.4, -0.03, 0.018))), mat=red,
                            bevel=0.004), self.prot)
        pv = p0 + V((0, 0, 0.018))
        self.prot_pivot = toy.empty("prot_pivot", tuple(pv))
        self.attach(self.prot_pivot, self.prot)
        self.attach(toy.box("prot_arm", (0.85, 0.02, 0.04), tuple(pv + V((-0.425, -0.055, 0.0))), mat=red,
                            bevel=0.004), self.prot_pivot, at=pv)
        self.prot.keyframe_insert("location", frame=1)
        self.prot_pivot.keyframe_insert("rotation_euler", frame=1)
        toy.hide_tree(self.prot, 1, True)
        # the calendar on a stake, left of the tub: three day pages (1, 2, 3 red dots) flip up and over,
        # revealing a green tick
        wood = tx.wood("bc_stake", "#9C7448", "#7D5A35")
        white = tx.paint("bc_paper", "#F7F5EF", coat=0.1)
        reddot = tx.paint("bc_cal_ring", "#D93A2F")
        green = tx.paint("bc_cal_tick", "#2FA84F")
        A = CAL_AT
        self.calendar = toy.empty("calendar_root", tuple(A))
        self.attach(toy.cylinder("calendar_post", 0.03, 1.85, (A.x, A.y + 0.05, 0.85), mat=wood, vertices=12),
                    self.calendar)
        self.attach(toy.box("calendar_board", (0.66, 0.03, 0.6), (A.x, A.y, 2.0), mat=white), self.calendar)
        self.attach(toy.box("calendar_bar", (0.68, 0.05, 0.1), (A.x, A.y - 0.005, 2.35),
                            mat=tx.paint("bc_cal_red", "#D93A2F")), self.calendar)
        self.pages = []
        for k in range(4):
            y = A.y - 0.05 + 0.01 * k                 # page 0 (day 1) in front
            hz = 2.27
            hinge = toy.empty(f"cal_hinge{k}", (A.x, y, hz))
            hw = V((A.x, y, hz))
            self.attach(toy.box(f"cal_page{k}", (0.58, 0.005, 0.5), (A.x, y, 2.0), mat=white, bevel=0.0), hinge, at=hw)
            if k < 3:
                for d in range(k + 1):
                    x = A.x + 0.16 * (d - k / 2)
                    self.attach(toy.box(f"cal_mark{k}{d}", (0.11, 0.004, 0.11), (x, y - 0.005, 1.98), mat=reddot,
                                        bevel=0.0), hinge, at=hw)
            else:
                self.attach(toy.box("cal_tick_a", (0.1, 0.004, 0.035), (A.x - 0.08, y - 0.005, 1.96), mat=green,
                                    rotation=(0, R(45), 0), bevel=0.0), hinge, at=hw)
                self.attach(toy.box("cal_tick_b", (0.24, 0.004, 0.035), (A.x + 0.04, y - 0.005, 2.01), mat=green,
                                    rotation=(0, R(-50), 0), bevel=0.0), hinge, at=hw)
            self.attach(hinge, self.calendar)
            hinge.keyframe_insert("rotation_euler", frame=1)
            self.pages.append(hinge)
        toy.hide_tree(self.calendar, 1, True)
        # the scale card: a board with a tiny stone dune in a blue flume strip (low, beside the castle)
        C = CARD_AT
        self.card = toy.empty("scale_card", tuple(C))
        self.attach(toy.cylinder("card_post", 0.03, 1.2, (C.x, C.y + 0.05, 0.5), mat=wood, vertices=12), self.card)
        self.attach(toy.box("card_board", (0.9, 0.04, 0.55), (C.x, C.y, 1.3),
                            mat=tx.paint("bc_card", "#F4F1E8", coat=0.2)), self.card)
        self.attach(toy.box("card_flume", (0.78, 0.02, 0.16), (C.x, C.y - 0.03, 1.16),
                            mat=tx.paint("bc_card_flume", "#3C8FD8"), bevel=0.003), self.card)
        self.attach(toy.sphere("card_dune", 0.2, (C.x - 0.1, C.y - 0.04, 1.24), scale=(1.3, 0.12, 0.45),
                               mat=_noise("bc_card_dune", "#EEE7D6", "#CFC4AD", scale=40)), self.card)
        toy.hide_tree(self.card, 1, True)

    # ------------------- the biocement bath -------------------

    def _bath(self):
        blue = tx.paint("bc_tub", "#2F7DD1", rough=0.4)
        self.tub = toy.empty("tub_root", (CX, CY, 0.0))
        for name, size, loc in (("tub_back", (2.84, 0.08, 2.42), (0.84, 2.9, 1.16)),
                                ("tub_left", (0.08, 1.77, 2.4), (-0.535, 1.985, 1.15)),
                                ("tub_right", (0.08, 1.77, 2.4), (2.215, 1.985, 1.15)),
                                ("tub_lip", (2.86, 0.12, 0.06), (0.84, 2.9, 2.4))):
            self.attach(toy.box(name, size, loc, mat=blue, bevel=0.015), self.tub)
        toy.hide_tree(self.tub, 1, True)
        # a tinted solution (more body glow, never more density) so the soak reads as liquid, not glass
        self.bath = st.Water("bath", -0.48, 2.16, 1.1, 2.84, bottom=0.012, level=0.06, color="#2FC4DA")
        self.bath.hide(1, True)
        toy.hide_tree(self.bath.line, 1, True)

    # ------------------- people -------------------

    def _people(self):
        self.max = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
        self.max.place(1, MAX_AT, 0)
        self.max.key("hips", 1, loc=(0, 0, 0.56))
        self.max.auto_blink(1, self.total + 400, seed=11)
        self.max.act("idle", 1, self.total + 400)
        self.kids = []
        for k in range(2):
            kid = Character(f"Kid{k + 1}", _kids_look(k))
            kid.place(1, KID_TOWER[k], 0)                  # they only come on stage in the tower (finale, hook)
            kid.key("hips", 1, loc=(0, 0, 0.56))
            kid.auto_blink(1, self.total + 400, seed=k + 3)
            kid.act("idle", 1, self.total + 400)
            toy.hide_tree(kid.root, 1, True)
            self.kids.append(kid)
        yellow = toy.material("bc_glove", toy.srgb("#F2C628"), roughness=0.5)
        self.gloves = []
        for h in ("L", "R"):
            g = toy.sphere(f"glove_{h}", 0.075, (0, 0, 0), scale=(1, 1, 1.3), mat=yellow)
            g.parent = self.max.j[f"hand{h}"]
            g.location = (0, 0, 0)
            toy.hide_tree(g, 1, True)
            self.gloves.append(g)

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

    def show(self, obj, f, visible=True):
        toy.hide_tree(obj, f, not visible)

    def kscale(self, ob, f, s):
        ob.scale = s
        ob.keyframe_insert("scale", frame=f)

    def grow(self, ob, f0, f1, s0, s1):
        self.kscale(ob, f0, s0)
        self.kscale(ob, f1, s1)

    def _wt_key(self, f, level):
        self.wt.scale = (1, 1, level - WT_BOT)
        self.wt.keyframe_insert("scale", frame=f)
        self.wt_line.location = (0, 0, level - 0.018)
        self.wt_line.keyframe_insert("location", frame=f)

    def wt_to(self, f0, f1, level):
        self._wt_key(f0, self._wt)
        self._wt_key(f1, level)
        self._wt = level

    def sea_to(self, f0, f1, level):
        self.sea.key_level(f0, self._sea)
        self.sea.key_level(f1, level, hold=False)
        self._sea = level

    def moat_to(self, f0, f1, z):
        w = self.moat_water
        toy.key_hold(w, "location", f0)
        w.location = (CX, CY, z)
        w.keyframe_insert("location", frame=f1)

    def label(self, text, loc, f0, f1, size=0.26):
        root = st.label(text, tuple(loc), f0, f1, size=size, tilt=-3)
        for f in (f0, f0 + 5, f0 + 8, f1 - 5, f1):
            root.scale = (1, 1, 1)
            root.keyframe_insert("scale", frame=f)
        w = 0.62 * size * len(text) / 2 + 0.08
        self._pts += [(loc[0] - w, loc[1], loc[2] + size * 0.7), (loc[0] + w, loc[1], loc[2] - size * 0.7)]
        return root

    def crab_to(self, f0, f1, loc, jump=False):
        """Crab moves to loc between f0 and f1 (jump=True: holds, then pops there at f1)."""
        toy.key_hold(self.crab, "location", f1 - 1 if jump else f0)
        self.crab.location = loc
        self.crab.keyframe_insert("location", frame=f1)

    def crab_flat(self, f, back=14):
        toy.key_hold(self.crab, "scale", f - 3)
        self.kscale(self.crab, f, (1.45, 1.45, 0.25))
        self.kscale(self.crab, f + back, (1.45, 1.45, 0.25))
        self.kscale(self.crab, f + back + 5, (1, 1, 1))
        events.add(f, "boing", gain=0.35)

    def prot_to(self, f0, f1, x, angle):
        toy.key_hold(self.prot, "location", f0)
        toy.key_hold(self.prot_pivot, "rotation_euler", f0)
        self.prot.location = (x, PROT_Y, 0.008)
        self.prot.keyframe_insert("location", frame=f1)
        self.prot_pivot.rotation_euler = (0, R(angle), 0)
        self.prot_pivot.keyframe_insert("rotation_euler", frame=f1)

    @staticmethod
    def prot_x(foot_x):
        return 0.45 + (foot_x - 0.45) * 0.82          # the gauge stands in front: perspective makes it bigger

    def hold(self, key, f0, f1, hand="L"):
        ob = self.held[key]
        if ob.parent is None:
            self.max.hold(ob, hand)
            ob.location = (0.0, 0.0, -0.05)
        self.show(ob, f0)
        self.show(ob, f1 + 1, False)

    def hand_pt(self, spot=None):
        s = MAX_AT if spot is None else spot
        return (s.x + 0.45, s.y - 0.12, s.z + 1.05)

    def at(self, f, spot=None, face=0.0):
        self.max.cut_place(f, MAX_AT if spot is None else spot, face)

    def close(self, f0, f1, frac=0.42, offset=(0.3, 0, 0), swing=10.0, angle=-90.0):
        st.close_on(self.rig, f0, f1, self.max, frac=frac, angle=angle, swing=swing, rise=0.22, lens=32,
                    look=0.62, offset=offset, cut=True, fstop=5.6, height=1.9)
        # the setup close-up frames Max tight, and the grain inset high above him was cut by the top edge of
        # every opening shot: it now appears on the cut to the wide shot (beats that hide it keep it hidden)
        if self._inset_visible(f1):
            self.inset_hide(f0, True)
            self.inset_hide(f1, False)

    def _inset_visible(self, f):
        for fc in toy.fcurves(self.inset_ring):
            if fc.data_path == "hide_render":
                return fc.evaluate(f) < 0.5
        return not self.inset_ring.hide_render

    def explain(self, f0, f1, things, ground=True):
        pts = list(things) + self._pts + [self.max] + ([GROUND_PT] if ground else [])
        st.frame_all(self.rig, f0, f1, pts, cut=True, margin=0.07, lens=28, rise=0.16, swing=7.0)

    @staticmethod
    def castle_pts(r=1.3, top=2.25):
        return [(CX - r, CY - 0.4, 0.0), (CX + r, CY - 0.4, 0.0), (CX, CY - 0.4, top)]

    def melt(self, root, f0, f1, sz=0.28, sxy=1.2):
        self.kscale(root, f0, (1, 1, 1))
        self.kscale(root, f1, (sxy, sxy, sz))

    def splash(self, tag, f, at=(CX + 0.6, 1.3, 0.45)):
        Puffs(f"splash_{tag}", "#F2FAFF", count=14, size=0.28, seed=len(tag)).emit(
            range(f, f + 10), lambda _f: at, rise=1.1, life=22, drift=0.5)
        events.add(f, "splash", gain=0.8)

    def wave_run(self, f0, f_hit, f_end, z0=-0.3, x0=7.5):
        w = self.wave
        self.show(w, f0)
        for f, x, z, s in ((f0, x0, z0, (1, 1, 0.75)), (f_hit, CX + 0.95, 0.0, (1, 1, 1.35)),
                           (f_end, CX - 0.15, -0.1, (0.6, 1, 0.22))):
            w.location = (x, WAVE_Y, z)
            w.keyframe_insert("location", frame=f)
            self.kscale(w, f, s)
        self.show(w, f_end + 1, False)
        events.add(f0, "water_rush", gain=0.5)

    def shrug(self, f0, f1):
        m = self.max
        for f, a in ((f0, 0), (f0 + 5, 62), (f1 - 4, 66), (f1, 0)):
            m.key("shoulderL", f, rot_deg=(-15 if a else 0, -a, 0))
            m.key("shoulderR", f, rot_deg=(-15 if a else 0, a, 0))
        m.key("head", f0 + 5, rot_deg=(-4, 0, 14))
        m.key("head", f1, rot_deg=(0, 0, 0))
        m.brows(f0 + 5, 0.9)
        m.brows(f1, 0.0)
        events.add(f0 + 5, "boing", gain=0.3)

    def arms_v(self, f0, f1):
        m = self.max
        for f, a in ((f0, 0), (f0 + 5, 150), (f1 - 4, 158), (f1, 0)):
            m.key("shoulderL", f, rot_deg=(0, -a, 0))
            m.key("shoulderR", f, rot_deg=(0, a, 0))
        m.smile(f0 + 5, big=True)

    def gasp(self, f0, f1):
        m = self.max
        m.key("mouth", f0, scale=(0.7, 0.6, 1.0))
        m.key("mouth", f0 + 4, scale=(1.2, 0.6, 2.6))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f0 + 4, 1.0)
        m.brows(f1, 0.0)

    # ------------------- the ladder -------------------

    def a_dry_tower(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        m = self.max
        self.at(b, DRY_AT, 0.0)                        # faces the camera; his LEFT arm tips the bucket over the tower
        self.steady(m, b + 6, e - 6)                   # the body under the bucket is hand-keyed: the stream meets it
        self.hold("bucket", b, e)
        self.held["bucket"].scale = (1.6, 1.6, 1.6)    # a big beach bucket, readable in his hand
        self.inset_hide(b, True)                       # this beat is about the bucket and the tower only
        self.inset_hide(e + 1, False)
        tw = self.c["c1"]
        self.show(tw, b)
        for k in range(6):                             # a bolder crenellated top
            bpy.data.objects[f"c1_merlon{k}"].scale = (1.35, 1.35, 1.7)
        # three dumps; the 1/2 and 7/8 moments both fall mid-dump (arm up, bucket tipped, sand streaming)
        dumps = [(fr(0.05), fr(0.3)), (fr(0.37), fr(0.62)), (fr(0.68), fr(0.96))]
        heights = [0.3, 0.55, 0.8, 1.0]
        self.kscale(tw, b, (1, 1, heights[0]))
        sand = toy.material("bc_dry_stream", toy.srgb("#FFE6A8"), roughness=0.9)
        m.key("shoulderL", b, rot_deg=(0, 0, 0))
        # the arm keys first (dense, below), so every stream starts at the hand as it really is
        prev = None
        for k, (d0, d1) in enumerate(dumps):
            if prev is not None:
                m.key("shoulderL", (prev + d0) // 2, rot_deg=(0, -95, 0))     # a quick dip to refill
            m.key("shoulderL", d0, rot_deg=(0, -125, 0))
            m.key("shoulderL", d1, rot_deg=(0, -128, 0))
            prev = d1
        m.key("shoulderL", e, rot_deg=(0, -122, 0))
        sh = m.j["shoulderL"]
        for f in range(b + 8, e, 8):                   # no gap the idle clip could pull the arm down in
            toy.key_hold(sh, "rotation_euler", f)
        tops = {}
        for k, (d0, d1) in enumerate(dumps):
            self.kscale(tw, d0, (1, 1, heights[k]))
            self.kscale(tw, d1, (1, 1, heights[k + 1]))
            src = self.hand_world((d0 + d1) // 2, "L", (DRY_AT.x + 0.62, DRY_AT.y - 0.05, 1.85))
            top = -0.01 + 1.8 * (heights[k] + heights[k + 1]) / 2 + 0.05
            Spray(f"dump_stream{k}", sand, count=54, radius=0.058, seed=30 + k).run(
                d0 + 1, d1, (src[0], src[1], src[2] - 0.15), (CX, CY, top), spread=0.18, arc=0.3, period=10)
            events.add(d0, "pour", duration=d1 - d0, gain=0.45)
            tops[d1] = -0.01 + 1.8 * heights[k + 1]
        Puffs("dump_dust", "#F4E2B4", count=10, size=0.16, seed=5).emit(
            [d1 for _, d1 in dumps], lambda f: (CX, CY - 0.3, tops.get(f, 1.8)), rise=0.4, life=16, drift=0.3)
        self.crab_to(fr(0.8), fr(0.84), (CX, CY, 1.8), jump=True)
        self.label("DRY SAND", (CX + 0.1, 1.0, 2.8), fr(0.15), e, size=0.34)
        m.look_at(b + 4, (CX, CY, 1.6), hold=int(L * 0.85))
        m.smile(fr(0.4), big=True)
        self.close(b, fr(0.22), offset=(0.45, 0, 0.2))
        self.frame_on(fr(0.22), e, [bpy.data.objects["c1_tower"]] + self.castle_pts(0.6, 2.0))

    def a_fail_pour(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        self.at(b, SIDE_AT, self.face_castle(SIDE_AT))   # beside the cone, not in front of it
        c0, c1 = fr(0.4), fr(0.82)
        tw, cone = self.c["c1"], self.c["c1_cone"]
        # the tower sinks straight down while the cone spreads evenly around it (uniform scale: always 34 deg)
        self.kscale(tw, c0, (1, 1, 1.0))
        self.kscale(tw, c1, (0.9, 0.9, 0.04))
        self.show(tw, c1 + 1, False)
        self.show(cone, c0)
        self.grow(cone, c0, c1, (0.3, 0.3, 0.3), (1, 1, 1))
        events.add(c0, "pour", duration=c1 - c0, gain=0.6)
        Puffs("pour_dust", "#E9D7A8", count=12, size=0.22, seed=6).emit(
            range(c0, c1, 4), lambda f: (CX, CY - 0.9, 0.35), rise=0.6, life=18, drift=0.4)
        toy.key_hold(self.crab, "location", c0)
        self.crab.location = (CX, CY, 0.84)
        self.crab.keyframe_insert("location", frame=c1)
        self.crab_flat(c1 + 1)
        # why: the grains drift apart (nothing pulls them together); the gauge rises to 34 degrees
        self.grains_to(c0, fr(0.76), self.loose_d, drop=-0.03)
        self.show(self.prot, b)
        px = self.prot_x(CX + 1.26)
        self.prot_to(b, b + 1, px, 0.0)
        self.prot_to(fr(0.44), c1, px, 34.0)
        self.label("34°", (px - 0.15, PROT_Y, 1.75), fr(0.42), e, size=0.34)   # right above the gauge
        self.label("NO GLUE", LBL_INSET, fr(0.4), e, size=0.32)
        self.max.act("talk", b + 2, c0)
        self.max.look_at(c0 + 2, (CX, CY, 1.4), hold=int(L * 0.4))
        self.shrug(fr(0.84), e)
        self.close(b, fr(0.3))
        self.frame_on(fr(0.3), e, [self.inset_ring, bpy.data.objects["c1_cone"]] + self.prot_pts(px)
                      + self.castle_pts(1.26, 2.1), margin=0.12)

    def a_mist(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        w = FLAT_AT
        self.at(b, w, self.face_castle(w))
        self.hold("sprayer", b, e)
        self.max.act("water", b + 2, fr(0.7))
        Spray("mist_drops", toy.material("bc_mist", toy.srgb("#A8DCFF"), roughness=0.1), count=44,
              radius=0.04, seed=7).run(b + 6, fr(0.66), self.hand_pt(w), (CX - 0.25, CY - 0.55, 1.0), spread=0.6,
                                       arc=0.25, period=12)
        # the mist cloud hangs against the castle, lower than Max's hat brim and away from him
        Puffs("mist_cloud", "#E6F6FF", count=16, size=0.3, seed=17).emit(
            range(fr(0.1), fr(0.66), 3), lambda f: (CX - 0.1, CY - 0.45, 0.4 + 0.8 * ((f * 7) % 10) / 10),
            rise=0.2, life=20, drift=0.15)
        events.add(b + 6, "pour", duration=fr(0.66) - b - 6, gain=0.25)
        # misted sand goes from the pale dry pile into a dark wet tower that rises through the middle
        cone, tw = self.c["c1_cone"], self.c["c2"]
        self.grow(cone, fr(0.25), fr(0.6), (1, 1, 1), (0.75, 0.75, 0.75))
        self.show(cone, fr(0.6) + 1, False)
        self.show(tw, fr(0.25))
        for f, s in ((fr(0.25), 0.2), (fr(0.35), 0.4), (fr(0.45), 0.6), (fr(0.55), 0.8), (fr(0.68), 1.0)):
            self.kscale(tw, f, (1, 1, s))
        toy.key_hold(self.crab, "location", fr(0.25) - 1)
        toy.key_hold(self.crab, "scale", fr(0.25) - 1)
        self.crab.location = (CX + 1.2, CY - 0.9, 0.0)
        self.crab.keyframe_insert("location", frame=fr(0.25))
        self.kscale(self.crab, fr(0.25), (1, 1, 1))
        self.crab_to(fr(0.72), fr(0.8), (CX, CY, 1.89), jump=True)
        # why: water bridges grow between the grains and pull them together; the skirt holds 45 degrees
        self.grains_to(fr(0.3), fr(0.5), GRAIN_D)
        self.inset_set(fr(0.42), ramp=max(12, int(L * 0.2)), bridges=True)
        px = self.prot_x(CX + 0.95)
        self.prot_to(fr(0.25) - 1, fr(0.25), px, 0.0)
        self.prot_to(fr(0.4), fr(0.68), px, 45.0)
        self.label("1% WATER", LBL_INSET, fr(0.34), e, size=0.3)
        self.label("45°", (px + 0.12, 0.4, 2.1), fr(0.42), e, size=0.3)         # above the caption band
        self.max.look_at(fr(0.2), (CX, CY, 1.2), hold=30)
        self.max.act("yes", fr(0.72), e)
        self.arms_v(fr(0.78), e)
        self.close(b, fr(0.28))
        self.explain(fr(0.28), e, [self.inset_ring] + self.prot_pts(px) + self.castle_pts(0.95, 2.1), ground=False)

    def a_fail_flood(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        spot = V((-0.55, 0.5, _ground_h(-0.55, 0.5) + FOOT))              # close to the tower: one tight shot
        self.at(b, spot, 0.0)
        heap = self._mud_heap()
        # Max aims a hose gun at the tower; a solid jet runs from its tip onto the tower through the whole slump
        s_on, s_off = fr(0.12), fr(0.92)
        self.steady(self.max, b + 6, e - 6)
        self.arm_hold(b + 6, s_on, s_off, e, up=-76.0)
        gun, tip_local = self._hose_gun()
        aim = (CX - 0.44, CY - 0.2, 0.6)                                    # the tower's face toward Max
        p, rot = self.grip(gun, fr(0.5), aim)
        tip = p + rot @ tip_local
        hl = self._hose_line(p)
        jet = self._jet(tip, aim)
        self.show(gun, b)                                                  # the gun stays in his hand all beat
        self.show(gun, e + 1, False)
        self.show(hl, s_on)
        self.show(hl, s_off + 1, False)
        self.show(jet, s_on + 2)
        self.show(jet, s_off + 1, False)
        Spray("hose_water", toy.material("bc_hose_water", toy.srgb("#3E9EE8"), roughness=0.05), count=70,
              radius=0.075, seed=8).run(s_on + 2, s_off, tuple(tip), aim, spread=0.3, arc=0.2, period=10)
        Puffs("hose_splash", "#F2FAFF", count=18, size=0.22, seed=17).emit(
            range(s_on + 4, s_off, 3), lambda _f: aim, rise=0.5, life=14, drift=0.4)
        events.add(s_on + 2, "water_rush", duration=s_off - s_on - 2, gain=0.5)
        tw, mud = self.c["c2"], self.c["c2_mud"]
        s0, s1 = fr(0.42), fr(0.84)
        self.kscale(tw, s0, (1, 1, 1))
        self.kscale(tw, s1, (1.3, 1.3, 0.2))
        self.show(tw, s1 + 1, False)
        self.show(mud, fr(0.3))
        self.grow(mud, fr(0.3), s1, (0.5, 0.5, 0.2), (1, 1, 1.4))
        toy.key_hold(self.crab, "location", s0)
        self.crab.location = (CX, CY, 0.64)
        self.crab.keyframe_insert("location", frame=s1)
        self.crab_flat(s1)
        # why: the pore water RISES through the grains, the bridges swell and merge into it, the grains float apart
        if self._inset_on["pore"]:
            self.inset_set(b, ramp=6, pore=False)
        fill, line, keys, levels, r = self._inset_fill()
        F = [fr(0.3), fr(0.38), fr(0.46), fr(0.54), fr(0.62)]
        for k, kb in enumerate(keys):
            seq = [(F[k], 0.0), (F[k + 1], 1.0)] + ([(F[k + 2], 0.0)] if k + 2 < len(F) else [])
            for f, v in seq:
                kb.value = v
                kb.keyframe_insert("value", frame=f)
        for f, lv in zip(F, levels):
            w = math.sqrt(max(0.0, r * r - lv * lv))
            line.location = (INSET.x, INSET.y - 0.14, INSET.z + min(lv, r - 0.02))
            line.keyframe_insert("location", frame=f)
            self.kscale(line, f, (max(0.001, w), 1, 1))
        for ob in (fill, line):
            self.show(ob, F[0])
            self.show(ob, e + 1, False)
        if self._inset_on["bridges"]:
            for k, br in enumerate(self.bridges):                          # swell, then gone by the middle
                toy.key_hold(br, "scale", fr(0.32))
                self.kscale(br, fr(0.4), (1.8, 1.8, 1.2))
                self.kscale(br, fr(0.5) + (k % 4), (0.001, 0.001, 0.001))
            self._inset_on["bridges"] = False
        self.grains_to(fr(0.5), fr(0.8), self.loose_d + 0.05, drop=0.04)
        # the gauge steps forward, BIG (in front of the heap), and drops to 16 degrees as the tower slumps
        pxm = self.prot_x(CX + 1.45)
        self.prot_move(fr(0.25) - 1, fr(0.25), self.prot_x(CX + 0.95), 45.0, 0.25)
        self.kscale(self.prot, fr(0.25) - 1, (1, 1, 1))
        self.kscale(self.prot, fr(0.25), (1.6, 1.6, 1.6))
        self.kscale(self.prot, e, (1.6, 1.6, 1.6))
        self.kscale(self.prot, e + 1, (1, 1, 1))
        self.prot_move(s0, s1, pxm, 16.0, 0.25)
        self.label("PORES FULL", LBL_INSET, fr(0.36), e, size=0.32)
        self.label("15-30°", (pxm - 0.2, 0.25, 1.35), fr(0.46), e, size=0.44)   # right above the big gauge
        self.max.look_at(s0, (CX, CY, 0.9), hold=int(L * 0.45))
        self.gasp(fr(0.58), fr(0.74))
        # 1) close on Max raising the hose gun and the jet leaving it; 2) Max, jet, tower, inset and gauge together
        self.close(b, fr(0.28), frac=0.46, offset=(0.55, 0, 0.1))
        self.frame_on(fr(0.28), e, [self.inset_ring, heap, gun, (pxm - 1.05, 0.25, 0.0), (pxm + 0.1, 0.25, 1.05)],
                      margin=0.08)

    def a_pack(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        w = self.work_at
        self.at(b, w, self.work_face)
        self.show(self.c["c2_mud"], b, False)
        self.show(self.prot, b, False)
        # Max pounds the sand with the spade through the whole build; the castle climbs with every thump
        self.hold("spade", b, fr(0.88), hand="R")
        self.max.hammer(fr(0.1), fr(0.86), hand="R")
        self.max.look_at(fr(0.12), (CX - 0.4, CY - 0.6, 0.4), hold=int(L * 0.6))
        c3 = self.c["c3"]
        self.show(c3, b)
        self.kscale(c3, b, (1, 1, 0.12))
        steps = [0.14, 0.23, 0.32, 0.41, 0.5, 0.59, 0.68, 0.78]
        thumps = []
        for k, t in enumerate(steps):
            s = 0.12 + 0.88 * (k + 1) / len(steps)
            self.kscale(c3, fr(t), (1, 1, s))
            if k + 1 < len(steps):
                self.kscale(c3, fr(steps[k + 1]) - 3, (1, 1, s))
            events.add(fr(t), "stone_thud", gain=0.45)
            thumps.append(fr(t))
        Puffs("thump_dust", "#E9C48A", count=14, size=0.22, seed=21).emit(
            thumps, lambda f: (CX - 0.55, CY - 0.8, 0.2), rise=0.5, life=14, drift=0.3)
        toy.key_hold(self.crab, "location", b - 1)
        self.crab.location = CRAB_SAND
        self.crab.keyframe_insert("location", frame=b)
        self.crab_to(fr(0.9), fr(0.96), CRAB_RIM, jump=True)
        # why: back to 1% water; loose grains are squeezed together and bridges form at every contact
        self.inset_set(b, ramp=8, pore=False)
        self.grains_to(b, b + 2, self.loose_d - 0.02)
        self.grains_to(fr(0.3), fr(0.78), self.pack_d)
        self.inset_set(fr(0.44), ramp=max(12, int(L * 0.3)), bridges=True)
        self.label("1% + PACKED", LBL_INSET, fr(0.28), e, size=0.32)
        self.label("70 THUMPS", LBL_CASTLE, fr(0.2), e, size=0.32)
        self.max.act("yes", fr(0.88), e)
        self.close(b, fr(0.26))
        self.explain(fr(0.26), e, [self.inset_ring, bpy.data.objects["c3_tower"]] + self.castle_pts(1.0, 2.25),
                     ground=False)

    def a_fail_tide(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        self.at(b, TIDE_AT, 0.0)
        self.show(self.moat, b)
        self.max.act("talk", b + 2, fr(0.4))
        self.max.point(b + 6, fr(0.3), hand="L", up_deg=20, side_deg=60)
        # the moat fills first; then the tide climbs the beach, floods the flat over the castle base, and the
        # water table rises in the cut below
        self.moat_to(fr(0.05), fr(0.36), MOAT_UP)
        self.wt_to(fr(0.12), fr(0.7), -0.04)
        self.sea_to(fr(0.1), fr(0.4), -0.04)
        self.sea_to(fr(0.42), fr(0.74), 0.12)
        events.add(fr(0.1), "water_rush", duration=fr(0.74) - fr(0.1), gain=0.45)
        self.inset_set(fr(0.34), ramp=max(14, int(L * 0.2)), pore=True)
        self.inset_set(fr(0.42), ramp=10, bridges=False)
        self.grains_to(fr(0.44), fr(0.72), self.loose_d - 0.02, drop=-0.03)
        # the castle slumps and sinks into the water: it sags, spreads and leans while a fan slides out
        c3, fan = self.c["c3"], self.c["c2_mud"]
        m0, m1 = fr(0.44), fr(0.84)
        mid = (m0 + m1) // 2
        for f, s, rot, z in ((m0, (1, 1, 1), 0.0, -0.01), (mid, (1.1, 1.1, 0.68), 5.0, -0.08),
                             (m1, (1.25, 1.25, 0.36), 9.0, -0.18)):
            self.kscale(c3, f, s)
            c3.rotation_euler = (R(rot * 0.4), R(rot), 0)
            c3.keyframe_insert("rotation_euler", frame=f)
            c3.location = (CX, CY, z)
            c3.keyframe_insert("location", frame=f)
        self.show(fan, m0)
        self.grow(fan, m0, m1, (0.55, 0.55, 0.2), (1.0, 1.0, 0.75))
        self.show(fan, e + 1, False)
        clods = _noise("bc_clods", "#A3845A", "#8A6D47", scale=30, rough=0.6)
        Spray("c3_clods", clods, count=26, radius=0.07, seed=19).run(
            m0 + 2, m1, (CX + 0.2, CY - 0.45, 1.3), (CX + 0.3, CY - 1.45, 0.1), spread=0.7, arc=0.08, period=14)
        self.splash("tide", fr(0.56), at=(CX + 0.3, CY - 1.4, 0.15))
        self.splash("tide2", fr(0.7), at=(CX - 0.6, CY - 1.2, 0.15))
        toy.key_hold(self.crab, "location", m0)
        self.crab.location = (CRAB_RIM.x + 0.1, CRAB_RIM.y - 0.1, 0.75)
        self.crab.keyframe_insert("location", frame=m1)
        self.crab_flat(m1)
        self.max.act("no", fr(0.56), fr(0.84))
        self.shrug(fr(0.86), e)
        # the change: Max, his castle and the moat filling (close enough that both read big)
        self.frame_on(b, fr(0.3), [bpy.data.objects["c3_tower"], self.moat_water, (CX - 1.75, CY, 0.0),
                                   (CX + 1.75, CY, 0.0)], margin=0.08)
        self.label("PORES FULL", LBL_INSET, fr(0.36), e, size=0.34)
        self.label("HIGH TIDE", LBL_CASTLE, fr(0.12), e, size=0.34)
        self.label("WATER TABLE", (0.7, -0.08, -0.66), fr(0.3), e, size=0.31)       # in the cut, below the captions
        # why + result: the rising water table in the cut, the inset, the moat and the castle sinking in the sea
        self.frame_on(fr(0.3), e, [self.inset_ring, bpy.data.objects["c3_tower"], self.moat_water,
                                   (-0.6, 0.0, -0.95), (2.45, 0.0, -0.95)] + self.castle_pts(1.3, 2.25))

    def a_spray_bacteria(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        spot = self.work_at                                                # right beside the castle, like pack
        self.at(b, spot, 0.0)
        self.sea_to(b - 1, b, SEA_LOW)
        self.wt_to(b - 1, b, WT_LOW)
        self.moat_to(b - 1, b, MOAT_DOWN)
        # the castle is rebuilt in plain wet sand; it turns pink as the spray coats it
        c3, c4 = self.c["c3"], self.c["c4"]
        for path in ("scale", "location", "rotation_euler"):
            toy.key_hold(c3, path, b - 1)
        c3.scale = (1, 1, 1)
        c3.keyframe_insert("scale", frame=b)
        c3.location = (CX, CY, -0.01)
        c3.keyframe_insert("location", frame=b)
        c3.rotation_euler = (0, 0, 0)
        c3.keyframe_insert("rotation_euler", frame=b)
        sw = fr(0.36)
        self.show(c3, sw, False)
        self.show(c4, sw)
        self.kscale(c4, b, (1, 1, 1))
        self.inset_set(b - 8, ramp=8, pore=False, bridges=True)
        self.grains_to(b - 8, b, self.pack_d)
        toy.key_hold(self.crab, "location", b - 1)
        toy.key_hold(self.crab, "scale", b - 1)
        self.crab.location = CRAB_SAND
        self.crab.keyframe_insert("location", frame=b)
        self.kscale(self.crab, b, (1, 1, 1))
        # a pink spray bottle in his raised left hand all beat, a pink mist from its nozzle onto the castle
        s_on, s_off = fr(0.12), fr(0.92)
        self.steady(self.max, b + 6, e - 6)
        self.arm_hold(b + 6, s_on, s_off, e - 2, up=-82.0)
        bottle, tip_local = self._bottle()
        aim = (CX - 0.35, CY - 0.6, 1.2)
        p, rot = self.grip(bottle, fr(0.5), aim)
        tip = p + rot @ tip_local
        self.show(bottle, b)
        self.show(bottle, e + 1, False)
        Spray("spray_bact", toy.material("bc_bact_mix", toy.srgb("#E58AC0"), roughness=0.2), count=64,
              radius=0.045, seed=9).run(s_on + 2, s_off, tuple(tip), aim, spread=0.55, arc=0.12, period=12)
        Puffs("spray_mist", "#F7A8D2", count=16, size=0.12, seed=21).emit(
            range(s_on + 2, s_off, 3), lambda _f: tuple(tip), rise=0.15, life=10, drift=0.25)
        events.add(s_on + 2, "pour", duration=s_off - s_on - 2, gain=0.3)
        self.inset_set(fr(0.36), ramp=max(12, int(L * 0.2)), bact=True)
        self.label("S. PASTEURII", LBL_INSET, fr(0.3), e, size=0.34)
        self.crab_to(fr(0.7), fr(0.78), CRAB_RIM, jump=True)
        self.max.look_at(b + 4, (CX, CY, 1.2), hold=int(L * 0.6))
        self.max.act("yes", fr(0.72), e)
        self.max.smile(fr(0.72), big=True)
        # 1) close on Max, the bottle in his raised hand and the mist hitting the castle; 2) bottle, castle, inset
        self.close(b, sw, frac=0.5, offset=(0.5, 0, 0.12))
        self.frame_on(sw, e, [self.inset_ring, bpy.data.objects["c4_tower"], bottle], margin=0.08)

    def a_fail_wave(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        self.at(b)
        hit = fr(0.44)
        # the curling wave of the hook and the finale (the old cylinder read as a blue sausage): it rushes in,
        # breaks on the castle and drains back
        sg = self._surge()
        self.show(sg, fr(0.28))
        for f, x, z, s in ((fr(0.28), 5.0, -1.0, (0.55, 1, 0.3)), (fr(0.37), 3.7, -0.4, (0.6, 1, 0.5)),
                           (hit, 2.65, -0.12, (0.6, 1, 0.6)), (fr(0.55), 2.45, -0.2, (0.62, 1, 0.38)),
                           (fr(0.66), 2.7, -0.6, (0.5, 1, 0.08))):
            sg.location = (x, 0.0, z)
            sg.keyframe_insert("location", frame=f)
            self.kscale(sg, f, s)
        self.show(sg, fr(0.66) + 1, False)
        events.add(fr(0.28), "water_rush", gain=0.5)
        self.splash("wave1", hit, at=(CX + 1.2, 1.3, 0.9))
        Puffs("wave1_spray", "#F2FAFF", count=30, size=0.32, seed=12).emit(
            range(hit, hit + 20, 1), lambda f: (CX + 0.9 + 0.2 * math.sin(f * 0.9), 1.3, 1.1 + 0.5 * math.sin(f * 0.6)),
            rise=1.5, life=20, drift=0.7)
        c4 = self.c["c4"]
        self.melt(c4, hit, fr(0.84))
        toy.key_hold(self.crab, "location", hit)
        self.crab.location = (CRAB_RIM.x + 0.1, CRAB_RIM.y - 0.1, 0.62)
        self.crab.keyframe_insert("location", frame=fr(0.84))
        self.crab_flat(fr(0.84))
        self.wt_to(hit, fr(0.62), WT_HIGH)
        self.wt_to(fr(0.66), fr(0.95), WT_LOW)
        # why: the pores flood, the bridges go, and the bacteria had nothing to make crystals from
        self.inset_set(hit - 2, ramp=10, pore=True)
        self.inset_set(hit, ramp=10, bridges=False)
        self.grains_to(hit, fr(0.72), self.loose_d - 0.02, drop=-0.03)
        self.label("NO UREA", LBL_INSET, fr(0.4), e, size=0.3)
        self.label("NO CALCIUM", LBL_CASTLE, fr(0.42), e, size=0.3)
        self.max.act("talk", b + 2, fr(0.4))
        self.max.look_at(fr(0.38), (CX + 1.6, CY, 0.6), hold=16)
        self.gasp(hit, fr(0.6))
        self.max.act("no", fr(0.6), fr(0.84))
        self.shrug(fr(0.86), e)
        self.close(b, fr(0.28))
        self.explain(fr(0.28), e, [self.inset_ring] + self.castle_pts(1.3, 2.25))

    def a_cement_bath(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        self.at(b)
        self.show(self.c["c4"], b, False)
        self.show(self.moat, b, False)
        self.show(self.c["c5w"], b)
        self.kscale(self.c["c5w"], b, (1, 1, 1))
        for g in self.gloves:
            self.show(g, b)
        toy.key_hold(self.crab, "location", b - 1)
        toy.key_hold(self.crab, "scale", b - 1)
        self.crab.location = (2.55, 1.75, -0.04)
        self.crab.keyframe_insert("location", frame=b)
        self.kscale(self.crab, b, (1, 1, 1))
        self.inset_set(b - 8, ramp=8, pore=False, bridges=True)
        self.grains_to(b - 8, b, self.pack_d)
        # the change: the tub goes round the castle and fills with urea + calcium chloride up over the top
        self.show(self.tub, b + 2)
        events.add(b + 3, "clink", gain=0.4)
        self.bath.hide(fr(0.08), False)
        toy.hide_tree(self.bath.line, fr(0.08), False)
        face, top = self._bath_liquid()

        def liquid(f, level):
            face.scale = (1, 1, max(0.001, level - 0.012))
            face.keyframe_insert("scale", frame=f)
            top.location = (0, 0, level + 0.006)
            top.keyframe_insert("location", frame=f)

        for ob in (face, top):
            self.show(ob, fr(0.08))
            self.show(ob, fr(0.73), False)
        self.bath_level(fr(0.08), 0.06)
        self.bath_level(fr(0.26), 2.25, hold=False)
        liquid(fr(0.08), 0.06)
        liquid(fr(0.26), 2.25)
        events.add(fr(0.08), "pour", duration=fr(0.26) - fr(0.08), gain=0.5)
        self.max.act("interact", b + 2, fr(0.26))
        self.label("UREA + CaCl2", LBL_CASTLE + V((0, 0, 0.45)), fr(0.2), fr(0.64), size=0.3)   # clear of the tub rim
        # bubbles rise through the soaking liquid in front of the castle
        Puffs("bath_bubbles", "#E8FBFF", count=18, size=0.07, seed=27).emit(
            range(fr(0.28), fr(0.6), 2), lambda f: (-0.3 + ((f * 37) % 23) / 23.0 * 2.3, 1.25, 0.25),
            rise=1.7, life=26, drift=0.15)
        # three days pass while it soaks: the (bigger) calendar's pages flip, calcite grows at every grain contact
        self.show(self.calendar, b)
        self.kscale(self.calendar, b, (1.25, 1.25, 1.25))
        self.inset_set(fr(0.2), ramp=10, pore=True, bridges=False)
        for k, t in enumerate((0.34, 0.46, 0.58)):
            pg = self.pages[k]
            toy.key_hold(pg, "rotation_euler", fr(t))
            pg.rotation_euler = (R(-178), 0, 0)
            pg.keyframe_insert("rotation_euler", frame=fr(t) + 8)
            self.show(pg, fr(t) + 9, False)
            events.add(fr(t), "pop", gain=0.25)
        self.label("3 DAYS", (CAL_AT.x, 0.4, 3.95), fr(0.3), fr(0.72), size=0.3)       # above the calendar, not behind it
        self.inset_set(fr(0.36), ramp=max(12, int(L * 0.22)), calcite=True)
        self.label("CALCITE", LBL_INSET, fr(0.38), e, size=0.32)
        self.max.act("fold_arms", fr(0.3), fr(0.6))
        # drain (a stream pours out, the level visibly drops; wet tub floor + puddle stay), then air drying
        self.bath_level(fr(0.62), 2.25)
        self.bath_level(fr(0.72), 0.06, hold=False)
        liquid(fr(0.62), 2.25)
        liquid(fr(0.72), 0.06)
        Spray("bath_drain", toy.material("bc_bath_drain", toy.srgb("#5CD3E8"), roughness=0.05), count=40,
              radius=0.06, seed=29).run(fr(0.62), fr(0.74), (2.3, 1.3, 0.18), (2.95, 1.2, -0.12), spread=0.2,
                                        arc=0.15, period=8)
        events.add(fr(0.62), "pour", duration=fr(0.74) - fr(0.62), gain=0.45)
        self.bath.empty(fr(0.73))
        toy.hide_tree(self.bath.line, fr(0.73), True)
        self.inset_set(fr(0.66), ramp=10, pore=False)
        self.show(self.c["c5w"], fr(0.76), False)
        self.show(self.c["c5"], fr(0.76))
        self.kscale(self.c["c5"], fr(0.76), (1, 1, 1))
        Puffs("dry_puff", "#FFFFFF", count=10, size=0.3, seed=12).emit(
            range(fr(0.73), fr(0.78)), lambda f: (CX, CY - 0.6, 1.2), rise=0.8, life=18, drift=0.5)
        self.label("AIR-DRY 2 DAYS", LBL_CASTLE + V((0, 0, 0.45)), fr(0.68), e, size=0.3)
        self.max.act("yes", fr(0.66), fr(0.8))
        self.arms_v(fr(0.82), e)
        self.close(b, fr(0.22))
        self.explain(fr(0.22), e, [bpy.data.objects["tub_back"], self.inset_ring,
                                   bpy.data.objects["calendar_board"], (-0.58, 1.1, 0.0), (2.26, 1.1, 0.0)],
                     ground=False)

    def a_finale(self, i, b, e):
        L = e - b
        fr = lambda t: b + int(L * t)                                      # noqa: E731
        self._pts = []
        self.at(b, FIN_AT, 0.0)
        self.show(self.tub, b, False)
        self.show(self.calendar, b, False)
        for o in (self.bath.puddle, self.bath.wet):
            toy.hide_tree(o, b, True)
        self.inset_hide(b, True)                       # the inset would sit in front of the kids in the tower
        toy.key_hold(self.crab, "location", b - 1)
        self.crab.location = CRAB_RIM
        self.crab.keyframe_insert("location", frame=b)
        spots = [KID_TOWER[0], KID_TOWER[1] + V((-0.07, 0.04, 0.0))]
        for k, kid in enumerate(self.kids):
            kid.cut_place(b, spots[k], 0)
            self.show(kid.root, b)
            kid.smile(b, big=True)
        top = [(k.x + s * 0.35, k.y, k.z + 1.25) for k in KID_TOWER for s in (-1, 1)]
        # opening shot: Max, the stone castle and both kids in its tower (whole, nobody at an edge)
        self.frame_on(b, fr(0.24), [self.kids[0], self.kids[1]] + top + self.castle_pts(1.3, 2.3), margin=0.1)
        # the scale sign: high above the beach on the right, clear of the tower and the kids, labels on its face
        sign = self._sign()
        self.show(sign, fr(0.26))
        events.add(fr(0.26), "pop", gain=0.3)
        self.label("OREGON FLUME", (SIGN_AT.x, SIGN_AT.y - 0.12, 3.85), fr(0.3), e, size=0.26)
        self.label("19 x 300 WAVES", (SIGN_AT.x, SIGN_AT.y - 0.12, 3.5), fr(0.32), e, size=0.26)
        # the surge rolls in, breaks on the castle's right side and KEEPS breaking there to the end of the beat
        self.sea_to(b, fr(0.3), -0.2)
        hit = fr(0.44)
        sg = self._surge()
        self.show(sg, fr(0.16))
        for f, x, z, s in ((fr(0.16), 5.0, -1.0, (0.55, 1, 0.3)), (fr(0.32), 3.7, -0.4, (0.6, 1, 0.45)),
                           (hit, 2.65, -0.12, (0.6, 1, 0.55)), (fr(0.62), 2.5, -0.1, (0.62, 1, 0.6)),
                           (fr(0.8), 2.45, -0.1, (0.6, 1, 0.57)), (e, 2.42, -0.12, (0.6, 1, 0.55))):
            sg.location = (x, 0.0, z)
            sg.keyframe_insert("location", frame=f)
            self.kscale(sg, f, s)
        self.show(sg, e + 1, False)
        events.add(fr(0.16), "water_rush", duration=e - fr(0.16), gain=0.6)
        self.sea_to(fr(0.36), fr(0.5), -0.03)                # washes to the castle's foot, never a glassy sheet
        self.sea_to(max(e + 2, self.EPI - 4), max(e + 3, self.EPI - 3), -0.2)   # the hook's sea, as before
        self.splash("wave2", hit, at=(CX + 1.25, 1.35, 0.9))
        self.splash("wave2b", hit + 6, at=(CX + 0.7, 1.15, 0.4))
        Puffs("wave2_spray", "#F2FAFF", count=30, size=0.3, seed=11).emit(
            range(hit, e, 2), lambda f: (CX + 1.15 + 0.1 * math.sin(f * 0.7), 1.35, 1.0 + 0.2 * math.sin(f * 0.43)),
            rise=1.0, life=16, drift=0.5)
        self.max.act("talk", b + 2, fr(0.36))
        self.gasp(hit - 4, hit + 10)
        self.kids[0].wave(fr(0.46), fr(0.84), hand="R")
        self.kids[1].wave(fr(0.48), fr(0.84), hand="L")
        events.add(fr(0.46), "kids_cheer", gain=0.5)
        self.arms_v(fr(0.5), e)
        self.max.act("yes", fr(0.48), e)
        self.frame_on(fr(0.24), e, [self.kids[0], self.kids[1], bpy.data.objects["scale_card_board"],
                                    (3.0, 1.3, 0.0)] + top + self.castle_pts(1.3, 2.3))

    # ------------------- hooks (staged after the story) -------------------

    def a_wave_hook(self, i, h0, h1):
        self._pts = []
        L = h1 - h0
        fr = lambda t: h0 + int(L * t)                                     # noqa: E731
        m = self.max
        self.show(self.card, h0, False)
        sign = bpy.data.objects.get("scale_card_sign")                     # the finale's sign: off the hook's tower
        if sign is not None:
            self.show(sign, h0, False)
        m.cut_place(h0, FLAT_AT, 0.0)
        # the first frame is the impact: a tall curling wave breaks ON the castle's right wall, spray bursting over
        # the tower; it keeps pounding, then sags back while the castle stands
        wv = self.build_hook_wave()
        self.show(wv, h0)
        # it MOVES: rushing in from the right, it slams the castle within half a second, explodes into spray over
        # the tower, then collapses and drains back while the castle stands (a wave that only stood beside the
        # castle for 5 s read as a frozen blue wall, and the rehearsal rejected the hook for it)
        hit = h0 + 14
        for f, x, sz in ((h0, 4.3, 0.9), (hit, 2.42, 1.08), (fr(0.42), 2.36, 0.88), (fr(0.75), 2.45, 0.42),
                         (h1, 2.7, 0.12)):
            wv.location = (x, 0.0, 0.0)
            wv.keyframe_insert("location", frame=f)
            self.kscale(wv, f, (HOOK_WAVE_SX, 1, sz))
        Puffs("wave_hook_burst", "#F2FAFF", count=60, size=0.5, seed=4).emit(
            range(hit - 2, hit + 26, 1), lambda f: (CX + 0.55 + 0.35 * math.sin(f * 1.3), 1.15,
                                                   1.6 + 0.9 * math.sin(f * 0.71)), rise=2.2, life=26, drift=1.1)
        Puffs("wave_hook_spray", "#F2FAFF", count=30, size=0.3, seed=9).emit(
            range(hit + 20, fr(0.75), 3), lambda f: (CX + 0.8 + 0.18 * math.sin(f * 0.6), 1.2,
                                                    1.4 + 0.3 * math.sin(f * 0.37)), rise=1.0, life=16, drift=0.5)
        events.add(h0, "water_rush", duration=L, gain=0.7)
        self.splash("hook", hit, at=(CX + 1.0, 1.2, 1.2))
        self.splash("hook2", hit + 4, at=(CX + 0.6, 1.1, 2.4))
        # Max startles and points at the wave with his left arm (held, every 8 frames), gasping (the one open mouth)
        m.look_at(h0 + 2, (2.4, 1.0, 2.2), hold=max(1, L - 6))
        up = lambda f: (0, -60, 0) if f < h0 + 4 else (0, -112 + 6 * math.sin((f - h0) * 0.3), 0)   # noqa: E731
        self.key_dense(m, "shoulderL", h0, h1 - 2, up)
        self.gasp(h0 + 2, fr(0.75))
        # the kids in the tower: arms straight up, mouths wide, held through the beat
        for k, kid in enumerate(self.kids):
            kid.look_at(h0 + 2, (2.4, 1.0, 2.2), hold=max(1, L - 6))
            arm = lambda f, k=k: 0 if f < h0 + 2 + k else 168 + 4 * math.sin((f - h0) * 0.4 + k)  # noqa: E731
            self.key_dense(kid, "shoulderL", h0, h1 - 2, lambda f, a=arm: (0, -a(f), 0))
            self.key_dense(kid, "shoulderR", h0, h1 - 2, lambda f, a=arm: (0, a(f), 0))
            kid.key("mouth", h0, scale=(0.7, 0.6, 1.0))
            kid.key("mouth", h0 + 4, scale=(1.2, 0.6, 2.6))
            kid.key("mouth", fr(0.8), scale=(1.2, 0.6, 2.4))
            kid.key("mouth", h1, scale=(0.7, 0.6, 1.0))
            kid.brows(h0 + 4, 1.0)
        events.add(h0 + 4, "kids_cheer", gain=0.4)
        top = [(kk.x + s * 0.35, kk.y, kk.z + 1.25) for kk in KID_TOWER for s in (-1, 1)]
        crest = (2.4 - 0.25 * HOOK_WAVE_SX, 0.3, 3.4)
        back = (2.55 + 2.45 * HOOK_WAVE_SX, 0.3, -0.2)
        st.frame_all(self.rig, h0, h1, [self.kids[0], self.kids[1], m, crest, back, (CX, CY, 2.3)] + top,
                     cut=True, margin=0.06, lens=28, rise=0.08, push=0.1, swing=6.0)

    def a_melt_hook(self, i, h0, h1):
        self._pts = []
        L = h1 - h0
        for k in ("c5", "c5w", "c4"):
            self.show(self.c[k], h0, False)
        for kid in self.kids:
            self.show(kid.root, h0, False)
        self.show(self.card, h0, False)
        c3 = self.c["c3"]
        self.show(c3, h0)
        self.kscale(c3, h0, (1, 1, 1))
        self.max.cut_place(h0, MAX_AT, 0)
        self.sea_to(h0, h0 + L // 2, SEA_HIGH)
        self.melt(c3, h0 + int(L * 0.35), h1 - 4)
        self.shrug(h1 - int(L * 0.3), h1)
        st.frame_all(self.rig, h0, h1, [self.max] + self.castle_pts(1.3, 2.25), cut=True, margin=0.07, lens=28,
                     rise=0.16, push=0.1, swing=9.0)

    def _colour_grade(self):
        """Set-wide toy look: warm sun, a clear blue day sky with white clouds, punchy colour."""
        try:
            st.key_sky(self.scene, 1, 40)
        except Exception:
            pass
        if self.sun is not None and getattr(self.sun, "data", None) is not None:
            self.sun.data.color = (1.0, 0.88, 0.7)
        try:
            vs = self.scene.view_settings
            if vs.view_transform == "AgX":
                vs.look = "AgX - Punchy"
        except Exception:
            pass
        # the bright card and calendar boards become coloured toys instead of off-white planes
        for name, hexc in (("bc_card", "#FFE066"),):
            mat = bpy.data.materials.get(name)
            bsdf = mat and next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf is not None and not bsdf.inputs["Base Color"].is_linked:
                bsdf.inputs["Base Color"].default_value = (*toy.srgb(hexc)[:3], 1.0)
        # white cumulus clouds high in the blue sky, far behind the beach
        cloud = toy.material("bc_cloud", (0.95, 0.96, 1.0), roughness=0.9)
        crnd = random.Random(41)
        for k, (cx, cy, cz) in enumerate(((-60, 180, 38), (-10, 200, 52), (40, 170, 34), (90, 210, 58),
                                          (-110, 220, 62), (15, 160, 26))):
            for j in range(5):
                ob = toy.sphere(f"world_cloud{k}_{j}", crnd.uniform(5, 9),
                                (cx + j * 7 - 14 + crnd.uniform(-2, 2), cy, cz + crnd.uniform(-2, 3)),
                                scale=(1.3, 0.8, 0.6), mat=cloud, subdiv=1)
                st.no_shadow(ob)

    def attach(self, child, root, at=None):
        """Parent with explicit local coordinates (root unrotated, unscaled; `at` = the root's world spot)."""
        at = V(root.location) if at is None else V(at)
        child.parent = root
        child.matrix_parent_inverse.identity()
        child.location = V(child.location) - at
        return child

    def inset_hide(self, f, hidden=True):
        for ob in self.inset_objs:
            toy.hide_tree(ob, f, hidden)

    def bath_level(self, f, level, hold=True):
        self.bath.key_level(f, level, hold=hold)
        self.bath.line.keyframe_insert("location", frame=f)

    def prot_pts(self, px):
        return [(px - 0.64, PROT_Y, 0.0), (px + 0.06, PROT_Y, 0.66)]

    def face_castle(self, spot):
        a = facing_to(tuple(spot), (CX, CY, 0.0))
        return 0.55 * (((a + 180.0) % 360.0) - 180.0)

    def hand_world(self, f, hand, guess):
        """World position of Max's hand at frame f (evaluated), or `guess` if the rig cannot be evaluated."""
        sc = bpy.context.scene
        keep = sc.frame_current
        try:
            sc.frame_set(f)
            p = tuple(self.max.j[f"hand{hand}"].matrix_world.translation)
        except Exception:
            p = guess
        sc.frame_set(keep)
        return p

    def build_hook_wave(self):
        root = toy.empty("wave_hook_root", (0, 0, 0))
        water = _water_skin("bc_hookwave", "#2E9BEA")
        foam = _noise("bc_foam", "#F6FCFF", "#CFE6F4", scale=14, rough=0.6, bump=0.3)
        y0, y1 = 0.25, 6.0
        body = st.prism("wave_hook_body", WAVE_PROFILE, y0, y1, mat=water)
        self.attach(body, root)
        ym, ln = (y0 + y1) / 2, y1 - y0 + 0.1
        for name, x, z, r in (("wave_hook_lip", -0.72, 2.72, 0.27), ("wave_hook_crest", -0.25, 3.1, 0.2),
                              ("wave_hook_toe", -0.95, -0.12, 0.3)):
            self.attach(toy.cylinder(name, r, ln, (x, ym, z), rotation=(R(90), 0, 0), mat=foam, vertices=20),
                        root)
        toy.hide_tree(root, 1, True)
        return root

    def frame_on(self, f0, f1, things, margin=0.11):
        """frame_all on `things` + the beat's labels + Max, with a safe margin (nothing cut by the edges)."""
        st.frame_all(self.rig, f0, f1, list(things) + self._pts + [self.max], cut=True, margin=margin, lens=28,
                     rise=0.16, swing=6.0)

    def grip(self, ob, f, aim, hand="L"):
        """Put `ob` in Max's hand as posed at frame f, its local +X aimed at `aim`; it follows the hand after."""
        sc = bpy.context.scene
        keep = sc.frame_current
        sc.frame_set(f)
        hj = self.max.j[f"hand{hand}"]
        p = hj.matrix_world.translation.copy()
        d = V(aim) - p
        rot = Euler((0.0, math.atan2(-d.z, math.hypot(d.x, d.y)), math.atan2(d.y, d.x)))
        ob.parent = None
        ob.location = p
        ob.rotation_euler = rot
        bpy.context.view_layer.update()
        toy.parent_keep(ob, hj)
        sc.frame_set(keep)
        return p, rot.to_matrix()

    def arm_out(self, f0, f1, f_end, up=-80.0):
        """Left arm raised out to the side (toward the castle, screen right) from f0, held to f1, down at f_end."""
        m = self.max
        m.key("shoulderL", f0 - 8, rot_deg=(0, 0, 0))
        m.key("shoulderL", f0, rot_deg=(0, up, 0))
        m.key("shoulderL", f1, rot_deg=(0, up - 3, 0))
        m.key("shoulderL", f_end, rot_deg=(0, 0, 0))

    def prot_move(self, f0, f1, x, angle, y):
        toy.key_hold(self.prot, "location", f0)
        toy.key_hold(self.prot_pivot, "rotation_euler", f0)
        self.prot.location = (x, y, 0.008)
        self.prot.keyframe_insert("location", frame=f1)
        self.prot_pivot.rotation_euler = (0, R(angle), 0)
        self.prot_pivot.keyframe_insert("rotation_euler", frame=f1)

    def _hose_gun(self):
        root = toy.empty("hose_gun")
        green = tx.paint("bc_hose_gun", "#2FA84F")
        toy.box("hose_gun_grip", (0.06, 0.06, 0.18), (0, 0, -0.07), mat=green, parent=root)
        toy.cylinder("hose_gun_barrel", 0.04, 0.44, (0.21, 0, 0.03), rotation=(0, R(90), 0), mat=green,
                     parent=root, vertices=16)
        toy.cylinder("hose_gun_tip", 0.055, 0.07, (0.46, 0, 0.03), rotation=(0, R(90), 0),
                     mat=tx.metal("bc_hose_tip", "#C9A13B"), parent=root, vertices=16)
        toy.hide_tree(root, 1, True)
        return root, V((0.5, 0.0, 0.03))

    def _hose_line(self, end):
        """A green garden hose lying from the coil across the sand and up to the gun in Max's hand."""
        pts = [(-1.85, 1.42, 0.24), (-1.45, 1.42, 0.226), (-0.85, 1.4, 0.3), (-0.5, 1.3, 0.85),
               (end.x - 0.06, end.y + 0.02, end.z - 0.14)]
        cu = bpy.data.curves.new("hose_line", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.022
        cu.bevel_resolution = 3
        sp = cu.splines.new("NURBS")
        sp.points.add(len(pts) - 1)
        for k, p in enumerate(pts):
            sp.points[k].co = (p[0], p[1], p[2], 1.0)
        sp.use_endpoint_u = True
        sp.order_u = 3
        cu.materials.append(tx.rubber("bc_hose_line", "#2E9A48"))
        ob = bpy.data.objects.new("hose_line", cu)
        bpy.context.scene.collection.objects.link(ob)
        toy.hide_tree(ob, 1, True)
        return ob

    def _bottle(self):
        root = toy.empty("spray_bottle")
        pink = toy.material("bc_bottle", toy.srgb("#F07AB8"), roughness=0.25, coat=0.5)
        white = tx.paint("bc_bottle_head", "#F4F4F0")
        toy.cylinder("spray_bottle_body", 0.085, 0.32, (0, 0, -0.13), mat=pink, parent=root, vertices=24)
        toy.box("spray_bottle_head", (0.18, 0.08, 0.1), (0.04, 0, 0.08), mat=white, parent=root)
        toy.cylinder("spray_bottle_tip", 0.025, 0.09, (0.17, 0, 0.09), rotation=(0, R(90), 0), mat=white,
                     parent=root, vertices=12)
        toy.box("spray_bottle_trigger", (0.035, 0.035, 0.09), (0.09, 0, 0.0), mat=white, parent=root)
        toy.hide_tree(root, 1, True)
        return root, V((0.22, 0.0, 0.09))

    def _sign(self):
        """The scale card as a big blue sign high on two posts: the stone dune in its flume, labels on its face."""
        C = SIGN_AT
        root = toy.empty("scale_card_sign", tuple(C))
        wood = tx.wood("bc_sign_post", "#9C7448", "#7D5A35")
        for k, x in enumerate((C.x - 1.0, C.x + 1.0)):
            self.attach(toy.cylinder(f"card_signpost{k}", 0.045, 3.5, (x, C.y + 0.06, 1.35), mat=wood,
                                     vertices=12), root)
        self.attach(toy.box("scale_card_board", (2.5, 0.05, 1.15), (C.x, C.y, 3.55),
                            mat=tx.paint("bc_sign", "#2F5E9E", coat=0.2)), root)
        self.attach(toy.box("card_signflume", (2.2, 0.02, 0.14), (C.x, C.y - 0.04, 3.12),
                            mat=tx.paint("bc_sign_flume", "#7CC8F2"), bevel=0.003), root)
        self.attach(toy.sphere("card_signdune", 0.3, (C.x - 0.4, C.y - 0.05, 3.2), scale=(1.4, 0.12, 0.4),
                               mat=_noise("bc_sign_dune", "#EEE7D6", "#CFC4AD", scale=40)), root)
        toy.hide_tree(root, 1, True)
        return root

    def _surge(self):
        """A smaller copy of the hook's curling wave (same profile, foam lip), behind the castle front."""
        root = toy.empty("wave_surge_root", (0, 0, 0))
        water = _water_skin("bc_surge", "#2E9BEA")
        foam = _noise("bc_surge_foam", "#F6FCFF", "#CFE6F4", scale=14, rough=0.6)
        y0, y1 = 1.3, 5.5
        self.attach(st.prism("wave_surge_body", WAVE_PROFILE, y0, y1, mat=water), root)
        ym, ln = (y0 + y1) / 2, y1 - y0 + 0.1
        for name, x, z, r in (("wave_surge_lip", -0.72, 2.72, 0.27), ("wave_surge_crest", -0.25, 3.1, 0.2),
                              ("wave_surge_toe", -0.95, -0.12, 0.3)):
            self.attach(toy.cylinder(name, r, ln, (x, ym, z), rotation=(R(90), 0, 0), mat=foam, vertices=20), root)
        toy.hide_tree(root, 1, True)
        return root

    def _mud_heap(self):
        """The slumped tower: a lumpy heap of wet sand with mud tongues, broken merlons and a wet sheen rim
        (replaces the smooth cone + dark puddle disc, which read as a flat brown dome)."""
        root = self.c["c2_mud"]
        if "c2_mudheap" in bpy.data.objects:
            return bpy.data.objects["c2_mudheap"]
        for nm in ("c2_mud", "c2_puddle"):
            ob = bpy.data.objects.get(nm)
            if ob is not None:
                bpy.data.objects.remove(ob, do_unlink=True)
        rnd = random.Random(31)
        R0, H, nr, ns = 1.5, 0.45, 16, 64

        def height(t):
            return H * max(0.0, 1.0 - t ** 1.5) ** 0.9

        vs, fs = [(0.0, 0.0, H * 1.04)], []
        for i in range(1, nr + 1):
            t = i / nr
            for k in range(ns):
                a = 2 * math.pi * k / ns
                edge = 1.0 + 0.09 * math.sin(4 * a + 0.7) + 0.05 * math.sin(9 * a + 2.1)
                r = R0 * t * edge
                lump = 1.0 + 0.16 * math.sin(3 * a + 1.3) * math.sin(6.0 * t) + 0.1 * math.sin(7 * a) * math.sin(11 * t)
                z = height(t) * lump + (rnd.uniform(-0.012, 0.012) if i < nr else 0.0)
                vs.append((r * math.cos(a), r * math.sin(a), max(0.0, z)))
        for k in range(ns):
            fs.append((0, 1 + k, 1 + (k + 1) % ns))
        for i in range(nr - 1):
            o0, o1 = 1 + i * ns, 1 + (i + 1) * ns
            for k in range(ns):
                k1 = (k + 1) % ns
                fs.append((o0 + k, o1 + k, o1 + k1, o0 + k1))
        mud = _noise("bc_mud_heap", "#C98444", "#9C5E2A", scale=14, rough=0.3)
        heap = st.mesh_obj("c2_mudheap", vs, fs, mats=(mud,), smooth=True)
        heap.location = (CX, CY, -0.01)
        self.attach(heap, root)
        parts = [heap]
        wet = bpy.data.materials.get("bc_wet_castle") or mud
        for k, (x, y, rot) in enumerate(((0.38, -0.5, 25.0), (-0.55, -0.22, -40.0), (0.18, 0.35, 70.0))):
            t = math.hypot(x, y) / R0
            ch = toy.box(f"c2_mudchunk{k}", (0.16, 0.13, 0.12), (CX + x, CY + y, -0.01 + height(t) + 0.02), mat=wet,
                         rotation=(R(18 * (k - 1)), R(22), R(rot)))
            self.attach(ch, root)
            parts.append(ch)
        sheen = _ring("c2_mudwet", 1.3, 1.72, 0.022, 0.03, toy.material("bc_mud_sheen", toy.srgb("#6FA9C9"),
                                                                       roughness=0.05, coat=0.6),
                      loc=(CX, CY, -0.01))
        self.attach(sheen, root)
        parts.append(sheen)
        for ob in parts:
            toy.hide_tree(ob, 1, True)
        return heap

    def _inset_fill(self):
        """Pore water RISING inside the magnifier (a flat-topped level, shape keys) with a bright waterline."""
        c, r = INSET, INSET_R - 0.03
        levels = [-r, -0.5 * r, 0.0, 0.5 * r, r]
        n = 40
        xs = [-r + 2 * r * k / n for k in range(n + 1)]

        def shape(lv):
            out = []
            for x in xs:
                h = math.sqrt(max(0.0, r * r - x * x))
                out += [(x, 0.0, -h), (x, 0.0, min(max(lv, -h), h))]
            return out

        fs = [(2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1) for k in range(n)]
        fill = st.mesh_obj("inset_fill", shape(levels[0]), fs,
                           mats=(_noise("bc_fill", "#2A86D6", "#5DB8F2", scale=7, rough=0.05),), smooth=False)
        fill.location = (c.x, c.y + 0.075, c.z)
        fill.shape_key_add(name="Basis")
        keys = []
        for k, lv in enumerate(levels[1:]):
            kb = fill.shape_key_add(name=f"level{k + 1}", from_mix=False)
            for vi, co in enumerate(shape(lv)):
                kb.data[vi].co = co
            kb.value = 0.0
            kb.keyframe_insert("value", frame=1)
            keys.append(kb)
        line = toy.box("inset_fillline", (2.0, 0.01, 0.024), (c.x, c.y - 0.14, c.z - r),
                       mat=st.glow_mat("bc_fill_glow", "#CFF2FF", 2.5), bevel=0.0)
        for ob in (fill, line):
            toy.hide_tree(ob, 1, True)
        return fill, line, keys, levels, r

    def _jet(self, tip, aim):
        """A solid arcing water jet from the hose tip onto the tower."""
        mid = (V(tip) + V(aim)) / 2 + V((0, 0, 0.12))
        pts = [tuple(tip), tuple(mid), tuple(aim)]
        cu = bpy.data.curves.new("hose_jet", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.035
        cu.bevel_resolution = 3
        sp = cu.splines.new("NURBS")
        sp.points.add(len(pts) - 1)
        for k, p in enumerate(pts):
            sp.points[k].co = (p[0], p[1], p[2], 1.0)
        sp.use_endpoint_u = True
        sp.order_u = 3
        cu.materials.append(_noise("bc_hose_jet", "#5CC4E6", "#DDF3FF", scale=12, rough=0.05))
        ob = bpy.data.objects.new("hose_jet", cu)
        bpy.context.scene.collection.objects.link(ob)
        toy.hide_tree(ob, 1, True)
        return ob

    def _bath_liquid(self):
        """The bath's readable liquid: a tinted see-through front face and a rippling top skin, both riding the level."""
        face = _slab("tub_liquidface", -0.48, 2.16, 1.072, 1.088, _water_skin("bc_bath_face", "#46D2EA", 0.45),
                     z0=0.012, h=1.0)
        top = _slab("tub_liquidtop", -0.48, 2.16, 1.088, 2.84, st.water_surface("bc_bath_skin", "#7FE3F2"),
                    z0=0.06, h=0.004)
        for ob in (face, top):
            toy.hide_tree(ob, 1, True)
        return face, top

    def steady(self, ch, f0, f1, arm="L", step=10):
        """Hand-key hips, spine and the holding elbow densely from f0 to f1 (no clip moves the held prop)."""
        rest = lambda j: tuple(math.degrees(a) for a in ch.rest[j])      # noqa: E731
        for f in sorted(set(list(range(f0, f1, step)) + [f1])):
            ch.key("hips", f, rot_deg=rest("hips"), loc=(0, 0, 0.56))
            ch.key("spine", f, rot_deg=rest("spine"))
            ch.key(f"elbow{arm}", f, rot_deg=rest(f"elbow{arm}"))

    def arm_hold(self, f0, s_on, s_off, f_end, up, step=10):
        """Left arm: down, raised out to the side by s_on, held to s_off, down at f_end, keyed every `step`."""
        def v(f):
            if f <= s_on - 8:
                return 0.0
            if f <= s_on:
                return up * st.smooth((f - (s_on - 8)) / 8.0)
            if f <= s_off:
                return up - 3.0 * (f - s_on) / max(1, s_off - s_on)
            return (up - 3.0) * (1.0 - st.smooth((f - s_off) / max(1.0, f_end - s_off)))
        frames = set(range(f0, f_end, step)) | {s_on - 8, s_on, s_off, f_end}
        for f in sorted(x for x in frames if f0 <= x <= f_end):
            self.max.key("shoulderL", f, rot_deg=(0, v(f), 0))

    def key_dense(self, ch, joint, f0, f1, rot_fn, step=8):
        for f in sorted(set(list(range(f0, f1, step)) + [f1])):
            ch.key(joint, f, rot_deg=rot_fn(f))
