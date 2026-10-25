"""
NUCLEAR STORY set — Blender builder (see nuclear_story_spec.py). Max builds a nuclear power
station for his town: a bare tank of fuel rods that runs away, control rods that tame it, heat
that is not electricity until a turbine and generator arrive, steam that chokes the turbine until
a condenser and cooling tower close the loop, radiation until a containment dome shields it...
then the town lights up. Side-on cutaway diorama: the vessel and the containment are sliced open
along the section plane y=0, so the rods stand visible in the glowing water.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from engine import events, textures as tx, toy
from engine.backyard import _appear, _hide, _key
from engine.camera import CameraRig, facing_to
from engine.character import Character
from engine.cutaway import _grass_tuft, flow_material, key_node_value
from engine.machines import Puffs, _constant_jumps
from engine.sets.nuclear_story_spec import ACTIONS, beat_actions
from engine.sets.plane_story import arrow, label

V = Vector
R = math.radians
CORE = V((-6.0, 0.0, 0.0))          # reactor vessel axis (on the section plane)
VESSEL_R, VESSEL_Z0, VESSEL_H = 1.0, 0.3, 3.0
WATER_TOP = 3.0
ROD_TOP_OUT, ROD_TOP_IN = 4.9, 2.6  # control-rod drive height: withdrawn / inserted
TURB_Y, TURB_Z = 0.8, 1.5           # turbine + generator shaft
TURB_X0, TURB_X1 = -0.4, 2.4
GEN_X0, GEN_X1 = 2.7, 4.1
TOWER = V((9.5, 5.0, 0.0))
TOWER_H = 9.0
WORK = V((-4.2, -1.5, 0.0))         # Max's spot in front of the reactor (clear of pad, pipes, beacon)
FIN_SPOT = V((13.2, -0.8, 0.0))      # Max at the lever for the finale, the lit town behind
TOWN_AIM = V((16.2, 8.6, 1.4))
SPIN = 0.11                         # turbine revolutions per frame at full speed (fast, no strobing)
HOUSES = [(13.6, 7.0), (16.0, 7.6), (18.4, 7.0), (14.6, 10.2), (17.2, 10.6), (19.8, 9.6)]


# ------------------- small builders -------------------

def _mat(name, hexc, rough=0.5, **kw):
    return toy.material(name, toy.srgb(hexc), roughness=rough, **kw)


def glow_material(name, hexc, strength=0.0, rough=0.3):
    """Emissive material whose strength is a keyable Value node named 'glow'."""
    mat = bpy.data.materials.new(name)
    bsdf = toy._principled(mat)
    nt = mat.node_tree
    toy._set(bsdf, "Base Color", (*toy.srgb(hexc), 1))
    toy._set(bsdf, "Emission Color", (*toy.srgb(hexc), 1))
    toy._set(bsdf, "Roughness", rough)
    val = nt.nodes.new("ShaderNodeValue")
    val.name = "glow"
    val.outputs[0].default_value = strength
    nt.links.new(val.outputs[0], bsdf.inputs["Emission Strength"])
    return mat


def _bisect(obj, co, no):
    """Remove the part of a mesh behind the plane (co, no): keeps the side the normal points to."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no,
                           clear_inner=True)
    bm.to_mesh(obj.data)
    bm.free()


def half_shell(name, radius, height, thick, mat, loc, segments=48, dome=False):
    """The BACK half (y >= 0) of a thick-walled cylinder (or hemisphere dome), base at loc: a cutaway."""
    if dome:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=segments, ring_count=segments // 2,
                                             location=(0, 0, 0))
    else:
        bpy.ops.mesh.primitive_cylinder_add(vertices=segments, radius=radius, depth=height, end_fill_type="NOTHING",
                                            location=(0, 0, 0))
    obj = bpy.context.active_object
    if not dome:
        obj.data.transform(Matrix.Translation((0, 0, height / 2)))     # origin at the base
    obj.name = name
    _bisect(obj, (0, 0, 0), (0, 1, 0))
    if dome:
        _bisect(obj, (0, 0, 0), (0, 0, 1))
    sol = obj.modifiers.new("wall", "SOLIDIFY")
    sol.thickness, sol.offset, sol.use_rim = thick, -1.0, True
    toy._finish(obj, mat, subdiv=0, smooth=True)
    obj.location = loc
    return obj


def pipe(name, pts, radius, mat, parent=None):
    """Straight segments + elbow spheres through the points. Returns the segment objects."""
    segs = []
    pts = [V(p) for p in pts]
    for k in range(len(pts) - 1):
        a, b = pts[k], pts[k + 1]
        d = b - a
        seg = toy.cylinder(f"{name}_{k}", radius, d.length, (a + b) / 2, mat=mat, vertices=16)
        seg.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        segs.append(seg)
    for k, p in enumerate(pts[1:-1]):
        segs.append(toy.sphere(f"{name}_elbow{k}", radius * 1.02, p, mat=mat, subdiv=0, segments=16, rings=8))
    if parent is not None:
        for s in segs:
            toy.parent_keep(s, parent)
    return segs


def lathe(name, profile, mat, segments=64, thick=0.15):
    """Surface of revolution around Z from [(radius, z), ...] (a cooling tower)."""
    bm = bmesh.new()
    vs = [bm.verts.new((r, 0, z)) for r, z in profile]
    edges = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    bmesh.ops.spin(bm, geom=vs + edges, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=segments,
                   use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    sol = obj.modifiers.new("wall", "SOLIDIFY")
    sol.thickness, sol.offset = thick, 0.0
    toy._finish(obj, mat, subdiv=0, smooth=True)
    return obj


class Sparks:
    """A pool of small glowing particles that either FLY from a to b (neutrons, radiation) or
    PULSE in place (fission flashes). Each particle is reused only after its last trip ended."""

    def __init__(self, name, hexc, count, radius, strength):
        mat = glow_material(f"{name}_mat", hexc, strength=strength, rough=0.3)
        self.parts = []
        for i in range(count):
            sp = toy.sphere(f"{name}_p{i}", radius, (0, 0, -50), mat=mat, subdiv=1, segments=10, rings=6)
            sp.visible_shadow = False
            self.parts.append(sp)
        self.free_at = {sp.name: -10 for sp in self.parts}

    def _take(self, f0, f1):
        for sp in self.parts:
            if self.free_at[sp.name] < f0 - 2:
                self.free_at[sp.name] = f1 + 2
                return sp
        return None

    @staticmethod
    def _k(sp, f, loc, sc):
        sp.location, sp.scale = loc, (sc, sc, sc)
        sp.keyframe_insert("location", frame=f)
        sp.keyframe_insert("scale", frame=f)

    def fly(self, f0, f1, a, b, shrink=False):
        sp = self._take(f0, f1)
        if sp is None:
            return
        park = V((0, 0, -50))
        self._k(sp, f0 - 1, park, 0.01)
        self._k(sp, f0, V(a), 1.0)
        self._k(sp, f1, V(b), 0.2 if shrink else 1.0)
        self._k(sp, f1 + 1, V(b), 0.01)
        self._k(sp, f1 + 2, park, 0.01)

    def pulse(self, f0, at, life=6, peak=1.0):
        sp = self._take(f0, f0 + life)
        if sp is None:
            return
        park = V((0, 0, -50))
        self._k(sp, f0 - 1, park, 0.01)
        self._k(sp, f0, V(at), 0.25)
        self._k(sp, f0 + life // 2, V(at), peak)
        self._k(sp, f0 + life, V(at), 0.01)
        self._k(sp, f0 + life + 1, park, 0.01)

    def finish(self):
        for sp in self.parts:
            _constant_jumps(sp)


def trefoil(name, loc, size=0.4):
    """The radiation warning sign: yellow disc, three black blades and a black hub, facing -Y."""
    root = toy.empty(name, loc)
    yellow = glow_material(f"{name}_y", "#FFD21F", strength=0.6, rough=0.4)
    black = _mat(f"{name}_k", "#141414", 0.5)
    disc = toy.cylinder(f"{name}_disc", size, 0.04, (0, 0, 0), rotation=(R(90), 0, 0), mat=yellow, vertices=48)
    disc.parent = root
    disc.location = (0, 0.02, 0)
    for k in range(3):
        bm = bmesh.new()
        a0 = R(90 + 120 * k - 30)
        pts = [bm.verts.new((0, 0, 0))]
        for j in range(9):
            a = a0 + R(60) * j / 8
            pts.append(bm.verts.new((math.cos(a) * size * 0.85, 0, math.sin(a) * size * 0.85)))
        for j in range(1, len(pts) - 1):
            bm.faces.new((pts[0], pts[j], pts[j + 1]))
        me = bpy.data.meshes.new(f"{name}_blade{k}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(f"{name}_blade{k}", me)
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(black)
        ob.parent = root
        ob.location = (0, -0.01, 0)
    hub_ring = toy.cylinder(f"{name}_ring", size * 0.3, 0.05, (0, 0, 0), rotation=(R(90), 0, 0), mat=yellow, vertices=32)
    hub_ring.parent = root
    hub_ring.location = (0, -0.015, 0)
    hub = toy.cylinder(f"{name}_hub", size * 0.2, 0.06, (0, 0, 0), rotation=(R(90), 0, 0), mat=black, vertices=32)
    hub.parent = root
    hub.location = (0, -0.025, 0)
    return root


def half_cylinder_solid(name, radius, z0, z1, mat, loc):
    """A SOLID half-cylinder (y >= 0) with a flat front face on the section plane (cutaway water)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=z1 - z0, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.transform(Matrix.Translation((0, 0, (z0 + z1) / 2)))
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 1, 0),
                           clear_inner=True)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    toy._finish(obj, mat, subdiv=0, smooth=False)
    obj.location = loc
    return obj


def flash(mat, f0, f1, period=8, hi=12.0):
    """Blink an emissive 'glow' value on/off between f0 and f1 (alarm beacon)."""
    f, on = f0, True
    while f < f1:
        key_node_value(mat, "glow", f, hi if on else 0.4, "CONSTANT")
        f += period // 2
        on = not on
    key_node_value(mat, "glow", f1, 0.4, "CONSTANT")


# ------------------- the set -------------------

class NuclearStorySet:
    ACTIONS = ACTIONS
    # contacts that are part of the design (the QA flags every other intersection between objects)
    QA_ALLOW = (r"pellet|fuel\d|ctrl\d|ctrl_bar|core_water|vessel|core_pad x vessel|_elbow|blade|turb_shaft|magnet"
                r"|coil\d x gen_casing|beacon|gantry_|gauge_|needle|lamp_|bulb_|_rib|radiation_sign|cont_(liner|wall)"
                r"|condenser x (cool|feed|dead)|cool\w+ x cooling_tower|wire_\d x wire_|pylon\d_\w+ x pylon\d"
                r"|steam_pipe_\d x steam_pipe|feedwater_\d x feedwater|cool_(out|back)_\d x cool_(out|back)"
                r"|dead_end_\d x (dead|turb)|hall_floor x (gauge|lamp|dead)|house\d+ x house\d+_"
                r"|apron x |roof-1 x house\d+_roof1|pylon\d_leg|lever_base x Max")

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self.rnd = random.Random(5)
        self._world()
        self._reactor()
        self._turbine_hall()
        self._cooling()
        self._grid_and_town()
        self.max = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
        self.kids = [Character("Kid1", {"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5",
                                        "hair": "#5B3A1E", "scale": 0.6, "ponytail": True}),
                     Character("Kid2", {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B",
                                        "hair": "#2B1A10", "scale": 0.56})]
        for kid in self.kids:
            toy.hide_tree(kid.root, 1, True)
        self.max.place(1, WORK, 0)
        self.max.auto_blink(1, total + 400, seed=7)
        self.props = self._props()

    # ------------------- world -------------------

    def _world(self):
        grass = toy.noise_material("nk_grass", toy.srgb("#4C8A33"), toy.srgb("#6AA543"), scale=30, bump=0.3)
        toy.box("field", (140, 90, 0.4), (4, 25, -0.2), mat=grass, bevel=0)
        apron = toy.noise_material("nk_apron", toy.srgb("#9A9893"), toy.srgb("#B3B1AB"), scale=40, roughness=0.85,
                                   bump=0.15)
        toy.box("apron", (15.5, 3.6, 0.04), (-1.8, 0.1, 0.01), mat=apron, bevel=0)
        tuft = _grass_tuft()
        for k, (nm, x0, x1, y0, y1, dens, size) in enumerate((
                ("g_front", -16, 22, -12, -1.75, 150, 1.6),
                ("g_back", -16, 22, 2.0, 14, 110, 1.4))):
            toy.scatter(nm, x0, x1, y0, y1, tuft, dens, size=size, seed=k + 3)
        tuft.hide_render = True
        hill = _mat("nk_hill", "#5F9B45", 0.9)
        for k, (x, r) in enumerate(((-28, 16), (6, 20), (40, 18))):
            toy.sphere(f"hill{k}", r, (x, 70, -r * 0.6), scale=(1.6, 1.0, 0.7), mat=hill, subdiv=1)
        bark = toy.noise_material("nk_bark", toy.srgb("#5A4632"), toy.srgb("#74604A"), scale=12, bump=0.6)
        leaf = toy.noise_material("nk_leaf", toy.srgb("#3D6B2A"), toy.srgb("#5E8C38"), scale=6, bump=0.6)
        for k, (x, y, s) in enumerate(((-12.5, 6, 1.1), (-10, 11, 0.9), (5.5, 11, 1.0), (21, 6, 1.2), (12, 13, 0.9))):
            h = 2.8 * s
            toy.cylinder(f"trunk{k}", 0.22 * s, h, (x, y, h / 2), mat=bark, vertices=10)
            rnd = random.Random(k)
            for j in range(6):
                toy.sphere(f"leaf{k}_{j}", rnd.uniform(0.7, 1.0) * s,
                           (x + rnd.uniform(-1, 1) * s, y + rnd.uniform(-0.7, 0.7) * s, h + rnd.uniform(0, 1.2) * s),
                           mat=leaf, subdiv=1)
        cloud = toy.material("nk_cloud", (1, 1, 1), roughness=0.95)
        rnd = random.Random(3)
        for i in range(7):
            root = toy.empty(f"cloud_{i}", (rnd.uniform(-40, 50), rnd.uniform(55, 80), rnd.uniform(15, 26)))
            for k in range(5):
                p = toy.sphere(f"cloud_{i}_{k}", rnd.uniform(2.4, 3.6), (0, 0, 0), scale=(1.4, 1.0, 0.65), mat=cloud,
                               subdiv=1)
                p.parent = root
                p.location = (rnd.uniform(-4, 4), rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.8))
                p.visible_shadow = False
            root.keyframe_insert("location", frame=1)
            root.location.x += 25
            root.keyframe_insert("location", frame=6000)
            toy.set_interpolation(root, "location", (1,), "LINEAR")

    # ------------------- reactor -------------------

    def _reactor(self):
        concrete = toy.noise_material("nk_concrete", toy.srgb("#A7A49D"), toy.srgb("#C3C0B8"), scale=50,
                                      roughness=0.9, bump=0.2)
        steel = tx.metal("nk_vessel", "#8E959C", 0.32)
        self.pad = toy.box("core_pad", (3.0, 2.6, 0.3), (CORE.x, 0.3, 0.15), mat=concrete, bevel=0.02)
        self.vessel = half_shell("vessel", VESSEL_R, VESSEL_H, 0.09, steel, CORE + V((0, 0, VESSEL_Z0 + 0.012)))
        bottom = half_cylinder_solid("vessel_floor", VESSEL_R - 0.02, VESSEL_Z0 + 0.012, VESSEL_Z0 + 0.1, steel,
                                     CORE + V((0, 0.003, 0)))       # floor sits ON the pad, never flush with it
        # the water: Cherenkov blue, its glow keyed with the reaction
        self.water_mat = glow_material("core_water", "#1E5FC8", strength=0.0, rough=0.08)
        toy._set(toy._principled(self.water_mat), "Emission Color", (*toy.srgb("#2E8BFF"), 1))
        self.water = half_cylinder_solid("core_water", VESSEL_R - 0.1, VESSEL_Z0 + 0.13, WATER_TOP, self.water_mat,
                                         CORE + V((0, 0.006, 0)))   # 3 cm above the floor: no z-fighting
        # fuel rods (cut lengthwise by the section plane, so half of each stands proud of the water)
        clad = tx.metal("nk_clad", "#B9BEC4", 0.28)
        self.fuel = []
        self.fuel_x = [CORE.x + dx for dx in (-0.6, -0.36, -0.12, 0.12, 0.36, 0.6)]
        for k, x in enumerate(self.fuel_x):
            self.fuel.append(toy.cylinder(f"fuel{k}", 0.06, 1.8, (x, 0.0, 1.5), mat=clad, vertices=16))
        self.pellet_mat = glow_material("nk_pellet", "#7FCF5A", strength=0.0)
        for k, rod in enumerate(self.fuel):
            for j in range(6):
                toy.cylinder(f"pellet{k}_{j}", 0.045, 0.12, (rod.location.x, -0.02, 0.85 + 0.26 * j),
                             mat=self.pellet_mat, vertices=12).parent = None
        # control rods on a drive (withdrawn = above the water)
        absorber = _mat("nk_absorber", "#2A2D33", 0.4, metallic=0.6)
        self.drive = toy.empty("rod_drive", (CORE.x, 0.0, ROD_TOP_OUT))
        self.ctrl = []
        self.ctrl_x = [CORE.x + dx for dx in (-0.48, -0.24, 0.0, 0.24, 0.48)]
        for k, dx in enumerate((-0.48, -0.24, 0.0, 0.24, 0.48)):
            r = toy.box(f"ctrl{k}", (0.07, 0.07, 1.8), (dx, -0.01, -0.9), mat=absorber, bevel=0.01)
            r.parent = self.drive
            r.location = (dx, -0.01, -0.9)
            self.ctrl.append(r)
        yellow = tx.paint("nk_gantry", "#F2B230", 0.35, coat=0.3)
        bar = toy.box("ctrl_bar", (1.3, 0.16, 0.14), (0, 0, 0.07), mat=yellow, bevel=0.02)
        bar.parent = self.drive
        bar.location = (0, 0, 0.07)
        self.gantry = [toy.box("gantry_postL", (0.16, 0.16, 5.2), (CORE.x - 1.25, 0.25, 2.9), mat=yellow, bevel=0.02),
                       toy.box("gantry_postR", (0.16, 0.16, 5.2), (CORE.x + 1.25, 0.25, 2.9), mat=yellow, bevel=0.02),
                       toy.box("gantry_beam", (2.7, 0.2, 0.22), (CORE.x, 0.25, 5.45), mat=yellow, bevel=0.02),
                       toy.box("gantry_motor", (0.5, 0.4, 0.35), (CORE.x, 0.25, 5.72), mat=tx.paint("nk_motor", "#3A5A8C", 0.4))]
        for o in self.gantry + [self.drive]:
            toy.hide_tree(o, 1, True)
        # glowing particles of the chain reaction (neutrons + fission flashes) and the radiation
        self.neutrons = Sparks("neutron", "#8FE3FF", 70, 0.035, 9.0)
        self.fissions = Sparks("fission", "#FFB347", 60, 0.09, 10.0)
        self.rays = Sparks("ray", "#D7FF3C", 70, 0.045, 7.0)
        self.sign = trefoil("radiation_sign", (CORE.x + 0.2, -0.9, 3.85), size=0.42)   # above the core, in the Geiger shot
        toy.hide_tree(self.sign, 1, True)
        # alarm beacon
        self.beacon_mat = glow_material("nk_beacon", "#FF2A1A", strength=0.4, rough=0.2)
        toy.cylinder("beacon_post", 0.05, 2.0, (CORE.x + 1.55, -0.55, 1.3), mat=tx.metal("nk_post", "#9AA0A6"))
        toy.sphere("beacon", 0.17, (CORE.x + 1.55, -0.55, 2.38), mat=self.beacon_mat, subdiv=1)
        ld = bpy.data.lights.new("alarm_light", "POINT")
        ld.color, ld.energy, ld.shadow_soft_size = (1.0, 0.15, 0.08), 0.0, 0.3
        self.alarm = bpy.data.objects.new("alarm_light", ld)
        self.alarm.location = (CORE.x + 1.4, -1.2, 2.6)
        bpy.context.scene.collection.objects.link(self.alarm)
        ld.keyframe_insert("energy", frame=1)
        key_node_value(self.beacon_mat, "glow", 1, 0.4, "CONSTANT")
        # containment building (rises at the end): steel liner + metre-thick concrete, cut open
        liner = tx.metal("nk_liner", "#9AA3AA", 0.3)
        wall = toy.noise_material("nk_containment", toy.srgb("#C9C6BE"), toy.srgb("#B4B0A8"), scale=30,
                                  roughness=0.85, bump=0.25)
        self.contain_root = toy.empty("containment", CORE)
        parts = [half_shell("cont_wall", 3.0, 5.0, 0.75, wall, (0, 0, 0)),
                 half_shell("cont_liner", 2.28, 5.0, 0.05, liner, (0, 0, 0)),
                 half_shell("cont_dome", 3.0, 0, 0.75, wall, (0, 0, 5.0), dome=True)]
        for p in parts:
            p.parent = self.contain_root
        self.contain_parts = parts
        toy.hide_tree(self.contain_root, 1, True)

    # ------------------- turbine hall -------------------

    def _turbine_hall(self):
        concrete = toy.noise_material("nk_concrete", toy.srgb("#A7A49D"), toy.srgb("#C3C0B8"), scale=50)
        steel = tx.metal("nk_casing", "#7E8790", 0.3)
        casing_paint = tx.paint("nk_turb_paint", "#5D8C6C", 0.5, coat=0.0)
        self.hall = [toy.box("hall_floor", (6.6, 2.4, 0.3), (1.8, 0.6, 0.15), mat=concrete, bevel=0.02)]
        L = TURB_X1 - TURB_X0
        casing = half_shell("turb_casing", 0.85, L, 0.06, casing_paint, (0, 0, 0))
        casing.rotation_euler = (0, R(90), 0)
        casing.location = (TURB_X0, TURB_Y, TURB_Z)
        self.rotor = toy.empty("turb_rotor", (TURB_X0, TURB_Y, TURB_Z))
        blade = tx.metal("nk_blade", "#C9CED4", 0.22)
        shaft = toy.cylinder("turb_shaft", 0.09, GEN_X1 - TURB_X0 + 0.2, (0, 0, 0), rotation=(0, R(90), 0), mat=steel)
        shaft.parent = self.rotor
        shaft.location = ((GEN_X1 - TURB_X0) / 2, 0, 0)
        for s, (x, r) in enumerate(((0.5, 0.45), (1.3, 0.6), (2.1, 0.75))):
            for k in range(14):
                a = 2 * math.pi * k / 14
                b = toy.box(f"blade{s}_{k}", (0.05, 0.12, r), (0, 0, 0), mat=blade, bevel=0.005)
                b.parent = self.rotor
                b.location = (x, math.sin(a) * r / 2, math.cos(a) * r / 2)
                b.rotation_euler = (-a, R(18), 0)
        gcase = half_shell("gen_casing", 0.78, GEN_X1 - GEN_X0, 0.08, tx.paint("nk_gen", "#2F6FB0", 0.35, coat=0.4),
                           (0, 0, 0))
        gcase.rotation_euler = (0, R(90), 0)
        gcase.location = (GEN_X0, TURB_Y, TURB_Z)
        copper = tx.metal("nk_copper", "#C77B3C", 0.3)
        for k in range(5):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.5, minor_radius=0.05,
                                             location=(GEN_X0 + 0.2 + 0.25 * k, TURB_Y + 0.12, TURB_Z),
                                             rotation=(0, R(90), 0))
            coil = bpy.context.active_object
            coil.name = f"coil{k}"
            toy._finish(coil, copper, subdiv=0)
        north, south = _mat("nk_mag_n", "#D8342C", 0.4), _mat("nk_mag_s", "#2E5FB8", 0.4)
        for k, (m, z) in enumerate(((north, 0.17), (south, -0.17))):
            mag = toy.box(f"magnet{k}", (GEN_X1 - GEN_X0 - 0.3, 0.3, 0.34), (0, 0, 0), mat=m, bevel=0.03)
            mag.parent = self.rotor
            mag.location = ((GEN_X0 + GEN_X1) / 2 - TURB_X0, 0, z)
        self.turbine_parts = [casing, gcase, self.rotor] + [o for o in bpy.data.objects if o.name.startswith("coil")]
        # steam line reactor → turbine (white stripes flow when the steam runs)
        self.steam_mat = flow_material("nk_steam", 1.0, speed=2.4, base="#D9E4EA", stripe="#FFFFFF")
        self.steam_pipe = pipe("steam_pipe", [(CORE.x + 0.35, 0.62, WATER_TOP - 0.2), (CORE.x + 0.35, 0.62, 3.8),
                                              (-0.9, 0.62, 3.8), (-0.9, TURB_Y, 3.8), (-0.9, TURB_Y, TURB_Z),
                                              (TURB_X0 + 0.05, TURB_Y, TURB_Z)], 0.15, self.steam_mat)   # behind the gantry posts
        # turbine exhaust: a dead end before the condenser exists
        self.dead_end = pipe("dead_end", [(1.0, TURB_Y, TURB_Z - 0.7), (1.0, TURB_Y, 0.45)], 0.16, steel)
        # a BIG pressure gauge at the front: green / yellow / red zones, thick needle
        G = V((0.35, -0.55, 2.55))
        toy.cylinder("gauge_post", 0.05, G.z - 0.3, (G.x, G.y + 0.08, (G.z + 0.3) / 2), mat=tx.metal("nk_post2", "#9AA0A6"))
        toy.cylinder("gauge_face", 0.46, 0.08, G + V((0, 0.06, 0)), rotation=(R(90), 0, 0), mat=_mat("nk_gauge", "#F7F4EC", 0.4),
                     vertices=48)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.47, minor_radius=0.04, location=G + V((0, 0.02, 0)),
                                         rotation=(R(90), 0, 0))
        rim = bpy.context.active_object
        rim.name = "gauge_rim"
        toy._finish(rim, tx.metal("nk_rim", "#2C2F33", 0.3), subdiv=0)
        zones = {"g": _mat("nk_zone_g", "#3DBE6E", 0.4), "y": _mat("nk_zone_y", "#F2C230", 0.4),
                 "r": _mat("nk_zone_r", "#E8322A", 0.4)}
        for k in range(15):
            a = -120 + 240 * k / 14
            zone = "g" if a < 20 else ("y" if a < 70 else "r")
            t = toy.box(f"gauge_tick{k}", (0.11, 0.02, 0.07), (0, 0, 0), mat=zones[zone], bevel=0.005)
            t.location = G + V((math.sin(R(a)) * 0.36, -0.005, math.cos(R(a)) * 0.36))
            t.rotation_euler = (0, R(a) + R(90), 0)
        self.needle = toy.empty("gauge_needle", G + V((0, -0.03, 0)))
        nd = toy.box("needle", (0.05, 0.03, 0.34), (0, 0, 0.15), mat=_mat("nk_needle", "#1A1A1A", 0.4), bevel=0.01)
        nd.parent = self.needle
        nd.location = (0, 0, 0.15)
        tip = toy.box("needle_tip", (0.05, 0.03, 0.08), (0, 0, 0.3), mat=zones["r"], bevel=0.01)
        tip.parent = self.needle
        tip.location = (0, 0, 0.3)
        hub = toy.cylinder("needle_hub", 0.06, 0.05, (0, 0, 0), rotation=(R(90), 0, 0), mat=_mat("nk_needle", "#1A1A1A"))
        hub.parent = self.needle
        hub.location = (0, -0.01, 0)
        self.needle.rotation_euler = (0, R(-100), 0)
        self.gauge_center = G
        # a lamp on a stand wired to the generator (lights up when the generator runs)
        self.lamp_bulb, self.lamp_mat, self.lamp_light = self._bulb("lamp")
        LAMP = V((5.0, -0.45, 1.7))
        toy.cylinder("lamp_post", 0.04, LAMP.z - 0.25, (LAMP.x, LAMP.y, (LAMP.z - 0.25) / 2 + 0.03),
                     mat=tx.metal("nk_lamp_post", "#3A3D42", 0.4))
        self.lamp_bulb.location = LAMP
        pipe("lamp_wire", [(GEN_X1 - 0.1, TURB_Y - 0.4, TURB_Z - 0.4), (4.6, -0.2, 0.9), (LAMP.x, LAMP.y, 1.4)], 0.02,
             _mat("nk_cord", "#1A1A1A", 0.6))
        self.turbine_parts += [o for o in bpy.data.objects if o.parent is None and
                               o.name.startswith(("gauge_", "lamp_post", "lamp_globe", "lamp_wire"))]
        for o in self.steam_pipe + self.turbine_parts + self.dead_end:
            toy.hide_tree(o, 1, True)

    # ------------------- condenser + cooling tower -------------------

    def _cooling(self):
        steel = tx.metal("nk_cond", "#8C949B", 0.3)
        self.condenser = toy.box("condenser", (2.4, 1.1, 0.28), (1.0, TURB_Y, 0.45), mat=steel, bevel=0.04)   # clear of the casing
        self.cold_mat = flow_material("nk_cold", 1.0, speed=1.4, base="#2F8FE0", stripe="#BFE9FF")
        self.loop_pipes = (pipe("cool_out", [(2.2, 1.2, 0.5), (7.0, 2.4, 0.5), (7.0, 3.6, 0.5)], 0.13, self.cold_mat)
                           + pipe("cool_back", [(7.7, 3.2, 0.5), (7.7, 1.8, 0.5), (2.2, 0.6, 0.5)], 0.13, self.cold_mat)
                           + pipe("feedwater", [(-0.2, 0.55, 0.5), (CORE.x + 1.6, 0.55, 0.5),
                                                (CORE.x + 0.8, 0.55, 0.62)], 0.12, self.cold_mat))   # parallel, never crossing
        tower_mat = toy.noise_material("nk_tower", toy.srgb("#D8D5CE"), toy.srgb("#BDB9B0"), scale=6, roughness=0.9,
                                       bump=0.3)
        self.tower = lathe("cooling_tower", [(3.3, 0.0), (2.9, 2.0), (2.25, 5.0), (2.0, 7.0), (2.15, 8.3),
                                             (2.35, TOWER_H)], tower_mat)
        self.tower.location = TOWER
        for o in [self.condenser, self.tower] + self.loop_pipes:
            toy.hide_tree(o, 1, True)

    # ------------------- power lines + town -------------------

    def _grid_and_town(self):
        steel = tx.metal("nk_pylon", "#8A9097", 0.4)
        self.wire_mat = flow_material("nk_power", 1.0, speed=6.0, base="#2B2B2B", stripe="#FFE066")
        arms = []
        for k, (x, y) in enumerate(((6.0, 0.9), (12.8, 2.0))):          # clear of the pipes and the tower
            for sx in (-0.5, 0.5):
                toy.cylinder(f"pylon{k}_leg{sx}", 0.06, 6.0, (x + sx * 0.6, y, 3.0), rotation=(0, R(-8 * sx * 2), 0),
                             mat=steel, vertices=8)
            toy.box(f"pylon{k}_arm", (2.2, 0.12, 0.12), (x, y, 5.8), mat=steel, bevel=0)
            arms.append((x, y - 0.14, 6.08))
        self.wires = pipe("wire", [(GEN_X1 - 0.2, TURB_Y, TURB_Z + 0.8), arms[0], arms[1], (14.6, 6.4, 3.0)], 0.025,
                          self.wire_mat)
        wall = tx.planks("nk_house", "#F2EEE6", "#E8E2D6", width=0.2, across="z", along="xy", lap=True, seam_dark=0.22)
        roof = tx.shingles("nk_roof", "#B8532F", "#7E3520")
        self.window_mats = []
        for k, (x, y) in enumerate(HOUSES):
            toy.box(f"house{k}", (1.8, 1.6, 1.4), (x, y, 0.7), mat=wall, bevel=0.03)
            for s in (-1, 1):
                toy.box(f"house{k}_roof{s}", (2.0, 1.0, 0.1), (x, y + 0.38 * s, 1.6), mat=roof, bevel=0.02,
                        rotation=(R(-35 * s), 0, 0))
            wm = glow_material(f"win{k}", "#FFD27A", strength=0.0, rough=0.2)
            self.window_mats.append(wm)
            for j, dx in enumerate((-0.45, 0.45)):
                toy.box(f"house{k}_win{j}", (0.46, 0.04, 0.5), (x + dx, y - 0.81, 0.8), mat=wm, bevel=0.01)

    # ------------------- props -------------------

    def _bulb(self, name):
        """A light bulb: glass globe (glows on cue), neck, ribbed screw base, plus its own light."""
        glass = glow_material(f"{name}_glass", "#FFF4C8", strength=0.0, rough=0.08)
        toy._set(toy._principled(glass), "Emission Color", (*toy.srgb("#FFD45A"), 1))
        bulb = toy.sphere(f"{name}_globe", 0.15, (0, 0, 0), scale=(1, 1, 1.1), mat=glass, subdiv=1)
        metal = tx.metal(f"{name}_base", "#C9CED4", 0.25)
        neck = toy.cylinder(f"{name}_neck", 0.075, 0.08, (0, 0, -0.16), mat=glass, vertices=24)
        neck.parent = bulb
        neck.location = (0, 0, -0.16)
        for j in range(3):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.07, minor_radius=0.015, location=(0, 0, 0))
            rib = bpy.context.active_object
            rib.name = f"{name}_rib{j}"
            toy._finish(rib, metal, subdiv=0)
            rib.parent = bulb
            rib.location = (0, 0, -0.22 - 0.035 * j)
        cap = toy.sphere(f"{name}_cap", 0.05, (0, 0, 0), scale=(1, 1, 0.6), mat=_mat(f"{name}_tip", "#2A2A2A"), subdiv=0)
        cap.parent = bulb
        cap.location = (0, 0, -0.33)
        ld = bpy.data.lights.new(f"{name}_light", "POINT")
        ld.color, ld.energy, ld.shadow_soft_size = (1.0, 0.85, 0.5), 0.0, 0.1
        light = bpy.data.objects.new(f"{name}_light", ld)
        bpy.context.scene.collection.objects.link(light)
        light.parent = bulb
        ld.keyframe_insert("energy", frame=1)
        return bulb, glass, light

    def light_bulb(self, mat, light, f):
        key_node_value(mat, "glow", f - 1, 0.0)
        key_node_value(mat, "glow", f + 3, 16.0)
        light.data.energy = 0
        light.data.keyframe_insert("energy", frame=f - 1)
        light.data.energy = 120
        light.data.keyframe_insert("energy", frame=f + 3)

    def _props(self):
        bulb, self.bulb_mat, self.bulb_light = self._bulb("bulb")
        geiger = toy.box("geiger", (0.26, 0.12, 0.16), (0, 0, 0), mat=tx.paint("nk_geiger", "#F2C230", 0.4), bevel=0.02)
        dial = toy.cylinder("geiger_dial", 0.035, 0.01, (0, -0.045, 0.01), rotation=(R(90), 0, 0),
                            mat=_mat("nk_dial", "#FFFFFF", 0.4))
        dial.parent = geiger
        dial.location = (0, -0.045, 0.01)
        lever = toy.box("lever_base", (0.4, 0.3, 0.9), (FIN_SPOT.x + 0.55, FIN_SPOT.y, 0.45),
                        mat=tx.paint("nk_lever", "#3A5A8C", 0.4))
        self.lever = toy.empty("lever_pivot", (FIN_SPOT.x + 0.55, FIN_SPOT.y - 0.18, 0.75))
        h = toy.box("lever_handle", (0.06, 0.06, 0.5), (0, 0, 0.25), mat=_mat("nk_lever_red", "#D8342C", 0.4))
        h.parent = self.lever
        h.location = (0, 0, 0.25)
        self.lever.rotation_euler = (R(-35), 0, 0)
        led = glow_material("nk_led", "#FF3B30", strength=0.0, rough=0.2)
        ledo = toy.sphere("geiger_led", 0.025, (0, 0, 0), mat=led, subdiv=0)
        ledo.parent = geiger
        ledo.location = (0.08, -0.06, 0.05)
        self.led_mat = led
        for o in (bulb, geiger, lever, self.lever):
            toy.hide_tree(o, 1, True)
        return {"bulb": bulb, "geiger": geiger, "lever": [lever, self.lever]}

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
        for pool in (self.neutrons, self.fissions, self.rays):
            pool.finish()
        self.rig.build()

    # ------------------- helpers -------------------

    def at(self, f, spot, face_to=None):
        # (no hide_tree(max) here: it would also un-hide every prop parented to his hands)
        self.max.cut_place(f, spot, facing_to(spot, face_to) if face_to is not None else 0)
        self.max.pose(f + 6)

    def light(self, f, sun_e=4.2, bg_v=0.22, fill_e=900):
        """Change the lighting AT frame f (a cut). The previous state is held up to f-1, so the
        lighting never drifts slowly between two far-apart keys across the whole film."""
        tree = self.bg.node.id_data                     # the world's node tree owns the socket's curve
        chans = [(self.sun.data, self.sun.data, "energy", sun_e), (self.fill.data, self.fill.data, "energy", fill_e),
                 (tree, self.bg, "default_value", bg_v)]
        for owner, holder, path, new in chans:
            curves = [fc for fc in toy.fcurves(owner) if fc.data_path.endswith(path)]
            old = curves[0].evaluate(f - 1) if curves else getattr(holder, path)
            setattr(holder, path, old)
            holder.keyframe_insert(path, frame=f - 1)
            for fc in toy.fcurves(owner):
                if fc.data_path.endswith(path):
                    for kp in fc.keyframe_points:
                        if int(round(kp.co.x)) == f - 1:
                            toy.set_key_interpolation(owner, fc, kp, "CONSTANT")
            setattr(holder, path, new)
            holder.keyframe_insert(path, frame=f)

    def glow(self, f, water, pellets=None):
        key_node_value(self.water_mat, "glow", f, water)
        key_node_value(self.pellet_mat, "glow", f, water * 0.6 if pellets is None else pellets)

    def rods(self, f, top):
        _key(self.drive, f, location=V((CORE.x, 0.0, top)))

    def spin(self, f0, f_full, f1):
        """Rotor: hold at f0, spin up to full speed at f_full, then steady until f1."""
        toy.key_hold(self.rotor, "rotation_euler", f0)
        v = toy.value_at(self.rotor, "rotation_euler", f0)[0]
        v += 2 * math.pi * SPIN * (f_full - f0) / 2
        self.rotor.rotation_euler = (v, 0, 0)
        self.rotor.keyframe_insert("rotation_euler", frame=f_full)
        self.rotor.rotation_euler = (v + 2 * math.pi * SPIN * (f1 - f_full), 0, 0)
        self.rotor.keyframe_insert("rotation_euler", frame=f1)
        toy.set_interpolation(self.rotor, "rotation_euler", (f_full,), "LINEAR")

    def spin_on(self, f0, f1):
        """Keep the rotor turning at full speed from its last key (f0-1) through f1."""
        v = toy.value_at(self.rotor, "rotation_euler", f0 - 1)[0]
        self.rotor.rotation_euler = (v + 2 * math.pi * SPIN * (f1 - f0 + 1), 0, 0)
        self.rotor.keyframe_insert("rotation_euler", frame=f1)
        toy.set_interpolation(self.rotor, "rotation_euler", (f0 - 1,), "LINEAR")

    def boil(self, f0, f1, name, rate=2, size=0.05):
        rnd = random.Random(len(name))
        Puffs(f"{name}_bubbles", "#EAF7FF", count=34, size=size, seed=len(name)).emit(
            range(f0, f1, rate), lambda f: (CORE.x + rnd.uniform(-0.75, 0.75), -0.06, rnd.uniform(0.6, 2.6)),
            rise=0.5, life=12, drift=0.05)

    def steam_burst(self, f0, f1, name, at=None, rate=3, size=0.3, rise=1.6):
        at = V(at or (CORE.x, 0.3, WATER_TOP + 0.4))
        Puffs(name, "#F4F4F4", count=18, size=size, seed=len(name) + 1).emit(
            range(f0, f1, rate), lambda f: at, rise=rise, life=24, drift=0.5)

    def chain(self, f0, f1, rate0, rate1, absorb0=0.0, absorb1=0.0, seed=1):
        """Show the chain reaction: neutrons fly between fuel rods, each landing makes a fission flash.
        rate = hops per frame (linear from rate0 to rate1); absorb = share of neutrons swallowed by
        the control rods (they end inside a dark rod, no flash)."""
        rnd = random.Random(seed)
        acc, y = 0.0, -0.11
        for f in range(f0, f1):
            t = (f - f0) / max(1, f1 - f0)
            acc += rate0 + (rate1 - rate0) * t
            while acc >= 1.0:
                acc -= 1.0
                i = rnd.randrange(len(self.fuel_x))
                za = rnd.uniform(0.75, 2.25)
                a = V((self.fuel_x[i], y, za))
                if rnd.random() < absorb0 + (absorb1 - absorb0) * t:
                    cx = min(self.ctrl_x, key=lambda x: abs(x - a.x) + rnd.random() * 0.3)
                    self.neutrons.fly(f, f + 4, a, V((cx, y, za + rnd.uniform(-0.25, 0.25))), shrink=True)
                    continue
                j = min(len(self.fuel_x) - 1, max(0, i + rnd.choice((-2, -1, 1, 2))))
                if j == i:
                    j = (i + 1) % len(self.fuel_x)
                b = V((self.fuel_x[j], y, min(2.3, max(0.7, za + rnd.uniform(-0.4, 0.4)))))
                hop = rnd.randint(4, 6)
                self.neutrons.fly(f, f + hop, a, b)
                self.fissions.pulse(f + hop, b, life=7, peak=rnd.uniform(0.8, 1.3))

    def radiation(self, f0, f1, rate, reach_fn, seed=2):
        """Radiation streaming out of the core: particles fly outward, mostly toward the viewer.
        reach_fn(frame) → how far they get (a wall stops them)."""
        rnd = random.Random(seed)
        acc = 0.0
        for f in range(f0, f1):
            acc += rate
            while acc >= 1.0:
                acc -= 1.0
                a = CORE + V((rnd.uniform(-0.5, 0.5), -0.12, rnd.uniform(0.8, 2.4)))
                ang = R(rnd.uniform(-170, -10))
                d = V((math.cos(ang), math.sin(ang), rnd.uniform(-0.25, 0.35))).normalized()
                reach = reach_fn(f)
                self.rays.fly(f, f + int(6 + reach * 2.2), a, a + d * reach, shrink=True)

    def cower(self, f0, f1):
        """Hands over the head, hunched, peeking: a comic 'take cover' that stays on his feet."""
        m = self.max
        m.pose(f0 + 4, shoulderL=(-165, -25, 0), shoulderR=(-165, 25, 0), spine=(16, 0, 0), head=(18, 0, 0))
        k, f = 0, f0 + 8
        while f < f1 - 4:                                     # trembling
            m.pose(f, shoulderL=(-165, -25, 0), shoulderR=(-165, 25, 0), spine=(16, 0, 3 if k % 2 else -3),
                   head=(18, 0, 4 if k % 2 else -4))
            f += 5
            k += 1
        m.brows(f0 + 4, 1.0)
        m.key("mouth", f0 + 4, scale=(1.1, 0.6, 2.4))

    def scratch_head(self, f0, f1):
        m = self.max
        m.pose(f0 + 4, shoulderR=(-25, 140, 0), head=(0, 14, 0))
        m.pose(f1 - 4, shoulderR=(-25, 150, 0), head=(0, 10, 0))
        m.brows(f0 + 4, 0.9)
        m.brows(f1, 0.0)
        m.pose(f1)

    def cover_ears(self, f0, f1):
        m = self.max
        m.pose(f0 + 4, shoulderL=(-20, -150, 0), shoulderR=(-20, 150, 0), head=(-6, 0, 0))
        m.pose(f1 - 3, shoulderL=(-20, -150, 0), shoulderR=(-20, 150, 0), head=(-6, 0, 6))
        m.key("mouth", f0 + 4, scale=(1.1, 0.6, 2.2))
        m.brows(f0 + 4, 1.0)
        m.brows(f1, 0.0)
        m.pose(f1)

    def show(self, objs, f, pop=True):
        for k, o in enumerate(objs):
            toy.hide_tree(o, f + 2 * k, False)
            if pop:
                fin = V(o.scale)
                _key(o, f + 2 * k, scale=fin * 0.01)
                _key(o, f + 2 * k + 4, scale=fin * 1.08)
                _key(o, f + 2 * k + 6, scale=fin)

    # ------------------- the ladder -------------------

    def a_build_core(self, i, b, e):
        L = e - b
        self.light(b)
        self.glow(b, 0.0)
        self.at(b, WORK, (CORE.x, 0, 0))
        drop = b + int(L * 0.25)
        for k, rod in enumerate(self.fuel):                         # rods lowered in one by one
            f = drop + 4 * k
            _key(rod, b, location=V((rod.location.x, 0.0, 4.2)))
            _key(rod, f, location=V((rod.location.x, 0.0, 4.2)))
            _key(rod, f + 10, location=V((rod.location.x, 0.0, 1.5)))
            events.add(f + 10, "clink", gain=0.6)
        pel = [o for o in bpy.data.objects if o.name.startswith("pellet")]
        for o in pel:
            _hide(o, 0, True)
            _hide(o, drop + 34, False)
        self.max.point(drop, drop + 30, hand="R", up_deg=30, side_deg=-20)
        self.glow(drop + 30, 0.0)
        self.glow(e - 6, 0.55)                                      # the blue glow appears
        self.chain(drop + 36, e + 1, 0.15, 0.6, seed=3)              # ...and atoms start splitting
        label("FUEL RODS", (CORE.x - 1.25, -0.4, 2.75), drop + 12, e, size=0.24, tilt=-5)
        label("WATER", (CORE.x + 0.1, -0.4, 3.35), drop + 30, e, size=0.22, tilt=5, color="#5EC8FF", outline="#0A2A3A")
        self.max.turn(e - 16, 0, frames=6)
        self.max.pose(e - 10, shoulderL=(-90, 0, 20))              # thumbs up
        self.max.smile(e - 10, big=True)
        self.rig.shot(b, e, cam_from=(-3.4, -6.4, 2.6), cam_to=(-3.8, -5.8, 2.4), aim_from=(-5.6, 0.2, 1.7),
                      aim_to=(-5.6, 0.2, 1.8), lens=24, fstop=8.0)

    def a_chain(self, i, b, e):
        L = e - b
        card_mat = _mat("nk_card", "#14324A", 0.6)
        toy._set(card_mat.node_tree.nodes.get("Principled BSDF"), "Emission Color", (*toy.srgb("#14324A"), 1))
        toy._set(card_mat.node_tree.nodes.get("Principled BSDF"), "Emission Strength", 0.6)
        c = V((CORE.x, -2.6, 2.6))
        card = toy.box("chain_card", (3.0, 0.04, 3.2), c + V((0, 0.12, 0)), mat=card_mat, bevel=0.12)
        card.visible_shadow = False
        _appear(card, b + 2, frames=8)
        _hide(card, e, True)
        atom_m = glow_material("nk_atom", "#6FDB5B", strength=0.6)
        neut_m = glow_material("nk_neutron", "#7FD3FF", strength=3.0)
        heat_m = glow_material("nk_heat", "#FF9A3C", strength=4.0)
        t0 = b + 10
        hit = t0 + int(L * 0.18)
        a0 = c + V((-0.9, -0.05, 0.9))
        atoms2 = [c + V((0.7, -0.05, 1.3)), c + V((0.8, -0.05, 0.3)), c + V((0.4, -0.05, -0.7))]

        def sphere(nm, r, at, m, f_on, f_off):
            s = toy.sphere(nm, r, at, mat=m, subdiv=1)
            s.visible_shadow = False
            _hide(s, 0, True)
            _hide(s, f_on, False)
            _hide(s, f_off, True)
            return s

        n0 = sphere("neutron0", 0.07, a0 + V((-0.45, 0, 0.45)), neut_m, t0, hit)
        _key(n0, t0, location=a0 + V((-0.45, 0, 0.45)))
        _key(n0, hit, location=a0)
        big = sphere("atom0", 0.24, a0, atom_m, b + 8, hit + 1)
        for k, d in enumerate((V((-0.35, 0, -0.4)), V((0.25, 0, 0.45)))):     # the two fragments fly apart
            frag = sphere(f"frag{k}", 0.17, a0, atom_m, hit + 1, e)
            _key(frag, hit + 1, location=a0)
            _key(frag, hit + 14, location=a0 + d)
        flare = sphere("heat0", 0.3, a0, heat_m, hit + 1, hit + 10)
        _key(flare, hit + 1, scale=V((0.2, 0.2, 0.2)))
        _key(flare, hit + 9, scale=V((1.6, 1.6, 1.6)))
        hit2 = hit + int(L * 0.25)
        for k, tgt in enumerate(atoms2):
            sphere(f"atom{k + 1}", 0.24, tgt, atom_m, b + 12, hit2 + 1)
            n = sphere(f"neutron{k + 1}", 0.07, a0, neut_m, hit + 2, hit2)
            _key(n, hit + 2, location=a0)
            _key(n, hit2, location=tgt)
            for j, d in enumerate((V((0.25, 0, 0.3)), V((0.3, 0, -0.3)))):
                fr = sphere(f"frag{k}_{j}", 0.17, tgt, atom_m, hit2 + 1, e)
                _key(fr, hit2 + 1, location=tgt)
                _key(fr, hit2 + 12, location=tgt + d)
            fl = sphere(f"heat{k + 1}", 0.3, tgt, heat_m, hit2 + 1, hit2 + 10)
            _key(fl, hit2 + 1, scale=V((0.2, 0.2, 0.2)))
            _key(fl, hit2 + 9, scale=V((1.5, 1.5, 1.5)))
        events.add(hit, "pop", gain=0.6)
        events.add(hit2, "pop", gain=0.6)
        label("NEUTRON", a0 + V((0.05, -0.08, 0.62)), t0 + 2, hit + 20, size=0.18, tilt=-5, color="#7FD3FF",
              outline="#0A2A3A")
        label("URANIUM", a0 + V((0.1, -0.08, -0.55)), b + 12, e, size=0.18, tilt=4, color="#6FDB5B", outline="#0E2A0A")
        label("HEAT", c + V((-0.2, -0.08, -1.25)), hit + 4, e, size=0.24, tilt=-4, color="#FF9A3C")
        self.rig.shot(b, e, cam_from=(CORE.x, -7.2, 2.7), cam_to=(CORE.x + 0.2, -6.8, 2.7), aim_from=c,
                      aim_to=c, lens=30, fstop=8.0, cut=True)

    def a_fail_runaway(self, i, b, e):
        L = e - b
        hot, boil0, burst = b + int(L * 0.15), b + int(L * 0.3), b + int(L * 0.5)
        self.glow(b, 0.55)
        self.glow(hot, 1.6)
        self.glow(burst, 6.0)
        self.glow(e - 2, 7.0)
        self.boil(boil0, e, "runaway", rate=1)
        self.chain(b, e + 1, 0.6, 3.2, seed=4)                        # the chain reaction runs away
        self.steam_burst(burst, e, "runaway_steam")
        flash(self.beacon_mat, burst, e)
        ld = self.alarm.data
        f, on = burst, True
        while f < e:
            ld.energy = 900 if on else 0
            ld.keyframe_insert("energy", frame=f)
            toy.set_interpolation(ld, "energy", (f,), "CONSTANT")
            f += 4
            on = not on
        ld.energy = 0
        ld.keyframe_insert("energy", frame=e)
        toy.set_interpolation(ld, "energy", (e,), "CONSTANT")
        events.add(boil0, "boil", duration=e - boil0)
        events.add(burst, "alarm")
        events.add(burst + 2, "steam_hiss")
        # Max: proud... then runs back and cowers, hands over his head
        self.at(b, WORK, (CORE.x, 0, 0))
        self.max.brows(hot + 4, 1.0)
        self.max.key("mouth", burst, scale=(1.2, 0.6, 2.6))
        hide = V((-3.75, -2.0, 0))
        self.max.walk(burst + 2, burst + 14, to=hide, facing_deg=facing_to(WORK, hide), step_frames=4)
        self.max.turn(burst + 15, facing_to(hide, (CORE.x, 0, 0)), frames=4)
        self.cower(burst + 17, e)
        self.rig.shot(b, e, cam_from=(-3.9, -6.4, 2.3), cam_to=(-3.8, -5.8, 2.2), aim_from=(-5.1, 0.1, 2.0),
                      aim_to=(-5.0, 0.1, 2.0), lens=24, fstop=8.0, cut=True)

    def a_control_rods(self, i, b, e):
        L = e - b
        self.glow(b, 7.0)
        self.boil(b, b + int(L * 0.5), "calming", rate=3)
        self.show(self.gantry, b + 2)
        toy.hide_tree(self.drive, b + 8, False)
        down0, down1 = b + int(L * 0.3), b + int(L * 0.6)
        self.rods(b, ROD_TOP_OUT)
        self.rods(down0, ROD_TOP_OUT)
        self.rods(down1, ROD_TOP_IN)
        self.glow(down0, 7.0)
        self.glow(down1 + 10, 0.55)                                   # tamed: a steady blue
        self.chain(b, down0, 3.0, 2.6, seed=5)
        self.chain(down0, down1 + 6, 2.6, 0.5, absorb0=0.1, absorb1=0.6, seed=6)   # the rods swallow neutrons
        self.chain(down1 + 6, self.EPI, 0.35, 0.35, absorb0=0.5, absorb1=0.5, seed=7)  # steady, under control
        events.add(down0, "rods_slide")
        label("CONTROL RODS", (CORE.x - 1.9, -0.3, 4.4), down0 + 2, e, size=0.24, tilt=-5)
        label("ABSORB NEUTRONS", (CORE.x - 1.6, -0.3, 3.85), down1, e, size=0.18, tilt=4, color="#5EC8FF",
              outline="#0A2A3A")
        arrow("rods_down", (CORE.x + 1.6, -0.4, 4.6), (0, 0, -1.4), down0, down1 + 12, color="#FFD23F")
        self.at(b, WORK, (CORE.x, 0, 0))
        self.max.point(down0, e - 4, hand="R", up_deg=55, side_deg=-25)
        self.max.smile(down1 + 10, big=True)
        self.rig.shot(b, e, cam_from=(-3.2, -7.4, 3.6), cam_to=(-3.6, -6.8, 3.4), aim_from=(-5.8, 0.2, 2.8),
                      aim_to=(-5.8, 0.2, 2.8), lens=22, fstop=8.0, cut=True)

    def a_fail_no_power(self, i, b, e):
        L = e - b
        bulb = self.props["bulb"]
        self.max.hold(bulb, "L")
        bulb.location = (0, -0.05, 0.12)
        toy.hide_tree(bulb, b, False)
        toy.hide_tree(bulb, e, True)
        spot = V((CORE.x + 1.9, -1.2, 0))
        self.at(b, spot, (CORE.x, 0.0, 0))
        up = b + int(L * 0.15)
        self.max.pose(up, shoulderL=(-115, 0, 25))                 # bulb held up to the glowing tank
        self.max.pose(up + int(L * 0.2), shoulderL=(-115, 0, 25))
        look = up + int(L * 0.25)
        self.max.turn(look, facing_to(spot, (spot.x - 1.2, -6, 0)), frames=6)   # ...turns to us with it
        self.max.pose(look + 6, shoulderL=(-150, 0, 10), head=(-8, 0, 0))       # holds it up by his face: dark
        for k in range(4):                                         # shakes it
            f = look + 14 + 4 * k
            self.max.pose(f, shoulderL=(-145, 0, 10 + (14 if k % 2 else -14)), head=(-8, 0, 0))
            events.add(f, "clink", gain=0.25)
        q = look + 34
        label("?", (spot.x + 0.15, spot.y - 0.2, 2.45), q, e, size=0.5, tilt=8, color="#FFD23F")
        events.add(q, "boing", gain=0.35)
        self.scratch_head(q + 2, e)
        self.rig.shot(b, e, cam_from=(-5.4, -4.6, 1.7), cam_to=(-5.2, -4.2, 1.65), aim_from=(-4.4, -0.6, 1.4),
                      aim_to=(-4.4, -0.6, 1.4), lens=26, fstop=8.0, cut=True)

    def a_turbine(self, i, b, e):
        L = e - b
        self.show(self.steam_pipe, b + 2)
        self.show(self.turbine_parts, b + 10)
        self.show(self.dead_end, b + 10, pop=False)
        flow0 = b + int(L * 0.35)
        key_node_value(self.steam_mat, "flow_on", flow0, 0.0)
        key_node_value(self.steam_mat, "flow_on", flow0 + 12, 1.0)
        spin0 = flow0 + 10
        self.spin(spin0, spin0 + 40, e)
        events.add(flow0, "steam_hiss", gain=0.5)
        events.add(spin0, "turbine", duration=e - spin0)
        events.add(spin0 + 30, "hum", duration=e - spin0 - 30, gain=0.6)
        lit = spin0 + 36
        self.light_bulb(self.lamp_mat, self.lamp_light, lit)          # the lamp wired to the generator lights up
        events.add(lit, "power_up", gain=0.7)
        label("TURBINE", (1.6, -0.2, 2.6), spin0, e, size=0.26, tilt=-5)
        label("GENERATOR", (3.4, -0.2, 2.55), spin0 + 8, e, size=0.24, tilt=5, color="#5EC8FF", outline="#0A2A3A")
        spot = V((4.3, -1.4, 0))
        self.at(b, spot, (5.0, -0.45, 0))
        self.max.smile(lit + 2, big=True)
        self.max.cheer(lit + 8, e - 2)
        self.rig.shot(b, e, cam_from=(-2.4, -10.0, 3.6), cam_to=(3.2, -5.8, 2.1), aim_from=(-2.4, 0.6, 2.2),
                      aim_to=(3.2, 0.4, 1.5), lens=22, fstop=8.0, cut=True)     # ends on turbine, generator AND the lamp

    def a_fail_pressure(self, i, b, e):
        L = e - b
        choke = b + int(L * 0.25)
        _key(self.needle, b, rotation_euler=V((0, R(-20), 0)))
        _key(self.needle, choke + int(L * 0.35), rotation_euler=V((0, R(105), 0)))  # deep into the red
        for k in range(6):                                                           # and quivering there
            _key(self.needle, choke + int(L * 0.35) + 3 + 3 * k, rotation_euler=V((0, R(105 + (5 if k % 2 else -5)), 0)))
        label("PRESSURE", self.gauge_center + V((0, -0.1, 0.72)), b + 4, e, size=0.22, tilt=-4)
        for k, at in enumerate(((TURB_X0 - 0.1, TURB_Y - 0.9, TURB_Z), (TURB_X1 + 0.1, TURB_Y - 0.9, TURB_Z),
                                (1.0, TURB_Y - 0.3, 0.5))):
            self.steam_burst(choke + 6 * k, e, f"leak{k}", at=at, rate=4, size=0.18, rise=0.9)
        # the turbine slows to a stop: hold the rotor from the choke and ease out
        stop = choke + int(L * 0.5)
        self.spin_on(b, choke)                                         # still spinning when the beat opens...
        v = toy.value_at(self.rotor, "rotation_euler", choke)[0]
        self.rotor.rotation_euler = (v + 2 * math.pi * SPIN * (stop - choke) / 2, 0, 0)   # ...then winds down
        self.rotor.keyframe_insert("rotation_euler", frame=stop)
        self.rotor.keyframe_insert("rotation_euler", frame=e)          # and stays stopped
        key_node_value(self.steam_mat, "flow_on", choke, 1.0)
        key_node_value(self.steam_mat, "flow_on", stop, 0.0)
        events.add(choke, "steam_hiss")
        events.add(choke + 20, "steam_hiss", gain=0.7)
        events.add(b, "turbine", duration=choke - b + 10, gain=0.7)
        spot = V((2.0, -1.1, 0))
        self.at(b, spot, (1.0, TURB_Y, 0))
        self.cover_ears(choke + 4, e - 2)
        self.rig.shot(b, e, cam_from=(1.0, -5.6, 2.3), cam_to=(0.9, -5.1, 2.25), aim_from=(1.0, 0.0, 1.8),
                      aim_to=(0.9, 0.0, 1.8), lens=24, fstop=8.0, cut=True)

    def a_cooling(self, i, b, e):
        L = e - b
        _key(self.needle, b, rotation_euler=V((0, R(105), 0)))
        _key(self.needle, b + int(L * 0.6), rotation_euler=V((0, R(-20), 0)))       # back to green
        for o in self.dead_end:
            _hide(o, b + 4, True)
        _appear(self.condenser, b + 4, frames=8)
        for k, o in enumerate(self.loop_pipes):
            _appear(o, b + 10 + k % 8, frames=6)
        self.tower.scale = (1, 1, 1)
        _hide(self.tower, 0, True)
        _hide(self.tower, b + 14, False)
        _key(self.tower, b + 14, scale=V((1, 1, 0.02)))
        _key(self.tower, b + 14 + int(L * 0.3), scale=V((1, 1, 1)))
        run = b + int(L * 0.5)
        key_node_value(self.cold_mat, "flow_on", run, 0.0)
        key_node_value(self.cold_mat, "flow_on", run + 12, 1.0)
        key_node_value(self.steam_mat, "flow_on", run, 0.0)
        key_node_value(self.steam_mat, "flow_on", run + 12, 1.0)
        self.spin(run, run + 30, self.total + 400)                     # running for good
        Puffs("plume", "#F7F7F7", count=26, size=1.1, seed=11).emit(
            range(run + 6, self.total + 400, 5), lambda f: (TOWER.x, TOWER.y, TOWER_H + 0.3), rise=3.2, life=48,
            drift=0.9)
        events.add(b + 14, "spray", duration=int(L * 0.3), gain=0.5)
        events.add(run, "pump", duration=e - run)
        events.add(run + 6, "turbine", duration=e - run - 6, gain=0.6)
        label("CONDENSER", (1.0, -0.3, 0.95), b + 10, e, size=0.24, tilt=-4, color="#5EC8FF", outline="#0A2A3A")
        label("COOLING TOWER", (TOWER.x - 1.4, TOWER.y - 3.6, 5.2), b + 20, e, size=0.42, tilt=4)
        label("WATER VAPOUR", (TOWER.x + 0.6, TOWER.y - 3.0, TOWER_H + 1.6), run + 20, e, size=0.36, tilt=-5,
              color="#FFFFFF", outline="#203040")
        spot = V((5.2, -1.4, 0))
        self.at(b, spot, (TOWER.x, TOWER.y, 0))
        self.max.point(b + int(L * 0.4), e - 4, hand="R", up_deg=55, side_deg=10)
        self.rig.shot(b, e, cam_from=(3.0, -12.6, 3.2), cam_to=(4.6, -13.2, 4.6), aim_from=(3.2, 1.5, 3.0),
                      aim_to=(4.6, 2.5, 4.6), lens=22, fstop=8.0, cut=True)

    def a_fail_geiger(self, i, b, e):
        L = e - b
        g = self.props["geiger"]
        self.max.hold(g, "R")
        toy.hide_tree(g, b, False)
        toy.hide_tree(g, e, True)
        start, near = V((-2.6, -1.9, 0)), V((-4.6, -1.4, 0))
        self.at(b, start, (CORE.x, 0, 0))
        reach = b + int(L * 0.5)
        self.max.walk(b + 4, reach, to=near, facing_deg=facing_to(start, near), step_frames=10)
        self.max.pose(b + 6, shoulderR=(-70, 0, 10))
        self.max.brows(reach - 6, 1.0)
        self.max.key("mouth", reach, scale=(1.1, 0.6, 2.2))
        back = near + V((1.4, -0.7, 0))
        self.max.walk(reach + 10, e - 4, to=back, facing_deg=facing_to(near, CORE), step_frames=12)   # backs away
        f, gap = b + 4, 14.0                                           # clicks speed up as he gets closer
        while f < e - 2:
            events.add(int(f), "geiger", gain=0.8)
            key_node_value(self.led_mat, "glow", int(f) - 1, 0.0, "CONSTANT")
            key_node_value(self.led_mat, "glow", int(f), 14.0, "CONSTANT")
            key_node_value(self.led_mat, "glow", int(f) + 1, 0.0, "CONSTANT")
            gap = max(2.0, gap * (0.82 if f < reach else 1.18))
            f += gap
        self.radiation(b + 2, e + 1, 2.2, lambda f: 4.2, seed=8)          # radiation streams out of the core
        toy.hide_tree(self.sign, b + int(L * 0.3), False)
        toy.hide_tree(self.sign, self.total + 400, True)
        _key(self.sign, b + int(L * 0.3), scale=V((0.01, 0.01, 0.01)))
        _key(self.sign, b + int(L * 0.3) + 6, scale=V((1.1, 1.1, 1.1)))
        _key(self.sign, b + int(L * 0.3) + 9, scale=V((1, 1, 1)))
        events.add(b + int(L * 0.3), "pop", gain=0.5)
        label("RADIATION", (CORE.x + 0.2, -1.0, 4.5), b + int(L * 0.3) + 4, e, size=0.26, tilt=-4, color="#D7FF3C",
              outline="#2A3300")
        self.rig.shot(b, e, cam_from=(-3.0, -5.8, 1.8), cam_to=(-3.3, -5.3, 1.75), aim_from=(-4.4, -0.3, 1.4),
                      aim_to=(-4.8, -0.3, 1.5), lens=24, fstop=8.0, cut=True)

    def a_containment(self, i, b, e):
        L = e - b
        toy.hide_tree(self.contain_root, b + 2, False)
        root = self.contain_root
        _key(root, b + 2, scale=V((1, 1, 0.02)))
        _key(root, b + 2 + int(L * 0.55), scale=V((1, 1, 1)))
        events.add(b + 2, "spray", duration=int(L * 0.5), gain=0.6)
        events.add(b + 2 + int(L * 0.55), "dump", gain=0.6)
        label("CONTAINMENT", (CORE.x - 3.3, -1.0, 5.6), b + int(L * 0.5), e, size=0.42, tilt=-4)   # beside the dome, clear of stickers
        label("1 M OF CONCRETE", (CORE.x + 2.2, -1.0, 3.2), b + int(L * 0.62), e, size=0.24, tilt=5, color="#FFFFFF",
              outline="#203040")
        g = self.props["geiger"]
        self.max.hold(g, "R")
        toy.hide_tree(g, b, False)
        toy.hide_tree(g, e, True)
        spot = V((-2.4, -2.2, 0))
        self.at(b, spot, (CORE.x, 0, 0))
        self.max.pose(b + 6, shoulderR=(-70, 0, 10))
        quiet = b + 2 + int(L * 0.55)
        f, gap = b + 2, 3.0
        while f < quiet:                                              # the clicks die away as the walls rise
            events.add(int(f), "geiger", gain=0.6)
            key_node_value(self.led_mat, "glow", int(f) - 1, 0.0, "CONSTANT")
            key_node_value(self.led_mat, "glow", int(f), 14.0, "CONSTANT")
            key_node_value(self.led_mat, "glow", int(f) + 1, 0.0, "CONSTANT")
            gap *= 1.25
            f += gap
        # the radiation now stops at the wall (the rising wall's inner face, ~2.2 m from the core)
        self.radiation(b + 2, quiet + 30, 2.0, lambda f: 4.2 if f < b + 2 + int(L * 0.3) else 2.0, seed=9)
        toy.hide_tree(self.sign, quiet + 10, True)
        self.max.smile(quiet + 4, big=True)
        self.max.turn(quiet + 6, 0, frames=6)
        self.max.pose(quiet + 12, shoulderL=(-90, 0, 20))           # thumbs up
        self.rig.shot(b, e, cam_from=(-2.2, -12.0, 3.6), cam_to=(-2.8, -11.2, 4.4), aim_from=(-5.6, 0.5, 3.4),
                      aim_to=(-5.4, 0.5, 4.0), lens=22, fstop=8.0, cut=True)

    def _night_town(self, f0, f1, lever=True):
        L = f1 - f0
        self.light(f0, sun_e=0.35, bg_v=0.04, fill_e=220)
        for o in self.props["lever"]:
            toy.hide_tree(o, f0, False)
        pull = f0 + int(L * 0.18)
        if lever:
            _key(self.lever, pull, rotation_euler=V((R(-35), 0, 0)))
            _key(self.lever, pull + 6, rotation_euler=V((R(35), 0, 0)))
            events.add(pull + 4, "switch")
        key_node_value(self.wire_mat, "flow_on", pull + 4, 0.0)
        key_node_value(self.wire_mat, "flow_on", pull + 14, 1.0)
        events.add(pull + 6, "power_up")
        for k, wm in enumerate(self.window_mats):                     # house by house
            f = pull + 18 + 6 * k
            key_node_value(wm, "glow", f0, 0.0)
            key_node_value(wm, "glow", f, 0.0)
            key_node_value(wm, "glow", f + 3, 9.0)
            events.add(f, "pop", gain=0.3)
        self.glow(f0, 0.55)
        return pull

    def a_finale(self, i, b, e):
        L = e - b
        pull = self._night_town(b, e)
        spot = FIN_SPOT
        self.at(b, spot, spot + V((1, 0, 0)))
        self.max.pose(pull - 4, shoulderR=(-60, 0, 10))
        self.max.pose(pull + 6, shoulderR=(-20, 0, 10))
        self.max.turn(pull + 24, facing_to(spot, TOWN_AIM), frames=8)
        self.max.cheer(pull + 40, e)
        self.max.smile(pull + 30, big=True)
        for k, kid in enumerate(self.kids):
            ks = FIN_SPOT + V((-0.8 - 0.7 * k, -0.4 - 0.3 * k, 0))
            toy.hide_tree(kid.root, b, False)
            kid.cut_place(b, ks, facing_to(ks, TOWN_AIM))
            kid.pose(b + 4)
            kid.cheer(pull + 30 + 4 * k, e)
            kid.smile(pull + 30, big=True)
            kid.auto_blink(b, e + 400, seed=k + 3)
        events.add(pull + 34, "kids_cheer")
        self.rig.shot(b, e, cam_from=(12.0, -9.4, 4.4), cam_to=(12.3, -8.8, 4.2), aim_from=(15.2, 6.0, 1.3),
                      aim_to=(15.4, 6.2, 1.4), lens=24, fstop=8.0, cut=True)       # high: family below the lit town

    # ------------------- hooks (epilogue) -------------------

    def _open_reactor(self, f):
        """Hooks are staged after the finale: put the open, rod-less reactor back for a boil-over."""
        toy.hide_tree(self.contain_root, f, True)
        for o in self.gantry:
            toy.hide_tree(o, f, True)
        toy.hide_tree(self.drive, f, True)
        self.light(f)

    def a_boil_hook(self, i, h0, h1):
        L = h1 - h0
        self._open_reactor(h0)
        for k, wm in enumerate(self.window_mats):
            key_node_value(wm, "glow", h0, 0.0)
        for kid in self.kids:
            toy.hide_tree(kid.root, h0, True)
        self.glow(h0, 6.0)
        self.glow(h1, 7.0)
        self.boil(h0, h1, "hook", rate=1)
        self.steam_burst(h0, h1, "hook_steam", rate=2)
        flash(self.beacon_mat, h0, h1 + 2, period=8)
        ld = self.alarm.data
        f, on = h0, True
        while f < h1:
            ld.energy = 900 if on else 0
            ld.keyframe_insert("energy", frame=f)
            toy.set_interpolation(ld, "energy", (f,), "CONSTANT")
            f += 4
            on = not on
        events.add(h0, "alarm")
        events.add(h0 + 2, "boil", duration=L)
        events.add(h0 + 6, "steam_hiss", gain=0.8)
        peek = V((CORE.x + 1.25, -1.75, 0))                          # peeking out from beside the pad
        self.at(h0, peek, (CORE.x + 3, -6, 0))
        self.cower(h0 + 1, h1)
        self.chain(h0, h1 + 1, 2.4, 3.0, seed=10)
        self.max.blink([h0 + 18, h0 + 40])
        self.rig.shot(h0, h1, cam_from=(-4.4, -6.6, 2.0), cam_to=(-4.7, -5.6, 2.1), aim_from=(-5.5, 0.1, 2.2),
                      aim_to=(-5.5, 0.1, 2.3), lens=24, fstop=8.0, cut=True)

    def a_lights_hook(self, i, h0, h1):
        pull = self._night_town(h0, h1, lever=False)
        for k, kid in enumerate(self.kids):
            ks = FIN_SPOT + V((-0.8 - 0.7 * k, -0.4 - 0.3 * k, 0))
            toy.hide_tree(kid.root, h0, False)
            kid.cut_place(h0, ks, facing_to(ks, TOWN_AIM))
            kid.cheer(pull + 20, h1)
        spot = FIN_SPOT
        self.at(h0, spot, TOWN_AIM)
        self.max.cheer(pull + 24, h1)
        events.add(pull + 20, "kids_cheer")
        self.rig.shot(h0, h1, cam_from=(12.0, -9.6, 4.4), cam_to=(12.4, -8.8, 4.2), aim_from=(15.2, 6.0, 1.3),
                      aim_to=(15.4, 6.3, 1.4), lens=24, fstop=8.0, cut=True)
