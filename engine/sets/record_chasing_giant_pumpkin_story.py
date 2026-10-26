"""
RECORD-CHASING GIANT PUMPKIN STORY set — Blender builder (see record_chasing_giant_pumpkin_story_spec.py).
Max grows a giant pumpkin for his kids: one root clump that can't feed it (buried vine: roots at every
leaf joint), flood watering that splits it (drip line on a timer), a vine shoved out of line that cracks
the stem (vine kept at 90 degrees), a soggy rotting bottom (sand bed), and a lift nobody can manage
(lifting ring + forklift). Finale: the forklift sets it on the weigh-off scale, the kids ride behind
in their little red wagon and sit on top for the photo.

One coherent backyard diorama, sliced open on the front face at y = 0: above the cut the bed, vine,
leaves, pumpkin, fence and shed; below it topsoil over darker subsoil. Everything underground (roots,
seed, drip line, droplets, wet soil) is drawn as a thin section decal just in front of the cut face.

Pumpkin coordinates: its root empty sits ON the vine at the stem joint (VJ) and the fruit grows away
from the vine toward +X, so scaling the root grows the pumpkin and its stem without detaching it.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from engine import events, textures as tx, toy
from engine.backyard import _appear, _key
from engine.camera import CameraRig, facing_to
from engine.character import Character
from engine.cutaway import _bold_font, _grass_tuft
from engine.machines import Puffs, Spray, nozzle
from engine.sets.plane_story import arrow, label
from engine.sets.record_chasing_giant_pumpkin_story_spec import ACTIONS, beat_actions

V = Vector
R = math.radians
PY = 0.95                            # the pumpkin's (and forklift lane's) line across the patch
VJ = V((-1.15, PY, 0.0))             # stem joint on the vine = the pumpkin root's x/y
BODY = V((1.1, 0.0, 0.47))           # fruit centre relative to its root (full size)
RXY, RZ = 0.85, 0.52                 # fruit radii (full size): 1.7 m wide, about 1 m tall
N_RIBS = 10
STEM_TOP = V((0.3, 0.0, 0.42))       # stem: fruit shoulder (pumpkin-root local) ...
STEM_BOT = V((0.02, 0.0, 0.08))      # ... down to the vine
RING_Z = 0.95                        # lifting ring height (pumpkin-root local)
SOIL_BASE = -0.04                    # pumpkin pressed into the bed
SAND_TOP = 0.08
TOP_Z, SUB_Z = -0.5, -6.0            # topsoil bottom, subsoil bottom
FACE = -0.025                        # section decals: just in front of the cut face (y = 0)
CROWN = V((-3.0, 0.35, 0.0))         # where the seed goes in: the main stem and its root ball
JOINTS_X = (-2.6, -2.15, -1.7)       # leaf joints along the front run of the vine (above the cut)
VINE0 = [V(p) for p in ((-3.0, 0.35, 0.04), (-2.6, 0.36, 0.04), (-2.15, 0.34, 0.04), (-1.7, 0.36, 0.04),
                        (-1.33, 0.4, 0.04), (-1.16, 0.6, 0.04), (-1.15, 0.95, 0.04), (-1.16, 1.3, 0.04),
                        (-1.3, 1.85, 0.04), (-1.8, 2.3, 0.04), (-2.6, 2.5, 0.04), (-3.4, 2.35, 0.04))]
JI = 6                                # the stem joint's index in VINE0
VINE_PULLED = list(VINE0)
VINE_PULLED[5], VINE_PULLED[6], VINE_PULLED[7] = V((-1.24, 0.63, 0.08)), V((-1.36, 0.95, 0.2)), V((-1.24, 1.27, 0.08))
MAXP = V((1.05, 0.38, 0))            # Max's usual spot: front-right of the pumpkin
VINE_SPOT = V((-2.15, 1.15, 0))      # behind the front vine, facing the camera
STEM_SPOT = V((-1.95, 1.4, 0))       # beside the stem joint
KID_SPOTS = (V((1.7, 2.3, 0)), V((2.2, 2.42, 0)))
WAGON_HOME = V((1.95, 1.85, 0))      # clear of the forklift lane (y 0.5..1.47)
WAGON_PUMP = V((1.15, 1.85, 0))      # pushed up to the pumpkin on harvest day
FENCE_Y = 2.9
SCALE_X = 4.6
TAP = V((-3.75, 0.25, 0))
SLIT_PHI = R(-54)                    # the rib (a groove) that splits, facing the camera
DIGITS = ("0", "88", "240", "415", "602", "771", "913", "1024", "1083", "1105")
PALLET_H = 0.14


def _mat(name, hexc, rough=0.5, **kw):
    return toy.material(name, toy.srgb(hexc), roughness=rough, **kw)


def _glow(name, hexc, strength=1.0, rough=0.4):
    m = _mat(name, hexc, rough)
    b = toy._principled(m)
    toy._set(b, "Emission Color", (*toy.srgb(hexc), 1))
    toy._set(b, "Emission Strength", strength)
    return m


def _curve(name, splines, radius, mat, taper=False, origin=(0, 0, 0), parent=None):
    """Smooth NURBS tube(s) through world points; the object's origin is `origin` (growth pivot)."""
    o = V(origin)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", radius, 3
    cu.resolution_u = 10
    if hasattr(cu, "use_fill_caps"):
        cu.use_fill_caps = True
    for pts in splines:
        sp = cu.splines.new("NURBS")
        sp.points.add(len(pts) - 1)
        for k, (pt, c) in enumerate(zip(sp.points, pts)):
            c = V(c) - o
            pt.co = (c.x, c.y, c.z, 1.0)
            pt.radius = (1.0 - 0.8 * k / max(1, len(pts) - 1)) if taper else 1.0
        sp.use_endpoint_u = True
        sp.order_u = min(3, len(pts))
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = o
    ob.data.materials.append(mat)
    if parent is not None:
        ob.parent = parent
    return ob


def _rod(name, a, b, radius, mat, parent=None, vertices=10):
    """A cylinder from point a to point b (in the parent's space)."""
    a, b = V(a), V(b)
    d = b - a
    ob = toy.cylinder(name, radius, d.length, (a + b) / 2, mat=mat, vertices=vertices)
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    if parent is not None:
        ob.parent = parent
    return ob


def _ribbon(name, pts, sides, mat, parent=None, thickness=0.012):
    """A flat strap through `pts`, `sides[k]` = half-width vector at each point."""
    bm = bmesh.new()
    left = [bm.verts.new(p - s) for p, s in zip(pts, sides)]
    right = [bm.verts.new(p + s) for p, s in zip(pts, sides)]
    for k in range(len(pts) - 1):
        bm.faces.new((left[k], left[k + 1], right[k + 1], right[k]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    sol = ob.modifiers.new("thick", "SOLIDIFY")
    sol.thickness = thickness
    if parent is not None:
        ob.parent = parent
    return ob


def _text(name, body, size, mat, parent=None, location=(0, 0, 0)):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.size, cu.extrude = body, size, 0.006
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    if _bold_font():
        cu.font = _bold_font()
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    ob.rotation_euler = (R(90), 0, 0)                      # reads from the front (-Y)
    if parent is not None:
        ob.parent = parent
    ob.location = location
    ob.visible_shadow = False
    return ob


def surface(phi, t, grow=1.0):
    """A point on the full-size fruit (pumpkin-root local): azimuth phi, elevation t (radians)."""
    z = math.sin(t)
    k = 1.0 - 0.06 * (0.5 - 0.5 * math.cos(N_RIBS * phi)) * (1 - abs(z) ** 4)
    zz = max(RZ * z, -0.47)
    return BODY + V((RXY * k * math.cos(t) * math.cos(phi) * grow, RXY * k * math.cos(t) * math.sin(phi) * grow,
                     zz * grow))


def pumpkin_mesh(name, mat, parent):
    """Squashed UV sphere with ten ribs (radial grooves) and a flattened base resting at z = 0."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=80, ring_count=40, location=(0, 0, 0))
    ob = bpy.context.active_object
    ob.name = name
    for v in ob.data.vertices:
        x, y, z = v.co
        phi = math.atan2(y, x)
        groove = 0.5 - 0.5 * math.cos(N_RIBS * phi)
        k = 1.0 - 0.06 * groove * (1 - abs(z) ** 4)
        zz = max(RZ * z * (1 - 0.025 * groove), -0.47)
        v.co = (BODY.x + x * RXY * k, BODY.y + y * RXY * k, BODY.z + zz)
    toy._finish(ob, mat, subdiv=1, parent=parent)
    return ob


class RecordChasingGiantPumpkinStorySet:
    ACTIONS = ACTIONS

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self.rnd = random.Random(11)
        self._light = None
        self._materials()
        self._world()
        self._plant()
        self._underground()
        self._pumpkin()
        self._props()
        self._wagon()
        self._forklift()
        self._scale()
        self._characters()
        self.vine_now = list(VINE0)
        self._initial_state()
        events.add(1, "birds", duration=total + 400, gain=0.12)          # quiet garden ambience

    # ------------------- materials -------------------

    def _materials(self):
        s = toy.srgb
        self.m = {
            "topsoil": toy.noise_material("pk_topsoil", s("#6E4A2E"), s("#87603F"), scale=9, roughness=0.9, bump=0.4),
            "subsoil": toy.noise_material("pk_subsoil", s("#422C1C"), s("#553A26"), scale=6, roughness=0.95, bump=0.4),
            "bed": toy.noise_material("pk_bed", s("#5A3B25"), s("#73503A"), scale=16, roughness=0.95, bump=0.7),
            "grass": toy.noise_material("pk_grass", s("#4C8A33"), s("#6AA543"), scale=30, bump=0.3),
            "wet": _mat("pk_wet_soil", "#2B1D14", 0.3, coat=0.4),
            "pumpkin": toy.noise_material("pk_skin", s("#F27A12"), s("#E3600A"), scale=5, roughness=0.42, bump=0.12),
            "stem": toy.noise_material("pk_stem", s("#A3A660"), s("#7E8742"), scale=18, roughness=0.7, bump=0.4),
            "vine": toy.noise_material("pk_vine", s("#4E8F2E"), s("#3B7424"), scale=22, roughness=0.6, bump=0.3),
            "leaf": toy.noise_material("pk_leaf", s("#3F8A2E"), s("#5BA640"), scale=8, roughness=0.6, bump=0.35),
            "root": _mat("pk_root", "#EADCB8", 0.7, subsurface=0.1),
            "slit": _mat("pk_slit", "#2A140A", 0.8),
            "water": _mat("pk_water", "#4FB3F0", 0.06, coat=0.8),
            "dripline": _mat("pk_dripline", "#161616", 0.5),
            "sand": toy.noise_material("pk_sand", s("#D9C38F"), s("#EAD8A8"), scale=45, roughness=0.95, bump=0.3),
            "rot": toy.noise_material("pk_rot", s("#5A3A1C"), s("#3A2511"), scale=14, roughness=0.8, bump=0.5),
            "worm": _mat("pk_worm", "#D98C8C", 0.4, subsurface=0.3),
            "seed": _mat("pk_seed", "#EFE3C0", 0.5),
            "post": tx.wood("pk_fence_post", "#7E5E40", "#9C7B58", along="z"),
            "rail": tx.wood("pk_fence_rail", "#7E5E40", "#9C7B58", along="x"),
            "red": tx.paint("pk_wagon_red", "#D8342C", 0.35, coat=0.5),
            "yellow": tx.paint("pk_fork_yellow", "#F2B705", 0.35, coat=0.4),
            "tyre": tx.rubber("pk_tyre", tread=24),
            "metal": tx.metal("pk_metal", "#8A9097", 0.3),
            "dark": tx.metal("pk_dark", "#2C2F33", 0.4, metallic=0.6),
            "ring": tx.paint("pk_ring", "#FF6A13", 0.4, coat=0.3),
            "strap": tx.cloth("pk_strap", "#FF8C1A"),
            "pallet": tx.wood("pk_pallet", "#C49A64", "#A57E4E", along="x"),
            "plank": tx.wood("pk_plank", "#B98250", "#9C6B3E", along="x"),
            "panel": _mat("pk_panel", "#15171B", 0.3, coat=0.5),
            "digits": _glow("pk_digits", "#FF8A1A", 3.0),
            "marker": _glow("pk_marker", "#FF7A1A", 1.4),
            "timer_led": _glow("pk_timer_led", "#3DFF6E", 4.0),
            "hose": _mat("pk_hose", "#2F8F3A", 0.5, coat=0.3),
        }

    # ------------------- world -------------------

    def _world(self):
        m = self.m
        toy.box("ground_topsoil", (30, 16, -TOP_Z), (0, 8, TOP_Z / 2), mat=m["topsoil"], bevel=0)
        toy.box("ground_subsoil", (30, 16, TOP_Z - SUB_Z), (0, 8, (TOP_Z + SUB_Z) / 2), mat=m["subsoil"], bevel=0)
        # lawn around the bed (front faces a hair behind the cut: a thin turf line on top of the section)
        for nm, x0, x1, y0, y1 in (("ground_lawn_r", 1.6, 15, 0.002, 16), ("ground_lawn_b", -15, 1.6, 2.75, 16),
                                   ("ground_lawn_l", -15, -3.95, 0.002, 2.75)):
            toy.box(nm, (x1 - x0, y1 - y0, 0.04), ((x0 + x1) / 2, (y0 + y1) / 2, -0.008), mat=m["grass"], bevel=0)
        # the pumpkin bed: slightly lumpy dug soil
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=60, size=1,
                                        location=((-3.95 + 1.6) / 2, (0.003 + 2.75) / 2, 0.004))
        bed = bpy.context.active_object
        bed.name = "ground_bed"
        bed.scale = (1.6 + 3.95, 2.75 - 0.003, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        tex = bpy.data.textures.new("pk_bed_lumps", "CLOUDS")
        tex.noise_scale = 0.25
        disp = bed.modifiers.new("lumps", "DISPLACE")
        disp.texture, disp.strength, disp.mid_level = tex, 0.03, 0.5
        bed.data.materials.append(m["bed"])
        tuft = _grass_tuft()
        for k, (nm, x0, x1, y0, y1) in enumerate((("g_right", 1.65, 9.0, 0.05, 2.7), ("g_back", -9.0, 9.0, 2.8, 9.0),
                                                  ("g_left", -9.0, -4.0, 0.05, 2.7))):
            toy.scatter(nm, x0, x1, y0, y1, tuft, 90, size=1.4, z=0.012, seed=k + 3)
        tuft.hide_render = True
        # small wooden fence behind the patch
        for k in range(14):
            toy.box(f"fence_post{k}", (0.09, 0.09, 0.95), (-3.9 + 0.55 * k, FENCE_Y, 0.475), mat=m["post"], bevel=0.01)
        for k, z in enumerate((0.4, 0.78)):
            toy.box(f"fence_rail{k}", (7.25, 0.05, 0.08), (-3.9 + 3.575, FENCE_Y - 0.06, z), mat=m["rail"], bevel=0.005)
        # garden shed
        shed = tx.planks("pk_shed", "#5C7C99", "#527090", width=0.2)
        toy.box("shed", (2.0, 1.6, 2.0), (-2.5, 4.1, 1.0), mat=shed, bevel=0.03)
        roof = tx.corrugated("pk_shed_roof", "#7C838C")
        for k, sd in enumerate((-1, 1)):
            toy.box(f"shed_roof{k}", (2.3, 1.0, 0.07), (-2.5, 4.1 + 0.42 * sd, 2.2), mat=roof, bevel=0.01,
                    rotation=(R(-30 * sd), 0, 0))
        toy.box("shed_door", (0.8, 0.05, 1.6), (-2.85, 3.29, 0.8), mat=tx.planks("pk_shed_door", "#7A4E2C", "#6B4426",
                                                                               width=0.12), bevel=0.01)
        toy.box("shed_window", (0.5, 0.05, 0.4), (-1.95, 3.29, 1.3), mat=_mat("pk_glass", "#9FC9E0", 0.05, coat=1.0),
                bevel=0.01)
        # tap on a standpipe (the hose, later the drip line, run from here)
        toy.cylinder("tap_pipe", 0.035, 1.1, (TAP.x, TAP.y, 0.2), mat=m["metal"], vertices=12)
        toy.box("tap_spout", (0.05, 0.12, 0.05), (TAP.x, TAP.y - 0.07, 0.62), mat=m["metal"], bevel=0.01)
        toy.cylinder("tap_handle", 0.06, 0.03, (TAP.x, TAP.y, 0.77), mat=_mat("pk_tap_red", "#C0392B", 0.4))
        # background: hills, trees, clouds
        hill = _mat("pk_hill", "#5F9B45", 0.9)
        for k, (x, r) in enumerate(((-22, 15), (6, 19), (34, 16))):
            toy.sphere(f"hill{k}", r, (x, 48, -r * 0.6), scale=(1.6, 1.0, 0.7), mat=hill, subdiv=1)
        bark = toy.noise_material("pk_bark", toy.srgb("#5A4632"), toy.srgb("#74604A"), scale=12, bump=0.6)
        leafy = toy.noise_material("pk_tree_leaf", toy.srgb("#3D6B2A"), toy.srgb("#5E8C38"), scale=6, bump=0.6)
        for k, (x, y, s) in enumerate(((-7.5, 7.5, 1.1), (6.5, 6.0, 1.0), (10.0, 10.0, 1.3), (-11.0, 11.0, 1.2))):
            h = 2.8 * s
            toy.cylinder(f"trunk{k}", 0.2 * s, h, (x, y, h / 2), mat=bark, vertices=10)
            r2 = random.Random(k + 20)
            for j in range(6):
                toy.sphere(f"leaf_tree{k}_{j}", r2.uniform(0.7, 1.0) * s,
                           (x + r2.uniform(-1, 1) * s, y + r2.uniform(-0.6, 0.6) * s, h + r2.uniform(0, 1.1) * s),
                           mat=leafy, subdiv=1)
        cloud = toy.material("pk_cloud", (1, 1, 1), roughness=0.95)
        r3 = random.Random(3)
        for i in range(6):
            root = toy.empty(f"cloud_{i}", (r3.uniform(-40, 40), r3.uniform(50, 75), r3.uniform(14, 24)))
            for k in range(5):
                pc = toy.sphere(f"cloud_{i}_{k}", r3.uniform(2.4, 3.6), (0, 0, 0), scale=(1.4, 1.0, 0.65), mat=cloud,
                                subdiv=1)
                pc.parent = root
                pc.location = (r3.uniform(-4, 4), r3.uniform(-1, 1), r3.uniform(-0.6, 0.8))
                pc.visible_shadow = False
            root.keyframe_insert("location", frame=1)
            root.location.x += 20
            root.keyframe_insert("location", frame=6000)
            toy.set_interpolation(root, "location", (1,), "LINEAR")
        for o in bpy.data.objects:
            if o.name.startswith(("ground_", "g_", "hill", "cloud")):
                o.visible_shadow = False

    # ------------------- the plant (above ground) -------------------

    def _plant(self):
        m = self.m
        # spring: the sprout (two seed leaves on a stalk)
        self.sprout = toy.empty("sprout", (CROWN.x, CROWN.y, 0.0))
        toy.cylinder("sprout_stalk", 0.012, 0.14, (0, 0, 0.07), mat=m["vine"], parent=self.sprout, vertices=8)
        for sd in (-1, 1):
            toy.sphere(f"sprout_leaf{sd}", 0.05, (0.05 * sd, 0, 0.15), scale=(1.4, 0.8, 0.25), mat=m["leaf"],
                       parent=self.sprout, subdiv=1).rotation_euler = (0, R(-20 * sd), 0)
        # the vine: one smooth tube whose control points can be keyed (pushed out of line, then fixed)
        self.vine = _curve("vine_main", [VINE0], 0.042, m["vine"])
        self.vine_spline = self.vine.data.splines[0]
        self.branch = _curve("vine_branch", [[(-3.0, 0.36, 0.04), (-3.25, 0.8, 0.04), (-3.4, 1.4, 0.04),
                                              (-3.3, 1.95, 0.04)]], 0.036, m["vine"])
        # broad leaves on petioles at the joints (each on a pivot so it can droop)
        self.leaves = []
        for k, (x, y, yaw, sc) in enumerate(((-2.6, 0.38, 0, 1.0), (-2.15, 0.36, 12, 1.1), (-1.7, 0.38, -12, 0.95),
                                             (-3.05, 0.4, 40, 0.9), (-3.25, 0.8, 70, 1.0), (-3.4, 1.45, 85, 1.05),
                                             (-1.3, 1.85, 45, 1.0), (-1.8, 2.3, 10, 1.1), (-2.6, 2.5, -10, 1.0),
                                             (-3.4, 2.35, 30, 0.95))):
            piv = toy.empty(f"leafpiv{k}", (x, y, 0.04), rotation=(0, 0, R(yaw)))
            piv.scale = (sc, sc, sc)
            _rod(f"leaf_petiole{k}", (0, 0, 0), (0, 0.15, 0.3), 0.013, m["vine"], parent=piv, vertices=8)
            disc = toy.sphere(f"leaf_blade{k}", 0.27, (0, 0.22, 0.33), scale=(1.0, 0.88, 0.1), mat=m["leaf"],
                              parent=piv, subdiv=1, segments=20, rings=10)
            disc.rotation_euler = (R(18), 0, 0)
            cup = toy.sphere(f"leaf_rim{k}", 0.2, (0, 0.24, 0.355), scale=(1.0, 0.85, 0.06), mat=m["leaf"],
                             parent=piv, subdiv=1, segments=16, rings=8)          # a raised centre: cupped
            cup.rotation_euler = (R(18), 0, 0)
            self.leaves.append((piv, yaw))
        # soil mounds that bury the front run of the vine
        self.mounds = []
        for k, x in enumerate((-2.82, -2.6, -2.38, -2.15, -1.92, -1.7, -1.5)):
            y = 0.35 + (0.05 if x > -1.6 else 0.0)
            mo = toy.sphere(f"mound{k}", 0.16, (x, y, 0.04), scale=(1.35, 0.85, 0.36), mat=m["bed"], subdiv=1)
            self.mounds.append(mo)

    # ------------------- underground (section decals in front of the cut face) -------------------

    def _underground(self):
        m = self.m
        rnd = random.Random(5)
        # the seed and its first root
        self.seed = toy.sphere("seed", 0.035, (CROWN.x, FACE + 0.01, -0.07), scale=(1.4, 0.5, 0.8), mat=m["seed"],
                               subdiv=1)
        self.seed_root = _curve("seed_root", [[(CROWN.x, FACE, -0.09), (CROWN.x + 0.02, FACE, -0.15),
                                               (CROWN.x - 0.01, FACE, -0.22)]], 0.01, m["root"], taper=True,
                                origin=(CROWN.x, FACE, -0.09))
        # the original root ball under the main stem: short and small
        top = V((CROWN.x, FACE, -0.02))
        spl = []
        for k in range(7):
            a = R(-160 + 140 * k / 6 + rnd.uniform(-8, 8))
            ln = rnd.uniform(0.2, 0.32)
            mid = top + V((math.cos(a) * ln * 0.5 + rnd.uniform(-0.03, 0.03), 0, math.sin(a) * ln * 0.5))
            spl.append([top, mid, top + V((math.cos(a) * ln, 0, math.sin(a) * ln))])
        self.rootball = _curve("rootball", spl, 0.02, m["root"], taper=True, origin=top)
        # roots that grow from each buried leaf joint
        self.jroots = []
        for k, x in enumerate(JOINTS_X):
            top = V((x, FACE, -0.02))
            main = [top, top + V((0.04, 0, -0.25)), top + V((-0.05, 0, -0.5)), top + V((0.02, 0, -0.78))]
            side_l = [top + V((0, 0, -0.18)), top + V((-0.18, 0, -0.3)), top + V((-0.34, 0, -0.5))]
            side_r = [top + V((0.01, 0, -0.3)), top + V((0.2, 0, -0.42)), top + V((0.3, 0, -0.62))]
            tiny = [top + V((0, 0, -0.05)), top + V((-0.12, 0, -0.1)), top + V((-0.2, 0, -0.2))]
            self.jroots.append(_curve(f"jroot{k}", [main, side_l, side_r, tiny], 0.022, m["root"], taper=True,
                                      origin=top))
        # drip line along the roots, fed from the tap; droplets fall from it
        y = FACE - 0.008
        self.dripline = _curve("drip_line", [[(-3.65, y, -0.14), (-1.4, y, -0.14), (0.9, y, -0.14)]], 0.016,
                               m["dripline"])
        self.dripfeed = _curve("drip_feed", [[(TAP.x, TAP.y - 0.12, 0.6), (TAP.x, TAP.y - 0.14, 0.4),
                                              (TAP.x, 0.04, 0.02), (TAP.x + 0.02, y, -0.12),
                                              (-3.65, y, -0.14)]], 0.016, m["dripline"])
        self.drip_root = toy.empty("drip_drops", (0, 0, 0))
        for k in range(12):
            x = -3.4 + 0.37 * k
            d = toy.sphere(f"drip_drop{k}", 0.022, (x, y - 0.012, -0.17), scale=(0.9, 0.9, 1.3), mat=m["water"],
                           parent=self.drip_root, subdiv=0, segments=10, rings=6)
            f0 = 1 + (k * 7) % 28
            for f, z, sc in ((f0, -0.165, 0.01), (f0 + 4, -0.17, 1.0), (f0 + 24, -0.38, 1.0), (f0 + 27, -0.39, 0.01)):
                d.location.z, d.scale = z, (0.9 * sc, 0.9 * sc, 1.3 * sc)
                d.keyframe_insert("location", index=2, frame=f)
                d.keyframe_insert("scale", frame=f)
            for fc in toy.fcurves(d):
                fc.modifiers.new("CYCLES")
        self.timer = toy.box("tap_timer", (0.13, 0.09, 0.17), (TAP.x, TAP.y - 0.08, 0.47),
                             mat=_mat("pk_timer", "#9AA0A6", 0.4, coat=0.3), bevel=0.015)
        led = toy.sphere("tap_timer_led", 0.016, (0, -0.048, 0.04), mat=m["timer_led"], parent=self.timer, subdiv=0)
        led.visible_shadow = False
        toy.cylinder("tap_timer_dial", 0.035, 0.01, (0, -0.048, -0.03), rotation=(R(90), 0, 0),
                     mat=_mat("pk_dial", "#F4F1EA", 0.4), parent=self.timer)
        # wet soil: the cut face darkens downward, the surface darkens around the pumpkin
        self.wet_face = toy.empty("wetsoil_face", (-0.2, -0.006, -0.002))
        toy.box("wetsoil_face_patch", (2.6, 0.006, 0.7), (0, 0, -0.35), mat=m["wet"], parent=self.wet_face, bevel=0)
        self.wet_top = toy.cylinder("wetsoil_top", 1.25, 0.006, (-0.25, PY, 0.016), mat=m["wet"], vertices=48)
        self.wet_top.scale = (1.0, 0.72, 1.0)                           # an oval that stops at the cut
        self.puddle = toy.cylinder("flood_puddle", 1.15, 0.01, (-0.4, PY - 0.08, 0.02), mat=m["water"], vertices=48)
        # sand bed (grows up from the bottom of a shallow pit) and the pile it comes from
        self.sand = toy.empty("sand_root", (-0.05, 0.948, -0.14))
        toy.box("sand_bed", (1.9, 1.904, 0.22), (0, 0, 0.11), mat=m["sand"], parent=self.sand, bevel=0)
        bpy.ops.mesh.primitive_cone_add(radius1=0.42, radius2=0.04, depth=0.42, vertices=24, location=(1.95, 0.42, 0.2))
        self.sand_pile = bpy.context.active_object
        self.sand_pile.name = "sand_pile"
        toy._finish(self.sand_pile, m["sand"], subdiv=1)
        # a worm in the mud
        self.worm = toy.empty("worm", (0.45, -0.045, -0.07))
        for k in range(3):
            toy.sphere(f"worm_seg{k}", 0.026, (0, 0, 0.045 * k), scale=(1, 1, 1.5), mat=m["worm"], parent=self.worm,
                       subdiv=1, segments=12, rings=8)
        toy.add_noise(self.worm, "rotation_euler", 1, strength=0.45, scale=5, phase=2)

    # ------------------- the pumpkin -------------------

    def _pumpkin(self):
        m = self.m
        self.pk = toy.empty("pk_root", VJ + V((0, 0, SOIL_BASE)))
        self.pk_body = pumpkin_mesh("pk_body", m["pumpkin"], self.pk)
        # stem: a short ridged cylinder from the fruit's shoulder to the vine, on a pivot at the fruit
        self.stem_piv = toy.empty("stem_piv", STEM_TOP, self.pk)
        self.stem_rest = (STEM_BOT - STEM_TOP).to_track_quat("Z", "Y").to_euler()
        self.stem_piv.rotation_euler = self.stem_rest
        ln = (STEM_BOT - STEM_TOP).length
        st = toy.cylinder("pk_stem", 0.075, ln, (0, 0, ln / 2), mat=m["stem"], parent=self.stem_piv, vertices=20)
        for v in st.data.vertices:
            idx = round(math.atan2(v.co.y, v.co.x) / (2 * math.pi / 20))
            if idx % 2:
                v.co.x *= 0.82
                v.co.y *= 0.82
        bpy.ops.mesh.primitive_torus_add(major_radius=0.074, minor_radius=0.02, location=(0, 0, 0))
        self.stem_crack = bpy.context.active_object
        self.stem_crack.name = "pk_stem_crack"
        toy._finish(self.stem_crack, m["slit"], subdiv=0, parent=st)
        self.stem_crack.location = (0, 0, -0.04)
        self.stem_crack.scale = (1.05, 1.05, 1.0)
        # the split along a rib (drawn in from bevel_factor_end)
        pts = []
        rnd = random.Random(9)
        side = V((-math.sin(SLIT_PHI), math.cos(SLIT_PHI), 0))
        for k in range(12):
            t = R(-42 + 100 * k / 11)
            pts.append(surface(SLIT_PHI, t, 1.012) + side * rnd.uniform(-0.025, 0.025))
        self.slit_mid = pts[5]
        self.slit_dir = V((math.cos(SLIT_PHI), math.sin(SLIT_PHI), 0.25)).normalized()
        self.slit = _curve("pk_slit", [pts], 0.03, m["slit"], parent=self.pk)
        # rot patch on the underside, facing the camera
        phi, t = R(-60), R(-38)
        self.rot = toy.sphere("pk_rot_patch", 0.26, surface(phi, t, 0.975), scale=(1.0, 0.22, 0.75), mat=m["rot"],
                              parent=self.pk, subdiv=1)
        self.rot.rotation_euler = (R(-20), 0, R(-150))
        # lifting ring + wide straps down the sides and under the fruit
        bpy.ops.mesh.primitive_torus_add(major_radius=0.42, minor_radius=0.045, location=(0, 0, 0))
        self.ring = bpy.context.active_object
        self.ring.name = "pk_ring"
        toy._finish(self.ring, m["ring"], subdiv=0, parent=self.pk)
        self.ring.location = (BODY.x, 0, RING_Z)
        self.straps = []
        for k in range(8):
            phi = R(22.5 + 45 * k)
            ts = [R(62 - 147 * j / 15) for j in range(16)]
            pts = []
            for t in ts:
                p = BODY + V((1.035 * RXY * math.cos(t) * math.cos(phi), 1.035 * RXY * math.cos(t) * math.sin(phi),
                              max(1.035 * RZ * math.sin(t), -0.485)))
                pts.append(p)
            sides = [V((-math.sin(phi), math.cos(phi), 0)) * 0.06 for _ in pts]
            self.straps.append(_ribbon(f"pk_strap{k}", pts, sides, m["strap"], parent=self.pk))
        self.pk_extras = {"slit": [self.slit], "rot": [self.rot], "ring": [self.ring] + self.straps,
                          "crack": [self.stem_crack]}

    # ------------------- small props -------------------

    def _props(self):
        m = self.m
        self.hose = nozzle("hose_nozzle")
        self.hose_tail = _curve("hose_tail", [[(0, 0, 0.0), (0, 0.05, -0.25), (0.05, 0.1, -0.6)]], 0.018, m["hose"],
                                parent=self.hose)
        self.jet = Spray("hose_jet", m["water"], count=30, radius=0.03, seed=3)
        self.spurt = Spray("slit_spurt", m["water"], count=28, radius=0.035, seed=5)
        self.dust = Puffs("bury_dust", "#7A5A3E", count=12, size=0.1, seed=4)
        # the plank lever of the failed lift: a short end under the fruit, a block, a long end on a hinge
        self.fulcrum = toy.box("plank_block", (0.25, 0.3, 0.2), (1.05, 0.6, 0.1), mat=m["post"], bevel=0.02)
        self.plank_a = toy.box("plank_short", (0.71, 0.24, 0.05), (0.7, 0.6, 0.18), mat=m["plank"], bevel=0.01,
                               rotation=(0, R(-9.7), 0))
        self.plank_b = toy.empty("plank_hinge", (1.05, 0.6, 0.24))
        toy.box("plank_long", (1.0, 0.24, 0.05), (0.5, 0, 0), mat=m["plank"], parent=self.plank_b, bevel=0.01)
        self.plank_b.rotation_euler = (0, R(-20), 0)
        # pallet (the forks slide between the bottom and top boards)
        self.pallet = toy.empty("pallet", (-0.05, 2.15, SAND_TOP))
        for j, y in enumerate((-0.5, 0.0, 0.5)):
            toy.box(f"pallet_base{j}", (1.2, 0.12, 0.025), (0, y, 0.0125), mat=m["pallet"], parent=self.pallet, bevel=0.004)
            for i, x in enumerate((-0.5, 0.0, 0.5)):
                toy.box(f"pallet_block{j}{i}", (0.12, 0.12, 0.09), (x, y, 0.07), mat=m["pallet"], parent=self.pallet,
                        bevel=0.004)
        for i in range(6):
            toy.box(f"pallet_deck{i}", (0.15, 1.2, 0.025), (-0.55 + 0.22 * i, 0, 0.1275), mat=m["pallet"],
                    parent=self.pallet, bevel=0.004)

    def _wagon(self):
        m = self.m
        self.wagon = toy.empty("wagon", (6.0, 1.8, 0))
        toy.box("wagon_floor", (1.1, 0.5, 0.04), (0, 0, 0.2), mat=m["red"], parent=self.wagon, bevel=0.01)
        for sd in (-1, 1):
            toy.box(f"wagon_side{sd}", (1.1, 0.03, 0.16), (0, 0.235 * sd, 0.3), mat=m["red"], parent=self.wagon,
                    bevel=0.008)
            toy.box(f"wagon_end{sd}", (0.03, 0.5, 0.16), (0.535 * sd, 0, 0.3), mat=m["red"], parent=self.wagon,
                    bevel=0.008)
        self.wagon_wheels = []
        for x in (-0.38, 0.38):
            for y in (-0.28, 0.28):
                self.wagon_wheels.append(toy.cylinder(f"wagon_wheel{x}{y}", 0.1, 0.05, (x, y, 0.1),
                                                      rotation=(R(90), 0, 0), mat=m["tyre"], parent=self.wagon))
        _rod("wagon_handle", (0.55, 0, 0.22), (0.95, 0, 0.55), 0.016, m["dark"], parent=self.wagon)
        toy.cylinder("wagon_grip", 0.022, 0.2, (0.95, 0, 0.55), rotation=(R(90), 0, 0), mat=m["dark"], parent=self.wagon)

    def _forklift(self):
        """Faces local +X (forks forward). Carriage slides up the mast; chains hang the lifting ring."""
        m = self.m
        r = self.fork = toy.empty("fork_root", (12.0, PY, 0))
        toy.box("fork_body", (1.85, 0.9, 0.5), (-1.1, 0, 0.55), mat=m["yellow"], parent=r, bevel=0.06)
        toy.box("fork_counter", (0.4, 0.95, 0.65), (-2.0, 0, 0.6), mat=m["yellow"], parent=r, bevel=0.08)
        toy.box("fork_seat", (0.4, 0.42, 0.12), (-1.15, 0, 0.86), mat=m["dark"], parent=r, bevel=0.03)
        toy.box("fork_seatback", (0.08, 0.42, 0.35), (-1.36, 0, 1.06), mat=m["dark"], parent=r, bevel=0.03)
        for x in (-0.45, -1.55):
            for y in (-0.4, 0.4):
                toy.cylinder(f"fork_post{x}{y}", 0.03, 1.05, (x, y, 1.33), mat=m["dark"], parent=r, vertices=10)
        toy.box("fork_roof", (1.25, 0.9, 0.05), (-1.0, 0, 1.87), mat=m["dark"], parent=r, bevel=0.01)
        toy.sphere("fork_beacon", 0.06, (-1.3, 0, 1.95), mat=_glow("pk_beacon", "#FF8A1A", 2.0), parent=r, subdiv=0)
        _rod("fork_column", (-0.6, 0, 0.8), (-0.78, 0, 1.1), 0.025, m["dark"], parent=r)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.13, minor_radius=0.018, location=(0, 0, 0))
        wheel = bpy.context.active_object
        wheel.name = "fork_steering"
        toy._finish(wheel, m["dark"], subdiv=0, parent=r)
        wheel.location, wheel.rotation_euler = (-0.8, 0, 1.12), (0, R(-35), 0)
        self.fork_wheels = []
        for x, rad in ((-0.4, 0.28), (-1.75, 0.22)):
            for y in (-0.52, 0.52):
                w = toy.cylinder(f"fork_wheel{x}{y}", rad, 0.2, (x, y, rad), rotation=(R(90), 0, 0), mat=m["tyre"],
                                 parent=r, bevel=0.03)
                self.fork_wheels.append((w, rad))
        for y in (-0.3, 0.3):
            toy.box(f"fork_mast{y}", (0.08, 0.08, 2.35), (0.02, y, 1.175), mat=m["metal"], parent=r, bevel=0.01)
        for z in (0.25, 2.3):
            toy.box(f"fork_mastbar{z}", (0.08, 0.68, 0.08), (0.02, 0, z), mat=m["metal"], parent=r, bevel=0.01)
        self.carriage = toy.empty("fork_carriage", (0.1, 0, 1.0), r)
        toy.box("fork_plate", (0.06, 0.7, 0.12), (0, 0, 0.0), mat=m["dark"], parent=self.carriage, bevel=0.01)
        toy.box("fork_backrest", (0.05, 0.7, 0.4), (0, 0, 0.26), mat=m["dark"], parent=self.carriage, bevel=0.01)
        for y in (-0.22, 0.22):
            toy.box(f"fork_tine{y}", (1.15, 0.1, 0.05), (0.6, y, 0.0), mat=m["dark"], parent=self.carriage, bevel=0.008)
        self.chains = toy.empty("fork_chains", (0, 0, 0), self.carriage)
        hook = V((0.85, 0, -0.05))
        toy.box("fork_hookbar", (0.08, 0.54, 0.04), (0.85, 0, -0.045), mat=m["dark"], parent=self.chains, bevel=0.005)
        for k, off in enumerate(((0.42, 0), (-0.42, 0), (0, 0.42), (0, -0.42))):
            _rod(f"fork_chain{k}", hook, (0.85 + off[0], off[1], -0.6), 0.012, m["metal"], parent=self.chains,
                 vertices=6)

    def _scale(self):
        m = self.m
        toy.box("scale_deck", (1.56, 1.6, 0.2), (SCALE_X, PY, 0.1), mat=m["metal"], bevel=0.03)
        toy.box("scale_deck_trim", (1.6, 1.64, 0.04), (SCALE_X, PY, 0.02), mat=m["dark"], bevel=0.01)
        px, py = SCALE_X + 1.2, PY + 0.6
        toy.cylinder("scale_post", 0.05, 1.6, (px, py, 0.8), mat=m["dark"], vertices=12)
        self.panel = toy.box("scale_panel", (1.1, 0.1, 0.5), (px, py, 1.75), mat=m["panel"], bevel=0.03)
        self.digits = [_text(f"scale_digits{k}", d, 0.3, m["digits"], parent=self.panel, location=(0, -0.056, -0.01))
                       for k, d in enumerate(DIGITS)]

    def _characters(self):
        self.max = Character("Max", {"hat": "#E2C25A", "iris": "#7A4A1C", "shirt": "#C8463C"})
        straw = tx.straw("pk_straw")
        for nm in ("Max_hat", "Max_brim"):
            ob = bpy.data.objects.get(nm)
            if ob is not None:
                ob.data.materials[0] = straw
        brim = bpy.data.objects.get("Max_brim")
        if brim is not None:
            brim.scale = (1.35, 1.48, 1.0)                     # wide straw-hat brim
        toy.cylinder("Max_hatband", 0.338, 0.07, (0, 0.01, 0.505), mat=_mat("pk_hatband", "#8E2A22", 0.6),
                     parent=self.max.j["head"], vertices=32).scale = (1.0, 1.05, 1.0)
        self.kids = [
            Character("Kid1", {"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5",
                               "hair": "#5B3A1E", "scale": 0.6, "ponytail": True}),
            Character("Kid2", {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B",
                               "hair": "#2B1A10", "scale": 0.56}),
        ]
        self.max.hold(self.hose, "R")
        self.hose.rotation_euler = (R(-30), 0, 0)
        self.max.place(1, VINE_SPOT, 0)
        self.max.auto_blink(1, self.total + 400, seed=11)
        for k, kid in enumerate(self.kids):
            kid.place(1, V((6.5 + 0.5 * k, 2.3, 0)), -90)
            kid.auto_blink(1, self.total + 400, seed=k + 3)

    def _initial_state(self):
        hide = [self.sprout, self.seed, self.seed_root, self.vine, self.branch, self.rootball, self.dripline,
                self.dripfeed, self.drip_root, self.timer, self.wet_face, self.wet_top, self.puddle, self.sand,
                self.sand_pile, self.worm, self.pk, self.fulcrum, self.plank_a, self.plank_b, self.pallet, self.fork,
                self.wagon, self.hose] + [p for p, _ in self.leaves] + self.mounds + self.jroots + self.digits[1:]
        for o in hide:
            toy.hide_tree(o, 1, True)
        for kid in self.kids:
            toy.hide_tree(kid.root, 1, True)

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

    # ------------------- keyframe helpers -------------------

    @staticmethod
    def _snap(obj, path, f, value):
        """Jump to `value` at frame f (a cut): hold the old value up to f-1."""
        toy.key_hold(obj, path, f - 1, "CONSTANT")
        setattr(obj, path, value)
        obj.keyframe_insert(path, frame=f)

    @staticmethod
    def move(obj, f0, f1, path, value, linear=False):
        toy.key_hold(obj, path, f0)
        if linear:
            toy.set_interpolation(obj, path, (f0,), "LINEAR")
        setattr(obj, path, value)
        obj.keyframe_insert(path, frame=f1)

    @staticmethod
    def pop(obj, f, frames=8):
        _appear(obj, f, frames=frames)
        toy.hide_tree(obj, f, False)

    def light(self, f, sun_e=4.2, bg_v=0.22, fill_e=900, color=(1.0, 0.93, 0.82), ease=0):
        if self._light is not None:
            self._key_light(f if ease else f - 1, *self._light)
        self._key_light(f + ease, sun_e, bg_v, fill_e, color)
        self._light = (sun_e, bg_v, fill_e, color)

    def _key_light(self, f, sun_e, bg_v, fill_e, color):
        d = self.sun.data
        d.energy, d.color = sun_e, color
        d.keyframe_insert("energy", frame=f)
        d.keyframe_insert("color", frame=f)
        self.fill.data.energy = fill_e
        self.fill.data.keyframe_insert("energy", frame=f)
        self.bg.default_value = bg_v
        self.bg.keyframe_insert("default_value", frame=f)

    def shot(self, f0, f1, cam_from, cam_to, aim_from, aim_to=None, lens=22, cut=True):
        self.rig.shot(f0, f1, cam_from=cam_from, cam_to=cam_to, aim_from=aim_from, aim_to=aim_to or aim_from,
                      lens=lens, fstop=8.0, cut=cut)

    def wide(self, f0, f1, cut=True):
        """The establishing three-quarter view: bed, cut face, pumpkin, Max and the kids at the fence."""
        self.shot(f0, f1, (1.4, -5.6, 2.3), (1.3, -5.3, 2.2), (-0.3, 1.3, 0.25), lens=22, cut=cut)

    # ------------------- world state -------------------

    def state(self, f, **flags):
        """Show/hide whole features of the diorama at frame f (only the ones named)."""
        groups = {
            "seed": [self.seed, self.seed_root], "sprout": [self.sprout],
            "vine": [self.vine, self.branch] + [p for p, _ in self.leaves],
            "rootball": [self.rootball], "jroots": self.jroots, "mounds": self.mounds,
            "drip": [self.dripline, self.dripfeed, self.drip_root, self.timer],
            "flood": [self.puddle], "wet": [self.wet_face, self.wet_top], "sand": [self.sand],
            "pile": [self.sand_pile], "worm": [self.worm], "plank": [self.fulcrum, self.plank_a, self.plank_b],
            "pallet": [self.pallet],
        }
        for key, on in flags.items():
            for o in groups[key]:
                toy.hide_tree(o, f, not on)

    # ---- the pumpkin ----

    def pk_show(self, f, extras=()):
        toy.hide_tree(self.pk, f, False)
        for name, objs in self.pk_extras.items():
            if name not in extras:
                for o in objs:
                    toy.hide_tree(o, f, True)

    def pk_snap(self, f, s, x=None, z=SOIL_BASE):
        self._snap(self.pk, "location", f, V((VJ.x if x is None else x, PY, z)))
        self._snap(self.pk, "scale", f, V((s, s, s)))

    def pk_to(self, f0, f1, s=None, loc=None, linear=False):
        if s is not None:
            self.move(self.pk, f0, f1, "scale", V((s, s, s)), linear)
        if loc is not None:
            self.move(self.pk, f0, f1, "location", V(loc), linear)

    def pk_world(self, f, local):
        root = V(toy.value_at(self.pk, "location", f))
        return root + V(local) * toy.value_at(self.pk, "scale", f)[0]

    def pk_center(self, f):
        return self.pk_world(f, BODY)

    def crack_open(self, f, frames=8):
        """The rib splits: the dark slit draws itself along the rib."""
        toy.hide_tree(self.slit, f, False)
        cu = self.slit.data
        cu.bevel_factor_end = 0.0
        cu.keyframe_insert("bevel_factor_end", frame=f)
        cu.bevel_factor_end = 1.0
        cu.keyframe_insert("bevel_factor_end", frame=f + frames)

    # ---- vine, stem, leaves ----

    def vine_key(self, f, pts):
        for p, c in zip(self.vine_spline.points, pts):
            p.co = (c.x, c.y, c.z, 1.0)
            p.keyframe_insert("co", frame=f)

    def vine_move(self, f0, f1, pts):
        self.vine_key(f0, self.vine_now)
        self.vine_key(f1, pts)
        self.vine_now = list(pts)

    def vine_snap(self, f, pts):
        self.vine_key(f - 1, self.vine_now)
        self.vine_key(f, pts)
        self.vine_now = list(pts)

    def stem_toward(self, f, world):
        """Stem pivot rotation + stretch so the stem's vine end reaches `world` at frame f."""
        root = V(toy.value_at(self.pk, "location", f))
        local = (V(world) - root) / toy.value_at(self.pk, "scale", f)[0]
        d = local - STEM_TOP
        return d.to_track_quat("Z", "Y").to_euler(), d.length / (STEM_BOT - STEM_TOP).length

    def stem_snap(self, f, rot=None, stretch=1.0):
        self._snap(self.stem_piv, "rotation_euler", f, rot or self.stem_rest)
        self._snap(self.stem_piv, "scale", f, V((1, 1, stretch)))

    def leaves_to(self, f0, f1, droop):
        for piv, yaw in self.leaves:
            self.move(piv, f0, f1, "rotation_euler", V((R(-droop), 0, R(yaw))))

    def leaves_snap(self, f, droop):
        for piv, yaw in self.leaves:
            self._snap(piv, "rotation_euler", f, V((R(-droop), 0, R(yaw))))

    # ---- wagon and forklift ----

    def wagon_snap(self, f, pos):
        self._snap(self.wagon, "location", f, V(pos))

    def wagon_move(self, f0, f1, pos):
        here = V(toy.value_at(self.wagon, "location", f0))
        self.move(self.wagon, f0, f1, "location", V(pos), linear=True)
        turns = (V(pos).x - here.x) / 0.1                 # rolling toward +X spins the wheels about +Y
        for w in self.wagon_wheels:
            toy.key_hold(w, "rotation_euler", f0)
            toy.set_interpolation(w, "rotation_euler", (f0,), "LINEAR")
            w.rotation_euler.y += turns
            w.keyframe_insert("rotation_euler", frame=f1)

    def fork_show(self, f, chains=False):
        toy.hide_tree(self.fork, f, False)
        toy.hide_tree(self.chains, f, not chains)

    def fork_snap(self, f, x, yaw, cz):
        self._snap(self.fork, "location", f, V((x, PY, 0)))
        self._snap(self.fork, "rotation_euler", f, V((0, 0, R(yaw))))
        self._snap(self.carriage, "location", f, V((0.1, 0, cz)))

    def fork_drive(self, f0, f1, x):
        here = V(toy.value_at(self.fork, "location", f0))
        yaw = toy.value_at(self.fork, "rotation_euler", f0)[2]
        ahead = (x - here.x) * math.cos(yaw)               # distance along the forklift's own +X
        self.move(self.fork, f0, f1, "location", V((x, PY, 0)), linear=True)
        for w, rad in self.fork_wheels:
            toy.key_hold(w, "rotation_euler", f0)
            toy.set_interpolation(w, "rotation_euler", (f0,), "LINEAR")
            w.rotation_euler.y += ahead / rad
            w.keyframe_insert("rotation_euler", frame=f1)

    def fork_lift(self, f0, f1, cz):
        self.move(self.carriage, f0, f1, "location", V((0.1, 0, cz)))

    # ---- Max ----

    def at(self, f, spot, face=0.0):
        toy.hide_tree(self.hose, f, True)
        self.max.cut_place(f, V(spot), face)
        self.max.pose(f)
        self.max.brows(f, 0.0)
        self.max.smile(f)

    def hose_on(self, f0, f1, target):
        """Max floods the bed from the hose in his hand (he keeps holding it afterwards)."""
        toy.hide_tree(self.hose, f0, False)
        m = self.max
        m.key("shoulderR", f0, rot_deg=(-55, 0, 10))
        m.key("shoulderR", f1, rot_deg=(-55, 0, 6))
        spot = V(toy.value_at(m.root, "location", f0))
        a = toy.value_at(m.root, "rotation_euler", f0)[2]
        fwd, side = V((math.sin(a), -math.cos(a), 0)), V((-math.cos(a), -math.sin(a), 0))
        src = spot + fwd * 0.55 + side * 0.27 + V((0, 0, 0.85))
        self.jet.run(f0 + 2, f1, source=src, target=V(target), spread=0.14, arc=0.25, period=9, sound="pour")

    def scratch_head(self, f0, f1):
        m = self.max
        m.pose(f0 + 4, shoulderR=(-25, 140, 0), head=(0, 14, 0))
        m.pose(f1 - 4, shoulderR=(-25, 150, 0), head=(0, 10, 0))
        m.brows(f0 + 4, 0.9)
        m.brows(f1, 0.0)
        m.pose(f1)

    def jaw_drop(self, f0, f1):
        m = self.max
        m.pose(f0 + 4, shoulderL=(-10, -60, 0), shoulderR=(-10, 60, 0), head=(-10, 0, 0))
        m.pose(f1 - 2, shoulderL=(-10, -70, 0), shoulderR=(-10, 70, 0), head=(-12, 0, 0))
        m.key("mouth", f0 + 4, scale=(1.2, 0.6, 2.6))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f0 + 4, 1.0)
        m.brows(f1, 0.0)

    def deadpan(self, f0, f1):
        """Turns slowly to the camera, flat brows, tiny mouth, two slow blinks."""
        m = self.max
        m.turn(f0 + 4, 0, frames=12)
        m.brows(f0, 0.3)
        m.brows(f0 + 24, -0.15)
        m.key("mouth", f0 + 8, scale=(0.6, 0.6, 0.55))
        m.blink([f for f in (f0 + 22, f0 + 40) if f < f1 - 3])

    def thumbs_up(self, f0, f1):
        m = self.max
        m.pose(f0 + 4, shoulderL=(-90, 0, 20))
        m.pose(f1 - 4, shoulderL=(-90, 0, 20))
        m.smile(f0 + 4, big=True)
        m.pose(f1)

    def salute(self, f0, f1):
        m = self.max
        m.pose(f0 + 6, shoulderR=(-150, 0, 40), head=(-4, 0, 0))
        m.pose(f1, shoulderR=(-150, 0, 40), head=(-4, 0, 0))
        m.smile(f0 + 6, big=True)

    def pat(self, f0, f1):
        """Hands working at ground level (packing soil, nudging the vine): arms only."""
        m = self.max
        f, k = f0, 0
        while f < f1 - 6:
            s = 1 if k % 2 else -1
            m.key("shoulderR", f, rot_deg=(-75, 0, 20 * s))
            m.key("shoulderL", f, rot_deg=(-65, 0, -15 * s))
            f += 8
            k += 1
        m.key("shoulderR", f1, rot_deg=(0, 0, 0))
        m.key("shoulderL", f1, rot_deg=(0, 0, 0))

    def strain(self, f0, f1):
        """Arms round the pumpkin, knees bent, heave... nothing moves."""
        m = self.max
        m.crouch(f0, f1, frames=8, lean=28)
        f, k = f0 + 8, 0
        m.key("shoulderL", f0, rot_deg=(0, 0, 0))
        m.key("shoulderR", f0, rot_deg=(0, 0, 0))
        while f < f1 - 6:
            m.key("shoulderL", f, rot_deg=(-80 - 6 * (k % 2), 0, -6))
            m.key("shoulderR", f, rot_deg=(-80 - 6 * (k % 2), 0, 6))
            f += 6
            k += 1
        m.key("shoulderL", f1, rot_deg=(0, 0, 0))
        m.key("shoulderR", f1, rot_deg=(0, 0, 0))
        m.brows(f0 + 8, -0.6)
        m.key("mouth", f0 + 10, scale=(1.1, 0.6, 0.5))
        m.brows(f1, 0.0)
        m.smile(f1)
        events.add(f0 + 12, "pant", gain=0.6)

    def push_down(self, f0, f1):
        m = self.max
        m.crouch(f0, f1, frames=6, lean=38)
        for f, a in ((f0, 0), (f0 + 6, -95), (f1 - 10, -40), (f1, 0)):
            m.key("shoulderL", f, rot_deg=(a, 0, -4))
            m.key("shoulderR", f, rot_deg=(a, 0, 4))

    # ---- the kids ----

    def kids_home(self, f):
        for k, kid in enumerate(self.kids):
            toy.hide_tree(kid.root, f, False)
            kid.cut_place(f, KID_SPOTS[k], 0)
            kid.pose(f)
            kid.smile(f)

    def glance(self, f):
        """The running gag: both kids look at their little wagon... then at the pumpkin."""
        wag = V(toy.value_at(self.wagon, "location", f)) + V((0, 0, 0.3))
        pk = self.pk_center(f)
        for k, kid in enumerate(self.kids):
            g = f + 3 * k
            kid.key("head", g - 4, rot_deg=(0, 0, 0))
            kid.look_at(g, wag, hold=14)
            kid.brows(g, 0.9)
            kid.look_at(g + 24, pk, hold=18)
            kid.brows(g + 48, 0.0)
            kid.key("head", g + 56, rot_deg=(0, 0, 0))

    @staticmethod
    def arms_up(kid, f0, f1):
        """Seated cheering: arms only (the hips stay down)."""
        f, n = f0, 0
        while f < f1 - 4:
            kid.key("shoulderL", f, rot_deg=(0, -150 - 10 * (n % 2), 0))
            kid.key("shoulderR", f, rot_deg=(0, 150 + 10 * (n % 2), 0))
            f += 7
            n += 1
        kid.key("shoulderL", f1, rot_deg=(0, 0, 0))
        kid.key("shoulderR", f1, rot_deg=(0, 0, 0))
        kid.smile(f0 + 2, big=True)

    @staticmethod
    def kid_top(k):
        """Where kid k sits on the pumpkin once it is on the scale."""
        dx = (-0.3, 0.3)[k]
        base = 0.2 + PALLET_H
        z = base + BODY.z + RZ * math.sqrt(1 - (dx / RXY) ** 2) - 0.02
        return V((SCALE_X + dx, PY - 0.05, z))

    # ------------------- the ladder -------------------

    def a_plant(self, i, b, e):
        L = e - b
        self.light(b)
        spot = V((CROWN.x, 0.95, 0))
        self.at(b, spot, 0)
        dig, drop, up = b + int(L * 0.12), b + int(L * 0.28), b + int(L * 0.48)
        m = self.max
        m.crouch(b + 4, up, frames=8, lean=32)
        for f, a in ((b + 4, 0), (dig, -60), (drop, -72), (up - 4, -40), (up, 0)):
            m.key("shoulderR", f, rot_deg=(a, 0, 10))
        events.add(dig, "scoop", gain=0.5)
        self.pop(self.seed, drop, frames=6)                      # the seed, seen in the cut face
        events.add(drop, "pop", gain=0.3)
        toy.hide_tree(self.seed_root, drop + 8, False)
        _key(self.seed_root, drop + 8, scale=V((0.01, 0.01, 0.01)))
        _key(self.seed_root, drop + 34, scale=V((1, 1, 1)))
        self.pop(self.sprout, up + 4, frames=14)
        events.add(up + 4, "pop", gain=0.4)
        m.point(up + 8, e - 6, hand="L", up_deg=25, side_deg=15)
        m.smile(up + 10, big=True)
        # the kids roll their little red wagon up to the fence, ready for the giant pumpkin
        w0, w1 = b + int(L * 0.5), b + int(L * 0.86)
        toy.hide_tree(self.wagon, b, False)
        self.wagon_snap(b, V((5.6, WAGON_HOME.y, 0)))
        self.wagon_move(w0, w1, WAGON_HOME)
        events.add(w0, "roll", duration=w1 - w0, gain=0.3)
        for k, kid in enumerate(self.kids):
            start = V((5.2 + 0.55 * k, KID_SPOTS[k].y, 0))
            face = facing_to(start, KID_SPOTS[k])
            toy.hide_tree(kid.root, b, False)
            kid.cut_place(b, start, face)
            kid.pose(b)
            kid.walk(w0 + 3 * k, w1 + 3 * k, to=KID_SPOTS[k], facing_deg=face, step_frames=6)
            kid.turn(w1 + 3 * k + 2, 0, frames=8)
            kid.smile(w1 + 6, big=True)
        cut = b + int(L * 0.52)
        self.shot(b, cut, (-2.2, -2.7, 0.8), (-2.3, -2.5, 0.75), (-3.0, 0.45, -0.12), lens=24)
        self.shot(cut + 1, e, (0.5, -6.4, 2.3), (0.3, -6.0, 2.2), (-0.5, 1.3, 0.0), lens=22)

    def a_fail_roots(self, i, b, e):
        L = e - b
        self.light(b, 5.2, 0.26, 950, color=(1.0, 0.8, 0.58))           # a hot afternoon
        self.state(b, seed=False, sprout=False, vine=True, rootball=True)
        self.pk_show(b)
        self.pk_snap(b, 0.3)
        self.pk_to(b + 2, e, s=0.32)                                     # it barely grows
        self.leaves_snap(b, 0)
        self.leaves_to(b + int(L * 0.1), b + int(L * 0.45), 55)          # the big leaves wilt
        spot = V((-0.25, 0.5, 0))
        self.at(b, spot, facing_to(spot, (-0.82, PY, 0)))
        self.max.turn(b + int(L * 0.32), 0, frames=8)
        self.scratch_head(b + int(L * 0.38), b + int(L * 0.7))
        self.kids_home(b)
        cut = b + int(L * 0.62)
        self.shot(b, cut, (-1.3, -4.4, 0.7), (-1.5, -4.1, 0.6), (-1.9, 0.6, -0.3), (-1.9, 0.6, -0.25))
        self.wide(cut + 1, e)
        self.glance(cut + 6)

    def a_bury_vine(self, i, b, e):
        L = e - b
        self.light(b)
        self.pk_show(b)
        self.pk_snap(b, 0.32)
        self.pk_to(b + int(L * 0.45), e, s=0.5)
        self.leaves_snap(b, 55)
        self.leaves_to(b + int(L * 0.55), b + int(L * 0.8), 0)          # fed again: the leaves perk up
        self.at(b, VINE_SPOT, 0)
        work = b + int(L * 0.62)
        self.max.crouch(b + 4, work, frames=8, lean=35)
        self.pat(b + 10, work - 2)
        span = work - b - 16
        drops, where = [], {}
        for k, mo in enumerate(self.mounds):
            t = b + 10 + int(span * k / (len(self.mounds) - 1))
            toy.hide_tree(mo, t, False)
            _key(mo, t, scale=V((1.35, 0.85, 0.02)))
            _key(mo, t + 8, scale=V((1.35, 0.85, 0.36)))
            if k % 2 == 0:
                events.add(t, "scoop", gain=0.35)
            drops.append(t)
            where[t] = V(mo.location) + V((0, -0.1, 0.06))
        self.dust.emit(drops, lambda f: where[f], rise=0.25, life=16, drift=0.15)
        for k, (jr, x) in enumerate(zip(self.jroots, JOINTS_X)):         # every buried joint roots
            t = drops[2 * k + 1] + 6
            toy.hide_tree(jr, t, False)
            _key(jr, t, scale=V((0.01, 0.01, 0.01)))
            _key(jr, t + 36, scale=V((1, 1, 1)))
            arrow(f"root_arrow{k}", (x, -0.12, -0.06), (0, 0, -0.32), t + 10, e, color="#FFD23F", width=0.06)
        self.max.point(work + 6, e - 4, hand="L", up_deg=15, side_deg=10)
        self.max.smile(work + 8, big=True)
        self.kids_home(b)
        self.shot(b, e, (-1.35, -3.9, 0.8), (-1.5, -3.6, 0.7), (-2.15, 0.5, -0.32), lens=22)

    def _flood(self, b, f1, f2, f3):
        """Soak, dry out, huge soak: the puddle and the dark wet soil in the cut face follow."""
        self._snap(self.puddle, "scale", b, V((0.01, 0.01, 1)))
        for f, s in ((f1, 0.85), (f2, 0.01), (f3, 1.2)):
            _key(self.puddle, f, scale=V((s, s * 0.6, 1)))              # oval: never past the cut face
        self._snap(self.wet_face, "scale", b, V((1, 1, 0.01)))
        for f, s in ((f1, 0.55), (f2, 0.15), (f3, 1.0)):
            _key(self.wet_face, f, scale=V((1, 1, s)))

    def _split(self, fc, end):
        self.crack_open(fc)
        events.add(fc, "crack", gain=1.0)
        events.add(fc + 2, "splash", gain=0.35)
        src = self.pk_world(fc, self.slit_mid)
        d = self.slit_dir
        tgt = V((src.x + d.x * 0.6, max(0.08, src.y + d.y * 0.45), 0.03))
        self.spurt.run(fc + 1, end - 2, source=src, target=tgt, spread=0.1, arc=0.35, period=10)

    def a_fail_split(self, i, b, e):
        L = e - b
        f1, f2, f3 = b + int(L * 0.2), b + int(L * 0.42), b + int(L * 0.6)
        fc = f3 + 4
        self.light(b)
        self.state(b, flood=True, wet=True)
        self.pk_show(b)
        self.pk_snap(b, 0.5)
        self.pk_to(b + 4, f1, s=0.62)                 # soak: a growth spurt
        self.pk_to(f1, f2, s=0.63)                    # dry days: almost nothing
        self.pk_to(f2 + 4, f3, s=0.8)                 # huge soak: the inside rushes ahead...
        self.pk_to(f3, fc, s=0.82)
        self._flood(b, f1, f2, f3)
        self.leaves_snap(b, 0)
        self.leaves_to(f1, f2, 28)
        self.leaves_to(f2 + 2, f3, 0)
        self.light(f1, 5.2, 0.26, 950, color=(1.0, 0.8, 0.58), ease=12)
        self.light(f2, ease=10)
        self.at(b, MAXP, facing_to(MAXP, (-0.4, PY, 0)))
        tgt = V((0.05, PY - 0.45, 0.03))
        self.hose_on(b + 2, f1, tgt)
        self.hose_on(f2 + 2, f3, tgt)
        self._split(fc, e)                            # ...and the skin gives way along a rib
        self.deadpan(fc + 4, e)
        self.kids_home(b)
        self.glance(fc + 14)
        self.shot(b, e, (2.0, -3.6, 1.5), (1.8, -3.3, 1.4), (0.2, 1.1, 0.3), lens=22)

    def a_drip_line(self, i, b, e):
        L = e - b
        self.light(b)
        self.state(b, flood=False, wet=False)
        self.pk_show(b)                               # a brand-new fruit: no split
        self.pk_snap(b, 0.22)
        self.pk_to(b + int(L * 0.3), e - 2, s=0.8, linear=True)        # steady water, steady growth
        d0, d1 = b + 4, b + int(L * 0.28)
        for ob in (self.dripline, self.dripfeed):
            toy.hide_tree(ob, d0, False)
            cu = ob.data
            cu.bevel_factor_end = 0.0
            cu.keyframe_insert("bevel_factor_end", frame=d0)
            cu.bevel_factor_end = 1.0
            cu.keyframe_insert("bevel_factor_end", frame=d1)
        self.pop(self.timer, d1 + 2)
        events.add(d1 + 2, "pop", gain=0.4)
        toy.hide_tree(self.drip_root, d1 + 10, False)                   # even droplets, every day
        self.leaves_snap(b, 0)
        spot = V((-3.25, 0.95, 0))
        self.at(b, spot, 0)
        self.max.point(d1, b + int(L * 0.7), hand="R", up_deg=30, side_deg=45)
        self.max.smile(d1 + 6, big=True)
        self.max.turn(b + int(L * 0.72), facing_to(spot, self.pk_center(e)), frames=8)
        self.kids_home(b)
        self.shot(b, e, (-1.5, -5.0, 1.1), (-1.4, -4.7, 1.0), (-1.9, 0.6, -0.15), lens=22)

    def a_fail_stem(self, i, b, e):
        L = e - b
        p0, p1 = b + int(L * 0.22), b + int(L * 0.6)
        self.light(b)
        self.pk_show(b)
        self.pk_snap(b, 0.8)
        self.pk_to(b + 2, p1, s=1.0)
        self.stem_snap(b)
        self.vine_move(p0, p1, VINE_PULLED)                             # the swelling side shoves the vine
        rot, stretch = self.stem_toward(p1, VINE_PULLED[JI])
        self.move(self.stem_piv, p0, p1, "rotation_euler", rot)         # ...bending the stem out of line
        self.move(self.stem_piv, p0, p1, "scale", V((1, 1, stretch)))
        events.add(p0 + 6, "creak", gain=0.5)
        toy.hide_tree(self.stem_crack, p1 + 1, False)                   # until it cracks
        events.add(p1 + 1, "crack", gain=0.8)
        arrow("vine_pull", (-1.22, PY - 0.42, 0.34), (-0.42, 0, 0.14), p0 + 4, e, color="#FF7A1A", width=0.07)
        self.at(b, STEM_SPOT, facing_to(STEM_SPOT, (VJ.x, PY, 0)))
        self.max.pose(b + int(L * 0.15), head=(12, 0, 0))
        cut = b + int(L * 0.8)
        self.jaw_drop(p1 + 3, cut)
        self.kids_home(b)
        self.shot(b, cut, (-2.5, -2.3, 1.9), (-2.35, -2.1, 1.8), (-1.05, PY, 0.25), lens=24)
        self.wide(cut + 1, e)
        self.glance(cut + 3)

    def _right_angle(self, f, end):
        """An orange right-angle marker on the ground where the stem meets the vine."""
        mat = self.m["marker"]
        c = V((VJ.x - 0.03, PY - 0.12, 0.13))
        parts = [toy.box("angle_vine", (0.04, 0.5, 0.025), (c.x, c.y - 0.25, c.z), mat=mat, bevel=0.005),
                 toy.box("angle_stem", (0.44, 0.04, 0.025), (c.x + 0.22, c.y, c.z), mat=mat, bevel=0.005),
                 toy.box("angle_sq_a", (0.1, 0.022, 0.02), (c.x + 0.05, c.y - 0.1, c.z), mat=mat, bevel=0.003),
                 toy.box("angle_sq_b", (0.022, 0.1, 0.02), (c.x + 0.1, c.y - 0.05, c.z), mat=mat, bevel=0.003)]
        for k, p in enumerate(parts):
            p.visible_shadow = False
            self.pop(p, f + 3 * k, frames=6)
            toy.hide_tree(p, end, True)
        events.add(f, "pop", gain=0.35)
        label("90°", (c.x + 0.3, c.y - 0.45, 0.5), f + 12, end, size=0.22, tilt=-4)

    def a_fix_angle(self, i, b, e):
        L = e - b
        self.light(b)
        self.pk_show(b)                               # the next fruit, stem whole
        self.pk_snap(b, 0.8)
        self.pk_to(b + int(L * 0.3), e - 2, s=1.0)
        self.vine_snap(b, VINE0)
        self.stem_snap(b)
        nudged = list(VINE0)                          # Max keeps the vine square to the stem as it grows
        for j in (5, 6, 7):
            nudged[j] = VINE0[j] + V((-0.04, 0, 0))
        self.vine_move(b + int(L * 0.3), b + int(L * 0.5), nudged)
        self.vine_move(b + int(L * 0.5), e - 2, VINE0)
        self.at(b, STEM_SPOT, facing_to(STEM_SPOT, (VJ.x, PY, 0)))
        work = b + int(L * 0.58)
        self.max.crouch(b + 4, work, frames=8, lean=35)
        self.pat(b + 10, work - 2)
        self.thumbs_up(work + 4, e)
        self._right_angle(b + int(L * 0.4), e)
        self.kids_home(b)
        self.shot(b, e, (-2.5, -2.3, 1.9), (-2.35, -2.1, 1.8), (-1.05, PY, 0.25), lens=24)

    def a_fail_rot(self, i, b, e):
        L = e - b
        self.light(b)
        self.state(b, wet=True)
        self.pk_show(b, extras=("rot",))
        self.pk_snap(b, 1.0)
        self._snap(self.rot, "scale", b, V((0.1, 0.022, 0.075)))
        _key(self.rot, b + int(L * 0.2), scale=V((0.1, 0.022, 0.075)))
        _key(self.rot, b + int(L * 0.75), scale=V((1.0, 0.22, 0.75)))   # the rot spreads
        self._snap(self.wet_face, "scale", b, V((1, 1, 1)))
        w0 = b + int(L * 0.42)
        toy.hide_tree(self.worm, w0, False)
        _key(self.worm, w0, scale=V((0.01, 0.01, 0.01)))
        _key(self.worm, w0 + 12, scale=V((1, 1, 1)))
        spot = V((1.0, 0.33, 0))
        self.at(b, spot, 0)
        self.thumbs_up(b + int(L * 0.1), b + int(L * 0.72))            # brave face
        self.max.brows(b + int(L * 0.5), 0.7)
        self.max.look_at(b + int(L * 0.5), (0.45, -0.05, -0.05), hold=24)
        self.kids_home(b)
        cut = b + int(L * 0.74)
        self.shot(b, cut, (0.7, -2.7, 0.2), (0.6, -2.45, 0.15), (0.2, 0.5, -0.05), lens=24)
        self.wide(cut + 1, e)
        self.glance(cut + 3)

    def a_sand_bed(self, i, b, e):
        L = e - b
        s0, s1 = b + int(L * 0.12), b + int(L * 0.66)
        self.light(b)
        self.state(b, worm=False, sand=True, pile=True)
        self.pk_show(b)
        self.pk_snap(b, 1.0)
        self.pk_to(s0, s1, loc=V((VJ.x, PY, SAND_TOP)))                 # rides up onto the sand
        self._snap(self.sand, "scale", b, V((1, 1, 0.01)))
        _key(self.sand, s0, scale=V((1, 1, 0.01)))
        _key(self.sand, s1, scale=V((1, 1, 1)))
        self._snap(self.sand_pile, "scale", b, V((1, 1, 1)))
        _key(self.sand_pile, s0, scale=V((1, 1, 1)))
        _key(self.sand_pile, s1, scale=V((0.4, 0.4, 0.4)))
        self.move(self.wet_face, s0, s1, "scale", V((1, 1, 0.01)))      # the soil under it dries
        self.state(s1 + 2, wet=False)
        for k, x in enumerate((-0.75, -0.05, 0.65)):                    # water drains down through the sand
            arrow(f"drain{k}", (x, -0.12, 0.05), (0, 0, -0.42), s1 - 8 + 4 * k, e, color="#5EC8FF", width=0.07)
        spot = V((1.1, 0.3, 0))
        self.at(b, spot, facing_to(spot, (-0.05, 0.3, 0)))
        self.max.rake(b + 6, s1)
        events.add(b + 8, "scoop", gain=0.3)
        self.max.turn(s1 + 2, 0, frames=8)
        self.max.point(s1 + 10, e - 4, hand="R", up_deg=10, side_deg=20)
        self.max.smile(s1 + 10, big=True)
        self.kids_home(b)
        self.shot(b, e, (0.7, -2.8, 0.3), (0.6, -2.6, 0.25), (0.2, 0.5, -0.05), lens=24)

    LIFT = V((0.95, 0.32, 0))
    PLANK_SPOT = V((2.3, 0.6, 0))

    def a_fail_lift(self, i, b, e):
        L = e - b
        t1 = b + int(L * 0.2)
        t2, t3 = b + int(L * 0.24), b + int(L * 0.38)
        t4 = b + int(L * 0.56)
        t5 = b + int(L * 0.68)
        t6 = b + int(L * 0.84)
        self.light(b, 4.4, 0.24, 950, color=(1.0, 0.95, 0.86))         # harvest day
        self.state(b, pile=False)
        self.pk_show(b)
        self.pk_snap(b, 1.0, z=SAND_TOP)
        self.wagon_snap(b, WAGON_HOME)
        self.wagon_move(b + 10, t1, WAGON_PUMP)                         # the wagon goes up to the pumpkin
        events.add(b + 10, "roll", duration=t1 - b - 10, gain=0.35)
        self.kids_home(b)
        for k, kid in enumerate(self.kids):
            kid.walk(b + 10, t1, to=KID_SPOTS[k] - V((0.75, 0, 0)), facing_deg=-90, step_frames=6)
            kid.turn(t1 + 6, 0, frames=8)
        push = V((3.15, WAGON_HOME.y, 0))
        mid = V((2.35, WAGON_HOME.y, 0))
        self.at(b, push, -90)
        self.max.walk(b + 10, t1, to=mid, facing_deg=-90, step_frames=8, hold_arm="R", hold_rot=(-60, 0, 0))
        self.max.walk(t2, t3, to=self.LIFT, facing_deg=facing_to(mid, self.LIFT), step_frames=7)
        self.max.turn(t3 + 2, facing_to(self.LIFT, (-0.05, self.LIFT.y, 0)), frames=6)
        self.strain(t3 + 6, t4)                                         # 1. by hand: nothing
        self._snap(self.plank_b, "rotation_euler", b, V((0, R(-20), 0)))
        for k, o in enumerate((self.fulcrum, self.plank_a, self.plank_b)):
            self.pop(o, t4 - 8 + 3 * k, frames=6)
            events.add(t4 - 8 + 3 * k, "pop", gain=0.25)
        self.max.walk(t4 + 2, t5, to=self.PLANK_SPOT, facing_deg=facing_to(self.LIFT, self.PLANK_SPOT), step_frames=7)
        self.max.turn(t5 + 1, facing_to(self.PLANK_SPOT, (0, self.PLANK_SPOT.y, 0)), frames=6)
        self.move(self.plank_b, t5 + 8, t6, "rotation_euler", V((0, R(12), 0)))   # 2. the plank bends flat
        self.push_down(t5 + 4, t6 + 6)
        events.add(t5 + 12, "creak", gain=0.7)
        events.add(t6, "flop", gain=0.4)
        self.max.brows(t6 + 4, 0.9)
        self.max.key("mouth", t6 + 6, scale=(0.7, 0.6, 0.5))
        self.glance(t6 + 8)                                             # the wagon... the pumpkin...
        self.shot(b, e, (1.5, -4.6, 1.8), (1.4, -4.3, 1.7), (0.9, 1.0, 0.45), lens=22)

    def a_lift_ring(self, i, b, e):
        L = e - b
        d0, d1 = b + int(L * 0.12), b + int(L * 0.38)
        l0, l1 = b + int(L * 0.42), b + int(L * 0.56)
        p0, p1 = b + int(L * 0.6), b + int(L * 0.72)
        o0, o1 = b + int(L * 0.76), b + int(L * 0.88)
        self.light(b, 4.4, 0.24, 950, color=(1.0, 0.95, 0.86))
        self.state(b, plank=False, pallet=True)
        self.pk_show(b, extras=("ring",))
        self.pk_snap(b, 1.0, z=SAND_TOP)
        self.pop(self.ring, b + 4, frames=8)                            # ring on top...
        for k, st in enumerate(self.straps):                            # ...wide straps all the way round
            toy.hide_tree(st, b, True)
            toy.hide_tree(st, b + 10 + 2 * k, False)
        events.add(b + 4, "pop", gain=0.3)
        self.fork_show(b)
        self.fork_snap(b, 5.8, 180, SAND_TOP + RING_Z + 0.6)
        self.fork_drive(d0, d1, 0.9)
        events.add(d0, "engine_rev", gain=0.6)
        events.add(d0 + 20, "engine", duration=e - d0 - 20, gain=0.45)
        toy.hide_tree(self.chains, d1 + 4, False)
        events.add(d1 + 4, "clink", gain=0.6)
        up = 0.55
        self.fork_lift(l0, l1, up + RING_Z + 0.6)
        self.pk_to(l0, l1, loc=V((VJ.x, PY, up)))
        events.add(l0, "engine_rev", gain=0.5)
        for j, k in enumerate((5, 6, 7, 0)):                            # the load shared by every strap
            phi = R(22.5 + 45 * k)
            a = BODY + V((1.09 * RXY * math.cos(phi), 1.09 * RXY * math.sin(phi), 0.02))
            c40 = math.cos(R(40))
            top = BODY + V((1.09 * RXY * c40 * math.cos(phi), 1.09 * RXY * c40 * math.sin(phi), 1.09 * RZ * math.sin(R(40))))
            arrow(f"strap_load{k}", a, (top - a) * 0.6, l0 + 8 + 2 * j, o1, color="#FFD23F", width=0.06, parent=self.pk)
        self._snap(self.pallet, "location", b, V((-0.05, 2.15, SAND_TOP)))
        self.move(self.pallet, p0, p1, "location", V((-0.05, PY, SAND_TOP)))
        events.add(p0, "roll", duration=p1 - p0, gain=0.3)
        rest = SAND_TOP + PALLET_H
        self.fork_lift(o0, o1, rest + RING_Z + 0.6)
        self.pk_to(o0, o1, loc=V((VJ.x, PY, rest)))
        events.add(o1, "stone_thud", gain=0.5)
        self.at(b, STEM_SPOT, facing_to(STEM_SPOT, (0.6, -4.0, 0)))
        self.max.point(b + 6, d1, hand="L", up_deg=60, side_deg=10)
        self.max.cheer(o1 + 2, e - 2)
        self.wagon_snap(b, WAGON_HOME)
        self.kids_home(b)
        for kid in self.kids:
            kid.cheer(o1 + 4, e - 2)
        events.add(o1 + 4, "kids_cheer", gain=0.7)
        self.shot(b, e, (2.2, -4.8, 2.4), (2.0, -4.5, 2.3), (0.35, 1.0, 0.85), (0.35, 1.0, 1.0), lens=22)

    def photo(self, f0, f1):
        """Both kids on top of the pumpkin on the scale, in one piece; Max salutes."""
        for k, kid in enumerate(self.kids):
            toy.hide_tree(kid.root, f0, False)
            kid.cut_place(f0, self.kid_top(k), 0)
            self.arms_up(kid, f0 + 4 + 3 * k, f1)
        events.add(f0 + 4, "kids_cheer")
        self.at(f0, V((SCALE_X - 1.3, 0.22, 0)), 0)
        self.salute(f0, f1)
        self.shot(f0, f1, (SCALE_X - 0.5, -3.9, 1.6), (SCALE_X - 0.45, -3.6, 1.55), (SCALE_X - 0.15, 0.95, 1.0),
                  lens=24)

    def a_finale(self, i, b, e):
        L = e - b
        x0 = 2.4
        t0, t1 = b + 10, b + int(L * 0.38)
        t2 = b + int(L * 0.46)
        tc = b + int(L * 0.64)
        zp, zd = 0.3, 0.2
        self.light(b, 4.4, 0.24, 950, color=(1.0, 0.95, 0.86))
        self.state(b, sand=False, pallet=True, pile=False)
        self.pk_show(b)
        self._snap(self.pallet, "location", b, V((x0, PY, zp)))
        self.pk_snap(b, 1.0, x=x0 - 1.1, z=zp + PALLET_H)
        self.fork_show(b)
        self.fork_snap(b, x0 - 0.7, 0, zp + 0.06)
        # 1. the parade: forklift and pumpkin, then Max pulling the wagon with both kids riding in it
        self.fork_drive(t0, t1, SCALE_X - 0.7)
        self.move(self.pallet, t0, t1, "location", V((SCALE_X, PY, zp)), linear=True)
        self.move(self.pk, t0, t1, "location", V((SCALE_X - 1.1, PY, zp + PALLET_H)), linear=True)
        events.add(b, "engine", duration=tc - b, gain=0.45)
        w0, w1 = V((x0 - 2.6, WAGON_HOME.y, 0)), V((SCALE_X - 2.6, WAGON_HOME.y, 0))
        self.wagon_snap(b, w0)
        self.wagon_move(t0, t1, w1)
        events.add(t0, "roll", duration=t1 - t0, gain=0.3)
        offs = (V((-0.27, 0, 0.22)), V((0.2, 0, 0.22)))
        for k, kid in enumerate(self.kids):
            toy.hide_tree(kid.root, b, False)
            kid.cut_place(b, w0 + offs[k], 90)
            kid.pose(b)
            kid.sit(b - 1, self.total + 380, frames=1)
            self.move(kid.root, t0, t1, "location", w1 + offs[k], linear=True)
            self.arms_up(kid, t0 + 10 + 4 * k, t1 - 6)
        events.add(t0 + 12, "kids_cheer", gain=0.6)
        pull = V((1.25, 0, 0))
        self.at(b, w0 + pull, 90)
        self.max.walk(t0, t1, to=w1 + pull, facing_deg=90, step_frames=8, hold_arm="R", hold_rot=(35, 0, 0))
        self.max.smile(t0 + 4, big=True)
        self.max.turn(t1 + 6, facing_to(w1 + pull, (SCALE_X, PY, 0)), frames=8)
        # 2. onto the scale: the digits roll up, the forks back out
        self.fork_lift(t1 + 2, t2, zd + 0.06)
        self.move(self.pallet, t1 + 2, t2, "location", V((SCALE_X, PY, zd)))
        self.move(self.pk, t1 + 2, t2, "location", V((SCALE_X - 1.1, PY, zd + PALLET_H)))
        events.add(t2, "stone_thud", gain=0.6)
        self.fork_lift(t2 + 2, t2 + 8, zd + 0.045)
        self.fork_drive(t2 + 10, tc - 4, SCALE_X - 2.1)
        roll_end = tc - 6
        for k in range(1, len(self.digits)):
            f = t2 + 4 + int((roll_end - t2 - 4) * k / (len(self.digits) - 1))
            toy.hide_tree(self.digits[k - 1], f, True)
            toy.hide_tree(self.digits[k], f, False)
            events.add(f, "pop", gain=0.12)
        self.shot(b, t1, (0.9, -5.6, 1.9), (2.6, -5.6, 1.9), (1.2, 1.2, 0.6), (2.9, 1.2, 0.6), lens=22)
        self.shot(t1 + 1, tc, (SCALE_X - 1.2, -4.8, 2.0), (SCALE_X - 1.0, -4.5, 1.9), (SCALE_X - 0.6, 1.1, 0.8),
                  lens=22)
        # 3. the photo: the hook again, but this time the pumpkin is in one piece
        self.photo(tc + 1, e)

    # ------------------- hooks (staged in the epilogue, shown first) -------------------

    def a_split_hook(self, i, h0, h1):
        L = h1 - h0
        self.light(h0)
        self.state(h0, seed=False, sprout=False, vine=True, rootball=True, jroots=True, mounds=True, drip=False,
                   flood=True, wet=True, sand=False, pile=False, worm=False, plank=False, pallet=False)
        toy.hide_tree(self.fork, h0, True)
        toy.hide_tree(self.wagon, h0, True)
        for kid in self.kids:
            toy.hide_tree(kid.root, h0, True)
        self.pk_show(h0)
        self.pk_snap(h0, 0.64)
        fc = h0 + int(L * 0.55)
        self.pk_to(h0 + 2, fc, s=0.84)                # it swells...
        self.leaves_snap(h0, 0)
        self.vine_snap(h0, VINE0)
        self.stem_snap(h0)
        self._snap(self.puddle, "scale", h0, V((1.1, 0.66, 1)))
        self._snap(self.wet_face, "scale", h0, V((1, 1, 1)))
        self.at(h0, MAXP, facing_to(MAXP, (-0.4, PY, 0)))
        self.hose_on(h0 + 1, fc - 2, V((0.05, PY - 0.45, 0.03)))
        self._split(fc, h1)                           # ...and bursts down one rib
        self.deadpan(fc + 3, h1)
        self.shot(h0, h1, (1.9, -3.3, 1.45), (1.75, -3.1, 1.4), (0.2, 1.05, 0.3), lens=22)

    def a_photo_hook(self, i, h0, h1):
        self.light(h0, 4.4, 0.24, 950, color=(1.0, 0.95, 0.86))
        self.photo(h0, h1)
